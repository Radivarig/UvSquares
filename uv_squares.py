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
    "version": (1, 14, 1),
    "blender": (2, 80, 0),
    "location": "UV Editor > N Panel > UV Squares",
    "category": "UV",
    "wiki_url": "http://wiki.blender.org/index.php/Extensions:2.6/Py/Scripts/UV/Uv_Squares"
}

import bpy
import bmesh
from collections import defaultdict
from math import radians, hypot
from timeit import default_timer as timer

precision = 3

#todo: make joining radius scale with editor zoom rate or average unit length
#todo: align to axis by respect to vert distance
#todo: snap 2dCursor to closest selected vert (when more vertices are selected
#todo: rip different vertex on each press

def main(context, operator, square = False, snapToClosest = False):
    if context.scene.tool_settings.use_uv_select_sync:
        operator.report({'ERROR'}, "Please disable 'Keep UV and edit mesh in sync'")
        # context.scene.tool_settings.use_uv_select_sync = False
        return

    selected_objects = context.selected_objects
    if (context.edit_object not in selected_objects):
        selected_objects.append(context.edit_object)

    for obj in selected_objects:
        if (obj.type == "MESH"):
            main1(obj, context, operator, square, snapToClosest)

def main1(obj, context, operator, square, snapToClosest):
    if context.scene.tool_settings.use_uv_select_sync:
        operator.report({'ERROR'}, "Please disable 'Keep UV and edit mesh in sync'")
        # context.scene.tool_settings.use_uv_select_sync = False
        return

    startTime = timer()
    me = obj.data
    bm = bmesh.from_edit_mesh(me)
    uv_layer = bm.loops.layers.uv.verify()
    # bm.faces.layers.tex.verify()  # currently blender needs both layers.

    edgeVerts, filteredVerts, selFaces, nonQuadFaces, vertsDict, noEdge = ListsOfVerts(uv_layer, bm)
    
    if len(filteredVerts) is 0: return 
    if len(filteredVerts) is 1: 
        SnapCursorToClosestSelected(filteredVerts)
        return 
    
    cursorClosestTo = CursorClosestTo(filteredVerts)
    #line is selected
    
    if len(selFaces) is 0:
        if snapToClosest is True:
            SnapCursorToClosestSelected(filteredVerts)
            return
        
        VertsDictForLine(uv_layer, bm, filteredVerts, vertsDict)
        
        if AreVectsLinedOnAxis(filteredVerts) is False:
            ScaleTo0OnAxisAndCursor(filteredVerts, vertsDict, cursorClosestTo)
            return SuccessFinished(me, startTime)
                
        MakeEqualDistanceBetweenVertsInLine(filteredVerts, vertsDict, cursorClosestTo)
        return SuccessFinished(me, startTime)

    # deselect non quads
    for nf in nonQuadFaces:
        for l in nf.loops:
            luv = l[uv_layer]
            luv.select = False

    def isFaceSelected(f):
        return f.select and all(l[uv_layer].select for l in f.loops)

    def getIslandFromFace(startFace):
        island = set()
        toCheck = set([startFace])

        while (len(toCheck)):
            face = toCheck.pop()
            if isFaceSelected(face) and face not in island:
                island.add(face)
                adjacentFaces = []
                for e in face.edges:
                    if e.seam is False:
                        for f in e.link_faces:
                            if f is not face:
                                adjacentFaces.append(f)
                toCheck.update(adjacentFaces)

        return island

    def getIslandsFromSelectedFaces(selectedFaces):
        islands = []
        toCheck = set(selectedFaces)
        while(len(toCheck)):
            face = toCheck.pop()
            island = getIslandFromFace(face)
            islands.append(island)
            toCheck.difference_update(island)
        return islands

    islands = getIslandsFromSelectedFaces(selFaces)

    def main2 (targetFace, faces):
        ShapeFace(uv_layer, operator, targetFace, vertsDict, square)
        
        if square: FollowActiveUV(operator, me, targetFace, faces, 'EVEN')
        else: FollowActiveUV(operator, me, targetFace, faces)

    for island in islands:
        targetFace = bm.faces.active
        if (targetFace is None or
            targetFace not in island or
            len(islands) > 1 or
            targetFace.select is False or
            len(targetFace.verts) is not 4):
                targetFace = next(iter(island))
        
        main2(targetFace, island)

    if noEdge is False:
        #edge has ripped so we connect it back 
        for ev in edgeVerts:
            key = (round(ev.uv.x, precision), round(ev.uv.y, precision))
            if key in vertsDict:
                ev.uv = vertsDict[key][0].uv
                ev.select = True
        
    return SuccessFinished(me, startTime)

