'''
Created on Jan 1, 2021

@author: Patrick
'''

import math
import time

import bpy
import bmesh
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

from d3lib.bmesh_utils.bmesh_delete import bmesh_fast_delete, bmesh_delete
from d3guard.subtrees.metaballs.vdb_tools import remesh_bme
from d3guard.subtrees.metaballs.vdb_remesh import read_bmesh, convert_vdb

from ..subtrees.bmesh_utils.bmesh_utilities_common import bme_rip_vertex, bbox_center, bound_box_bmverts
from ..subtrees.bmesh_utils.bmesh_utilities_common import edge_loops_from_bmedges_topo, offset_bmesh_edge_loop, collapse_ed_simple
from ..subtrees.geometry_utils.loops_tools import relax_loops_util
from ..subtrees.geometry_utils.transformations import clockwise_loop



from ..tooth_numbering import upper_right, upper_left, lower_left, lower_right, upper_view_order, lower_view_order, data_tooth_label
  
from .. import tooth_numbering

def get_teeth(context):                                     
    
    selected_teeth = [ob for ob in context.scene.objects if ob.type == 'MESH' and 'tooth' in ob.data.name and ob.select]
    all_teeth = [ob for ob in context.scene.objects if ob.type == 'MESH' and 'tooth' in ob.data.name]
    upper_obs = [ob for ob in all_teeth if tooth_numbering.data_tooth_label(ob.name) in tooth_numbering.upper_teeth]
    lower_obs = [ob for ob in all_teeth if tooth_numbering.data_tooth_label(ob.name) in tooth_numbering.lower_teeth]
    
    return all_teeth, selected_teeth, upper_obs, lower_obs

def get_convex(teeth):
    convex_teeth = [bpy.data.objects.get(ob.name + " Convex") for ob in teeth if ob.name + " Convex" in bpy.data.objects]     
    return convex_teeth

def add_to_bmesh(bme, ob, transform = False):
    
    mx = ob.matrix_world
    imx = mx.inverted()
    
    if transform:
        ob.data.transform(mx)
    bme.from_mesh(ob.data)
    if transform:
        ob.data.transform(imx)
   
def make_temp(ob):    
    
    new_name = ob.name.split(' ')[0] + ' Temp Shell'
    if new_name in bpy.data.objects:
        new_ob = bpy.data.objects.get(new_name)
    else:
        me = bpy.data.meshes.new(new_name)
        new_ob = bpy.data.objects.new(new_name, me)
        bpy.context.scene.objects.link(new_ob)
        new_ob.parent = ob
        new_ob.matrix_world = ob.matrix_world
    
    new_ob["d3output"] = True
    
    
    bme_subtract = bmesh.new()
    bme_join = bmesh.new()

       
    r_name = ob.name.split(' ')[0] + ' root_prep'
    root = bpy.data.objects.get(r_name)
        
    add_to_bmesh(bme_join, ob)
        
    if ob.get('PREPARED') == 1:
        add_to_bmesh(bme_subtract, root)
    
        
        
    bmesh.ops.triangulate(bme_subtract, faces = bme_subtract.faces[:])
    bmesh.ops.triangulate(bme_join, faces = bme_join.faces[:])  
    voxel_size = .1
    verts0, tris0, quads0 = read_bmesh(bme_join)         
    vdb_base = convert_vdb(verts0, tris0, quads0, voxel_size)
    bme_join.free()
    
   
    bme_subtract.normal_update()
    for v in bme_subtract.verts:
        v.co += .15 * v.normal
        
    verts1, tris1, quads1 = read_bmesh(bme_subtract)         
    vdb_subtract = convert_vdb(verts1, tris1, quads1, voxel_size)
    bme_subtract.free()
    
    vdb_base.difference(vdb_subtract, False)
    
    ve, tr, qu = vdb_base.convertToPolygons(0.0, (3.0/100.0)**2)

    bm = bmesh.new()
    for co in ve.tolist():
        bm.verts.new(co)

    bm.verts.ensure_lookup_table()    
    bm.faces.ensure_lookup_table()    

    for face_indices in tr.tolist() + qu.tolist():
        bm.faces.new(tuple(bm.verts[index] for index in reversed(face_indices)))

    bm.normal_update()
    
    bm.to_mesh(new_ob.data)
    bm.free()
    
    
    return new_ob
        
