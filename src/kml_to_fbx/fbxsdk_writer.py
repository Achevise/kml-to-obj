from __future__ import annotations

import os
import platform
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, Tuple

from .mesh_builder import MeshData


RGBAlpha = Tuple[float, float, float, float]


@dataclass
class FbxSdkMeshObject:
    name: str
    mesh: MeshData
    rgba: RGBAlpha
    material_key: str = ""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _safe_name(value: str) -> str:
    s = "".join(ch if (ch.isalnum() or ch in "._-") else "_" for ch in value.strip())
    s = s.strip("._")
    return s or "unnamed"


def _default_sdk_root() -> str:
    env = os.environ.get("FBXSDK_ROOT", "").strip()
    if env:
        return env
    repo = _repo_root()
    sysname = platform.system().lower()
    if sysname == "darwin":
        return str(repo / "tools" / "fbxsdk" / "pkg_expanded" / "Root.pkg" / "Payload" / "Applications" / "Autodesk" / "FBX SDK" / "2020.3.9")
    if sysname == "windows":
        return r"C:\Program Files\Autodesk\FBX\FBX SDK\2020.3.9"
    return str(repo / "tools" / "fbxsdk" / "sdk")


def _default_exporter_bin() -> str:
    exe = "fbxsdk_exporter.exe" if platform.system().lower() == "windows" else "fbxsdk_exporter"
    return str(_repo_root() / "tools" / "fbxsdk" / "bin" / exe)


def _find_first_existing(paths: Sequence[Path]) -> str | None:
    for p in paths:
        if p.exists():
            return str(p)
    return None


def _resolve_lib_dir(sdk_root: str) -> str:
    root = Path(sdk_root)
    sysname = platform.system().lower()
    if sysname == "darwin":
        candidates = [root / "lib" / "clang" / "release", root / "lib"]
    elif sysname == "windows":
        candidates = [
            root / "lib" / "vs2022" / "x64" / "release",
            root / "lib" / "vs2019" / "x64" / "release",
            root / "lib" / "vs2017" / "x64" / "release",
            root / "lib" / "vs2015" / "x64" / "release",
            root / "lib",
        ]
    else:
        candidates = [
            root / "lib" / "gcc" / "x64" / "release",
            root / "lib" / "gcc" / "release",
            root / "lib",
        ]
    found = _find_first_existing(candidates)
    if not found:
        raise RuntimeError(
            "FBX SDK libs not found. Set --fbxsdk-root/FBXSDK_ROOT to a valid Autodesk FBX SDK installation."
        )
    return found


def ensure_fbxsdk_exporter(exporter_bin: str | None = None, sdk_root: str | None = None) -> str:
    exporter_bin = exporter_bin or _default_exporter_bin()
    sdk_root = sdk_root or _default_sdk_root()

    src_cpp = str(_repo_root() / "tools" / "fbxsdk" / "src" / "fbxsdk_exporter.cpp")
    include_dir = os.path.join(sdk_root, "include")
    lib_dir = _resolve_lib_dir(sdk_root)

    if not os.path.exists(src_cpp):
        raise RuntimeError(f"FBX SDK exporter source not found: {src_cpp}")
    if not os.path.exists(include_dir):
        raise RuntimeError(
            "FBX SDK headers/libs not found. Set --fbxsdk-root to your extracted Autodesk FBX SDK path."
        )

    os.makedirs(os.path.dirname(exporter_bin), exist_ok=True)
    if os.path.exists(exporter_bin) and os.path.getmtime(exporter_bin) >= os.path.getmtime(src_cpp):
        return exporter_bin

    sysname = platform.system().lower()
    if sysname == "windows":
        raise RuntimeError(
            "Auto-build for fbxsdk_exporter is not implemented on Windows. "
            "Build tools/fbxsdk/src/fbxsdk_exporter.cpp with your FBX SDK and pass --fbxsdk-exporter-bin."
        )

    cmd = [
        "clang++",
        "-std=c++17",
        "-O2",
        f"-I{include_dir}",
        src_cpp,
        f"-L{lib_dir}",
        "-lfbxsdk",
        "-lz",
        "-o",
        exporter_bin,
    ]
    if sysname == "darwin":
        cmd.append("-liconv")
    cmd.append(f"-Wl,-rpath,{lib_dir}")
    subprocess.run(cmd, check=True)
    return exporter_bin


def _write_mesh_input(path: str, objects: Sequence[FbxSdkMeshObject]) -> None:
    used: dict[str, int] = {}
    with open(path, "w", encoding="utf-8") as f:
        for obj in objects:
            if not obj.mesh.vertices or not obj.mesh.triangles:
                continue
            base_name = _safe_name(obj.name)
            idx = used.get(base_name, 0) + 1
            used[base_name] = idx
            out_name = base_name if idx == 1 else f"{base_name}_{idx}"
            f.write(f"o {out_name}\n")
            mat_key = _safe_name(obj.material_key or out_name)
            f.write(f"m {mat_key}\n")
            r, g, b, a = obj.rgba
            f.write(f"c {r:.9f} {g:.9f} {b:.9f} {a:.9f}\n")
            f.write(f"v {len(obj.mesh.vertices)}\n")
            for x, y, z in obj.mesh.vertices:
                f.write(f"{x:.9f} {y:.9f} {z:.9f}\n")
            f.write(f"f {len(obj.mesh.triangles)}\n")
            for i, j, k in obj.mesh.triangles:
                f.write(f"{i} {j} {k}\n")


def export_with_fbxsdk(
    output_fbx_path: str,
    objects: Sequence[FbxSdkMeshObject],
    exporter_bin: str | None = None,
    sdk_root: str | None = None,
) -> None:
    sdk_root = sdk_root or _default_sdk_root()
    exporter = ensure_fbxsdk_exporter(exporter_bin=exporter_bin, sdk_root=sdk_root)

    valid = [o for o in objects if o.mesh.vertices and o.mesh.triangles]
    if not valid:
        raise RuntimeError("No valid meshes to export")

    with tempfile.TemporaryDirectory(prefix="k2f_fbxsdk_") as tmpdir:
        mesh_in = os.path.join(tmpdir, "scene.mesh")
        _write_mesh_input(mesh_in, valid)
        env = os.environ.copy()
        lib_dir = _resolve_lib_dir(sdk_root)
        sysname = platform.system().lower()
        if sysname == "darwin":
            cur = env.get("DYLD_LIBRARY_PATH", "")
            env["DYLD_LIBRARY_PATH"] = f"{lib_dir}:{cur}" if cur else lib_dir
        elif sysname == "linux":
            cur = env.get("LD_LIBRARY_PATH", "")
            env["LD_LIBRARY_PATH"] = f"{lib_dir}:{cur}" if cur else lib_dir
        elif sysname == "windows":
            bin_dir = str(Path(sdk_root) / "bin")
            cur = env.get("PATH", "")
            env["PATH"] = os.pathsep.join([lib_dir, bin_dir, cur]) if cur else os.pathsep.join([lib_dir, bin_dir])
        subprocess.run([exporter, mesh_in, output_fbx_path], check=True, env=env)
