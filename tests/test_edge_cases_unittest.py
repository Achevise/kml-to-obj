from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kml_to_fbx.fbx_writer import FbxMeshObject, write_ascii_fbx
from kml_to_fbx.kml_parser import parse_kml
from kml_to_fbx.mesh_builder import MeshData, linestring_to_ribbon_mesh, polygon_to_mesh


def _tri_area_xy(a, b, c):
    return abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) * 0.5


def _mesh_area_xy(mesh: MeshData) -> float:
    area = 0.0
    for i, j, k in mesh.triangles:
        area += _tri_area_xy(mesh.vertices[i], mesh.vertices[j], mesh.vertices[k])
    return area


class EdgeCaseSuite(unittest.TestCase):
    def _parse_from_text(self, kml_text: str):
        with tempfile.TemporaryDirectory(prefix="kml_test_") as tmpdir:
            path = Path(tmpdir) / "input.kml"
            path.write_text(kml_text, encoding="utf-8")
            return parse_kml(str(path))

    def test_multigeometry_default_name_and_indexing(self):
        kml = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<kml xmlns=\"http://www.opengis.net/kml/2.2\"><Document>
  <Placemark>
    <MultiGeometry>
      <Point><coordinates>-3,40,0</coordinates></Point>
      <LineString><coordinates>-3,40,0</coordinates></LineString>
      <Polygon><outerBoundaryIs><LinearRing><coordinates>
        -3,40,0 -2,40,0 -2,41,0 -3,41,0 -3,40,0
      </coordinates></LinearRing></outerBoundaryIs></Polygon>
    </MultiGeometry>
  </Placemark>
</Document></kml>"""
        scene = self._parse_from_text(kml)
        self.assertEqual(2, len(scene.shapes))
        self.assertEqual("Placemark_1_1", scene.shapes[0].name)
        self.assertEqual("Placemark_1_2", scene.shapes[1].name)

    def test_stylemap_normal_color_resolution(self):
        kml = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<kml xmlns=\"http://www.opengis.net/kml/2.2\"><Document>
  <Style id=\"lineS\"><LineStyle><color>ff0000ff</color></LineStyle></Style>
  <StyleMap id=\"lineMap\">
    <Pair><key>normal</key><styleUrl>#lineS</styleUrl></Pair>
    <Pair><key>highlight</key><styleUrl>#lineS</styleUrl></Pair>
  </StyleMap>
  <Placemark>
    <name>L1</name>
    <styleUrl>#lineMap</styleUrl>
    <LineString><coordinates>0,0,0 1,0,0</coordinates></LineString>
  </Placemark>
</Document></kml>"""
        scene = self._parse_from_text(kml)
        self.assertEqual(1, len(scene.shapes))
        # ff0000ff in aabbggrr => red
        self.assertEqual((1.0, 0.0, 0.0, 1.0), scene.shapes[0].rgba)

    def test_geoid_is_prefixed_in_leaf_hierarchy_name(self):
        kml = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<kml xmlns=\"http://www.opengis.net/kml/2.2\"><Document>
  <name>US</name>
  <Placemark>
    <name>Adams</name>
    <ExtendedData><SchemaData>
      <SimpleData name=\"GEOID\">08001</SimpleData>
    </SchemaData></ExtendedData>
    <Polygon><outerBoundaryIs><LinearRing><coordinates>
      -3,40,0 -2,40,0 -2,41,0 -3,41,0 -3,40,0
    </coordinates></LinearRing></outerBoundaryIs></Polygon>
  </Placemark>
</Document></kml>"""
        scene = self._parse_from_text(kml)
        self.assertEqual(1, len(scene.shapes))
        s = scene.shapes[0]
        self.assertEqual("08001_Adams", s.hierarchy[-1])
        self.assertEqual("US_08001_Adams", s.name)

    def test_polygon_with_hole_reorients_and_triangulates(self):
        # Outer CW + hole CCW to force orientation normalization.
        outer_cw = [
            (0.0, 0.0, 0.0),
            (0.0, 10.0, 0.0),
            (10.0, 10.0, 0.0),
            (10.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
        ]
        hole_ccw = [
            (3.0, 3.0, 0.0),
            (7.0, 3.0, 0.0),
            (7.0, 7.0, 0.0),
            (3.0, 7.0, 0.0),
            (3.0, 3.0, 0.0),
        ]
        mesh = polygon_to_mesh([outer_cw, hole_ccw])
        self.assertTrue(mesh.vertices)
        self.assertTrue(mesh.triangles)
        self.assertAlmostEqual(84.0, _mesh_area_xy(mesh), places=6)

    def test_polygon_with_multiple_holes(self):
        outer = [
            (0.0, 0.0, 0.0),
            (20.0, 0.0, 0.0),
            (20.0, 20.0, 0.0),
            (0.0, 20.0, 0.0),
            (0.0, 0.0, 0.0),
        ]
        hole1 = [
            (2.0, 2.0, 0.0),
            (2.0, 6.0, 0.0),
            (6.0, 6.0, 0.0),
            (6.0, 2.0, 0.0),
            (2.0, 2.0, 0.0),
        ]
        hole2 = [
            (12.0, 10.0, 0.0),
            (12.0, 13.0, 0.0),
            (16.0, 13.0, 0.0),
            (16.0, 10.0, 0.0),
            (12.0, 10.0, 0.0),
        ]
        mesh = polygon_to_mesh([outer, hole1, hole2])
        self.assertTrue(mesh.vertices)
        self.assertTrue(mesh.triangles)
        # 20*20 - 4*4 - 4*3 = 372
        self.assertAlmostEqual(372.0, _mesh_area_xy(mesh), places=6)

    def test_polygon_degenerate_colinear_returns_empty(self):
        ring = [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
        ]
        mesh = polygon_to_mesh([ring])
        self.assertEqual([], mesh.vertices)
        self.assertEqual([], mesh.triangles)

    def test_linestring_repeated_points_still_builds_mesh_shape(self):
        coords = [
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
        ]
        mesh = linestring_to_ribbon_mesh(coords, width=1.0)
        self.assertEqual(6, len(mesh.vertices))
        self.assertEqual(4, len(mesh.triangles))

    def test_fbx_writer_skips_empty_mesh_objects(self):
        with tempfile.TemporaryDirectory(prefix="fbx_test_") as tmpdir:
            out = Path(tmpdir) / "out.fbx"
            write_ascii_fbx(
                str(out),
                [
                    FbxMeshObject(name="Empty", mesh=MeshData(vertices=[], triangles=[]), rgba=(1, 1, 1, 1)),
                    FbxMeshObject(
                        name="Valid",
                        mesh=MeshData(vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)], triangles=[(0, 1, 2)]),
                        rgba=(0.2, 0.4, 0.6, 1.0),
                    ),
                ],
            )
            text = out.read_text(encoding="utf-8")
            self.assertIn("Geometry::Valid", text)
            self.assertNotIn("Geometry::Empty", text)


if __name__ == "__main__":
    unittest.main()
