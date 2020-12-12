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
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree


from d3lib.bmesh_utils.bmesh_delete import bmesh_fast_delete
from d3lib.geometry_utils.bound_box_utils import get_bbox_center
from d3lib.bmesh_utils.bmesh_utilities_common import bmesh_join_list, increase_vert_selection, new_bmesh_from_bmelements
from d3guard.subtrees.metaballs.vdb_tools import remesh_bme

from ..tooth_numbering import data_tooth_label
from .. import tooth_numbering



meta_radius = .5
meta_resolution = .2
pre_offset = -.35
middle_factor = .75
epsilon = .001

relax_iterations = 5

def relax_vert(v, perim_eds, factor = .2):
    '''
    relaxes vertex by factor percent toward the
    line drawn between the neighboring verts
    '''
    
    other_eds = [ed for ed in v.link_edges if ed in perim_eds]
    
    if len(other_eds) != 2: 
        print('how did this vert get in here')
        return Vector((0,0,0))

    v0 = other_eds[0].other_vert(v)
    v1 = other_eds[1].other_vert(v)
    
    mid = .5 * (v0.co + v1.co)
    vec = v1.co - v0.co
    vec.normalize()
    delta = mid - v.co
    
    delta_perp = delta - delta.dot(vec) * vec
    
    return factor * delta_perp


#This is a slightly customized version    
def convexify_object(context, ob, offset = False, offset_amount = 0.3):
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
    
    if offset:
        for v in bme.verts:
            v.co = v.co + offset_amount * v.normal
        for v in bme_convex.verts:
            v.co = v.co + offset_amount * v.normal
              
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
    
 
    bme_convex.to_mesh(new_me)
    bpy.context.scene.objects.active = new_ob
    bpy.ops.object.mode_set(mode = 'EDIT')
    bpy.ops.mesh.select_all(action = 'SELECT')
    bpy.ops.mesh.fill_holes(sides = 20)
    bpy.ops.object.mode_set(mode = 'OBJECT')
    
    mod = new_ob.modifiers.new('Remesh', type = 'REMESH')
    mod.octree_depth = 6
    mod.mode = 'SMOOTH'
    
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
    
    #now snap the original mesh back to the perimeter of  the convex
    
    #eds_non_man_remesh = [ed for ed in bme_remesh.edges if len(ed.link_faces == 1)]
    #eds_non_man_orgin = [ed for ed in bme.edges if len(ed.link_faces) == 1]
            
    bm_merged = bmesh_join_list([bme_remesh, bme])
    
    #non_man_edges = [ed for ed in bme_merged if len(ed.link_faces == 1)]
    #non_man_verts = set()
    #for ed in non_man_edges:
    #    non_man_verts.update(ed.verts[:])
        
    #nodes = [v for v in non_man_verts if len([ed for ed in v.link_edges if ed in non_man_edges]) > 2]
    
    
    context.scene.objects.unlink(new_ob)
    bpy.data.objects.remove(new_ob)
    bpy.data.meshes.remove(newest_me)
    
    bme_remesh.free()
    bme.free()
    
    return bm_merged



