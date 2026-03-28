"""
Chạy trong Blender: Scripting workspace → Open → chọn file này → Run Script.

Điều kiện:
- Nên mở lại file .blend TRƯỚC khi bị "Separate Loose" (hoặc File → Revert).
- Mesh owlbear là MỘT object (vd. Mesh_0), chưa tách 656 mảnh.

Bước 1 (khuyên dùng — xóa đế tròn tay cho chắc):
  Edit Mode → chọn 1 mặt trên mặt đế → Ctrl+L (Select Linked) → X → Faces.
  Nếu nó chọn cả chân, chọn mặt khác trên đế hoặc tách nhỏ vùng.

Bước 2: Chạy script này để orbit + nhún (và xóa đế heuristic nếu bật flag bên dưới).
"""
from __future__ import annotations

import math

import bpy
import bmesh
from mathutils import Vector

# Đặt True nếu muốn thử xóa đế tự động (heuristic — có thể cần chỉnh slab)
AUTO_DELETE_BASE_DISC = False
# Nếu None: tự chọn mesh có nhiều đỉnh nhất (bỏ qua Cube mặc định)
MESH_NAME: str | None = None
RADIUS = 2.0
LOOP_FRAMES = 120


def _world_bbox_z(obj: bpy.types.Object) -> tuple[float, float]:
    zs = []
    for corner in obj.bound_box:
        zs.append((obj.matrix_world @ Vector(corner)).z)
    return min(zs), max(zs)


def delete_flat_base_heuristic(obj: bpy.types.Object) -> int:
    """Xóa các mặt ở lớp đáy rất mỏng (đế tròn). Trả về số mặt đã xóa."""
    zmin, zmax = _world_bbox_z(obj)
    h = max(zmax - zmin, 1e-6)
    # Mặt đỉnh của đế thường nằm trong ~1.5% chiều cao từ đáy; mặt hướng lên trên
    slab = zmin + 0.015 * h
    mw = obj.matrix_world
    wi = mw.inverted().to_3x3()

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()

    to_delete = []
    for f in bm.faces:
        center = Vector((0.0, 0.0, 0.0))
        for v in f.verts:
            center += v.co
        center /= len(f.verts)
        wcenter = mw @ center
        wn = (mw.to_3x3() @ f.normal).normalized()
        # Đế: gần đáy, pháp tuyến gần +Z (mặt trên của đế), diện tích đủ lớn
        if wcenter.z > slab + 0.002 * h:
            continue
        if wn.z < 0.35:
            continue
        if f.calc_area() < 1e-6:
            continue
        to_delete.append(f)

    if not to_delete:
        bm.free()
        return 0

    bmesh.ops.delete(bm, geom=to_delete, context="FACES")
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()
    return len(to_delete)


def ensure_orbit_and_animate(mesh: bpy.types.Object) -> None:
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = LOOP_FRAMES

    for name in ("Owlbear_Orbit", "Owlbear_Offset"):
        o = bpy.data.objects.get(name)
        if o:
            bpy.data.objects.remove(o, do_unlink=True)

    orbit = bpy.data.objects.new("Owlbear_Orbit", None)
    offset = bpy.data.objects.new("Owlbear_Offset", None)
    col = bpy.context.collection
    col.objects.link(orbit)
    col.objects.link(offset)
    offset.parent = orbit
    offset.location = (RADIUS, 0.0, 0.0)

    mw = mesh.matrix_world.copy()
    mesh.parent = offset
    mesh.matrix_world = mw

    for obj in (mesh, orbit, offset):
        if obj.animation_data:
            obj.animation_data_clear()

    orbit.rotation_mode = "XYZ"
    orbit.rotation_euler = (0.0, 0.0, 0.0)
    orbit.keyframe_insert(data_path="rotation_euler", frame=1, index=-1)
    orbit.rotation_euler = (0.0, 0.0, math.tau)
    orbit.keyframe_insert(data_path="rotation_euler", frame=LOOP_FRAMES + 1, index=-1)

    for f in range(1, LOOP_FRAMES + 1):
        t = (f - 1) / LOOP_FRAMES
        bob = 0.08 * abs(math.sin(t * math.tau * 2.0))
        tilt_x = 0.06 * math.sin(t * math.tau * 2.0)
        tilt_y = 0.03 * math.sin(t * math.tau * 2.0 + 0.5)
        mesh.location = Vector((0.0, 0.0, bob))
        mesh.rotation_euler = (tilt_x, tilt_y, 0.0)
        mesh.keyframe_insert(data_path="location", frame=f, index=-1)
        mesh.keyframe_insert(data_path="rotation_euler", frame=f, index=-1)

    scene.frame_set(1)


def pick_main_mesh() -> bpy.types.Object:
    """Ưu tiên MESH_NAME nếu set; không thì chọn mesh lớn nhất (theo số đỉnh), bỏ Cube."""
    if MESH_NAME:
        o = bpy.data.objects.get(MESH_NAME)
        if o and o.type == "MESH":
            return o
    candidates: list[bpy.types.Object] = []
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        if o.name == "Cube":
            continue
        candidates.append(o)
    if not candidates:
        raise RuntimeError("Không có mesh nào (ngoài Cube). Import model hoặc đổi MESH_NAME.")
    return max(candidates, key=lambda o: len(o.data.vertices))


def main() -> None:
    cube = bpy.data.objects.get("Cube")
    if cube:
        cube.hide_viewport = True
        cube.hide_render = True

    mesh = pick_main_mesh()

    if AUTO_DELETE_BASE_DISC:
        n = delete_flat_base_heuristic(mesh)
        print(f"Đã thử xóa đế (heuristic): {n} mặt.")

    ensure_orbit_and_animate(mesh)
    print("Xong: orbit + nhún trên", mesh.name, "— Space để xem timeline.")


if __name__ == "__main__":
    main()
