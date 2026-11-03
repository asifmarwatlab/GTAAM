from __future__ import annotations
from collections import OrderedDict
import numpy as np
from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPolygonF,
)
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QMenu, QPushButton, QToolButton,
    QVBoxLayout, QWidget,
)

from ui.panels.icon_generator import icon, pixmap
from ui.panels.layer_statistics import SampleWorkspace, fmt

PX_METERS = 0.000264583      

# ----------------------------------------------------------------------------
# canvas
# ----------------------------------------------------------------------------
class MapCanvas(QWidget):
    pixelMoved = pyqtSignal(float, float)     
    viewChanged = pyqtSignal()
    regionsChanged = pyqtSignal()
    modeChanged = pyqtSignal(str)
    hintChanged = pyqtSignal(str)             
    statusMessage = pyqtSignal(str)

    MIN_SCALE, MAX_SCALE = 0.04, 80.0

    def __init__(self, ws: SampleWorkspace) -> None:
        super().__init__()
        self.ws = ws
        self.scale = 1.0
        self.ox = 0.0
        self.oy = 0.0
        self.mode = "explore"                 # explore | draw | select
        self.draft: list[tuple[float, float]] = []
        self.hover: tuple[float, float] | None = None
        self.selected_region = -1
        self.preview: str | None = None        # None | "edit" | "mosaic"
        self.selected_layer_id: str | None = None
        self._press: QPointF | None = None
        self._dragged = False
        self._dbl = False
        self._imgs: dict = {}
        self._paths: list | None = None
        self._fitted = False
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(320, 240)
        self._update_cursor()

    # ----- view maths -------------------------------------------------------
    def to_cell(self, x: float, y: float) -> tuple[float, float]:
        return (x - self.ox) / self.scale, (y - self.oy) / self.scale

    def to_screen(self, cx: float, cy: float) -> QPointF:
        return QPointF(cx * self.scale + self.ox, cy * self.scale + self.oy)

    def meters_per_pixel(self) -> float:
        return self.ws.CELL / self.scale

    def scale_denominator(self) -> float:
        return self.meters_per_pixel() / PX_METERS

    def fit(self, extent: tuple[float, float, float, float] | None = None) -> None:
        x0, y0, x1, y1 = extent or self.ws.extent_cells()
        w, h = max(self.width(), 1), max(self.height(), 1)
        ew, eh = max(x1 - x0, 1), max(y1 - y0, 1)
        self.scale = max(self.MIN_SCALE, min(self.MAX_SCALE, min(w / ew, h / eh) * 0.9))
        self.ox = w / 2 - (x0 + ew / 2) * self.scale
        self.oy = h / 2 - (y0 + eh / 2) * self.scale
        self._fitted = True
        self.update()
        self.viewChanged.emit()

    def zoom_by(self, factor: float, anchor: QPointF | None = None) -> None:
        a = anchor or QPointF(self.width() / 2, self.height() / 2)
        cx, cy = self.to_cell(a.x(), a.y())
        self.scale = max(self.MIN_SCALE, min(self.MAX_SCALE, self.scale * factor))
        self.ox = a.x() - cx * self.scale
        self.oy = a.y() - cy * self.scale
        self.update()
        self.viewChanged.emit()

    def set_scale_denominator(self, denom: float) -> None:
        a = QPointF(self.width() / 2, self.height() / 2)
        cx, cy = self.to_cell(a.x(), a.y())
        self.scale = max(self.MIN_SCALE, min(self.MAX_SCALE, self.ws.CELL / (denom * PX_METERS)))
        self.ox = a.x() - cx * self.scale
        self.oy = a.y() - cy * self.scale
        self.update()
        self.viewChanged.emit()

    def zoom_to_layer(self, lid: str) -> None:
        lyr = self.ws.layer(lid)
        if lyr.group == "raster":
            shape = lyr.data.shape if lyr.data is not None else (
                lyr.rgba.shape[:2] if lyr.rgba is not None else None
            )
            if shape is not None:
                self.fit((lyr.col0, 0, lyr.col0 + shape[1], shape[0]))
            else:
                self.fit()
        elif lid == "regions" and self.ws.regions:
            pts = [p for poly in self.ws.regions for p in poly]
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            self.fit((min(xs) - 20, min(ys) - 20, max(xs) + 20, max(ys) + 20))
        elif lyr.shapes:
            x0, y0, x1, y1 = lyr.shapes["view"]
            self.fit((x0, y0, x1, y1))
        elif lyr.group == "vector" and lyr.vector_lines:
            self.fit((0, 0, lyr.source_width or 1, lyr.source_height or 1))
        else:
            self.fit()

    # ----- modes ------------------------------------------------------------
    def set_mode(self, mode: str) -> None:
        if mode != "draw":
            self.draft.clear()
            self.hintChanged.emit("")
        else:
            self.hintChanged.emit("Click to add vertices · Double-click to finish · Esc to cancel")
        self.mode = mode
        self._update_cursor()
        self.modeChanged.emit(mode)
        self.update()

    def _update_cursor(self) -> None:
        self.setCursor({"explore": Qt.CursorShape.OpenHandCursor,
                        "draw": Qt.CursorShape.CrossCursor,
                        "select": Qt.CursorShape.PointingHandCursor}[self.mode])

    def set_preview(self, kind: str | None) -> None:
        self.preview = kind
        self.update()

    def cancel_draw(self) -> None:
        if self.draft:
            self.draft.clear()
            self.update()
            self.statusMessage.emit("Drawing cancelled")
        if self.mode == "draw":
            self.set_mode("explore")

    def finish_polygon(self) -> None:
        if len(self.draft) >= 3:
            self.ws.regions.append(list(self.draft))
            self.selected_region = len(self.ws.regions) - 1
            self.statusMessage.emit(f"Editing region {len(self.ws.regions)} added")
            self.regionsChanged.emit()
        else:
            self.statusMessage.emit("A region needs at least three vertices")
        self.draft.clear()
        self.set_mode("explore")

    def delete_selected(self) -> bool:
        if 0 <= self.selected_region < len(self.ws.regions):
            del self.ws.regions[self.selected_region]
            self.selected_region = -1
            self.regionsChanged.emit()
            self.update()
            return True
        return False

    def clear_regions(self) -> None:
        self.ws.regions.clear()
        self.selected_region = -1
        self.regionsChanged.emit()
        self.update()

    def invalidate(self) -> None:
        self._imgs.clear()
        self._paths = None
        self.update()

    # ----- painting ---------------------------------------------------------
    def _image(self, lyr) -> QImage:
        key = (lyr.id, id(lyr.rgba))
        img = self._imgs.get(key)
        if img is None:
            arr = np.ascontiguousarray(lyr.rgba)
            h, w = arr.shape[:2]
            img = QImage(arr.data, w, h, w * 4, QImage.Format.Format_RGBA8888).copy()
            self._imgs[key] = img
        return img

    def _contour_paths(self) -> list:
        if self._paths is None:
            self._paths = []
            for level, lines in self.ws.contours:
                path = QPainterPath()
                for ln in lines:
                    path.moveTo(float(ln[0][0]), float(ln[0][1]))
                    for x, y in ln[1:]:
                        path.lineTo(float(x), float(y))
                self._paths.append((level, path))
        return self._paths

    def paintEvent(self, _e) -> None:
        if not self._fitted and self.width() > 50:
            self.fit()
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#f1f3f5"))
        ws, s = self.ws, self.scale
        vis = {l.id: l for l in ws.layers if l.visible}

        # reference grid (basemap) - 500 m lines in screen space
        if "basemap" in vis:
            p.setOpacity(vis["basemap"].opacity / 100)
            step = 50 * s
            if step > 10:
                p.setPen(QPen(QColor("#c8d7e0"), 1))
                x = self.ox % step
                while x < self.width():
                    p.drawLine(QPointF(x, 0), QPointF(x, self.height()))
                    x += step
                y = self.oy % step
                while y < self.height():
                    p.drawLine(QPointF(0, y), QPointF(self.width(), y))
                    y += step
            p.setOpacity(1)

        p.save()
        p.translate(self.ox, self.oy)
        p.scale(s, s)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, s < 2.5)

        raster_order = ("east", "slope", "dem", "hillshade")
        rasters = [vis[lid] for lid in raster_order if lid in vis]
        rasters.extend(
            lyr for lyr in self.ws.rasters()
            if lyr.visible and lyr.id not in raster_order
        )
        selected = next(
            (lyr for lyr in rasters
             if lyr.id == self.selected_layer_id and lyr.user_added),
            None,
        )
        if selected is not None:
            rasters = [lyr for lyr in rasters if lyr.id != selected.id]
            rasters.append(selected)
        for lyr in rasters:
            if lyr.rgba is None:
                continue
            p.setOpacity(lyr.opacity / 100)
            if lyr.id == "hillshade" and ("dem" in vis or "slope" in vis):
                p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
            h, w = lyr.rgba.shape[:2]
            p.drawImage(QRectF(lyr.col0, 0, w, h), self._image(lyr))
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        p.setOpacity(1)

        # raster outline
        p.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(QColor(36, 69, 87, 120), 1)
        pen.setCosmetic(True)
        p.setPen(pen)
        for lid in ("dem", "east"):
            if lid in vis:
                l = vis[lid]
                p.drawRect(QRectF(l.col0, 0, l.data.shape[1], l.data.shape[0]))

        if "contours" in vis:
            p.setOpacity(vis["contours"].opacity / 100)
            for level, path in self._contour_paths():
                major = int(level) % 1000 == 0
                pen = QPen(QColor("#5c3d27" if major else "#7d5c43"), 1.5 if major else 0.8)
                pen.setCosmetic(True)
                p.setPen(pen)
                p.drawPath(path)
            p.setOpacity(1)

        for lyr in self.ws.layers:
            if not lyr.visible or lyr.group != "vector" or not lyr.vector_lines:
                continue
            p.setOpacity(lyr.opacity / 100)
            for level, points in lyr.vector_lines:
                path = QPainterPath()
                path.moveTo(float(points[0, 0]), float(points[0, 1]))
                for x, y in points[1:]:
                    path.lineTo(float(x), float(y))
                major = int(level) % 1000 == 0
                pen = QPen(QColor("#5c3d27" if major else "#7d5c43"),
                           1.5 if major else 0.8)
                pen.setCosmetic(True)
                p.setPen(pen)
                p.drawPath(path)
        p.setOpacity(1)

        # mosaic preview: highlight the overlap between Upper_Indus_DEM and DEM_East
        if self.preview == "mosaic":
            east = ws.layer("east")
            r = QRectF(east.col0, 0, ws.WIDTH - east.col0, ws.HEIGHT)
            p.setBrush(QBrush(QColor(224, 123, 0, 120), Qt.BrushStyle.BDiagPattern))
            pen = QPen(QColor("#e07b00"), 2, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.drawRect(r)
        # vector files: the backend sends shapes already in drawing cells
        for lyr in reversed(self.ws.layers):             # top of the Layers list draws on top
            if lyr.visible and lyr.shapes:
                self._draw_shapes(p, lyr)
        p.setOpacity(1)
        p.restore()

        # editing regions (vector layer)
        if "regions" in vis:
            p.setOpacity(vis["regions"].opacity / 100)
            for i, poly in enumerate(ws.regions):
                pts = QPolygonF([self.to_screen(x, y) for x, y in poly])
                sel = i == self.selected_region
                col = QColor("#e07b00") if sel else QColor("#1f6f9a")
                fill = QColor(col)
                fill.setAlpha(70 if sel else 42)
                brush = QBrush(fill)
                if self.preview == "edit":
                    brush = QBrush(QColor(224, 123, 0, 140), Qt.BrushStyle.BDiagPattern)
                p.setBrush(brush)
                p.setPen(QPen(col, 2.2 if sel else 1.8))
                p.drawPolygon(pts)
                p.setBrush(QColor("#ffffff"))
                for pt in pts:
                    p.drawRect(QRectF(pt.x() - 3, pt.y() - 3, 6, 6))
                c = pts.boundingRect().center()
                f = QFont(self.font())
                f.setPointSizeF(9.5)
                f.setBold(True)
                p.setFont(f)
                p.setPen(QColor("#12384f"))
                p.drawText(QPointF(c.x() - 24, c.y() + 4), f"Region {i + 1}")
            p.setOpacity(1)

        # polygon being drawn
        if self.draft:
            pts = [self.to_screen(x, y) for x, y in self.draft]
            p.setPen(QPen(QColor("#e07b00"), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for a, b in zip(pts, pts[1:]):
                p.drawLine(a, b)
            if self.hover is not None:
                dash = QPen(QColor("#e07b00"), 1.5, Qt.PenStyle.DashLine)
                p.setPen(dash)
                p.drawLine(pts[-1], self.to_screen(*self.hover))
            p.setPen(QPen(QColor("#e07b00"), 2))
            p.setBrush(QColor("#ffffff"))
            for pt in pts:
                p.drawEllipse(pt, 4, 4)
        p.end()

    @staticmethod
    def _draw_shapes(p: QPainter, lyr) -> None:
        col = QColor(lyr.vec_color)
        fill = QColor(col)
        fill.setAlpha(70)
        pen = QPen(col, 1.4)
        pen.setCosmetic(True)
        p.setOpacity(lyr.opacity / 100)
        for f in lyr.shapes["features"]:
            if f["polys"]:
                path = QPainterPath()
                path.setFillRule(Qt.FillRule.OddEvenFill)
                for ring in f["polys"]:
                    path.moveTo(*ring[0])
                    for pt in ring[1:]:
                        path.lineTo(*pt)
                    path.closeSubpath()
                p.setPen(pen)
                p.setBrush(QBrush(fill))
                p.drawPath(path)
            for line in f["lines"]:
                path = QPainterPath()
                path.moveTo(*line[0])
                for pt in line[1:]:
                    path.lineTo(*pt)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(path)
            if f["pts"]:
                dot = QPen(col, 8)
                dot.setCosmetic(True)
                dot.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(dot)
                for x, y in f["pts"]:
                    p.drawPoint(QPointF(x, y))

    # ----- interaction ------------------------------------------------------
    def resizeEvent(self, e) -> None:
        if self._fitted:
            self.viewChanged.emit()
        super().resizeEvent(e)

    def wheelEvent(self, e) -> None:
        delta = e.angleDelta().y()
        if delta:
            self.zoom_by(1.0016 ** delta, e.position())
        e.accept()

    def mousePressEvent(self, e) -> None:
        self.setFocus()
        if e.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
            self._press = e.position()
            self._dragged = False
            self._last = e.position()
        elif e.button() == Qt.MouseButton.RightButton and self.mode == "draw" and self.draft:
            self.draft.pop()
            self.update()

    def mouseMoveEvent(self, e) -> None:
        pos = e.position()
        cx, cy = self.to_cell(pos.x(), pos.y())
        self.hover = (cx, cy)
        self.pixelMoved.emit(cx, cy)
        if self._press is not None and e.buttons() & (Qt.MouseButton.LeftButton | Qt.MouseButton.MiddleButton):
            if not self._dragged and (pos - self._press).manhattanLength() > 4:
                self._dragged = True
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            if self._dragged:
                d = pos - self._last
                self.ox += d.x()
                self.oy += d.y()
                self.update()
                self.viewChanged.emit()
        self._last = pos
        if self.draft:
            self.update()

    def mouseReleaseEvent(self, e) -> None:
        if e.button() != Qt.MouseButton.LeftButton or self._press is None:
            self._press = None
            return
        was_drag = self._dragged
        self._press = None
        self._dragged = False
        self._update_cursor()
        if was_drag:
            return
        if self._dbl:
            self._dbl = False
            return
        cx, cy = self.to_cell(e.position().x(), e.position().y())
        if self.mode == "draw":
            self.draft.append((cx, cy))
            self.update()
        elif self.mode == "select":
            hit = -1
            for i in range(len(self.ws.regions) - 1, -1, -1):
                poly = QPolygonF([QPointF(x, y) for x, y in self.ws.regions[i]])
                if poly.containsPoint(QPointF(cx, cy), Qt.FillRule.OddEvenFill):
                    hit = i
                    break
            self.selected_region = hit
            self.statusMessage.emit(f"Region {hit + 1} selected" if hit >= 0 else "No region selected")
            self.update()

    def mouseDoubleClickEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton and self.mode == "draw":
            self._dbl = True
            self.finish_polygon()

    def keyPressEvent(self, e) -> None:
        if e.key() == Qt.Key.Key_Escape:
            self.cancel_draw()
        elif e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.mode == "draw":
            self.finish_polygon()
        elif e.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self.mode == "select":
            self.delete_selected()
        elif e.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.zoom_by(1.4)
        elif e.key() == Qt.Key.Key_Minus:
            self.zoom_by(1 / 1.4)
        else:
            super().keyPressEvent(e)


# ----------------------------------------------------------------------------
# overlay widgets
# ----------------------------------------------------------------------------
class NorthArrow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(40, 56)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(255, 255, 255, 215))
        p.setPen(QPen(QColor("#c4d4de"), 1))
        p.drawRoundedRect(QRectF(0.5, 0.5, 39, 55), 8, 8)
        f = QFont(self.font())
        f.setBold(True)
        f.setPointSizeF(10)
        p.setFont(f)
        p.setPen(QColor("#244557"))
        p.drawText(QRectF(0, 3, 40, 16), Qt.AlignmentFlag.AlignCenter, "N")
        right = QPolygonF([QPointF(20, 20), QPointF(30, 50), QPointF(20, 44)])
        left = QPolygonF([QPointF(20, 20), QPointF(20, 44), QPointF(10, 50)])
        p.setBrush(QColor("#244557"))
        p.setPen(QPen(QColor("#244557"), 1))
        p.drawPolygon(right)
        p.setBrush(QColor("#ffffff"))
        p.drawPolygon(left)


class ScaleBar(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.bar_px, self.text = 93, "500 m"
        self.setFixedHeight(38)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._resize()

    def _resize(self) -> None:
        self.setFixedWidth(self.bar_px + 28)

    def set_scale(self, bar_px: int, text: str) -> None:
        self.bar_px, self.text = bar_px, text
        self._resize()
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setBrush(QColor(255, 255, 255, 225))
        p.setPen(QPen(QColor("#c4d4de"), 1))
        p.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 7, 7)
        p.setPen(QPen(QColor("#244557"), 2))
        y, x0 = 26, 14
        p.drawLine(x0, y, x0 + self.bar_px, y)
        p.drawLine(x0, y - 5, x0, y)
        p.drawLine(x0 + self.bar_px, y - 5, x0 + self.bar_px, y)
        f = QFont(self.font())
        f.setPointSizeF(9)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(x0, 3, self.bar_px, 16), Qt.AlignmentFlag.AlignLeft, self.text)


class MapSurface(QWidget):

    def __init__(self, canvas: MapCanvas) -> None:
        super().__init__()
        self.canvas = canvas
        canvas.setParent(self)

        # layer label (top-left)
        self.label_box = QFrame(self)
        self.label_box.setObjectName("mapLabel")
        ll = QHBoxLayout(self.label_box)
        ll.setContentsMargins(10, 6, 10, 6)
        ll.setSpacing(7)
        dot = QLabel()
        dot.setObjectName("greenDot")
        dot.setFixedSize(8, 8)
        self.label = QLabel("Upper_Indus_DEM.tif")
        self.label.setObjectName("mapLabelText")
        chip = QLabel("SAMPLE")
        chip.setObjectName("sampleChip")
        ll.addWidget(dot)
        ll.addWidget(self.label)
        ll.addWidget(chip)
        self.label_box.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.label_box.hide()

        # navigation (top-right)
        self.nav = QFrame(self)
        self.nav.setObjectName("mapNav")
        nl = QVBoxLayout(self.nav)
        nl.setContentsMargins(3, 3, 3, 3)
        nl.setSpacing(2)
        self.zoom_in = self._nav_btn("plus", "Zoom in")
        self.zoom_out = self._nav_btn("minus", "Zoom out")
        self.full_extent = self._nav_btn("fullscreen", "Full extent")
        div = QFrame()
        div.setObjectName("navDivider")
        div.setFixedHeight(1)
        nl.addWidget(self.zoom_in)
        nl.addWidget(self.zoom_out)
        nl.addWidget(div)
        nl.addWidget(self.full_extent)

        self.north = NorthArrow()
        self.north.setParent(self)
        self.scale_bar = ScaleBar()
        self.scale_bar.setParent(self)
        self.label_box.hide()

        self.annotation = QLabel("", self)
        self.annotation.setObjectName("mapAnnotation")
        self.annotation.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.annotation.hide()

        self.hint = QLabel("", self)
        self.hint.setObjectName("drawHint")
        self.hint.hide()

        self.banner = QFrame(self)
        self.banner.setObjectName("previewBanner")
        bl = QHBoxLayout(self.banner)
        bl.setContentsMargins(12, 6, 8, 6)
        bl.setSpacing(8)
        bdot = QLabel()
        bdot.setObjectName("amberDot")
        bdot.setFixedSize(9, 9)
        self.banner_text = QLabel("Modification preview")
        self.banner_text.setObjectName("bannerText")
        self.discard = QPushButton("Discard")
        self.discard.setObjectName("discardButton")
        self.discard.setCursor(Qt.CursorShape.PointingHandCursor)
        bl.addWidget(bdot)
        bl.addWidget(self.banner_text)
        bl.addWidget(self.discard)
        self.banner.hide()

        # pixel inspector (bottom-right)
        self.inspector = QFrame(self)
        self.inspector.setObjectName("pixelInspector")
        self.inspector.setFixedWidth(262)
        g = QGridLayout(self.inspector)
        g.setContentsMargins(12, 10, 12, 10)
        g.setHorizontalSpacing(8)
        g.setVerticalSpacing(5)
        head = QHBoxLayout()
        hi = QLabel()
        hi.setPixmap(pixmap("crosshair", "#1f6f9a", 18))
        ht = QLabel("PIXEL INSPECTOR")
        ht.setObjectName("inspectorHead")
        self.live_label = QLabel("NO DATA")
        self.live_label.setObjectName("liveLabel")
        head.addWidget(hi)
        head.addWidget(ht)
        head.addStretch(1)
        head.addWidget(self.live_label)
        g.addLayout(head, 0, 0, 1, 3)
        self.easting_name, self.easting, self.easting_unit = self._coord_row(
            g, 1, "Easting", "—"
        )
        self.northing_name, self.northing, self.northing_unit = self._coord_row(
            g, 2, "Northing", "—"
        )
        self.ptype = QLabel("—")
        self.ptype.setObjectName("pixelType")
        self.pvalue = QLabel("—")
        self.pvalue.setObjectName("pixelValue")
        self.punit = QLabel("—")
        self.punit.setObjectName("pixelUnit")
        g.addWidget(self.ptype, 3, 0)
        g.addWidget(self.pvalue, 3, 1, Qt.AlignmentFlag.AlignRight)
        g.addWidget(self.punit, 3, 2)
        self.pcell = QLabel("—")
        self.pcell.setObjectName("pixelMeta")
        self.band = QLabel("—")
        self.band.setObjectName("pixelMeta")
        g.addWidget(self.pcell, 4, 0, 1, 2)
        g.addWidget(self.band, 4, 2, Qt.AlignmentFlag.AlignRight)
        g.setColumnStretch(1, 1)
        self.inspector.adjustSize()

    @staticmethod
    def _nav_btn(name: str, tip: str) -> QToolButton:
        b = QToolButton()
        b.setObjectName("navButton")
        b.setIcon(icon(name, "#244557", 20))
        b.setToolTip(tip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFixedSize(34, 34)
        return b

    @staticmethod
    def _coord_row(
        g: QGridLayout, row: int, name: str, val: str
    ) -> tuple[QLabel, QLabel, QLabel]:
        a = QLabel(name)
        a.setObjectName("coordName")
        b = QLabel(val)
        b.setObjectName("coordValue")
        b.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        c = QLabel("m")
        c.setObjectName("coordUnit")
        g.addWidget(a, row, 0)
        g.addWidget(b, row, 1)
        g.addWidget(c, row, 2)
        return a, b, c

    def resizeEvent(self, e) -> None:
        self._layout_overlays()
        super().resizeEvent(e)

    def _layout_overlays(self) -> None:
        w, h = self.width(), self.height()
        self.canvas.setGeometry(0, 0, w, h)
        self.label_box.adjustSize()
        self.label_box.move(14, 14)
        self.nav.adjustSize()
        self.nav.move(w - self.nav.width() - 14, 14)
        self.north.move(w - self.north.width() - 14, 14 + self.nav.height() + 12)
        self.scale_bar.move(14, h - self.scale_bar.height() - 14)
        self.inspector.adjustSize()
        self.inspector.move(w - self.inspector.width() - 14, h - self.inspector.height() - 14)
        for box in (self.hint, self.banner):
            box.adjustSize()
            box.move((w - box.width()) // 2, 14)

    def reposition(self) -> None:
        self._layout_overlays()

    def raise_overlays(self) -> None:
        for wdg in (self.label_box, self.nav, self.north, self.scale_bar, self.annotation,
                    self.hint, self.banner, self.inspector):
            wdg.raise_()


# ----------------------------------------------------------------------------
# whole centre section
# ----------------------------------------------------------------------------
class MapSection(QFrame):
    layersToggled = pyqtSignal()
    statisticsToggled = pyqtSignal()
    discardPreview = pyqtSignal()
    pixelSampleRequested = pyqtSignal(str, int, int)

    SCALE_PRESETS = [5000, 10000, 20000, 50000, 100000, 250000]

    def __init__(self, ws: SampleWorkspace) -> None:
        super().__init__()
        self.ws = ws
        self.setObjectName("mapSection")
        self.canvas = MapCanvas(ws)
        self.surface = MapSurface(self.canvas)

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # tab bar
        bar = QFrame()
        bar.setObjectName("mapTabbar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(10, 0, 10, 0)
        bl.setSpacing(10)
        tab = QFrame()
        tab.setObjectName("mapTab")
        tl = QHBoxLayout(tab)
        tl.setContentsMargins(12, 0, 12, 0)
        tl.setSpacing(7)
        ti = QLabel()
        ti.setPixmap(pixmap("terrain", "#1f6f9a", 18))

        self.project_name = "Untitled"
        self.tab_text = QLabel(self.project_name)
        self.tab_text.setObjectName("mapTabText")
        tt = self.tab_text

        td = QLabel()
        td.setObjectName("tinyDot")
        td.setFixedSize(6, 6)
        tl.addWidget(ti)
        tl.addWidget(tt)
        td.hide()                      # shown while the project has unsaved changes
        self.tab_dot = td
        tl.addWidget(td)
        ctx = QLabel("2D · Map view")
        ctx.setObjectName("mapContext")
        bl.addWidget(tab)
        bl.addWidget(ctx)
        bl.addStretch(1)
        self.btn_layers = self._pane_button("layers", "Layers", "Show or hide layers")
        self.btn_stats = self._pane_button("stats", "Statistics", "Show or hide layer statistics")
        self.btn_layers.clicked.connect(self.layersToggled)
        self.btn_stats.clicked.connect(self.statisticsToggled)
        bl.addWidget(self.btn_layers)
        bl.addWidget(self.btn_stats)
        v.addWidget(bar)
        v.addWidget(self.surface, 1)

        # footer
        foot = QFrame()
        foot.setObjectName("mapFooter")
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(10, 0, 12, 0)
        fl.setSpacing(14)
        self.scale_btn = QToolButton()
        self.scale_btn.setObjectName("scaleButton")
        self.scale_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.scale_btn.setToolTip("Map scale")
        menu = QMenu(self.scale_btn)
        for d in self.SCALE_PRESETS:
            menu.addAction(f"1 : {d:,}", lambda dd=d: self.canvas.set_scale_denominator(dd))
        menu.addSeparator()
        menu.addAction("Full extent", lambda: self.canvas.fit())
        self.scale_btn.setMenu(menu)
        fl.addWidget(self.scale_btn)
        self.tool_label = QLabel("Explore")
        self.tool_label.setObjectName("footerTool")
        self.tool_label.hide()
        fl.addStretch(1)
        dot = QLabel()
        dot.setObjectName("greenDot")
        dot.setFixedSize(8, 8)
        fl.addWidget(dot)
        crs = QLabel(ws.CRS_NAME)
        crs.setObjectName("footerCrs")
        fl.addWidget(crs)
        v.addWidget(foot)

        # wiring
        s = self.surface
        s.zoom_in.clicked.connect(lambda: self.canvas.zoom_by(1.5))
        s.zoom_out.clicked.connect(lambda: self.canvas.zoom_by(1 / 1.5))
        s.full_extent.clicked.connect(lambda: self.canvas.fit())
        s.discard.clicked.connect(self.discardPreview)
        self.canvas.viewChanged.connect(self.update_scale)
        self.canvas.hintChanged.connect(self.show_hint)
        self.canvas.regionsChanged.connect(self.update_annotation)
        self.canvas.modeChanged.connect(self._mode_changed)
        self.canvas.pixelMoved.connect(self._pixel_moved)
        self.selected_layer_id: str | None = None
        self._pixel_sample_timer = QTimer(self, singleShot=True)
        self._pixel_sample_timer.setInterval(16)
        self._pixel_sample_timer.timeout.connect(self._request_pixel_sample)
        self._pending_pixel_sample: tuple[str, int, int] | None = None
        self._last_pixel_cell: tuple[str, int, int] | None = None
        self._pixel_cache: OrderedDict[tuple[str, int, int], dict] = OrderedDict()
        self.update_scale()
        self.update_annotation()
        self.clear_pixel()
        s.raise_overlays()

    @staticmethod
    def _pane_button(ic: str, text: str, tip: str) -> QToolButton:
        b = QToolButton()
        b.setObjectName("paneButton")
        b.setText(text)
        b.setIcon(icon(ic, "#244557", 18))
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        b.setCheckable(True)
        b.setChecked(True)
        b.setToolTip(tip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        return b

    # ----- slots ------------------------------------------------------------
    def _mode_changed(self, mode: str) -> None:
        self.tool_label.setText({"explore": "Explore", "draw": "Draw editing region",
                                 "select": "Select region"}[mode])

    def _pixel_moved(self, cx: float, cy: float) -> None:
        if self.selected_layer_id is None:
            self.clear_pixel()
            return
        lyr = self.ws.layer(self.selected_layer_id)
        if lyr.user_added and lyr.data is None and lyr.rgba is not None:
            display_height, display_width = lyr.rgba.shape[:2]
            if not (0 <= cx < display_width and 0 <= cy < display_height):
                self._pending_pixel_sample = None
                self._pixel_sample_timer.stop()
                self._last_pixel_cell = None
                self.clear_pixel()
                return
            row = min(
                lyr.source_height - 1,
                int(cy * lyr.source_height / display_height),
            )
            col = min(
                lyr.source_width - 1,
                int(cx * lyr.source_width / display_width),
            )
            key = (lyr.id, row, col)
            cached = self._pixel_cache.get(key)
            if cached is not None:
                self._pixel_sample_timer.stop()
                self._pending_pixel_sample = None
                self.update_backend_pixel(lyr.id, cached)
                return
            if key != self._last_pixel_cell:
                self._last_pixel_cell = key
                self._pending_pixel_sample = key
                self.surface.live_label.setText("LOADING")
                self._pixel_sample_timer.start()
            return
        if lyr.data is None:                        # vector / basemap -> show DEM values
            lyr = next((layer for layer in self.ws.layers if layer.id == "dem"), None)
            if lyr is None or lyr.data is None:
                self.clear_pixel()
                return
        self.update_pixel(self.ws.sample(lyr, cx, cy))

    def _request_pixel_sample(self) -> None:
        if self._pending_pixel_sample is not None:
            self.pixelSampleRequested.emit(*self._pending_pixel_sample)

    def is_pixel_sample_current(self, layer_id: str, row: int, col: int) -> bool:
        return self._last_pixel_cell == (layer_id, row, col)

    def cache_pixel_sample(
        self, layer_id: str, row: int, col: int, info: dict
    ) -> None:
        key = (layer_id, row, col)
        self._pixel_cache[key] = info
        self._pixel_cache.move_to_end(key)
        if len(self._pixel_cache) > 2048:
            self._pixel_cache.popitem(last=False)

    def refresh_pixel(self) -> None:
        hv = getattr(self.canvas, "hover", None)
        if hv:
            self._pixel_moved(*hv)
        else:
            self.clear_pixel()

    def clear_pixel(self) -> None:
        s = self.surface
        for label in (s.easting, s.northing, s.ptype, s.pvalue, s.punit, s.pcell, s.band):
            label.setText("—")
        s.live_label.setText("NO DATA")

    def update_pixel(self, info: dict) -> None:
        s = self.surface
        x = info.get("x", info.get("easting"))
        y = info.get("y", info.get("northing"))
        geographic = info.get("coordinate_unit") == "°" or (
            info.get("crs") and "4326" in info["crs"]
        )
        s.easting.setText(f"{x:,.6f}" if geographic
                          else f"{x:,.2f}")
        s.northing.setText(f"{y:,.6f}" if geographic
                           else f"{y:,.2f}")
        s.easting_unit.setText(info.get("coordinate_unit", "m"))
        s.northing_unit.setText(info.get("coordinate_unit", "m"))
        s.easting_name.setText(info.get("x_label", "Easting"))
        s.northing_name.setText(info.get("y_label", "Northing"))
        s.ptype.setText(info["type"])
        s.pvalue.setText("—" if info["value"] is None else fmt(info["value"]))
        s.punit.setText(info.get("unit", "m"))
        if info["value"] is None:
            s.pcell.setText(
                f"NoData · Column {info['col']} · Row {info['row']}"
                if info.get("row") is not None else "Outside raster"
            )
        else:
            s.pcell.setText(f"Column {info['col']} · Row {info['row']}")
        s.band.setText("Band 1")
        s.live_label.setText("LIVE")

    def update_backend_pixel(self, layer_id: str, info: dict) -> None:
        if layer_id != self.selected_layer_id:
            return
        info = {
            **info,
            "type": "Elevation",
            "unit": "m",
        }
        self.update_pixel(info)

    def show_pixel_error(self, layer_id: str, message: str) -> None:
        if layer_id == self.selected_layer_id:
            self.clear_pixel()
            self.surface.live_label.setText("ERROR")
            self.surface.live_label.setToolTip(message)

    def set_selected_layer(self, lid: str | None) -> None:
        self.selected_layer_id = lid
        self.canvas.selected_layer_id = lid
        self.canvas.update()
        self._pixel_sample_timer.stop()
        self._pending_pixel_sample = None
        self._last_pixel_cell = None
        if lid is None:
            self.surface.easting_name.setText("Easting")
            self.surface.northing_name.setText("Northing")
            self.surface.easting_unit.setText("m")
            self.surface.northing_unit.setText("m")
            self.surface.label.setText("No layer selected")
            self.clear_pixel()
            return
        lyr = self.ws.layer(lid)
        self.surface.label.setText(lyr.name)
        self.clear_pixel()

    def set_project_name(self, name: str) -> None:
        self.project_name = name
        self.tab_text.setText(name)

    def update_scale(self) -> None:
        mpp = self.canvas.meters_per_pixel()
        best = 1.0
        for m in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000):
            if m / mpp <= 140:
                best = float(m)
        bar = max(24, int(round(best / mpp)))
        text = f"{int(best):,} m" if best < 1000 else f"{best / 1000:g} km"
        self.surface.scale_bar.set_scale(bar, text)
        self.surface.reposition()
        self.scale_btn.setText(f"Scale   1 : {self.canvas.scale_denominator():,.0f}  ⌄")

    def update_annotation(self) -> None:
        n = len(self.ws.regions)
        self.surface.annotation.setText(f"{n} editing region{'s' if n != 1 else ''}")
        self.surface.reposition()

    def show_hint(self, text: str) -> None:
        self.surface.hint.setVisible(bool(text))
        if text:
            self.surface.hint.setText(text)
            self.surface.reposition()
            self.surface.hint.raise_()

    def show_preview(self, text: str | None) -> None:
        self.surface.banner.setVisible(bool(text))
        if text:
            self.surface.banner_text.setText(text)
            self.surface.reposition()
            self.surface.banner.raise_()

    def set_element_visible(self, name: str, on: bool) -> None:
        s = self.surface
        widget = {"north_arrow": s.north, "scale_bar": s.scale_bar,
              "pixel_inspector": s.inspector}.get(name)
        if widget is not None:
            widget.setVisible(on)

    def set_pane_buttons(self, contents_on: bool, stats_on: bool) -> None:
        self.btn_layers.setChecked(contents_on)
        self.btn_stats.setChecked(stats_on)