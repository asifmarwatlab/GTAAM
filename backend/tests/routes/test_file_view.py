import pytest

from core.raster.writer import write_geotiff

API = "/api/v1"


def test_layers_panel_flow(client, layer_id):
    layers = client.get(f"{API}/file/add-data/layers").json()
    assert [l["id"] for l in layers] == [layer_id] and layers[0]["kind"] == "raster"
    r = client.patch(f"{API}/file/add-data/layers/{layer_id}", json={"name": "Renamed", "opacity": 0.5})
    assert r.json()["name"] == "Renamed" and r.json()["opacity"] == 0.5
    assert client.patch(f"{API}/file/add-data/layers/{layer_id}", json={"opacity": 3}).status_code == 422
    assert client.delete(f"{API}/file/add-data/layers/{layer_id}").status_code == 200
    assert client.get(f"{API}/file/add-data/layers").json() == []


def test_add_raster_from_file_and_basemap(client, hill, tmp_path):
    path = write_geotiff(hill, tmp_path / "dem.tif")
    r = client.post(f"{API}/file/add-data/raster", json={"path": path})
    assert r.status_code == 201 and r.json()["name"] == "dem" and r.json()["width"] == 100
    assert client.post(f"{API}/file/add-data/raster", json={"path": "missing.tif"}).status_code == 404
    b = client.post(f"{API}/file/add-data/basemap", json={"name": "OSM", "url_template": "https://x/{z}/{x}/{y}.png"})
    assert b.status_code == 201 and b.json()["kind"] == "basemap"


def test_add_vector(client, tmp_path):
    f = tmp_path / "pts.geojson"
    f.write_text('{"type":"FeatureCollection","features":[]}')
    assert client.post(f"{API}/file/add-data/vector", json={"path": str(f)}).status_code == 201
    bad = tmp_path / "x.shp"
    bad.write_text("x")
    assert client.post(f"{API}/file/add-data/vector", json={"path": str(bad)}).status_code == 400


def test_add_vector_shapefile_in_utm_comes_back_in_lon_lat(client, tmp_path):
    fiona = pytest.importorskip("fiona")
    shp = tmp_path / "wells.shp"
    schema = {"geometry": "Point", "properties": {"name": "str"}}
    with fiona.open(shp, "w", driver="ESRI Shapefile", schema=schema, crs="EPSG:32643") as out:
        out.write({"type": "Feature", "geometry": {"type": "Point", "coordinates": [314214.39, 3708509.35]},
                   "properties": {"name": "w1"}})
    r = client.post(f"{API}/file/add-data/vector", json={"path": str(shp)})
    assert r.status_code == 201 and r.json()["name"] == "wells"
    gj = client.get(f"{API}/file/add-data/layers/{r.json()['id']}/geojson").json()
    lon, lat = gj["features"][0]["geometry"]["coordinates"]
    assert (round(lon, 2), round(lat, 2)) == (73.0, 33.5)


def test_project_save_and_open_round_trip(client, hill, tmp_path):
    tif = write_geotiff(hill, tmp_path / "dem.tif")
    client.post(f"{API}/file/project/new", json={"name": "Upper Indus"})
    lid = client.post(f"{API}/file/add-data/raster", json={"path": tif}).json()["id"]
    client.post(f"{API}/analysis/surface-analysis/slope", json={"layer_id": lid})          # derived, unsaved
    assert client.get(f"{API}/file/project").json()["dirty"] is True
    saved = client.post(f"{API}/file/project/save-as", json={"path": str(tmp_path / "p.json")}).json()
    assert saved["saved_layers"] == 2 and saved["skipped_layers"] == [] and saved["dirty"] is False   # the slope result is kept too
    client.post(f"{API}/file/project/new", json={"name": "Other"})
    assert client.get(f"{API}/file/add-data/layers").json() == []
    opened = client.post(f"{API}/file/project/open", json={"path": saved["path"]}).json()
    assert opened["name"] == "Upper Indus" and opened["layer_count"] == 2 and opened["missing_layers"] == []
    assert client.post(f"{API}/file/project/save").status_code == 200
    assert client.post(f"{API}/file/project/open", json={"path": str(tmp_path / "nope.json")}).status_code == 404


def test_export_map_image_elevations_statistics(client, layer_id, tmp_path):
    png = client.get(f"{API}/file/export/map-image/{layer_id}?ramp=viridis")
    assert png.status_code == 200 and png.content[:4] == b"\x89PNG"
    assert client.get(f"{API}/file/export/map-image/{layer_id}?ramp=nope").status_code == 400
    out = client.post(f"{API}/file/export/elevations", json={"layer_id": layer_id, "path": str(tmp_path / "o.tif")})
    assert out.status_code == 200 and (tmp_path / "o.tif").exists()
    csv = client.get(f"{API}/file/export/statistics/{layer_id}?format=csv")
    assert csv.headers["content-type"].startswith("text/csv") and "mean" in csv.text
    assert client.get(f"{API}/file/export/statistics/{layer_id}").json()["count"] == 8000


