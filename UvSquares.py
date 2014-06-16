#    <Uv Squares, Blender addon that reshapes UV faces into squares.>
#    Copyright (C) <2014>  <Reslav Hollos>
#    This work is under the MIT License (MIT), see LICENSE file.

bl_info = {
    "name": "Uv Squares",
    "description": "Reshapes UV faces to a grid of equivalent squares",
    "author": "Reslav Hollos",
    "version": (1, 0, 2),
    "blender": (2, 7, 0),
    "category": "Mesh"
    #"location": "UV Image Editor > UVs > UVs to grid of squares", 
    #"warning": "",
    #"wiki_url": "http://wiki.blender.org/index.php/Extensions:2.6/Py/"
    #            "Scripts/UV/Uv_Squares",
    }
import bpy
import bmesh
from collections import defaultdict  
from math import radians
import time

#known_issue: if loop cut was used, mesh has to be unwrapped again'

def main(context):
    obj = context.active_object
    me = obj.data
    bm = bmesh.from_edit_mesh(me)

    startTime = time.clock()
    
    uv_layer = bm.loops.layers.uv.verify()
    bm.faces.layers.tex.verify()  # currently blender needs both layers.
    
    selVerts = ListOfSelVerts(uv_layer, bm)  #remember selected verts so we can reselect at end
    
    leftUpCornerV, leftDownCornerV, rightUpCornerV, rightDownCornerV = FetchCorners(uv_layer, bm, selVerts)
    if leftUpCornerV is None:      #we don't need to check for others since they are all None
        print("--error: number of corners is not 4, faces might not be rectangles")
        return
    else:
        print("success! matched 4 corners")
        
    if len(selVerts) is 4:
        leftUpCornerUvF, leftDownCornerUvF, rightUpCornerUvF, rightDownCornerUvF = MakeCornerUvFacesFrom4Corners(leftUpCornerV, leftDownCornerV, rightUpCornerV, rightDownCornerV)
    else:        
        leftUpCornerF, leftDownCornerF, rightUpCornerF, rightDownCornerF = FetchCornerFaces(uv_layer, bm, leftUpCornerV, leftDownCornerV, rightUpCornerV, rightDownCornerV)
        if leftUpCornerF is None or leftDownCornerF is None or rightUpCornerF is None or rightDownCornerF is None:
            print("--error: corner face might not be a rectangle")
            return
        else:
            print("success! recognized 4 corner faces")
    
        leftUpCornerUvF, leftDownCornerUvF, rightUpCornerUvF, rightDownCornerUvF = MakeCornerUvFaces(uv_layer, bm, leftUpCornerF, leftDownCornerF, rightUpCornerF, rightDownCornerF, leftUpCornerV, leftDownCornerV, rightUpCornerV, rightDownCornerV)                                                                                          
        if leftUpCornerUvF is None or leftDownCornerUvF is None or rightUpCornerUvF is None or rightDownCornerUvF is None:
            print("--error: couldn't determine corners of given corner face")
            return
        else:
            print("success! corners of all 4 corner faces recognized")
        
    array2dOfVerts = Build2DimArrayOfUvFaces(uv_layer, bm, leftUpCornerUvF, leftDownCornerUvF, rightUpCornerUvF, rightDownCornerUvF)
    if array2dOfVerts is None:
        print("--error: not all faces were recognized, add more distance between close vertices")
        return
    else:
        print("success! all faces recognized and nested list is created")
    
    MakeUvFacesEqualRectangles(uv_layer, bm, array2dOfVerts, leftUpCornerV, rightUpCornerV)
    
    SelectVerts(uv_layer, bm, selVerts)
    bmesh.update_edit_mesh(me)
    print("success! UvSquares script finnished.")
    
    print("time taken", time.clock() - startTime)
    
    return
   
def MakeCornerUvFacesFrom4Corners(leftUpCornerV, leftDownCornerV, rightUpCornerV, rightDownCornerV):
    face = UvFace()
    face.leftUpVert = leftUpCornerV
    face.leftDownVert = leftDownCornerV
    face.rightUpVert = rightUpCornerV
    face.rightDownVert = rightDownCornerV
    a = face
    b = face
    c = face
    d = face
    return a,b,c,d

