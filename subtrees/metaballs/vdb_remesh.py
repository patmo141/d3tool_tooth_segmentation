# Copyright 2018 Tommi Hyppänen, license: GNU General Public License v3.0

import platform

if platform.system() == 'Windows':
    from . import pyopenvdb_win as vdb
elif platform.system() == 'Darwin' and platform.release() == '19.2.0':
    from . import pyopenvdb_mac as vdb

else:
    print('we failed to import vdb due to OS incompatibility')
    
import numpy as np
import bpy
import bmesh

# import random
import pstats, io

DEBUG = False


def write_slow(mesh, ve, tr, qu):
    bm = bmesh.new()
    for co in ve.tolist():
        bm.verts.new(co)

    bm.verts.ensure_lookup_table()

    for face_indices in tr.tolist() + qu.tolist():
        bm.faces.new(tuple(bm.verts[index] for index in face_indices))

    return bm


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
    # me.validate(verbose=True)

    return me


def read_loops(mesh):
    loops = np.zeros((len(mesh.polygons)), dtype=np.int)
    mesh.polygons.foreach_get("loop_total", loops)
    return loops


def vdb_remesh(
    verts,
    tris,
    quads,
    iso,
    adapt,
    only_quads,
    vxsize,
    filter_iterations,
    filter_width,
    filter_style,
    filter_param,
    grid=None,
):

    iso *= vxsize

    def _read(verts, tris, quads, vxsize):
        vtransform = vdb.createLinearTransform(voxelSize=vxsize)

        if len(tris) == 0 and len(quads) == 0:
            grid = vdb.FloatGrid.createLevelSetFromPoints(
                verts, transform=vtransform, radius=vxsize * 2
            )
        elif len(tris) == 0:
            grid = vdb.FloatGrid.createLevelSetFromPolygons(
                verts, quads=quads, transform=vtransform
            )
        elif len(quads) == 0:
            grid = vdb.FloatGrid.createLevelSetFromPolygons(
                verts, triangles=tris, transform=vtransform
            )
        else:
            grid = vdb.FloatGrid.createLevelSetFromPolygons(
                verts, tris, quads, transform=vtransform
            )

        bb = grid.evalActiveVoxelBoundingBox()
        bb_size = (bb[1][0] - bb[0][0], bb[1][1] - bb[0][1], bb[1][2] - bb[0][2])

        return grid

    saved_grid = None
    if grid == None:
        grid = _read(verts, tris, quads, vxsize)
    else:
        saved_grid = grid
        grid = grid.deepCopy()

    def _write(gr):
        fit = filter_iterations if filter_iterations > 0 else 0
        if platform.system() == 'Darwin':
            for _ in range(fit):
                gr.gaussian(filter_param, filter_width)
            verts, tris, quads = gr.convertToPolygons(iso, adapt)

        else:
            verts, tris, quads = gr.convertToComplex(iso, adapt, fit, filter_width, filter_param)
        return (verts, tris, quads)

    return (_write(grid), grid if saved_grid == None else saved_grid)


def read_bmesh(bmesh):
    bmesh.verts.ensure_lookup_table()
    bmesh.faces.ensure_lookup_table()

    verts = [(i.co[0], i.co[1], i.co[2]) for i in bmesh.verts]
    qu, tr = [], []
    for f in bmesh.faces:
        if len(f.verts) == 4:
            qu.append([])
            for v in f.verts:
                qu[-1].append(v.index)
        if len(f.verts) == 3:
            tr.append([])
            for v in f.verts:
                tr[-1].append(v.index)

    return (np.array(verts), np.array(tr), np.array(qu))


#################### Blender side classes ##########################################################################


def get_voxel_res_object(self):
    return self.get("voxel_resolution_object", 20)


def set_voxel_res_object(self, value):
    limit = bpy.context.user_preferences.addons[__package__].preferences.max_voxel
    if value > limit:
        value = limit
    if value < 4:
        value = 4
    self["voxel_resolution_object"] = value


def get_voxel_res_world(self):
    return self.get("voxel_resolution_world", 20)


def set_voxel_res_world(self, value):
    limit = bpy.context.user_preferences.addons[__package__].preferences.max_voxel
    if value > limit:
        value = limit
    if value < 4:
        value = 4
    self["voxel_resolution_world"] = value