'''def ScaleSelection(factor, pivot = 'CURSOR'):
    last_pivot = bpy.context.space_data.pivot_point
    bpy.context.space_data.pivot_point = pivot
    bpy.ops.transform.resize(value=(factor, factor, factor), constraint_axis=(False, False, False), mirror=False, proportional_edit_falloff='SMOOTH', proportional_size=1)
    bpy.context.space_data.pivot_point = last_pivot
    return'''

def ShapeFace(uv_layer, operator, targetFace, vertsDict, square):
    corners = []
    for l in targetFace.loops:
        luv = l[uv_layer]
        corners.append(luv)
    
    if len(corners) is not 4: 
        #operator.report({'ERROR'}, "bla")
        return
    
    lucv, ldcv, rucv, rdcv = Corners(corners)
    
    cct = CursorClosestTo([lucv, ldcv, rdcv, rucv])
    MakeUvFaceEqualRectangle(vertsDict, lucv, rucv, rdcv, ldcv, cct, square)
    return

def MakeUvFaceEqualRectangle(vertsDict, lucv, rucv, rdcv, ldcv, startv, square = False):
    sizeX, sizeY = ImageSize()
    ratio = sizeX/sizeY
    
    if startv is None: startv = lucv.uv
    elif AreVertsQuasiEqual(startv, rucv): startv = rucv.uv
    elif AreVertsQuasiEqual(startv, rdcv): startv = rdcv.uv
    elif AreVertsQuasiEqual(startv, ldcv): startv = ldcv.uv
    else: startv = lucv.uv
    
    lucv = lucv.uv
    rucv = rucv.uv
    rdcv = rdcv.uv
    ldcv = ldcv.uv    
   
    if (startv == lucv): 
        finalScaleX = hypotVert(lucv, rucv)
        finalScaleY = hypotVert(lucv, ldcv)
        currRowX = lucv.x
        currRowY = lucv.y
    
    elif (startv == rucv):
        finalScaleX = hypotVert(rucv, lucv)
        finalScaleY = hypotVert(rucv, rdcv)
        currRowX = rucv.x - finalScaleX
        currRowY = rucv.y
       
    elif (startv == rdcv):
        finalScaleX = hypotVert(rdcv, ldcv)
        finalScaleY = hypotVert(rdcv, rucv)
        currRowX = rdcv.x - finalScaleX
        currRowY = rdcv.y + finalScaleY
        
    else:
        finalScaleX = hypotVert(ldcv, rdcv)
        finalScaleY = hypotVert(ldcv, lucv)
        currRowX = ldcv.x
        currRowY = ldcv.y +finalScaleY
    
    if square: finalScaleY = finalScaleX*ratio
    #lucv, rucv
    x = round(lucv.x, precision)
    y = round(lucv.y, precision)
    for v in vertsDict[(x,y)]:
        v.uv.x = currRowX
        v.uv.y = currRowY
  
    x = round(rucv.x, precision)
    y = round(rucv.y, precision)
    for v in vertsDict[(x,y)]:
        v.uv.x = currRowX + finalScaleX
        v.uv.y = currRowY
    
    #rdcv, ldcv
    x = round(rdcv.x, precision)
    y = round(rdcv.y, precision)    
    for v in vertsDict[(x,y)]:
        v.uv.x = currRowX + finalScaleX
        v.uv.y = currRowY - finalScaleY
        
    x = round(ldcv.x, precision)
    y = round(ldcv.y, precision)    
    for v in vertsDict[(x,y)]:
        v.uv.x = currRowX
        v.uv.y = currRowY - finalScaleY

        
    return

