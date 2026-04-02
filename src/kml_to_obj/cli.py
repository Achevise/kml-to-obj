from __future__ import annotations

import argparse
import math
import os
from collections import defaultdict
from types import SimpleNamespace
from typing import Dict, List, Sequence, Tuple
import xml.etree.ElementTree as ET

from .geo import lonlatalt_to_local_meters
from .kml_parser import parse_kml
from .mesh_builder import (
    extrude_mesh_axis,
    flip_mesh_winding,
    linestring_to_ribbon_mesh_axis,
    orient_closed_mesh_outward,
    polygon_outline_mesh_axis,
    point_to_octahedron_mesh,
    polygon_to_mesh,
)
from .obj_writer import ObjMeshObject, write_obj_with_mtl


def _sub3(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross3(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _axis_index(up_axis: str) -> int:
    axis = up_axis.lower()
    if axis == "x":
        return 0
    if axis == "y":
        return 1
    if axis == "z":
        return 2
    raise ValueError(f"Unsupported up axis: {up_axis}")


def _horizontal_axes(up_axis: str) -> Tuple[int, int]:
    idx = _axis_index(up_axis)
    axes = [0, 1, 2]
    axes.remove(idx)
    return axes[0], axes[1]


def _orient_polygon_front(mesh, up: bool, up_axis: str):
    if not mesh.vertices or not mesh.triangles:
        return mesh
    up_idx = _axis_index(up_axis)
    y_sum = 0.0
    for i, j, k in mesh.triangles:
        a = mesh.vertices[i]
        b = mesh.vertices[j]
        c = mesh.vertices[k]
        n = _cross3(_sub3(b, a), _sub3(c, a))
        y_sum += n[up_idx]
    if abs(y_sum) <= 1e-12:
        return mesh
    if (up and y_sum < 0.0) or ((not up) and y_sum > 0.0):
        return flip_mesh_winding(mesh)
    return mesh


def _point_segment_distance_h(p, a, b, h1: int, h2: int) -> float:
    px, pz = p[h1], p[h2]
    ax, az = a[h1], a[h2]
    bx, bz = b[h1], b[h2]
    abx = bx - ax
    abz = bz - az
    ab2 = abx * abx + abz * abz
    if ab2 <= 1e-15:
        dx = px - ax
        dz = pz - az
        return math.sqrt(dx * dx + dz * dz)
    t = ((px - ax) * abx + (pz - az) * abz) / ab2
    t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
    qx = ax + t * abx
    qz = az + t * abz
    dx = px - qx
    dz = pz - qz
    return math.sqrt(dx * dx + dz * dz)


def _rdp_simplify_linestring(coords, tolerance: float, up_axis: str):
    if tolerance <= 0.0 or len(coords) <= 2:
        return list(coords)
    h1, h2 = _horizontal_axes(up_axis)

    keep = [False] * len(coords)
    keep[0] = True
    keep[-1] = True
    stack = [(0, len(coords) - 1)]

    while stack:
        i0, i1 = stack.pop()
        a = coords[i0]
        b = coords[i1]
        max_dist = -1.0
        max_idx = -1
        for i in range(i0 + 1, i1):
            d = _point_segment_distance_h(coords[i], a, b, h1, h2)
            if d > max_dist:
                max_dist = d
                max_idx = i
        if max_idx != -1 and max_dist > tolerance:
            keep[max_idx] = True
            stack.append((i0, max_idx))
            stack.append((max_idx, i1))

    out = [p for i, p in enumerate(coords) if keep[i]]
    if len(out) < 2:
        return [coords[0], coords[-1]]
    return out


def _simplify_ring(coords, tolerance: float, up_axis: str):
    if tolerance <= 0.0 or len(coords) < 4:
        return list(coords)
    h1, h2 = _horizontal_axes(up_axis)

    closed = coords[0] == coords[-1]
    ring = list(coords[:-1] if closed else coords)
    if len(ring) < 3:
        return list(coords)

    # Iteratively remove near-collinear points in XZ plane.
    while len(ring) > 3:
        best_idx = -1
        best_dist = float("inf")
        n = len(ring)
        for i in range(n):
            a = ring[(i - 1) % n]
            b = ring[i]
            c = ring[(i + 1) % n]
            d = _point_segment_distance_h(b, a, c, h1, h2)
            if d < best_dist:
                best_dist = d
                best_idx = i
        if best_idx == -1 or best_dist > tolerance:
            break
        del ring[best_idx]

    if closed:
        ring.append(ring[0])
    return ring


def _decimate_shape_coords(geometry_type: str, coordinates, tolerance: float, up_axis: str):
    if tolerance <= 0.0:
        return coordinates
    if geometry_type == "Point":
        return coordinates
    if geometry_type == "LineString":
        return _rdp_simplify_linestring(coordinates, tolerance, up_axis)
    if geometry_type == "Polygon":
        out = []
        for ring in coordinates:
            s = _simplify_ring(ring, tolerance, up_axis)
            if len(s) >= 4 and s[0] == s[-1]:
                out.append(s)
            elif len(s) >= 3:
                out.append(s)
        return out
    return coordinates


def _scale_point(v, sx: float, sy: float, sz: float):
    return (v[0] * sx, v[1] * sy, v[2] * sz)


def _scale_shape_coords(geometry_type: str, coordinates, sx: float, sy: float, sz: float):
    if geometry_type == "Point":
        return [_scale_point(p, sx, sy, sz) for p in coordinates]
    if geometry_type == "LineString":
        return [_scale_point(p, sx, sy, sz) for p in coordinates]
    if geometry_type == "Polygon":
        return [[_scale_point(p, sx, sy, sz) for p in ring] for ring in coordinates]
    return coordinates


def _project_shape(shape, origin_lon: float, origin_lat: float, up_axis: str):
    if shape.geometry_type == "Point":
        return [
            lonlatalt_to_local_meters(lon, lat, alt, origin_lon, origin_lat, up_axis=up_axis)
            for lon, lat, alt in shape.coordinates
        ]

    if shape.geometry_type == "LineString":
        return [
            lonlatalt_to_local_meters(lon, lat, alt, origin_lon, origin_lat, up_axis=up_axis)
            for lon, lat, alt in shape.coordinates
        ]

    if shape.geometry_type == "Polygon":
        rings = []
        for ring in shape.coordinates:
            rings.append(
                [
                    lonlatalt_to_local_meters(lon, lat, alt, origin_lon, origin_lat, up_axis=up_axis)
                    for lon, lat, alt in ring
                ]
            )
        return rings

    raise ValueError(f"Unsupported geometry type: {shape.geometry_type}")


def _shape_to_mesh(shape, point_radius: float, line_width: float, polygon_height: float, up_axis: str):
    if shape.geometry_type == "Point":
        mesh = point_to_octahedron_mesh(shape.coordinates[0], point_radius)
        return orient_closed_mesh_outward(mesh)

    if shape.geometry_type == "LineString":
        return linestring_to_ribbon_mesh_axis(shape.coordinates, line_width, up_axis=up_axis)

    if shape.geometry_type == "Polygon":
        mesh = polygon_to_mesh(shape.coordinates)
        if polygon_height > 0.0:
            mesh = extrude_mesh_axis(mesh, polygon_height, up_axis=up_axis)
            mesh = orient_closed_mesh_outward(mesh)
        return mesh

    raise ValueError(f"Unsupported geometry type: {shape.geometry_type}")


def _safe_token(value: str) -> str:
    out = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value.strip())
    return out.strip("._") or "unnamed"


def _parse_partition_level(value: str) -> int | None:
    if value == "all":
        return None
    n = int(value)
    if n < 1:
        raise ValueError("partition level must be >= 1 or 'all'")
    return n


def _partition_key(hierarchy: Sequence[str], level: int | None) -> Tuple[str, ...]:
    if level is None:
        return ("all",)
    if not hierarchy:
        return ("root",)
    return tuple(hierarchy[:level]) if len(hierarchy) >= level else tuple(hierarchy)


def _inspect_kml(path: str) -> str:
    scene = parse_kml(path)
    object_shapes: Dict[Tuple[str, ...], int] = defaultdict(int)
    shape_types: Dict[str, int] = defaultdict(int)
    hierarchy_depths: Dict[int, int] = defaultdict(int)
    color_counts: Dict[Tuple[float, float, float, float], int] = defaultdict(int)
    material_source_counts: Dict[str, int] = defaultdict(int)
    object_colors: Dict[Tuple[str, ...], set] = defaultdict(set)
    for s in scene.shapes:
        key = tuple(s.hierarchy)
        object_shapes[key] += 1
        shape_types[s.geometry_type] += 1
        hierarchy_depths[len(s.hierarchy)] += 1
        color_counts[s.rgba] += 1
        material_source_counts[s.material_source or ""] += 1
        object_colors[key].add(s.rgba)

    tree = ET.parse(path)
    root = tree.getroot()
    ns = {"kml": "http://www.opengis.net/kml/2.2"}
    styles = len(root.findall(".//kml:Style", ns))
    stylemaps = len(root.findall(".//kml:StyleMap", ns))
    placemarks = len(root.findall(".//kml:Placemark", ns))
    folders = len(root.findall(".//kml:Folder", ns))
    documents = len(root.findall(".//kml:Document", ns))

    per_object = sorted(object_shapes.values())
    min_shapes = per_object[0] if per_object else 0
    max_shapes = per_object[-1] if per_object else 0
    multiple_material_objects = sum(1 for cols in object_colors.values() if len(cols) > 1)
    sample_hier = sorted(["_".join(k) for k in object_shapes.keys()])[:10]

    lines: List[str] = []
    lines.append(f"KML file: {path}")
    lines.append("Structure:")
    lines.append(f"- Documents: {documents}")
    lines.append(f"- Folders: {folders}")
    lines.append(f"- Objects (Placemark): {placemarks}")
    lines.append(f"- Parsed objects (unique hierarchy paths): {len(object_shapes)}")
    lines.append(f"- Total shapes: {len(scene.shapes)}")
    lines.append(f"- Shapes per object (min/max): {min_shapes}/{max_shapes}")
    dist = defaultdict(int)
    for n in per_object:
        dist[n] += 1
    lines.append("- Shapes per object distribution:")
    for n in sorted(dist):
        lines.append(f"  {n}: {dist[n]}")
    lines.append("Shape types:")
    for t in sorted(shape_types):
        lines.append(f"- {t}: {shape_types[t]}")
    lines.append("Hierarchy:")
    for d in sorted(hierarchy_depths):
        lines.append(f"- Depth {d}: {hierarchy_depths[d]} shape(s)")
    lines.append("- Sample hierarchy names (up to 10):")
    for h in sample_hier:
        lines.append(f"  {h}")
    lines.append("Materials / styles:")
    lines.append(f"- Styles declared: {styles}")
    lines.append(f"- StyleMaps declared: {stylemaps}")
    lines.append(f"- Unique RGBA in parsed shapes: {len(color_counts)}")
    for rgba, count in sorted(color_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]:
        lines.append(f"  {rgba}: {count} shape(s)")
    lines.append(f"- Unique material sources: {len(material_source_counts)}")
    for ms, count in sorted(material_source_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]:
        lines.append(f"  {ms}: {count} shape(s)")
    lines.append(f"- Objects with multiple materials: {multiple_material_objects}")
    return "\n".join(lines)


def _write_geoid_map_py(scene, output_path: str) -> str:
    out_base, _ = os.path.splitext(output_path)
    map_path = f"{out_base}.py"
    geoid_to_obj: Dict[str, str] = {}
    for s in scene.shapes:
        geoid = (s.geoid or "").strip()
        if not geoid:
            continue
        obj_name = "_".join(s.hierarchy)
        if geoid not in geoid_to_obj:
            geoid_to_obj[geoid] = obj_name

    with open(map_path, "w", encoding="utf-8") as f:
        f.write("# Auto-generated by kml2obj\n")
        f.write("GEOID_TO_OBJECT = {\n")
        for geoid in sorted(geoid_to_obj):
            f.write(f'    "{geoid}": "{geoid_to_obj[geoid]}",\n')
        f.write("}\n")
    return map_path


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert KML shapes to OBJ with name + material")
    parser.add_argument("input_kml", help="Path to input .kml")
    parser.add_argument("output_path", nargs="?", help="Path to output .obj file")
    parser.add_argument("--point-radius", type=float, default=1.0, help="Point marker radius in meters")
    parser.add_argument("--line-width", type=float, default=0.2, help="Line thickness in meters")
    parser.add_argument("--polygon-height", type=float, default=0.0, help="Extrusion height for polygons in meters")
    parser.add_argument(
        "--polygon-outline-width",
        type=float,
        default=0.0,
        help="Outline thickness in meters for polygon rings (0 disables)",
    )
    parser.add_argument(
        "--polygon-outline-only",
        action="store_true",
        help="Export polygons only as outline geometry (no filled polygon mesh)",
    )
    parser.add_argument(
        "--polygon-front",
        choices=["up", "down", "keep"],
        default="up",
        help="Front-face direction for non-extruded polygons",
    )
    parser.add_argument(
        "--decimate-tolerance",
        type=float,
        default=0.0,
        help="Simplify LineString/Polygon coordinates in meters (0 disables)",
    )
    parser.add_argument("--flip-winding", action="store_true", help="Flip triangle winding for all meshes")
    parser.add_argument("--up-axis", choices=["x", "y", "z"], default="z", help="World up axis")
    parser.add_argument("--scale", type=float, default=1.0, help="Global scale multiplier")
    parser.add_argument("--scale-x", type=float, default=1.0, help="Additional scale multiplier for X axis")
    parser.add_argument("--scale-y", type=float, default=1.0, help="Additional scale multiplier for Y axis")
    parser.add_argument("--scale-z", type=float, default=1.0, help="Additional scale multiplier for Z axis")
    parser.add_argument(
        "--material-mode",
        choices=["per-shape", "source", "shared"],
        default="source",
        help="Material assignment strategy",
    )
    parser.add_argument(
        "--partition-level",
        default="all",
        help="Partition output by hierarchy level: 'all' or a positive integer (1,2,3,...)",
    )
    parser.add_argument(
        "--inspect-kml",
        action="store_true",
        help="Print source KML structure report and exit (no export)",
    )

    args = parser.parse_args(argv)
    if args.inspect_kml:
        print(_inspect_kml(args.input_kml))
        return 0
    if not args.output_path:
        print("Error: output_path is required unless --inspect-kml is used.")
        return 1

    try:
        partition_level = _parse_partition_level(args.partition_level)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1
    if args.decimate_tolerance < 0.0:
        print("Error: decimate tolerance must be >= 0")
        return 1
    if args.polygon_outline_width < 0.0:
        print("Error: polygon outline width must be >= 0")
        return 1
    if args.polygon_outline_only and args.polygon_outline_width <= 0.0:
        print("Error: polygon outline only mode requires --polygon-outline-width > 0")
        return 1
    if args.scale <= 0.0 or args.scale_x <= 0.0 or args.scale_y <= 0.0 or args.scale_z <= 0.0:
        print("Error: scale values must be > 0")
        return 1

    scene = parse_kml(args.input_kml)
    if not scene.shapes:
        print("Error: no supported shapes found in KML.")
        return 1

    projected = []
    sx = args.scale * args.scale_x
    sy = args.scale * args.scale_y
    sz = args.scale * args.scale_z
    for shape in scene.shapes:
        projected_coords = _project_shape(shape, scene.origin_lon, scene.origin_lat, up_axis=args.up_axis)
        decimated = _decimate_shape_coords(
            shape.geometry_type, projected_coords, args.decimate_tolerance, up_axis=args.up_axis
        )
        scaled = _scale_shape_coords(shape.geometry_type, decimated, sx=sx, sy=sy, sz=sz)
        projected.append(
            {
                "name": shape.name,
                "hierarchy": list(shape.hierarchy),
                "geometry_type": shape.geometry_type,
                "coordinates": scaled,
                "rgba": shape.rgba,
                "material_source": shape.material_source,
            }
        )

    grouped: Dict[Tuple[str, ...], List[ObjMeshObject]] = defaultdict(list)
    skipped = 0
    for item in projected:
        shape_view = SimpleNamespace(
            name=item["name"],
            hierarchy=item["hierarchy"],
            geometry_type=item["geometry_type"],
            coordinates=item["coordinates"],
            rgba=item["rgba"],
            material_source=item["material_source"],
        )

        mesh = _shape_to_mesh(
            shape_view,
            point_radius=args.point_radius,
            line_width=args.line_width,
            polygon_height=args.polygon_height,
            up_axis=args.up_axis,
        )
        if item["geometry_type"] == "Polygon" and args.polygon_outline_only:
            mesh = type(mesh)(vertices=[], triangles=[])
        if item["geometry_type"] == "Polygon" and args.polygon_height <= 0.0 and args.polygon_front != "keep":
            mesh = _orient_polygon_front(mesh, up=(args.polygon_front == "up"), up_axis=args.up_axis)
        if args.flip_winding:
            mesh = flip_mesh_winding(mesh)

        key = _partition_key(item["hierarchy"], partition_level)
        generated_any = False
        if mesh.vertices and mesh.triangles:
            grouped[key].append(
                ObjMeshObject(
                    name=item["name"],
                    mesh=mesh,
                    rgba=item["rgba"],
                    material_key=item["material_source"] or item["name"],
                )
            )
            generated_any = True

        if item["geometry_type"] == "Polygon" and args.polygon_outline_width > 0.0:
            outline = polygon_outline_mesh_axis(item["coordinates"], args.polygon_outline_width, up_axis=args.up_axis)
            if args.flip_winding:
                outline = flip_mesh_winding(outline)
            if outline.vertices and outline.triangles:
                grouped[key].append(
                    ObjMeshObject(
                        name=f"{item['name']}_Outline",
                        mesh=outline,
                        rgba=item["rgba"],
                        material_key=item["material_source"] or item["name"],
                    )
                )
                generated_any = True

        if not generated_any:
            skipped += 1
            print(f"Warning: shape '{item['name']}' produced empty mesh and was skipped.")
            continue

    if not grouped:
        print("Error: no valid meshes generated from KML shapes.")
        return 1

    out_dir = os.path.dirname(args.output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    out_stem, out_ext = os.path.splitext(args.output_path)
    generated_paths: List[str] = []
    for key, objects in sorted(grouped.items()):
        if partition_level is None:
            target_path = args.output_path
        else:
            suffix = "_".join(_safe_token(part) for part in key)
            target_path = f"{out_stem}__{suffix}{out_ext}"

        mtl_path = os.path.splitext(target_path)[0] + ".mtl"
        write_obj_with_mtl(
            obj_path=target_path,
            mtl_path=mtl_path,
            objects=objects,
            double_sided=False,
            include_materials=True,
            material_mode=args.material_mode,
        )
        generated_paths.append(target_path)

    print(
        f"OK: generated obj in {len(generated_paths)} file(s), "
        f"{sum(len(v) for v in grouped.values())} object(s) from {len(scene.shapes)} shape(s). "
        f"Skipped: {skipped}. Output base: {args.output_path}"
    )
    out_py = _write_geoid_map_py(scene, args.output_path)
    print(f"OK: wrote GEOID map: {out_py}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
