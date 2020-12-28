'''
Created on Dec 26, 2019

@author: Patrick
'''
from ..tooth_numbering import data_tooth_label
from .. import tooth_numbering
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

from ..subtrees.geometry_utils.transformations import calculate_plane
from ..cloud_api.export_upload import *
from ..common.utils import get_settings


import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

from d3lib.bmesh_utils.bmesh_utilities_common import bmesh_join_list
from d3lib.bmesh_utils.bmesh_delete import bmesh_fast_delete
from d3guard.subtrees.metaballs.vdb_tools import remesh_bme

from d3lib.bmesh_utils.bmesh_utilities_common import bmesh_join_list
from d3lib.geometry_utils.bound_box_utils import get_bbox_center

meta_radius = .5
meta_resolution = .2
pre_offset = -.35
middle_factor = .75
epsilon = .001


def create_bme_ob(name, bme):
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    bme.to_mesh(me)
    bpy.context.scene.objects.link(ob)
    
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
              voxel_size = .2,
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
        
        bm_merged.free()
        bm_merged = bmesh.new()
        bm_merged.from_object(new_ob, context.scene)
        
        bme_vdb_remesh = remesh_bme(bm_merged, 
              isovalue = 0.01, 
              adaptivity = 0.0, 
              only_quads = False, 
              voxel_size = .2,
              filter_iterations = 1,
              filter_width = 4,
              filter_sigma = 1.0,
              grid = None,
              write_method = 'FAST')
        
        bme_vdb_remesh.to_mesh(newest_me)
        
    else:              
        bme_vdb_remesh.to_mesh(newest_me)
    
    bme_vdb_remesh.free()
    bm_merged.free()
    bme_remesh.free()
    bme.free()
    
    return new_ob

       