def test_workspace_reset_and_exit(client, layer_id):
    client.put(f"{API}/view/appearance", json={"colour_ramp": "viridis", "scale_bar": False})
    assert client.get(f"{API}/view/appearance").json()["colour_ramp"] == "viridis"
    client.post(f"{API}/file/workspace/reset")
    assert client.get(f"{API}/view/appearance").json()["colour_ramp"] == "terrain"
    assert client.post(f"{API}/file/workspace/exit").json()["unsaved_changes"] is True


def test_view_navigation_panes_display(client, layer_id):
    ext = client.get(f"{API}/view/navigate/full-extent").json()
    assert len(ext["bounds"]) == 4
    assert client.get(f"{API}/view/navigate/zoom-to-layer/{layer_id}").status_code == 200
    client.put(f"{API}/view/navigate/viewport", json={"scale": 40000})
    assert client.post(f"{API}/view/navigate/zoom-in").json()["scale"] == 20000
    assert client.post(f"{API}/view/navigate/zoom-out", json={"factor": 4}).json()["scale"] == 80000
    assert client.put(f"{API}/view/panes/statistics", json={"visible": False}).json()["statistics"] is False
    assert client.put(f"{API}/view/panes/nope", json={"visible": True}).status_code == 404
    assert client.get(f"{API}/view/appearance/colour-ramps").json()
    assert client.put(f"{API}/view/appearance", json={"colour_ramp": "nope"}).status_code == 400
    assert client.get(f"{API}/view/display/hillshade/{layer_id}").content[:4] == b"\x89PNG"
    assert client.get(f"{API}/view/display/slope/{layer_id}").content[:4] == b"\x89PNG"
    fc = client.get(f"{API}/view/display/contours/{layer_id}?interval=50").json()
    assert fc["type"] == "FeatureCollection" and fc["features"]
    grid = client.get(f"{API}/view/display/reference-grid/{layer_id}?spacing=0.005").json()
    assert grid["features"]
    note = client.post(f"{API}/view/display/annotations", json={"x": 1, "y": 2, "text": "peak"}).json()
    assert client.get(f"{API}/view/display").json()["annotations"][0]["text"] == "peak"
    assert client.delete(f"{API}/view/display/annotations/{note['id']}").status_code == 200
    assert client.put(f"{API}/view/display", json={"reference_grid": True}).json()["reference_grid"] is True


def test_project_keeps_tool_results_gui_state_and_extension(client, hill, tmp_path):
    tif = write_geotiff(hill, tmp_path / "dem.tif")
    client.post(f"{API}/file/project/new", json={"name": "P"})
    lid = client.post(f"{API}/file/add-data/raster", json={"path": tif}).json()["id"]
    slope = client.post(f"{API}/analysis/surface-analysis/slope", json={"layer_id": lid}).json()["layer"]
    cont = client.post(f"{API}/analysis/terrain-derivatives/contours",
                       json={"layer_id": lid, "interval": 100, "base": 0}).json()["layer"]
    gui = {"ramp": "Hypsometric", "view": {"scale": 2.5}}
    saved = client.post(f"{API}/file/project/save-as",
                        json={"path": str(tmp_path / "mine"), "name": "mine", "gui": gui}).json()
    assert saved["path"].endswith("mine.agtaam") and saved["saved_layers"] == 3
    assert (tmp_path / "mine_data").is_dir()
    client.post(f"{API}/file/project/new", json={"name": "Other"})
    opened = client.post(f"{API}/file/project/open", json={"path": saved["path"]}).json()
    assert opened["name"] == "mine" and opened["gui"] == gui and opened["missing_layers"] == []
    layers = {l["id"]: l for l in client.get(f"{API}/file/add-data/layers").json()}
    assert layers[slope["id"]]["tool"] == "slope" and layers[slope["id"]]["derived_from"] == lid
    assert layers[cont["id"]]["kind"] == "vector" and layers[cont["id"]]["tool"] == "contours"
    assert client.get(f"{API}/file/add-data/layers/{cont['id']}/geojson").json()["features"]


