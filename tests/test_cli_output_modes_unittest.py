from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from kml_to_obj.cli import main as cli_main


class CliOutputModesSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample_kml = Path(__file__).resolve().parents[1] / "samples" / "example.kml"

    def test_obj_mode_writes_obj_and_mtl(self):
        with tempfile.TemporaryDirectory(prefix="kml_cli_obj_") as tmpdir:
            obj_path = Path(tmpdir) / "scene.obj"
            rc = cli_main([str(self.sample_kml), str(obj_path)])
            self.assertEqual(0, rc)

            mtl_path = obj_path.with_suffix(".mtl")
            self.assertTrue(obj_path.exists())
            self.assertTrue(mtl_path.exists())

            obj_text = obj_path.read_text(encoding="utf-8")
            mtl_text = mtl_path.read_text(encoding="utf-8")
            self.assertIn("mtllib scene.mtl", obj_text)
            self.assertIn("o SamplePoint", obj_text)
            self.assertIn("newmtl MAT_style__lineGreen", mtl_text)

    def test_obj_shared_material_mode_writes_single_material(self):
        with tempfile.TemporaryDirectory(prefix="kml_cli_obj_shared_") as tmpdir:
            obj_path = Path(tmpdir) / "scene.obj"
            rc = cli_main([str(self.sample_kml), str(obj_path), "--material-mode", "shared"])
            self.assertEqual(0, rc)

            mtl_path = obj_path.with_suffix(".mtl")
            self.assertTrue(obj_path.exists())
            self.assertTrue(mtl_path.exists())

            obj_text = obj_path.read_text(encoding="utf-8")
            mtl_text = mtl_path.read_text(encoding="utf-8")
            self.assertEqual(1, sum(1 for ln in mtl_text.splitlines() if ln.startswith("newmtl ")))
            self.assertIn("newmtl MAT_SHARED", mtl_text)
            self.assertIn("usemtl MAT_SHARED", obj_text)

    def test_obj_source_material_mode_groups_by_kml_style(self):
        kml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Style id="same"><PolyStyle><color>ff0000ff</color></PolyStyle></Style>
    <Placemark>
      <name>A</name><styleUrl>#same</styleUrl>
      <Polygon><outerBoundaryIs><LinearRing><coordinates>
        -3.0,40.0,0 -2.9,40.0,0 -2.9,40.1,0 -3.0,40.1,0 -3.0,40.0,0
      </coordinates></LinearRing></outerBoundaryIs></Polygon>
    </Placemark>
    <Placemark>
      <name>B</name><styleUrl>#same</styleUrl>
      <Polygon><outerBoundaryIs><LinearRing><coordinates>
        -3.2,40.0,0 -3.1,40.0,0 -3.1,40.1,0 -3.2,40.1,0 -3.2,40.0,0
      </coordinates></LinearRing></outerBoundaryIs></Polygon>
    </Placemark>
  </Document>
