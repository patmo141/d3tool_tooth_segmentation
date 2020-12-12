'''
Created on Nov 27, 2019

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

from ..tooth_numbering import data_tooth_label
from .. import tooth_numbering

from .get_reduction_shell import make_reduction_shells

 

def add_to_bmesh(bme, ob):
    
    mx = ob.matrix_world
    imx = mx.inverted()
    
    ob.data.transform(mx)
    bme.from_mesh(ob.data)
    ob.data.transform(imx)
   
def make_model(gingiva, teeth):    
    
    
    #get gingiva BVH
    
    bme_subtract = bmesh.new()
    bme_join = bmesh.new()
    
    add_to_bmesh(bme_join, gingiva)
    for ob in teeth:
        if ob.get('EXTRACT'):
            continue
        r_name = ob.name.split(' ')[0] + ' root_prep'
        root = bpy.data.objects.get(r_name)
        
        if ob.get('REMOVABLE_DIE'):
            
            if root:
                add_to_bmesh(bme_subtract, root)
            add_to_bmesh(bme_subtract, ob)
        
            continue
        
        if not ob.get('PREPARED'):  #add the tooth to it
            add_to_bmesh(bme_join , ob)
        
        if root:
            add_to_bmesh(bme_join, root)
    
    bmesh.ops.triangulate(bme_subtract, faces = bme_subtract.faces[:])
    bmesh.ops.triangulate(bme_join, faces = bme_join.faces[:])  
    voxel_size = .125
    verts0, tris0, quads0 = read_bmesh(bme_join)         
    vdb_base = convert_vdb(verts0, tris0, quads0, voxel_size)
    bme_join.free()
    
   
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
    
    
    return bm
        
class AITeeth_OT_make_diagnostic_model(bpy.types.Operator):
    """Create roots and preparations from teeth"""
    bl_idname = "ai_teeth.root_preps"
    bl_label = "Make Diagnostic Model(s)"

    
    
    
    @classmethod
    def poll(cls, context):

        return True

    def invoke(self, context, event):

        
        return context.window_manager.invoke_props_dialog(self, width = 300)
    

            
    def execute(self, context):
        print('MAIN FUNCTION')
        
        
        upper_ging = bpy.data.objects.get('Upper Gingiva')
        lower_ging = bpy.data.objects.get('Lower Gingiva')
        
        obs = [ob for ob in bpy.data.objects if 'Convex' in ob.name]
        upper_teeth = [ob for ob in obs if data_tooth_label(ob.name.split(' ')[0]) in tooth_numbering.upper_teeth]
        lower_teeth = [ob for ob in obs if data_tooth_label(ob.name.split(' ')[0]) in tooth_numbering.lower_teeth]
        
        if upper_ging:
            bm_upper = make_model(upper_ging, upper_teeth)
            if "Upper Output" not in bpy.data.objects:
                me = bpy.data.meshes.new('Upper Output')
                upper_ob = bpy.data.objects.new('Upper Output', me)
                context.scene.objects.link(upper_ob)
            else:
                upper_ob = bpy.data.objects.get('Upper Output')
                
            bm_upper.to_mesh(upper_ob.data)
            bm_upper.free()
            
        if lower_ging:
            bm_upper = make_model(upper_ging, upper_teeth)
            if "Lower Output" not in bpy.data.objects:
                me = bpy.data.meshes.new('Lower Output')
                upper_ob = bpy.data.objects.new('Lower Output', me)
                context.scene.objects.link(ob)
            else:
                upper_ob = bpy.data.objects.get('Lower Output')
                
            bm_upper.to_mesh(upper_ob.data)
            bm_upper.free()
        
        #TODO, set up the modal operator
        return {'FINISHED'}

def register():
    bpy.utils.register_class(AITeeth_OT_make_diagnostic_model)


def unregister():
    bpy.utils.unregister_class(AITeeth_OT_make_diagnostic_model)

