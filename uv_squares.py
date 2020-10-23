#    <Uv Squares, Blender addon for reshaping UV vertices to grid.>
#    Copyright (C) <2020> <Reslav Hollos>
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

bl_info = {
    "name": "UV Squares",
    "description": "UV Editor tool for reshaping selection to grid.",
    "author": "Reslav Hollos",
    "version": (1, 14, 0),
    "blender": (2, 80, 0),
    "location": "UV Editor > N Panel > UV Squares",
    "category": "UV",
    "wiki_url": "http://wiki.blender.org/index.php/Extensions:2.6/Py/Scripts/UV/Uv_Squares",
}

from collections import defaultdict, deque
from dataclasses import dataclass, field
from math import hypot, isclose
from operator import itemgetter
from timeit import default_timer as timer
from typing import Dict, Iterable, List, Sequence, Set, Tuple

import bmesh
import bpy
import numpy as np

precision = 3

# todo:
#   make joining radius scale with editor zoom rate or average unit length
#   align to axis by respect to vert distance
#   snap 2dCursor to closest selected vert (when more vertices are selected
#   rip different vertex on each press


def main(context, operator, square=False, snap_to_closest=False):
    if context.scene.tool_settings.use_uv_select_sync:
        operator.report({"ERROR"}, "Please disable 'Keep UV and edit mesh in sync'")
        # context.scene.tool_settings.use_uv_select_sync = False
        return

    selected_objects = context.selected_objects
    if context.edit_object not in selected_objects:
        selected_objects.append(context.edit_object)

    for obj in selected_objects:
        if obj.type == "MESH":
            main1(obj, context, operator, square, snap_to_closest)


def main1(obj, context, operator, square, snap_to_closet):
    if context.scene.tool_settings.use_uv_select_sync:
        operator.report({"ERROR"}, "Please disable 'Keep UV and edit mesh in sync'")
        # context.scene.tool_settings.use_uv_select_sync = False
        return

    start_time = timer()
    me = obj.data
    bm = bmesh.from_edit_mesh(me)
    uv_layer = bm.loops.layers.uv.verify()
    # bm.faces.layers.tex.verify()  # currently blender needs both layers.

    (
        edge_verts,
        fitered_verts,
        sel_faces,
        non_quad_faces,
        verts_dict,
        no_edge,
    ) = lists_of_verts(uv_layer, bm)

    if len(fitered_verts) == 0:
        return
    if len(fitered_verts) == 1:
        snap_cursor_to_closest_selected(fitered_verts)
        return

    closest_vert_to_cursor = cursor_closest_to(fitered_verts)
    # line is selected

    if len(sel_faces) == 0:
        if snap_to_closet:
            snap_cursor_to_closest_selected(fitered_verts)
            return

        verts_dict_for_line(uv_layer, bm, fitered_verts, verts_dict)

        if not are_vects_lined_on_axis(fitered_verts):
            scale_to_0_on_axis_and_cursor(
                fitered_verts, verts_dict, closest_vert_to_cursor
            )
            return success_finished(me, start_time)

        make_equal_distance_between_verts_in_line(
            fitered_verts, verts_dict, closest_vert_to_cursor
        )
        return success_finished(me, start_time)

    # deselect non quads
    for nf in non_quad_faces:
        for l in nf.loops:
            luv = l[uv_layer]
            luv.select = False

    def is_face_selected(f):
        return f.select and all(l[uv_layer].select for l in f.loops)

    def get_island_from_face(start_face):
        island = set()
        to_check = set([start_face])

        while to_check:
            face = to_check.pop()
            if is_face_selected(face) and face not in island:
                island.add(face)
                adjacent_faces = []
                for e in face.edges:
                    if not e.seam:
                        for f in e.link_faces:
                            if f is not face:
                                adjacent_faces.append(f)
                to_check.update(adjacent_faces)

        return island

    def get_islands_from_selected_faces(selected_faces):
        islands = []
        to_check = set(selected_faces)
        while to_check:
            face = to_check.pop()
            island = get_island_from_face(face)
            islands.append(island)
            to_check.difference_update(island)
        return islands

    islands = get_islands_from_selected_faces(sel_faces)

    def main2(target_face, faces):
        shape_face(uv_layer, operator, target_face, verts_dict, square)

        if square:
            follow_active_uv(operator, me, target_face, faces, "EVEN")
        else:
            follow_active_uv(operator, me, target_face, faces)

    for island in islands:
        target_face = bm.faces.active
        if (
            (target_face is None)
            or (target_face not in island)
            or (len(islands) > 1)
            or (not target_face.select)
            or (len(target_face.verts) != 4)
        ):
            target_face = next(iter(island))

        main2(target_face, island)

    if not no_edge:
        # edge has ripped so we connect it back
        for ev in edge_verts:
            key = (round(ev.uv.x, precision), round(ev.uv.y, precision))
            if key in verts_dict:
                ev.uv = verts_dict[key][0].uv
                ev.select = True

    return success_finished(me, start_time)


