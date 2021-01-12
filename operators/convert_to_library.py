'''
Created on Jan 11, 2021

@author: Patrick
'''

import bpy
import bmesh
import time
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

from .. import tooth_numbering

from ..subtrees.geometry_utils.transformations import calculate_plane

def get_convex(teeth):
    convex_teeth = [bpy.data.objects.get(ob.name + " Convex") for ob in teeth if ob.name + " Convex" in bpy.data.objects]     
    return convex_teeth

def spline_obj_from_RDP_nodes(nodes,name, cyclic = True,):
    '''
    list of vertex coords
    closed loop or not
    name
    
    '''
    
    if name in bpy.data.objects:
        spline_obj = bpy.data.objects.get(name)
        spline_data = spline_obj.data
    
        #clear old spline data, dont remove items form list while iterating over it
        splines = [s for s in spline_data.splines]
        for s in splines:
            spline_data.splines.remove(s)
                
    else:
        spline_data = bpy.data.curves.new(name, 'CURVE')
        spline_obj = bpy.data.objects.new(name, spline_data)
        bpy.context.scene.objects.link(spline_obj)
        #crv_obj.parent = self.obj
        #crv_obj.matrix_world = self.obj.matrix_world
        
    spline_obj.data.dimensions = '3D'
    spline = spline_data.splines.new('BEZIER')
    spline.bezier_points.add(count = len(nodes) - 1)
    for i,node in enumerate(nodes):
        bpt = spline.bezier_points[i]
        bpt.handle_right_type = 'AUTO'
        bpt.handle_left_type = 'AUTO'
        bpt.co = node
    
    if cyclic:
        spline.use_cyclic_u = True          
    return spline_obj

def convert_teeth_to_arch_lib(context, teeth, archname):

    

    start = time.time()
    #get the gingiva and teeth
    
    teeth.sort(key = lambda x: int(x.name.split(' ')[0]))
    bme = bmesh.new()
    bme.verts.ensure_lookup_table()
    
    high_points = []
    vert_map = []
    for tooth in teeth:
        mx = tooth.matrix_world
        
        #teeth are assumed to be axis aigned by the user
        v_occlusal = min(tooth.data.vertices, key = lambda x: x.co[2])  #Y is always lingual, Z is always apical, X points in direction of tooth numbering system 1 to 32
        v_facial = min(tooth.data.vertices, key = lambda x: x.co[1])
        
        
        v_convex = mx * Vector((0, v_facial.co[1], v_occlusal.co[2]))
        high_points.append(v_convex)
        
        #most_occlusals.append(v_occlusal.co)
        #most_facials.append(v_facial.co)
        vert_map.append((len(bme.verts), len(bme.verts) + len(tooth.data.vertices)))  #maybe -1
        imx = mx.inverted()
        tooth.data.transform(mx)
        bme.from_mesh(tooth.data)
        tooth.data.transform(imx)
        
 
        
    out_geom = bmesh.ops.convex_hull(bme, input = bme.verts[:], use_existing_faces = True)
                    
    unused_geom = out_geom['geom_interior']       
    del_v = [ele for ele in unused_geom if isinstance(ele, bmesh.types.BMVert)]
    del_f = [ele for ele in unused_geom if isinstance(ele, bmesh.types.BMFace)]
            
    #these must go
    bmesh.ops.delete(bme, geom = del_v, context = 1)
    #bmesh.ops.delete(bme, geom = del_e, context = )
    bmesh.ops.delete(bme, geom = del_f, context = 5)
    
    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    
    bvh = BVHTree.FromBMesh(bme)
    
    v_most_anterior = min(bme.verts, key = lambda x: x.co[1])
    
    loc, no = calculate_plane(high_points, itermax = 500, debug = False)
    
    com = Vector((0,loc[1], loc[2]))
    anterior_midpoint = Vector((0, v_most_anterior.co[1], com[2]))
    
    snapped_points = []
    for i, tooth in enumerate(teeth):
        loc, no, ind, d = bvh.find_nearest(high_points[i])
        snapped_points.append(loc)
        
    
    loc, no = calculate_plane(snapped_points, itermax = 500, debug = False)
    for i in range(0, len(snapped_points)):
        v = snapped_points[i]
        snapped_points[i] = v - (v - com).dot(no) * no
        
    
    v0 = snapped_points[0] - snapped_points[1]
    v0.normalize()
    
    v_end = snapped_points[-1] - snapped_points[-2]
    v_end.normalize()
    
    snapped_points.insert(0, snapped_points[0] + 10 * v0)
    snapped_points.append(snapped_points[-1] + 10 * v_end)
    
    new_curve = spline_obj_from_RDP_nodes(snapped_points, archname + ' Baseline Curve', False)
    
    bme.free()
    
    
    
    
    
    
