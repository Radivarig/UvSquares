Uv Squares
==
Blender's UV Editor tool that reshapes UV selection into grid. 

Features
--
(Best place to start is **toolbar**)
* Reshape selected UV faces (quads) to **grid** of either:
    * equivalent **squares** 
    * or by respect to **shape**
* Align sequenced vertices on **axis** (X or Y axis is determined by slope automatically) :
    * make them **equally** distanced
* **Rip** faces
* Join selected vertices to any closest unselected vertices 

Shortcuts
--
* [**grid**]/[**aligning**] is **alt + [E]** 
* Rip faces is **alt + [V]**
* Join vertices is **shift + alt + [V]**

Notes
--
**Aligning to axis**
* All vertices have to be ordered/sequenced by x/y value depending of X/Y axis that they are getting aligned to. Otherwise you will have swapped vertices in the result.
* What script does here:
    * set pivot to cursor (sets it back after)
    * 2d cursor will snap to closest vertex and the alignment will be made at that verts x/y value, depending on the axis
    * restrict scale to axis (recognize X or Y by the slope) 
    * scale to 0 to where the cursor has snapped
    
**Reshaping to grid**
* Works on any UV selection shape of quad faces
* You can specify active quad by making it the last selected face, if not one face will automatically be taken as reference quad 
* 2d cursor is snapped to closest corner and is determining the direction for calculating the length of start and end of grid as well as **length** of one unit for square grid

**Rip faces**
* Rip/separate any selected faces
* Rip single **vertex**

**Join vertices**
* Snaps selected vertices to closest non selected
    * For faces, if you want to connect islands back to their original place - use stitch (shortcut: V, while stitching press I to toggle island)

For any questions, bug reports or suggestions please contact me at **reslav.hollos@gmail.com**