def shape_face(uv_layer, operator, target_face, verts_dict, square):
    corners = []
    for l in target_face.loops:
        luv = l[uv_layer]
        corners.append(luv)

    if len(corners) != 4:
        # operator.report({'ERROR'}, "bla")
        return

    lucv, ldcv, rucv, rdcv = get_corners(corners)

    cct = cursor_closest_to([lucv, ldcv, rdcv, rucv])
    make_uv_face_equal_rectangle(verts_dict, lucv, rucv, rdcv, ldcv, cct, square)


def make_uv_face_equal_rectangle(
    verts_dict, lucv, rucv, rdcv, ldcv, startv, square=False
):
    size_x, size_y = get_image_size()
    ratio = size_x / size_y

    if startv is None:
        startv = lucv.uv
    elif are_verts_quasi_equal(startv, rucv):
        startv = rucv.uv
    elif are_verts_quasi_equal(startv, rdcv):
        startv = rdcv.uv
    elif are_verts_quasi_equal(startv, ldcv):
        startv = ldcv.uv
    else:
        startv = lucv.uv

    lucv = lucv.uv
    rucv = rucv.uv
    rdcv = rdcv.uv
    ldcv = ldcv.uv

    if startv == lucv:
        final_scale_x = hypot_vert(lucv, rucv)
        final_scale_y = hypot_vert(lucv, ldcv)
        curr_row_x = lucv.x
        curr_row_y = lucv.y

    elif startv == rucv:
        final_scale_x = hypot_vert(rucv, lucv)
        final_scale_y = hypot_vert(rucv, rdcv)
        curr_row_x = rucv.x - final_scale_x
        curr_row_y = rucv.y

    elif startv == rdcv:
        final_scale_x = hypot_vert(rdcv, ldcv)
        final_scale_y = hypot_vert(rdcv, rucv)
        curr_row_x = rdcv.x - final_scale_x
        curr_row_y = rdcv.y + final_scale_y

    else:
        final_scale_x = hypot_vert(ldcv, rdcv)
        final_scale_y = hypot_vert(ldcv, lucv)
        curr_row_x = ldcv.x
        curr_row_y = ldcv.y + final_scale_y

    if square:
        final_scale_y = final_scale_x * ratio
    # lucv, rucv
    x = round(lucv.x, precision)
    y = round(lucv.y, precision)
    for v in verts_dict[(x, y)]:
        v.uv.x = curr_row_x
        v.uv.y = curr_row_y

    x = round(rucv.x, precision)
    y = round(rucv.y, precision)
    for v in verts_dict[(x, y)]:
        v.uv.x = curr_row_x + final_scale_x
        v.uv.y = curr_row_y

    # rdcv, ldcv
    x = round(rdcv.x, precision)
    y = round(rdcv.y, precision)
    for v in verts_dict[x, y]:
        v.uv.x = curr_row_x + final_scale_x
        v.uv.y = curr_row_y - final_scale_y

    x = round(ldcv.x, precision)
    y = round(ldcv.y, precision)
    for v in verts_dict[x, y]:
        v.uv.x = curr_row_x
        v.uv.y = curr_row_y - final_scale_y


def snap_cursor_to_closest_selected(filtered_verts):
    # TODO: snap to closest selected
    if len(filtered_verts) == 1:
        set_all_2d_cursors_to(filtered_verts[0].uv.x, filtered_verts[0].uv.y)


def lists_of_verts(uv_layer, bm):
    edge_verts: List[bmesh.types.BMLoopUV] = []
    all_edge_verts: List[bmesh.types.BMLoopUV] = []
    filtered_verts: List[bmesh.types.BMLoopUV] = []
    sel_faces = []
    non_quad_faces = []
    verts_dict = defaultdict(list)

    for f in bm.faces:
        is_face_sel = True
        faces_edge_verts = []
        if not f.select:
            continue

        # collect edge verts if any
        for l in f.loops:
            luv = l[uv_layer]
            if luv.select:
                faces_edge_verts.append(luv)
            else:
                is_face_sel = False

        all_edge_verts.extend(faces_edge_verts)
        if is_face_sel:
            if len(f.verts) != 4:
                non_quad_faces.append(f)
                edge_verts.extend(faces_edge_verts)
            else:
                sel_faces.append(f)

                for l in f.loops:
                    luv = l[uv_layer]
                    x = round(luv.uv.x, precision)
                    y = round(luv.uv.y, precision)
                    verts_dict[x, y].append(luv)

        else:
            edge_verts.extend(faces_edge_verts)

    no_edge = False
    if len(edge_verts) == 0:
        no_edge = True
        edge_verts.extend(all_edge_verts)

    if len(sel_faces) == 0:
        for ev in edge_verts:
            if not list_quasi_contains_vect(filtered_verts, ev):
                filtered_verts.append(ev)
    else:
        filtered_verts = edge_verts

    return edge_verts, filtered_verts, sel_faces, non_quad_faces, verts_dict, no_edge