def SnapCursorToClosestSelected(filteredVerts):
    #TODO: snap to closest selected 
    if len(filteredVerts) is 1: 
        SetAll2dCursorsTo(filteredVerts[0].uv.x, filteredVerts[0].uv.y)
    
    return

def ListsOfVerts(uv_layer, bm):
    edgeVerts = []
    allEdgeVerts = []
    filteredVerts = []
    selFaces = []
    nonQuadFaces = []
    vertsDict = defaultdict(list)                #dict
    
    for f in bm.faces:
        isFaceSel = True
        facesEdgeVerts = []
        if (f.select == False):
            continue
        
        #collect edge verts if any
        for l in f.loops:
            luv = l[uv_layer]
            if luv.select is True:
                facesEdgeVerts.append(luv)
            else: isFaceSel = False
        
        allEdgeVerts.extend(facesEdgeVerts)
        if isFaceSel:            
            if len(f.verts) is not 4:
                nonQuadFaces.append(f)
                edgeVerts.extend(facesEdgeVerts)
            else: 
                selFaces.append(f)
                
                for l in f.loops:
                    luv = l[uv_layer]
                    x = round(luv.uv.x, precision)
                    y = round(luv.uv.y, precision)
                    vertsDict[(x, y)].append(luv)
        
        else: edgeVerts.extend(facesEdgeVerts)
    
    noEdge = False
    if len(edgeVerts) is 0:
        noEdge = True
        edgeVerts.extend(allEdgeVerts)
    
    if len(selFaces) is 0:
        for ev in edgeVerts:
            if ListQuasiContainsVect(filteredVerts, ev) is False:
                filteredVerts.append(ev)
    else: filteredVerts = edgeVerts
        
    return edgeVerts, filteredVerts, selFaces, nonQuadFaces, vertsDict, noEdge

def ListQuasiContainsVect(list, vect):
    for v in list:
        if AreVertsQuasiEqual(v, vect):
            return True
    return False

#modified ideasman42's uvcalc_follow_active.py
def FollowActiveUV(operator, me, f_act, faces, EXTEND_MODE = 'LENGTH_AVERAGE'):
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
                    if (l_edge.is_manifold is True) and (l_edge.seam is False):
                        l_other = l.link_loop_radial_next
                        f_other = l_other.face
                        if not f_other.tag:
                            yield (f, l, f_other)
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

    def extrapolate_uv(fac,
                       l_a_outer, l_a_inner,
                       l_b_outer, l_b_inner):
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

        if EXTEND_MODE == 'LENGTH_AVERAGE':
            try:
                fac = edge_lengths[l_b[2].edge.index][0] / edge_lengths[l_a[1].edge.index][0]
            except ZeroDivisionError:
                fac = 1.0
        elif EXTEND_MODE == 'LENGTH':
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

        extrapolate_uv(fac,
                       l_a_uv[3], l_a_uv[0],
                       l_b_uv[3], l_b_uv[0])

        extrapolate_uv(fac,
                       l_a_uv[2], l_a_uv[1],
                       l_b_uv[2], l_b_uv[1])

    # -------------------------------------------
    # Calculate average length per loop if needed

    if EXTEND_MODE == 'LENGTH_AVERAGE':
        bm.edges.index_update()
        edge_lengths = [None] * len(bm.edges)   #NoneType times the length of edges list
        
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

    bmesh.update_edit_mesh(me, loop_triangles=False)

'''----------------------------------'''

def SuccessFinished(me, startTime):
    #use for backtrack of steps 
    #bpy.ops.ed.undo_push()
    bmesh.update_edit_mesh(me)
    elapsed = round(timer()-startTime, 2)
    #if (elapsed >= 0.05): operator.report({'INFO'}, "UvSquares finished, elapsed:", elapsed, "s.")
    if (elapsed >= 0.05): print("UvSquares finished, elapsed:", elapsed, "s.")
    return

