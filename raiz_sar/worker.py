"""RQ worker entry point: ``python -m raiz_sar.worker sar|ai``. One job at a time per worker."""

from __future__ import annotations

import sys

from redis import Redis
from rq import Queue, Worker

from .config import get_settings
from .jobs import reap_expired


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in ("sar", "ai"):
        print("usage: python -m raiz_sar.worker sar|ai", file=sys.stderr)
        return 2
    s = get_settings()
    reap_expired()  # recover jobs abandoned by a previous worker process
    conn = Redis.from_url(s.valkey_url)
    worker = Worker([Queue(argv[1], connection=conn)], connection=conn, name=None)
    worker.work(with_scheduler=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
