from __future__ import annotations

import argparse
import time
from typing import TYPE_CHECKING

import requests
from requests import RequestException
from prometheus_client import start_http_server, Info, Summary

if TYPE_CHECKING:
    import threading
    from typing import Optional

    from prometheus_client.exposition import ThreadingWSGIServer


MEMPOOL_API_URL = "https://mempool.space/api/v1/blocks"


class BlockTracker:
    def __init__(self, max_blocks_in_cache=288):
        self.blocks = []
        self.max_blocks_in_cache = max_blocks_in_cache
        self.metric_generator_info = Info("bitcoin_block_info", "Information about a bitcoin block", ["height"])

    @staticmethod
    def get_block_batch(from_height: Optional[int] = None) -> list[dict]:
        """Returns blocks starting from `from_height` and before. The amount
        depends on the API's defaults. For mempool, this is 10.

        Args:
            from_height: From which block to look back.

        Returns:
            A list of blocks as parsed JSON, from the API.
        """
        from_height = from_height if from_height is not None else ""
        response = requests.get(f"{MEMPOOL_API_URL}/{from_height}")
        response.raise_for_status()

        blocks = response.json()

        return blocks

    def get_last_block_height_in_cache(self) -> int:
        """Returns the max height of the blocks in the block cache."""
        if len(self.blocks) == 0:
            return 0

        return int(self.blocks[-1]["height"])

    def _update_blocks_cache(self, blocks: list[dict]) -> None:
        """Updates the cache with the new blocks by trying to glue the new ones
        to the existing ones, and limiting the cache to the last blocks, up to
        self.max_blocks_in_cache.

        If the new blocks can't be glued due to a gap (missing blocks), an
        exception is thrown.
        """
        blocks = sorted(blocks, key=lambda b: int(b["height"]))
        last_known_height = self.get_last_block_height_in_cache()
        if last_known_height < int(blocks[0]["height"]):
            if len(blocks) < self.max_blocks_in_cache:
                raise Exception("Can't update block cache. Blocks are missing.")

            self.blocks = blocks
        else:
            split_pos = last_known_height - int(blocks[0]["height"]) + 1
            self.blocks += blocks[split_pos:]

        self.blocks = self.blocks[-self.max_blocks_in_cache :]

        self.metric_generator_info.clear()
        for block in self.blocks:
            m = self.metric_generator_info.labels(height=str(block["height"]))
            m.info({"timestamp": str(block["timestamp"])})

    def get_recent_blocks(self, last_n: int) -> dict:
        """Fetches the most recent Bitcoin blocks and their mined times.

        Args:
            last_n: Get this amount last blocks.

        Returns:
            The blocks obtained from the mempool API, as JSON.
        """
        if last_n > self.max_blocks_in_cache:
            raise Exception("Can't request more blocks than the cache limit")

        blocks = self.get_block_batch()
        blocks.sort(key=lambda b: int(b["height"]))
        blocks_stack = blocks

        last_known_height = self.get_last_block_height_in_cache()
        while last_known_height < blocks_stack[0]["height"] and len(blocks_stack) < self.max_blocks_in_cache:
            blocks = self.get_block_batch(int(blocks_stack[0]["height"]) - 1)
            blocks.sort(key=lambda b: int(b["height"]))
            blocks_stack = blocks + blocks_stack
            time.sleep(0.5)

        self._update_blocks_cache(blocks_stack)

        return self.blocks[-last_n:]


def run_exporter(server: ThreadingWSGIServer, server_thread: threading.Thread) -> None:
    request_time_interval = 60  # seconds
    """
    metric_generator_binfo = Info("bitcoin_block_info", "Information about a bitcoin block", ["height"])

    m = metric_generator_binfo.labels(height=str("dsadjksald"))
    m.info({"timestamp": "dsdsada"})
    """

    block_tracker = BlockTracker(max_blocks_in_cache=288)

    while server_thread.is_alive():
        # Fetch blocks from last day
        block_tracker.get_recent_blocks(144)
        time.sleep(request_time_interval)

    server.shutdown()
    server.server_close()
    server_thread.join()


def parse_args():
    parser = argparse.ArgumentParser(
        prog="Block Exporter",
        description="Streams data about the Bitcoin Blockhain",
    )

    parser.add_argument("--host", default="127.0.0.1", help="Hostname of the web server")
    parser.add_argument("-p", "--port", type=int, default=8000, help="Port of the web server")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server, thread = start_http_server(addr=args.host, port=args.port)
    run_exporter(server, thread)


if __name__ == "__main__":
    main()
