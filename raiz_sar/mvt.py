"""Minimal Mapbox Vector Tile (v2) decoder: protobuf wire format, layers, features, tags and geometry commands.

Spec: https://github.com/mapbox/vector-tile-spec/tree/master/2.1 . No dependency. Geometry is returned in tile
coordinates (0..extent); :func:`to_lonlat` converts them with the tile's z/x/y.
"""

from __future__ import annotations

import math
from typing import Any, Iterator


class MVTError(ValueError):
    pass


def _varint(buf: bytes, i: int) -> tuple[int, int]:
    shift = result = 0
    while True:
        if i >= len(buf):
            raise MVTError("truncated varint")
        b = buf[i]
        i += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, i
        shift += 7
        if shift > 63:
            raise MVTError("varint too long")


def _fields(buf: bytes) -> Iterator[tuple[int, int, Any]]:
    """Yield (field_number, wire_type, value) for one protobuf message."""
    i = 0
    n = len(buf)
    while i < n:
        key, i = _varint(buf, i)
        field, wt = key >> 3, key & 7
        if wt == 0:
            v, i = _varint(buf, i)
        elif wt == 1:
            if i + 8 > n:
                raise MVTError("truncated fixed64")
            v, i = buf[i:i + 8], i + 8
        elif wt == 2:
            ln, i = _varint(buf, i)
            if i + ln > n:
                raise MVTError("truncated bytes")
            v, i = buf[i:i + ln], i + ln
        elif wt == 5:
            if i + 4 > n:
                raise MVTError("truncated fixed32")
            v, i = buf[i:i + 4], i + 4
        else:
            raise MVTError(f"unsupported wire type {wt}")
        yield field, wt, v


def _packed(buf: bytes) -> list[int]:
    out, i = [], 0
    while i < len(buf):
        v, i = _varint(buf, i)
        out.append(v)
    return out


def _zigzag(n: int) -> int:
    return (n >> 1) ^ -(n & 1)


def _value(buf: bytes) -> Any:
    import struct

    for f, wt, v in _fields(buf):
        if f == 1:
            return v.decode("utf-8", "replace")
        if f == 2:
            return struct.unpack("<f", v)[0]
        if f == 3:
            return struct.unpack("<d", v)[0]
        if f in (4, 5):
            return v if f == 5 else (v - (1 << 64) if v >= 1 << 63 else v)
        if f == 6:
            return _zigzag(v)
        if f == 7:
            return bool(v)
    return None


def _geometry(cmds: list[int], gtype: int) -> list[list[tuple[int, int]]]:
    """Decode geometry commands into parts (points: one part per point; lines/rings: one part each)."""
    parts: list[list[tuple[int, int]]] = []
    cur: list[tuple[int, int]] = []
    x = y = 0
    i = 0
    while i < len(cmds):
        cid, count = cmds[i] & 7, cmds[i] >> 3
        i += 1
        if cid == 1:  # MoveTo
            for _ in range(count):
                if i + 1 >= len(cmds):
                    raise MVTError("truncated MoveTo")
                x += _zigzag(cmds[i]); y += _zigzag(cmds[i + 1]); i += 2
                if cur:
                    parts.append(cur)
                cur = [(x, y)]
        elif cid == 2:  # LineTo
            for _ in range(count):
                if i + 1 >= len(cmds):
                    raise MVTError("truncated LineTo")
                x += _zigzag(cmds[i]); y += _zigzag(cmds[i + 1]); i += 2
                cur.append((x, y))
        elif cid == 7:  # ClosePath
            if cur:
                cur.append(cur[0])
        else:
            raise MVTError(f"unknown command {cid}")
    if cur:
        parts.append(cur)
    return parts


GEOM_TYPES = {1: "Point", 2: "LineString", 3: "Polygon"}


def decode(data: bytes, layers: set[str] | None = None) -> dict[str, dict[str, Any]]:
    """{layer_name: {"extent": int, "features": [{"type", "parts", "props"}]}}."""
    out: dict[str, dict[str, Any]] = {}
    for f, wt, v in _fields(data):
        if f != 3 or wt != 2:
            continue
        name, extent, keys, values, raw = None, 4096, [], [], []
        for lf, lwt, lv in _fields(v):
            if lf == 1:
                name = lv.decode("utf-8", "replace")
            elif lf == 2:
                raw.append(lv)
            elif lf == 3:
                keys.append(lv.decode("utf-8", "replace"))
            elif lf == 4:
                values.append(_value(lv))
            elif lf == 5:
                extent = lv
        if name is None or (layers is not None and name not in layers):
            continue
        feats = []
        for fb in raw:
            tags, gtype, geom = [], 0, []
            for ff, fwt, fv in _fields(fb):
                if ff == 2:
                    tags = _packed(fv) if fwt == 2 else [fv]
                elif ff == 3:
                    gtype = fv
                elif ff == 4:
                    geom = _packed(fv) if fwt == 2 else [fv]
            props = {}
            for k in range(0, len(tags) - 1, 2):
                if tags[k] < len(keys) and tags[k + 1] < len(values):
                    props[keys[tags[k]]] = values[tags[k + 1]]
            if gtype in GEOM_TYPES:
                feats.append({"type": GEOM_TYPES[gtype], "parts": _geometry(geom, gtype), "props": props})
        out[name] = {"extent": extent, "features": feats}
    return out


def to_lonlat(px: float, py: float, z: int, x: int, y: int, extent: int) -> tuple[float, float]:
    n = 2 ** z
    lon = (x + px / extent) / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + py / extent) / n))))
    return lon, lat


def ring_area(ring: list[tuple[int, int]]) -> float:
    """Signed area in tile units (MVT: exterior rings are positive with y pointing down)."""
    return sum(ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1] for i in range(len(ring) - 1)) / 2
