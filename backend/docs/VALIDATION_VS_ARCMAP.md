# Validation against ArcMap 10.8

Terrain functions checked against ArcMap 10.8 (Spatial Analyst) on 29 Oct 2026.

**Test data**
- `ALPSMLC30_N033E073_DSM.tif`: ALOS AW3D30 tile, EPSG:4326, 3600 x 3600, 0.000278 deg cells (geographic)
- `dem_utm43.tif`: the same tile reprojected in ArcMap (Project Raster, bilinear) to WGS 1984 UTM 43N, 3304 x 3924, 28.6 m cells (projected)

Projected data is the clean test: no degree-to-metre conversion, so only the formula is compared.

## Results (projected DEM, `dem_utm43.tif`)

| Function | ArcMap settings | Result |
|---|---|---|
| Slope | DEGREE, PLANAR, Z 1 | Max 67.7533 / Mean 12.7332 / Std 11.2211 in ArcMap; 67.8 / 12.7 / 11.2 in the app. Within 0.4%. |
| Hillshade | Az 315, Alt 45, no shadows, Z 1 | ArcMap Mean 171.51 / Std 37.79; app 172.0 / 37.8. After rounding down to whole numbers (ArcMap stores 8-bit), 100% of pixels identical. |
| Curvature | Z 1 | Min -10.3873 / Max 11.4871 / Std 0.836 in both. 100% pixel match (max difference ~1e-15). |
| Contours | interval 200, base 0, Z 1 | Same 15 levels (400-3200 m). Total length 12,389 km vs 12,432 km (-0.35%). App keeps ~410 tiny rings (<60 m) that ArcMap drops. |

## Results (geographic DEM, `ALPSMLC30_N033E073_DSM.tif`)

| Function | Result |
|---|---|
| Aspect | ArcMap (flat cells excluded) Mean 181.49 / Std 100.98; app 181.4 / 99.8. With ArcMap's square-cell assumption the app matches on 100% of pixels. ArcMap writes -1 for flat cells; the app leaves them blank. |
| Hillshade | ArcMap at Z 1 treats degrees as metres (dark, misleading output: Mean 55.8). The app's formula matches it on 100% of pixels when given the same cell size. With ArcMap Z 0.0000108 the difference from the app is about 1% in mean, because ArcMap assumes square cells. |
| Slope | ArcMap geographic Mean 12.12 vs app 13.1. Differences come from the degree-to-metre handling, not the formula (the formula matches on the projected DEM). |

## Degree-to-metre handling

For geographic DEMs the app converts degrees to metres using the WGS84 series at the raster's mid-latitude (`core/raster/crs.py`, `metres_per_degree`). ArcMap uses a fixed value and treats cells as square. The app's cell shape (about 25.8 m x 30.8 m at 33.5 N) is the more accurate one. For comparisons with ArcMap, use a projected DEM.

## Distance (geographic DEM, geodesic lengths)

Checked on 10 Nov 2026. Three lines drawn in ArcMap 10.8 on `test_lines.shp` (WGS 84). ArcMap length from the Python window: `Polyline.getLength("GEODESIC", "METERS")`. The app: `POST /analysis/measure/distance` with the same vertices as `points` (longitude, latitude), units metres, on the geographic DEM.

| Line | Vertices (lon, lat) | ArcMap geodesic | App | Difference |
|---|---|---|---|---|
| Short | (73.2, 33.3) to (73.25, 33.33) | 5,722.69 m | 5,722.6868 m | under 1 cm |
| Long | (73.1, 33.1) to (73.9, 33.9) | 115,754.26 m | 115,754.2576 m | under 1 cm |
| Bends | (73.1, 33.2), (73.3, 33.5), (73.5, 33.3), (73.8, 33.6) | 110,497.63 m | 110,497.6280 m | under 1 cm |

The app uses Vincenty's method on the WGS84 ellipsoid for degree-based layers (`core/measure/distance.py`, `geodesic_distance`). An earlier version used a sphere (haversine) and was off by 3 m, 71 m and 100 m on these lines. The three ArcMap values are also automated tests (`test_geodesic_matches_arcmap`).

### Distance: elevation difference

ArcMap `GetCellValue_management` returns the value of the cell a point falls in. The app normally blends the four nearest cells (bilinear), so this check used `"snap": true`, which moves each point to its cell centre. The points were chosen away from cell edges.

| Point (lon, lat) | ArcMap `GetCellValue` | App (`snap` on) |
|---|---|---|
| Start (73.1234, 33.1234) | 531 m | 531.0000 m |
| End (73.8765, 33.8765) | 1850 m | 1850.0000 m |
| Difference (end minus start) | 1319 m | 1319.0000 m |

Exact match (differences of 1e-10 m are float rounding). Without snap the app gives a bilinear value, which can differ slightly from the cell value by design; that was not compared with ArcMap.

### Distance: projected DEM (`dem_utm43.tif`, WGS 84 / UTM 43N)

Three lines in UTM metres. ArcMap: `Polyline.getLength("PLANAR", "METERS")` on a polyline in the raster's spatial reference. App: the same vertices through `POST /analysis/measure/distance`, which measures flat lengths on the grid for a projected layer.

| Line | Vertices (x, y) | ArcMap PLANAR | App | Difference |
|---|---|---|---|---|
| A | (350000, 3700000), (352000, 3701500) | 2,500.0000 m | 2,500.0000 m | 0 |
| B | (330000, 3680000), (390000, 3740000) | 84,852.8137 m | 84,852.8137 m | 0 |
| C | (335000, 3690000), (350000, 3720000), (365000, 3700000), (385000, 3730000) | 94,596.5324 m | 94,596.5324 m | 0 |

ArcMap GEODESIC on the same lines is longer (2,500.32 / 84,865.94 / 94,610.88 m, about 0.015%) because UTM shrinks distances slightly. A projected layer is measured on the grid, so the planar value is the one to compare.

Not yet compared with ArcMap: measuring a loaded line layer.

## Not yet validated
Layer Statistics and Histogram, Area, Elevation Profile, and the remaining tabs. Roughness, TPI and Ruggedness have no single ArcMap tool and were compared with Raster Calculator; their numbers still need to be added to this file.
