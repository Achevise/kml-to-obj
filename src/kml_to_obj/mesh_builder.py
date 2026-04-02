from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence, Tuple


Vec3 = Tuple[float, float, float]
Tri = Tuple[int, int, int]


@dataclass
class MeshData:
    vertices: List[Vec3]
    triangles: List[Tri]


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _length(v: Vec3) -> float:
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _normalize(v: Vec3) -> Vec3:
    n = _length(v)
    if n == 0.0:
        return (0.0, 0.0, 0.0)
    return (v[0] / n, v[1] / n, v[2] / n)


def point_to_octahedron_mesh(center: Vec3, radius: float) -> MeshData:
    x, y, z = center
    v = [
        (x + radius, y, z),
        (x - radius, y, z),
        (x, y + radius, z),
        (x, y - radius, z),
        (x, y, z + radius),
        (x, y, z - radius),
    ]
    t: List[Tri] = [
        (0, 2, 4),
        (2, 1, 4),
        (1, 3, 4),
        (3, 0, 4),
        (2, 0, 5),
        (1, 2, 5),
        (3, 1, 5),
        (0, 3, 5),
    ]
    return MeshData(vertices=v, triangles=t)


def linestring_to_ribbon_mesh(coords: Sequence[Vec3], width: float) -> MeshData:
    return linestring_to_ribbon_mesh_axis(coords, width, up_axis="z")


def linestring_to_ribbon_mesh_axis(coords: Sequence[Vec3], width: float, up_axis: str) -> MeshData:
    if len(coords) < 2:
        return MeshData(vertices=[], triangles=[])

    axis = up_axis.lower()
    if axis == "x":
        h1, h2 = 1, 2
    elif axis == "y":
        h1, h2 = 0, 2
    elif axis == "z":
        h1, h2 = 0, 1
    else:
        raise ValueError(f"Unsupported up axis: {up_axis}")

    half = width * 0.5
    left_right: List[Tuple[Vec3, Vec3]] = []

    for i, p in enumerate(coords):
        if i == 0:
            tangent = _sub(coords[1], coords[0])
        elif i == len(coords) - 1:
            tangent = _sub(coords[-1], coords[-2])
        else:
            t1 = _normalize(_sub(coords[i], coords[i - 1]))
            t2 = _normalize(_sub(coords[i + 1], coords[i]))
            tangent = (t1[0] + t2[0], t1[1] + t2[1], t1[2] + t2[2])

        t2 = (tangent[h1], tangent[h2])
        tlen = math.hypot(t2[0], t2[1])
        if tlen <= 1e-15:
            t2 = (1.0, 0.0)
            tlen = 1.0
        tx, ty = (t2[0] / tlen, t2[1] / tlen)
        nx, ny = (-ty, tx)

        l = [p[0], p[1], p[2]]
        r = [p[0], p[1], p[2]]
        l[h1] += nx * half
        l[h2] += ny * half
        r[h1] -= nx * half
        r[h2] -= ny * half
        l = (l[0], l[1], l[2])
        r = (r[0], r[1], r[2])
        left_right.append((l, r))

    verts: List[Vec3] = []
    tris: List[Tri] = []

    for i, (l, r) in enumerate(left_right):
        verts.extend([l, r])
        if i > 0:
            a = (i - 1) * 2
            b = a + 1
            c = i * 2
            d = c + 1
            tris.append((a, c, b))
            tris.append((b, c, d))

    return MeshData(vertices=verts, triangles=tris)


def merge_meshes(meshes: Sequence[MeshData]) -> MeshData:
    verts: List[Vec3] = []
    tris: List[Tri] = []
    offset = 0
    for m in meshes:
        if not m.vertices or not m.triangles:
            continue
        verts.extend(m.vertices)
        tris.extend((i + offset, j + offset, k + offset) for (i, j, k) in m.triangles)
        offset += len(m.vertices)
    return MeshData(vertices=verts, triangles=tris)


