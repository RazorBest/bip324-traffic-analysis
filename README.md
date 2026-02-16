# Traffic analysis of post-BIP324 P2P Bitcoin traffic

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