'''def SymmetrySelected(axis, pivot = "MEDIAN"):
    last_pivot = bpy.context.space_data.pivot_point
    bpy.context.space_data.pivot_point = pivot
    bpy.ops.transform.mirror(constraint_axis=(True, False, False), constraint_orientation='GLOBAL', proportional_edit_falloff='SMOOTH', proportional_size=1)
    bpy.context.space_data.pivot_point = last_pivot
    return'''

def AreVectsLinedOnAxis(verts):
    areLinedX = True
    areLinedY = True
    allowedError = 0.00001
    valX = verts[0].uv.x
    valY = verts[0].uv.y
    for v in verts:
        if abs(valX - v.uv.x) > allowedError:
            areLinedX = False
        if abs(valY - v.uv.y) > allowedError:
            areLinedY = False
    return areLinedX or areLinedY  

def MakeEqualDistanceBetweenVertsInLine(filteredVerts, vertsDict, startv = None):    
    verts = filteredVerts
    verts.sort(key=lambda x: x.uv[0])      #sort by .x
    
    first = verts[0].uv
    last = verts[len(verts)-1].uv
    
    horizontal = True
    if ((last.x - first.x) >0.00001):
        slope = (last.y - first.y)/(last.x - first.x)
        if (slope > 1) or (slope <-1):
            horizontal = False 
    else: 
        horizontal = False
    
    if horizontal is True:
        length = hypot(first.x - last.x, first.y - last.y)
        
        if startv is last:
            currentX = last.x - length
            currentY = last.y
        else:
            currentX = first.x
            currentY = first.y
    else:
        verts.sort(key=lambda x: x.uv[1])  #sort by .y
        verts.reverse()     #reverse because y values drop from up to down
        first = verts[0].uv
        last = verts[len(verts)-1].uv
        
        length = hypot(first.x - last.x, first.y - last.y)  # we have to call length here because if it is not Hor first and second can not actually be first and second
        
        if startv is last:
            currentX = last.x
            currentY = last.y + length
        
        else:
            currentX = first.x
            currentY = first.y
        
    numberOfVerts = len(verts)
    finalScale = length / (numberOfVerts-1)
    
    if horizontal is True:
        first = verts[0]
        last = verts[len(verts)-1]
        
        for v in verts:
            v = v.uv
            x = round(v.x, precision)
            y = round(v.y, precision)
            
            for vert in vertsDict[(x,y)]:
                vert.uv.x = currentX
                vert.uv.y = currentY
            
            currentX = currentX + finalScale
    else:    
        for v in verts:
            x = round(v.uv.x, precision)
            y = round(v.uv.y, precision)
            
            for vert in vertsDict[(x,y)]:
                vert.uv.x = currentX
                vert.uv.y = currentY
            
            currentY = currentY - finalScale
    return

def VertsDictForLine(uv_layer, bm, selVerts, vertsDict):
    for f in bm.faces:
        for l in f.loops:
                luv = l[uv_layer]
                if luv.select is True:
                    x = round(luv.uv.x, precision)
                    y = round(luv.uv.y, precision)
         
                    vertsDict[(x, y)].append(luv)
    return

def ScaleTo0OnAxisAndCursor(filteredVerts, vertsDict, startv = None, horizontal = None):      
    
    verts = filteredVerts
    verts.sort(key=lambda x: x.uv[0])      #sort by .x
    
    first = verts[0]
    last = verts[len(verts)-1]
    
    if horizontal is None:
        horizontal = True
        if ((last.uv.x - first.uv.x) >0.00001):
            slope = (last.uv.y - first.uv.y)/(last.uv.x - first.uv.x)
            if (slope > 1) or (slope <-1):
                horizontal = False 
        else: 
            horizontal = False
    
    if horizontal is True:
        if startv is None:
            startv = first  
        
        SetAll2dCursorsTo(startv.uv.x, startv.uv.y)
        #scale to 0 on Y
        ScaleTo0('Y')
        return
       
    else:
        verts.sort(key=lambda x: x.uv[1])  #sort by .y
        verts.reverse()     #reverse because y values drop from up to down
        first = verts[0]
        last = verts[len(verts)-1]
        if startv is None:
            startv = first  

        SetAll2dCursorsTo(startv.uv.x, startv.uv.y)
        #scale to 0 on X
        ScaleTo0('X')
        return
    
