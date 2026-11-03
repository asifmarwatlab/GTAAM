import numpy as np
import pytest

from core.raster.crs import cell_size_meters, is_geographic
from core.terrain.aspect import compute_aspect
from core.terrain.contours import contour_lines
from core.terrain.curvature import compute_curvature
from core.terrain.hillshade import compute_hillshade
from core.terrain.roughness import compute_roughness
from core.terrain.ruggedness import compute_ruggedness
from core.terrain.slope import compute_slope
from core.terrain.tpi import compute_tpi
from tests.conftest import make_hill, make_plane


def test_slope_of_a_plane_matches_trigonometry():
    plane = make_plane(0.5)
    s = compute_slope(plane.data, 30, 30)
    assert s[5:-5, 5:-5] == pytest.approx(np.degrees(np.arctan(0.5)), abs=1e-3)   # 26.565 deg
    p = compute_slope(plane.data, 30, 30, units="percent")
    assert p[5, 5] == pytest.approx(50.0, abs=1e-3)


def test_aspect_of_a_plane_rising_east_faces_west():
    plane = make_plane(0.5)
    assert compute_aspect(plane.data, 30, 30)[10, 10] == pytest.approx(270.0, abs=1e-3)


def test_flat_ground_has_no_aspect_and_hillshade_180():
    flat = np.full((10, 10), 100.0, dtype=np.float32)
    assert np.isnan(compute_aspect(flat, 30, 30)).all()
    assert compute_hillshade(flat, 30, 30, altitude=45)[5, 5] == pytest.approx(180.6, abs=0.5)


def test_hillshade_sun_side_is_brighter():
    plane = make_plane(0.5)                    # slopes face west
    west = compute_hillshade(plane.data, 30, 30, azimuth=270)[10, 10]
    east = compute_hillshade(plane.data, 30, 30, azimuth=90)[10, 10]
    assert west > east


def test_curvature_hilltop_is_convex_positive():
    r = make_hill(geographic=False)
    c = compute_curvature(r.data, 30, 30)
    assert c[r.height // 2, r.width // 2] > 0


def test_roughness_tpi_ruggedness_on_a_single_peak():
    z = np.zeros((7, 7), dtype=np.float32)
    z[3, 3] = 10
    assert compute_roughness(z)[3, 3] == 10
    assert compute_tpi(z)[3, 3] == pytest.approx(10.0)
    assert compute_ruggedness(z)[3, 3] == pytest.approx(np.sqrt(8 * 100))


def test_geographic_cell_size_is_narrower_east_west():
    r = make_hill(geographic=True)
    dx, dy = cell_size_meters(r)
    assert is_geographic(r)
    assert 25 < dx < dy < 35


def test_contours_return_geojson_lines():
    fc = contour_lines(make_hill(geographic=False), interval=100)
    assert fc["type"] == "FeatureCollection" and len(fc["features"]) >= 3
    assert fc["features"][0]["geometry"]["type"] == "MultiLineString"
    with pytest.raises(ValueError):
        contour_lines(make_hill(), interval=0.001)


def test_metres_per_degree_follows_wgs84():
    from core.raster.crs import metres_per_degree
    lon0, lat0 = metres_per_degree(0)
    assert lon0 == pytest.approx(111_319.5, abs=1)        # equator, east-west
    assert lat0 == pytest.approx(110_574.3, abs=1)        # equator, north-south
    lon, lat = metres_per_degree(33.5)                    # northern Pakistan
    assert lat == pytest.approx(110_913, abs=5)
    assert lon == pytest.approx(92_922, abs=5)
    assert metres_per_degree(90)[1] == pytest.approx(111_694, abs=2)
