# Traffic analysis of post-BIP324 P2P Bitcoin traffic

<p align="center">
<img width="318" height="134" alt="correlation" src="https://github.com/user-attachments/assets/b6aa22fb-1389-4dfe-9fa7-f881d58fe127" />
</p>

## Project Layout

This project consists of:
- This current repo
- [Pcap exporter](https://github.com/RazorBest/pcap_exporter), which was specifically made for this project
- [BIP324 MITM](https://github.com/RazorBest/bip324-mitm)

## Installation

### Prerequisites
- Docker: https://docs.docker.com/engine/install/
- Bitcoin-core: https://bitcoin.org/en/bitcoin-core/

You can also check [the node setup](/setup_node.md) commands that were used for this project.

### Installing the traffic capture containers

It is expected that you have a running bitcoin node on mainnet. Check
that the `command` from `pcap_exporter` service in `compose.yml` matches your
node's network parameters.

Copy the `/example_env_file` into `/.env`, and change the environment variables:
| Variable | Description |
| --- | --- |
| `HOST_IP` | The IP of the interface that is monitored by Pcap exporter. This is the IP that you get by running `ip a s`, and looking at the correct interface (e.g. eth0). |
| `NODE_LABEL` | A name that is used to differentiate Prometheus metrics. It's useful when you deploy this project on multiple machines, each one running a different Bitcoin node. |
| `PUBLISH_SECRET_KEY_FILE` | An absolute path to the secret key used for publishing on GitHub. |
| `PUBLISH_METRICS_REPO` | The repository on which metrics are published by Pcap Publisher. |
| `GITNAME` | The `git config user.name` used by Pcap Publisher. |
| `GITEMAIL` | The `git config user.email` used by Pcap Publisher. |

Finally, run
```sh
docker compose up -d
```

Check that your containers are up, by running `docker ps`, and that the Prometheus
dashboard is available at `127.0.0.1:9090`.

### Installing the Grafana containers

Copy the `/grafana/example_env_file` into `/grafana/.env`, and change the environment variables:
| Variable | Description |
| --- | --- |
| `GF_SECURITY_ADMIN_PASSWORD` | The admin password of the Grafana dashboard. MAKE SURE YOU REPLACE THE DEFAULT. |
| `GF_SERVER_ROOT_URL` | The URL that is used to expose the app on the internet. If you don't need this, it can be any URL. |
| `CADDY_PUBLIC_DOMAIN` | The URL domain, used by Caddy to set up the TLS certificate. |
| `PROMETHEUS_URL` | The URL of the Prometheus instance, which must be accessible by Grafana's container. |
| `PROMETHEUS_DATASOURCE_TIME_INTERVAL` | The time interval granularity which Grafana should query Prometheus for. It makes sense to be at least as big as the `scrape_interval` option in prometheus.yml. |

Finally, run
```sh
docker compose -f grafana/grafana-compose.yml up -d
```

Check that your containers are up, by running `docker ps`, and that the Grafana
app is exposed on ports 80 and 443, on your domain.

> [!CAUTION]
> This part exposes your Grafana app to the public internet. Everyone will have access to it as an anonymous user. Users can't change the dashboards, but they can see the queries, and what data is returned by Prometheus. Also, users can cause Denial of Service to the Prometheus server.

## Infrastructure

This repo contains two docker compose configurations.

**The TCP capture infrastructure:**
- Configuration stored in `compose.yml`
- Pcap Exporter: attached to the host's network, monitoring the traffic and storing the data.
- Pcap Publisher: uploads periodically to github, the exact same file served by the PCAP Exporter's webserver.
- Prometheus: Periodically queries the Pcap Exporter webserver and stores the metrics

Currently, there are two running nodes:
| Name | Properties | Region |
| --- | --- | --- |
| Epicurus | bitcoin-core:v28.1.0; prune=5000; server=1; v2transport=0 | EU |
| Polybius | bitcoin-core:v28.1.0; prune=5000; server=1; v2transport=1 | EU |

Epicurus doesn't support v2transport. So hopefully, all the communication is not encrypted.
On the other hand, Polybius supports v2transport. This, however, doesn't necessarily
mean that all the packets are encrypted, since it depends whether the other peer supports v2transport.

Currently, the publisher updates the repositories every 5 minutes:
- https://github.com/lutmis/pcap-sensor-prom-epicurus.
- https://github.com/lutmis/pcap-sensor-prom-polybius

These repositories can be plugged to your own Prometheus instance, if you want to collect the data.
The interval was deribelately set to 5 minutes, to add a little be of anonimity to the node.
Moreover, the IPs and ports were masked. The measurements are still separated by connections.
The host's IP was explicitly mapped to `1.1.1.1`.

---

**The Grafana capture infrastructure:**
- Configuration stored in `grafana/grafana-compose.yml`
- Grafana: it can connect to the Prometheus instance mentioned earlier.
- Caddy: reverse proxy configured to make the Grafana instance accessible from the internet

This Grafana instance was configured with an anonymous user that has access to
some already existing dashboards. It's the developer's job to specify the
correct Prometheus URL, and ensure that the containers can communicate with each
other. So, you will probably need to change `compose.yml` to expose the port
of the Prometheus instance. This project runs Prometheus on one machine, and
Grafana on a different machine, where the communication happens through a VPN.

## Scope

The purpose of this project is to have a working demo at the end of the month that:
- gathers traffic data from live connections
- processes the data
- gathers bitcoin-core logs
- extracts relevant events
- plots the measured data

Traffic analysis is a pretty broad concept. We need to define a security model,
and how BIP324 relates to that model.

The participants of the protocol are clients and servers. Some nodes are both
clients and servers. Some nodes run a bitcoin P2P service. Servers that run
bitcoin can also receive connections. Nodes that don't run a bitcoin,
but run a different service (either as a client or as a server), are called
"non-bitcoin" nodes.

### Passive adversary

An adversary can see the network traffic for one node, and also has access
to the live mempool and blockchain of a bitcoin node. The adversary is passive,
meaning that they can't alter the contents of the network packets.

The adversary can distinguish between the packets of different TCP connections,
but doesn't see the IPs and ports of those connections. With this, we're saying
that we don't care about IP based detection. Since, it's very easy to find the
IPs of listenting P2P nodes. And, no matter how much encryption is added to the
application layer, the simple fact that a user connects to one of those IPs is
a strong indicaton that the traffic between them is P2P bitcoin. This type of
identification is outside the scope of this project.

Similary, Tor traffic is outside of this project's scope, since BIP-324 doesn't
change the structure of a Tor connection.

We can distinguish between two types of passive adversaries:
- true-passive (or just passive) adversary: the traffic can be recorded, and the adversary can later analyse it offline, with 0 interactions on the victim's network
- semi-passive: the adversary is online and can delay and fragment packets, and close connections.

We include the semi-passive adversary in our model because, as far as I know, no protocol can prevent those type of interactions.
Delaying packets might give the adversary information about the causality between a sent packet and a recevied packet.

TLS is not immune against a semi-passive adversary, since it splits its payloads in "records" (https://tls12.xargs.org/#client-application-data/annotated), which
might reveal something about the internal state machine of the application. Let's look at a small example:

**Passive adversary:**
1. Victim sends 20 TLS records
2. Node replies with 2 records

**Same victim-server interaction, but with a semi-passive adversary:**
1. Victim sends 20 TLS records
2. Adversary intercepts, and sends only the first 10 records
3. Node replies with 1 record
4. Adversary sends the next 10 records of the victim
5. Node replies with 1 record

You can see that in both scenarios, the end state between the victim and the node is the same.
However, in the second scenario, the adversary gained additional information. They know that
the first reply record of the node is caused by the first 10 records of the victim.


### Bitcoin detection

Here we define what it means for an adversary to succeed. A first statement
would be: the adversary wins when, given a connection, they correctly identify
it as a bitcoin (P2P) connection.

But this is not enough. Let's consider the setup where all the connections
are P2P bitcoin, and the adversary knows this. Then, 100% of all the connections
are bitcoin, and the answer to the question is trivial.

A better definition is one based on indistiguishability in comparison to other
applications. The victim can choose to start one of two traffic generating applications.
Only one of these applications is bitcoin. Then, the adversary wins whenever it
successfully identifies if the bitcoin application was started.

With other words, the adversary wants to distinguish connection to bitcoin nodes,
from connections to non-bitcoin nodes.

Then, we specify applications that a bitcoin P2P connection could use as camouflage:
- HTTPS
- obfs4 (as mentioned in BIP-324)
- An application with cTLS enabled
- A random TCP stream generator


## Node setup

I wound up a Digital Ocean Ubuntu machine, with ssh access. I didn't want the
remote node to perform an IBD, so I copied the files from my local bitcoin-core
node.

```
rsync -r ~/.bitcoin <SSH_URI>:./bitcoin_copy
```

Then, on the remote:
```
cp bitcoin_copy/.bitcoin/{bitcoin.conf,blocks,chainstate} ~/.bitcoin/ -r

bitcoind -daemon -assumevalid=<block_id>
```

The assumevalid was used to ensure that the blocks before that id are not verified,
but it might not be necessary.

It turned out that `bitcoin.conf`, `blocks`, and `chainstate` files/directories are
enough to restore the state of a node.

To check that everything went well, we can run on the remote:
```
bitcoin-cli getblockchaininfo

{
  "chain": "main",
  "blocks": 936564,
  "headers": 936756,
  "bestblockhash": "00000000000000000001cc05a9e03dc7bed627c7235a758fa8a39bd520c14902",
  "difficulty": 125864590119494.3,
  "time": 1771078642,
  "mediantime": 1771075820,
  "verificationprogress": 0.9995438276836643,
  "initialblockdownload": true,
  "chainwork": "00000000000000000000000000000000000000010f3047a8539fca953498f4a6",
  "size_on_disk": 5151609407,
  "pruned": true,
  "pruneheight": 934019,
  "automatic_pruning": true,
  "prune_target_size": 5242880000,
  "warnings": [
  ]
}
```

This is how my bitcoin.conf looks:
```
main=1
prune=5000
# This is redundant but only allows your computer to access your node
rpcallowip=127.0.0.1
# Forces your node to accept rpc commands
server=1

[main]
```

Depending on how much space you have available on the disk, you might increase
the prune variable (or remove it at all). If you want to setup an archival node,
and need some numbers, you can check: https://publicnode.com/snapshots. Last time
I checked, you needed 700GB of disk.


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


## Running netcap (old)

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
