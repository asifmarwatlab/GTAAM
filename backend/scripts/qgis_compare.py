"""Compare one of our outputs with the same product made by QGIS/GDAL.

    py scripts/qgis_compare.py ours_slope.tif qgis_slope.tif
    py scripts/qgis_compare.py ours_slope.tif qgis_slope.tif --trim 1

Both files must be on the same grid. --trim drops N border pixels, because QGIS and our
3x3 filters treat the outermost ring differently.
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.raster.reader import read_raster          # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ours")
    ap.add_argument("reference")
    ap.add_argument("--trim", type=int, default=1, help="border pixels to ignore (default 1)")
    args = ap.parse_args()

    a, b = read_raster(args.ours), read_raster(args.reference)
    if a.data.shape != b.data.shape:
        print(f"Shapes differ: {a.data.shape} vs {b.data.shape}. Clip/resample to the same grid first.")
        return 1
    t = args.trim
    x = a.data[t:-t, t:-t] if t else a.data
    y = b.data[t:-t, t:-t] if t else b.data
    ok = np.isfinite(x) & np.isfinite(y)
    if not ok.any():
        print("No overlapping valid cells.")
        return 1
    d = x[ok].astype(np.float64) - y[ok].astype(np.float64)
    corr = float(np.corrcoef(x[ok], y[ok])[0, 1]) if ok.sum() > 1 else float("nan")
    print(f"cells compared : {int(ok.sum()):,}")
    print(f"bias (mean)    : {d.mean():+.6f}")
    print(f"MAE            : {np.abs(d).mean():.6f}")
    print(f"RMSE           : {np.sqrt((d ** 2).mean()):.6f}")
    print(f"max |diff|     : {np.abs(d).max():.6f}")
    print(f"correlation    : {corr:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