def list_quasi_contains_vect(vect_list, vect):
    for v in vect_list:
        if are_verts_quasi_equal(v, vect):
            return True
    return False


# modified ideasman42's uvcalc_follow_active.py
def follow_active_uv(operator, me, f_act, faces, EXTEND_MODE="LENGTH_AVERAGE"):
    bm = bmesh.from_edit_mesh(me)
    uv_act = bm.loops.layers.uv.active

    # our own local walker
    def walk_face_init(faces, f_act):
        # first tag all faces True (so we dont uvmap them)
        for f in bm.faces:
            f.tag = True
        # then tag faces arg False
        for f in faces:
            f.tag = False
        # tag the active face True since we begin there
        f_act.tag = True

    def walk_face(f):
        # all faces in this list must be tagged
        f.tag = True
        faces_a = [f]
        faces_b = []

        while faces_a:
            for f in faces_a:
                for l in f.loops:
                    l_edge = l.edge
                    if l_edge.is_manifold and not l_edge.seam:
                        l_other = l.link_loop_radial_next
                        f_other = l_other.face
                        if not f_other.tag:
                            yield f, l, f_other
                            f_other.tag = True
                            faces_b.append(f_other)
            # swap
            faces_a, faces_b = faces_b, faces_a
            faces_b.clear()

    def walk_edgeloop(l):
        """
        Could make this a generic function
        """
        e_first = l.edge
        e = None
        while True:
            e = l.edge
            yield e

            # don't step past non-manifold edges
            if e.is_manifold:
                # welk around the quad and then onto the next face
                l = l.link_loop_radial_next
                if len(l.face.verts) == 4:
                    l = l.link_loop_next.link_loop_next
                    if l.edge is e_first:
                        break
                else:
                    break
            else:
                break

    def extrapolate_uv(fac, l_a_outer, l_a_inner, l_b_outer, l_b_inner):
        l_b_inner[:] = l_a_inner
        l_b_outer[:] = l_a_inner + ((l_a_inner - l_a_outer) * fac)

    def apply_uv(f_prev, l_prev, f_next):
        l_a = [None, None, None, None]
        l_b = [None, None, None, None]

        l_a[0] = l_prev
        l_a[1] = l_a[0].link_loop_next
        l_a[2] = l_a[1].link_loop_next
        l_a[3] = l_a[2].link_loop_next

        #  l_b
        #  +-----------+
        #  |(3)        |(2)
        #  |           |
        #  |l_next(0)  |(1)
        #  +-----------+
        #        ^
        #  l_a   |
        #  +-----------+
        #  |l_prev(0)  |(1)
        #  |    (f)    |
        #  |(3)        |(2)
        #  +-----------+
        #  copy from this face to the one above.

        # get the other loops
        l_next = l_prev.link_loop_radial_next
        if l_next.vert != l_prev.vert:
            l_b[1] = l_next
            l_b[0] = l_b[1].link_loop_next
            l_b[3] = l_b[0].link_loop_next
            l_b[2] = l_b[3].link_loop_next
        else:
            l_b[0] = l_next
            l_b[1] = l_b[0].link_loop_next
            l_b[2] = l_b[1].link_loop_next
            l_b[3] = l_b[2].link_loop_next

        l_a_uv = [l[uv_act].uv for l in l_a]
        l_b_uv = [l[uv_act].uv for l in l_b]

        if EXTEND_MODE == "LENGTH_AVERAGE":
            try:
                fac = (
                    edge_lengths[l_b[2].edge.index][0]
                    / edge_lengths[l_a[1].edge.index][0]
                )
            except ZeroDivisionError:
                fac = 1.0
        elif EXTEND_MODE == "LENGTH":
            a0, b0, c0 = l_a[3].vert.co, l_a[0].vert.co, l_b[3].vert.co
            a1, b1, c1 = l_a[2].vert.co, l_a[1].vert.co, l_b[2].vert.co

            d1 = (a0 - b0).length + (a1 - b1).length
            d2 = (b0 - c0).length + (b1 - c1).length
            try:
                fac = d2 / d1
            except ZeroDivisionError:
                fac = 1.0
        else:
            fac = 1.0

        extrapolate_uv(fac, l_a_uv[3], l_a_uv[0], l_b_uv[3], l_b_uv[0])

        extrapolate_uv(fac, l_a_uv[2], l_a_uv[1], l_b_uv[2], l_b_uv[1])

    # -------------------------------------------
    # Calculate average length per loop if needed

    if EXTEND_MODE == "LENGTH_AVERAGE":
        bm.edges.index_update()
        edge_lengths = [None] * len(bm.edges)

        for f in faces:
            # we know its a quad
            l_quad = f.loops[:]
            l_pair_a = (l_quad[0], l_quad[2])
            l_pair_b = (l_quad[1], l_quad[3])

            for l_pair in (l_pair_a, l_pair_b):
                if edge_lengths[l_pair[0].edge.index] is None:

                    edge_length_store = [-1.0]
                    edge_length_accum = 0.0
                    edge_length_total = 0

                    for l in l_pair:
                        if edge_lengths[l.edge.index] is None:
                            for e in walk_edgeloop(l):
                                if edge_lengths[e.index] is None:
                                    edge_lengths[e.index] = edge_length_store
                                    edge_length_accum += e.calc_length()
                                    edge_length_total += 1

                    edge_length_store[0] = edge_length_accum / edge_length_total

    # done with average length
    # ------------------------

    walk_face_init(faces, f_act)
    for f_triple in walk_face(f_act):
        apply_uv(*f_triple)

    bmesh.update_edit_mesh(me, False)