class AITeeth_OT_arch_baseline_curves(bpy.types.Operator):
    """Creates Baseline Curves for this case"""
    bl_idname = "aiteeth.arch_baseline_curves"
    bl_label = "Calculate Baseline Curves"
    
    
    @classmethod
    def poll(cls, context):
        #gingiva
        #teeth
        #animated
        #etc
        return True
    
    
    def execute(self, context):
       
    
        selected_teeth = [ob for ob in bpy.context.scene.objects if ob.type == 'MESH' and 'tooth' in ob.data.name]

        upper_teeth = get_convex([ob for ob in selected_teeth if tooth_numbering.data_tooth_label(ob.name) in tooth_numbering.upper_teeth])
        lower_teeth = get_convex([ob for ob in selected_teeth if tooth_numbering.data_tooth_label(ob.name) in tooth_numbering.lower_teeth])

        print(upper_teeth)
        print(lower_teeth)
        
        if len(upper_teeth) >= 6:
            convert_teeth_to_arch_lib(context, upper_teeth, 'Upper')
        
        if len(lower_teeth) >= 6:
            convert_teeth_to_arch_lib(context, lower_teeth, 'Lower')
        
        
        return {'FINISHED'}
    
    
class AITeeth_OT_convert_file_to_tooth_library(bpy.types.Operator):
    """Reduces file to just the convex teeth, shells, roots and baseline curves"""
    bl_idname = "aiteeth.convert_file_to_library"
    bl_label = "Convert Segmentation to Library"

    
    @classmethod
    def poll(cls, context):
        #dx setup
        #axes adjsuted
        
        #teeth
        #animated
        #etc
        return True
    
    
    def execute(self, context):
       
    
        selected_teeth = [ob for ob in bpy.context.scene.objects if ob.type == 'MESH' and 'tooth' in ob.data.name]

        convex_teeth = get_convex([ob for ob in selected_teeth])

        obs_to_keep = set()
        obs_to_keep.update(convex_teeth)
        
        bpy.ops.aiteeth.arch_baseline_curves()
        
        if 'Upper Baseline Curve' in bpy.data.objects:
            obs_to_keep.add(bpy.data.objects.get('Upper Baseline Curve'))
            
        if 'Lower Baseline Curve' in bpy.data.objects:
            obs_to_keep.add(bpy.data.objects.get('Lower Baseline Curve'))
            
        key_names = ['margin_line', 'open_shell', 'root_empty']
        for ob in convex_teeth:
            for child in ob.children:
                if any([name in child.name for name in key_names]):
                    obs_to_keep.add(child)
        
        
        to_delete = set(bpy.data.objects) - obs_to_keep
        
        for ob in to_delete:
            if ob.name in bpy.context.scene.objects:
                bpy.context.scene.objects.unlink(ob)
            bpy.data.objects.remove(ob)
            
        return {'FINISHED'}
    



def register():
    bpy.utils.register_class(AITeeth_OT_arch_baseline_curves)
    bpy.utils.register_class(AITeeth_OT_convert_file_to_tooth_library)

def unregister():
    bpy.utils.unregister_class(AITeeth_OT_arch_baseline_curves)
    bpy.utils.unregister_class(AITeeth_OT_convert_file_to_tooth_library)
