# Traffic analysis of post-BIP324 P2P Bitcoin traffic

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