class OpenVDBsettings(bpy.types.PropertyGroup):
    names = {
        "voxel_size_def",
        "voxel_resolution_world",
        "voxel_resolution_object",
        "isovalue",
        "adaptivity",
        "filter_iterations",
        "filter_width",
        "filter_sigma",
        "only_quads",
        "smooth",
        "nearest",
    }

    voxel_size_def = bpy.props.EnumProperty(
        items=[
            ("relative", "Relative", "Voxel size is defined in relation to the object size"),
            ("absolute", "Absolute", "Voxel size is defined in world coordinates"),
        ],
        name="voxel_size_def",
        default="absolute",
    )

    voxel_resolution_world = bpy.props.IntProperty(
        name="Voxel resolution",
        description="Voxel resolution defined in world coordinates",
        get=get_voxel_res_world,
        set=set_voxel_res_world
        # min=4,
        # max=1000,
        # default=20,
    )

    voxel_resolution_object = bpy.props.IntProperty(
        name="Voxel resolution (relative)",
        description="Voxel resolution in relation to the objects longest bounding box edge",
        get=get_voxel_res_object,
        set=set_voxel_res_object
        # min=4,
        # max=1000,
        # default=50,
    )

    isovalue = bpy.props.FloatProperty(
        name="Isovalue", description="Isovalue", min=-3.0, max=3.0, default=0.0
    )

    adaptivity = bpy.props.FloatProperty(
        name="Adaptivity", description="Adaptivity", min=0.0, max=100.0, default=0.0
    )

    filter_iterations = bpy.props.IntProperty(
        name="Gaussian iterations", description="Gaussian iterations", min=0, max=20, default=0
    )

    filter_width = bpy.props.IntProperty(
        name="Gaussian width", description="Gaussian width", min=1, max=10, default=4
    )

    filter_sigma = bpy.props.FloatProperty(
        name="Gaussian sigma", description="Gaussian sigma", min=0.1, max=10.0, default=1.0
    )

    only_quads = bpy.props.BoolProperty(
        name="Quads only", description="Construct the mesh using only quad topology", default=False
    )

    smooth = bpy.props.BoolProperty(
        name="Smooth", description="Smooth shading toggle", default=True
    )

    nearest = bpy.props.BoolProperty(
        name="Project to nearest",
        description="Project generated mesh points to nearest surface point",
        default=False,
    )


def draw_props(vdb, layout):
    row = layout.row()
    row.prop(vdb, "voxel_size_def", expand=True, text="Island margin quality/performance")

    row = layout.row()
    col = row.column(align=True)
    if vdb.voxel_size_def == "relative":
        col.prop(vdb, "voxel_resolution_object")
    else:
        col.prop(vdb, "voxel_resolution_world")

    row = layout.row()
    col = row.column(align=True)
    col.prop(vdb, "isovalue")
    col.prop(vdb, "adaptivity")

    row = layout.row()
    col = row.column(align=True)

    col.prop(vdb, "filter_iterations")
    col.prop(vdb, "filter_width")
    col.prop(vdb, "filter_sigma")

    row = layout.row()
    # row.prop(self, "only_quads")
    row.prop(vdb, "smooth")
    row.prop(vdb, "nearest")


