from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

from .models import RGBAlpha, SceneData, Shape


KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}


def _clean_text(value: Optional[str]) -> str:
    return (value or "").strip()


def _parse_kml_color(color_value: str) -> Optional[RGBAlpha]:
    value = _clean_text(color_value).lower()
    if len(value) != 8:
        return None

    # KML uses aabbggrr
    aa = int(value[0:2], 16)
    bb = int(value[2:4], 16)
    gg = int(value[4:6], 16)
    rr = int(value[6:8], 16)
    return (rr / 255.0, gg / 255.0, bb / 255.0, aa / 255.0)


def _deterministic_rgba(name: str) -> RGBAlpha:
    digest = hashlib.sha1(name.encode("utf-8")).digest()
    return (
        0.2 + (digest[0] / 255.0) * 0.7,
        0.2 + (digest[1] / 255.0) * 0.7,
        0.2 + (digest[2] / 255.0) * 0.7,
        1.0,
    )


def _parse_coord_string(coord_text: str) -> List[Tuple[float, float, float]]:
    out: List[Tuple[float, float, float]] = []
    for token in coord_text.replace("\n", " ").split():
        parts = token.split(",")
        if len(parts) < 2:
            continue
        lon = float(parts[0])
        lat = float(parts[1])
        alt = float(parts[2]) if len(parts) > 2 and parts[2] else 0.0
        out.append((lon, lat, alt))
    return out


def _extract_style_color(style_node: ET.Element) -> Optional[RGBAlpha]:
    for tag in ("PolyStyle", "LineStyle", "IconStyle"):
        color_el = style_node.find(f"kml:{tag}/kml:color", KML_NS)
        if color_el is not None and color_el.text:
            rgba = _parse_kml_color(color_el.text)
            if rgba is not None:
                return rgba
    return None


def _parse_styles(root: ET.Element) -> Tuple[Dict[str, RGBAlpha], Dict[str, str]]:
    style_colors: Dict[str, RGBAlpha] = {}
    style_map: Dict[str, str] = {}

    for style in root.findall(".//kml:Style", KML_NS):
        style_id = style.attrib.get("id")
        if not style_id:
            continue
        rgba = _extract_style_color(style)
        if rgba:
            style_colors[f"#{style_id}"] = rgba

    for smap in root.findall(".//kml:StyleMap", KML_NS):
        map_id = smap.attrib.get("id")
        if not map_id:
            continue
        for pair in smap.findall("kml:Pair", KML_NS):
            key_el = pair.find("kml:key", KML_NS)
            style_url_el = pair.find("kml:styleUrl", KML_NS)
            if key_el is None or style_url_el is None:
                continue
            if _clean_text(key_el.text) == "normal":
                style_map[f"#{map_id}"] = _clean_text(style_url_el.text)

    return style_colors, style_map


def _resolve_material(
    placemark: ET.Element,
    style_colors: Dict[str, RGBAlpha],
    style_map: Dict[str, str],
    name: str,
) -> Tuple[RGBAlpha, str]:
    inline_style = placemark.find("kml:Style", KML_NS)
    if inline_style is not None:
        rgba = _extract_style_color(inline_style)
        if rgba:
            return rgba, f"inline:{rgba}"

    style_url_el = placemark.find("kml:styleUrl", KML_NS)
    if style_url_el is not None and style_url_el.text:
        style_ref = _clean_text(style_url_el.text)
        mapped = style_map.get(style_ref, style_ref)
        rgba = style_colors.get(mapped)
        if rgba:
            return rgba, f"style:{mapped}"

    return _deterministic_rgba(name), f"auto:{name}"


def _add_point_shapes(
    container: List[Shape],
    base_name: str,
    hierarchy: List[str],
    geom_node: ET.Element,
    rgba: RGBAlpha,
    material_source: str,
) -> None:
    coord_el = geom_node.find("kml:coordinates", KML_NS)
    if coord_el is None or not coord_el.text:
        return
    coords = _parse_coord_string(coord_el.text)
    if not coords:
        return
    container.append(
        Shape(
            name=base_name,
            hierarchy=hierarchy,
            geometry_type="Point",
            coordinates=[coords[0]],
            rgba=rgba,
            material_source=material_source,
        )
    )


def _add_linestring_shapes(
    container: List[Shape],
    base_name: str,
    hierarchy: List[str],
    geom_node: ET.Element,
    rgba: RGBAlpha,
    material_source: str,
) -> None:
    coord_el = geom_node.find("kml:coordinates", KML_NS)
    if coord_el is None or not coord_el.text:
        return
    coords = _parse_coord_string(coord_el.text)
    if len(coords) < 2:
        return
    container.append(
        Shape(
            name=base_name,
            hierarchy=hierarchy,
            geometry_type="LineString",
            coordinates=coords,
            rgba=rgba,
            material_source=material_source,
        )
    )


def _add_polygon_shapes(
    container: List[Shape],
    base_name: str,
    hierarchy: List[str],
    geom_node: ET.Element,
    rgba: RGBAlpha,
    material_source: str,
) -> None:
    rings: List[List[Tuple[float, float, float]]] = []

    outer = geom_node.find("kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", KML_NS)
    if outer is not None and outer.text:
        coords = _parse_coord_string(outer.text)
        if len(coords) >= 3:
            rings.append(coords)

    for inner in geom_node.findall("kml:innerBoundaryIs/kml:LinearRing/kml:coordinates", KML_NS):
        if inner.text:
            coords = _parse_coord_string(inner.text)
            if len(coords) >= 3:
                rings.append(coords)

    if rings:
        container.append(
            Shape(
                name=base_name,
                hierarchy=hierarchy,
                geometry_type="Polygon",
                coordinates=rings,
                rgba=rgba,
                material_source=material_source,
            )
        )


