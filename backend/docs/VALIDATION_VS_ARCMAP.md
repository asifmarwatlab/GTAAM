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

## Not yet validated
Roughness, TPI, Ruggedness (no single ArcMap tool; Raster Calculator comparison planned), Layer Statistics and Histogram, Distance, Area, Elevation Profile, and the remaining tabs.
