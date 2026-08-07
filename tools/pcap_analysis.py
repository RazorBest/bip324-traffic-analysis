from __future__ import annotations

import argparse
import dpkt
import glob
import hashlib
import logging
import os
import struct
from datetime import datetime, timezone
from io import BytesIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import BinaryIO, Optional

import matplotlib.pyplot as plt
import seaborn as sns
import warnet
from test_framework.p2p import MESSAGEMAP
from test_framework.messages import deser_string
from bitcoin.messages import msg_version, msg_tx, msg_block, MsgSerializable


class MsgAlert:
    def __init__(self):
        self.data = b""

    def deserialize(self, f: BytesIO):
        self.vch_msg = deser_string(f)
        self.vch_sig = deser_string(f)


MESSAGEMAP[b"alert"] = MsgAlert


DEBUG = False

def DEBUG_ON():
    global DEBUG
    DEBUG = True

def DEBUG_OFF():
    global DEBUG
    DEBUG = False


# Copied from: https://github.com/petertodd/python-bitcoinlib/blob/91e334d831fd16c60c932ad7df42c88fd6567c02/bitcoin/messages.py
def parse_p2p_message(data: bytes):
    idx = 0
    recvbuf = data[idx:idx+4+12+4+4]
    idx += 4+12+4+4

    # remaining header fields: command, msg length, checksum
    command = recvbuf[4:4+12].split(b"\x00", 1)[0]
    msglen = struct.unpack(b"<i", recvbuf[4+12:4+12+4])[0]
    checksum = recvbuf[4+12+4:4+12+4+4]

    # read message body
    if len(data[idx:]) < msglen:
        return None, 0
    recvbuf += data[idx:idx+msglen]
    idx += msglen

    msg = recvbuf[4+12+4+4:4+12+4+4+msglen]
    th = hashlib.sha256(msg).digest()
    h = hashlib.sha256(th).digest()
    if checksum != h[:4]:
        raise ValueError("got bad checksum %s" % repr(recvbuf))

    if command in MESSAGEMAP:
        cls = MESSAGEMAP[command]
        instance = cls()
        instance.deserialize(BytesIO(msg))

        return instance, len(recvbuf)
    else:
        print(f"Header: {data[:4+12+4+4]}")
        print(f"Data: {msg}")
        raise ValueError(f"Command '{command!r}' not in messagemap")


# ---------- START pcap.py -------------
# Copied from https://github.com/jonasoberschweiber/pypcap/blob/8b40cb1c637aebef13448cdef4a7518963cc28a3/pcap.py
PCAP_GLOBAL_HEADER_FORMAT = 'IHHiIII'
PCAP_GLOBAL_HEADER_LEN = 24
PCAP_PACKET_HEADER_FORMAT = 'IIII'
PCAP_PACKET_HEADER_LEN = 16

class PcapFile():
    def __init__(self, file):
        self.f = file
        header_data = self.f.read(PCAP_GLOBAL_HEADER_LEN)
        self.global_header = PcapGlobalHeader(header_data)
        self.prev_packet_header = None
        self.buffer = b""

    def undo_read(self, data: bytes):
        self.buffer = data + self.buffer

    def _read(self, size: int) -> bytes:
        # Buffered read
        data = self.buffer[:size]
        self.buffer = self.buffer[size:]
        size -= len(data)

        # Read from file
        data += self.f.read(size)

        return data

    def next_packet_header(self):
        header_data = self._read(PCAP_PACKET_HEADER_LEN)
        if len(header_data) == 0:
            return None

        packet_header = PcapPacket(header_data)
        return packet_header

    def next_packet(self, packet_header = None, payload_limit = None):
        if packet_header is None:
            packet_header = self.next_packet_header()

        if packet_header is None:
            return None

        payload_limit = payload_limit if payload_limit is not None else 100000000

        data = self._read(min(packet_header.incl_len, payload_limit))
        packet_header.data = data

        return packet_header

    def tell(self):
        return self.f.tell() - len(self.buffer)

