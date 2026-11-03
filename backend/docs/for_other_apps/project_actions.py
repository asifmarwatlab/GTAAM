"""File > Project: New / Open / Save / Save As, the way GIS desktop programs do them.

How it works (plain words)
  * The BACKEND is the real project: it holds the layers and writes the project file
    (<name>.agtaam, a JSON file) plus a "<name>_data" folder that keeps tool results
    (slope, contours ...) so nothing is lost.
  * This file only drives the window: it asks "save changes?" before anything that
    would throw work away, keeps the title / tab marker, and rebuilds the layer list
    after Open from what the backend sends back.

MainWindow inherits ProjectMixin, so these methods behave like normal MainWindow methods.
"""
from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox

EXT = ".agtaam"
FILTER = "A-GTAAM project (*.agtaam);;Older projects (*.json);;All files (*)"
DEFAULT_NAME = "Untitled"
# colour ramp used when a tool result is drawn (same choices the tool panels use)
TOOL_RAMP = {"hillshade": "greys", "slope": "slope", "aspect": "viridis", "curvature": "diverging"}


def _clean_error(exc: Exception) -> str:
    """'API error 404: {"error":..,"message":..}' -> just the message."""
    text = str(exc)
    if "{" in text:
        try:
            body = json.loads(text[text.index("{"):])
            return str(body.get("message") or body.get("detail") or body.get("error") or text)
        except (ValueError, AttributeError):
            pass
    return text


