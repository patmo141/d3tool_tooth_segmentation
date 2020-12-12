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
from mathutils import Vector, Matrix, Color
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree


from d3lib.bmesh_utils.bmesh_delete import bmesh_fast_delete
from d3lib.geometry_utils.bound_box_utils import get_bbox_center
from d3lib.bmesh_utils.bmesh_utilities_common import bmesh_join_list, increase_vert_selection, new_bmesh_from_bmelements
from d3guard.subtrees.metaballs.vdb_tools import remesh_bme
from d3lib.geometry_utils.transformations import r_matrix_from_principal_axes, random_axes_from_normal

from ..tooth_numbering import data_tooth_label
from .. import tooth_numbering

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
    
    
 
class AITeeth_OT_final_model(bpy.types.Operator):
    """Create Final Model"""
    bl_idname = "ai_teeth.final_model"
    bl_label = "Create Final Model"

    
    
    
    @classmethod
    def poll(cls, context):

        return True


            
    def execute(self, context):
        
        #which teeth are to be extracted?
        
        #which teeth are to be removable dies
        
        #which teeth are to be preps
        
        #
        
        #TODO, set up the modal operator
        return {'FINISHED'}



def register():
    bpy.utils.register_class(AITeeth_OT_ortho_setup)

def unregister():
    bpy.utils.unregister_class(AITeeth_OT_ortho_setup)
