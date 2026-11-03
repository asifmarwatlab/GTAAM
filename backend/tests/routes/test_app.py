def test_health_lists_all_six_modules(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert set(body["modules"]) == {"file", "view", "analysis", "tools", "terrain_editing", "terrain_mosaic"}


def test_every_ribbon_group_has_endpoints(client):
    paths = set(client.get("/openapi.json").json()["paths"])
    for prefix in ("/file/project", "/file/add-data", "/file/export", "/file/workspace",
                   "/view/navigate", "/view/panes", "/view/appearance", "/view/display",
                   "/analysis/measure", "/analysis/quality-statistics", "/analysis/surface-analysis",
                   "/analysis/terrain-derivatives", "/tools/data-management", "/tools/inspect",
                   "/tools/workspace", "/terrain-editing/selection", "/terrain-editing/modify-terrain",
                   "/terrain-editing/review", "/terrain-editing/output", "/terrain-mosaic/input",
                   "/terrain-mosaic/overlap-analysis", "/terrain-mosaic/mosaic", "/terrain-mosaic/output"):
        assert any(p.startswith(f"/api/v1{prefix}") for p in paths), prefix


def test_unknown_layer_gives_clean_404(client):
    r = client.get("/api/v1/analysis/quality-statistics/layer-statistics/nope")
    assert r.status_code == 404 and r.json()["error"] == "layer_not_found"


def test_bad_input_gives_422_not_a_crash(client, layer_id):
    r = client.post("/api/v1/analysis/measure/distance", json={"layer_id": layer_id, "points": [[1, 2]]})
    assert r.status_code == 422
