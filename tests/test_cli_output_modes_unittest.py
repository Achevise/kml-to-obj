from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from kml_to_fbx.cli import main as cli_main


class CliOutputModesSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample_kml = Path(__file__).resolve().parents[1] / "samples" / "example.kml"

    def test_obj_mode_writes_obj_and_mtl(self):
        with tempfile.TemporaryDirectory(prefix="kml_cli_obj_") as tmpdir:
            obj_path = Path(tmpdir) / "scene.obj"
            rc = cli_main([str(self.sample_kml), str(obj_path), "--output-format", "obj"])
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
            rc = cli_main([str(self.sample_kml), str(obj_path), "--output-format", "obj", "--material-mode", "shared"])
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
            rc = cli_main([str(kml_path), str(obj_path), "--output-format", "obj", "--material-mode", "source"])
            self.assertEqual(0, rc)
            mtl_text = obj_path.with_suffix(".mtl").read_text(encoding="utf-8")
            self.assertEqual(1, sum(1 for ln in mtl_text.splitlines() if ln.startswith("newmtl ")))

    def test_fbx_sdk_mode_writes_binary_fbx(self):
        with tempfile.TemporaryDirectory(prefix="kml_cli_fbxsdk_") as tmpdir:
            fbx_path = Path(tmpdir) / "scene_fbxsdk.fbx"
            rc = cli_main([str(self.sample_kml), str(fbx_path), "--output-format", "fbx-sdk"])
            self.assertEqual(0, rc)
            header = fbx_path.read_bytes()[:32]
            self.assertTrue(header.startswith(b"Kaydara FBX Binary  "))

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
            rc = cli_main([str(kml_path), str(out_base), "--output-format", "obj", "--partition-level", "2"])
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
            rc_no = cli_main([str(kml_path), str(obj_no), "--output-format", "obj"])
            self.assertEqual(0, rc_no)

            obj_dec = Path(tmpdir) / "line_dec.obj"
            rc_dec = cli_main(
                [
                    str(kml_path),
                    str(obj_dec),
                    "--output-format",
                    "obj",
                    "--decimate-tolerance",
                    "5.0",
                ]
            )
            self.assertEqual(0, rc_dec)

            v_no = sum(1 for ln in obj_no.read_text(encoding="utf-8").splitlines() if ln.startswith("v "))
            v_dec = sum(1 for ln in obj_dec.read_text(encoding="utf-8").splitlines() if ln.startswith("v "))
            self.assertLess(v_dec, v_no)

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
            rc_up = cli_main([str(kml_path), str(up_obj), "--output-format", "obj", "--polygon-front", "up"])
            self.assertEqual(0, rc_up)
            up_normals = [
                float(ln.split()[2])
                for ln in up_obj.read_text(encoding="utf-8").splitlines()
                if ln.startswith("vn ")
            ]
            self.assertTrue(up_normals)
            self.assertTrue(all(ny > 0.0 for ny in up_normals))

            down_obj = Path(tmpdir) / "down.obj"
            rc_down = cli_main([str(kml_path), str(down_obj), "--output-format", "obj", "--polygon-front", "down"])
            self.assertEqual(0, rc_down)
            down_normals = [
                float(ln.split()[2])
                for ln in down_obj.read_text(encoding="utf-8").splitlines()
                if ln.startswith("vn ")
            ]
            self.assertTrue(down_normals)
            self.assertTrue(all(ny < 0.0 for ny in down_normals))

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


if __name__ == "__main__":
    unittest.main()