def main_function(context,
                  shoulder_width,
                  peg_depth,
                  use_select = False):
    
    
    if use_select:
        selected_teeth = [ob for ob in bpy.context.scene.objects if ob.type == 'MESH' and 'tooth' in ob.data.name and ob.select]
    
    else:
        selected_teeth = [ob for ob in bpy.context.scene.objects if  ob.type == 'MESH' and 'tooth' in ob.data.name]
    
    upper_teeth = [ob for ob in selected_teeth if data_tooth_label(ob.name) in tooth_numbering.upper_teeth]
    lower_teeth = [ob for ob in selected_teeth if data_tooth_label(ob.name) in tooth_numbering.lower_teeth]
    
    
    upper_ob = bpy.data.objects.get(context.scene.d3ortho_upperjaw)
    lower_ob = bpy.data.objects.get(context.scene.d3ortho_lowerjaw)
    
    
    for ob in bpy.data.objects:
        ob.hide = True
        
    if upper_ob and len(upper_teeth):
        tooth_model, subtract_model = two_part_model(upper_ob, 
                                                     upper_teeth,
                                                     shoulder_width,
                                                     peg_depth)
        
        mod = upper_ob.modifiers.new('Boolean', type = 'BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.object = subtract_model
    
        upper_ob.hide = False
        tooth_model.hide = False
        subtract_model.hide = True
    if lower_ob and len(lower_teeth):
        tooth_model, subtract_model = two_part_model(lower_ob,
                                                     lower_teeth,
                                                     shoulder_width,
                                                     peg_depth)
        
        mod = lower_ob.modifiers.new('Boolean', type = 'BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.object = subtract_model
        
        lower_ob.hide = False
        tooth_model.hide = False
        subtract_model.hide = True
        
    context.space_data.show_textured_solid = False 
        
def two_part_model(ob, teeth,
                   shoulder_width,
                   peg_depth):
        
    start = time.time()
    interval = start
    
    base_ob = ob
    bme_base = bmesh.new()
    bme_base.from_mesh(base_ob.data)
    bvh_base = BVHTree.FromBMesh(bme_base)
    
    mx = base_ob.matrix_world
    imx = base_ob.matrix_world.inverted()
    
    
    bmes = []
    for ob in teeth:
        ob.data.update()
        print('convexifying ' + ob.name)
        bme = convexify_object(bpy.context, ob)
        bme.transform(ob.matrix_world)
        bmes += [bme]
        ob.hide = True
        
    finish = time.time()
    print('took %f seconds to convexify' % (finish-interval))
    interval = finish
    bme_merged = bmesh_join_list(bmes)
    
    
    new_me= bpy.data.meshes.new('Merged Teeth')
    new_ob= bpy.data.objects.new("Merged Teeth", new_me)
    bpy.context.scene.objects.link(new_ob)
    bme_merged.to_mesh(new_me)
    bme_merged.free()
    
    
    
    print('adding dual contour')
    mod = new_ob.modifiers.new('Remesh', type = 'REMESH')
    mod.mode = 'SMOOTH'
    mod.use_remove_disconnected = False
    mod.octree_depth = 9
    
    print('converting dual contour to mesh')
    me = new_ob.to_mesh(bpy.context.scene, apply_modifiers = True, settings = 'PREVIEW')
    new_ob.modifiers.clear()
    
    bme = bmesh.new()
    bme.from_mesh(me)
    
    finish = time.time()
    print('took %f dual contour' % (finish-interval))
    interval = finish
    
    print('remesh happening')
    bme_remeshed = remesh_bme(bme, 
                  isovalue = 0.0, 
                  adaptivity = 0.0, 
                  only_quads = False, 
                  voxel_size = .175,
                  filter_iterations = 0,
                  filter_width = 4,
                  filter_sigma = 1.0,
                  grid = None,
                  write_method = 'FAST')
    
    print('triangulating remesh')
    quads = [f for f in bme_remeshed.faces if len(f.verts) > 3]
    bmesh.ops.triangulate(bme_remeshed, faces = quads, quad_method = 0, ngon_method = 0)
    
    
    finish = time.time()
    print('took %f seconds to remesh and triangulate' % (finish-interval))
    interval = finish
    
    print('creating shoulder/insertion if desired')
    
    outer_verts = set()
    engagement_verts = set()
    for v in bme_remeshed.verts:
        loc, no, ind, d = bvh_base.find_nearest(imx * v.co)
        if d < .25:
            outer_verts.add(v)
        if d >=  shoulder_width:
            engagement_verts.add(v) 
            
            
    engagement_faces = set()
    for v in engagement_verts:
        engagement_faces.update(v.link_faces[:])
        
    perim_eds = set()
    perim_verts = set()
    seen_eds = set()
    for f in engagement_faces:
        for ed in f.edges:
            if ed in seen_eds:continue 
            seen_eds.add(ed)
            if not all([lf in engagement_faces for lf in ed.link_faces]):
                perim_eds.add(ed)
                perim_verts.update(ed.verts[:])
    
    finish = time.time()
    print('took %f seconds to detect the underside' % (finish-interval))
    interval = finish
    
    
    print('relaxing the border')
    perim_verts = list(perim_verts)
    relax_dict = {}
    for i in range(0,relax_iterations):
        for v in perim_verts:
            relax_dict[v] = relax_vert(v, perim_eds, factor = .25)
        for v in perim_verts:
            v.co += relax_dict[v]
     
    finish = time.time()
    print('took %f seconds to relax the boundary' % (finish-interval))
    interval = finish
    
    average_normal = Vector((0,0,0))
    total_area = 0
    for f in engagement_faces:
        a = f.calc_area()
        total_area += a
        average_normal += a * f.normal
    average_normal *= 1/total_area
    average_normal.normalize()
    
    engagement_peg = new_bmesh_from_bmelements(engagement_faces)
    for v in engagement_peg.verts:
        v.co -= .5 * average_normal
    
    finish = time.time()
    print('took %f seconds to calculate the average normal' % (finish-interval))
    interval = finish
    
    print('extruding the inner region')
    gdict = bmesh.ops.extrude_face_region(engagement_peg, geom = engagement_peg.faces[:])
    extrude_verts = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMVert)]
    for v in extrude_verts: 
        v.co += peg_depth * average_normal
       
    teeth_and_peg = bmesh_join_list([bme, engagement_peg]) 
    engagement_peg.free()
    
    print('remesh happening')
    bme_remeshed = remesh_bme(teeth_and_peg, 
                  isovalue = 0.0, 
                  adaptivity = 0.0, 
                  only_quads = False, 
                  voxel_size = .175,
                  filter_iterations = 0,
                  filter_width = 4,
                  filter_sigma = 1.0,
                  grid = None,
                  write_method = 'FAST')
    
    
    
    finish = time.time()
    print('took %f seconds to remesh the first time' % (finish-interval))
    interval = finish
    
    print('setting remesh data to object')
    bme_remeshed.to_mesh(me)
    new_ob.data = me
    bpy.data.meshes.remove(new_me)
    
    
    ratio = 100000/len(me.vertices)
    if ratio < .9:
        mod = new_ob.modifiers.new('Decimate', type = 'DECIMATE')
        mod.ratio = ratio
        bpy.context.scene.update()
        me = new_ob.to_mesh(bpy.context.scene, apply_modifiers = True, settings = 'PREVIEW')
        old_me = new_ob.data
        new_ob.modifiers.clear()
        new_ob.data = me
        bpy.data.meshes.remove(old_me)
        
        
    
    #TODO, selectively offset the peg and the teeth
    for v in bme_remeshed.verts:
        v.co += .2 * v.normal
        
    bme_remeshed2 = remesh_bme(bme_remeshed, 
                  isovalue = 0.0, 
                  adaptivity = 0.0, 
                  only_quads = False, 
                  voxel_size = .175,
                  filter_iterations = 0,
                  filter_width = 4,
                  filter_sigma = 1.0,
                  grid = None,
                  write_method = 'FAST')
                  
    
    finish = time.time()
    print('took %f seconds to remesh the second time' % (finish-interval))
    interval = finish          
                  
    new_me2= bpy.data.meshes.new('Teeth Subtract')
    new_ob2 = bpy.data.objects.new("Teeth Subtract", new_me2)
    bpy.context.scene.objects.link(new_ob2)
    bme_remeshed2.to_mesh(new_me2)
    
    ratio = 60000/len(new_ob2.data.vertices)
    if ratio < .9:
        mod2 = new_ob2.modifiers.new('Decimate', type = 'DECIMATE')
        mod2.ratio = ratio
        bpy.context.scene.update()
        new_me2 = new_ob2.to_mesh(bpy.context.scene, apply_modifiers = True, settings = 'PREVIEW')
        old_me = new_ob2.data
        new_ob2.modifiers.clear()
        new_ob2.data = new_me2
        bpy.data.meshes.remove(old_me)
            
    bme_remeshed.free()
    bme_remeshed2.free()
    
    
    return new_ob, new_ob2
    print('Took %f seconds for entire operation' % (finish-start))

 
