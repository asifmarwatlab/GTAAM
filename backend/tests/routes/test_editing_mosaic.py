import time

import numpy as np
import pytest

from shared.layer_store import add_raster_layer
from tests.conftest import make_hill

API = "/api/v1"
ED = f"{API}/terrain-editing"
MO = f"{API}/terrain-mosaic"
BOX = [[73.010, 33.492], [73.016, 33.492], [73.016, 33.486], [73.010, 33.486]]   # around the hill top


def test_editing_flow_queue_preview_apply(client, layer_id):
    assert client.post(f"{ED}/modify-terrain/smooth", json={"layer_id": layer_id}).status_code == 400   # no region yet
    region = client.post(f"{ED}/selection/draw-region", json={"layer_id": layer_id, "polygon": BOX})
    assert region.status_code == 201
    far = client.post(f"{ED}/selection/draw-region", json={"layer_id": layer_id, "polygon": [[0, 0], [1, 0], [1, 1]]})
    assert far.status_code == 400                                                                      # outside raster

    queued = client.post(f"{ED}/modify-terrain/raise-lower", json={"layer_id": layer_id, "amount": -25}).json()
    assert queued["count"] == 1
    client.post(f"{ED}/modify-terrain/flatten", json={"layer_id": layer_id})
    client.post(f"{ED}/modify-terrain/smooth", json={"layer_id": layer_id, "iterations": 2})
    client.post(f"{ED}/modify-terrain/fill-sinks", json={"layer_id": layer_id})
    assert client.get(f"{ED}/review/pending/{layer_id}").json()["count"] == 4

    pre = client.post(f"{ED}/review/preview", json={"layer_id": layer_id}).json()
    assert pre["changed_cells"] > 0 and pre["max_lower"] < 0 and pre["volume_change_m3"] < 0
    cmp = client.post(f"{ED}/review/compare", json={"layer_id": layer_id}).json()
    assert cmp["after"]["max"] < cmp["before"]["max"]

    applied = client.post(f"{ED}/output/apply", json={"layer_id": layer_id}).json()
    assert applied["layer"]["name"].endswith("(edited)")
    original = client.get(f"{API}/analysis/quality-statistics/layer-statistics/{layer_id}").json()
    edited = client.get(f"{API}/analysis/quality-statistics/layer-statistics/{applied['layer']['id']}").json()
    assert original["max"] > edited["max"]                                    # original untouched
    assert client.get(f"{ED}/review/pending/{layer_id}").json()["count"] == 0


def test_editing_select_delete_discard_clear_export(client, layer_id, tmp_path):
    r1 = client.post(f"{ED}/selection/draw-region", json={"layer_id": layer_id, "polygon": BOX, "name": "A"}).json()
    r2 = client.post(f"{ED}/selection/draw-region", json={"layer_id": layer_id, "polygon": BOX, "name": "B"}).json()
    sel = client.post(f"{ED}/selection/select-region", json={"layer_id": layer_id, "region_ids": [r2["id"]]}).json()
    assert [r["selected"] for r in sel["regions"]] == [False, True]
    assert client.post(f"{ED}/selection/select-region", json={"layer_id": layer_id, "region_ids": ["zzz"]}).status_code == 404
    client.post(f"{ED}/modify-terrain/raise-lower", json={"layer_id": layer_id, "amount": 10})
    exp = client.post(f"{ED}/output/export-edited-dem", json={"layer_id": layer_id, "path": str(tmp_path / "e.tif")})
    assert exp.status_code == 200 and (tmp_path / "e.tif").exists()
    assert client.post(f"{ED}/selection/delete-selected", json={"layer_id": layer_id}).json()["deleted"] == 1
    assert client.get(f"{ED}/review/pending/{layer_id}").json()["count"] == 0          # its op went with it
    client.post(f"{ED}/modify-terrain/smooth", json={"layer_id": layer_id})
    assert client.post(f"{ED}/review/discard", json={"layer_id": layer_id}).json()["count"] == 0
    assert client.post(f"{ED}/selection/clear-all", json={"layer_id": layer_id}).json()["count"] == 0
    assert client.post(f"{ED}/review/preview", json={"layer_id": layer_id}).status_code == 400   # no edits