"""----------------------------------"""


def success_finished(me, start_time):
    # use for backtrack of steps
    # bpy.ops.ed.undo_push()
    bmesh.update_edit_mesh(me)
    elapsed = round(timer() - start_time, 2)
    # if (elapsed >= 0.05): operator.report({'INFO'}, "UvSquares finished, elapsed:", elapsed, "s.")
    if elapsed >= 0.05:
        print("UvSquares finished, elapsed:", elapsed, "s.")


def are_vects_lined_on_axis(verts) -> bool:
    are_lined_x = True
    are_lined_y = True
    val_x = verts[0].uv.x
    val_y = verts[0].uv.y
    for v in verts:
        if not isclose(val_x, v.uv.x):
            are_lined_x = False
        if not isclose(val_y, v.uv.y):
            are_lined_y = False
    return are_lined_x or are_lined_y


def make_equal_distance_between_verts_in_line(filtered_verts, verts_dict, startv=None):
    verts = filtered_verts
    # sort by .x
    verts.sort(key=lambda x: x.uv[0])

    first = verts[0].uv
    last = verts[-1].uv

    horizontal = True
    if not isclose(last.x, first.x):
        slope = (last.y - first.y) / (last.x - first.x)
        if abs(slope) > 1:
            horizontal = False
    else:
        horizontal = False

    if horizontal:
        length = hypot(first.x - last.x, first.y - last.y)

        if startv is last:
            current_x = last.x - length
            current_y = last.y
        else:
            current_x = first.x
            current_y = first.y
    else:
        # sort by .y
        verts.sort(key=lambda x: x.uv[1])
        # reverse because y values drop from up to down
        verts.reverse()
        first = verts[0].uv
        last = verts[len(verts) - 1].uv
        # we have to call length here because if it is not Hor first and second can not actually be first and second
        length = hypot(first.x - last.x, first.y - last.y)

        if startv is last:
            current_x = last.x
            current_y = last.y + length

        else:
            current_x = first.x
            current_y = first.y

    number_of_verts = len(verts)
    final_scale = length / (number_of_verts - 1)

    if horizontal:
        first = verts[0]
        last = verts[-1]

        for v in verts:
            v = v.uv
            x = round(v.x, precision)
            y = round(v.y, precision)

            for vert in verts_dict[(x, y)]:
                vert.uv.x = current_x
                vert.uv.y = current_y

            current_x = current_x + final_scale
    else:
        for v in verts:
            x = round(v.uv.x, precision)
            y = round(v.uv.y, precision)

            for vert in verts_dict[(x, y)]:
                vert.uv.x = current_x
                vert.uv.y = current_y

            current_y = current_y - final_scale


def verts_dict_for_line(uv_layer, bm, sel_verts, verts_dict):
    for f in bm.faces:
        for l in f.loops:
            luv = l[uv_layer]
            if luv.select:
                x = round(luv.uv.x, precision)
                y = round(luv.uv.y, precision)

                verts_dict[x, y].append(luv)


