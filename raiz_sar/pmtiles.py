"""PMTiles v3 reader over HTTP range requests (no dependency): header, directories, tile lookup.

Spec: https://github.com/protomaps/PMTiles/blob/main/spec/v3/spec.md . Only the byte ranges needed for the
requested tiles are fetched; directories are cached in memory per archive.
"""

from __future__ import annotations

import gzip
import struct
import threading
from typing import Any

import httpx

from . import upstream

_lock = threading.Lock()
_headers: dict[str, dict[str, Any]] = {}
_dirs: dict[tuple[str, int, int], list[tuple[int, int, int, int]]] = {}


def _get_range(url: str, offset: int, length: int) -> bytes:
    from .sources import http

    r = upstream.get(http(), url, headers={"Range": f"bytes={offset}-{offset + length - 1}"}, timeout=30)
    if r.status_code not in (200, 206):
        raise upstream.UpstreamError(f"PMTiles range HTTP {r.status_code}")
    return r.content if r.status_code == 206 else r.content[offset:offset + length]


def _decompress(data: bytes, comp: int) -> bytes:
    if comp in (0, 1):
        return data
    if comp == 2:
        return gzip.decompress(data)
    raise ValueError(f"unsupported PMTiles compression {comp}")


def header(url: str) -> dict[str, Any]:
    with _lock:
        if url in _headers:
            return _headers[url]
    b = _get_range(url, 0, 16384)
    if b[:7] != b"PMTiles" or b[7] != 3:
        raise ValueError("not a PMTiles v3 archive")
    q = struct.unpack_from("<11Q", b, 8)  # bytes 8..95
    h = {"root_offset": q[0], "root_length": q[1], "metadata_offset": q[2], "metadata_length": q[3],
         "leaf_offset": q[4], "leaf_length": q[5], "data_offset": q[6], "data_length": q[7],
         "addressed_tiles": q[8], "tile_entries": q[9], "tile_contents": q[10]}
    clustered, internal_c, tile_c, tile_type, minz, maxz = struct.unpack_from("<BBBBBB", b, 96)
    min_lon, min_lat, max_lon, max_lat = (v / 1e7 for v in struct.unpack_from("<iiii", b, 102))
    h.update(clustered=clustered, internal_compression=internal_c, tile_compression=tile_c, tile_type=tile_type,
             min_zoom=minz, max_zoom=maxz, bounds=[min_lon, min_lat, max_lon, max_lat], _first=b)
    with _lock:
        _headers[url] = h
    return h


def _varint(buf: bytes, i: int) -> tuple[int, int]:
    shift = res = 0
    while True:
        c = buf[i]
        i += 1
        res |= (c & 0x7F) << shift
        if not c & 0x80:
            return res, i
        shift += 7


def _directory(url: str, offset: int, length: int, comp: int) -> list[tuple[int, int, int, int]]:
    key = (url, offset, length)
    with _lock:
        if key in _dirs:
            return _dirs[key]
    h = header(url)
    raw = h["_first"][offset:offset + length] if offset + length <= len(h["_first"]) else _get_range(url, offset, length)
    buf = _decompress(raw, comp)
    i = 0
    n, i = _varint(buf, i)
    ids, runs, lens, offs = [], [], [], []
    last = 0
    for _ in range(n):
        v, i = _varint(buf, i)
        last += v
        ids.append(last)
    for _ in range(n):
        v, i = _varint(buf, i)
        runs.append(v)
    for _ in range(n):
        v, i = _varint(buf, i)
        lens.append(v)
    for k in range(n):
        v, i = _varint(buf, i)
        offs.append(offs[k - 1] + lens[k - 1] if v == 0 and k > 0 else v - 1)
    entries = list(zip(ids, offs, lens, runs))
    with _lock:
        _dirs[key] = entries
    return entries


def zxy_to_tileid(z: int, x: int, y: int) -> int:
    """Hilbert-curve tile id (PMTiles v3)."""
    acc = sum(4 ** i for i in range(z))
    n = 2 ** z
    rx = ry = 0
    d = 0
    s = n // 2
    tx, ty = x, y
    while s > 0:
        rx = 1 if (tx & s) > 0 else 0
        ry = 1 if (ty & s) > 0 else 0
        d += s * s * ((3 * rx) ^ ry)
        if ry == 0:
            if rx == 1:
                tx = s - 1 - tx
                ty = s - 1 - ty
            tx, ty = ty, tx
        s //= 2
    return acc + d


def _find(entries, tile_id):
    lo, hi = 0, len(entries) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        c = tile_id - entries[mid][0]
        if c > 0:
            lo = mid + 1
        elif c < 0:
            hi = mid - 1
        else:
            return entries[mid]
    if hi >= 0:
        e = entries[hi]
        if e[3] == 0 or tile_id - e[0] < e[3]:
            return e
    return None


def get_tile(url: str, z: int, x: int, y: int, decompress: bool = True) -> bytes | None:
    """Tile bytes (decompressed unless ``decompress`` is False) or None when the tile is absent."""
    h = header(url)
    if z < h["min_zoom"] or z > h["max_zoom"]:
        return None
    tid = zxy_to_tileid(z, x, y)
    off, length = h["root_offset"], h["root_length"]
    for _ in range(4):
        entries = _directory(url, off, length, h["internal_compression"])
        e = _find(entries, tid)
        if e is None:
            return None
        if e[3] > 0:  # tile entry
            raw = _get_range(url, h["data_offset"] + e[1], e[2])
            return _decompress(raw, h["tile_compression"]) if decompress else raw
        off, length = h["leaf_offset"] + e[1], e[2]  # leaf directory
    return None


def metadata(url: str) -> dict[str, Any]:
    import json

    h = header(url)
    raw = _get_range(url, h["metadata_offset"], h["metadata_length"])
    return json.loads(_decompress(raw, h["internal_compression"]))