def ScaleTo0(axis):
    last_area = bpy.context.area.type
    bpy.context.area.type = 'IMAGE_EDITOR'
    last_pivot = bpy.context.space_data.pivot_point
    bpy.context.space_data.pivot_point = 'CURSOR'
    
    for area in bpy.context.screen.areas:
        if area.type == 'IMAGE_EDITOR':
            if axis is 'Y':
                bpy.ops.transform.resize(value=(1, 0, 1), constraint_axis=(False, True, False), mirror=False, proportional_edit_falloff='SMOOTH', proportional_size=1)
            else:
                bpy.ops.transform.resize(value=(0, 1, 1), constraint_axis=(True, False, False), mirror=False, proportional_edit_falloff='SMOOTH', proportional_size=1)
                

    bpy.context.space_data.pivot_point = last_pivot
    return


def hypotVert(v1, v2):
    hyp = hypot(v1.x - v2.x, v1.y - v2.y)
    return hyp

def Corners(corners):
    firstHighest = corners[0]
    for c in corners:
        if c.uv.y > firstHighest.uv.y:
            firstHighest = c    
    corners.remove(firstHighest)
    
    secondHighest = corners[0]
    for c in corners:
        if (c.uv.y > secondHighest.uv.y):
            secondHighest = c
    
    if firstHighest.uv.x < secondHighest.uv.x:
        leftUp = firstHighest
        rightUp = secondHighest
    else:
        leftUp = secondHighest
        rightUp = firstHighest
    corners.remove(secondHighest)
    
    firstLowest = corners[0]
    secondLowest = corners[1]
    
    if firstLowest.uv.x < secondLowest.uv.x:
        leftDown = firstLowest
        rightDown = secondLowest
    else:
        leftDown = secondLowest
        rightDown = firstLowest
    
    return leftUp, leftDown, rightUp, rightDown

def ImageSize():
    ratioX, ratioY = 256,256
    for a in bpy.context.screen.areas:
        if a.type == 'IMAGE_EDITOR':
            img = a.spaces[0].image
            if img is not None and img.size[0] is not 0:
                ratioX, ratioY = img.size[0], img.size[1]
            break
    return ratioX, ratioY

def CursorClosestTo(verts):
    sizeX, sizeY = ImageSize()
    if bpy.app.version >= (2, 80, 0):
        sizeX, sizeY = 1,1
    min = float('inf')
    minV = verts[0]
    for v in verts:
        if v is None: continue
        for area in bpy.context.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                loc = area.spaces[0].cursor_location
                hyp = hypot(loc.x/sizeX -v.uv.x, loc.y/sizeY -v.uv.y)
                if (hyp < min):
                    min = hyp
                    minV = v
    return minV

def SetAll2dCursorsTo(x,y):
    last_area = bpy.context.area.type
    bpy.context.area.type = 'IMAGE_EDITOR'
   
    bpy.ops.uv.cursor_set(location=(x, y))

    bpy.context.area.type = last_area
    return

'''def RotateSelected(angle, pivot = None):
    if pivot is None:
        pivot = "MEDIAN"
   
    last_area = bpy.context.area.type
    bpy.context.area.type = 'IMAGE_EDITOR'
    
    last_pivot = bpy.context.space_data.pivot_point
    bpy.context.space_data.pivot_point = pivot
    
    for area in bpy.context.screen.areas:
        if area.type == 'IMAGE_EDITOR':
            bpy.ops.transform.rotate(value=radians(angle), axis=(-0, -0, -1), constraint_axis=(False, False, False), constraint_orientation='LOCAL', mirror=False, proportional_edit_falloff='SMOOTH', proportional_size=1)
            break

    bpy.context.space_data.pivot_point = last_pivot
    bpy.context.area.type = last_area
    
    return'''

