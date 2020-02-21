# ##### BEGIN GPL LICENSE BLOCK #####
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, version 2 of the license.

#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.

#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####

bl_info = {
    "name": "OpenVDB remesh",
    "category": "Mesh",
    "description": "OpenVDB operations",
    "author": "Tommi Hyppänen (ambi)",
    "location": "3D view > Tools > Retopology",
    "version": (1, 6, 6),
    "blender": (2, 79, 0),
}


# import/reload all source files
if "bpy" in locals():
    import importlib

    importlib.reload(vdb_remesh)
else:
    from . import vdb_remesh

import bpy
import platform

from bpy_extras.object_utils import AddObjectHelper
import bmesh


if platform.system() == 'Windows':
    from . import pyopenvdb_win as vdb
elif platform.system() == 'Darwin' and platform.release() == '19.2.0':
    from . import pyopenvdb_mac as vdb

else:
    print('we failed to import vdb due to OS incompatibility')
    


import numpy as np
import time

from bpy.types import AddonPreferences
from bpy.props import IntProperty, BoolProperty

MIN_VXSIZE = 0.005
ISO_SURFER = True


class VDBRemeshAddonPreferences(AddonPreferences):
    bl_idname = __name__

    max_polygons = IntProperty(name="Maximum polygons", default=10000000)
    max_voxel = IntProperty(name="Maximum voxels", default=1000)
    suppress_warnings = BoolProperty(name="Suppress warnings", default=False)
    # min_absolute_voxel: FloatProperty(name="Minimum absolute voxel size", default=0.005)
    # max_absolute_voxel: FloatProperty(name="Maximum absolute voxel size", default=0.5)

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, "max_polygons")
        row.prop(self, "max_voxel")
        row.prop(self, "suppress_warnings")

        # col = layout.column()
        # col.label(text="World space voxel size setting")
        # row = col.row()
        # row.prop(self, "min_absolute_voxel")
        # row.prop(self, "max_absolute_voxel")


def add_isosurf(self, context):
    mesh = bpy.data.meshes.new(name="IsoSurface")
    obj = bpy.data.objects.new("IsoSurface", mesh)
    bpy.context.scene.objects.link(obj)
    obj["IsoSurfer"] = True
    obj.IsoSurf_res = True


class OBJECT_OT_add_isosurf(bpy.types.Operator, AddObjectHelper):
    bl_idname = "mesh.add_isosurf"
    bl_label = "Add IsoSurface Object"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        add_isosurf(self, context)

        return {"FINISHED"}


def add_isosurf_button(self, context):
    test_group = bpy.data.node_groups.new("testGroup", "ShaderNodeTree")
    self.layout.operator(
        OBJECT_OT_add_isosurf.bl_idname, text="IsoSurface", icon="OUTLINER_DATA_META"
    )


def isosurf_prerender(context):
    scn = bpy.context.scene
    scn.IsoSurf_context = "RENDER"
    isosurf(context)


def isosurf_postrender(context):
    scn = bpy.context.scene
    scn.IsoSurf_context = "WINDOW"


def isosurf_frame(context):
    scn = bpy.context.scene
    if scn.IsoSurf_context == "WINDOW":
        isosurf(context)


def write_fast(ve, tr, qu):
    me = bpy.data.meshes.new("testmesh")

    quadcount = len(qu)
    tricount = len(tr)

    me.vertices.add(count=len(ve))

    loopcount = quadcount * 4 + tricount * 3
    facecount = quadcount + tricount

    me.loops.add(loopcount)
    me.polygons.add(facecount)

    face_lengths = np.zeros(facecount, dtype=np.int)
    face_lengths[:tricount] = 3
    face_lengths[tricount:] = 4

    loops = np.concatenate((np.arange(tricount) * 3, np.arange(quadcount) * 4 + tricount * 3))

    # [::-1] makes normals consistent (from OpenVDB)
    v_out = np.concatenate((tr.ravel()[::-1], qu.ravel()[::-1]))

    me.vertices.foreach_set("co", ve.ravel())
    me.polygons.foreach_set("loop_total", face_lengths)
    me.polygons.foreach_set("loop_start", loops)
    me.polygons.foreach_set("vertices", v_out)

    me.update(calc_edges=True)

    return me


