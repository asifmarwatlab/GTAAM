"""The current project: its name, workspace state, and save/open as a .json file."""
from __future__ import annotations

import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from core.raster.reader import read_raster
from core.raster.writer import write_geotiff
from core.vector.reader import read_vector
from shared.errors import BadRequest
from shared.layer_store import Layer, layer_store

FORMAT = "A-GTAAM-project"
FORMAT_VERSION = 2
EXT = ".agtaam"                       # a JSON file with this extension
ALLOWED_EXT = {".agtaam", ".json"}    # .json = older projects, still readable


def default_workspace() -> dict:
    return copy.deepcopy({
        "mode": "explore",
        "fullscreen": False,
        "panes": {"contents": True, "statistics": True, "pixel_inspector": True},
        "viewport": {"center": None, "scale": None},
        "appearance": {"north_arrow": True, "scale_bar": True, "layer_label": False,
                       "colour_ramp": "terrain"},
        "display": {"regions": True, "reference_grid": False, "annotation": False},
        "annotations": [],
        "options": {"units": "metric", "decimals": 2, "default_ramp": "terrain"},
    })


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ProjectStore:
    def __init__(self) -> None:
        self.reset()

    def reset(self, name: str = "Untitled project") -> None:
        self.name = name
        self.path: str | None = None
        self.created = _now()
        self.workspace = default_workspace()
        self.gui: dict = {}                # the window's own state (view, colour ramp, ...)
        self._saved_version = layer_store.version

    def is_dirty(self) -> bool:
        return layer_store.version != self._saved_version

    def info(self) -> dict:
        return {"name": self.name, "path": self.path, "dirty": self.is_dirty(),
                "layer_count": len(layer_store.list()), "created": self.created}

    def new(self, name: str) -> None:
        layer_store.clear()
        self.reset(name)

    def reset_workspace(self) -> None:
        self.workspace = default_workspace()

    # ---- save / open ----
    @staticmethod
    def _rel(source: str, folder: Path) -> str | None:
        """Path of a data file relative to the project file (None if on another drive)."""
        try:
            return os.path.relpath(source, folder)
        except ValueError:
            return None

    def _store_derived(self, layer: Layer, data_dir: Path) -> str | None:
        """Write a tool result (slope, contours, ...) next to the project so it is not lost."""
        if layer.kind == "raster" and layer.raster is not None:
            target = data_dir / f"{layer.id}.tif"
            if not target.exists():              # tool results never change, so write once
                write_geotiff(layer.raster, target)
            return str(target)
        if layer.kind == "vector" and layer.geojson is not None:
            target = data_dir / f"{layer.id}.geojson"
            if not target.exists():
                data_dir.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(layer.geojson), encoding="utf-8")
            return str(target)
        return None

    def save(self, path: str | None = None, gui: dict | None = None,
             name: str | None = None) -> dict:
        target = path or self.path
        if not target:
            raise BadRequest("No file path yet - use Save As.", code="no_path")
        target_p = Path(target)
        if target_p.suffix.lower() not in ALLOWED_EXT:
            target_p = target_p.with_suffix(EXT)
        if name:
            self.name = name
        if gui is not None:
            self.gui = gui
        data_dir = target_p.with_name(target_p.stem + "_data")
        saved, skipped = [], []
        for layer in reversed(layer_store.list()):          # bottom first
            source = layer.source
            if layer.tool and layer.derived_from:            # a tool result: keep a copy
                try:
                    source = self._store_derived(layer, data_dir)
                except OSError:
                    source = None
                if source:
                    layer.source = source
            if source is None and layer.kind != "basemap":
                skipped.append(layer.name)
                continue
            saved.append({"id": layer.id, "name": layer.name, "kind": layer.kind,
                          "source": source,
                          "source_rel": self._rel(source, target_p.parent) if source and layer.kind != "basemap" else None,
                          "visible": layer.visible, "opacity": layer.opacity,
                          "derived_from": layer.derived_from, "tool": layer.tool,
                          "meta": layer.meta})
        doc = {"format": FORMAT, "version": FORMAT_VERSION, "name": self.name,
               "created": self.created, "saved": _now(), "workspace": self.workspace,
               "gui": self.gui, "layers": saved}
        target_p.parent.mkdir(parents=True, exist_ok=True)
        tmp = target_p.with_name(target_p.name + ".tmp")     # write fully, then swap in:
        tmp.write_text(json.dumps(doc, indent=2), encoding="utf-8")   # a crash never
        os.replace(tmp, target_p)                                     # leaves a half file
        self.path = str(target_p)
        self._saved_version = layer_store.version
        return {**self.info(), "saved_layers": len(saved), "skipped_layers": skipped}

    @staticmethod
    def _find(entry: dict, folder: Path) -> str | None:
        """The data file for a layer: the saved path, else the same place relative to the project."""
        src = entry.get("source")
        rel = entry.get("source_rel")
        for cand in (src, str(folder / rel) if rel else None):
            if cand and Path(cand).is_file():
                return cand
        return None

    def load(self, path: str) -> dict:
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"Project file not found: {path}")
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise BadRequest("This is not an A-GTAAM project file.", code="bad_project_file")
        if not isinstance(doc, dict) or doc.get("format") != FORMAT:
            raise BadRequest("This is not an A-GTAAM project file.", code="bad_project_file")
        layer_store.clear()
        missing = []
        for entry in doc.get("layers", []):                 # bottom first, so add() stacks right
            kind = entry["kind"]
            src = self._find(entry, p.parent) if kind != "basemap" else entry.get("source")
            try:
                if kind != "basemap" and src is None:
                    raise FileNotFoundError(entry.get("source"))
                layer = Layer(id=entry["id"], name=entry["name"], kind=kind, source=src,
                              visible=entry.get("visible", True),
                              opacity=entry.get("opacity", 1.0), meta=entry.get("meta", {}),
                              derived_from=entry.get("derived_from"), tool=entry.get("tool"))
                if kind == "raster":
                    layer.raster = read_raster(src)
                elif kind == "vector":
                    if Path(src).suffix.lower() in (".geojson", ".json"):
                        layer.geojson = json.loads(Path(src).read_text(encoding="utf-8"))
                    else:
                        layer.geojson = read_vector(src)
                layer_store.add(layer)
            except (FileNotFoundError, OSError, ValueError, ImportError):
                missing.append(entry.get("name", str(src)))
        self.name = doc.get("name", p.stem)
        self.created = doc.get("created", _now())
        self.workspace = {**default_workspace(), **doc.get("workspace", {})}
        self.gui = doc.get("gui", {}) or {}
        self.path = str(p)
        self._saved_version = layer_store.version
        return {**self.info(), "missing_layers": missing, "gui": self.gui}


project = ProjectStore()