def AreVertsQuasiEqual(v1, v2, allowedError = 0.00001):
    if abs(v1.uv.x -v2.uv.x) < allowedError and abs(v1.uv.y -v2.uv.y) < allowedError:
        return True
    return False

def RipUvFaces(context, operator):
    startTime = timer()
    
    obj = context.active_object
    me = obj.data
    bm = bmesh.from_edit_mesh(me)
    
    uv_layer = bm.loops.layers.uv.verify()
    # bm.faces.layers.tex.verify()  # currently blender needs both layers.
       
    selFaces = []
    
    for f in bm.faces:
        isFaceSel = True
        for l in f.loops:
            luv = l[uv_layer]
            if luv.select is False:
                isFaceSel = False
                break
    
        if isFaceSel is True:
            selFaces.append(f)
    
    if len(selFaces) is 0:
        target = None
        for f in bm.faces:
            for l in f.loops:
                luv = l[uv_layer]
                if luv.select is True:
                    target = luv
                    break
            if target is not None: break
        
        for f in bm.faces:
            for l in f.loops:
                luv = l[uv_layer]
                luv.select = False
        
        target.select = True
        return SuccessFinished(me, startTime)

    DeselectAll()
    
    for sf in selFaces:
        for l in sf.loops:
            luv = l[uv_layer]
            luv.select = True
    
    return SuccessFinished(me, startTime)

def JoinUvFaces(context, operator):
    startTime = timer()
    
    obj = context.active_object
    me = obj.data
    bm = bmesh.from_edit_mesh(me)
    
    uv_layer = bm.loops.layers.uv.verify()
    # bm.faces.layers.tex.verify()  # currently blender needs both layers.
    
    vertsDict = defaultdict(list)        #dict 
             
    #TODO: radius by image scale
    radius = 0.002
    
    for f in bm.faces:
        for l in f.loops:
           luv = l[uv_layer]
           if luv.select is True:
               x = round(luv.uv.x, precision)
               y = round(luv.uv.y, precision)
               vertsDict[(x,y)].append(luv)
         
    for key in vertsDict:
        min = 1
        minV = None
        
        for f in bm.faces:
            for l in f.loops:
                luv = l[uv_layer]
                if luv.select is False:
                    hyp = hypot(vertsDict[(key[0], key[1])][0].uv.x -luv.uv.x, vertsDict[(key[0], key[1])][0].uv.y -luv.uv.y)
                    if (hyp <= min) and hyp < radius:
                        min = hyp
                        minV = luv
                        minV.select = True
        
            if min is not 1:
                for v in vertsDict[(key[0], key[1])]:
                    v = v.uv
                    v.x = minV.uv.x
                    v.y = minV.uv.y
    
    return SuccessFinished(me, startTime)

def DeselectAll():
    bpy.ops.uv.select_all(action='DESELECT')
    return


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
    bl_region_type = 'UI'
    bl_category = 'UV Squares'

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.label(text="Select Sequenced Vertices to:")
        split = layout.split()
        col = split.column(align=True)
        col.operator(UV_PT_SnapToAxis.bl_idname, text="Snap to Axis (X or Y)", icon = "ARROW_LEFTRIGHT")
        col.operator(UV_PT_SnapToAxisWithEqual.bl_idname, text="Snap with Equal Distance", icon = "THREE_DOTS")

        row = layout.row()
        row.label(text="Convert \"Rectangle\" (4 corners):")
        split = layout.split()
        col = split.column(align=True)
        col.operator(UV_PT_UvSquaresByShape.bl_idname, text="To Grid By Shape", icon = "UV_FACESEL")
        col.operator(UV_PT_UvSquares.bl_idname, text="To Square Grid", icon = "GRID")

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

    if (wm.keyconfigs.addon):
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
