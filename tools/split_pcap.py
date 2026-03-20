import argparse
import glob
import os
import struct

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
    parser = argparse.ArgumentParser(prog="pcap_split", description="Tool for splitting a big pcap file into smaller ones")
    parser.add_argument("filename", help="The pcap file to read")
    parser.add_argument("--outdir", help="The directory in which to write the output pcap files. If not specified, the directory of the given file is used.")
    parser.add_argument("--reference-mac", action="append", dest="reference_macs", help="MAC address that can be used to identify Ethernet frames in order to recover corrupted PCAP files.")
    parser.add_argument("--chunks", type=int, default=100, help="The number of chunked files to write. If this limit is reached, the program stops without parsing the rest of the input file")
    parser.add_argument("--fseek", type=int, default=0,
        help="Offset to start reading the input file. This is applied after the global header is read."
    )
    parser.add_argument("--start", type=int, default=0,
        help="Where to start with the subfile counter"
    )

    args = parser.parse_args()

    args.reference_macs = [bytes.fromhex(mac) for mac in args.reference_macs]

    return args


def get_outfile_prefix(args):
    parent, base = os.path.split(args.filename)
    if args.outdir is not None:
        parent = args.outdir

    return os.path.join(parent, base)


def check_for_subfiles(filename: str):
    subfiles = glob.glob(filename + ".*" )
    if len(subfiles) > 0:
        print("Can't create new pcap subfiles. Existing files might be overwritten")
        print(f"Rename the input file or delete the following: {', '.join(subfiles[:10])}")
        exit(1)


def small_file_gen(prefix: str, global_header: PcapGlobalHeader, start: int = 0, end: int = None):
    counter = start
    while counter is None or counter < end:
        path = prefix + f".{counter:04}"
        file = open(path, "wb")
        size = global_header.write(file)
        yield file, size, path
        file.close()
        counter += 1


def resync(packet_header: PcapPacket, expected_macs: list[str], prev_packet: PcapPacket):
    # Skip the header, and the MAC destination+source of the Ethernet frame. We want to look for discrepancies in the previous packet by finding MACs where they shouldn't be
    prev_data = prev_packet.to_bytes()[PCAP_PACKET_HEADER_LEN:] if prev_packet is not None else b""
    data = prev_data + packet_header.to_bytes()

    best_idx = -1
    for mac in expected_macs:
        idx = data.find(mac, PCAP_PACKET_HEADER_LEN)
        if idx != -1 and (best_idx == -1 or idx < best_idx):
            best_idx = idx

    if best_idx == -1:
        raise Exception("Can't resync packet. No mac found")

    if best_idx < len(prev_data):
        prev_packet = None

    best_idx -= PCAP_PACKET_HEADER_LEN
    if best_idx < 0:
        raise Exception("Can't resync packet")

    unparsed_synced_data = data[best_idx:]
    lost = data[:best_idx]

    return prev_packet, unparsed_synced_data, lost


CORRUPTION_THRESHOLD = 70000
SIZE_PER_CHUNK = 1024 * 1024 * 50 # 50 MB


def split_pcap(args: argparse.ArgumentParser, prefix):
    if os.path.getsize(args.filename) < SIZE_PER_CHUNK:
        print("File is already small enough")
        return

    file = open(args.filename, "rb")
    pcap = PcapFile(file)
    file.seek(args.fseek)
    gen = small_file_gen(prefix, pcap.global_header, start=args.start, end=args.start+args.chunks)
    curr_file, curr_size, path = next(gen)

    prev_packet = None

    total_lost_bytes = 0

    while packet_header := pcap.next_packet_header():
        if packet_header.incl_len > CORRUPTION_THRESHOLD:
            print(f"Packet len: {packet_header.incl_len}")
            packet_header = pcap.next_packet(packet_header, 4096)
            prev_packet, data, lost = resync(packet_header, args.reference_macs, prev_packet)
            packet_header = None
            pcap.undo_read(data)

            packet_header = pcap.next_packet_header()
            if packet_header.incl_len > CORRUPTION_THRESHOLD:
                raise Exception("Couldn't recover corrupted packet")

            print(f"Lost bytes: {len(lost)}")
            total_lost_bytes += len(lost)

        packet = pcap.next_packet(packet_header)

        if prev_packet is not None:
            # Write prev_packet because only now we know whether it's corrupted or not
            # We need the current packet to determine whether the prev packet was corrupted
            if curr_size + prev_packet.writable_size() > SIZE_PER_CHUNK:
                print(f"Written chunk to: {path}")
                try:
                    curr_file, curr_size, path = next(gen)
                except StopIteration:
                    pcap.undo_read(packet.to_bytes())
                    pcap.undo_read(prev_packet.to_bytes())
                    packet = None
                    prev_packet = None
                    break

            curr_size += prev_packet.write(curr_file)

        prev_packet = packet

    if prev_packet is not None:
        if curr_size + prev_packet.writable_size() > SIZE_PER_CHUNK:
            print(f"Written chunk to: {path}")
            try:
                curr_file, curr_size, path = next(gen)
            except StopIteration:
                pcap.undo_read(prev_packet.to_bytes())
            else:
                curr_size += prev_packet.write(curr_file)
        else:
            curr_size += prev_packet.write(curr_file)

    print(f"Ftell: {pcap.tell()}")
    print(f"Total lost bytes: {total_lost_bytes}")


def main():
    args = parse_args()

    """
    file = open(args.filename, "rb")
    offset = 0x03661f4e - 1
    file.read(offset)

    print(file.read(8).hex())

    exit(1)
    """

    prefix = get_outfile_prefix(args)
    if args.start == 0:
        check_for_subfiles(prefix)
    split_pcap(args, prefix)

    print("")

if __name__ == "__main__":
    main()