def isosurf(context):
    scn = bpy.context.scene

    stime = time.clock()
    SurfList = []
    for i, obj in enumerate(bpy.context.scene.objects):
        if "IsoSurfer" in obj:
            obsurf = obj
            mesurf = obj.data
            res = obj.IsoSurf_res

            SurfList.append([(obsurf, mesurf, res)])

            for item in obj.IsoSurf:
                if item.active == True:
                    if item.obj != "":
                        if item.psys != "":
                            SurfList[-1].append((item.obj, item.psys))

    for surfobj in SurfList:
        print("Calculating isosurface, for frame:", bpy.context.scene.frame_current)

        for obj, psys in surfobj[1:]:
            psys = bpy.data.objects[obj].particle_systems[psys]

            ploc = []
            stime = time.clock()

            palive = False
            for par in range(len(psys.particles)):
                if psys.particles[par].alive_state == "ALIVE":
                    ploc.append(psys.particles[par].location)
                    palive = True

            if palive:
                print("  pack particles:", time.clock() - stime, "sec")

                vxsize = scn.isosurface_voxelsize
                sradius = scn.isosurface_sphereradius
                ssteps = scn.isosurface_smoothsteps

                vtransform = vdb.createLinearTransform(voxelSize=vxsize)
                grid = vdb.FloatGrid.createLevelSetFromPoints(
                    np.array(ploc), transform=vtransform, radius=sradius
                )
                # iso, adaptivity, gaussian iterations, gaussian kernel size, gaussian sigma
                verts, tris, quads = grid.convertToComplex(0.0, 0.01, ssteps, 4, 0.8)

                print("  vdb remesh:", time.clock() - stime, "sec")
                stime = time.clock()

                # TODO: eats all memory & resets materials
                # obsurf.data = write_fast(verts, tris, quads)
                # bpy.ops.object.shade_smooth()
                # scn.update()

                bm = bmesh.new()

                bm.from_mesh(mesurf)
                bm.clear()

                for co in verts.tolist():
                    bm.verts.new(co)

                bm.verts.ensure_lookup_table()
                bm.faces.ensure_lookup_table()

                for face_indices in tris.tolist() + quads.tolist():
                    bm.faces.new(tuple(bm.verts[index] for index in face_indices[::-1]))

                for f in bm.faces:
                    f.smooth = True

                bm.to_mesh(mesurf)
                bm.free()

                mesurf.calc_normals()

                scn.update()

                print("  write:", time.clock() - stime, "sec")


