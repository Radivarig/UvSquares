#    <Uv Squares, Blender addon for reshaping UV vertices to grid.>
#    Copyright (C) <2018> <Reslav Hollos>
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
    "version": (1, 5, 0),
    "blender": (2, 80, 0),
    "category": "Mesh",
    #"location": "UV Image Editor > UVs > UVs to grid of squares",
    #"warning": "",
    "wiki_url": "http://wiki.blender.org/index.php/Extensions:2.6/Py/Scripts/UV/Uv_Squares"
    }


def register():
    bpy.utils.register_class(UV_OT_UvSquaresPanel)
    bpy.utils.register_class(UV_OT_UvSquares)
    bpy.utils.register_class(UV_OT_UvSquaresByShape)
    bpy.utils.register_class(UV_OT_RipFaces)
    bpy.utils.register_class(UV_OT_JoinFaces)
    bpy.utils.register_class(UV_OT_SnapToAxis)
    bpy.utils.register_class(UV_OT_SnapToAxisWithEqual)

    #menu
    bpy.types.IMAGE_MT_uvs.append(menu_func_uv_squares)
    bpy.types.IMAGE_MT_uvs.append(menu_func_uv_squares_by_shape)
    bpy.types.IMAGE_MT_uvs.append(menu_func_face_rip)
    bpy.types.IMAGE_MT_uvs.append(menu_func_face_join)

    #handle the keymap
    wm = bpy.context.window_manager

    km = wm.keyconfigs.addon.keymaps.new(name='UV Editor', space_type='EMPTY')
    kmi = km.keymap_items.new(UV_OT_UvSquaresByShape.bl_idname, 'E', 'PRESS', alt=True)
    addon_keymaps.append((km, kmi))

    km = wm.keyconfigs.addon.keymaps.new(name='UV Editor', space_type='EMPTY')
    kmi = km.keymap_items.new(UV_OT_RipFaces.bl_idname, 'V', 'PRESS', alt=True)
    addon_keymaps.append((km, kmi))

    km = wm.keyconfigs.addon.keymaps.new(name='UV Editor', space_type='EMPTY')
    kmi = km.keymap_items.new(UV_OT_JoinFaces.bl_idname, 'V', 'PRESS', alt=True, shift=True)
    addon_keymaps.append((km, kmi))


def unregister():
    bpy.utils.unregister_class(UV_OT_UvSquaresPanel)
    bpy.utils.unregister_class(UV_OT_UvSquares)
    bpy.utils.unregister_class(UV_OT_UvSquaresByShape)
    bpy.utils.unregister_class(UV_OT_RipFaces)
    bpy.utils.unregister_class(UV_OT_JoinFaces)
    bpy.utils.unregister_class(UV_OT_SnapToAxis)
    bpy.utils.unregister_class(UV_OT_SnapToAxisWithEqual)

    bpy.types.IMAGE_MT_uvs.remove(menu_func_uv_squares)
    bpy.types.IMAGE_MT_uvs.remove(menu_func_uv_squares_by_shape)
    bpy.types.IMAGE_MT_uvs.remove(menu_func_face_rip)
    bpy.types.IMAGE_MT_uvs.remove(menu_func_face_join)

    # handle the keymap
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    # clear the list
    addon_keymaps.clear()