class AITeeth_OT_two_part_model(bpy.types.Operator):
    """Submit file to get two part models"""
    bl_idname = "ai_teeth.two_part_model"
    bl_label = "Two Part Model"

    tooth_selection = bpy.props.EnumProperty(name = 'Tooth Selection', items = (('ALL_TEETH','ALL_TEETH','ALL_TEETH'), ('SELECTED_TEETH','SELECTED_TEETH','SELECTED_TEETH')))
    
    #make shoulder
    make_shoulder = bpy.props.BoolProperty(default = True)
    #shoulder_width
    shoulder_width =  bpy.props.FloatProperty(name = 'Shoulder Width', default = 1.0, min = 0.5, max = 2.0)
    #engagement_depth
    engagement_detph = bpy.props.FloatProperty(name = 'Peg Depth', default = 3.0, min = 0.5, max = 5.0)
    #compensation_gap
    compensation_gap = bpy.props.FloatProperty(name = 'Compensation Gap', default = 0.2, min = 0.0, max = 1.0)
    
    
    @classmethod
    def poll(cls, context):

        return True

    def invoke(self, context, event):

        
        return context.window_manager.invoke_props_dialog(self, width = 300)
    

            
    def execute(self, context):
        
        main_function(context, 
                      self.shoulder_width,
                      self.engagement_detph,
                      use_select = self.tooth_selection)

        #TODO, set up the modal operator
        return {'FINISHED'}



def register():
    bpy.utils.register_class(AITeeth_OT_two_part_model)

def unregister():
    bpy.utils.unregister_class(AITeeth_OT_two_part_model)
