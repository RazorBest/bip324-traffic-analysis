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