class ProjectMixin:
    _dirty = False
    _project_ready = False          # becomes True once the window is fully built

    # ------------------------------------------------------------------ setup
    def _init_project_actions(self) -> None:
        self._dirty = False
        self._project_ready = True
        self._last_dir = str(Path.home())
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.act_new_project)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, activated=self.act_save_project_as)
        self._refresh_title()

    # ---------------------------------------------------------- unsaved marker
    def mark_dirty(self) -> None:
        if self._project_ready and not self._dirty:
            self._dirty = True
            self._refresh_title()

    def _mark_clean(self) -> None:
        self._dirty = False
        self._refresh_title()

    def _refresh_title(self) -> None:
        star = "*" if self._dirty else ""
        self.setWindowTitle(f"{self.project_name}{star} - GTAAM")
        self.map.set_project_name(self.project_name)
        self.map.tab_dot.setVisible(self._dirty)

    def _set_project_name(self, name: str) -> None:
        self.project_name = name
        self._refresh_title()

    # ------------------------------------------------------------ ask first
    def _confirm_discard(self, action: str) -> bool:
        """True = go ahead. If there are unsaved changes: Save / Don't save / Cancel."""
        if not self._dirty:
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Unsaved changes")
        box.setText(f"Save changes to “{self.project_name}” before you {action}?")
        box.setInformativeText("Your changes will be lost if you don't save them.")
        save = box.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Don't Save", QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save)
        box.exec()
        clicked = box.clickedButton()
        if clicked is cancel:
            return False
        if clicked is save:
            return self.act_save_project()          # False if the user cancelled Save As
        return True

    def closeEvent(self, event) -> None:            # window X / Alt+F4 / File > Exit
        if self._confirm_discard("close"):
            event.accept()
        else:
            event.ignore()

    # ------------------------------------------------------------------- New
    def act_new_project(self) -> None:
        if not self._confirm_discard("create a new project"):
            return
        try:
            self.api_post("/file/project/new", {"name": "Untitled project"})
        except Exception as exc:
            self.show_toast(f"New project failed: {_clean_error(exc)}")
            return
        self.ws.reset()
        self.project_path = None
        self.project_name = DEFAULT_NAME
        self._refresh_everything()
        self._mark_clean()
        self.show_toast("New project")

    # ------------------------------------------------------------------ Save
    def _gui_state(self) -> dict:
        """What only the window knows: view, colour ramp, regions, layer visibility/order."""
        c = self.map.canvas
        return {
            "ramp": self.ws.ramp_name,
            "regions": [[list(p) for p in poly] for poly in self.ws.regions],
            "view": {"scale": c.scale, "ox": c.ox, "oy": c.oy},
            "layers": {l.id: {"visible": l.visible, "opacity": l.opacity} for l in self.ws.layers},
            "order": [l.id for l in self.ws.layers],
        }

    def act_save_project(self) -> bool:
        """Save over the current file (asks for a name the first time). True = saved."""
        if self.project_path is None:
            return self.act_save_project_as()
        return self._save_to(self.project_path, self.project_name, "/file/project/save")

    def act_save_project_as(self) -> bool:
        start = str(Path(self._last_dir) / f"{self.project_name}{EXT}")
        path, _ = QFileDialog.getSaveFileName(self, "Save project as", start, FILTER)
        if not path:
            return False
        p = Path(path)
        if p.suffix.lower() not in (EXT, ".json"):
            p = p.with_suffix(EXT)
        return self._save_to(p, p.stem, "/file/project/save-as")

    def _save_to(self, path: Path, name: str, route: str) -> bool:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            res = self.api_post(route, {"path": str(path), "name": name, "gui": self._gui_state()})
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Save project", f"Could not save the project:\n{_clean_error(exc)}")
            return False
        QApplication.restoreOverrideCursor()
        self.project_path = Path(res.get("path") or path)
        self._last_dir = str(self.project_path.parent)
        self._set_project_name(res.get("name", name))
        self._mark_clean()
        skipped = res.get("skipped_layers") or []
        if skipped:
            QMessageBox.warning(self, "Save project",
                                "These layers could not be written and are not in the project:\n\n"
                                + "\n".join(f"  • {n}" for n in skipped))
        self.show_toast(f"Project saved · {self.project_path.name}")
        return True

    # ------------------------------------------------------------------ Open
    def act_open_project(self) -> None:
        if not self._confirm_discard("open another project"):
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open project", self._last_dir, FILTER)
        if path:
            self.open_project_file(Path(path))

    def open_project_file(self, path: Path) -> None:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            res = self.api_post("/file/project/open", {"path": str(path)})
            layers = self.api_get_list("/file/add-data/layers")
            problems = self._rebuild_from_backend(layers, res.get("gui") or {})
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Open project", f"Could not open the project:\n{_clean_error(exc)}")
            return
        QApplication.restoreOverrideCursor()
        self.project_path = path
        self._last_dir = str(path.parent)
        self.project_name = res.get("name", path.stem)
        self._refresh_everything()
        self._apply_gui_view(res.get("gui") or {})
        self._mark_clean()
        missing = list(res.get("missing_layers") or [])
        if missing or problems:
            lines = [f"  • {n}  (file not found)" for n in missing]
            lines += [f"  • {n}" for n in problems]
            QMessageBox.warning(self, "Open project",
                                "The project opened, but some layers could not be loaded:\n\n"
                                + "\n".join(lines))
        self.show_toast(f"Project opened · {path.name}")

    def api_get_list(self, path: str) -> list:
        """api_get returns a dict; the layer list is a JSON array, so ask for it here."""
        import httpx
        from backend_runner import API_PREFIX, BASE_URL, wait_until_ready
        wait_until_ready()
        r = httpx.get(f"{BASE_URL}{API_PREFIX}{path}", timeout=60)
        r.raise_for_status()
        return r.json()

    def _rebuild_from_backend(self, layers: list, gui: dict) -> list[str]:
        """Recreate the layer list from what the backend loaded. Returns notes about layers
        that could not be drawn."""
        import numpy as np
        notes: list[str] = []
        self.ws.reset()
        if gui.get("ramp"):
            self.ws.ramp_name = gui["ramp"]
        bottom_first = list(reversed(layers))                   # backend lists top first
        for info in (i for i in bottom_first if i["kind"] == "raster"):
            try:
                self._restore_raster(info)
            except Exception as exc:
                notes.append(f"{info['name']}: {_clean_error(exc)}")
        for info in (i for i in bottom_first if i["kind"] == "vector"):
            try:
                parent = info.get("derived_from")
                if info.get("tool") == "contours" and parent and self.ws.has_layer(parent):
                    geo = self.api_get(f"/file/add-data/layers/{info['id']}/geojson")
                    self.ws.add_contour_layer(info["id"], info["name"], geo, self.ws.layer(parent))
                else:
                    notes.append(f"{info['name']}: vector layers cannot be drawn in this window yet")
            except Exception as exc:
                notes.append(f"{info['name']}: {_clean_error(exc)}")
        for info in layers:
            if info["kind"] == "basemap":
                notes.append(f"{info['name']}: basemap layers cannot be drawn in this window yet")
        # visibility, opacity and stacking order the user had
        saved = gui.get("layers", {})
        for lyr in self.ws.layers:
            s = saved.get(lyr.id)
            if s:
                lyr.visible, lyr.opacity = bool(s.get("visible", True)), int(s.get("opacity", 100))
        order = {lid: n for n, lid in enumerate(gui.get("order", []))}
        if order:
            self.ws.layers.sort(key=lambda l: order.get(l.id, len(order)))
        self.ws.regions = [[tuple(p) for p in poly] for poly in gui.get("regions", [])]
        return notes

    def _restore_raster(self, info: dict) -> None:
        """Same steps as Add Raster / a terrain tool: picture + statistics + histogram."""
        import numpy as np
        lid = info["id"]
        ramp = TOOL_RAMP.get(info.get("tool") or "")
        url = f"/file/export/map-image/{lid}" + (f"?ramp={ramp}" if ramp else "")
        rgba = self._decode_raster_image(self.api_get_bytes(url))
        s = self.api_get(f"/file/export/statistics/{lid}")
        h = self.api_get(f"/analysis/quality-statistics/histogram/{lid}", {"bins": 30})
        stats = {"min": s["min"], "max": s["max"], "mean": s["mean"], "std": s["std_dev"],
                 "median": s["median"], "count": s["count"], "nodata_count": s["nodata_count"],
                 "hist": np.asarray(h["counts"]), "edges": np.asarray(h["bin_edges"])}
        parent = info.get("derived_from")
        if info.get("tool") and parent and self.ws.has_layer(parent):
            desc = f"Derived from {self.ws.layer(parent).name}"
        else:
            desc = info.get("source") or ""
        self.ws.add_raster_image(lid, info["name"], rgba, desc, info, stats)

    def _apply_gui_view(self, gui: dict) -> None:
        v = gui.get("view")
        if v:
            c = self.map.canvas
            c.scale, c.ox, c.oy = v["scale"], v["ox"], v["oy"]
            c.update()
            c.viewChanged.emit()
        self._regions_changed()

    # ----------------------------------------------------------- rename (kept)
    def act_name_project(self) -> None:
        from ui.gui import ProjectNameDialog
        dialog = ProjectNameDialog(self.project_name, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._set_project_name(dialog.project_name)
        self.mark_dirty()
