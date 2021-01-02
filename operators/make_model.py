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

 

def add_to_bmesh(bme, ob, transform = True):
    
    mx = ob.matrix_world
    imx = mx.inverted()
    
    if transform:
        ob.data.transform(mx)
    bme.from_mesh(ob.data)
    if transform:
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
            
            
            if not ob.get('PREPARED'):
                #join the tooth to the root_prep
                bme_die = bmesh.new()
                add_to_bmesh(bme_die, root, transform = False)
                add_to_bmesh(bme_die, ob, transform = False)
                bmesh.ops.triangulate(bme_die, faces = bme_die.faces[:])
                bme_die2 = remesh_bme(bme_die, 
                          isovalue = 0.01, 
                          adaptivity = 0.5, 
                          only_quads = False, 
                          voxel_size = .09,
                          filter_iterations = 0,
                          filter_width = 4,
                          filter_sigma = 1.0,
                          grid = None,
                          write_method = 'FAST')
                
                bme_die2.to_mesh(root.data)
                bme_die.free()
                bme_die2.free()
                
            root["d3output"] = True
        
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
    
    
    return bm
        
class AITeeth_OT_make_diagnostic_model(bpy.types.Operator):
    """Create Diagnostic Model"""
    bl_idname = "ai_teeth.make_diagnostic_model"
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
            upper_ob["d3output"] = True
            
        if lower_ging:
            bm_lower = make_model(lower_ging, lower_teeth)
            if "Lower Output" not in bpy.data.objects:
                me = bpy.data.meshes.new('Lower Output')
                lower_ob = bpy.data.objects.new('Lower Output', me)
                context.scene.objects.link(lower_ob)
            else:
                upper_ob = bpy.data.objects.get('Lower Output')
                
            bm_lower.to_mesh(lower_ob.data)
            bm_lower.free()
            lower_ob["d3output"] = True
        
        #TODO, set up the modal operator
        return {'FINISHED'}

def register():
    bpy.utils.register_class(AITeeth_OT_make_diagnostic_model)


def unregister():
    bpy.utils.unregister_class(AITeeth_OT_make_diagnostic_model)

