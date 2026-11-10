import pytest

from shared.layer_store import add_raster_layer
from tests.conftest import make_hill, make_plane


def test_layer_info_gives_cell_size_in_metres():
    geo = add_raster_layer(make_hill(geographic=True), "geo").info()
    dx, dy = geo["pixel_size_m"]
    assert dx == pytest.approx(25.8, abs=0.5)       # 1 arc-second east-west at 33.5 N
    assert dy == pytest.approx(30.8, abs=0.5)       # 1 arc-second north-south
    proj = add_raster_layer(make_plane(), "proj").info()
    assert proj["pixel_size_m"] == [30.0, 30.0]     # projected layers are already in metres


def test_layers_endpoint_sends_cell_size_in_metres(client, layer_id):
    layers = client.get("/api/v1/file/add-data/layers").json()
    dx, dy = layers[0]["pixel_size_m"]
    assert dx == pytest.approx(25.8, abs=0.5)
    assert dy == pytest.approx(30.8, abs=0.5)
