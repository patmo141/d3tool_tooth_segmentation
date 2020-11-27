'''
Created on Dec 26, 2019

@author: Patrick
'''
'''
Created on Nov 27, 2019

@author: Patrick
'''
import requests
import json
import time
import os
from concurrent.futures import ThreadPoolExecutor

import bpy
import blf
from bpy.props import *


from ..subtrees.point_picker.functions.common import showErrorMessage
from ..cloud_api.export_upload import *
from ..common.utils import get_settings


import bmesh
import bpy
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree


from d3lib.bmesh_utils.bmesh_delete import bmesh_fast_delete
from d3lib.geometry_utils.bound_box_utils import get_bbox_center
from d3lib.bmesh_utils.bmesh_utilities_common import bmesh_join_list, increase_vert_selection, new_bmesh_from_bmelements
from d3lib.metaballs.vdb_tools import remesh_bme
from d3lib.geometry_utils.transformations import r_matrix_from_principal_axes

from ..tooth_numbering import data_tooth_label
from .. import tooth_numbering

meta_radius = .5
meta_resolution = .2
pre_offset = -.35
middle_factor = .75
epsilon = .001

def convexify_object(context, ob):
    '''
    uses the convex hull to fill in the bottom
    '''
    me = ob.data
    
    bme = bmesh.new()
    bme.from_mesh(me)
    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    
    #another duplicate to convert to a convex hull
    bme_convex = bmesh.new()
    bme_convex.from_mesh(me)
    bme_convex.verts.ensure_lookup_table()
    bme_convex.edges.ensure_lookup_table()
    bme_convex.faces.ensure_lookup_table()
    
    #BVH for snapping and ray_casting
    bvh = BVHTree.FromBMesh(bme)
    
    #get the convex_hull of the tooth
    out_geom = bmesh.ops.convex_hull(bme_convex, input = bme_convex.verts[:], use_existing_faces = True)
                    
    unused_geom = out_geom['geom_interior']       
    del_v = [ele for ele in unused_geom if isinstance(ele, bmesh.types.BMVert)]
    del_e = [ele for ele in unused_geom if isinstance(ele, bmesh.types.BMEdge)]
    del_f = [ele for ele in unused_geom if isinstance(ele, bmesh.types.BMFace)]
            
    #these must go
    bmesh.ops.delete(bme_convex, geom = del_v, context = 1)
    #bmesh.ops.delete(bme, geom = del_e, context = )
    bmesh.ops.delete(bme_convex, geom = del_f, context = 5)
    #then we need to remove internal faces that got enclosed in
    holes_geom = out_geom['geom_holes']
            
    del_f = [ele for ele in holes_geom if isinstance(ele, bmesh.types.BMFace)]
    #bmesh.ops.delete(bme_convex, geom = del_f, context = 5)
                  
    #find bad edges
    bad_eds = [ed for ed in bme_convex.edges if len(ed.link_faces) != 2]
            
    eds_zero_face = [ed for ed in bad_eds if len(ed.link_faces) == 0]
    eds_one_face = [ed for ed in bad_eds if len(ed.link_faces) == 1]
    eds_three_face = [ed for ed in bad_eds if len(ed.link_faces) == 3]
    eds_other = [ed for ed in bad_eds if len(ed.link_faces) > 3]
                  
    new_me = bpy.data.meshes.new(ob.name + " Convex")
    new_ob = bpy.data.objects.new(ob.name + " Convex", new_me)
    new_ob.matrix_world = ob.matrix_world
    bpy.context.scene.objects.link(new_ob)
    
    #The new object is just a remeshed convex hulll
    bme_convex.to_mesh(new_me)
    bpy.context.scene.objects.active = new_ob
    bpy.ops.object.mode_set(mode = 'EDIT')
    bpy.ops.mesh.select_all(action = 'SELECT')
    bpy.ops.mesh.fill_holes(sides = 20)
    bpy.ops.object.mode_set(mode = 'OBJECT')
    
    mod = new_ob.modifiers.new('Remesh', type = 'REMESH')
    mod.octree_depth = 6
    mod.mode = 'SMOOTH'
    
    #now, get the remeshed convex hull and compare it to the open shell
    newest_me  = new_ob.to_mesh(bpy.context.scene, apply_modifiers = True, settings = 'PREVIEW')
    new_ob.modifiers.clear()
    new_ob.data = newest_me
    bpy.data.meshes.remove(new_me)
    bme_remesh = bmesh.new()
    bme_remesh.from_mesh(newest_me)
    bme_remesh.verts.ensure_lookup_table()
    
    #skip the perimeters
    non_man_vs = set()
    non_man_eds = [ed for ed in bme.edges if len(ed.link_faces) < 2]
    for ed in non_man_eds:
        non_man_vs.update(ed.verts[:])
        
    kd = KDTree(len(non_man_vs))
    for i, v in enumerate(non_man_vs):
        kd.insert(v.co, i)
    
    kd.balance()    
    
    to_delete = []   
    for v in bme_remesh.verts:
       
        co3d, ind, dist = kd.find(v.co)
        if dist < .75:
            v.co = co3d
            continue
        
        loc, no, ind, d = bvh.find_nearest(v.co)
        if d < .1:
            to_delete.append(v)
            continue
            
        loc, no, ind, d = bvh.ray_cast(v.co - epsilon * v.normal, -v.normal)
        if loc:
            if no.dot(v.normal) > .25:
                to_delete.append(v)
                v.co = loc
                continue
       
    bmesh.ops.delete(bme_remesh, geom = to_delete, context = 1)
    
    bm_merged = bmesh_join_list([bme_remesh, bme])
    
    bme_vdb_remesh = remesh_bme(bm_merged, 
              isovalue = 0.01, 
              adaptivity = 0.0, 
              only_quads = False, 
              voxel_size = .1,
              filter_iterations = 1,
              filter_width = 4,
              filter_sigma = 1.0,
              grid = None,
              write_method = 'FAST')
    
    if len(bme_vdb_remesh.verts) == 0:
        print('Uh oh, remesh failed')
        bme_vdb_remesh.free()
        bm_merged.to_mesh(newest_me)
        #new_ob.data = newest_me #already true
        mod = new_ob.modifiers.new('Remesh', type = 'REMESH')
        mod.octree_depth = 7
        mod.mode = 'SMOOTH'
        
        context.scene.update()
        
        bm_merged.free()
        bm_merged = bmesh.new()
        bm_merged.from_object(new_ob, context.scene)
        
        bme_vdb_remesh = remesh_bme(bm_merged, 
              isovalue = 0.01, 
              adaptivity = 0.0, 
              only_quads = False, 
              voxel_size = .1,
              filter_iterations = 1,
              filter_width = 4,
              filter_sigma = 1.0,
              grid = None,
              write_method = 'FAST')
        
    if len(bme_vdb_remesh.verts) != 0:
        bme_vdb_remesh.to_mesh(newest_me)             
    else:
        bm_merged.to_mesh(newest_me)
    
    bme_vdb_remesh.free()
    bm_merged.free()
    bme_remesh.free()
    bme.free()
    
    return new_ob

