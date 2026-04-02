from __future__ import annotations

from pathlib import Path

from kml_to_fbx.fbx_writer import FbxMeshObject, write_ascii_fbx
from kml_to_fbx.mesh_builder import MeshData


def test_write_ascii_fbx_smoke(tmp_path: Path):
    mesh = MeshData(
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        triangles=[(0, 1, 2)],
    )
    out = tmp_path / "tri.fbx"
    write_ascii_fbx(str(out), [FbxMeshObject(name="Tri", mesh=mesh, rgba=(1.0, 0.0, 0.0, 1.0))])

    text = out.read_text(encoding="utf-8")
    assert "Geometry::Tri" in text
    assert "Model::Tri" in text
    assert "Material::MAT_Tri" in text
    assert "PolygonVertexIndex" in text
    assert "GeometryVersion: 124" in text
    assert "LayerElementNormal" in text
