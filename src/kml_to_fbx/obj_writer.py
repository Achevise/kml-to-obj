from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

from .mesh_builder import MeshData


RGBAlpha = Tuple[float, float, float, float]


@dataclass
class ObjMeshObject:
    name: str
    mesh: MeshData
    rgba: RGBAlpha
    material_key: str = ""


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
        return (0.0, 1.0, 0.0)
    return (v[0] / n, v[1] / n, v[2] / n)


def _safe_name(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name.strip())
    return cleaned or "Object"


def write_obj_with_mtl(
    obj_path: str,
    mtl_path: str,
    objects: Sequence[ObjMeshObject],
    double_sided: bool = False,
    include_materials: bool = True,
    material_mode: str = "per-shape",
) -> None:
    valid: List[ObjMeshObject] = [o for o in objects if o.mesh.vertices and o.mesh.triangles]
    shared_mat_name = "MAT_SHARED"
    if material_mode not in ("per-shape", "shared", "source"):
        raise ValueError(f"Unsupported material_mode: {material_mode}")

    if include_materials:
        with open(mtl_path, "w", encoding="utf-8") as mtl:
            if material_mode == "shared":
                if valid:
                    r, g, b, _a = valid[0].rgba
                else:
                    r, g, b = 0.7, 0.7, 0.7
                mtl.write(f"newmtl {shared_mat_name}\n")
                mtl.write(f"Kd {r:.6f} {g:.6f} {b:.6f}\n")
                mtl.write("illum 1\n\n")
            else:
                written = set()
                for obj in valid:
                    key = obj.material_key if material_mode == "source" else obj.name
                    mat_name = f"MAT_{_safe_name(key)}"
                    if mat_name in written:
                        continue
                    written.add(mat_name)
                    r, g, b, _a = obj.rgba
                    mtl.write(f"newmtl {mat_name}\n")
                    # Keep MTL minimal to avoid ambiguous transparency mappings in FBX converters/viewers.
                    mtl.write(f"Kd {r:.6f} {g:.6f} {b:.6f}\n")
                    mtl.write("illum 1\n\n")

    with open(obj_path, "w", encoding="utf-8") as objf:
        if include_materials:
            objf.write(f"mtllib {mtl_path.split('/')[-1]}\n")

        vertex_offset = 1
        normal_offset = 1
        for obj in valid:
            obj_name = _safe_name(obj.name)
            if material_mode == "shared":
                mat_name = shared_mat_name
            elif material_mode == "source":
                mat_name = f"MAT_{_safe_name(obj.material_key or obj_name)}"
            else:
                mat_name = f"MAT_{obj_name}"
            objf.write(f"o {obj_name}\n")
            if include_materials:
                objf.write(f"usemtl {mat_name}\n")
            objf.write("s off\n")

            for x, y, z in obj.mesh.vertices:
                objf.write(f"v {x:.9f} {y:.9f} {z:.9f}\n")

            tri_normals: List[Tuple[float, float, float]] = []
            for i, j, k in obj.mesh.triangles:
                a = obj.mesh.vertices[i]
                b = obj.mesh.vertices[j]
                c = obj.mesh.vertices[k]
                n = _normalize(_cross(_sub(b, a), _sub(c, a)))
                tri_normals.append(n)
                if double_sided:
                    tri_normals.append((-n[0], -n[1], -n[2]))

            for nx, ny, nz in tri_normals:
                objf.write(f"vn {nx:.9f} {ny:.9f} {nz:.9f}\n")

            local_tri = 0
            for i, j, k in obj.mesh.triangles:
                a = i + vertex_offset
                b = j + vertex_offset
                c = k + vertex_offset
                nidx = normal_offset + local_tri
                objf.write(f"f {a}//{nidx} {b}//{nidx} {c}//{nidx}\n")
                local_tri += 1
                if double_sided:
                    nidx_back = normal_offset + local_tri
                    objf.write(f"f {c}//{nidx_back} {b}//{nidx_back} {a}//{nidx_back}\n")
                    local_tri += 1

            objf.write("\n")
            vertex_offset += len(obj.mesh.vertices)
            normal_offset += len(tri_normals)