def make_reduction_shells(context, depth):                                     
    bpy.context.scene.update() 
    
              
    selected_teeth = [ob for ob in bpy.context.scene.objects if ob.type == 'MESH' and 'Convex' in ob.name and ob.select]
    
        
    upper_teeth = [ob for ob in selected_teeth if data_tooth_label(ob.name.split(' ')[0]) in tooth_numbering.upper_teeth]
    lower_teeth = [ob for ob in selected_teeth if data_tooth_label(ob.name.split(' ')[0]) in tooth_numbering.lower_teeth]
    
    
    for convex_teeth in [upper_teeth, lower_teeth]:
        
        if len(convex_teeth) == 0:
            continue
        
        if convex_teeth[0].name.split(' ')[0] in tooth_numbering.upper_teeth:
            print('DOING UPPERS')
            if 'Upper Reduction' in bpy.data.objects:
                shell_ob = bpy.data.objects.get('Upper Reduction')
                shell_me = shell_ob.data
            else:
                shell_me = bpy.data.meshes.new('Upper Reduction')
                shell_ob = bpy.data.objects.new('Upper Reduction', shell_me)
                bpy.context.scene.objects.link(shell_ob)
        else:
            print('DOING LOWERS')
            if 'Lower Reduction' in bpy.data.objects:
                shell_ob = bpy.data.objects.get('Lower Reduction')
                shell_me = shell_ob.data
            else:
                shell_me = bpy.data.meshes.new('Lower Reduction')
                shell_ob = bpy.data.objects.new('Lower Reduction', shell_me)
                bpy.context.scene.objects.link(shell_ob)
        
    

        
        thimble_preps = []
        original_teeth = []
        
        margin_bme = bmesh.new()
        for c_ob in convex_teeth:
            
            margin_ob = None
            for child in c_ob.children:
                if 'thimble_prep' in child.name:
                    thimble_preps.append(child)
                    child.data.update()
                    mod = child.modifiers.new('Solidify', type = 'SOLIDIFY')
                    mod.thickness = depth
                    mod.offset = 1.0
                    
                if 'margin_line' in child.name:
                    mx = child.matrix_world
                    imx = mx.inverted()
                    
                    child.data.transform(mx)  #world coord
                    margin_bme.from_mesh(child.data) #append to bmesh
                    child.data.transform(imx) #put back
                    margin_ob = child
                    
               
                    
            ob = bpy.data.objects.get(c_ob.name.split(' ')[0] + " open_shell")
            if ob:
                original_teeth.append(ob)

                ob.data.update()
                
                if margin_ob:
                    if "Margin Prox" not in ob.vertex_groups:
                        vg = ob.vertex_groups.new(name = "Margin Prox")
                    else:
                        vg = ob.vertex_groups.get('Margin Prox')
                    vg.add([i for i in range(0,len(ob.data.vertices))], 0, type = 'REPLACE')
                
                    pmod = ob.modifiers.new('Margin Prox', 'VERTEX_WEIGHT_PROXIMITY')
        
                    pmod.target = margin_ob
                    pmod.vertex_group = "Margin Prox"
                    pmod.proximity_mode = 'GEOMETRY'
                    pmod.proximity_geometry = {'VERTEX'}
                    pmod.min_dist = 0.5 #4.5
                    pmod.max_dist = 2.0
                    pmod.falloff_type = 'ICON_SPHERECURVE' #LINEAR' #'SMOOTH' #'SHARP' #'ICON_SPHERECURVE'
                    pmod.show_expanded = False
                
                
                mod = ob.modifiers.new('Solidify', type = 'SOLIDIFY')
                mod.thickness = 2.0 * depth
                mod.offset = 0.0
                if "Margin Prox" in ob.vertex_groups:
                    mod.vertex_group = "Margin Prox"
                    mod.thickness_vertex_group = .15
            
        
        margin_bme.verts.ensure_lookup_table()
        margin_bme.verts.index_update()
        #filter the margin
        kd_margin = KDTree(len(margin_bme.verts))
        for v in margin_bme.verts:
            kd_margin.insert(v.co, v.index)
        kd_margin.balance()
           
        kd_convex = KDTree(len(convex_teeth))
        bvhs = []
        bmes_convex = []
        centers = {}
        for i, ob in enumerate(convex_teeth):
            
            center = get_bbox_center(ob)
            centers[i] = center
            kd_convex.insert(center, i)
            bme = bmesh.new()
            bme.from_mesh(ob.data)
            bme.transform(ob.matrix_world)
            
            bvh = BVHTree.FromBMesh(bme)
            bvhs.append(bvh)
            bmes_convex.append(bme)
            
        kd_convex.balance()
    
        for i, bme in enumerate(bmes_convex):
            to_delete = []
            
            center = centers[i]
            neighbors = kd_convex.find_n(center, 3)  #will find 2 closest neighbors since it's going to find itself
            
            print('Checking on tooth ' + convex_teeth[i].name)
            for packet in neighbors[1:]:
                _, ind, _ = packet
                print(convex_teeth[ind].name)
                
                
            if len(neighbors) > 2:
                _, n1, _ = neighbors[1]
                _, n2, _ = neighbors[2]
            
                for v in bme.verts:
                    #_,_, d3 = kd_margin.find(v.co)
                    
                    #if d3 < .5 * depth:
                    #    to_delete.append(v)
                    #    continue
                        
                    _, _, _, d1 = bvhs[n1].find_nearest(v.co)
                    _, _, _, d2 = bvhs[n2].find_nearest(v.co)
                    
                    if d1 > .45 and d2 > .45:# and abs(v.normal.dot(plane_no)) > .45:  #Let's see
                        to_delete.append(v)
                        continue
                    
                
                print('deleting %i out of %i verts' % (len(to_delete), len(bme.verts)))
                bmesh_fast_delete(bme, verts = to_delete)
                bme.verts.ensure_lookup_table()
                bme.faces.ensure_lookup_table()
                bme.edges.ensure_lookup_table()
                bmesh.ops.solidify(bme, geom = bme.faces[:], thickness = depth)
               
        bme_contacts = bmesh_join_list(bmes_convex)    
        bpy.context.scene.update()
        
        bmes = []
        for ob in original_teeth + thimble_preps:
            bme  = bmesh.new()
            bme.from_object(ob, bpy.context.scene)
            bme.transform(ob.matrix_world)
            
            bmes += [bme]
            ob.modifiers.clear()
            
        bme_offset = bmesh_join_list(bmes) # + [bme_contacts])
        
        final_bme = remesh_bme(bme_offset, 
                    isovalue = 0.1, 
                    adaptivity = 0.0, 
                    only_quads = False, 
                    voxel_size = .175,
                    filter_iterations = 1,
                    filter_width = 4,
                    filter_sigma = 1.0,
                    grid = None,
                    write_method = 'FAST')
    
        final_bme.to_mesh(shell_me)
        bme_offset.free()
        final_bme.free()
    
        for bme in bmes + bmes_convex:
            bme.free()
    

