from __future__ import annotations

import os
import sys


def _extract_args(argv: list[str]) -> list[str]:
    if "--" in argv:
        return argv[argv.index("--") + 1 :]
    return argv[1:]


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv
    args = _extract_args(argv)
    if len(args) < 2:
        print("Usage: blender --background --python blender_obj_to_fbx.py -- <input.obj> <output.fbx>")
        return 2

    input_obj = args[0]
    output_fbx = args[1]

    import bpy  # type: ignore

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    bpy.ops.wm.obj_import(filepath=input_obj)

    # Make shading predictable in strict viewers.
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH":
            for p in obj.data.polygons:
                p.use_smooth = False

    os.makedirs(os.path.dirname(output_fbx) or ".", exist_ok=True)
    bpy.ops.export_scene.fbx(
        filepath=output_fbx,
        use_selection=False,
        add_leaf_bones=False,
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_UNITS",
        mesh_smooth_type="FACE",
        path_mode="AUTO",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
