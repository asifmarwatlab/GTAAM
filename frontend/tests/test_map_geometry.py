import importlib.util
import pathlib

import numpy as np
import pytest

_p = pathlib.Path(__file__).resolve().parents[1] / "frontend" / "ui" / "panels" / "map_geometry.py"
_s = importlib.util.spec_from_file_location("map_geometry", _p)
mg = importlib.util.module_from_spec(_s)
_s.loader.exec_module(mg)

GEO = "EPSG:4326"
UTM = "EPSG:32643"


def test_same_crs_reference_is_identity():
    b = (70.0, 34.0, 71.0, 35.0)
    t = mg.placement(b, (100, 100), GEO, b, (100, 100), GEO)
    assert np.allclose(t, mg.IDENTITY, atol=1e-9)


def test_same_crs_neighbour_sits_to_the_right():
    ref = (70.0, 34.0, 71.0, 35.0)
    east = (71.0, 34.0, 72.0, 35.0)
    t = mg.placement(ref, (100, 100), GEO, east, (100, 100), GEO)
    assert np.allclose(mg.canvas_box(t, (100, 100)), (100, 0, 200, 100), atol=1e-9)


def test_different_size_picture_is_scaled_to_the_same_ground():
    ref = (70.0, 34.0, 71.0, 35.0)
    t = mg.placement(ref, (100, 100), GEO, ref, (50, 200), GEO)
    assert np.allclose(mg.canvas_box(t, (50, 200)), (0, 0, 100, 100), atol=1e-9)


def test_utm_layer_lands_over_the_same_ground_as_geographic():
    pytest.importorskip("pyproj")
    from pyproj import Transformer
    ref = (70.0, 34.0, 71.0, 35.0)
    x0, y0 = Transformer.from_crs(GEO, UTM, always_xy=True).transform(70.0, 34.0)
    x1, y1 = Transformer.from_crs(GEO, UTM, always_xy=True).transform(71.0, 35.0)
    utm_b = (x0, y0, x1, y1)
    t = mg.placement(ref, (100, 100), GEO, utm_b, (100, 100), UTM)
    x, y, x2, y2 = mg.canvas_box(t, (100, 100))
    assert x < 5 and y < 5 and x2 > 95 and y2 > 95        # roughly covers the reference
    assert abs(t[1]) > 1e-4 or abs(t[2]) > 1e-4            # the tilt is kept


def test_round_trip_and_unusable_inputs():
    t = (1.2, 0.1, -0.1, 0.9, 5.0, 7.0)
    px, py = mg.apply(t, 10.0, 20.0)
    assert np.allclose(mg.to_layer_pixel(t, float(px), float(py)), (10.0, 20.0))
    assert mg.invert((0, 0, 0, 0, 1, 1)) is None
    assert mg.placement(None, (1, 1), GEO, (0, 0, 1, 1), (1, 1), GEO) is None
    assert mg.placement((0, 0, 1, 1), (1, 1), "", (0, 0, 1, 1), (1, 1), GEO) is None
