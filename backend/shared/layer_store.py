"""Remembers every loaded layer by id, so tools can say "run slope on layer ab12cd34".

Every request is separate, so the backend must hold the loaded DEMs somewhere.
This is that place. One instance (layer_store) is shared by all modules.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.raster.model import Raster
from shared.errors import BadRequest, NotFound


def new_id() -> str:
    return uuid.uuid4().hex[:8]


@dataclass
class Layer:
    name: str
    kind: str                                   # raster | vector | basemap
    id: str = field(default_factory=new_id)
    raster: Raster | None = None
    geojson: dict | None = None
    source: str | None = None                   # file path (or URL template for basemaps)
    visible: bool = True
    opacity: float = 1.0
    derived_from: str | None = None
    tool: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def info(self) -> dict:
        d = {
            "id": self.id, "name": self.name, "kind": self.kind, "source": self.source,
            "visible": self.visible, "opacity": self.opacity,
            "derived_from": self.derived_from, "tool": self.tool, "meta": self.meta,
        }
        if self.raster is not None:
            d.update(self.raster.summary())
        return d


class LayerStore:
    def __init__(self) -> None:
        self._layers: dict[str, Layer] = {}
        self._order: list[str] = []             # drawing order, top first
        self._lock = threading.RLock()
        self.version = 0                        # bumps on every change (used for "unsaved")
        self._clear_hooks: list = []
        self._remove_hooks: list = []

    def on_clear(self, fn) -> None:
        """Run fn() whenever all layers are cleared (new / open project)."""
        self._clear_hooks.append(fn)

    def on_remove(self, fn) -> None:
        """Run fn(layer_id) whenever one layer is removed."""
        self._remove_hooks.append(fn)

    def _bump(self) -> None:
        self.version += 1

    def add(self, layer: Layer) -> Layer:
        with self._lock:
            self._layers[layer.id] = layer
            self._order.insert(0, layer.id)
            self._bump()
        return layer

    def get(self, layer_id: str) -> Layer:
        try:
            return self._layers[layer_id]
        except KeyError:
            raise NotFound(f"Layer '{layer_id}' does not exist.", code="layer_not_found")

    def remove(self, layer_id: str) -> None:
        with self._lock:
            self.get(layer_id)
            del self._layers[layer_id]
            self._order.remove(layer_id)
            self._bump()
            for hook in self._remove_hooks:
                hook(layer_id)

    def list(self, kind: str | None = None) -> list[Layer]:
        with self._lock:
            layers = [self._layers[i] for i in self._order]
        return [l for l in layers if kind is None or l.kind == kind]

    def update(self, layer_id: str, **fields) -> Layer:
        with self._lock:
            layer = self.get(layer_id)
            for k, v in fields.items():
                if v is not None:
                    setattr(layer, k, v)
            self._bump()
        return layer

    def reorder(self, layer_ids: list[str]) -> None:
        with self._lock:
            if sorted(layer_ids) != sorted(self._order):
                raise BadRequest("layer_ids must list every existing layer exactly once.")
            self._order = list(layer_ids)
            self._bump()

    def clear(self) -> None:
        with self._lock:
            self._layers.clear()
            self._order.clear()
            self._bump()
            for hook in self._clear_hooks:
                hook()


layer_store = LayerStore()


def get_raster_layer(layer_id: str) -> Layer:
    layer = layer_store.get(layer_id)
    if layer.kind != "raster" or layer.raster is None:
        raise BadRequest(f"Layer '{layer.name}' is not a raster layer.", code="not_a_raster")
    return layer


def add_raster_layer(raster: Raster, name: str, *, source: str | None = None,
                     derived_from: str | None = None, tool: str | None = None) -> Layer:
    return layer_store.add(Layer(name=name, kind="raster", raster=raster, source=source,
                                 derived_from=derived_from, tool=tool))


def add_vector_layer(geojson: dict, name: str, *, source: str | None = None,
                     derived_from: str | None = None, tool: str | None = None) -> Layer:
    return layer_store.add(Layer(name=name, kind="vector", geojson=geojson, source=source,
                                 derived_from=derived_from, tool=tool))