def _node_name(node: ET.Element, fallback: str) -> str:
    value = _clean_text(node.findtext("kml:name", default="", namespaces=KML_NS))
    return value if value else fallback


def _node_name_if_present(node: ET.Element) -> str:
    return _clean_text(node.findtext("kml:name", default="", namespaces=KML_NS))


def _extract_geoid(placemark: ET.Element) -> str:
    # Common Census KML schema variants.
    for key in ("GEOID", "GEOID10", "GEO_ID"):
        sd = placemark.find(f".//kml:SimpleData[@name='{key}']", KML_NS)
        if sd is not None and sd.text:
            value = _clean_text(sd.text)
            if value:
                return value
        dv = placemark.find(f".//kml:Data[@name='{key}']/kml:value", KML_NS)
        if dv is not None and dv.text:
            value = _clean_text(dv.text)
            if value:
                return value
    return ""


def _join_hierarchy(parts: List[str]) -> str:
    return "_".join([p for p in parts if p])


def _extract_shapes_from_placemark(
    placemark: ET.Element,
    placemark_index: int,
    ancestry: List[str],
    style_colors: Dict[str, RGBAlpha],
    style_map: Dict[str, str],
    shapes: List[Shape],
) -> None:
    placemark_name = _node_name(placemark, f"Placemark_{placemark_index}")
    geoid = _extract_geoid(placemark)
    leaf_name = f"{geoid}_{placemark_name}" if geoid else placemark_name
    hierarchy = ancestry + [leaf_name]
    base_name = _join_hierarchy(hierarchy)
    rgba, material_source = _resolve_material(placemark, style_colors, style_map, base_name)

    direct_geometries = [
        ("Point", placemark.find("kml:Point", KML_NS)),
        ("LineString", placemark.find("kml:LineString", KML_NS)),
        ("Polygon", placemark.find("kml:Polygon", KML_NS)),
    ]

    for gtype, geom in direct_geometries:
        if geom is None:
            continue
        if gtype == "Point":
            _add_point_shapes(shapes, base_name, hierarchy, geom, rgba, material_source)
        elif gtype == "LineString":
            _add_linestring_shapes(shapes, base_name, hierarchy, geom, rgba, material_source)
        elif gtype == "Polygon":
            _add_polygon_shapes(shapes, base_name, hierarchy, geom, rgba, material_source)

    mgeo = placemark.find("kml:MultiGeometry", KML_NS)
    if mgeo is not None:
        sub_index = 1
        for point in mgeo.findall("kml:Point", KML_NS):
            name = f"{base_name}_{sub_index}"
            _add_point_shapes(shapes, name, hierarchy, point, rgba, material_source)
            if shapes and shapes[-1].name == name:
                sub_index += 1
        for line in mgeo.findall("kml:LineString", KML_NS):
            name = f"{base_name}_{sub_index}"
            _add_linestring_shapes(shapes, name, hierarchy, line, rgba, material_source)
            if shapes and shapes[-1].name == name:
                sub_index += 1
        for poly in mgeo.findall("kml:Polygon", KML_NS):
            name = f"{base_name}_{sub_index}"
            _add_polygon_shapes(shapes, name, hierarchy, poly, rgba, material_source)
            if shapes and shapes[-1].name == name:
                sub_index += 1


def _walk_kml_tree(
    node: ET.Element,
    ancestry: List[str],
    style_colors: Dict[str, RGBAlpha],
    style_map: Dict[str, str],
    shapes: List[Shape],
    counter: Dict[str, int],
) -> None:
    tag = node.tag.split("}")[-1] if "}" in node.tag else node.tag

    if tag == "Placemark":
        counter["placemark"] += 1
        _extract_shapes_from_placemark(node, counter["placemark"], ancestry, style_colors, style_map, shapes)
        return

    next_ancestry = ancestry
    if tag in ("Document", "Folder"):
        container_name = _node_name_if_present(node)
        if container_name:
            next_ancestry = ancestry + [container_name]

    for child in list(node):
        child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if child_tag in ("Document", "Folder", "Placemark"):
            _walk_kml_tree(child, next_ancestry, style_colors, style_map, shapes, counter)


def parse_kml(path: str) -> SceneData:
    tree = ET.parse(path)
    root = tree.getroot()

    style_colors, style_map = _parse_styles(root)
    shapes: List[Shape] = []
    all_coords: List[Tuple[float, float, float]] = []

    counter = {"placemark": 0}
    _walk_kml_tree(root, [], style_colors, style_map, shapes, counter)

    for shape in shapes:
        if shape.geometry_type == "Point":
            all_coords.extend(shape.coordinates)
        elif shape.geometry_type == "LineString":
            all_coords.extend(shape.coordinates)
        elif shape.geometry_type == "Polygon":
            for ring in shape.coordinates:
                all_coords.extend(ring)

    if not all_coords:
        origin_lon, origin_lat = 0.0, 0.0
    else:
        origin_lon = sum(c[0] for c in all_coords) / len(all_coords)
        origin_lat = sum(c[1] for c in all_coords) / len(all_coords)

    return SceneData(shapes=shapes, origin_lon=origin_lon, origin_lat=origin_lat)
