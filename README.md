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

You can also check [the node setup](/docs/setup-node.md) commands that were used for this project.

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

## Documentation
- [Project scope](/docs/scope.md):
- [Node setup](/docs/setup-node.md):
- [Experiment setup](/docs/experiment-setup.md)

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