class PcapGlobalHeader():
    def __init__(self, data):
        unpacked = struct.unpack(PCAP_GLOBAL_HEADER_FORMAT, data)
        self.magic_number = unpacked[0]
        self.swapped = self.magic_number != 0xa1b2c3d4
        self.version_major = unpacked[1]
        self.version_minor = unpacked[2]
        self.thiszone = unpacked[3]
        self.sigfigs = unpacked[4]
        self.snaplen = unpacked[5]
        self.network = unpacked[6]

        if self.thiszone != 0:
            raise ValueError("Can't handle non-zero thiszone values in pcap file")
        if self.sigfigs != 0:
            raise ValueError("Can't handle non-zero sigfig values in pcap file")

    def write(self, file):
        data = struct.pack(
            PCAP_GLOBAL_HEADER_FORMAT,
            self.magic_number, self.version_major, self.version_minor,
            self.thiszone, self.sigfigs, self.snaplen, self.network
        )
        file.write(data)

        return len(data)


class PcapPacket():
    def __init__(self, header_data):
        unpacked = struct.unpack(PCAP_PACKET_HEADER_FORMAT, header_data)
        self.raw_header = header_data
        self.ts_sec = unpacked[0]
        self.ts_usec = unpacked[1]
        self.incl_len = unpacked[2]
        self.orig_len = unpacked[3]
        self.data = b""

    def writable_size(self) -> int:
        return PCAP_PACKET_HEADER_LEN + len(self.data)

    def to_bytes(self):
        return struct.pack(PCAP_PACKET_HEADER_FORMAT,
            self.ts_sec, self.ts_usec, self.incl_len, self.orig_len
        ) + self.data

    def write(self, file):
        file.write(data := self.to_bytes())
        return len(data)


# ---------- END pcap.py -------------


def parse_args():
    parser = argparse.ArgumentParser(prog="pcap_analysis", description="Tool for analyzing pcap files taken from a Bitcoin P2P communication")
    parser.add_argument("capture_prefix", help='The pcap file prefix. If value set to "some_file", will search all "some_file.pcap*"')

    args = parser.parse_args()

    return args


def get_pcap_files(prefix: str) -> list[str]:
    return sorted(glob.glob(prefix + ".pcap*"))


def parse_packet(data: bytes):
    eth = dpkt.ethernet.Ethernet(data)
    if not isinstance(eth.data, dpkt.ip.IP):
        raise ValueError(f"Expected IP packet: {eth.data}")

    if not isinstance(eth.data.data, dpkt.tcp.TCP):
        raise ValueError(f"Expected TCP packet: {ip.data}")

    return eth


class BitcoinP2PProtocolException(Exception):
    pass


class BitcoinP2PProtocol:
    MAINNET_MAGIC = bytes.fromhex("f9beb4d9") 
    TESTNET_MAGIC = bytes.fromhex("0b110907") 
    REGTEST_MAGIC = bytes.fromhex("fabfb5da") 

    def __init__(self):
        self.network: Optional[bytes] = None
        self.messages = []
        self.buf = b""

        self.contains_magic = False
        self.invalid = False

    def parse_one_packet(self, dt: datetime, f: BytesIO) -> bool:
        self.buf += f.read()

        if len(self.buf) < 4:
            return False

        self.contains_magic |= self.data_has_magic(self.buf)

        if (magic := self.get_magic(self.buf)) is None:
            self.invalid = True
            raise BitcoinP2PProtocolException("Data is not P2P Bitcoin")

        if self.network is None:
            self.network = magic
        if self.network != magic:
            self.invalid = True
            raise BitcoinP2PProtocolException(f"Wrong magic. Expected: {self.network}. Received: {magic}")

        msg, read = parse_p2p_message(self.buf)
        self.buf = self.buf[read:]

        if msg is not None:
            self.messages.append((dt, read, msg))
            return True

        return False

    def push_data(self, dt: datetime, f: BytesIO):
        while self.parse_one_packet(dt, f):
            pass

    def started(self):
        return self.network is not None

    def data_has_magic(cls, data: bytes) -> bool:
        for magic in [cls.MAINNET_MAGIC, cls.TESTNET_MAGIC, cls.REGTEST_MAGIC]:
            if magic in data:
                return True
        
        return False

    @classmethod
    def get_magic(cls, data: bytes) -> Optional[bytes]:
        magics = [cls.MAINNET_MAGIC, cls.TESTNET_MAGIC, cls.REGTEST_MAGIC]
        try:
            idx = magics.index(data[:4])
            return magics[idx] if idx != -1 else None
        except ValueError:
            return None


