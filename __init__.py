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

from .uv_squares import *