def MakeUvFacesEqualRectangles(uv_layer, bm, array2dOfVerts, leftUpCornerV, rightUpCornerV):
    rowNumber = len(array2dOfVerts) +1   #number of faces +1 equals number of rows, same for column
    colNumber = len(array2dOfVerts[0]) +1
    
    initDistance = rightUpCornerV.x - leftUpCornerV.x
    finalScale = initDistance / (colNumber - 1)
        
    currRowX = leftUpCornerV.x
    currRowY = leftUpCornerV.y

    #faster but does not move unselected shared vertices
    
    #for row in array2dOfVerts:
    #   for face in row:
    #       face.leftUpVert.x = currRowX
    #       face.leftUpVert.y = currRowY
    #       
    #       face.leftDownVert.x = currRowX
    #       face.leftDownVert.y = currRowY - finalScale
    #       
    #       currRowX = currRowX + finalScale
    #       
    #       face.rightUpVert.x = currRowX
    #       face.rightUpVert.y = currRowY
    #       
    #       face.rightDownVert.x = currRowX
    #       face.rightDownVert.y = currRowY - finalScale
    #               
    #   currRowX = leftUpCornerV.x
    #   currRowY = currRowY - finalScale
    
    for row in array2dOfVerts:
        for face in row:
            leftUpVerts = []
            leftDownVerts = []
            rightUpVerts = []
            rightDownVerts = []
            
            leftUpVerts.append(face.leftUpVert)
            leftDownVerts.append(face.leftDownVert)
            rightUpVerts.append(face.rightUpVert)
            rightDownVerts.append(face.rightDownVert)
            
            
            for f in bm.faces:
                for l in f.loops:
                    luv = l[uv_layer]
                    if AreVectorsQuasiEqual(face.leftUpVert, luv.uv):
                        leftUpVerts.append(luv.uv)
                        
                    if AreVectorsQuasiEqual(face.leftDownVert, luv.uv):
                        leftDownVerts.append(luv.uv)
                    
                    if AreVectorsQuasiEqual(face.rightUpVert, luv.uv):
                        rightUpVerts.append(luv.uv)
                    
                    if AreVectorsQuasiEqual(face.rightDownVert, luv.uv):
                        rightDownVerts.append(luv.uv)
            
            for v in leftUpVerts:
                v.x = currRowX
                v.y = currRowY
                
            for v in leftDownVerts:
                v.x = currRowX
                v.y = currRowY - finalScale
            
            for v in rightUpVerts:
                v.x = currRowX + finalScale
                v.y = currRowY
            
            for v in rightDownVerts:
                v.x = currRowX + finalScale
                v.y = currRowY - finalScale  
                        
            currRowX = currRowX + finalScale
                     
        currRowX = leftUpCornerV.x
        currRowY = currRowY - finalScale

    return

def MakeCornerUvFaces(uv_layer, bm,
                         leftUpCornerF, leftDownCornerF, rightUpCornerF, rightDownCornerF, 
                         leftUpCornerV, leftDownCornerV, rightUpCornerV, rightDownCornerV):
    
    leftUpCornerUvF = SetCornerFace(uv_layer, bm, "leftUp", leftUpCornerF, leftUpCornerV) 
    leftDownCornerUvF = SetCornerFace(uv_layer, bm, "leftDown", leftDownCornerF, leftDownCornerV)
    rightupCornerUvF = SetCornerFace(uv_layer, bm, "rightUp", rightUpCornerF, rightUpCornerV)
    rightDownCornerUvF = SetCornerFace(uv_layer, bm, "rightDown", rightDownCornerF, rightDownCornerV)
    
    return leftUpCornerUvF, leftDownCornerUvF, rightupCornerUvF, rightDownCornerUvF


