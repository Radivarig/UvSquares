# UV Squares
Blender's UV Editor tool that reshapes UV quad selection into a grid.

## Installation
Go to `Edit > Preferences > Addons > Install` and either select .zip file or the unzipped `uv_squares.py` file.

## Location
`UV Editor > N Panel > UV Squares`

## Support
If you need help with the addon or you want to support me back please do so over BlenderMarket ❤️:
https://blendermarket.com/products/uv-squares

## Affiliates
If you are advertising the addon through a blog/course/video please contact me and I will give you a percent of the sales!

## Features
* Reshape selected UV faces (quads) to **grid** of either:
    * equivalent **squares** (each square area is the same)
    * or by respect to **shape** of an active quad (area of rectangles can differ but they fit into straight lines)
* convert multiple islands at once (select more than one separate UV chunk)
* Align sequenced vertices on an **axis** (X or Y axis is determined by slope automatically):
    * make them **equally** distanced
* Join selected faces/vertices to closest unselected vertices
* Select single vertex and snap 2d cursor to it

## Shortcut
* **Grid**/**Align**: **Alt + E**

## Notes
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

**Join vertices**
* Snaps selected vertices to closest non selected
    * For faces, if you want to connect islands back to their original place:
     - use stitch (shortcut: Alt V, while stitching press I to toggle island)

## Development
* When bumping versions increment both `bl_info` objects, one in `__init__.py` which is used for .zip install, and another in the main `uv_squares.py` file.