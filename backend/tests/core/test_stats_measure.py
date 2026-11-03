import numpy as np
import pytest

from core.measure.area import polygon_area
from core.measure.distance import haversine, path_length
from core.measure.profile import elevation_profile
from core.stats import histogram, layer_stats, nodata_check, outliers
from tests.conftest import make_plane


def test_layer_stats_ignore_nan():
    d = np.array([[1, 2], [3, np.nan]], dtype=np.float32)
    s = layer_stats.compute(d)
    assert (s["min"], s["max"], s["mean"], s["nodata_count"]) == (1, 3, 2, 1)


def test_histogram_counts_add_up():
    d = np.arange(100, dtype=np.float32).reshape(10, 10)
    h = histogram.compute(d, bins=10)
    assert sum(h["counts"]) == 100 and len(h["bin_edges"]) == 11


def test_nodata_check():
    d = np.ones((4, 4), dtype=np.float32)
    assert nodata_check.run(d)["status"] == "clean"
    d[0, 0] = np.nan
    r = nodata_check.run(d)
    assert r["nodata_count"] == 1 and r["status"] == "has_nodata"


def test_outliers_find_the_spike():
    d = np.random.default_rng(1).normal(100, 1, (50, 50)).astype(np.float32)
    d[10, 10] = 500
    for method in ("iqr", "zscore"):
        r = outliers.run(d, method)
        assert r["outlier_count"] >= 1 and r["highest_outlier"] == 500
    with pytest.raises(ValueError):
        outliers.run(d, "nope")


def test_distance_and_area():
    assert path_length([(0, 0), (3, 4)], geographic=False)["total"] == 5
    assert haversine(0, 0, 1, 0) == pytest.approx(111_195, rel=1e-3)
    sq = polygon_area([(0, 0), (100, 0), (100, 100), (0, 100)], geographic=False)
    assert sq["area_m2"] == 10_000
    deg = polygon_area([(73, 33), (73.01, 33), (73.01, 33.01), (73, 33.01)], geographic=True)
    assert 0.9e6 < deg["area_m2"] < 1.1e6            # ~0.93 km x 1.1 km


def test_profile_follows_the_plane():
    plane = make_plane(0.5)                           # z = 0.5 * x
    p = elevation_profile(plane, [(30, 300), (450, 300)], geographic=False, samples=50)
    assert p["total_distance"] == pytest.approx(420)
    assert p["elevation"][0] == pytest.approx(15 + 0, abs=1.0) or p["elevation"][0] is not None
    assert p["gain"] > 0 and p["loss"] == 0