def Build2DimArrayOfUvFaces(uv_layer, bm, leftUpCornerUvF, leftDownCornerUvF, rightUpCornerUvF, rightDownCornerUvF):
    
    array2dOfVerts = []
    
    if leftUpCornerUvF is None or rightUpCornerUvF is None:
        print("error: None corner passed to Build2DimArray")
        return None
    
    startF = UvFace(leftUpCornerUvF)
    endF = UvFace(rightUpCornerUvF)

    while True:
        column = UvFacesFromTo(uv_layer, bm, "right", startF, endF)
        if column is None:
            print("--error: column was not built.")
            return None
        
        array2dOfVerts.append(column)
                   
        if AreUvFacesEqual(startF, leftDownCornerUvF):
            break
              
        startF = UvFaceDownOf(uv_layer, bm, startF)
        endF = UvFaceDownOf(uv_layer, bm, endF)
           
    return array2dOfVerts
    
def NextUvFace(uv_layer, bm, orientation, givenF):
    if orientation is "down":
        return UvFaceDownOf(uv_layer, bm, givenF)
    
    elif orientation is "right":
        return UvFaceRightOf(uv_layer, bm, givenF)
    
    else:
        return None

def UvFaceRightOf(uv_layer, bm, givenF):
    DeselectAll()
    
    contains = [givenF.rightUpVert, givenF.rightDownVert]
    notContains = [givenF.leftUpVert, givenF.leftDownVert]
    
    verts = SelectFaceContaining(uv_layer, bm, contains, notContains)
    
    i=0
    if (len(verts) <=3):
        if len(verts) is 3:
            print("--error: triangles not supported")
        
        for v in verts:
            print("corner", i+1,v)
            i=i+1 
         
        print("--error in UvFaceRightOf - len(face corners):", len(verts))
        return
    
    
    face = UvFace()
    DetermineUvFaceParts(uv_layer, bm, face, verts, "leftUp", givenF.rightUpVert)
    
    DeselectAll()
    return face 


def UvFaceDownOf(uv_layer, bm, givenF):
    DeselectAll()
    
    contains = [givenF.leftDownVert, givenF.rightDownVert]
    notContains = [givenF.leftUpVert, givenF.rightUpVert]
    
    verts = SelectFaceContaining(uv_layer, bm, contains, notContains)
    
    i=0
    if (len(verts) <=3):
        if len(verts) is 3:
            print("--error: triangles not supported")
        
        for v in verts:
            print("corner", i+1,v)
            i=i+1 
         
        print("--error in UvFaceDownOf - len(face corners):", len(verts))
        return
    
    
    face = UvFace()
    DetermineUvFaceParts(uv_layer, bm, face, verts, "leftUp", givenF.leftDownVert)
    
    return face 

def ListOfSelVerts(uv_layer, bm):
    selectedV = []
    for f in bm.faces:
        for l in f.loops:
            luv = l[uv_layer]
            if luv.select is True:
                selectedV.append(luv.uv)
    return selectedV


def UvFacesFromTo(uv_layer, bm, orientation, startUvF, endUvF):
    column = []
        
    current = UvFace(startUvF)      #so we don't overwrite original 
    
    #print(startUvF.leftUpVert, startUvF.leftDownVert, startUvF.rightUpVert, startUvF.rightDownVert)
    #print(endUvF.leftUpVert, endUvF.leftDownVert, endUvF.rightUpVert, endUvF.rightDownVert)
    
    if(AreUvFacesEqual(startUvF, endUvF)):
        #print("kuu")
        column.append(current)
        return column
    
    while True:       
        column.append(current)
        
        current = NextUvFace(uv_layer, bm, orientation, current)
        if current is None:
            print("--error: column returned None, in UvFacesFromTo")
            return None
        
        if AreUvFacesEqual(current, endUvF):
            column.append(current)
            break
        #print(i)
        #i=i+1
        
    return column
   
 
def DeselectAll():
    bpy.ops.uv.select_all(action='DESELECT')
    return

def SetCornerFace(uv_layer, bm, side, cornerF, cornerV):
    verts = []
    face = UvFace()
    
    last_area = bpy.context.area.type
    bpy.context.area.type = 'IMAGE_EDITOR'
    bpy.ops.uv.select_all(action='DESELECT')
    bpy.context.area.type = last_area

    #fill face verts to list
    for l in cornerF.loops:
        luv = l[uv_layer]
        verts.append(luv.uv)
    

    #select all verts that are same as from the face (each "vertex" is actually 1, 2 or 4 vertices, depending on number of faces that have it)
    i=0
    for f in bm.faces: 
        for l in f.loops:   
            for v in verts:
                loop_uv = l[uv_layer]
                if AreVectorsQuasiEqual(loop_uv.uv, v):
                    loop_uv.select = True
                    i=i+1
                    if i is 16:
                        break   #should break from all three for loops since we selected them all
    
    DetermineUvFaceParts(uv_layer, bm, face, verts, side, cornerV)
    
    return face