def scale_to_0_on_axis_and_cursor(
    filtered_verts, verts_dict, startv=None, horizontal=None
):
    verts = filtered_verts
    # sort by .x
    verts.sort(key=lambda x: x.uv[0])

    first = verts[0]
    last = verts[len(verts) - 1]

    if horizontal is None:
        horizontal = True
        if not isclose(last.uv.x, first.uv.x):
            slope = (last.uv.y - first.uv.y) / (last.uv.x - first.uv.x)
            if abs(slope) > 1:
                horizontal = False
        else:
            horizontal = False

    if horizontal:
        if startv is None:
            startv = first

        set_all_2d_cursors_to(startv.uv.x, startv.uv.y)
        # scale to 0 on Y
        scale_to_0("Y")

    else:
        # sort by .y
        verts.sort(key=lambda x: x.uv[1])
        # reverse because y values drop from up to down
        verts.reverse()
        first = verts[0]
        last = verts[len(verts) - 1]
        if startv is None:
            startv = first

        set_all_2d_cursors_to(startv.uv.x, startv.uv.y)
        # scale to 0 on X
        scale_to_0("X")


def scale_to_0(axis):
    last_area = bpy.context.area.type
    bpy.context.area.type = "IMAGE_EDITOR"
    last_pivot = bpy.context.space_data.pivot_point
    bpy.context.space_data.pivot_point = "CURSOR"

    for area in bpy.context.screen.areas:
        if area.type == "IMAGE_EDITOR":
            if axis == "Y":
                bpy.ops.transform.resize(
                    value=(1, 0, 1),
                    constraint_axis=(False, True, False),
                    mirror=False,
                    proportional_edit_falloff="SMOOTH",
                    proportional_size=1,
                )
            else:
                bpy.ops.transform.resize(
                    value=(0, 1, 1),
                    constraint_axis=(True, False, False),
                    mirror=False,
                    proportional_edit_falloff="SMOOTH",
                    proportional_size=1,
                )

    bpy.context.space_data.pivot_point = last_pivot


def hypot_vert(v1, v2):
    hyp = hypot(v1.x - v2.x, v1.y - v2.y)
    return hyp


def get_corners(corners):
    first_highest = corners[0]
    for c in corners:
        if c.uv.y > first_highest.uv.y:
            first_highest = c
    corners.remove(first_highest)

    second_highest = corners[0]
    for c in corners:
        if c.uv.y > second_highest.uv.y:
            second_highest = c

    if first_highest.uv.x < second_highest.uv.x:
        left_up = first_highest
        right_up = second_highest
    else:
        left_up = second_highest
        right_up = first_highest
    corners.remove(second_highest)

    first_lowest = corners[0]
    second_lowest = corners[1]

    if first_lowest.uv.x < second_lowest.uv.x:
        left_down = first_lowest
        right_down = second_lowest
    else:
        left_down = second_lowest
        right_down = first_lowest

    return left_up, left_down, right_up, right_down


def get_image_size():
    ratio_x = ratio_y = 256
    for a in bpy.context.screen.areas:
        if a.type == "IMAGE_EDITOR":
            img = a.spaces[0].image
            if img is not None and img.size[0] != 0:
                ratio_x, ratio_y = img.size[0], img.size[1]
            break
    return ratio_x, ratio_y


def cursor_closest_to(verts):
    size_x, size_y = get_image_size()
    if bpy.app.version >= (2, 80, 0):
        size_x = size_y = 1
    min_hypot = float("inf")
    min_v = verts[0]
    for v in verts:
        if v is None:
            continue
        for area in bpy.context.screen.areas:
            if area.type == "IMAGE_EDITOR":
                loc = area.spaces[0].cursor_location
                hyp = hypot(loc.x / size_x - v.uv.x, loc.y / size_y - v.uv.y)
                if hyp < min_hypot:
                    min_hypot = hyp
                    min_v = v
    return min_v


def set_all_2d_cursors_to(x, y):
    last_area = bpy.context.area.type
    bpy.context.area.type = "IMAGE_EDITOR"

    bpy.ops.uv.cursor_set(location=(x, y))

    bpy.context.area.type = last_area


def are_verts_quasi_equal(v1, v2):
    return isclose(v1.uv.x, v2.uv.x) and isclose(v1.uv.y, v2.uv.y)


def rip_uv_faces(context, operator):
    start_time = timer()

    obj = context.active_object
    me = obj.data
    bm = bmesh.from_edit_mesh(me)

    uv_layer = bm.loops.layers.uv.verify()
    # bm.faces.layers.tex.verify()  # currently blender needs both layers.

    sel_faces = []

    for f in bm.faces:
        is_face_sel = True
        for l in f.loops:
            luv = l[uv_layer]
            if not luv.select:
                is_face_sel = False
                break

        if is_face_sel:
            sel_faces.append(f)

    if len(sel_faces) == 0:
        target = None
        for f in bm.faces:
            for l in f.loops:
                luv = l[uv_layer]
                if luv.select:
                    target = luv
                    break
            if target is not None:
                break

        for f in bm.faces:
            for l in f.loops:
                luv = l[uv_layer]
                luv.select = False

        target.select = True
        return success_finished(me, start_time)

    deselect_all()

    for sf in sel_faces:
        for l in sf.loops:
            luv = l[uv_layer]
            luv.select = True

    return success_finished(me, start_time)