@pytest.fixture
def two_tiles():
    west = make_hill(40, 60, geographic=False)
    east_raster = make_hill(40, 60, geographic=False)
    east_raster.transform = (30.0, 0, 400000.0 + 40 * 30, 0, -30.0, 3700000.0)        # 20 columns overlap
    east_raster.data = east_raster.data + 5
    return add_raster_layer(west, "West").id, add_raster_layer(east_raster, "East").id


def test_mosaic_flow(client, two_tiles, tmp_path):
    a, b = two_tiles
    assert client.post(f"{MO}/mosaic/preview").status_code == 400                    # nothing selected
    sel = client.post(f"{MO}/input/select-dems", json={"layer_ids": [a, b]}).json()
    assert sel["compatible"] is True and sel["names"] == ["West", "East"]
    assert client.get(f"{MO}/input/select-dems").json()["layer_ids"] == [a, b]

    diff = client.post(f"{MO}/overlap-analysis/difference-map").json()
    assert diff["layer"]["width"] == 20 and diff["extra"]["overlap_cells"] > 0
    seam = client.post(f"{MO}/overlap-analysis/seamline", json={"layer_a": a, "layer_b": b}).json()
    assert seam["extra"]["seamline"]["geometry"]["type"] == "LineString"

    assert client.put(f"{MO}/mosaic/blend-settings", json={"method": "mean", "feather_pixels": 10}).json()["method"] == "mean"
    assert client.put(f"{MO}/mosaic/blend-settings", json={"method": "wat"}).status_code == 422
    client.put(f"{MO}/mosaic/blend-settings", json={"method": "feather", "feather_pixels": 8})
    pre = client.post(f"{MO}/mosaic/preview").json()
    assert pre["width"] == 100 and pre["height"] == 40
    applied = client.post(f"{MO}/mosaic/apply").json()
    assert applied["layer"]["name"] == "Mosaic" and applied["layer"]["width"] == 100
    out = client.post(f"{MO}/output/export-elevations", json={"path": str(tmp_path / "m.tif")})
    assert out.status_code == 200 and (tmp_path / "m.tif").exists()


def test_mosaic_background_job_and_incompatible_dems(client, two_tiles):
    a, b = two_tiles
    client.post(f"{MO}/input/select-dems", json={"layer_ids": [a, b]})
    r = client.post(f"{MO}/mosaic/preview?background=true")
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    for _ in range(100):
        job = client.get(f"{API}/jobs/{job_id}").json()
        if job["state"] in ("done", "failed"):
            break
        time.sleep(0.05)
    assert job["state"] == "done" and job["result"]["width"] == 100 and job["progress"] == 1
    assert client.get(f"{API}/jobs/zzz").status_code == 404

    geo = add_raster_layer(make_hill(geographic=True), "Geo").id
    sel = client.post(f"{MO}/input/select-dems", json={"layer_ids": [a, geo]}).json()
    assert sel["compatible"] is False and "coordinate" in sel["problem"]
    assert client.post(f"{MO}/mosaic/preview").status_code == 400


def test_sessions_follow_the_layers(client, two_tiles):
    """Removing a layer or starting a new project must not leave stale ids behind."""
    a, b = two_tiles
    client.post(f"{MO}/input/select-dems", json={"layer_ids": [a, b]})
    client.post(f"{ED}/selection/draw-region", json={"layer_id": a, "polygon": [[400100, 3699900], [400400, 3699900], [400400, 3699600]]})
    client.delete(f"{API}/file/add-data/layers/{b}")
    assert client.get(f"{MO}/input/select-dems").json()["layer_ids"] == [a]          # b dropped from the selection
    client.delete(f"{API}/file/add-data/layers/{a}")
    assert client.get(f"{ED}/selection/regions/{a}").status_code == 404                # layer gone -> 404, not stale data
    c, d = add_raster_layer(make_hill(40, 60, geographic=False), "C").id, add_raster_layer(make_hill(40, 60, geographic=False), "D").id
    client.post(f"{MO}/input/select-dems", json={"layer_ids": [c, d]})
    client.put(f"{MO}/mosaic/blend-settings", json={"method": "mean", "feather_pixels": 3})
    client.post(f"{API}/file/project/new", json={"name": "Fresh"})
    assert client.get(f"{MO}/input/select-dems").json()["layer_ids"] == []
    assert client.get(f"{MO}/mosaic/blend-settings").json() == {"method": "feather", "feather_pixels": 20}
