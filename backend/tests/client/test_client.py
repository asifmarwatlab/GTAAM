"""The client is tested against the REAL backend (in-process), not against mocks."""
import json
import re
from pathlib import Path

import pytest

from core.raster.model import Raster
from core.raster.writer import write_geotiff
from terrain_client import ApiConnectionError, ApiError, TerrainApi
from tests.conftest import make_hill

BOX = [(401350, 3698950), (401650, 3698950), (401650, 3698650), (401350, 3698650)]   # around the peak


def _record(client):
    calls = []
    original = client.request

    def recording(method, url, **kw):
        resp = original(method, url, **kw)
        calls.append((method.upper(), url.split("?")[0], resp.status_code))
        return resp

    client.request = recording
    return calls


def _operations(spec):
    return {(m.upper(), path) for path, item in spec["paths"].items()
            for m in item if m in ("get", "post", "put", "patch", "delete")}


def _matches(op, calls):
    method, template = op
    rx = re.compile("^" + re.sub(r"\{[^}]+\}", "[^/]+", template) + "$")
    return any(m == method and rx.match(url) for m, url, _ in calls)


def test_every_backend_endpoint_is_reachable_through_the_client(client, tmp_path):
    spec = client.get("/openapi.json").json()
    calls = _record(client)
    api = TerrainApi(client=client)

    # ---------- files on disk ----------
    dem = write_geotiff(make_hill(geographic=False), tmp_path / "dem.tif")
    west = write_geotiff(make_hill(40, 60, geographic=False), tmp_path / "west.tif")
    east_r = make_hill(40, 60, geographic=False)
    east = write_geotiff(Raster(east_r.data + 5, (30.0, 0, 401200.0, 0, -30.0, 3700000.0), "EPSG:32643", -9999.0),
                         tmp_path / "east.tif")
    pts = tmp_path / "pts.geojson"
    pts.write_text(json.dumps({"type": "FeatureCollection", "features": []}))

    # ---------- system ----------
    assert api.health()["status"] == "ok" and api.is_alive() and api.jobs.list() == []
    assert api._http.get("/health", prefix=False)["status"] == "ok"      # legacy path kept

    # ---------- File ----------
    f = api.file
    assert f.new_project("Upper Indus")["name"] == "Upper Indus"
    lid = f.add_raster(dem, name="DEM")["id"]
    assert f.add_vector(str(pts))["kind"] == "vector"
    base = f.add_basemap("OSM", "https://tile.openstreetmap.org/{z}/{x}/{y}.png", "OSM contributors")
    assert f.project_info()["dirty"] is True
    saved = f.save_project_as(str(tmp_path / "p.json"))
    assert saved["saved_layers"] == 3 and f.save_project()["dirty"] is False
    opened = f.open_project(saved["path"])
    assert opened["layer_count"] == 3 and opened["missing_layers"] == []
    assert any(l["id"] == lid for l in f.layers())                       # ids survive save/open
    f.reorder_layers([l["id"] for l in reversed(f.layers())])
    assert f.update_layer(lid, name="Hill", opacity=0.8, visible=True)["name"] == "Hill"
    f.remove_layer(base["id"])
    assert f.map_image(lid, ramp="viridis", vmin=1500, vmax=1900, max_pixels=5000)[:4] == b"\x89PNG"
    assert Path(f.export_elevations(lid, str(tmp_path / "out.tif"))["path"]).exists()
    assert f.statistics(lid)["count"] == 8000 and "mean" in f.statistics(lid, "csv")
    disp = f.layer_display(lid, bins=10)
    assert disp["ramp"] == "terrain" and disp["statistics"]["count"] == 8000 and len(disp["histogram"]["counts"]) == 10
    area = tmp_path / "area.geojson"
    area.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"name": "A", "n": 2},
         "geometry": {"type": "Polygon", "coordinates": [[[71, 34], [71.2, 34], [71.2, 34.2], [71, 34.2], [71, 34]]]}},
        {"type": "Feature", "properties": {"name": "B", "n": 1},
         "geometry": {"type": "Point", "coordinates": [72, 35]}}]}))
    vid = f.add_vector(str(area))["id"]
    at = f.layer_attributes(vid, sort="n")
    assert at["total"] == 2 and [r["fid"] for r in at["rows"]] == [1, 0] and at["fields"] == ["name", "n"]
    assert f.identify(vid, 71.1, 34.1, 0.01)["properties"]["name"] == "A"
    sh = f.layer_shapes(vid, fit_width=100, fit_height=50)
    assert sh["total"] == 2 and sh["framed_on"] == "own" and len(sh["features"][0]["polys"][0][0]) == 5
    assert f.layer_shapes(vid, raster=lid, width=200, height=100)["framed_on"] == "raster"
    f.remove_layer(vid)
    f.set_fullscreen(True)
    assert f.exit_app()["ok"] is True
    f.reset_workspace()

    # ---------- View ----------
    v = api.view
    assert v.explore("identify")["mode"] == "identify" and v.full_extent()["bounds"]
    assert v.zoom_to_layer(lid)["layer_id"] == lid
    px = f.pixel_value(lid, 0, 0)
    assert px["row"] == 0 and px["col"] == 0 and "value" in px
    v.update_viewport(center=(401500, 3698800), scale=40000)
    assert v.zoom_in()["scale"] == 20000 and v.zoom_out(4)["scale"] == 80000
    assert v.set_pane("statistics", False)["statistics"] is False and "contents" in v.panes()
    assert v.update_appearance(colour_ramp="viridis", scale_bar=False, north_arrow=True,
                               layer_label=True)["colour_ramp"] == "viridis"
    assert "terrain" in v.colour_ramps() and v.appearance()["scale_bar"] is False
    assert v.update_display(regions=True, reference_grid=True, annotation=True)["reference_grid"] is True
    assert v.hillshade_image(lid, azimuth=270, altitude=30, z_factor=2)[:4] == b"\x89PNG"
    assert v.slope_image(lid, "magma")[:4] == b"\x89PNG"
    assert v.contours(lid, 100, 0)["features"] and v.reference_grid(lid, 500)["features"]
    note = v.add_annotation(401500, 3698800, "peak")
    assert v.display()["annotations"][0]["text"] == "peak"
    v.remove_annotation(note["id"])

    # ---------- Analysis ----------
    a = api.analysis
    assert a.distance(lid, [(401400, 3698800), (401700, 3698800)])["total"] == pytest.approx(300)
    assert a.area(lid, BOX)["area_m2"] == pytest.approx(90_000)
    prof = a.elevation_profile(lid, [(400500, 3698800), (402500, 3698800)], samples=40)
    assert len(prof["elevation"]) == 40 and prof["max"] > prof["min"]
    assert a.layer_statistics(lid)["max"] > 1890 and sum(a.histogram(lid, 10)["counts"]) == 8000
    assert a.nodata_check(lid)["status"] == "clean" and a.outlier_check(lid, "zscore", 2)["method"] == "zscore"
    for name, call in {"hillshade": lambda: a.hillshade(lid, 270, 30, 1.5), "slope": lambda: a.slope(lid, "percent"),
                       "aspect": lambda: a.aspect(lid), "curvature": lambda: a.curvature(lid),
                       "roughness": lambda: a.roughness(lid), "tpi": lambda: a.tpi(lid),
                       "ruggedness": lambda: a.ruggedness(lid)}.items():
        out = call()
        assert out["layer"]["tool"] == name and out["statistics"]["count"] > 0, name
    cont = a.contours(lid, 100, 0)
    assert cont["extra"]["feature_count"] >= 3
    assert f.layer_geojson(cont["layer"]["id"])["type"] == "FeatureCollection"

    # ---------- Tools ----------
    t = api.tools
    assert t.clip(lid, (400300, 3698500, 400900, 3699400))["layer"]["width"] == 20
    assert t.clip(lid, {"min_x": 400300, "min_y": 3698500, "max_x": 400900, "max_y": 3699400})["layer"]
    assert t.resample(lid, 60, "nearest")["layer"]["width"] == 50
    assert t.reproject(lid, 4326, "bilinear")["layer"]["crs"] == "EPSG:4326"
    assert t.fill_nodata(lid, 10)["layer"]["tool"] == "fill_nodata"
    hit = t.identify(lid, 401515, 3698785)
    assert (hit["row"], hit["col"]) == (40, 50) and hit["value"] > 1890
    assert t.pixel(lid, 401515, 3698785)["value"] == hit["value"]
    assert t.properties(lid)["dimensions"] == [100, 80] and t.metadata(lid)["driver"] == "GTiff"
    assert t.update_options(units="imperial", decimals=3, default_ramp="viridis")["decimals"] == 3
    assert t.options()["units"] == "imperial" and t.shortcuts() and t.about()["version"]

    # ---------- Terrain Editing ----------
    e = api.editing
    r1 = e.draw_region(lid, BOX, name="Peak")
    r2 = e.draw_region(lid, [(400100, 3699900), (400400, 3699900), (400400, 3699600), (400100, 3699600)])
    assert e.regions(lid)["count"] == 2
    assert [r["selected"] for r in e.select_region(lid, [r1["id"]])["regions"]] == [True, False]
    e.raise_lower(lid, -25)
    e.smooth(lid, 2, region_ids=[r1["id"]])
    e.flatten(lid)
    e.fill_sinks(lid)
    assert e.pending(lid)["count"] == 4
    pre = e.preview(lid)
    assert pre["changed_cells"] > 0 and e.compare(lid)["after"]["max"] < e.compare(lid)["before"]["max"]
    assert e.discard(lid)["count"] == 0
    e.raise_lower(lid, 10)
    assert Path(e.export_edited_dem(lid, str(tmp_path / "edited.tif"))["path"]).exists()
    assert e.apply(lid)["layer"]["name"].endswith("(edited)")
    assert e.delete_selected(lid)["deleted"] == 1 and e.clear_all(lid)["count"] == 0

    # ---------- Terrain Mosaic ----------
    m = api.mosaic
    w, ea = f.add_raster(west, "West")["id"], f.add_raster(east, "East")["id"]
    sel = m.select_dems([w, ea])
    assert sel["compatible"] is True and m.selection()["layer_ids"] == [w, ea]
    assert m.difference_map()["layer"]["width"] == 20
    assert m.seamline(w, ea)["extra"]["seamline"]["geometry"]["type"] == "LineString"
    assert m.set_blend_settings("mean", 5)["method"] == "mean" and m.blend_settings()["feather_pixels"] == 5
    m.set_blend_settings("feather", 8)
    assert m.preview()["width"] == 100
    job = m.preview(background=True)
    assert api.jobs.wait(job["job_id"], timeout=30, poll=0.05)["width"] == 100
    assert api.jobs.get(job["job_id"])["state"] == "done" and api.jobs.list()
    assert m.apply()["layer"]["name"] == "Mosaic"
    assert Path(m.export_elevations(str(tmp_path / "mosaic.tif"))["path"]).exists()

    # ---------- the contract: every backend operation was exercised, and none failed ----------
    failed = [c for c in calls if c[2] >= 400]
    assert not failed, failed
    missing = sorted(op for op in _operations(spec) if not _matches(op, calls))
    assert not missing, f"Backend endpoints with no client method: {missing}"