def join_uv_faces(context, operator):
    start_time = timer()

    obj = context.active_object
    me = obj.data
    bm = bmesh.from_edit_mesh(me)

    uv_layer = bm.loops.layers.uv.verify()
    # bm.faces.layers.tex.verify()  # currently blender needs both layers.

    verts_dict = defaultdict(list)

    # TODO: radius by image scale
    radius = 0.002

    for f in bm.faces:
        for l in f.loops:
            luv = l[uv_layer]
            if luv.select:
                x = round(luv.uv.x, precision)
                y = round(luv.uv.y, precision)
                verts_dict[x, y].append(luv)

    for key in verts_dict:
        min_hypot = 1
        min_v = None

        for f in bm.faces:
            for l in f.loops:
                luv = l[uv_layer]
                if not luv.select:
                    hyp = hypot(
                        verts_dict[key[0], key[1]][0].uv.x - luv.uv.x,
                        verts_dict[key[0], key[1]][0].uv.y - luv.uv.y,
                    )
                    if (hyp <= min_hypot) and hyp < radius:
                        min_hypot = hyp
                        min_v = luv
                        min_v.select = True

            if min_hypot != 1:
                for v in verts_dict[(key[0], key[1])]:
                    v = v.uv
                    v.x = min_v.uv.x
                    v.y = min_v.uv.y

    return success_finished(me, start_time)


def deselect_all():
    bpy.ops.uv.select_all(action="DESELECT")


class UV_PT_UvSquares(bpy.types.Operator):
    """Reshapes UV faces to a grid of equivalent squares"""

    bl_idname = "uv.uv_squares"
    bl_label = "UVs to grid of squares"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def execute(self, context):
        main(context, self, True)
        return {"FINISHED"}


class UV_PT_UvSquaresByShape(bpy.types.Operator):
    """Reshapes UV faces to a grid with respect to shape by length of edges around selected corner"""

    bl_idname = "uv.uv_squares_by_shape"
    bl_label = "UVs to grid with respect to shape"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def execute(self, context):
        main(context, self)
        return {"FINISHED"}


class UV_PT_RipFaces(bpy.types.Operator):
    """Rip UV faces apart"""

    bl_idname = "uv.uv_face_rip"
    bl_label = "UV face rip"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def execute(self, context):
        rip_uv_faces(context, self)
        return {"FINISHED"}


class UV_PT_JoinFaces(bpy.types.Operator):
    """Join selected UV faces to closest nonselected vertices"""

    bl_idname = "uv.uv_face_join"
    bl_label = "UV face join"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def execute(self, context):
        join_uv_faces(context, self)
        return {"FINISHED"}


class UV_PT_SnapToAxis(bpy.types.Operator):
    """Snap sequenced vertices to Axis"""

    bl_idname = "uv.uv_snap_to_axis"
    bl_label = "UV snap vertices to axis"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def execute(self, context):
        main(context, self)
        return {"FINISHED"}


class UV_PT_SnapToAxisWithEqual(bpy.types.Operator):
    """Snap sequenced vertices to Axis with Equal Distance between"""

    bl_idname = "uv.uv_snap_to_axis_and_equal"
    bl_label = "UV snap vertices to axis with equal distance between"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def execute(self, context):
        main(context, self)
        # wtf, first pass aligns vertices, second pass does equal spacing
        main(context, self)
        return {"FINISHED"}


@dataclass(frozen=True)
class UvVertex:
    coordinates: Tuple[float, float]
    bm_loops: Sequence[bmesh.types.BMLoop] = field(
        default_factory=list, compare=False, repr=False
    )


class CoordinateVertexDict(dict):
    def __missing__(self, key: Tuple[float, float]):
        value = UvVertex(coordinates=key)
        self[key] = value
        return value


