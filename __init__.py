#    <Uv Squares, Blender addon for reshaping UV vertices to grid.>
#    Copyright (C) <2019> <Reslav Hollos>
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>.

import bpy
from .uv_squares import *

bl_info = {
    "name": "UV Squares",
    "description": "UV Editor tool for reshaping selection to grid.",
    "author": "Reslav Hollos",
    "version": (1, 8, 2),
    "blender": (2, 80, 0),
    "category": "Mesh",
    "wiki_url": "http://wiki.blender.org/index.php/Extensions:2.6/Py/Scripts/UV/Uv_Squares"
}

class UV_PT_UvSquares(bpy.types.Operator):
    """Reshapes UV faces to a grid of equivalent squares"""
    bl_idname = "uv.uv_squares"
    bl_label = "UVs to grid of squares"
    bl_options = {'REGISTER', 'UNDO'}
    @classmethod
    def poll(cls, context):
        return (context.mode == 'EDIT_MESH')

    def execute(self, context):
        main(context, self, True)
        return {'FINISHED'}

class UV_PT_UvSquaresByShape(bpy.types.Operator):
    """Reshapes UV faces to a grid with respect to shape by length of edges around selected corner"""
    bl_idname = "uv.uv_squares_by_shape"
    bl_label = "UVs to grid with respect to shape"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.mode == 'EDIT_MESH')

    def execute(self, context):
        main(context, self)
        return {'FINISHED'}

class UV_PT_RipFaces(bpy.types.Operator):
    """Rip UV faces apart"""
    bl_idname = "uv.uv_face_rip"
    bl_label = "UV face rip"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.mode == 'EDIT_MESH')

    def execute(self, context):
        RipUvFaces(context, self)
        return {'FINISHED'}

class UV_PT_JoinFaces(bpy.types.Operator):
    """Join selected UV faces to closest nonselected vertices"""
    bl_idname = "uv.uv_face_join"
    bl_label = "UV face join"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.mode == 'EDIT_MESH')

    def execute(self, context):
        JoinUvFaces(context, self)
        return {'FINISHED'}

class UV_PT_SnapToAxis(bpy.types.Operator):
    """Snap sequenced vertices to Axis"""
    bl_idname = "uv.uv_snap_to_axis"
    bl_label = "UV snap vertices to axis"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.mode == 'EDIT_MESH')

    def execute(self, context):
        main(context, self)
        return {'FINISHED'}

class UV_PT_SnapToAxisWithEqual(bpy.types.Operator):
    """Snap sequenced vertices to Axis with Equal Distance between"""
    bl_idname = "uv.uv_snap_to_axis_and_equal"
    bl_label = "UV snap vertices to axis with equal distance between"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.mode == 'EDIT_MESH')

    def execute(self, context):
        main(context, self)
        main(context, self)
        return {'FINISHED'}

addon_keymaps = []

def menu_func_uv_squares(self, context): self.layout.operator(UV_PT_UvSquares.bl_idname)
def menu_func_uv_squares_by_shape(self, context): self.layout.operator(UV_PT_UvSquaresByShape.bl_idname)
def menu_func_face_rip(self, context): self.layout.operator(UV_PT_RipFaces.bl_idname)
def menu_func_face_join(self, context): self.layout.operator(UV_PT_JoinFaces.bl_idname)