class OBJECT_OT_VDBRemesh(bpy.types.Operator):
    """OpenVDB Remesh"""

    bl_idname = "object.vdbremesh_op"
    bl_label = "OpenVDB remesh"
    bl_options = {"REGISTER", "UNDO"}

    op_settings = bpy.props.PointerProperty(type=OpenVDBsettings)

    grid = None
    grid_voxelsize = None
    max_polys_reached = False

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def invoke(self, context, event):
        self.vdb_settings = self.op_settings
        # print(self.vdb_settings, dir(self.vdb_settings), self.vdb_settings.__dict__)

        if context.scene.openvdb_from_panel == True:
            # copy values for properties from panel
            for k in OpenVDBsettings.names:
                setattr(self.vdb_settings, k, getattr(context.scene.openvdb_settings, k))

        return self.execute(context)

    def execute(self, context):
        addon_prefs = context.user_preferences.addons[__package__].preferences

        context_mode = context.object.mode
        bpy.ops.object.mode_set(mode="OBJECT")

        # enforce global settings for  min and max values
        # if self.voxel_size_world < addon_prefs.min_absolute_voxel:
        #     self.voxel_size_world = addon_prefs.min_absolute_voxel

        # if self.voxel_size_world > addon_prefs.max_absolute_voxel:
        #     self.voxel_size_world = addon_prefs.max_absolute_voxel

        if DEBUG:
            pr = cProfile.Profile()
            pr.enable()

        voxel_size = 0.05

        if self.vdb_settings.voxel_size_def == "relative":
            voxel_size = (
                max(context.active_object.dimensions)
                * 1.0
                / self.vdb_settings.voxel_resolution_object
            )
        else:
            voxel_size = 1.0 / self.vdb_settings.voxel_resolution_world

        # apply modifiers for the active object before remeshing
        for mod in context.active_object.modifiers:
            try:
                bpy.ops.object.modifier_apply(modifier=mod.name)
            except RuntimeError as ex:
                print(ex)

        # apply scale
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

        # start remesh
        me = context.active_object.data

        if self.grid is not None or self.grid_voxelsize != voxel_size:
            # caching
            self.only_verts = False
            self.grid = None

            bm = bmesh.new()
            bm.from_mesh(me)

            if len(bm.faces) == 0:
                self.only_verts = True

            if not self.only_verts:
                loops = read_loops(me)
                if np.max(loops) > 4:
                    print("Mesh has ngons! Triangulating...")
                    bmesh.ops.triangulate(
                        bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY"
                    )

            self.grid_voxelsize = voxel_size
            nverts, ntris, nquads = read_bmesh(bm)
            self.vert_0 = len(nverts)
            bm.free()
        else:
            nverts, ntris, nquads = None, None, None

        new_mesh, self.grid = vdb_remesh(
            nverts,
            ntris,
            nquads,
            self.vdb_settings.isovalue,
            (self.vdb_settings.adaptivity / 100.0) ** 2,
            self.vdb_settings.only_quads,
            voxel_size,
            self.vdb_settings.filter_iterations,
            self.vdb_settings.filter_width,
            "blur",
            self.vdb_settings.filter_sigma,
            grid=self.grid,
        )

        print("vdb_remesh: new mesh {}".format([i.shape for i in new_mesh]))
        self.vert_1 = len(new_mesh[0])
        self.face_1 = len(new_mesh[1]) + len(new_mesh[2])

        if self.face_1 < addon_prefs.max_polygons:
            self.max_polys_reached = False

            remeshed = write_fast(*new_mesh)

            if self.vdb_settings.smooth:
                values = [True] * len(remeshed.polygons)
                remeshed.polygons.foreach_set("use_smooth", values)
                # for f in remeshed.polygons:
                #     f.use_smooth = True
                # bpy.ops.object.shade_smooth()

            context.active_object.data = remeshed

            if self.vdb_settings.nearest:

                def _project_wrap():
                    temp_object = bpy.data.objects.new("temp.remesher.947", me)
                    temp_object.matrix_world = context.active_object.matrix_world

                    bpy.ops.object.modifier_add(type="SHRINKWRAP")
                    context.object.modifiers["Shrinkwrap"].target = temp_object

                    for mod in context.active_object.modifiers:
                        try:
                            bpy.ops.object.modifier_apply(modifier=mod.name)
                        except RuntimeError as ex:
                            print(ex)

                    objs = bpy.data.objects
                    objs.remove(objs["temp.remesher.947"], do_unlink=True)

                _project_wrap()

        else:
            self.max_polys_reached = True

        if DEBUG:
            pr.disable()
            s = io.StringIO()
            sortby = "cumulative"
            ps = pstats.Stats(pr, stream=s)
            ps.strip_dirs().sort_stats(sortby).print_stats()
            print(s.getvalue())

        print("vdb_remesh: exit")

        bpy.ops.object.mode_set(mode=context_mode)

        return {"FINISHED"}

    def draw(self, context):
        addon_prefs = context.user_preferences.addons[__package__].preferences
        # vdb_settings = context.scene.openvdb_settings

        layout = self.layout
        col = layout.column()

        if self.max_polys_reached:
            row = col.row()
            row.label(text="Max poly count reached (>{})".format(addon_prefs.max_polygons))
            row = col.row()
            row.label(text="Skipping writing to mesh.")

        draw_props(self.vdb_settings, layout)

        if hasattr(self, "vert_0"):
            infotext = "Change: {:.2%}".format(self.vert_1 / self.vert_0)
            row = layout.row()
            row.label(text=infotext)
            row = layout.row()
            row.label(text="Verts: {}, Polys: {}".format(self.vert_1, self.face_1))

            row = layout.row()
            row.label(text="Cache: {} voxels".format(self.grid.activeVoxelCount()))


class OBJECT_PT_VDBRemesh(bpy.types.Panel):
    """OpenVDB remesh operator panel"""

    bl_label = "VDB remesh"
    bl_idname = "object.vdbremesh_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "Retopology"

    def draw(self, context):
        addon_prefs = context.user_preferences.addons[__package__].preferences
        layout = self.layout

        if context.object.mode == "SCULPT" and addon_prefs.suppress_warnings == False:
            text = ["WARNING!", "Undo is very", "unreliable in", "sculpt mode."]
            for t in text:
                row = layout.row()
                row.alert = True
                row.label(text=t)

        row = layout.row()
        row.prop(context.scene, "openvdb_from_panel")
        if context.scene.openvdb_from_panel == True:
            draw_props(context.scene.openvdb_settings, layout)

        row = layout.row()
        row.scale_y = 2.0
        row.operator(OBJECT_OT_VDBRemesh.bl_idname, text="OpenVDB remesh")


classes = (OpenVDBsettings, OBJECT_OT_VDBRemesh, OBJECT_PT_VDBRemesh)


def register():
    print("OpenVDB register called")
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.openvdb_settings = bpy.props.PointerProperty(type=OpenVDBsettings)
    bpy.types.Scene.openvdb_from_panel = bpy.props.BoolProperty(
        name="Values from panel", description="Use settings from panel", default=False
    )


def unregister():
    print("OpenVDB unregister called")
    del bpy.types.Scene.openvdb_from_panel
    del bpy.types.Scene.openvdb_settings
    for c in reversed(classes):
        bpy.utils.unregister_class(c)