</kml>"""
        with tempfile.TemporaryDirectory(prefix="kml_cli_obj_source_") as tmpdir:
            kml_path = Path(tmpdir) / "src.kml"
            kml_path.write_text(kml, encoding="utf-8")
            obj_path = Path(tmpdir) / "scene.obj"
            rc = cli_main([str(kml_path), str(obj_path), "--material-mode", "source"])
            self.assertEqual(0, rc)
            mtl_text = obj_path.with_suffix(".mtl").read_text(encoding="utf-8")
            self.assertEqual(1, sum(1 for ln in mtl_text.splitlines() if ln.startswith("newmtl ")))

    def test_partition_level_splits_files_by_hierarchy(self):
        nested_kml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>US</name>
    <Folder>
      <name>Colorado</name>
      <Placemark>
        <name>Denver</name>
        <Point><coordinates>-104.99,39.74,0</coordinates></Point>
      </Placemark>
    </Folder>
    <Folder>
      <name>Texas</name>
      <Placemark>
        <name>Austin</name>
        <Point><coordinates>-97.74,30.27,0</coordinates></Point>
      </Placemark>
    </Folder>
  </Document>
</kml>"""
        with tempfile.TemporaryDirectory(prefix="kml_cli_partition_") as tmpdir:
            kml_path = Path(tmpdir) / "nested.kml"
            kml_path.write_text(nested_kml, encoding="utf-8")

            out_base = Path(tmpdir) / "scene.obj"
            rc = cli_main([str(kml_path), str(out_base), "--partition-level", "2"])
            self.assertEqual(0, rc)

            out1 = Path(tmpdir) / "scene__US_Colorado.obj"
            out2 = Path(tmpdir) / "scene__US_Texas.obj"
            self.assertTrue(out1.exists())
            self.assertTrue(out2.exists())

            self.assertIn("o US_Colorado_Denver", out1.read_text(encoding="utf-8"))
            self.assertIn("o US_Texas_Austin", out2.read_text(encoding="utf-8"))

    def test_decimate_tolerance_reduces_linestring_geometry(self):
        line_kml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>LineDense</name>
      <LineString>
        <coordinates>
          -3.00000,40.00000,0
          -2.99990,40.00000,0
          -2.99980,40.00000,0
          -2.99970,40.00000,0
          -2.99960,40.00000,0
          -2.99950,40.00000,0
          -2.99940,40.00000,0
          -2.99930,40.00000,0
          -2.99920,40.00000,0
          -2.99910,40.00000,0
          -2.99900,40.00000,0
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>"""
        with tempfile.TemporaryDirectory(prefix="kml_cli_decimate_") as tmpdir:
            kml_path = Path(tmpdir) / "line.kml"
            kml_path.write_text(line_kml, encoding="utf-8")

            obj_no = Path(tmpdir) / "line_no.obj"
            rc_no = cli_main([str(kml_path), str(obj_no)])
            self.assertEqual(0, rc_no)

            obj_dec = Path(tmpdir) / "line_dec.obj"
            rc_dec = cli_main(
                [
                    str(kml_path),
                    str(obj_dec),
                    "--decimate-tolerance",
                    "5.0",
                ]
            )
            self.assertEqual(0, rc_dec)

            v_no = sum(1 for ln in obj_no.read_text(encoding="utf-8").splitlines() if ln.startswith("v "))
            v_dec = sum(1 for ln in obj_dec.read_text(encoding="utf-8").splitlines() if ln.startswith("v "))
            self.assertLess(v_dec, v_no)

    def test_polygon_outline_width_adds_geometry(self):
        poly_kml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>P</name>
      <Polygon><outerBoundaryIs><LinearRing><coordinates>
        -3.0,40.0,0 -2.9,40.0,0 -2.9,40.1,0 -3.0,40.1,0 -3.0,40.0,0
      </coordinates></LinearRing></outerBoundaryIs></Polygon>
    </Placemark>
  </Document>
</kml>"""
        with tempfile.TemporaryDirectory(prefix="kml_cli_outline_") as tmpdir:
            kml_path = Path(tmpdir) / "poly.kml"
            kml_path.write_text(poly_kml, encoding="utf-8")

            obj_no = Path(tmpdir) / "poly_no.obj"
            rc_no = cli_main([str(kml_path), str(obj_no)])
            self.assertEqual(0, rc_no)

            obj_ol = Path(tmpdir) / "poly_ol.obj"
            rc_ol = cli_main([str(kml_path), str(obj_ol), "--polygon-outline-width", "5.0"])
            self.assertEqual(0, rc_ol)

            v_no = sum(1 for ln in obj_no.read_text(encoding="utf-8").splitlines() if ln.startswith("v "))
            ol_text = obj_ol.read_text(encoding="utf-8")
            v_ol = sum(1 for ln in ol_text.splitlines() if ln.startswith("v "))
            self.assertGreater(v_ol, v_no)
            self.assertIn("o P", ol_text)
            self.assertIn("o P_Outline", ol_text)

    def test_polygon_outline_only_skips_polygon_fill(self):
        poly_kml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>P</name>
      <Polygon><outerBoundaryIs><LinearRing><coordinates>
        -3.0,40.0,0 -2.9,40.0,0 -2.9,40.1,0 -3.0,40.1,0 -3.0,40.0,0
      </coordinates></LinearRing></outerBoundaryIs></Polygon>
    </Placemark>
  </Document>
