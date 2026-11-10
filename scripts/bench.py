"""Measures this machine's NumPy speed and xz decompression rate, for the plan's Machine budget.

Run: .venv/bin/python scripts/bench.py
"""

import io
import lzma
import time

import numpy as np


def best(fn, repeats=5):
    times = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        times.append(time.perf_counter() - start)
    return min(times)


def main():
    rng = np.random.default_rng(0)

    a = rng.random((1500, 1500))
    print(f"matrix product 1500x1500:        {best(lambda: a @ a) * 1e3:8.1f} ms")

    # One star's track: blend two 1,500-point tracks of 20 columns, as EEP interpolation does.
    lo, hi = rng.random((2, 1500, 20))
    t = best(lambda: [lo + 0.3 * (hi - lo) for _ in range(1000)]) / 1000
    print(f"blend two 1500x20 tracks:        {t * 1e6:8.1f} us")

    x = np.sort(rng.random(1500))
    y = rng.random(1500)
    q = rng.random(200_000)
    print(f"np.interp, 200k points:          {best(lambda: np.interp(q, x, y)) * 1e3:8.1f} ms")

    # Text like a MIST table: 20 columns of smoothly changing numbers, about 46 MB.
    # Synthetic, so the rate is a guide; Phase 1 times one real archive.
    table = np.cumsum(rng.normal(size=(100_000, 20)), axis=0)
    buffer = io.BytesIO()
    np.savetxt(buffer, table, fmt="%.16E")
    raw = buffer.getvalue()
    packed = lzma.compress(raw, preset=1)
    t = best(lambda: lzma.decompress(packed), repeats=3)
    print(f"xz decompression:                {len(raw) / 1e6 / t:8.1f} MB/s of text out, "
          f"{len(packed) / 1e6 / t:.1f} MB/s of archive in "
          f"({len(packed) / 1e6:.0f} MB -> {len(raw) / 1e6:.0f} MB)")

if __name__ == "__main__":
    main()
