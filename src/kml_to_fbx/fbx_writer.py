from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

from .mesh_builder import MeshData


RGBAlpha = Tuple[float, float, float, float]


@dataclass
class FbxMeshObject:
    name: str
    mesh: MeshData
    rgba: RGBAlpha


class _IdGen:
    def __init__(self, start: int = 1000000):
        self._cur = start

    def next(self) -> int:
        self._cur += 1
        return self._cur


def _q(value: str) -> str:
    return value.replace('"', "'")


def _fmt_float(v: float) -> str:
    return f"{v:.9f}".rstrip("0").rstrip(".") if abs(v) > 1e-12 else "0"


def _polygon_index_stream(tris: Sequence[Tuple[int, int, int]]) -> List[int]:
    out: List[int] = []
    for a, b, c in tris:
        out.extend([a, b, -c - 1])
    return out


def _block_vertices(vertices: Sequence[Tuple[float, float, float]]) -> str:
    flat: List[str] = []
    for x, y, z in vertices:
        flat.extend([_fmt_float(x), _fmt_float(y), _fmt_float(z)])
    return ",".join(flat)


def _block_ints(values: Iterable[int]) -> str:
    return ",".join(str(v) for v in values)


def _sub(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _normalize(v: Tuple[float, float, float]) -> Tuple[float, float, float]:
    n = (v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) ** 0.5
    if n <= 1e-12:
        return (0.0, 0.0, 1.0)
    return (v[0] / n, v[1] / n, v[2] / n)


def _polygon_vertex_normals(vertices: Sequence[Tuple[float, float, float]], tris: Sequence[Tuple[int, int, int]]) -> List[float]:
    out: List[float] = []
    for i, j, k in tris:
        a = vertices[i]
        b = vertices[j]
        c = vertices[k]
        n = _normalize(_cross(_sub(b, a), _sub(c, a)))
        out.extend([n[0], n[1], n[2], n[0], n[1], n[2], n[0], n[1], n[2]])
    return out


def _block_floats(values: Iterable[float]) -> str:
    return ",".join(_fmt_float(v) for v in values)


def write_ascii_fbx(path: str, objects: Sequence[FbxMeshObject]) -> None:
    ids = _IdGen()
    root_model_id = ids.next()

    enriched = []
    for obj in objects:
        if not obj.mesh.vertices or not obj.mesh.triangles:
            continue
        enriched.append(
            {
                "obj": obj,
                "model_id": ids.next(),
                "geom_id": ids.next(),
                "mat_id": ids.next(),
            }
        )

    lines: List[str] = []
    lines.append('; FBX 7.4.0 project file')
    lines.append('FBXHeaderExtension:  {')
    lines.append('  FBXHeaderVersion: 1003')
    lines.append('  FBXVersion: 7400')
    lines.append('  Creator: "kml-to-fbx"')
    lines.append('}')
    lines.append('GlobalSettings:  {')
    lines.append('  Version: 1000')
    lines.append('  Properties70:  {')
    lines.append('    P: "UpAxis", "int", "Integer", "",1')
    lines.append('    P: "UpAxisSign", "int", "Integer", "",1')
    lines.append('    P: "FrontAxis", "int", "Integer", "",2')
    lines.append('    P: "FrontAxisSign", "int", "Integer", "",1')
    lines.append('    P: "CoordAxis", "int", "Integer", "",0')
    lines.append('    P: "CoordAxisSign", "int", "Integer", "",1')
    lines.append('    P: "UnitScaleFactor", "double", "Number", "",1')
    lines.append('  }')
    lines.append('}')

    lines.append('Definitions:  {')
    lines.append('  Version: 100')
    lines.append(f'  Count: {len(enriched) * 3 + 1}')
    lines.append('  ObjectType: "Model" { Count: %d }' % (len(enriched) + 1))
    lines.append('  ObjectType: "Geometry" { Count: %d }' % len(enriched))
    lines.append('  ObjectType: "Material" { Count: %d }' % len(enriched))
    lines.append('}')

    lines.append('Objects:  {')
    lines.append(f'  Model: {root_model_id}, "Model::RootNode", "Null" {{')
    lines.append('    Version: 232')
    lines.append('    Properties70:  {')
    lines.append('      P: "Lcl Translation", "Lcl Translation", "", "A",0,0,0')
    lines.append('      P: "Lcl Rotation", "Lcl Rotation", "", "A",0,0,0')
    lines.append('      P: "Lcl Scaling", "Lcl Scaling", "", "A",1,1,1')
    lines.append('    }')
    lines.append('  }')

    for item in enriched:
        obj: FbxMeshObject = item["obj"]
        name = _q(obj.name)

        vtx = _block_vertices(obj.mesh.vertices)
        pidx = _block_ints(_polygon_index_stream(obj.mesh.triangles))
        normals = _block_floats(_polygon_vertex_normals(obj.mesh.vertices, obj.mesh.triangles))
        per_poly_material = _block_ints([0] * len(obj.mesh.triangles))

        lines.append(f'  Geometry: {item["geom_id"]}, "Geometry::{name}", "Mesh" {{')
        lines.append('    GeometryVersion: 124')
        lines.append('    Vertices: *%d {' % (len(obj.mesh.vertices) * 3))
        lines.append(f'      a: {vtx}')
        lines.append('    }')
        lines.append('    PolygonVertexIndex: *%d {' % (len(obj.mesh.triangles) * 3))
        lines.append(f'      a: {pidx}')
        lines.append('    }')
        lines.append('    LayerElementNormal: 0 {')
        lines.append('      Version: 101')
        lines.append('      Name: ""')
        lines.append('      MappingInformationType: "ByPolygonVertex"')
        lines.append('      ReferenceInformationType: "Direct"')
        lines.append(f'      Normals: *{len(obj.mesh.triangles) * 9} {{')
        lines.append(f'        a: {normals}')
        lines.append('      }')
        lines.append('    }')
        lines.append('    LayerElementMaterial: 0 {')
        lines.append('      Version: 101')
        lines.append('      Name: ""')
        lines.append('      MappingInformationType: "ByPolygon"')
        lines.append('      ReferenceInformationType: "IndexToDirect"')
        lines.append(f'      Materials: *{len(obj.mesh.triangles)} {{')
        lines.append(f'        a: {per_poly_material}')
        lines.append('      }')
        lines.append('    }')
        lines.append('    Layer: 0 {')
        lines.append('      Version: 100')
        lines.append('      LayerElement:  {')
        lines.append('        Type: "LayerElementNormal"')
        lines.append('        TypedIndex: 0')
        lines.append('      }')
        lines.append('      LayerElement:  {')
        lines.append('        Type: "LayerElementMaterial"')
        lines.append('        TypedIndex: 0')
        lines.append('      }')
        lines.append('    }')
        lines.append('  }')

        lines.append(f'  Model: {item["model_id"]}, "Model::{name}", "Mesh" {{')
        lines.append('    Version: 232')
        lines.append('    Properties70:  {')
        lines.append('      P: "Lcl Translation", "Lcl Translation", "", "A",0,0,0')
        lines.append('      P: "Lcl Rotation", "Lcl Rotation", "", "A",0,0,0')
        lines.append('      P: "Lcl Scaling", "Lcl Scaling", "", "A",1,1,1')
        lines.append('    }')
        lines.append('    Shading: T')
        lines.append('    Culling: "CullingOff"')
        lines.append('  }')

        r, g, b, a = obj.rgba
        lines.append(f'  Material: {item["mat_id"]}, "Material::MAT_{name}", "" {{')
        lines.append('    Version: 102')
        lines.append('    ShadingModel: "phong"')
        lines.append('    MultiLayer: 0')
        lines.append('    Properties70:  {')
        lines.append('      P: "DiffuseColor", "Color", "", "A",%s,%s,%s' % (_fmt_float(r), _fmt_float(g), _fmt_float(b)))
        lines.append('      P: "TransparencyFactor", "Number", "", "A",%s' % _fmt_float(1.0 - a))
        lines.append('    }')
        lines.append('  }')

    lines.append('}')

    lines.append('Connections:  {')
    for item in enriched:
        lines.append(f'  C: "OO",{item["geom_id"]},{item["model_id"]}')
        lines.append(f'  C: "OO",{item["mat_id"]},{item["model_id"]}')
        lines.append(f'  C: "OO",{item["model_id"]},{root_model_id}')
    lines.append(f'  C: "OO",{root_model_id},0')
    lines.append('}')
    lines.append('Takes:  {')
    lines.append('  Current: ""')
    lines.append('}')

    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
        f.write('\n')