def DetermineUvFaceParts(uv_layer, bm, face, verts, side, cornerV):
    if len(verts) is not 4:
        #ForceInfiniteLoopError("error, face is not a rectangle")
        print("--error in determining a face")
        return

    #print("was here 3")
    rotatedFor = RotateSelFaceUntilCornerIsHor(uv_layer, bm, verts, side, cornerV)
    #print("was here 4")
    SetUvFace(face, verts[:], side, cornerV) 
    RotateSelected(-rotatedFor)
    #print("was here 5")
    
    return

def AreUvFacesEqual(face1, face2):
    if AreVectorsQuasiEqual(face1.leftUpVert, face2.leftUpVert) is False:
        return False
    if AreVectorsQuasiEqual(face1.leftDownVert, face2.leftDownVert) is False:
        return False
    if AreVectorsQuasiEqual(face1.rightUpVert, face2.rightUpVert) is False:
        return False
    if AreVectorsQuasiEqual(face1.rightDownVert, face2.rightDownVert) is False:
        return False
    return True

def SelectVerts(uv_layer, bm, containingV):
    for f in bm.faces:
        #checking for contained verts 
        for cv in containingV:
            for l in f.loops:
                luv = l[uv_layer]
                if AreVectorsQuasiEqual(cv, luv.uv):
                    luv.select = True              
    return

def SelectFaceContaining(uv_layer, bm, containingV, notContainingV = None):
    #face = None
    
    verts = []
    for f in bm.faces:
        selectThisFace = True
        
        #checking for contained verts 
        for cv in containingV:
            containsV = False
            for l in f.loops:
                luv = l[uv_layer]
                if AreVectorsQuasiEqual(cv, luv.uv):
                    containsV = True
                    break
            
            if containsV is False:
                selectThisFace = False
                break
        
        if selectThisFace is False:
            continue
        
        if notContainingV is not None:
            #checking for not contained verts
            for ncv in notContainingV:
                for l in f.loops:
                    luv = l[uv_layer]
                    if AreVectorsQuasiEqual(ncv, luv.uv):
                        selectThisFace = False
                        break
        
        if selectThisFace is False:
            continue
        
        #if we met requirements we add it to list
        for l in f.loops:
            luv = l[uv_layer]
            verts.append(luv.uv)
        
        #face = f
        break
           
    #we select all verts that are equal to any in the list
    for f in bm.faces:
        for v in verts:
            for l in f.loops:
                luv = l[uv_layer]
                if AreVectorsQuasiEqual(luv.uv, v):
                    luv.select = True
    return verts