def polygon_outline_mesh(rings: Sequence[Sequence[Vec3]], width: float) -> MeshData:
    return polygon_outline_mesh_axis(rings, width, up_axis="z")


def polygon_outline_mesh_axis(rings: Sequence[Sequence[Vec3]], width: float, up_axis: str) -> MeshData:
    if width <= 0.0:
        return MeshData(vertices=[], triangles=[])
    parts: List[MeshData] = []
    for ring in rings:
        r = list(ring)
        if len(r) < 3:
            continue
        if r[0] == r[-1]:
            r = r[:-1]
        if len(r) < 3:
            continue
        closed = r + [r[0]]
        parts.append(linestring_to_ribbon_mesh_axis(closed, width, up_axis=up_axis))
    return merge_meshes(parts)


def _signed_area_2d(poly: Sequence[Tuple[float, float]]) -> float:
    area = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return 0.5 * area


def _is_convex(a, b, c, ccw: bool) -> bool:
    cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return cross > 0 if ccw else cross < 0


def _point_in_tri_strict(p, a, b, c, eps: float = 1e-9) -> bool:
    def s(p1, p2, p3):
        return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])

    d1 = s(p, a, b)
    d2 = s(p, b, c)
    d3 = s(p, c, a)
    has_neg = d1 < -eps or d2 < -eps or d3 < -eps
    has_pos = d1 > eps or d2 > eps or d3 > eps
    if has_neg and has_pos:
        return False
    return abs(d1) > eps and abs(d2) > eps and abs(d3) > eps


def _ear_clip_indices(poly: Sequence[Tuple[float, float]]) -> List[Tri]:
    n = len(poly)
    if n < 3:
        return []

    ccw = _signed_area_2d(poly) > 0
    idx = list(range(n))
    out: List[Tri] = []

    guard = 0
    while len(idx) > 3 and guard < 50000:
        guard += 1
        ear_found = False

        for i in range(len(idx)):
            i0 = idx[(i - 1) % len(idx)]
            i1 = idx[i]
            i2 = idx[(i + 1) % len(idx)]

            a, b, c = poly[i0], poly[i1], poly[i2]
            if not _is_convex(a, b, c, ccw):
                continue

            contains = False
            for j in idx:
                if j in (i0, i1, i2):
                    continue
                if _point_in_tri_strict(poly[j], a, b, c):
                    contains = True
                    break
            if contains:
                continue

            out.append((i0, i1, i2) if ccw else (i2, i1, i0))
            del idx[i]
            ear_found = True
            break

        if not ear_found:
            return []

    if len(idx) == 3:
        if ccw:
            out.append((idx[0], idx[1], idx[2]))
        else:
            out.append((idx[2], idx[1], idx[0]))

    return out


def _tri_area2_2d(a: Tuple[float, float], b: Tuple[float, float], c: Tuple[float, float]) -> float:
    return abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1]))


def _rotate_to_start(indices: Sequence[int], start_idx: int) -> List[int]:
    p = list(indices)
    at = p.index(start_idx)
    return p[at:] + p[:at]


def _orient(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a, b, p, eps: float = 1e-9) -> bool:
    return (
        min(a[0], b[0]) - eps <= p[0] <= max(a[0], b[0]) + eps
        and min(a[1], b[1]) - eps <= p[1] <= max(a[1], b[1]) + eps
    )


def _segments_intersect(a, b, c, d, eps: float = 1e-9) -> bool:
    o1 = _orient(a, b, c)
    o2 = _orient(a, b, d)
    o3 = _orient(c, d, a)
    o4 = _orient(c, d, b)

    if (o1 > eps and o2 < -eps or o1 < -eps and o2 > eps) and (o3 > eps and o4 < -eps or o3 < -eps and o4 > eps):
        return True

    if abs(o1) <= eps and _on_segment(a, b, c, eps):
        return True
    if abs(o2) <= eps and _on_segment(a, b, d, eps):
        return True
    if abs(o3) <= eps and _on_segment(c, d, a, eps):
        return True
    if abs(o4) <= eps and _on_segment(c, d, b, eps):
        return True
    return False