class UV_PT_UvSquaresPanel(bpy.types.Panel):
    """UvSquares Panel"""
    bl_label = "UV Squares"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'TOOLS'

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.label(text="Select Sequenced Vertices to:")
        split = layout.split()
        col = split.column(align=True)
        col.operator(UV_PT_SnapToAxis.bl_idname, text="Snap to Axis (X or Y)", icon = "ARROW_LEFTRIGHT")
        col.operator(UV_PT_SnapToAxisWithEqual.bl_idname, text="Snap with Equal Distance", icon = "KEY_DEHLT")

        row = layout.row()
        row.label(text="Convert \"Rectangle\" (4 corners):")
        split = layout.split()
        col = split.column(align=True)
        col.operator(UV_PT_UvSquaresByShape.bl_idname, text="To Grid By Shape", icon = "GRID")
        col.operator(UV_PT_UvSquares.bl_idname, text="To Square Grid", icon = "UV_FACESEL")

        split = layout.split()
        col = split.column(align=True)
        row = col.row(align=True)

        row = layout.row()

        row.label(text="Select Faces or Vertices to:")
        split = layout.split()
        col = split.column(align=True)
        row = col.row(align=True)

        row.operator(UV_PT_RipFaces.bl_idname, text="Rip Vertex", icon = "LAYER_ACTIVE")
        row.operator(UV_PT_RipFaces.bl_idname, text="Rip Faces", icon = "UV_ISLANDSEL")
        col.operator(UV_PT_JoinFaces.bl_idname, text="Snap to Closest Unselected", icon = "SNAP_GRID")
        row = layout.row()
        row.label(text="V - Join (Stitch), I -Toggle Islands")

def register():
    bpy.utils.register_class(UV_PT_UvSquaresPanel)
    bpy.utils.register_class(UV_PT_UvSquares)
    bpy.utils.register_class(UV_PT_UvSquaresByShape)
    bpy.utils.register_class(UV_PT_RipFaces)
    bpy.utils.register_class(UV_PT_JoinFaces)
    bpy.utils.register_class(UV_PT_SnapToAxis)
    bpy.utils.register_class(UV_PT_SnapToAxisWithEqual)

    #menu
    bpy.types.IMAGE_MT_uvs.append(menu_func_uv_squares)
    bpy.types.IMAGE_MT_uvs.append(menu_func_uv_squares_by_shape)
    bpy.types.IMAGE_MT_uvs.append(menu_func_face_rip)
    bpy.types.IMAGE_MT_uvs.append(menu_func_face_join)

    #handle the keymap
    wm = bpy.context.window_manager

    km = wm.keyconfigs.addon.keymaps.new(name='UV Editor', space_type='EMPTY')
    kmi = km.keymap_items.new(UV_PT_UvSquaresByShape.bl_idname, 'E', 'PRESS', alt=True)
    addon_keymaps.append((km, kmi))

    km = wm.keyconfigs.addon.keymaps.new(name='UV Editor', space_type='EMPTY')
    kmi = km.keymap_items.new(UV_PT_RipFaces.bl_idname, 'V', 'PRESS', alt=True)
    addon_keymaps.append((km, kmi))

    km = wm.keyconfigs.addon.keymaps.new(name='UV Editor', space_type='EMPTY')
    kmi = km.keymap_items.new(UV_PT_JoinFaces.bl_idname, 'V', 'PRESS', alt=True, shift=True)
    addon_keymaps.append((km, kmi))

def unregister():
    bpy.utils.unregister_class(UV_PT_UvSquaresPanel)
    bpy.utils.unregister_class(UV_PT_UvSquares)
    bpy.utils.unregister_class(UV_PT_UvSquaresByShape)
    bpy.utils.unregister_class(UV_PT_RipFaces)
    bpy.utils.unregister_class(UV_PT_JoinFaces)
    bpy.utils.unregister_class(UV_PT_SnapToAxis)
    bpy.utils.unregister_class(UV_PT_SnapToAxisWithEqual)

    bpy.types.IMAGE_MT_uvs.remove(menu_func_uv_squares)
    bpy.types.IMAGE_MT_uvs.remove(menu_func_uv_squares_by_shape)
    bpy.types.IMAGE_MT_uvs.remove(menu_func_face_rip)
    bpy.types.IMAGE_MT_uvs.remove(menu_func_face_join)

    # handle the keymap
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    # clear the list
    addon_keymaps.clear()

if __name__ == "__main__":
    register()