def SetUvFace(face, verts, side, corner):
    
    if(len(verts) <= 3):
        #ForceInfiniteLoopError("error in iscornerhoriz", len(verts))
        print("--error something")
        return True
    
    #print("side", side, "corner", corner)
    
    if side is "leftUp":
        for v in verts:
            if AreVectorsQuasiEqual(v, corner):
                face.leftUpVert = v
                verts.remove(v)
                break
        
        rightUpV = verts[0]
        for v in verts:
            if (v.y > rightUpV.y):
                rightUpV = v
        face.rightUpVert = rightUpV
        verts.remove(rightUpV)
        
        leftDownV = verts[0]
        for v in verts:
            if(v.x < leftDownV.x):
                leftDownV = v
        face.leftDownVert = leftDownV
        verts.remove(leftDownV)
        
        face.rightDownVert = verts[0]
        verts.remove(verts[0])

    elif side is "leftDown":
        for v in verts:
            if AreVectorsQuasiEqual(v, corner):
                face.leftDownVert = v
                verts.remove(v)
                break
        
        rightDownV = verts[0]
        for v in verts:
            if(v.y < rightDownV.y):
                rightDownV = v
        face.rightDownVert = rightDownV
        verts.remove(rightDownV)
        
        rightUpV = verts[0]
        for v in verts:
            if (v.x > rightUpV.x):
                rightUpV = v
        face.rightUpVert = rightUpV
        verts.remove(rightUpV)
        
        face.leftUpVert = verts[0]
        verts.remove(verts[0])
    
    elif side is "rightUp":
        for v in verts:
            if AreVectorsQuasiEqual(v, corner):
                face.rightUpVert = v
                verts.remove(v)
                break
        
        leftUpV = verts[0]
        for v in verts:
            if (v.y > leftUpV.y):
                leftUpV = v
        face.leftUpVert = leftUpV
        verts.remove(leftUpV)
        
        leftDownV = verts[0]
        for v in verts:
            if(v.x < leftDownV.x):
                leftDownV = v
        face.leftDownVert = leftDownV
        verts.remove(leftDownV)
        
        face.rightDownVert = verts[0]
        verts.remove(verts[0])

    elif side is "rightDown":
        for v in verts:
            if AreVectorsQuasiEqual(v, corner):
                face.rightDownVert = v
                verts.remove(v)
                break
        
        leftDownV = verts[0]
        for v in verts:
            if(v.y < leftDownV.y):
                leftDownV = v
        face.leftDownVert = leftDownV
        verts.remove(leftDownV)
        
        rightUpV = verts[0]
        for v in verts:
            if (v.x > rightUpV.x):
                rightUpV = v
        face.rightUpVert = rightUpV
        verts.remove(rightUpV)
        
        face.leftUpVert = verts[0]
        verts.remove(verts[0])
    
    else:
        print("code for", side, "is missing in SetUvFace")
 
    return 

def ForceInfiniteLoopError(message = ""):
    #point of this is to get this message and prevent further compilation, then we just ctrl+c in console and see where the problem is 
    print("--error, infinite loop.", message, ",press ctrl+c to cancel")
    b = True
    while b is True:
        b = True
    return
    
def IsCornerHorizontal(uv_layer, verts, side, corner):
    allowedError = 0.01
    
    if(len(verts) <= 3):
        #ForceInfiniteLoopError(len(verts))
        print("--error, something2")
        return True
    
    if side is "leftUp" or side is "rightUp":
        firstHighest = verts[0]
        for v in verts: 
            if (v.y > firstHighest.y):
                firstHighest = v
                
        secondHighest = verts[0]
        if AreVectorsQuasiEqual(firstHighest, secondHighest):
            secondHighest = verts[1]
        for v in verts:
            if AreVectorsQuasiEqual(v, firstHighest) is False:
                if(v.y > secondHighest.y):
                    secondHighest = v
                
        if abs(firstHighest.y - secondHighest.y) > allowedError:
            return False
        
        if AreVectorsQuasiEqual(corner, firstHighest):
            if side is "leftUp":
                if firstHighest.x < secondHighest.x:
                    return True
            if side is "rightUp":
                if firstHighest.x > secondHighest.x:
                    return True
                
        elif AreVectorsQuasiEqual(corner, secondHighest):
            if side is "leftUp":
                if secondHighest.x < firstHighest.x:
                    return True
            if side is "rightUp":
                if secondHighest.x > firstHighest.x:
                    return True     
          
    elif side is "leftDown" or side is "rightDown":
        firstLowest = verts[0]
        for v in verts: 
            if (v.y < firstLowest.y):
                firstLowest = v
        
        secondLowest = verts[0]
        if AreVectorsQuasiEqual(firstLowest, secondLowest):
            secondLowest = verts[1]
        for v in verts:
            if AreVectorsQuasiEqual(v, firstLowest) is False:
                if(v.y < secondLowest.y):
                    secondLowest = v
        
        if abs(firstLowest.y - secondLowest.y) > allowedError:
            return False
        
        if AreVectorsQuasiEqual(corner, firstLowest):
            if side is "leftDown":
                if firstLowest.x < secondLowest.x:
                    return True
            if side is "rightDown":
                if firstLowest.x > secondLowest.x:
                    return True
                
        elif AreVectorsQuasiEqual(corner, secondLowest):
            if side is "leftDown":
                if secondLowest.x < firstLowest.x:
                    return True
            if side is "rightDown":
                if secondLowest.x > firstLowest.x:
                    return True
    
    #print("NOTHING 45455")
    #print("side:",side)
    #print("corner",corner)
    #for v in verts:
    #   print("v", v)
    #
    #if side is "leftUp" or side is "rightUp":
    #   print("firstH", firstHighest)
    #   print("secondH", secondHighest)
    #   
    #elif side is "leftDown" or side is "rightDown":
    #   print("firstL", firstLowest)
    #   print("secondL", secondLowest)