def test_project_finds_moved_data_and_reports_missing(client, hill, tmp_path):
    import shutil
    folder = tmp_path / "a"
    folder.mkdir()
    tif = write_geotiff(hill, folder / "dem.tif")
    client.post(f"{API}/file/project/new", json={"name": "P"})
    client.post(f"{API}/file/add-data/raster", json={"path": tif})
    saved = client.post(f"{API}/file/project/save-as", json={"path": str(folder / "p.agtaam")}).json()
    moved = tmp_path / "b"
    shutil.copytree(folder, moved)                          # whole project folder moved
    shutil.rmtree(folder)
    ok = client.post(f"{API}/file/project/open", json={"path": str(moved / "p.agtaam")}).json()
    assert ok["missing_layers"] == [] and ok["layer_count"] == 1
    (moved / "dem.tif").unlink()
    gone = client.post(f"{API}/file/project/open", json={"path": str(moved / "p.agtaam")}).json()
    assert gone["missing_layers"] == ["dem"] and gone["layer_count"] == 0


def test_project_reopens_a_shapefile_layer(client, tmp_path):
    pytest.importorskip("fiona")
    import fiona
    from fiona.crs import from_epsg
    shp = tmp_path / "pts.shp"
    with fiona.open(shp, "w", driver="ESRI Shapefile", crs=from_epsg(4326),
                    schema={"geometry": "Point", "properties": {"id": "int"}}) as dst:
        dst.write({"geometry": {"type": "Point", "coordinates": (73.0, 33.5)}, "properties": {"id": 1}})
    client.post(f"{API}/file/project/new", json={"name": "P"})
    client.post(f"{API}/file/add-data/vector", json={"path": str(shp)})
    saved = client.post(f"{API}/file/project/save-as", json={"path": str(tmp_path / "p.agtaam")}).json()
    client.post(f"{API}/file/project/new", json={"name": "Other"})
    opened = client.post(f"{API}/file/project/open", json={"path": saved["path"]}).json()
    assert opened["layer_count"] == 1 and opened["missing_layers"] == []


def test_open_rejects_a_non_project_file(client, tmp_path):
    bad = tmp_path / "x.agtaam"
    bad.write_text("not json at all", encoding="utf-8")
    r = client.post(f"{API}/file/project/open", json={"path": str(bad)})
    assert r.status_code == 400 and "not an A-GTAAM project" in r.text


def test_add_vector_reports_facts_and_converts_to_raster_crs(client, tmp_path):
    f = tmp_path / "area.geojson"
    f.write_text('{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"a":1},'
                 '"geometry":{"type":"Polygon","coordinates":[[[71.0,34.0],[71.1,34.0],[71.1,34.1],'
                 '[71.0,34.0]]]}}]}')
    r = client.post(f"{API}/file/add-data/vector", json={"path": str(f)})
    assert r.status_code == 201
    meta = r.json()["meta"]
    assert meta["features"] == 1 and meta["geometry"] == "Polygon" and meta["vertices"] == 4
    assert meta["bounds"] == [71.0, 34.0, 71.1, 34.1] and meta["crs"] == "EPSG:4326"
    lid = r.json()["id"]
    raw = client.get(f"{API}/file/add-data/layers/{lid}/geojson").json()
    assert raw["features"][0]["geometry"]["coordinates"][0][0] == [71.0, 34.0]
    utm = client.get(f"{API}/file/add-data/layers/{lid}/geojson", params={"crs": "EPSG:32642"})
    assert utm.status_code == 200
    x, y = utm.json()["features"][0]["geometry"]["coordinates"][0][0]
    assert 100_000 < x < 900_000 and 3_700_000 < y < 3_900_000      # metres, not degrees


def _two_features(tmp_path):
    f = tmp_path / "two.geojson"
    f.write_text('{"type":"FeatureCollection","features":['
                 '{"type":"Feature","properties":{"name":"A","n":10},"geometry":{"type":"Polygon","coordinates":'
                 '[[[71,34],[71.4,34],[71.4,34.4],[71,34.4],[71,34]],[[71.1,34.1],[71.2,34.1],[71.2,34.2],[71.1,34.2],[71.1,34.1]]]}},'
                 '{"type":"Feature","properties":{"name":"B","n":2},"geometry":{"type":"LineString","coordinates":[[72,35],[72.5,35.5]]}},'
                 '{"type":"Feature","properties":{"name":"C","n":null},"geometry":{"type":"Point","coordinates":[73,36]}}]}')
    return f


