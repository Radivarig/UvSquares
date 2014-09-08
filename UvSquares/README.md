Uv Squares
==
Blender's UV Editor tool that reshapes UV selection into grid. 

Features
--
(Best place to start is **toolbar**)
* Reshape selected UV faces to **grid** of either:
    * equivalent **squares** 
    * or by respect to **shape**
* Align sequenced vertices on **axis** (X or Y axis is determined by slope automatically) :
    * make them **equally** distanced
* **Rip** faces
* Join selected vertices to any closest unselected vertices 

Shortcuts
--
* **[**grid**]/[**aligning**]** is **alt + [E]** 
    * pressed once for **[**shape**]/[**align to axis**]**
    * pressed **twice** for **[**squares**]/[**equal distance**]**
        * counter-clockwise for grid is **shift** + alt + [E] 
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
* Works on any UV selection that is a "potential rectangle"
    * **n**Rows times **m**Columns grid, exactly **4** corners
* 2d cursor is snapped to closest corner and is determining the direction for calculating the length of start and end of grid as well as **length** of one unit for square grid.
* Length is calculated from leftUp to rightUp, rightUp to rightDown etc. (**clockwise**)
    * counter-clockwise is triggered with **shift**
* Selection should be under 2200 faces at a time
* Selected UV faces should not overlap
* Works best on selection that resembles the desired grid

**Rip faces**
* Rip selected faces, separate them and create a new island.
* Single **vertex** can be ripped as well


**Join vertices**
* Snaps selected vertices to closest non selected
    * For faces, if you want to connect islands back to their original place - use stitch (shortcut: V, while stitching press I to toggle island)

**Debugging** 
* If there is no behaviour:
    * separate vertices from one another
    * convert part by part to see where it's stuck
    * rotate or move corners a bit 
    * scale everything up and reuse

For any questions, bug reports or suggestions please contact me at **reslav.hollos@gmail.com**