@dataclass
class UvVertexCollection:
    obj: bpy.types.Object
    bm: bmesh.types.BMesh
    uv_layer: bmesh.types.BMLayerItem
    vertices: Set[UvVertex] = field(default_factory=set)
    coordinate_mapping: Dict[Tuple[float, float], UvVertex] = field(
        default_factory=CoordinateVertexDict
    )
    loop_vert_mapping: Dict[bmesh.types.BMLoop, UvVertex] = field(default_factory=dict)

    @classmethod
    def populate(cls, obj):
        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.verify()

        self = cls(obj=obj, bm=bm, uv_layer=uv_layer)

        for f in bm.faces:
            if not f.select:
                continue

            for loop in f.loops:
                luv = loop[uv_layer]
                if luv.select:
                    vertex = self.coordinate_mapping[tuple(luv.uv)]
                    vertex.bm_loops.append(loop)
                    self.loop_vert_mapping[loop] = vertex

        self.vertices.update(self.coordinate_mapping.values())

        return self

    def get_selected_neighbors(self, v: UvVertex) -> Set[UvVertex]:
        # Can't be a method on the UvVertex class, since we need to use the
        # mapping from BMLoopUV objects to UvVertex instances

        # Can't just traverse links and yield UvVertex objects when we find
        # a selected BMLoopUV object, since we need to traverse all loops that
        # a vertex is part of, and we will likely encounter each UvVertex
        # more than once. Could separate this into a generator function that
        # yields duplicate UvVertex objects, and a wrapper that just calls
        # set(that_generator()), but I don't see any benefit
        selected_neighbors: Set[UvVertex] = set()
        for bml in v.bm_loops:
            loop_neighbors = [bml.link_loop_prev, bml.link_loop_next]

            for ln in loop_neighbors:
                if ln[self.uv_layer].select:
                    selected_neighbors.add(self.loop_vert_mapping[ln])

        return selected_neighbors

    def bfs_traverse(self, start: UvVertex) -> Iterable[Tuple[UvVertex, int]]:
        seen = set()
        q = deque([(start, 0)])
        while q:
            v, dist = q.popleft()
            seen.add(v)
            yield v, dist
            new_verts = self.get_selected_neighbors(v) - seen
            new_dist = dist + 1
            q.extend((new_vert, new_dist) for new_vert in new_verts)

    def sort_vertices(self) -> List[List[UvVertex]]:
        """
        Returns nested lists to support disconnected sets of vertices
        """
        if not self.vertices:
            return [[]]

        sorted_vertex_subsets = []
        unsorted_vertices = self.vertices.copy()
        while unsorted_vertices:
            arbitrary_first_vertex = next(iter(unsorted_vertices))
            first_bfs_distances = self.bfs_traverse(arbitrary_first_vertex)
            farthest = max(first_bfs_distances, key=itemgetter(1))[0]
            second_bfs_distances = self.bfs_traverse(farthest)
            # BFS traversal ensures that verts are sorted by distance already
            verts, distances = list(zip(*second_bfs_distances))
            if len(set(distances)) < len(distances):
                raise ValueError(f"Found non-linear set of {len(distances)} vertices")
            sorted_vertex_subsets.append(verts)
            unsorted_vertices -= set(verts)

        return sorted_vertex_subsets


class UV_PT_SnapToAxisPreserveDist(bpy.types.Operator):
    """Snap selected vertices to axis, preserving distance"""

    bl_idname = "uv.uv_snap_to_axis_preserve_dist"
    bl_label = "UV snap vertices to axis preserving original distances"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def execute(self, context):
        # TODO: deduplicate
        if context.scene.tool_settings.use_uv_select_sync:
            self.report({"ERROR"}, "Please disable 'Keep UV and edit mesh in sync'")
            # context.scene.tool_settings.use_uv_select_sync = False
            return

        selected_objects = context.selected_objects
        if context.edit_object not in selected_objects:
            selected_objects.append(context.edit_object)

        for obj in selected_objects:
            if obj.type == "MESH":
                try:
                    self.align(context, obj)
                except ValueError as e:
                    self.report({"ERROR"}, e.args[0])

        return {"FINISHED"}

    def align(self, context, obj):
        start_time = timer()

        vert_collection = UvVertexCollection.populate(obj)
        if not vert_collection.vertices:
            # nothing to do
            return

        sorted_vert_subsets = vert_collection.sort_vertices()
        for vert_subset in sorted_vert_subsets:
            coordinates = np.array([vert.coordinates for vert in vert_subset])
            min_point = np.min(coordinates, axis=0)
            max_point = np.max(coordinates, axis=0)
            mid_point = (min_point + max_point) / 2
            ranges = max_point - min_point
            # vertices will have a constant value along this axis
            alignment_axis = np.argmin(ranges)
            # both dimensions
            uv_distances = coordinates[:-1] - coordinates[1:]
            distances = np.hypot(uv_distances[:, 0], uv_distances[:, 1])
            start_point = mid_point.copy()
            start_point[1 - alignment_axis] -= np.sum(distances) / 2
            new_coords = np.tile(start_point, (len(vert_subset), 1))
            new_coords[1:, np.argmax(ranges)] += np.cumsum(distances)

            for vert, new_pos in zip(vert_subset, new_coords):
                for bml in vert.bm_loops:
                    bml[vert_collection.uv_layer].uv = new_pos

        return success_finished(obj.data, start_time)