</kml>"""
        with tempfile.TemporaryDirectory(prefix="kml_cli_outline_only_") as tmpdir:
            kml_path = Path(tmpdir) / "poly.kml"
            kml_path.write_text(poly_kml, encoding="utf-8")

            obj_path = Path(tmpdir) / "poly_outline_only.obj"
            rc = cli_main([str(kml_path), str(obj_path), "--polygon-outline-width", "5.0", "--polygon-outline-only"])
            self.assertEqual(0, rc)
            text = obj_path.read_text(encoding="utf-8")
            self.assertNotIn("o P\n", text)
            self.assertIn("o P_Outline", text)

    def test_polygon_front_normalization_up_and_down(self):
        poly_kml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>A</name>
      <Polygon><outerBoundaryIs><LinearRing><coordinates>
        -3.0,40.0,0 -2.9,40.0,0 -2.9,40.1,0 -3.0,40.1,0 -3.0,40.0,0
      </coordinates></LinearRing></outerBoundaryIs></Polygon>
    </Placemark>
    <Placemark>
      <name>B</name>
      <Polygon><outerBoundaryIs><LinearRing><coordinates>
        -3.2,40.0,0 -3.2,40.1,0 -3.1,40.1,0 -3.1,40.0,0 -3.2,40.0,0
      </coordinates></LinearRing></outerBoundaryIs></Polygon>
    </Placemark>
  </Document>
</kml>"""
        with tempfile.TemporaryDirectory(prefix="kml_cli_polyfront_") as tmpdir:
            kml_path = Path(tmpdir) / "poly.kml"
            kml_path.write_text(poly_kml, encoding="utf-8")

            up_obj = Path(tmpdir) / "up.obj"
            rc_up = cli_main([str(kml_path), str(up_obj), "--polygon-front", "up"])
            self.assertEqual(0, rc_up)
            up_normals = [
                float(ln.split()[3])
                for ln in up_obj.read_text(encoding="utf-8").splitlines()
                if ln.startswith("vn ")
            ]
            self.assertTrue(up_normals)
            self.assertTrue(all(nz > 0.0 for nz in up_normals))

            down_obj = Path(tmpdir) / "down.obj"
            rc_down = cli_main([str(kml_path), str(down_obj), "--polygon-front", "down"])
            self.assertEqual(0, rc_down)
            down_normals = [
                float(ln.split()[3])
                for ln in down_obj.read_text(encoding="utf-8").splitlines()
                if ln.startswith("vn ")
            ]
            self.assertTrue(down_normals)
            self.assertTrue(all(nz < 0.0 for nz in down_normals))

    def test_inspect_kml_outputs_source_summary(self):
        buf = StringIO()
        with redirect_stdout(buf):
            rc = cli_main([str(self.sample_kml), "--inspect-kml"])
        self.assertEqual(0, rc)
        out = buf.getvalue()
        self.assertIn("Structure:", out)
        self.assertIn("Objects (Placemark):", out)
        self.assertIn("Shape types:", out)
        self.assertIn("Materials / styles:", out)

    def test_generates_out_py_geoid_map(self):
        kml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>US</name>
    <Placemark>
      <name>Adams</name>
      <ExtendedData><SchemaData>
        <SimpleData name="GEOID">08001</SimpleData>
      </SchemaData></ExtendedData>
      <Polygon><outerBoundaryIs><LinearRing><coordinates>
        -3.0,40.0,0 -2.9,40.0,0 -2.9,40.1,0 -3.0,40.1,0 -3.0,40.0,0
      </coordinates></LinearRing></outerBoundaryIs></Polygon>
    </Placemark>
  </Document>
