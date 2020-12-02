'''
Created on Feb 19, 2020

@author: Patrick
'''

import bpy
import bmesh
import time

from mathutils.bvhtree import BVHTree

from ..subtrees.metaballs.vdb_tools import remesh_bme
from ..subtrees.bmesh_utils.bmesh_utilities_common import bmesh_join_list


from .. import tooth_numbering


def get_convex(teeth):
    convex_teeth = [bpy.data.objects.get(ob.name + " Convex") for ob in teeth if ob.name + " Convex" in bpy.data.objects]     
    return convex_teeth


def main(context, gingiva, teeth, frame):

    context.scene.frame_set(frame)

    start = time.time()
    #get the gingiva and teeth
    
    
    attachments = []
    roots = []
    for tooth in teeth:
        for child in tooth.children:
            if 'CB_attach' in child.name:
                attachments.append(child)
            if 'root_prep' in child.name:
                roots.append(child)   
    
    bme = bmesh.new()
    bme.from_object(gingiva, context.scene)
    bme.transform(gingiva.matrix_world)
    
    

    #fastest way to join objects
    for ob in teeth + attachments + roots:
        
        mx = ob.matrix_world
        imx = mx.inverted()
        
        ob.data.transform(mx)
        bme.from_mesh(ob.data)
        ob.data.transform(imx)
    
     
    remeshed_model = remesh_bme(bme, isovalue = 0.0, voxel_size = .15, adaptivity = 7.0)
    
    
    new_me = bpy.data.meshes.new(gingiva.name[0:5] + ' ' + str(frame))
    new_ob = bpy.data.objects.new(gingiva.name[0:5] + str(frame), new_me)
    
    context.scene.objects.link(new_ob)
    remeshed_model.to_mesh(new_me)
    #bme.to_mesh(new_me)
    
    bme.free()
    remeshed_model.free()
    
    finish = time.time()
    print('made solid model in %f seconds' % (finish - start))
    return new_ob
    
    
class AITeeth_OT_keyframe_to_solid(bpy.types.Operator):
    """Create Model of Current Keyframe"""
    bl_idname = "d3ortho.keyframe_solid"
    bl_label = "Keyframe to Solid"

    
    
    @classmethod
    def poll(cls, context):
        #gingiva
        #teeth
        #animated
        #etc
        return True
    
    
    def execute(self, context):
        frame = context.scene.frame_current
        
        
        
        selected_teeth = [ob for ob in bpy.context.scene.objects if ob.type == 'MESH' and 'tooth' in ob.data.name]
        
        upper_teeth = get_convex([ob for ob in selected_teeth if tooth_numbering.data_tooth_label(ob.name) in tooth_numbering.upper_teeth])
        lower_teeth = get_convex([ob for ob in selected_teeth if tooth_numbering.data_tooth_label(ob.name) in tooth_numbering.lower_teeth])
        upper_ging = bpy.data.objects.get('Upper Gingiva')
        lower_ging = bpy.data.objects.get('Lower Gingiva')
    
    
        new_obs = []
        if upper_ging and upper_teeth:
            
            new_obs.append(main(context, upper_ging, upper_teeth, frame))
            
        if lower_ging and lower_teeth:
            
            new_obs.append(main(context, lower_ging, lower_teeth, frame))
            
        for ob in bpy.data.objects:
            ob.select = False
            ob.hide = True
            
        for ob in new_obs:
            ob.hide = False
        
        return {'FINISHED'}
    
def register():
    bpy.utils.register_class(AITeeth_OT_keyframe_to_solid)


def unregister():
    bpy.utils.register_class(AITeeth_OT_keyframe_to_solid)
    