addon_keymaps = []


def menu_func_uv_squares(self, context):
    self.layout.operator(UV_PT_UvSquares.bl_idname)


def menu_func_uv_squares_by_shape(self, context):
    self.layout.operator(UV_PT_UvSquaresByShape.bl_idname)


def menu_func_face_rip(self, context):
    self.layout.operator(UV_PT_RipFaces.bl_idname)


def menu_func_face_join(self, context):
    self.layout.operator(UV_PT_JoinFaces.bl_idname)


class UV_PT_UvSquaresPanel(bpy.types.Panel):
    """UvSquares Panel"""

    bl_label = "UV Squares"
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"
    bl_category = "UV Squares"

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.label(text="Select Sequenced Vertices to:")
        split = layout.split()
        col = split.column(align=True)
        col.operator(
            UV_PT_SnapToAxis.bl_idname,
            text="Snap to Axis (X or Y)",
            icon="ARROW_LEFTRIGHT",
        )
        col.operator(
            UV_PT_SnapToAxisWithEqual.bl_idname,
            text="Snap with Equal Distance",
            icon="THREE_DOTS",
        )
        col.operator(
            UV_PT_SnapToAxisPreserveDist.bl_idname,
            text="Snap, Preserve Distance",
            icon="THREE_DOTS",
        )

        row = layout.row()
        row.label(text='Convert "Rectangle" (4 corners):')
        split = layout.split()
        col = split.column(align=True)
        col.operator(
            UV_PT_UvSquaresByShape.bl_idname, text="To Grid By Shape", icon="UV_FACESEL"
        )
        col.operator(UV_PT_UvSquares.bl_idname, text="To Square Grid", icon="GRID")

        split = layout.split()
        col = split.column(align=True)
        row = col.row(align=True)

        row = layout.row()

        row.label(text="Select Faces or Vertices to:")
        split = layout.split()
        col = split.column(align=True)
        row = col.row(align=True)

        row.operator(UV_PT_RipFaces.bl_idname, text="Rip Vertex", icon="LAYER_ACTIVE")
        row.operator(UV_PT_RipFaces.bl_idname, text="Rip Faces", icon="UV_ISLANDSEL")
        col.operator(
            UV_PT_JoinFaces.bl_idname,
            text="Snap to Closest Unselected",
            icon="SNAP_GRID",
        )
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
    bpy.utils.register_class(UV_PT_SnapToAxisPreserveDist)

    # menu
    bpy.types.IMAGE_MT_uvs.append(menu_func_uv_squares)
    bpy.types.IMAGE_MT_uvs.append(menu_func_uv_squares_by_shape)
    bpy.types.IMAGE_MT_uvs.append(menu_func_face_rip)
    bpy.types.IMAGE_MT_uvs.append(menu_func_face_join)

    # handle the keymap
    wm = bpy.context.window_manager

    if wm.keyconfigs.addon:
        km = wm.keyconfigs.addon.keymaps.new(name="UV Editor", space_type="EMPTY")
        kmi = km.keymap_items.new(
            UV_PT_UvSquaresByShape.bl_idname, "E", "PRESS", alt=True
        )
        addon_keymaps.append((km, kmi))

        km = wm.keyconfigs.addon.keymaps.new(name="UV Editor", space_type="EMPTY")
        kmi = km.keymap_items.new(UV_PT_RipFaces.bl_idname, "V", "PRESS", alt=True)
        addon_keymaps.append((km, kmi))

        km = wm.keyconfigs.addon.keymaps.new(name="UV Editor", space_type="EMPTY")
        kmi = km.keymap_items.new(
            UV_PT_JoinFaces.bl_idname, "V", "PRESS", alt=True, shift=True
        )
        addon_keymaps.append((km, kmi))


def unregister():
    bpy.utils.unregister_class(UV_PT_UvSquaresPanel)
    bpy.utils.unregister_class(UV_PT_UvSquares)
    bpy.utils.unregister_class(UV_PT_UvSquaresByShape)
    bpy.utils.unregister_class(UV_PT_RipFaces)
    bpy.utils.unregister_class(UV_PT_JoinFaces)
    bpy.utils.unregister_class(UV_PT_SnapToAxis)
    bpy.utils.unregister_class(UV_PT_SnapToAxisWithEqual)
    bpy.utils.unregister_class(UV_PT_SnapToAxisPreserveDist)

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
