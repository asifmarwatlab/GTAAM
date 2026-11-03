"""Shared test fixtures: a small synthetic DEM and a clean app state for every test."""
import numpy as np
import pytest
from fastapi.testclient import TestClient

from core.raster.model import Raster
from main import create_app
from shared.layer_store import add_raster_layer, layer_store
from shared.project_store import project


def make_hill(h: int = 80, w: int = 100, geographic: bool = True, origin=(73.0, 33.5)) -> Raster:
    """A smooth Gaussian hill, ~30 m cells."""
    yy, xx = np.mgrid[0:h, 0:w]
    z = 1500 + 400 * np.exp(-(((xx - w / 2) / 20) ** 2 + ((yy - h / 2) / 15) ** 2))
    if geographic:
        step = 0.000277778                       # 1 arc-second ~ 30 m
        return Raster(z.astype(np.float32), (step, 0, origin[0], 0, -step, origin[1]), "EPSG:4326", -9999.0)
    return Raster(z.astype(np.float32), (30.0, 0, 400000.0, 0, -30.0, 3700000.0), "EPSG:32643", -9999.0)


def make_plane(rise_per_m: float = 0.5, h: int = 20, w: int = 20) -> Raster:
    """Rises toward the east: z = rise_per_m * x (metres). Projected, 30 m cells."""
    x = np.arange(w) * 30.0
    z = np.tile(rise_per_m * x, (h, 1)).astype(np.float32)
    return Raster(z, (30.0, 0, 0.0, 0, -30.0, h * 30.0), "EPSG:32643", None)


@pytest.fixture(autouse=True)
def clean_state():
    layer_store.clear()
    project.reset()
    yield
    layer_store.clear()
    project.reset()


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.fixture
def hill():
    return make_hill()


@pytest.fixture
def layer_id(hill):
    return add_raster_layer(hill, "Hill").id