class AITeeth_OT_make_temps_individual(bpy.types.Operator):
    """Create Temp Shells"""
    bl_idname = "ai_teeth.make_individual_temp_shells"
    bl_label = "Make Temp Shells"

    
    @classmethod
    def poll(cls, context):

        return True

    def invoke(self, context, event):
        
        self.hidden_obs = [ob for ob in bpy.data.objects if ob.hide]
        self.visible_obs = [ob for ob in bpy.data.objects if not ob.hide]
        for ob in bpy.data.objects:
            ob.hide = True
            ob.select = False
            
        all, sel, upper, lower = get_teeth(context)

                
        self.upper_teeth = get_convex(upper)
        self.lower_teeth = get_convex(lower)
        
        for ob in self.upper_teeth + self.lower_teeth:
            if ob.get('EXTRACT') == None:
                #create the custom ID prop
                ob['EXTRACT'] = False
                ob.hide = False
                
            else:
                print('ALREADY EXTRACTED')
                ob.hide = ob.get('EXTRACT') == 1
                ob.select = ob.get('EXTRACT') == True
                

        
        
        self.upper_teeth.sort(key = lambda x: upper_view_order.index(data_tooth_label(x.name.split(' ')[0])))
        self.lower_teeth.sort(key = lambda x: lower_view_order.index(data_tooth_label(x.name.split(' ')[0])))
        
        self.upper_right_teeth = [ele for ele in self.upper_teeth if data_tooth_label(ele.name.split(' ')[0]) in upper_right]
        self.upper_left_teeth = [ele for ele in self.upper_teeth if data_tooth_label(ele.name.split(' ')[0]) in upper_left]
        
        self.lower_left_teeth = [ele for ele in self.lower_teeth if data_tooth_label(ele.name.split(' ')[0]) in lower_left]
        self.lower_right_teeth = [ele for ele in self.lower_teeth if data_tooth_label(ele.name.split(' ')[0]) in lower_right]
        
        
        return context.window_manager.invoke_props_dialog(self, width = 700)
           
    def execute(self, context):
        print('MAIN FUNCTION')
        
        
        
        obs = [ob for ob in bpy.data.objects if 'Convex' in ob.name and ob.select]
        upper_obs = [ob for ob in obs if data_tooth_label(ob.name.split(' ')[0]) in tooth_numbering.upper_teeth]
        lower_obs = [ob for ob in obs if data_tooth_label(ob.name.split(' ')[0]) in tooth_numbering.lower_teeth]
        
        if len(upper_obs):
            
            for ob in upper_obs:
                make_temp(ob)
            for ob in lower_obs:
                make_temp(ob)
        
        #TODO, set up the modal operator
        return {'FINISHED'}
    
    def draw(self, context):
        
        
        
        row = self.layout.row()
        row.label('Make Temp Bridge')
        
        row = self.layout.row()
        split = row.split(percentage = .5)
        
        col1 = split.column()
        rowUR = col1.row()
        
        for ob in self.upper_right_teeth:
            rowUR.prop(ob, "select", text = ob.name)
        rowLR = col1.row()
        for ob in self.lower_right_teeth:
            rowLR.prop(ob, "select", text = ob.name)
        
        col2 = split.column()
        rowUL = col2.row()
        for ob in self.upper_left_teeth:
            rowUL.prop(ob, "select", text = ob.name)
        rowLL = col2.row()
        for ob in self.lower_left_teeth:
            rowLL.prop(ob, "select", text = ob.name)   

def register():
    bpy.utils.register_class(AITeeth_OT_make_temps_individual)


def unregister():
    bpy.utils.unregister_class(AITeeth_OT_make_temps_individual)