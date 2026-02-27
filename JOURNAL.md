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

---

## 27.02.2026

- [x] Create [PCAP Exporter](https://github.com/RazorBest/pcap_exporter) for linking captured traffic data with Prometheus
- [x] Add IP and port masking to PCAP Exporter, to enable the publication of anonymized traffic metrics
- [x] Install two Bitcoin nodes: one with `v2transport=0`, and one with `v2transport=1`
- [x] Show the total traffic in Grafana, separated by inbound and outbound, for each node
- [x] Show the timestamps of the mined blocks in Grafana
- [x] Publish the Grafana dashboard on the internet

**Journal:**

I created 2 bitcoin-core nodes: one with encryption (Polybius), and one without (Epicurus). Both have their network metrics public on: https://bitcoin-grafana-viewer.duckdns.org. The plots also contain vertical blue lines that represent the timestamps of the mined blocks.

**Anonymization**: For the public data, the (IP, port) pairs were replaced with other random (IP, port) pairs. This is to discourage other people discovering my node's IP and altering the traffic measurements.

**Birds eye view**: For each node, I created a Grafana dashboard that tracks:
- Total inbound traffic bytes
- Total outbound traffic bytes
- Inbound bandwidth in bytes/s
- Outbound bandwidth in bytes/s

Finally, I plotted the block mining times, since one assumption was that when a block gets mined, more traffic gets generated.

By looking at the dashboards, the following observations can be made:
- The inbound traffic is higher than the outbound one
- Spikes in the inbound traffic are very proeminent (usually, there's an x2.5 increase)
- The outbound traffic doesn't have observable spikes
- There isn't a definitive correlation between the mined block timestamp and the spikes in the inbound traffic

The inbound traffic is higher because we're running a listening node. This is a cause of the simple fact that we have more peers that started a connection to us.

We don't know why the outbound traffic is less eventful. My hyptothesis is that, since the outbound traffic represents connections to other listenting nodes, you don't need to pass inv messages to all of them. Whereas, for the inbound nodes, there is a high probability that they're non-listening, and my node acts as an "edge node" that sends all the needed blockchain data.

Finally, one reason the traffic doesn't correlate strongly with the timestamp of the mined blocks might have multiple reasons:
- We fetch data every 10 seconds from a public API, so it might happen that we fetch stale blocks
- The timestamp is chosen by the miner, and doesn't reflect the exact time the block was relayed to the other nodes.
- Some blocks have a small number of transactions, so the node needs to do less fetches

**Plan:**

The next step is to identify which types of messages are sent, and test the hypotheses presented above.

In order to identify the messages in the encrypted traffic, we have two ways:
- Perform a MitM
- Parse the debug.log

I will choose the first method, and use [libnetfilter_queue](https://www.netfilter.org/projects/libnetfilter_queue/index.html), since libpcap only does capturing, but not interception.

The data analysis part will be done in Python.

Next steps are:
- Intercep traffic
- Perform MitM and decrypt the BIP-324 packets
- Identify important types of messages
- Determine when a new block is mined, based on the messages
- Correlate and plot
- Play with the semi-passive adversary idea