def test_attribute_table_pages_and_sorts(client, tmp_path):
    lid = client.post(f"{API}/file/add-data/vector", json={"path": str(_two_features(tmp_path))}).json()["id"]
    r = client.get(f"{API}/file/add-data/layers/{lid}/attributes").json()
    assert r["total"] == 3 and r["fields"] == ["name", "n"] and [x["fid"] for x in r["rows"]] == [0, 1, 2]
    asc = client.get(f"{API}/file/add-data/layers/{lid}/attributes", params={"sort": "n"}).json()
    assert [x["fid"] for x in asc["rows"]] == [1, 0, 2]                 # 2, 10, then the empty value last
    desc = client.get(f"{API}/file/add-data/layers/{lid}/attributes", params={"sort": "n", "descending": True}).json()
    assert [x["fid"] for x in desc["rows"]] == [0, 1, 2]
    page = client.get(f"{API}/file/add-data/layers/{lid}/attributes", params={"offset": 1, "limit": 1, "fields": "name"}).json()
    assert page["rows"] == [{"fid": 1, "values": {"name": "B"}}]
    assert client.get(f"{API}/file/add-data/layers/{lid}/attributes", params={"sort": "nope"}).status_code == 400


def test_identify_finds_the_feature_under_a_point(client, tmp_path):
    lid = client.post(f"{API}/file/add-data/vector", json={"path": str(_two_features(tmp_path))}).json()["id"]
    url = f"{API}/file/add-data/layers/{lid}/identify"
    hit = client.post(url, json={"x": 71.35, "y": 34.35, "tolerance": 0.001}).json()
    assert hit["hit"] and hit["fid"] == 0 and hit["properties"]["name"] == "A"
    hole = client.post(url, json={"x": 71.15, "y": 34.15, "tolerance": 0.001}).json()
    assert hole["hit"] is False                                         # inside the polygon's hole
    line = client.post(url, json={"x": 72.25, "y": 35.25, "tolerance": 0.01}).json()
    assert line["fid"] == 1
    pt = client.post(url, json={"x": 73.001, "y": 36.0, "tolerance": 0.01}).json()
    assert pt["fid"] == 2
    miss = client.post(url, json={"x": 80, "y": 10, "tolerance": 0.01}).json()
    assert miss == {"hit": False, "fid": None, "properties": {}}
    metres = client.post(url, json={"x": 700000, "y": 3750000, "tolerance": 50, "crs": "EPSG:32642"})
    assert metres.status_code == 200


def test_layer_display_bundles_ramp_statistics_histogram(client, layer_id):
    d = client.get(f"{API}/file/add-data/layers/{layer_id}/display", params={"bins": 12}).json()
    assert d["ramp"] == "terrain" and d["statistics"]["count"] > 0 and len(d["histogram"]["counts"]) == 12


def test_vector_shapes_come_back_in_drawing_cells(client, layer_id, tmp_path):
    lid = client.post(f"{API}/file/add-data/vector", json={"path": str(_two_features(tmp_path))}).json()["id"]
    url = f"{API}/file/add-data/layers/{lid}/shapes"
    own = client.get(url, params={"fit_width": 400, "fit_height": 300}).json()
    assert own["framed_on"] == "own" and own["total"] == 3
    x0, y0, x1, y1 = own["view"]
    assert 0 <= x0 < x1 <= 400.01 and 0 <= y0 < y1 <= 300.01             # fitted into the window
    poly = own["features"][0]["polys"][0]
    assert len(poly) == 2 and len(poly[0]) == 5                          # outer ring + one hole
    assert own["features"][1]["lines"] and own["features"][2]["pts"] and own["features"][0]["anchor"]
    r = client.get(url, params={"raster": layer_id, "width": 200, "height": 100}).json()
    assert r["framed_on"] == "raster" and r["total"] == 3
    assert client.get(url, params={"raster": layer_id}).status_code == 400   # needs the picture size


def test_open_project_returns_every_layer_with_display_data(client, hill, tmp_path):
    path = write_geotiff(hill, tmp_path / "dem.tif")
    client.post(f"{API}/file/add-data/raster", json={"path": path})
    saved = client.post(f"{API}/file/project/save-as", json={"path": str(tmp_path / "p.agtaam")}).json()
    res = client.post(f"{API}/file/project/open", json={"path": saved["path"]}).json()
    assert len(res["layers"]) == 1 and res["layers"][0]["kind"] == "raster"
    d = res["layers"][0]["display"]
    assert d["ramp"] == "terrain" and d["statistics"]["count"] > 0 and d["histogram"]["counts"]


def _canvas(cid, name, layers, **extra):
    return {"id": cid, "name": name, "layers": layers, **extra}


