'''
Created on Nov 27, 2019

@author: Patrick
'''
import bpy




##Methods to overwrite per job
def validate_scene(scn):
    #make sure the scene is appropriate for cloud operation
    return True
    
    
def check_credits(key):
    #submit user key to the credit check link
    credit_balance = 4.0
    
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


class SimpleCloudComputeOperator(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "object.simple_cloud_operator"
    bl_label = "Simple Cloud Operator"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def invoke(self, context, event):
        #validate scene
        #if not valid, warn users -> cancel
        #check credits
        #show popup with credit amount, ask user if they are sure
        
        return context.window_manager.invoke_props_dialog(self, event)
    
    def draw(self, context):
        
        #this job requires %f compute credit
        #you have %f compute credit remaining
        #property 1
        #property 2
        #submit the job?
        
        return
            
    def execute(self, context):
        main(context)
        return {'FINISHED'}


def register():
    bpy.utils.register_class(SimpleCloudComputeOperator)


def unregister():
    bpy.utils.unregister_class(SimpleCloudComputeOperator)


if __name__ == "__main__":
    register()

    # test call
    bpy.ops.object.simple_operator()