class OBJECT_UL_IsoSurf(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        split = layout.split(0.1)
        split.label(str(index))
        split.prop(item, "name", text="", emboss=False, translate=False, icon="OUTLINER_OB_META")
        split.prop(item, "active", text="")


class IsoSurferPanel(bpy.types.Panel):
    bl_label = "VDB remesh particles"
    bl_idname = "OBJECT_PT_ui_list_example"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "Retopology"

    def draw(self, context):
        obj = context.object

        if obj != None and "IsoSurfer" in obj:
            layout = self.layout
            box = layout.box()

            # row = box.row()
            # row.prop(obj,"IsoSurf_res",text = "Voxel size:")
            row = box.row()
            col = row.column(align=True)
            col.prop(context.scene, "isosurface_voxelsize", text="Voxel size")
            col.prop(context.scene, "isosurface_sphereradius", text="Particle radius")
            col.prop(context.scene, "isosurface_smoothsteps", text="Smoothing steps")

            row = box.row()
            row.template_list("OBJECT_UL_IsoSurf", "", obj, "IsoSurf", obj, "IsoSurf_index")

            col = row.column(align=True)
            col.operator("op.isosurfer_item_add", icon="ZOOMIN", text="").add = True
            col.operator("op.isosurfer_item_add", icon="ZOOMOUT", text="").add = False

            if obj.IsoSurf and obj.IsoSurf_index < len(obj.IsoSurf):
                row = box.row()
                row.prop(obj.IsoSurf[obj.IsoSurf_index], "active", text="Active")
                row = box.row()
                row.label("Object: ")
                row.prop_search(
                    obj.IsoSurf[obj.IsoSurf_index], "obj", context.scene, "objects", text=""
                )

                if obj.IsoSurf[obj.IsoSurf_index].obj != "":
                    if bpy.data.objects[obj.IsoSurf[obj.IsoSurf_index].obj].type != "MESH":
                        obj.IsoSurf[obj.IsoSurf_index].obj = ""
                    else:
                        row = box.row()
                        row.label("Particles: ")
                        row.prop_search(
                            obj.IsoSurf[obj.IsoSurf_index],
                            "psys",
                            bpy.data.objects[obj.IsoSurf[obj.IsoSurf_index].obj],
                            "particle_systems",
                            text="",
                        )

        else:
            layout = self.layout
            box = layout.box()
            row = box.row()
            row.label("Please select an isosurface object!", icon="ERROR")


class OBJECT_OT_isosurfer_add(bpy.types.Operator):
    bl_label = "Add/Remove items from IsoSurf obj"
    bl_idname = "op.isosurfer_item_add"
    add = bpy.props.BoolProperty(default=True)

    def invoke(self, context, event):
        add = self.add
        ob = context.object
        if ob != None:
            item = ob.IsoSurf
            if add:
                item.add()
                l = len(item)
                item[-1].name = "IsoSurf." + str(l)
                item[-1].active = True
                # item[-1].res = 0.25
                item[-1].id = l
            else:
                index = ob.IsoSurf_index
                item.remove(index)

        return {"FINISHED"}


class IsoSurf(bpy.types.PropertyGroup):
    active = bpy.props.BoolProperty()
    id = bpy.props.IntProperty()
    obj = bpy.props.StringProperty()
    psys = bpy.props.StringProperty()


def register():
    bpy.utils.register_class(VDBRemeshAddonPreferences)
    vdb_remesh.register()
    # bpy.utils.register_class(vdb_remesh.OBJECT_OT_VDBRemesh)
    # bpy.utils.register_class(vdb_remesh.OBJECT_PT_VDBRemesh)

    if ISO_SURFER:

        bpy.utils.register_class(OBJECT_OT_add_isosurf)
        bpy.utils.register_class(IsoSurferPanel)
        bpy.types.INFO_MT_mesh_add.append(add_isosurf_button)
        # bpy.utils.register_class(IsoSurf)
        bpy.utils.register_module(__name__)

        bpy.types.Object.IsoSurf = bpy.props.CollectionProperty(type=IsoSurf)
        bpy.types.Object.IsoSurf_index = bpy.props.IntProperty()
        bpy.types.Object.IsoSurf_res = bpy.props.FloatProperty()
        bpy.types.Object.IsoSurf_preview = bpy.props.BoolProperty()
        bpy.types.Scene.IsoSurf_context = bpy.props.StringProperty(default="WINDOW")

        bpy.types.Scene.isosurface_voxelsize = bpy.props.FloatProperty(
            name="isosurface_voxelsize", default=0.025, min=MIN_VXSIZE, max=1.0
        )
        bpy.types.Scene.isosurface_sphereradius = bpy.props.FloatProperty(
            name="isosurface_sphereradius", default=0.05, min=MIN_VXSIZE * 2.0, max=2.0
        )
        bpy.types.Scene.isosurface_smoothsteps = bpy.props.IntProperty(
            name="isosurface_smoothsteps", default=2, min=0, max=20
        )

        if "isosurf_frame" not in [i.__name__ for i in bpy.app.handlers.frame_change_post]:
            print("create isosurfer handlers...")
            # print(bpy.app.handlers.frame_change_post)
            bpy.app.handlers.persistent(isosurf_frame)
            bpy.app.handlers.frame_change_post.append(isosurf_frame)
            bpy.app.handlers.persistent(isosurf_prerender)
            bpy.app.handlers.render_pre.append(isosurf_prerender)
            bpy.app.handlers.persistent(isosurf_postrender)
            bpy.app.handlers.render_post.append(isosurf_postrender)
            bpy.app.handlers.render_cancel.append(isosurf_postrender)
            bpy.app.handlers.render_complete.append(isosurf_postrender)
            print("isosurfer handler created successfully!")


def unregister():
    vdb_remesh.unregister()
    bpy.utils.unregister_class(VDBRemeshAddonPreferences)
    # bpy.utils.unregister_class(vdb_remesh.OBJECT_OT_VDBRemesh)
    # bpy.utils.unregister_class(vdb_remesh.OBJECT_PT_VDBRemesh)

    if ISO_SURFER:

        bpy.utils.unregister_class(OBJECT_OT_add_isosurf)
        bpy.utils.unregister_class(IsoSurferPanel)
        bpy.types.INFO_MT_mesh_add.remove(add_isosurf_button)
        bpy.utils.unregister_module(__name__)
        # bpy.utils.unregister_class(IsoSurf)
        del bpy.types.Object.IsoSurf
