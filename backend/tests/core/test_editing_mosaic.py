import numpy as np
import pytest

from core.editing.compare import compare
from core.editing.fill_sinks import fill_sinks
from core.editing.flatten import flatten
from core.editing.raise_lower import raise_lower
from core.editing.regions import polygon_mask
from core.editing.smooth import smooth
from core.mosaic.difference import difference_map
from core.mosaic.merge import mosaic
from core.mosaic.seamline import min_difference_seamline
from core.raster.clip import clip
from core.raster.nodata import fill_nodata
from core.raster.resample import resample
from core.raster.model import Raster
from core.render.map_image import render_png
from tests.conftest import make_hill, make_plane


def test_polygon_mask_covers_the_right_cells():
    plane = make_plane(h=20, w=20)                    # 600 m x 600 m, 30 m cells
    mask = polygon_mask(plane.data.shape, plane.transform, [(0, 0), (300, 0), (300, 300), (0, 300)])
    assert mask.sum() == 100                          # 10 x 10 cells
    with pytest.raises(ValueError):
        polygon_mask(plane.data.shape, plane.transform, [(0, 0), (1, 1)])


def test_raise_flatten_smooth_only_touch_the_mask():
    z = np.random.default_rng(0).normal(100, 5, (30, 30)).astype(np.float32)
    mask = np.zeros_like(z, dtype=bool)
    mask[10:20, 10:20] = True
    up = raise_lower(z, mask, 10)
    assert np.allclose(up[mask], z[mask] + 10) and np.array_equal(up[~mask], z[~mask])
    flat = flatten(z, mask)
    assert np.ptp(flat[mask]) == 0 and np.array_equal(flat[~mask], z[~mask])
    sm = smooth(z, mask, 3)
    assert sm[mask].std() < z[mask].std() and np.array_equal(sm[~mask], z[~mask])
    c = compare(z, up, cell_area_m2=900)
    assert c["changed_cells"] == 100 and c["max_raise"] == pytest.approx(10)
    assert c["volume_change_m3"] == pytest.approx(100 * 10 * 900)


def test_fill_sinks_fills_a_pit():
    z = np.add.outer(np.arange(20), np.arange(20)).astype(np.float32)   # slopes to the corner
    z[10, 10] = -50                                                       # a pit
    out = fill_sinks(z)
    assert out[10, 10] == 18          # fills up to its lowest spill point (diagonal neighbour)
    assert np.array_equal(out[0], z[0])                                  # border untouched


def test_fill_nodata_closes_holes():
    z = np.ones((10, 10), dtype=np.float32) * 5
    z[4:6, 4:6] = np.nan
    assert np.isfinite(fill_nodata(z)).all()


def test_clip_and_resample():
    r = make_hill(geographic=False)                  # 100 x 80 cells, 30 m
    c = clip(r, (400000 + 300, 3700000 - 1200, 400000 + 900, 3700000 - 300))
    assert c.width == 20 and c.height == 30
    assert c.origin_x == pytest.approx(400300)
    big = resample(r, 60.0, "bilinear")
    assert big.width == 50 and big.height == 40
    with pytest.raises(ValueError):
        clip(r, (0, 0, 1, 1))


def _tile(origin_x, value):
    return Raster(np.full((50, 50), value, dtype=np.float32), (30.0, 0, origin_x, 0, -30.0, 1500.0), "EPSG:32643")


def test_mosaic_difference_and_seamline():
    a, b = _tile(0.0, 100.0), _tile(1200.0, 110.0)        # 50 cells = 1500 m; overlap = 300 m (10 cells)
    for method in ("feather", "first", "last", "mean", "min", "max"):
        m = mosaic([a, b], method, feather_pixels=5)
        assert m.width == 90 and m.height == 50
    mean = mosaic([a, b], "mean")
    assert mean.data[10, 45] == pytest.approx(105)
    feathered = mosaic([a, b], "feather", 5).data
    assert 100 <= feathered[10, 45] <= 110 and feathered[10, 2] == pytest.approx(100)
    diff, stats = difference_map(a, b)
    assert stats["bias"] == pytest.approx(-10) and diff.width == 10
    seam = min_difference_seamline(a, b)
    assert seam["geometry"]["type"] == "LineString" and len(seam["geometry"]["coordinates"]) == 50
    with pytest.raises(ValueError):
        difference_map(a, _tile(99999.0, 1))
    with pytest.raises(ValueError):
        mosaic([a, make_hill(geographic=True)])            # different coordinate system


def test_render_png_is_a_valid_png():
    png = render_png(make_hill(), "terrain")
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and b"IEND" in png[-12:]