def _loop_edges(loop: Sequence[int]) -> List[Tuple[int, int]]:
    return [(loop[i], loop[(i + 1) % len(loop)]) for i in range(len(loop))]


def _shares_endpoint(e0: Tuple[int, int], e1: Tuple[int, int]) -> bool:
    return e0[0] in e1 or e0[1] in e1


def _bridge_hole(
    contour: List[int],
    hole: List[int],
    points2d: List[Tuple[float, float]],
    points3d: List[Vec3],
) -> List[int]:
    h_right = max(hole, key=lambda i: (points2d[i][0], -points2d[i][1]))
    hp = points2d[h_right]

    candidates = sorted(contour, key=lambda i: (points2d[i][0] - hp[0]) ** 2 + (points2d[i][1] - hp[1]) ** 2)
    contour_edges = _loop_edges(contour)
    hole_edges = _loop_edges(hole)

    chosen = None
    for c in candidates:
        cp = points2d[c]
        bridge = (h_right, c)
        ok = True

        for e in contour_edges:
            if _shares_endpoint(bridge, e):
                continue
            if _segments_intersect(hp, cp, points2d[e[0]], points2d[e[1]]):
                ok = False
                break
        if not ok:
            continue

        for e in hole_edges:
            if _shares_endpoint(bridge, e):
                continue
            if _segments_intersect(hp, cp, points2d[e[0]], points2d[e[1]]):
                ok = False
                break
        if ok:
            chosen = c
            break

    if chosen is None:
        # Fallback: nearest contour vertex even if visibility test fails.
        chosen = candidates[0]

    outer_pos = contour.index(chosen)
    hole_cycle = _rotate_to_start(hole, h_right)
    hole_tail = hole_cycle[1:]

    # Create cloned bridge vertices so the merged contour has unique indices.
    h_clone = len(points2d)
    points2d.append(points2d[h_right])
    points3d.append(points3d[h_right])

    c_clone = len(points2d)
    points2d.append(points2d[chosen])
    points3d.append(points3d[chosen])

    # contour[:outer+1] + in-bridge + hole walk + out-bridge + contour rest
    merged = contour[: outer_pos + 1] + [h_right] + hole_tail + [h_clone, c_clone] + contour[outer_pos + 1 :]
    return merged


def polygon_to_mesh(rings: Sequence[Sequence[Vec3]]) -> MeshData:
    if not rings:
        return MeshData(vertices=[], triangles=[])

    clean_rings: List[List[Vec3]] = []
    for ring in rings:
        r = list(ring)
        if len(r) > 2 and r[0] == r[-1]:
            r = r[:-1]
        if len(r) >= 3:
            clean_rings.append(r)
    if not clean_rings:
        return MeshData(vertices=[], triangles=[])

    outer = clean_rings[0]

    # Build a local 2D plane for triangulation from outer-ring normal.
    p0 = outer[0]
    normal = (0.0, 0.0, 1.0)
    for i in range(1, len(outer) - 1):
        v1 = _sub(outer[i], p0)
        v2 = _sub(outer[i + 1], p0)
        n = _cross(v1, v2)
        if _length(n) > 1e-9:
            normal = _normalize(n)
            break

    ref = (1.0, 0.0, 0.0) if abs(normal[0]) < 0.9 else (0.0, 1.0, 0.0)
    u = _normalize(_cross(ref, normal))
    v = _cross(normal, u)

    points3d: List[Vec3] = []
    points2d: List[Tuple[float, float]] = []
    ring_indices: List[List[int]] = []

    for ring in clean_rings:
        idxs: List[int] = []
        for p in ring:
            d = _sub(p, p0)
            points3d.append(p)
            points2d.append((d[0] * u[0] + d[1] * u[1] + d[2] * u[2], d[0] * v[0] + d[1] * v[1] + d[2] * v[2]))
            idxs.append(len(points3d) - 1)
        ring_indices.append(idxs)

    contour = ring_indices[0]
    # Outer should be CCW for ear clipping.
    if _signed_area_2d([points2d[i] for i in contour]) < 0:
        contour = list(reversed(contour))

    holes: List[List[int]] = []
    for h in ring_indices[1:]:
        # Holes should be CW.
        if _signed_area_2d([points2d[i] for i in h]) > 0:
            h = list(reversed(h))
        holes.append(h)

    for hole in holes:
        contour = _bridge_hole(contour, hole, points2d, points3d)

    contour2d = [points2d[i] for i in contour]
    tri_local = _ear_clip_indices(contour2d)
    tri: List[Tri] = []
    for a, b, c in tri_local:
        if _tri_area2_2d(contour2d[a], contour2d[b], contour2d[c]) <= 1e-12:
            continue
        tri.append((contour[a], contour[b], contour[c]))

    if not tri:
        return MeshData(vertices=[], triangles=[])

    return MeshData(vertices=points3d, triangles=tri)


