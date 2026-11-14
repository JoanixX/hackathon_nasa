"""Write a Y4M video of the printed AR target for Chromium's fake camera.

Used by the browser AR test: Chromium is launched with
``--use-file-for-fake-video-capture=<file>.y4m`` so MindAR receives real camera frames
through getUserMedia. Frames show the target (rotated, as if on a table), then an empty
table (tracking loss), then the target again.

Usage: python tools/make_fake_camera.py assets/ar/target.png .local/qa/fake-camera.y4m
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import rasterio

W, H = 640, 480


def _frame(target: np.ndarray, angle_deg: float, scale: float, show: bool) -> np.ndarray:
    out = np.full((H, W, 3), (92, 84, 74), dtype=np.uint8)  # table colour
    if not show:
        return out
    th, tw = target.shape[:2]
    a = math.radians(angle_deg)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    cx, cy = W / 2, H / 2
    # Inverse mapping: output pixel -> target pixel (rotation + uniform scale).
    dx, dy = xx - cx, yy - cy
    u = (math.cos(a) * dx + math.sin(a) * dy) / scale + tw / 2
    v = (-math.sin(a) * dx + math.cos(a) * dy) / scale + th / 2
    inside = (u >= 0) & (u < tw - 1) & (v >= 0) & (v < th - 1)
    out[inside] = target[v[inside].astype(int), u[inside].astype(int)]
    return out


def _yuv420(rgb: np.ndarray) -> bytes:
    r, g, b = (rgb[..., i].astype(np.float64) for i in range(3))
    y = 0.299 * r + 0.587 * g + 0.114 * b
    u = -0.168736 * r - 0.331264 * g + 0.5 * b + 128
    v = 0.5 * r - 0.418688 * g - 0.081312 * b + 128
    sub = lambda c: c.reshape(H // 2, 2, W // 2, 2).mean(axis=(1, 3))  # noqa: E731
    planes = [np.clip(y, 0, 255), np.clip(sub(u), 0, 255), np.clip(sub(v), 0, 255)]
    return b"".join(p.round().astype(np.uint8).tobytes() for p in planes)


def main(src: str, dst: str) -> None:
    with rasterio.open(src) as ds:
        target = np.moveaxis(ds.read([1, 2, 3]), 0, -1)
    scale = 440 / target.shape[1]
    frames = [(8 + 4 * math.sin(i / 10), True) for i in range(120)]
    frames += [(0, False)] * 60
    frames += [(-6 + 3 * math.sin(i / 8), True) for i in range(120)]
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "wb") as fh:
        fh.write(f"YUV4MPEG2 W{W} H{H} F30:1 Ip A1:1 C420jpeg\n".encode())
        for angle, show in frames:
            fh.write(b"FRAME\n")
            fh.write(_yuv420(_frame(target, angle, scale, show)))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