#   
#   else: 
#       print("aaaalala")
    
    #ForceInfiniteLoopError("nothing 445445")
    
    return False

def RotateSelFaceUntilCornerIsHor(uv_layer, bm, verts, side, corner):
    i=0
    rotations = 0
    #angle = 43.11 # 45-1 to break symetry and -1 not to restrict to even angles, +0.11 if the verts are really close, so it will stack up until they meet requirement
    angle = 43.11   
    
    allowedRotations = 200
    #if side is "lefUp" or side is "rightDown":
    #   angle = -angle
        
    isHor = False
    while isHor is False:
        for face in bm.faces: 
            for loop in face.loops:
                loop_uv = loop[uv_layer]
                if loop_uv.select is True:    
                    isHor = IsCornerHorizontal(uv_layer, verts, side, corner)
                    rotations = rotations +1
                    
                    if (rotations >=allowedRotations):
                        print("exceeded max allowed rotations")
                        return i*angle
                        
                    if isHor is False:   
                        RotateSelected(angle)
                        i=i+1
                        
    #print("i", i)                   
    return i*angle

def RotateSelected(angle):
    last_area = bpy.context.area.type
    bpy.context.area.type = 'IMAGE_EDITOR'
    
    last_pivot = bpy.context.space_data.pivot_point
    bpy.context.space_data.pivot_point = 'MEDIAN'

    bpy.ops.transform.rotate(value=radians(angle), axis=(-0, -0, -1), constraint_axis=(False, False, False), constraint_orientation='LOCAL', mirror=False, proportional='DISABLED', proportional_edit_falloff='SMOOTH', proportional_size=1)
    
    bpy.context.space_data.pivot_point = last_pivot
    bpy.context.area.type = last_area
    
    return


def FetchVerts(uv_layer, bm):
   
    verts = defaultdict(list)                #dict
    for face in bm.faces:
        isFaceSel = True
        for l in face.loops:
            luv = l[uv_layer]
            if luv.select is False:
                isFaceSel = False
                break
        
        if isFaceSel is True:
            for l in face.loops:
                luv = l[uv_layer]
                verts[(luv.uv.x, luv.uv.y)].append(luv.uv)
                    
    return verts

#def FetchVerts2(uv_layer, bm):
#    verts = defaultdict(list)                #dict
#    
#    for face in bm.faces:
#        for l in face.loops:
#            luv = l[uv_layer]
#            if luv.select is True:
#                verts[(luv.uv.x, luv.uv.y)].append(luv.uv)
#        
#    
#    return verts

def CountQuasiEqualVectors(v, list):
    i=0
    for e in list:
        if AreVectorsQuasiEqual(v,e):
            i=i+1
    return i