class AITeeth_OT_reduction_shell(bpy.types.Operator):
    """Process model for shell reduction"""
    bl_idname = "ai_teeth.prep_original_model"
    bl_label = "Prep Original Model"
    bl_options = {'REGISTER', 'UNDO'}
    
    tooth_selection = bpy.props.EnumProperty(name = 'Tooth Selection', items = (('ALL_TEETH','ALL_TEETH','ALL_TEETH'), ('SELECTED_TEETH','SELECTED_TEETH','SELECTED_TEETH')))

    thickness = bpy.props.FloatProperty(default = 1.0, min = 0.5, max = 2.5)

    @classmethod
    def poll(cls, context):
        
        return True
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width = 300)
        
    def execute(self, context):
        
        if self.tooth_selection == 'SELECTED_TEETH':
        
            selected_teeth = [ob for ob in bpy.context.scene.objects if ob.type == 'MESH' and 'Convex' in ob.name and ob.select]
        
        else:
            selected_teeth = [ob for ob in bpy.context.scene.objects if ob.type == 'MESH' and 'Convex' in ob.name]
            
            
        upper_teeth = [ob for ob in selected_teeth if data_tooth_label(ob.name.split(' ')[0]) in tooth_numbering.upper_teeth]
        lower_teeth = [ob for ob in selected_teeth if data_tooth_label(ob.name.split(' ')[0]) in tooth_numbering.lower_teeth]
    
    
    
        make_reduction_shells(context, self.thickness)
        
        upper_ob = bpy.data.objects.get(context.scene.d3ortho_upperjaw)
        lower_ob = bpy.data.objects.get(context.scene.d3ortho_lowerjaw)
        
        upper_reduction = bpy.data.objects.get('Upper Reduction')
        lower_reduction = bpy.data.objects.get('Lower Reduction')
        
        for ob in bpy.data.objects:
            ob.hide = True
            
        if upper_ob and upper_reduction:
            upper_ob.hide = False
            if 'Reduction' in upper_ob.modifiers:
                mod = upper_ob.modifiers.get('Reduction')
            else:
                mod = upper_ob.modifiers.new('Reduction', type = 'BOOLEAN')
                
            mod.operation = 'DIFFERENCE'
            mod.object = upper_reduction
    
        if lower_ob and lower_reduction:
            lower_ob.hide = False
            if 'Reduction' in lower_ob.modifiers:
                mod = lower_ob.modifiers.get('Reduction')
            else:
                mod = lower_ob.modifiers.new('Reduction', type = 'BOOLEAN')
                
            mod.operation = 'DIFFERENCE'
            mod.object = lower_reduction
        
        context.space_data.viewport_shade = 'SOLID'
        context.space_data.show_textured_solid = False    
        return {'FINISHED'}

def register():
    bpy.utils.register_class(AITeeth_OT_reduction_shell)
    

def unregister():
    bpy.utils.unregister_class(AITeeth_OT_reduction_shell)
    