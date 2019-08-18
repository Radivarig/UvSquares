Uv Squares
==
Blender's UV Editor tool that reshapes UV selection into grid.

Installation
--
Go to `Edit > Preferences > Addons > Install` and either select .zip file or the unzipped `uv_squares.py` file.

Location
--
`UV Editor > N Panel > UV Squares`

Features
--
* Reshape selected UV faces (quads) to **grid** of either:
    * equivalent **squares** (each square area is the same)
    * or by respect to **shape** of an active quad (area of rectangles can differ but they fit into straight lines)
* convert multiple islands at once (select more than one separate UV chunk)
* Align sequenced vertices on an **axis** (X or Y axis is determined by slope automatically):
    * make them **equally** distanced
* **Rip** faces (deselect vertices from unselected faces, as if there were seams)
* Join selected vertices to any closest unselected vertices
* Select single vertex and snap 2d cursor to it

Shortcuts
--
* **grid**/**aligning** is **Alt + E** 
* Rip faces is **Alt + V**
* Join vertices is **Shift + Alt + V**

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
* You can specify an **active quad** by making it the last selected face. If not, one face will **automatically** be taken
* 2d cursor is snapped to closest **corner** and is determining the direction for calculating the length of start and end of grid as well as **length** of one unit for square grid

**Rip faces**
* Rip/separate any selected faces
* Rip single **vertex**

**Join vertices**
* Snaps selected vertices to closest non selected
    * For faces, if you want to connect islands back to their original place - use stitch (shortcut: V, while stitching press I to toggle island)

Development
* When bumping versions increment both `bl_info` objects, one in `__init__.py` which is used for .zip install, and another in the main `uv_squares.py` file.

For any questions, bug reports or suggestions please contact me at **reslav.hollos@gmail.com**
