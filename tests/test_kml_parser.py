from __future__ import annotations

import tempfile
from pathlib import Path

from kml_to_fbx.kml_parser import parse_kml


def test_parse_example_kml():
    kml_path = Path(__file__).resolve().parents[1] / "samples" / "example.kml"
    scene = parse_kml(str(kml_path))

    assert len(scene.shapes) == 3

    names = [s.name for s in scene.shapes]
    assert "SamplePoint" in names
    assert "SampleLine" in names
    assert "SamplePolygon" in names

    line = next(s for s in scene.shapes if s.name == "SampleLine")
    assert line.geometry_type == "LineString"
    # ff00ff00 -> opaque green in KML (aabbggrr)
    assert line.rgba == (0.0, 1.0, 0.0, 1.0)


def test_parse_nested_hierarchy_names():
    kml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>US</name>
    <Folder>
      <name>Colorado</name>
      <Folder>
        <name>Denver</name>
        <Placemark>
          <name>District1</name>
          <Point><coordinates>-104.99,39.74,0</coordinates></Point>
        </Placemark>
      </Folder>
    </Folder>
  </Document>
</kml>"""
    with tempfile.TemporaryDirectory(prefix="kml_nested_") as tmpdir:
        p = Path(tmpdir) / "nested.kml"
        p.write_text(kml, encoding="utf-8")
        scene = parse_kml(str(p))

    assert len(scene.shapes) == 1
    shape = scene.shapes[0]
    assert shape.hierarchy == ["US", "Colorado", "Denver", "District1"]
    assert shape.name == "US_Colorado_Denver_District1"


def test_geoid_prefixes_leaf_name_in_hierarchy():
    kml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>US</name>
    <Placemark>
      <name>Adams</name>
      <ExtendedData>
        <SchemaData>
          <SimpleData name="GEOID">08001</SimpleData>
        </SchemaData>
      </ExtendedData>
      <Polygon>
        <outerBoundaryIs><LinearRing><coordinates>
          -3,40,0 -2,40,0 -2,41,0 -3,41,0 -3,40,0
        </coordinates></LinearRing></outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>"""
    with tempfile.TemporaryDirectory(prefix="kml_geoid_") as tmpdir:
        p = Path(tmpdir) / "geoid.kml"
        p.write_text(kml, encoding="utf-8")
        scene = parse_kml(str(p))

    assert len(scene.shapes) == 1
    shape = scene.shapes[0]
    assert shape.hierarchy[-1] == "08001_Adams"
    assert shape.name == "US_08001_Adams"
