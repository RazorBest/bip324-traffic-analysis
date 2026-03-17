## Install Bitcoin-Core

```
wget https://bitcoin.org/bin/bitcoin-core-28.1/bitcoin-28.1-x86_64-linux-gnu.tar.gz
tar -xvf bitcoin-*.tar.gz
echo -e '\nexport PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
mkdir -p ~/.local/bin
for file in $(find $PWD/bitcoin-*/bin -type f); do ln -s $file ~/.local/bin/$(basename $file); done
```

## Install Docker

Reference: https://docs.docker.com/engine/install/ubuntu/

You need sudo here.

This assumes there's a user named btc.

```
# Add Docker's official GPG key:
sudo apt update
sudo apt install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo usermod -aG docker btc
```

## Run Bitcoin-Core with IBD skip

Assume you already have a Bitcoin node. Call that the source. If it's a pruned
node, then the new node must be pruned as well.

If this is your first node, you can't do an IBD skip. You can find bitcoin-core
snapshots on the internet, but they can't be trusted.

This is the bitcoin.conf in the `~/.bitcoin` directory:
```
main=1
prune=5000
# This is redundant but only allows your computer to access your node
rpcallowip=127.0.0.1
# Forces your node to accept rpc commands
server=1

[main]
v2transport=1 # Set to 0 if we don't want P2P encryption.
maxuploadtarget=1024 # Change this if you have a higher bandwidth limit
```

From the source, run:
```
bitcoin-cli stop # The files should stay the same while we perform the copy
rsync -r ~/.bitcoin <SSH_URI>:./bitcoin_copy
```

From the new node, run:
```
cp bitcoin_copy/.bitcoin/{bitcoin.conf,blocks,chainstate} ~/.bitcoin/ -r
bitcoind -daemon
```

Then, check that the new node is up, by running:
```
bitcoin-cli getblockchaininfo
```

Example output:
```
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

Depending on how much space you have available on the disk, you might increase
the prune variable (or remove it at all). If you want to setup an archival node,
and need some numbers, you can check: https://publicnode.com/snapshots. Last time
I checked, you needed 700GB of disk.