class SessionAnalyserException(Exception):
    pass


class NewSYNPacket(SessionAnalyserException):
    pass


class WrongTCPSeq(SessionAnalyserException):
    pass


class SessionAnalyser:
    def __init__(self, src_ip: bytes, dst_ip: bytes, src_port: int, dst_port: int):
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.src_port = src_port
        self.dst_port = dst_port
        self.key = src_ip + dst_ip + b"////" + src_port.to_bytes(2, "big") + dst_port.to_bytes(2, "big")

        self.out_prev = None
        self.in_prev = None

        self.out_protocol = BitcoinP2PProtocol()
        self.in_protocol = BitcoinP2PProtocol()

        self.out_seq = None
        self.in_seq = None

        self.no_handshake = False

        self.events = []

        self.invalid = False

    def _push_packet_out(self, dt: datetime, tcp: dpkt.tcp.TCP):
        is_first = False
        if (tcp.flags & dpkt.tcp.TH_SYN) and not (tcp.flags & dpkt.tcp.TH_ACK):
            if self.out_prev is not None:
                raise NewSYNPacket("Can't receive second SYN packet for this session")

            is_first = True
            self.out_prev = tcp
            self.out_seq = tcp.seq + 1

        if self.out_prev is None:
            self.no_handshake = True
            return

        if not is_first and tcp.seq != self.out_seq:
            self.invalid = True
            raise WrongTCPSeq(f"Wrong TCP sequence number. Received - Expected: {tcp.seq - self.out_seq}")

        self.out_seq += len(tcp.data)

        if len(tcp.data) == 0:
            return

        if self.out_protocol is not None:
            try:
                self.out_protocol.push_data(dt, BytesIO(tcp.data))
                for _, size, msg in self.out_protocol.messages:
                    self.events.append({
                        "direction": "out",
                        "dt": dt,
                        "msg": msg,
                        "size": size,
                    })
                self.out_protocol.messages = []

            except BitcoinP2PProtocolException:
                if self.out_protocol.started():
                    raise

                self.out_protocol = None

    def _push_packet_in(self, dt: datetime, tcp: dpkt.tcp.TCP):
        is_first = False
        if (tcp.flags & dpkt.tcp.TH_SYN & dpkt.tcp.TH_ACK):
            if self.in_prev is not None:
                raise SessionAnalyserException("Can't receive second SYN/ACK packet for this session")

            is_first = True
            self.in_prev = tcp
            self.in_seq = tcp.seq + 1

        if self.in_prev is None:
            self.no_handshake = True
            return

        if not is_first and tcp.seq != self.in_seq:
            self.invalid = True
            raise WrongTCPSeq(f"Wrong TCP sequence number. Received - Expected: {tcp.seq - self.in_seq}")

        self.in_seq += len(tcp.data)

        if len(tcp.data) == 0:
            return

        if self.in_protocol is not None:
            try:
                if self.src_port == 40725:
                    print(f"Data in: {tcp.data}")
                self.in_protocol.push_data(dt, BytesIO(tcp.data))
                for _, size, msg in self.in_protocol.messages:
                    self.events.append({
                        "direction": "in",
                        "dt": dt,
                        "msg": msg,
                        "size": size,
                    })
                self.in_protocol.messages = []
            except BitcoinP2PProtocolException:
                if self.in_protocol.started():
                    raise

                self.in_protocol = None

    def push_packet(self, dt: datetime, tcp: dpkt.tcp.TCP):
        if self.src_port == tcp.sport and self.dst_port == tcp.dport:
            self._push_packet_out(dt, tcp)
        elif self.src_port == tcp.dport and self.dst_port == tcp.sport:
            self._push_packet_in(dt, tcp)
        else:
            raise SessionAnalyserException("Wrong TCP packet for the session. Mismatching ports.")

    def get_key(self):
        return self.key


