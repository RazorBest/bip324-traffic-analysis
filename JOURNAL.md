## 17.02.2026

- [x] Configure a Digital Ocean machine with a pruned node
- [x] Research on existing work about P2P analysis
- [x] Write the scope and plan for the project

**Journal:**

A recent podcast [with B10C](https://stephanlivera.com/episode/707/) helped me understand a bit about the progress made on P2P traffic analysis. This is how I found out about [bnox.xyz](https://bnoc.xyz/), a forum dedicated on publishing and discussing findings about the P2P nodes.

There's also [peer-observer](https://github.com/peer-observer/peer-observer): a framework for collecting metrics from a bitcoin node. This overlaps with some parts of our project, but I'm still not sure whether it's useful to include `peer-observer` in it.

There's also this previous work by virtu, related to P2P traffic analysis, split by types of messages: https://github.com/virtu/bitcoind-p2p-traffic/tree/master. I think this is a good inspiration to how to make plots.

I wrote the scope for the project, which includes defining what a passive adversary can do, and what it means for P2P traffic to be detected.

**Plan:**

Bitcoin-core supports some tracing: https://github.com/bitcoin/bitcoin/blob/29.x/doc/tracing.md, which can help us see in what state a node is. But I think it might be an overkill. Reading logs and network packets should be enough.

Next steps are:
- Connect a tcpdump instance to capture the running node's packets
- Test that we can look at the packets in Wireshark
- Make a plot that gives a birds-eye view of the traffic
- Get information about the internal state. I see this being done in two ways: either by reading the debug logs, or by performing a mitm over the encrypted channel, to get the actual contents of the packets
- Get in touch with B10C to get more insider knowledge