</kml>"""
        with tempfile.TemporaryDirectory(prefix="kml_cli_outpy_") as tmpdir:
            kml_path = Path(tmpdir) / "geoid.kml"
            kml_path.write_text(kml, encoding="utf-8")
            obj_path = Path(tmpdir) / "scene.obj"
            rc = cli_main([str(kml_path), str(obj_path)])
            self.assertEqual(0, rc)

            out_py = Path(tmpdir) / "scene.py"
            self.assertTrue(out_py.exists())
            text = out_py.read_text(encoding="utf-8")
            self.assertIn('GEOID_TO_OBJECT = {', text)
            self.assertIn('"08001": "US_08001_Adams"', text)

    def test_up_axis_controls_altitude_axis(self):
        point_kml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>P</name>
      <Point><coordinates>-3.0,40.0,10</coordinates></Point>
    </Placemark>
  </Document>
</kml>"""
        with tempfile.TemporaryDirectory(prefix="kml_cli_upaxis_") as tmpdir:
            kml_path = Path(tmpdir) / "p.kml"
            kml_path.write_text(point_kml, encoding="utf-8")

            def centroid_for(args):
                obj_path = Path(tmpdir) / f"p_{'_'.join(args) if args else 'z'}.obj"
                rc = cli_main([str(kml_path), str(obj_path), *args])
                self.assertEqual(0, rc)
                verts = []
                for ln in obj_path.read_text(encoding="utf-8").splitlines():
                    if ln.startswith("v "):
                        _v, x, y, z = ln.split()
                        verts.append((float(x), float(y), float(z)))
                self.assertTrue(verts)
                n = len(verts)
                return (
                    sum(v[0] for v in verts) / n,
                    sum(v[1] for v in verts) / n,
                    sum(v[2] for v in verts) / n,
                )

            cx, cy, cz = centroid_for([])
            self.assertAlmostEqual(10.0, cz, places=6)  # default z-up
            self.assertAlmostEqual(0.0, cy, places=6)

            cx, cy, cz = centroid_for(["--up-axis", "y"])
            self.assertAlmostEqual(10.0, cy, places=6)
            self.assertAlmostEqual(0.0, cz, places=6)

            cx, cy, cz = centroid_for(["--up-axis", "x"])
            self.assertAlmostEqual(10.0, cx, places=6)

    def test_scale_and_axis_scales_apply(self):
        point_kml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>P</name>
      <Point><coordinates>-3.0,40.0,10</coordinates></Point>
    </Placemark>
  </Document>
</kml>"""
        with tempfile.TemporaryDirectory(prefix="kml_cli_scale_") as tmpdir:
            kml_path = Path(tmpdir) / "p.kml"
            kml_path.write_text(point_kml, encoding="utf-8")

            def centroid(args):
                obj_path = Path(tmpdir) / f"s_{'_'.join(args) if args else 'base'}.obj"
                rc = cli_main([str(kml_path), str(obj_path), *args])
                self.assertEqual(0, rc)
                verts = []
                for ln in obj_path.read_text(encoding="utf-8").splitlines():
                    if ln.startswith("v "):
                        _v, x, y, z = ln.split()
                        verts.append((float(x), float(y), float(z)))
                n = len(verts)
                return (sum(v[0] for v in verts) / n, sum(v[1] for v in verts) / n, sum(v[2] for v in verts) / n)

            # default z-up + global scale
            _, _, z = centroid(["--scale", "3"])
            self.assertAlmostEqual(30.0, z, places=6)

            # y-up + per-axis scale on Y
            _, y, _ = centroid(["--up-axis", "y", "--scale-y", "0.5"])
            self.assertAlmostEqual(5.0, y, places=6)


if __name__ == "__main__":
    unittest.main()
