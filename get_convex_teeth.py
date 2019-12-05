'''
Created on Nov 27, 2019

@author: Patrick
'''
import requests
import json


import bpy
from bpy.props import *

from .common.utils import get_settings


##Methods to overwrite per job
def validate_scene(scn):
    #make sure the scene is appropriate for cloud operation
    return True
    
    
def check_credits(key):
    #submit user key to the credit check link
    credit_balance = 4.0
    
    server = 'http://104.196.199.206'
    
    url = 'http://104.196.199.206/get_credits?key={}'.format(key)
    
    print(url)
    jdict = json.loads(requests.get(url).text)
    
    print(jdict)
    if jdict:
        credit_balance = jdict['credits']
    else:
        credit_balnce = -1
    return credit_balance

def sumbit_job(context, job_type, user_key):
    #need some job_type dictionary so the server knows wtf to do with it?
    #collect all the data, package it into blend file
    return


def retrieve_preview():
    #get some preview data
    #put it in the scene
    return

def main(context):
    for ob in context.scene.objects:
        print(ob)


class AITeeth_OT_cloud_convex_teeth(bpy.types.Operator):
    """Submit file to get convex teeth"""
    bl_idname = "ai_teeth.cloud_convex_teeth"
    bl_label = "Cloud Convex Teeth"

    credits_cost =  FloatProperty(name = 'Available Credits', default = 5.0)
    credits_avail = FloatProperty(name = 'Available Credits', default = 0.0)
    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def invoke(self, context, event):
        #validate scene
        #if not valid, warn users -> cancel
        #check credits
        #show popup with credit amount, ask user if they are sure
        
        prefs = get_settings()
        key_file = open(prefs.key_path)
        key_val = key_file.read()
        
        print(key_val)
        
        self.credits_avail = check_credits(key_val)
        
        
        return context.window_manager.invoke_props_dialog(self, width = 300)
    
    def draw(self, context):
        
        layout = self.layout
        
        row = layout.row()
        text = 'This operation costs {:.2f}'.format(self.credits_cost)
        row.label(text)
        
        row = layout.row()
        text = 'You have {:.2f} credits available'.format(self.credits_avail)
        row.label(text)
        
        
        #this job requires %f compute credit
        #you have %f compute credit remaining
        #property 1
        #property 2
        #submit the job?
        
        return
            
    def execute(self, context):
        
        
        #TODO, set up the modal operator
        return {'FINISHED'}



def register():
    bpy.utils.register_class(AITeeth_OT_cloud_convex_teeth)


def unregister():
    bpy.utils.unregister_class(AITeeth_OT_cloud_convex_teeth)


if __name__ == "__main__":
    register()

    # test call
    bpy.ops.object.simple_operator()