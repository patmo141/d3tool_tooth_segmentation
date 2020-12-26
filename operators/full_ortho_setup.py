'''
Created on Nov 27, 2020

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
from mathutils import Vector, Matrix, Color
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree


from d3lib.bmesh_utils.bmesh_delete import bmesh_fast_delete
from d3lib.geometry_utils.bound_box_utils import get_bbox_center
from d3lib.bmesh_utils.bmesh_utilities_common import bmesh_join_list, increase_vert_selection, new_bmesh_from_bmelements
from d3guard.subtrees.metaballs.vdb_tools import remesh_bme
from d3lib.geometry_utils.transformations import r_matrix_from_principal_axes, random_axes_from_normal

from ..tooth_numbering import data_tooth_label, mes_dis_relation
from .. import tooth_numbering
from .remove_collisions_from_teeth import main as collisions_main

meta_radius = .5
meta_resolution = .2
pre_offset = -.35
middle_factor = .75
epsilon = .001

from .simple_base import simple_base_bme


def create_empty(name, loc):
    
    ob = bpy.data.objects.new(name, None)
    Mx = Matrix.Translation(loc)
    ob.matrix_world = Mx
    bpy.context.scene.objects.link(ob)
    
    
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
              adaptivity = 0.5, 
              only_quads = False, 
              voxel_size = .15,
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
        
        new_ob.modifiers.clear()
        
        bme_vdb_remesh = remesh_bme(bm_merged, 
              isovalue = 0.01, 
              adaptivity = 0.0, 
              only_quads = False, 
              voxel_size = .15,
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
    
    new_ob['original_ob_name'] = ob.name  #store the original ob name as ID prop
    
    return new_ob

def main_function(context,
                  use_select = False,
                  base = True,
                  trim = True,
                  decollide = True):
    
    if use_select:
        selected_teeth = [ob for ob in bpy.context.scene.objects if ob.type == 'MESH' and 'tooth' in ob.data.name and ob.select == True]
    
    else:
        selected_teeth = [ob for ob in bpy.context.scene.objects if ob.type == 'MESH' and 'tooth' in ob.data.name]
    
    upper_teeth = [ob for ob in selected_teeth if data_tooth_label(ob.name) in tooth_numbering.upper_teeth]
    lower_teeth = [ob for ob in selected_teeth if data_tooth_label(ob.name) in tooth_numbering.lower_teeth]
    
    
    upper_ob = bpy.data.objects.get(context.scene.d3ortho_upperjaw)
    lower_ob = bpy.data.objects.get(context.scene.d3ortho_lowerjaw)
    
    
    for ob in bpy.data.objects:
        ob.hide = True
        
    if upper_ob and len(upper_teeth):
        print('DOING UPPER TEETH')
        subtract_model, upper_gingiva  = ortho_setup(upper_ob, upper_teeth, add_base = base, auto_trim = trim, remove_collisions= decollide)
        
        upper_gingiva.modifiers.clear()
        mod = upper_gingiva.modifiers.new('Boolean', type = 'BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.object = subtract_model
    
        
        for ob in bpy.data.objects:
            ob.hide = True
        upper_ob.hide = True
        subtract_model.hide = True
        upper_gingiva.hide = False
        
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        
        upper_gingiva.hide = False
        
    if lower_ob and len(lower_teeth):
        print('DOING LOWER TEETH')
        subtract_model, lower_gingiva = ortho_setup(lower_ob, lower_teeth, add_base= base, auto_trim = trim, remove_collisions= decollide)
        
        lower_gingiva.modifiers.clear()                                    
        mod = lower_gingiva.modifiers.new('Boolean', type = 'BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.object = subtract_model
        
        for ob in bpy.data.objects:
            ob.hide = True
        lower_ob.hide = True
        subtract_model.hide = True
        lower_gingiva.hide = False
        
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
    
    
    if upper_ob and len(upper_teeth):
        upper_gingiva.hide = False

    if lower_ob and len(lower_teeth):    
        lower_gingiva.hide = False
    
    for ob in bpy.data.objects:
        if 'Convex' in ob.name:
            ob.hide = False  
            ob.hide_select = True  
    #context.space_data.show_textured_solid = False 
        
def ortho_setup(base_ob, teeth, add_base = True, auto_trim = True, remove_collisions = True):
    
    
    convex_teeth = []
    for ob in teeth:
        if ob.name + " Convex" in bpy.data.objects:
            convex_teeth.append(bpy.data.objects.get(ob.name + ' Convex'))
        else:
            convex_teeth.append(convexify_object(bpy.context, ob))
    
        ob.hide = True
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
    
    #BVH for filtration based on original geometry
    bme_base = bmesh.new()
    mx_base = base_ob.matrix_world
    imx_base = mx_base.inverted()
    base_ob.data.transform(mx_base)
    bme_base.from_mesh(base_ob.data)  #in world coordinates
    base_ob.data.transform(imx_base) #put the data back in it's local coords
    bvh_base = BVHTree.FromBMesh(bme_base)

    
    #KD tree and BVH's for filter for neighboring teeth    
    kd_convex = KDTree(len(convex_teeth))
    bvhs = []
    bmes_convex = []
    centers = {}
    convex_bme = bmesh.new()  #a mesh join of all convex teeth
    
    for i, ob in enumerate(convex_teeth):
        
        center = get_bbox_center(ob)
        MX = Matrix.Translation(center)
        
        
        mx_world = ob.matrix_world
        imx_world = mx_world.inverted()
        
        local_center = imx_world * center
        RS = mx_world.to_3x3().to_4x4()  #Rotation, Scale
        
        mx = Matrix.Translation(local_center)
        imx = mx.inverted()
        centers[i] = center
        kd_convex.insert(center, i)
        
        ob.data.transform(mx_world)  #Temporarly put the data in world coordinates
        
        bme = bmesh.new()
        bme.from_mesh(ob.data)  #pull the data in to the individual bmesh (it's in world coordinates)
        convex_bme.from_mesh(ob.data) #pull the data in to the combine bmesh (it's in world coordinates)
        bme.normal_update()  #AHH, normals are not transformed unless recalced manually
        
        bvh = BVHTree.FromBMesh(bme)
        bvhs.append(bvh)
        bmes_convex.append(bme)
        
        
        ob.data.transform(imx_world)  #Put the data back where it was originally.
        ob.data.transform(RS * imx)  #apply the rotation and scale and center it locally
        ob.matrix_world = MX 
        
        
        ob.update_tag()  #MAYBE FIX
   
    #bpy.ops.ai_teeth.remove_convex_collisions(iterations=2, factor = .25)  #do it as operator?
    collisions_main(convex_teeth, 2, .35)   #remove collisions between the convex teeth
    
    bpy.context.scene.update()
      
    kd_convex.balance()
    
    convex_bme.verts.ensure_lookup_table()
    convex_bme.faces.ensure_lookup_table()
    convex_bme.normal_update()
    
    for v in convex_bme.verts:
        loc, no, ind, d3 = bvh_base.find_nearest(v.co)
                
        if d3 < .5:  #this means is close to the original or close to the neigbors
            v.co += .25 * v.normal
            
    solid_remesh = remesh_bme(convex_bme, 
                  isovalue = 0.1, 
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
    
    
    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
    
    if auto_trim:
        bvh_trim = BVHTree.FromBMesh(solid_remesh)
        
        to_del = []
        for v in bme_base.verts:
            l, n, i, d = bvh_trim.find_nearest(v.co)
            if d > 5.0:  #TODO settings
                to_del.append(v)
        bmesh_fast_delete(bme_base, to_del)
        
        
    if add_base:
        Z = base_ob.matrix_world.to_quaternion() * Vector((0,0,1))  #z axis in world coordiantes
        simple_base_bme(bme_base, Vector((0,0,1)), base_height = 6.0,
                do_clean_geom = True,
                close_holes = True,
                relax_border = True)
        
    solid_remesh.free()
    convex_bme.free()
    
    #now filter the tooth solid geometry for proximity
    for i, bme in enumerate(bmes_convex):
        
        out_patch = set()
        out_patch_accurate = set()
        
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
            
            
            ob0_name = convex_teeth[i]["original_ob_name"]
            ob1_name = convex_teeth[n1]["original_ob_name"]
            ob2_name = convex_teeth[n2]["original_ob_name"]
            
            md1 = mes_dis_relation(ob0_name, ob1_name)
            md2 = mes_dis_relation(ob0_name, ob1_name)
            
            
            #diagnostic visualization help for debugging
            #create_empty(convex_teeth[i].name + 'co1', co1)
            #create_empty(convex_teeth[i].name + 'co2', co2)
            #create_empty(convex_teeth[i].name + 'center', center)
            #create_bme_ob(convex_teeth[i].name + 'bme preview', bme)
            
            interval = time.time()
            for v in bme.verts:
                
                _, _, _, d3 = bvh_base.find_nearest(v.co)  #more likley to be near the original model...check this first, and will save 2 checks
                if d3 < 1.5:
                    out_patch.add(v)
                    if d3 < .2:
                        out_patch_accurate.add(v)
                      
                _, _, _, d1 = bvhs[n1].find_nearest(v.co)
                if d1 < 1.5:
                    out_patch.add(v)
                    if d1 < .25:
                        out_patch_accurate.add(v)
                        
                    continue
                _, _, _, d2 = bvhs[n2].find_nearest(v.co)
                if d2 < 1.5:
                    out_patch.add(v)
                    if d2 < .25:
                        out_patch_accurate.add(v)
                    continue
             
            vs_inner = set(bme.verts) - out_patch_accurate
            if 'Under Side' not in convex_teeth[i].vertex_groups:
                vg = convex_teeth[i].vertex_groups.new('Under Side') 
            else:
                vg = convex_teeth[i].vertex_groups.get('Under Side')
            
            vg.add([v.index for v in vs_inner], 1.0, type = 'REPLACE')
                
            print('Took %f seconds to categorize the verts' % (time.time() - interval))
            interval = time.time()
            

            average_normal = Vector((0,0,0))
            total_area = 0.0
            
            interval = time.time()
            
            for f in bme.faces:
                if not all([v not in out_patch for v in f.verts[:]]): continue
                a = f.calc_area()
                total_area += a
                average_normal += a * f.normal
            
            if abs(total_area) < .001:
                average_normal = Vector((0,0,1))
            else:
                average_normal *= 1/total_area
                average_normal.normalize()
                
            print('Took %f seconds to calc average area' % (time.time() - interval))
            interval = time.time()
            
            co_c = centers[i]
            Tmx = Matrix.Translation(co_c) #get the cetnral point
            Z = average_normal
            
            
            #Check if terminal tooth
            if (co2 - co_c).dot(co1 - co_c) > 0:
                X = co1 - co_c  #only point toward the closest
                X.normalize()
                
                if int(data_tooth_label(ob0_name)) > int(data_tooth_label(ob2_name)):
                    X *= -1
                    
            else:
                #now check direction around arch
                if int(data_tooth_label(ob1_name)) > int(data_tooth_label(ob2_name)):
                    X = (co1 - co2).normalized()
                else:
                    X = (co2 - co1).normalized() 
            
            
            
            Y = Z.cross(X)
            X = Y.cross(Z) #put mes/dis perp to root
            
            X.normalize()
            Y.normalize()
            print('AVERAGE  NORMAL MATRIX STUFF')
            print(X.length)
            print(Y.length)
            print(Z.length)
            
            #X,Y,Z = random_axes_from_normal(Z)
            Rmx = r_matrix_from_principal_axes(X,Y,Z).to_4x4()
        
            
            root_name = convex_teeth[i].name.split(' ')[0] + ' root_empty'
            root_empty = bpy.data.objects.new(root_name, None)
            root_empty.empty_draw_type = 'SINGLE_ARROW'
            root_empty.empty_draw_size = 12
            bpy.context.scene.objects.link(root_empty)
            root_empty.parent = convex_teeth[i]
            #R_parent = convex_teeth[i].matrix_world.to_quaternion().to_matrix().to_4x4()
            root_empty.matrix_world = Tmx * Rmx
            
            #bme.to_mesh(convex_teeth[i].data)
            bme.free()
    
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
    
    bme_base.transform(imx_base)
    mat = bpy.data.materials.get("Gingiva Material")
    if mat is None:
        # create material
        mat = bpy.data.materials.new(name="Gingiva Material")
        mat.diffuse_color =  Color((.9, .4, .5))
        mat.use_transparency = True
        mat.transparency_method = 'Z_TRANSPARENCY'
        mat.alpha = .4
        
        
    if base_ob == bpy.data.objects.get(bpy.context.scene.d3ortho_upperjaw):
        ging = bpy.data.objects.get('Upper Gingiva')
        if ging:
            bme_base.to_mesh(ging.data)
        else:
            me = bpy.data.meshes.new('Upper Gingiva')
            uper_ging = bpy.data.objects.new('Upper Gingiva', me)
            bpy.context.scene.objects.link(ging)
            ob.matrix_world = base_ob.matrix_world
            
            bme_base.to_mesh(me)
        
        if len(ging.data.vertex_colors):
            while len(ging.data.vertex_colors):
                ging.data.vertex_colors.remove(ging.data.vertex_colors[0])
        ging.data.materials.clear()        
        if mat.name not in ging.data.materials:
            ging.data.materials.append(mat)
            
    elif base_ob == bpy.data.objects.get(bpy.context.scene.d3ortho_lowerjaw):
        ging = bpy.data.objects.get('Lower Gingiva')
        if ging:
            bme_base.to_mesh(ging.data)
        else:
            me = bpy.data.meshes.new('Lower Gingiva')
            ging = bpy.data.objects.new('Lower Gingiva', me)
            bpy.context.scene.objects.link(ging)
            ob.matrix_world = base_ob.matrix_world
            bme_base.to_mesh(me)
        ging.data.materials.clear()
        if mat.name not in ging.data.materials:
            ging.data.materials.append(mat)
            
        if len(ging.data.vertex_colors):
            while len(ging.data.vertex_colors):
                ging.data.vertex_colors.remove(ging.data.vertex_colors[0])
        
    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
    bme_base.free()
        
        
    return new_ob2, ging
 
class AITeeth_OT_ortho_setup(bpy.types.Operator):
    """Generate Ortho Setup"""
    bl_idname = "ai_teeth.diagnostic_setup"
    bl_label = "Get Diagnostic Setup"

    tooth_selection = bpy.props.EnumProperty(name = 'Tooth Selection', items = (('ALL_TEETH','ALL_TEETH','ALL_TEETH'), ('SELECTED_TEETH','SELECTED_TEETH','SELECTED_TEETH')))
    
    add_base = bpy.props.BoolProperty(name = 'Add Base', default = True)
    auto_trim = bpy.props.BoolProperty(name = 'Auto Trim', default = True)
    decollide = bpy.props.BoolProperty(name = 'Remove Collisions', default = True)
    
    @classmethod
    def poll(cls, context):

        return context.scene.lower_teeth_segmented or context.scene.upper_teeth_segmented
        

    def invoke(self, context, event):

        
        return context.window_manager.invoke_props_dialog(self, width = 300)
    

            
    def execute(self, context):
        print('MAIN FUNCTION')
        
        bpy.ops.view3d.viewnumpad(type = 'FRONT')
        main_function(context,
                      use_select = self.tooth_selection == 'SELECTED_TEETH',
                      base = self.add_base,
                      trim = self.auto_trim,
                      decollide = self.decollide)

        bpy.context.scene.dx_setup = True
        #TODO, set up the modal operator
        return {'FINISHED'}



def register():
    bpy.utils.register_class(AITeeth_OT_ortho_setup)

def unregister():
    bpy.utils.unregister_class(AITeeth_OT_ortho_setup)