def test_project_saves_and_opens_two_canvases(client, hill, tmp_path):
    """Madam's case: one DEM per canvas, plus one layer shared by both."""
    a = write_geotiff(hill, tmp_path / "islamabad.tif")
    b = write_geotiff(hill, tmp_path / "karachi.tif")
    client.post(f"{API}/file/project/new", json={"name": "P"})
    isb = client.post(f"{API}/file/add-data/raster", json={"path": a}).json()["id"]
    khi = client.post(f"{API}/file/add-data/raster", json={"path": b}).json()["id"]
    canvases = [
        _canvas("c1", "Islamabad", [{"id": isb, "visible": True, "opacity": 1.0}],
                view={"scale": 2.0}, regions=[[[0, 0], [1, 1], [0, 1]]]),
        _canvas("c2", "Karachi", [{"id": khi, "visible": False, "opacity": 0.4},
                                  {"id": isb, "visible": True, "opacity": 0.8}]),   # isb is shared
    ]
    saved = client.post(f"{API}/file/project/save-as",
                        json={"path": str(tmp_path / "two.agtaam"), "canvases": canvases,
                              "active_canvas": "c2"}).json()
    client.post(f"{API}/file/project/new", json={"name": "Other"})
    opened = client.post(f"{API}/file/project/open", json={"path": saved["path"]}).json()
    assert opened["active_canvas"] == "c2"
    got = {c["id"]: c for c in opened["canvases"]}
    assert [c["name"] for c in opened["canvases"]] == ["Islamabad", "Karachi"]
    assert got["c1"]["view"] == {"scale": 2.0} and got["c1"]["regions"]
    assert [l["id"] for l in got["c2"]["layers"]] == [khi, isb]
    assert got["c2"]["layers"][0]["visible"] is False and got["c2"]["layers"][1]["opacity"] == 0.8


def test_removing_a_layer_takes_it_out_of_every_canvas(client, hill, tmp_path):
    tif = write_geotiff(hill, tmp_path / "dem.tif")
    client.post(f"{API}/file/project/new", json={"name": "P"})
    lid = client.post(f"{API}/file/add-data/raster", json={"path": tif}).json()["id"]
    both = [_canvas("c1", "One", [{"id": lid}]), _canvas("c2", "Two", [{"id": lid}])]
    path = str(tmp_path / "p.agtaam")
    client.post(f"{API}/file/project/save-as", json={"path": path, "canvases": both})
    assert client.delete(f"{API}/file/add-data/layers/{lid}").status_code in (200, 204)
    client.post(f"{API}/file/project/save")                  # keeps the canvases it already has
    opened = client.post(f"{API}/file/project/open", json={"path": path}).json()
    assert all(c["layers"] == [] for c in opened["canvases"]) and len(opened["canvases"]) == 2


def test_old_project_opens_as_one_map_canvas(client, hill, tmp_path):
    tif = write_geotiff(hill, tmp_path / "dem.tif")
    client.post(f"{API}/file/project/new", json={"name": "P"})
    lid = client.post(f"{API}/file/add-data/raster", json={"path": tif}).json()["id"]
    path = str(tmp_path / "old.agtaam")
    client.post(f"{API}/file/project/save-as", json={"path": path, "gui": {"view": {"scale": 3.0}}})
    import json
    doc = json.loads((tmp_path / "old.agtaam").read_text(encoding="utf-8"))
    doc.pop("canvases"), doc.pop("active_canvas")           # what a version-2 file looked like
    (tmp_path / "old.agtaam").write_text(json.dumps(doc), encoding="utf-8")
    opened = client.post(f"{API}/file/project/open", json={"path": path}).json()
    assert [c["name"] for c in opened["canvases"]] == ["Map Canvas 1"]
    only = opened["canvases"][0]
    assert [l["id"] for l in only["layers"]] == [lid] and only["view"] == {"scale": 3.0}
    assert opened["active_canvas"] == only["id"]


def test_canvas_input_is_checked(client, tmp_path):
    path = str(tmp_path / "x.agtaam")
    dup = [_canvas("c1", "A", []), _canvas("c1", "B", [])]
    assert client.post(f"{API}/file/project/save-as", json={"path": path, "canvases": dup}).status_code == 422
    bad_active = {"path": path, "canvases": [_canvas("c1", "A", [])], "active_canvas": "zzz"}
    assert client.post(f"{API}/file/project/save-as", json=bad_active).status_code == 422
    twice = [_canvas("c1", "A", [{"id": "x"}, {"id": "x"}])]
    assert client.post(f"{API}/file/project/save-as", json={"path": path, "canvases": twice}).status_code == 422
    bad_opacity = [_canvas("c1", "A", [{"id": "x", "opacity": 2}])]
    assert client.post(f"{API}/file/project/save-as", json={"path": path, "canvases": bad_opacity}).status_code == 422