def extrude_mesh_y(mesh: MeshData, height: float) -> MeshData:
    return extrude_mesh_axis(mesh, height, up_axis="y")


def extrude_mesh_axis(mesh: MeshData, height: float, up_axis: str) -> MeshData:
    if height <= 0.0 or not mesh.vertices or not mesh.triangles:
        return mesh

    axis = up_axis.lower()
    if axis == "x":
        up_idx = 0
    elif axis == "y":
        up_idx = 1
    elif axis == "z":
        up_idx = 2
    else:
        raise ValueError(f"Unsupported up axis: {up_axis}")

    bottom = list(mesh.vertices)
    offset = len(bottom)
    top = []
    for v in bottom:
        vv = [v[0], v[1], v[2]]
        vv[up_idx] += height
        top.append((vv[0], vv[1], vv[2]))

    tris: List[Tri] = []
    # Bottom cap (original orientation).
    tris.extend(mesh.triangles)
    # Top cap with reversed winding.
    tris.extend((k + offset, j + offset, i + offset) for (i, j, k) in mesh.triangles)

    # Detect boundary edges (edges used by exactly one triangle).
    undirected_count: dict[Tuple[int, int], int] = {}
    oriented_edges: List[Tuple[int, int]] = []
    for i, j, k in mesh.triangles:
        for a, b in ((i, j), (j, k), (k, i)):
            key = (a, b) if a < b else (b, a)
            undirected_count[key] = undirected_count.get(key, 0) + 1
            oriented_edges.append((a, b))

    for a, b in oriented_edges:
        key = (a, b) if a < b else (b, a)
        if undirected_count.get(key, 0) != 1:
            continue
        a2 = a + offset
        b2 = b + offset
        # Side quad split into 2 triangles.
        tris.append((a, b, b2))
        tris.append((a, b2, a2))

    return MeshData(vertices=bottom + top, triangles=tris)


def _mesh_signed_volume(mesh: MeshData) -> float:
    vol6 = 0.0
    for i, j, k in mesh.triangles:
        ax, ay, az = mesh.vertices[i]
        bx, by, bz = mesh.vertices[j]
        cx, cy, cz = mesh.vertices[k]
        vol6 += (
            ax * (by * cz - bz * cy)
            - ay * (bx * cz - bz * cx)
            + az * (bx * cy - by * cx)
        )
    return vol6 / 6.0


def orient_closed_mesh_outward(mesh: MeshData) -> MeshData:
    if not mesh.vertices or not mesh.triangles:
        return mesh

    vol = _mesh_signed_volume(mesh)
    if abs(vol) < 1e-12:
        return mesh
    if vol > 0.0:
        return mesh

    flipped = [(k, j, i) for (i, j, k) in mesh.triangles]
    return MeshData(vertices=list(mesh.vertices), triangles=flipped)


def flip_mesh_winding(mesh: MeshData) -> MeshData:
    if not mesh.vertices or not mesh.triangles:
        return mesh
    return MeshData(vertices=list(mesh.vertices), triangles=[(k, j, i) for (i, j, k) in mesh.triangles])
