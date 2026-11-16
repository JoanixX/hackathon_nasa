"""RQ worker entry point: ``python -m raiz_sar.worker <queue>[,<queue>...]``. One job at a time per worker.

Queues are taken in the order given (earlier = higher priority): e.g. ``ai,evidence`` or ``evidence,sar``.
"""

from __future__ import annotations

import sys

from redis import Redis
from rq import Queue, Worker

from .config import get_settings
from .jobs import reap_expired


def main(argv: list[str]) -> int:
    names = argv[1].split(",") if len(argv) == 2 else []
    if not names or any(n not in ("sar", "ai", "evidence") for n in names) or len(set(names)) != len(names):
        print("usage: python -m raiz_sar.worker sar|ai|evidence[,...]", file=sys.stderr)
        return 2
    s = get_settings()
    # RQ runs each job in a forked child: import the handlers (Gemini client, rasterio, GDAL) once here so
    # every child inherits them instead of re-importing (~1.4 s idle, minutes under CPU saturation).
    from . import sources, tasks  # noqa: F401
    import rasterio  # noqa: F401

    reap_expired()  # recover jobs abandoned by a previous worker process
    conn = Redis.from_url(s.valkey_url)
    worker = Worker([Queue(n, connection=conn) for n in names], connection=conn, name=None)
    worker.work(with_scheduler=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
