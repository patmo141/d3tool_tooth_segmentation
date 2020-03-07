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




def main(context, frame):

    context.scene.frame_set(frame)

    start = time.time()
    #get the gingiva and teeth
    gingiva = bpy.data.objects.get('Base Gingiva')
    teeth = [ob for ob in bpy.data.objects if 'Convex' in ob.name]
    attachments = [ob for ob in bpy.data.objects if 'CB' in ob.name]

    bme_teeth = []
    
    bme_gingiva = bmesh.new()
    bme_gingiva.from_object(gingiva, context.scene)
    bme_gingiva.transform(gingiva.matrix_world)
    
    bme_teeth = []
    
    for ob in teeth + attachments:
        bme = bmesh.new()
        bme.from_object(ob, context.scene)
        bme.transform(ob.matrix_world)
        bme_teeth.append(bme)
    
    
    unified_teeth = bmesh_join_list(bme_teeth)    
    bvh = BVHTree.FromBMesh(unified_teeth)
    
    
        
    for v in bme_gingiva.verts:
        loc, no, ind, d = bvh.find_nearest(v.co)
        
        if d < .25:
            v.co = loc
        
    
    unified_model = bmesh_join_list([bme_gingiva, unified_teeth])
    remeshed_model = remesh_bme(unified_model, isovalue = 0.0, voxel_size = .15)
    
    
    me = bpy.data.meshes.new('Output' + str(frame))
    ob = bpy.data.objects.new('Output' + str(frame), me)
    
    context.scene.objects.link(ob)
    remeshed_model.to_mesh(me)
    #unified_model.to_mesh(me)
    
    for bme in bme_teeth:
        bme.free()
    unified_teeth.free()
    unified_model.free()
    remeshed_model.free()
    
    finish = time.time()
    print('made solid model in %f seconds' % (finish - start))
    
    
    
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
        
        main(context, frame)
        
        return {'FINISHED'}
    
def register():
    bpy.utils.register_class(AITeeth_OT_keyframe_to_solid)


def unregister():
    bpy.utils.register_class(AITeeth_OT_keyframe_to_solid)
    