def test_errors_become_apierror_with_a_code_and_a_message(client, layer_id):
    api = TerrainApi(client=client)
    with pytest.raises(ApiError) as nf:
        api.analysis.slope("nope")
    assert (nf.value.status, nf.value.code) == (404, "layer_not_found") and "nope" in str(nf.value)

    with pytest.raises(ApiError) as bad:
        api.analysis.histogram(layer_id, bins=0)
    assert bad.value.status == 400 and bad.value.code == "bad_bins"

    with pytest.raises(ApiError) as val:                       # core raised ValueError -> 400
        api.tools.clip(layer_id, (0, 0, 1, 1))
    assert val.value.status == 400 and val.value.code == "invalid_value" and "overlap" in val.value.message

    with pytest.raises(ApiError) as inv:                       # request validation -> 422, readable
        api.analysis.distance(layer_id, [(1, 2)])
    assert inv.value.status == 422 and inv.value.code == "validation_error" and "points" in inv.value.message

    with pytest.raises(ApiError) as job:
        api.jobs.get("zzz")
    assert job.value.code == "job_not_found"


def test_failed_job_raises_job_failed(client):
    from shared.jobs import jobs

    def boom(report):
        raise RuntimeError("it broke")

    jid = jobs.submit("boom", boom)
    with pytest.raises(ApiError) as exc:
        TerrainApi(client=client).jobs.wait(jid, timeout=10, poll=0.02)
    assert exc.value.code == "job_failed" and "it broke" in exc.value.message


def test_unreachable_backend_raises_connection_error():
    api = TerrainApi("http://127.0.0.1:9", timeout=1.0)
    assert api.is_alive() is False
    with pytest.raises(ApiConnectionError) as exc:
        api.file.layers()
    assert "Is it running" in str(exc.value)


def test_client_does_not_import_the_backend():
    """The UI project copies terrain_client alone, so it must not depend on `app`."""
    root = Path(__file__).resolve().parents[2] / "terrain_client"
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"^\s*(from|import)\s+app(\.|\s|$)", text, re.M), path.name
