#!/usr/bin/env python3
"""
build_catchments.py — Crosssight (resolves finding C1).

Generates REAL Voronoi/Thiessen catchment polygons for the London Type-1 A&E
hospitals in data/catchments.json, clips each cell to a Greater London boundary,
computes the polygon centroid, and writes:
  - catchmentPolygon : GeoJSON-style array of [lon, lat] rings (outer ring only)
  - catchmentCentroid: [lon, lat]
into every hospital entry.

NOTE ON THE BOUNDARY (honest approximation): we do not ship the official GLA
Greater-London outline offline, so we clip to a bounding box
  lon in [-0.55, 0.30], lat in [51.28, 51.70].
This is an APPROXIMATION to be replaced by the GLA boundary in data-prep.
The Voronoi tessellation itself is real (computed from the hospital coordinates);
only the outer clip boundary is approximate.

Deterministic: no randomness. Re-running produces identical output.

Deps: scipy, shapely, numpy. If missing: pip install scipy shapely numpy
"""

import json
import os
import sys

# --- dependency check (fail loud, per C1) ---------------------------------
try:
    import numpy as np
    from scipy.spatial import Voronoi
    from shapely.geometry import Polygon, MultiPolygon, box
    from shapely.ops import polygonize, unary_union
except ImportError as exc:  # pragma: no cover
    sys.stderr.write(
        "Missing dependency: %s\n"
        "Install with: pip install scipy shapely numpy\n" % exc
    )
    sys.exit(1)

HERE = os.path.dirname(os.path.abspath(__file__))
CATCHMENTS_PATH = os.path.normpath(os.path.join(HERE, "..", "catchments.json"))

# Greater London clip boundary (bbox approximation — see module docstring).
LON_MIN, LON_MAX = -0.55, 0.30
LAT_MIN, LAT_MAX = 51.28, 51.70
BBOX_NOTE = (
    "Voronoi/Thiessen tessellation of hospital coordinates, clipped to a "
    "Greater-London BOUNDING BOX lon[-0.55,0.30] lat[51.28,51.70]. "
    "Approximation to be replaced by the GLA Greater-London outline. "
    "The tessellation is real; only the outer clip boundary is approximate."
)


def finite_voronoi_polygons(points, clip_polygon):
    """Return one clipped shapely polygon per input point.

    scipy's Voronoi leaves boundary cells open (regions referencing the
    point at infinity). We reconstruct closed cells by intersecting the
    Voronoi ridges with a generously padded boundary, then assign each
    resulting cell back to its nearest input point.
    """
    vor = Voronoi(points)

    # Build a large padding box so every (even unbounded) cell is closed
    # before we clip to the real Greater-London boundary.
    minx, miny, maxx, maxy = clip_polygon.bounds
    pad = max(maxx - minx, maxy - miny) * 5.0
    big = box(minx - pad, miny - pad, maxx + pad, maxy + pad)

    # Collect every finite Voronoi ridge as a line segment; add the big box
    # edges so polygonize can close the unbounded cells.
    from shapely.geometry import LineString

    segments = []
    center = vor.points.mean(axis=0)
    radius = pad * 2.0
    for (p1, p2), (v1, v2) in zip(vor.ridge_points, vor.ridge_vertices):
        if v1 >= 0 and v2 >= 0:
            segments.append(LineString([vor.vertices[v1], vor.vertices[v2]]))
        else:
            # One end at infinity: build the ray direction.
            finite_v = v1 if v1 >= 0 else v2
            tangent = vor.points[p2] - vor.points[p1]
            tangent = tangent / np.linalg.norm(tangent)
            normal = np.array([-tangent[1], tangent[0]])
            midpoint = vor.points[[p1, p2]].mean(axis=0)
            direction = np.sign(np.dot(midpoint - center, normal)) * normal
            far_point = vor.vertices[finite_v] + direction * radius
            segments.append(LineString([vor.vertices[finite_v], far_point]))

    segments.append(big.exterior)
    merged = unary_union(segments)
    cells = list(polygonize(merged))

    # Assign each cell to the nearest input point (Voronoi defining property).
    pts = [Polygon() for _ in range(len(points))]
    cell_centroids = [c.representative_point() for c in cells]
    for cell, rep in zip(cells, cell_centroids):
        d = np.hypot(points[:, 0] - rep.x, points[:, 1] - rep.y)
        idx = int(np.argmin(d))
        # Clip to the real Greater-London boundary.
        clipped = cell.intersection(clip_polygon)
        if not clipped.is_empty:
            pts[idx] = unary_union([pts[idx], clipped])
    return pts


def to_ring(geom):
    """Return outer ring [[lon,lat],...] for a (Multi)Polygon, closed."""
    if isinstance(geom, MultiPolygon):
        # Use the largest sub-polygon's exterior.
        geom = max(geom.geoms, key=lambda g: g.area)
    coords = [[round(x, 6), round(y, 6)] for x, y in geom.exterior.coords]
    if coords[0] != coords[-1]:
        coords.append(coords[0])
    return coords


def main():
    with open(CATCHMENTS_PATH, "r") as fh:
        data = json.load(fh)

    hospitals = data["hospitals"]
    points = np.array([[h["lon"], h["lat"]] for h in hospitals], dtype=float)

    clip_polygon = box(LON_MIN, LAT_MIN, LON_MAX, LAT_MAX)

    cells = finite_voronoi_polygons(points, clip_polygon)

    missing = 0
    for h, cell in zip(hospitals, cells):
        if cell.is_empty:
            missing += 1
            sys.stderr.write("WARNING: empty cell for %s\n" % h["id"])
            continue
        h["catchmentPolygon"] = to_ring(cell)
        c = cell.centroid
        h["catchmentCentroid"] = [round(c.x, 6), round(c.y, 6)]

    # Keep _meta honest about the bbox approximation.
    data["_meta"]["catchmentPolygonMethod"] = BBOX_NOTE
    if "fieldsToRegenerate" in data["_meta"]:
        data["_meta"]["fieldsToRegenerate"] = [
            (
                "catchmentPolygon — NOW POPULATED with real Voronoi cells clipped "
                "to a Greater-London BBOX; replace the bbox clip with the GLA "
                "Greater-London outline (ARCHITECTURE.md §3.3)"
            )
            if f.startswith("catchmentPolygon")
            else f
            for f in data["_meta"]["fieldsToRegenerate"]
        ]

    with open(CATCHMENTS_PATH, "w") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")

    print("Wrote %d hospitals (%d missing cells)." % (len(hospitals), missing))


if __name__ == "__main__":
    main()
