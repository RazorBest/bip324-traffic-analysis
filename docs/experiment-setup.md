## Setting up a tcpdump sniffer

First, we need to know our network interfaces, by running `ip a s`. My machine
has two interfaces: eth0, and eth1. That's because Digital Ocean connects
my machines to an internal network. Since we only care about packets going
over the internet, we run `ip route | grep default` to find the IP of the
default gateway, and we corelate that with the output of `ip a s`. In my case,
the IP of the default gateway was configured on `eth0`. The machine is also
configured such that the on IP of the interface is the same as the IP used
on the internet.

---

To get a view of the active connections, we can run `ss -ap state established | grep $(pidof bitcoind)`.
However, this includes both inbound and outbound ports. We can differentiate
between them, when the TCP connection is made with `<HOST_IP>:8333`.

For seeing the outbound connections of our bitcoin node, we can run:
```
ss -ap state established '( sport != :8333 )' | grep $(pidof bitcoind)
```

And, for seeing the inbound connections:
```
ss -ap state established '( sport == :8333 )' | grep $(pidof bitcoind)
```

My node currently has 10 outbound and 23 inbound connections.

---

I'm running the tcpdump command from root, but storing the pcap in /home/btc. Here's the command:
```
tcpdump -i eth0 port 8333 -w /home/btc/bitcoin_pcap/capture.pcap -Z btc
```

This captures both inbound and outbund P2P packets, and downgrades to the user btc. My system has an apparmor configuration that limits tcpdump from doing some stuff, including writing files outside the home directory. So, that's why `-Z btc` was needed.

---

## Running netcap (outdated)

I eventually gave up netcap. But these are the notes that I've written, before taking that decision.

I followed this guide, in order to install and run netcap: https://docs.netcap.io/docker-containers.

```
docker pull dreadl0ck/netcap:ubuntu-v0.7.6
docker run --rm -ti --network=host -v /home/btc/netcap_data:/netcap/data dreadl0ck/netcap:ubuntu-v0.7.6 bash
```

I used docker because when I tried running the naked binary, it required some dependencies which were not straightforward to installed. I figured out its better to have a reproduciable setup (for starting new machines or resetting them), so Docker was the next best option. If I knew NixOS, I would've probably tried that.

go build -tags nodpi -ldflags "-s -w" -o .local/bin/net github.com/dreadl0ck/netcap/cmd

It turns out netcap has some errors. One of them being that a metric was registered twice in Prometheus. That was not the first issue I encountered, so I decided that netcap is not stable enough.

---

## Implementing your own network capture app

I wanted to streamline the visualization of my captured data, so I turned to
Grafana, since it has easy to use out-of-the-box plots. I first used (network-traffic-metrics)[https://github.com/zaneclaes/network-traffic-metrics],
which is a Python script that calls `tcpdump` with `subprocess`, and parses the data into some useful metrics, which are serialized for Prometheus, and served as a HTTP server.
Basically, the script takes the role of a sensor, which Prometheus instance can probe periodically.

The Python script was nice, until I realised that I want to also record the ports in the metrics. Since the script
was so small, my head said: "Running tcpdump as a subprocess and reading from stdout has an overhead. Why don't we use libpcap directly? Why not rebuild it in Rust?". And that's what I did.
That's how the **Pcap exporter** project was born: https://github.com/RazorBest/pcap_exporter.

Rust has a wrapper for libpcap called `pcap`, which is pretty to use. My Rust CLI application
does something similar to what network-traffic-metrics is doing, but also:
- Registers a source and destination ports as metric labels
- Lets the user add custom labels with constant values, for differentiating sensors.
- Masks port or (IP, port) pairs for an increase in anonymity. An `(IP, port)` pair will be mapped to the same `(IP', port')` pair between runs, as long as the same seed stored in its data directory is used.

---

### Anonymization

I wanted to make the measurements public. However, I didn't want the IP of my nodes to be public,
since this creates the risk of a bias, from someone that discovers that the nodes
are used to gather data about the network traffic.

I arrived to a solution that is not secure, but it does the job, assuming the small
scale of this project: masking. So, in the public metrics, I replaced all the (IP, port)
pairs with a different (IP, port) pair. Morover, I want this mapping to be deterministic
and saved between runs. So, if I map (127.0.0.1, 80) to (1.2.240.3, 10458) the first time,
the next time, that pair should be mapped to the same value. And, even if I restart
the Pcap Exporter, the mapping should preserved. This problem can generally be solved
by randomly choosing a unique value, and then storing that mapping on the disk. This scales
with the number of (IP, port) pairs that the exporter has ever seen. The alternative
to this is to use a random bijective function.

The term used in cryptography is Pseudo Random Permutation (PRP), and it refers to
an algorithm that generates pseurandom bijective functions same domain as the input.
However, we don't want to construct this algorithm from scratch. We want to use
existing block ciphers, which are generators of PRPs. The issue is that block
cipher usually have a predefined input size. This particular problem is solved
by algorithms called Format Preserving Encryption. If you don't need something
very serious (which was my case), (Ciphers with Arbitrary Finite Domains, by Black & Rogaway)[https://www.cs.ucdavis.edu/~rogaway/papers/subset.pdf]
is a very good paper that gives an overview on how to implement a Format
Preserving Encryption.

For masking (IPv6, port), you need a 144-bit Format Preserving Encryption. But
the AES block cipher works on 128 bits. To solve this, I used a trick that is
not presented in the paper, but it's similar to their last construction.  
AES-CTS (Ciphertext stealing, defined in NIST SP 800-38A) turns AES into a
bijective cipher that maps N bits to N bits, assuming N >= 128. So, AES-CTS is
a bijection. But not a random permutation, since a change in one of the input
bits doesn't always propagate to all the output bits - this is called diffusion.

But, just in Black & Rogaway's paper, you can make a construction that uses
more rounds, to add diffusion. My solution performs AES-CTS 10 times, which is
a downgrade from Black & Rogway's Feistel scheme with layers that mix the
sub-blocks. But it does the job, and it's easy to implement.

For masking (IPv4, port), you only need 48 bits, which can be done with a
lightweight block cipher. I used [Speck](https://eprint.iacr.org/2013/404) to solve that.

For masking just ports, it's easier to just hold the mapping in memory, in
an array of 65536 elements, each of size of 2 bytes.
