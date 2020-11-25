'''
Created on Aug 9, 2019

@author: Patrick
'''
import bpy


        
        
class AITEETH_OT_segment_mandibular_teeth(bpy.types.Operator):
    """ Segment on the desired teeth"""
    bl_idname = "aiteeth.segment_lower_teeth"
    bl_label = "Segment Lower Teeth"
    bl_description = "Indicate points to identify each tooth"
    
    @classmethod
    def poll(cls, context):
        if context.scene.d3ortho_lowerjaw in bpy.data.objects:
            return True
        
        return False
    
    
    def execute(self,context):
        
        
        ob = bpy.data.objects.get(context.scene.d3ortho_lowerjaw)
        
        context.scene.objects.active = ob
        ob.select = True
        ob.hide = False
        
        bpy.ops.aiteeth.polytrim("INVOKE_DEFAULT")
        
        return {'FINISHED'}
    
class AITEETH_OT_segment_maxillary_teeth(bpy.types.Operator):
    """ Segment on the desired teeth"""
    bl_idname = "aiteeth.segment_upper_teeth"
    bl_label = "Segment Upper Teeth"
    bl_description = "Interactive segment"
    
    @classmethod
    def poll(cls, context):
        if context.scene.d3ortho_upperjaw in bpy.data.objects:
            return True
        
        return False
    
    
    def execute(self,context):
        
        
        ob = bpy.data.objects.get(context.scene.d3ortho_upperjaw)
        
        context.scene.objects.active = ob
        ob.select = True
        ob.hide = False
        
        bpy.ops.aiteeth.polytrim("INVOKE_DEFAULT")
        
        return {'FINISHED'}
        

def register():
    bpy.utils.register_class(AITEETH_OT_segment_maxillary_teeth)
    bpy.utils.register_class(AITEETH_OT_segment_mandibular_teeth)
    
     
def unregister():
    bpy.utils.register_class(AITEETH_OT_segment_maxillary_teeth)
    bpy.utils.register_class(AITEETH_OT_segment_mandibular_teeth)