def get_first_session_key(ip: dpkt.ip.IP, tcp: dpkt.tcp.TCP):
    return ip.src + ip.dst + b"////" + tcp.sport.to_bytes(2, "big") + tcp.dport.to_bytes(2, "big")


def get_second_session_key(ip: dpkt.ip.IP, tcp: dpkt.tcp.TCP):
    return ip.dst + ip.src + b"////" + tcp.dport.to_bytes(2, "big") + tcp.sport.to_bytes(2, "big")


def get_pcap_packet_datetime(packet: PcapPacket):
    d = datetime.fromtimestamp(packet.ts_sec, tz=timezone.utc)
    d = d.replace(microsecond=packet.ts_usec)

    return d


def analyse_opened_pcap_file(file: BinaryIO):
    pcap = PcapFile(file) 

    old_sessions = []
    sessions = {}

    while (packet := pcap.next_packet()) is not None:
        if len(packet.data) == 0:
            continue

        dt = get_pcap_packet_datetime(packet)
        eth = parse_packet(packet.data)
        ip = eth.data
        tcp = eth.data.data

        # --- Find session
        first_key = get_first_session_key(ip, tcp)
        second_key = get_second_session_key(ip, tcp)

        session = sessions.get(first_key)
        session = sessions.get(second_key, session)

        if session is None:
            session = SessionAnalyser(ip.src, ip.dst, tcp.sport, tcp.dport)
            sessions[session.get_key()] = session
        # ---

        try:
            session.push_packet(dt, tcp)
        except NewSYNPacket:
            del sessions[session.get_key()]
            old_sessions.append(session)

            session = SessionAnalyser(ip.src, ip.dst, tcp.sport, tcp.dport)
            sessions[session.get_key()] = session

            session.push_packet(dt, tcp)
        except BitcoinP2PProtocolException:
            pass
        except WrongTCPSeq:
            pass

    old_sessions.extend(sessions.values())

    non_bitcoin_sessions = 0
    corrupted_sessions = 0
    for session in old_sessions:
        if session.in_protocol is None or session.out_protocol is None:
            non_bitcoin_sessions += 1
        elif session.in_protocol.invalid or session.out_protocol.invalid:
            non_bitcoin_sessions += 1
            if session.in_protocol.contains_magic or session.out_protocol.contains_magic:
                corrupted_sessions += 1
        elif session.invalid:
            non_bitcoin_sessions += 1

    print(f"Total registered number of sessions: {len(old_sessions)}")
    print(f"Non Bitcoin P2P sessions: {non_bitcoin_sessions}")
    print(f"Corrupted sessions: {corrupted_sessions}")

    count = 0
    for session in old_sessions:
        if len(session.events) == 0:
            continue

        df = {"time": [], "packet_size": []}
        for entry in session.events:
            df["time"].append(entry["dt"])
            df["packet_size"].append(entry["size"])

        count += 1
        if count <= 1:
            continue

        sns.set(style="whitegrid") 
        plt.figure(figsize=(12, 5))

        plt.vlines(x=df["time"], ymin=0, ymax=df["packet_size"], alpha=0.5, linewidth=8)

        plt.xlabel("Time (seconds)")
        plt.ylabel("Packet Size (bytes)")
        plt.title("TCP Packet Timeline")
        plt.tight_layout()
        plt.savefig("tcp_timeline.svg", format="svg")

        exit(1)


def analyse_all_files(pcap_files: list[str]):
    for pcap_file in pcap_files:
        with open(pcap_file, "rb") as file:
            print(pcap_file)
            analyse_opened_pcap_file(file)

        break
    

def main():
    args = parse_args()
    pcap_files = get_pcap_files(args.capture_prefix)

    logging.info(f"Found {len(pcap_files)} pcap files")
    
    analyse_all_files(pcap_files)

if __name__ == "__main__":
    logging.basicConfig(format="%(message)s", level=logging.INFO)

    main()