def main_function(context,
                  use_select = False):
    
    
    if use_select:
        selected_teeth = [ob for ob in bpy.context.scene.objects if 'tooth' in ob.data.name and ob.select == True]
    
    else:
        selected_teeth = [ob for ob in bpy.context.scene.objects if 'tooth' in ob.data.name]
    
    upper_teeth = [ob for ob in selected_teeth if data_tooth_label(ob.name) in tooth_numbering.upper_teeth]
    lower_teeth = [ob for ob in selected_teeth if data_tooth_label(ob.name) in tooth_numbering.lower_teeth]
    
    
    upper_ob = bpy.data.objects.get(context.scene.d3ortho_upperjaw)
    lower_ob = bpy.data.objects.get(context.scene.d3ortho_lowerjaw)
    
    
    for ob in bpy.data.objects:
        ob.hide = True
        
    if upper_ob and len(upper_teeth):
        
        subtract_model = ortho_setup(upper_ob, upper_teeth)
        
        mod = upper_ob.modifiers.new('Boolean', type = 'BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.object = subtract_model
    
        upper_ob.hide = False
        
        subtract_model.hide = True
    if lower_ob and len(lower_teeth):
        subtract_model = ortho_setup(lower_ob,
                                                     lower_teeth)
                                                    
        
        mod = lower_ob.modifiers.new('Boolean', type = 'BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.object = subtract_model
        
        lower_ob.hide = False
    
        subtract_model.hide = True
        
    context.space_data.show_textured_solid = False 
        
def ortho_setup(base_ob, teeth):
    
    
    convex_teeth = []
    for ob in teeth:
        if ob.name + " Convex" in bpy.data.objects:
            convex_teeth.append(ob)
        else:
            convex_teeth.append(convexify_object(bpy.context, ob))
    
    #BVH for filtration based on original geometry
    bme_base = bmesh.new()
    bme_base.from_mesh(base_ob.data)
    bvh_base = BVHTree.FromBMesh(bme_base)
    
    #KD tree and BVH's for filter for neighboring teeth    
    kd_convex = KDTree(len(convex_teeth))
    bvhs = []
    bmes_convex = []
    centers = {}
    for i, ob in enumerate(convex_teeth):
        
        center = get_bbox_center(ob)
        mx = Matrix.Translation(center)
        imx = mx.inverted()
        centers[i] = center
        kd_convex.insert(center, i)
        bme = bmesh.new()
        bme.from_mesh(ob.data)
        bme.transform(ob.matrix_world)
        
        bvh = BVHTree.FromBMesh(bme)
        bvhs.append(bvh)
        bmes_convex.append(bme)
        
        #center the teeth while we are at it but after bmesh and bvh extraction
        #to keep everything in world coords
        ob.data.transform(imx)
        ob.matrix_world = mx  #right?
        
    kd_convex.balance()
    
    convex_bme = bmesh_join_list(bmes_convex, normal_update= True)
    for v in convex_bme.verts:
        loc, no, ind, d3 = bvh_base.find_nearest(v.co)
                
        if d3 < .5:  #this means is close to the original or close to the neigbors
            v.co += .2 * v.normal
            
    solid_remesh = remesh_bme(convex_bme, 
                  isovalue = 0.01, 
                  adaptivity = 0.0, 
                  only_quads = False, 
                  voxel_size = .3,
                  filter_iterations = 1,
                  filter_width = 4,
                  filter_sigma = 1.0,
                  grid = None,
                  write_method = 'FAST')
    
    new_me2= bpy.data.meshes.new('Teeth Subtract')
    new_ob2 = bpy.data.objects.new("Teeth Subtract", new_me2)
    bpy.context.scene.objects.link(new_ob2)
    solid_remesh.to_mesh(new_me2)
    solid_remesh.free()
    convex_bme.free()
    
    #now filter the solid geometry for proximit
    for i, bme in enumerate(bmes_convex):
        to_delete = []
        
        center = centers[i]
        neighbors = kd_convex.find_n(center, 3)
        
        #what the f am I doing here?  oh deciphering the kd.find_n data
        #print('Checking on tooth ' + convex_teeth[i].name)
        #for packet in neighbors[1:]:
        #    _, ind, _ = packet
        #    print(convex_teeth[ind].name)
            
            
        if len(neighbors) > 2:  #remember it's going to find itself as the closest element in the KDTree so we wane the 1 and 2, not the 0 and 1
            co1, n1, _ = neighbors[1]
            co2, n2, _ = neighbors[2]
        
            for v in bme.verts:
                _, _, _, d1 = bvhs[n1].find_nearest(v.co)
                _, _, _, d2 = bvhs[n2].find_nearest(v.co)
                _, _, _, d3 = bvh_base.find_nearest(v.co)
                
                if d1 < 1.5 or d2 < 1.5 or d3 < 1.5:  #this means is close to the original or close to the neigbors
                    to_delete.append(v)
            
            print('there are %i faces' % len(bme.faces))
            print('deleting %i out of %i verts' % (len(to_delete), len(bme.verts)))
            bmesh_fast_delete(bme, verts = to_delete)
            bme.verts.ensure_lookup_table()
            bme.faces.ensure_lookup_table()
            bme.edges.ensure_lookup_table()
            print('there are %i faces' % len(bme.faces))
            average_normal = Vector((0,0,0))
            total_area = 0.0
            
            for j in range(0,20):
                bmesh.ops.smooth_vert(bme, verts=bme.verts[:], factor=1.0)
                
            for f in bme.faces:
                a = f.calc_area()
                total_area += a
                average_normal += a * f.normal
            
            if abs(total_area) < .001:
                average_normal = Vector((0,0,1))
            else:
                average_normal *= 1/total_area
                average_normal.normalize()
            
            Tmx = Matrix.Translation(centers[i]) #get the cetnral point
            Z = average_normal
            X = (co2 - co1).normalized()
            Y = Z.cross(X)
            X = Y.cross(Z) #put mes/dis perp to root
            
            Rmx = r_matrix_from_principal_axes(X,Y,Z).to_4x4()
        
            
            root_name = convex_teeth[i].name.split(' ')[0] + '_root_empty'
            root_empty = bpy.data.objects.new(root_name, None)
            root_empty.empty_draw_type = 'SINGLE_ARROW'
            root_empty.empty_draw_size = 12
            bpy.context.scene.objects.link(root_empty)
            root_empty.parent = convex_teeth[i]
            root_empty.matrix_world = Tmx * Rmx
            
            #bme.to_mesh(convex_teeth[i].data)
            bme.free()
   
    return new_ob2
 
class AITeeth_OT_ortho_setup(bpy.types.Operator):
    """Generate Ortho Setup"""
    bl_idname = "ai_teeth.diagnostic_setup"
    bl_label = "Get Diagnostic Setup"

    tooth_selection = bpy.props.EnumProperty(name = 'Tooth Selection', items = (('ALL_TEETH','ALL_TEETH','ALL_TEETH'), ('SELECTED_TEETH','SELECTED_TEETH','SELECTED_TEETH')))
    
    
    @classmethod
    def poll(cls, context):

        return True

    def invoke(self, context, event):

        
        return context.window_manager.invoke_props_dialog(self, width = 300)
    

            
    def execute(self, context):
        
        main_function(context,
                      use_select = self.tooth_selection)

        #TODO, set up the modal operator
        return {'FINISHED'}



def register():
    bpy.utils.register_class(AITeeth_OT_ortho_setup)

def unregister():
    bpy.utils.register_class(AITeeth_OT_ortho_setup)