def FetchCorners(uv_layer, bm, selVerts):
    #this doesn't work for UV selection
    #for selV in reversed(bm.select_history):
    #   if isinstance(selV, bmesh.types.BMVert):
    #       lastSelV = selV
    #       break
    
    if len(selVerts) is 0:
        print("--error: nothing is selected.")
        return None, None, None, None
   
    #corners.append(filter by vectors that share location)
    corners = []
    [corners.append(v) for v in selVerts if CountQuasiEqualVectors(v, corners) is 0]
    
    #if there are only 4 "click selected" vertices (corners is here holder for filtered selVerts) 
    if len(corners) is 4:
        selVerts[:] = []
        selVerts.extend(corners)
        
    else:
        corners = []
        verts = FetchVerts(uv_layer, bm)
            
        for v in verts:
            if len(verts[v]) is 1:
                corners.append(verts[v][0])
         
        if len(corners) is not 4:
            print(len(corners), "corners found, 4 required")
            return None, None, None, None
        
    firstHighest = corners[0]
    for c in corners:
        if c.y > firstHighest.y:
            firstHighest = c    
    corners.remove(firstHighest)
    
    secondHighest = corners[0]
    for c in corners:
        if (c.y > secondHighest.y):
            secondHighest = c
    
    if firstHighest.x < secondHighest.x:
        leftUp = firstHighest
        rightUp = secondHighest
    else:
        leftUp = secondHighest
        rightUp = firstHighest
    corners.remove(secondHighest)
    
    firstLowest = corners[0]
    secondLowest = corners[1]
    
    if firstLowest.x < secondLowest.x:
        leftDown = firstLowest
        rightDown = secondLowest
    else:
        leftDown = secondLowest
        rightDown = firstLowest
    
    #print(leftUp, leftDown, rightUp, rightDown)
    return leftUp, leftDown, rightUp, rightDown

def FetchCornerFaces(uv_layer, bm, leftUpV, leftDownV, rightUpV, rightDownV):   
    for face in bm.faces: 
        isFaceSel = True
        for l in face.loops:        
            luv = l[uv_layer]
            if luv.select is False:
                isFaceSel = False
                break
        
        if isFaceSel is True:
            for l in face.loops:
                luv = l[uv_layer]
                
                #no elif or breaks because one face can have 1,2 or all 4 corners
                if AreVectorsQuasiEqual(luv.uv, leftUpV):
                    leftUpFace = face
             
                if AreVectorsQuasiEqual(luv.uv, leftDownV):
                    leftDownFace = face
                
                if AreVectorsQuasiEqual(luv.uv, rightUpV):
                    rightUpFace = face
               
                if AreVectorsQuasiEqual(luv.uv, rightDownV):
                    rightDownFace = face
                
    return leftUpFace, leftDownFace, rightUpFace, rightDownFace


def AreVectorsQuasiEqual(vect1, vect2, allowedError = 0.0001):
    if abs(vect1.x -vect2.x) <= allowedError and abs(vect1.y -vect2.y) <= allowedError:
        return True
    return False

class Vector(object):
    def __init__(self, x=0, y=0):
        self._x, self._y, = x, y

    def setx(self, x): self._x = float(x)
    def sety(self, y): self._y = float(y)       

    x = property(lambda self: float(self._x), setx)
    y = property(lambda self: float(self._y), sety)


class UvFace():
    leftUpVert = Vector()
    leftDownVert = Vector()
    rightUpVert = Vector()
    rightDownVert = Vector()
    
    def __init__(self, face=None):
        if face is not None:
            self.leftUpVert = face.leftUpVert
            self.leftDownVert = face.leftDownVert
            self.rightUpVert = face.rightUpVert
            self.rightDownVert = face.rightDownVert

class UvSquares(bpy.types.Operator):
    """Reshapes UV faces to a grid of equivalent squares"""
    bl_idname = "uv.uv_squares"
    bl_label = "UVs to grid of squares"

    @classmethod
    def poll(cls, context):
        return (context.mode == 'EDIT_MESH')

    def execute(self, context):
        main(context)
        return {'FINISHED'}

addon_keymaps = []

def menu_func(self, context):
    self.layout.operator(UvSquares.bl_idname)

def register():
    bpy.utils.register_class(UvSquares)
    #menu
    bpy.types.IMAGE_MT_uvs.append(menu_func)

    #handle the keymap
    wm = bpy.context.window_manager
    km = wm.keyconfigs.addon.keymaps.new(name='UV Editor', space_type='EMPTY')
    kmi = km.keymap_items.new(UvSquares.bl_idname, 'E', 'PRESS', alt=True)
    addon_keymaps.append(km)

def unregister():
    bpy.utils.unregister_class(UvSquares)
    bpy.types.IMAGE_MT_uvs.remove(menu_func)
    # handle the keymap
    wm = bpy.context.window_manager
    for km in addon_keymaps:
        wm.keyconfigs.addon.keymaps.remove(km)
    # clear the list
    addon_keymaps.clear()

if __name__ == "__main__":
    register()

    # test call
    bpy.ops.uv.uv_squares()

