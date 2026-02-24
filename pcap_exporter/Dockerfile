FROM rust:1.93.1-slim AS builder

# Install git (required for cargo install --git), and libpcap (required by pcap_exporter)
RUN apt-get update && apt-get install -y git libpcap-dev && rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/RazorBest/pcap_exporter
RUN cargo install --locked --path pcap_exporter
RUN ldd /usr/bin/pcap_exporter | grep libpcap.so | awk '{print $3}' > libpcap_location

FROM debian:trixie-slim

RUN apt-get update && apt-get install -y libpcap-dev && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/local/cargo/bin/pcap_exporter /usr/bin/pcap_exporter

