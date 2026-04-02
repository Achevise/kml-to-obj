from __future__ import annotations

from kml_to_fbx.mesh_builder import polygon_to_mesh


def _tri_area_xy(a, b, c):
    return abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) * 0.5


def test_polygon_with_hole_triangulates_non_empty():
    outer = [
        (0.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
        (10.0, 10.0, 0.0),
        (0.0, 10.0, 0.0),
        (0.0, 0.0, 0.0),
    ]
    hole = [
        (3.0, 3.0, 0.0),
        (3.0, 7.0, 0.0),
        (7.0, 7.0, 0.0),
        (7.0, 3.0, 0.0),
        (3.0, 3.0, 0.0),
    ]

    mesh = polygon_to_mesh([outer, hole])
    assert mesh.vertices
    assert mesh.triangles

    area = 0.0
    for i, j, k in mesh.triangles:
        area += _tri_area_xy(mesh.vertices[i], mesh.vertices[j], mesh.vertices[k])

    # Outer area 100 - hole area 16 = 84
    assert 83.9 <= area <= 84.1
