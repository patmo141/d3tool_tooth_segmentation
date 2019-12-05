'''
'''
    
    
import bpy
import uuid
    
import os
    
class AITeeth_OT_anonymize_names(bpy.types.Operator):
    """Random_rename_models"""
    bl_idname = "ai_teeth.anonymize_names"
    bl_label = "Anonymize Names"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    def execute(self,context):
        
        safe_words = ['Upper', 'Lower', "Maxilla", "Mandible", "Mandibular", "upper", "lower", "maxilla", "mandible", "mandibular"]
        
        for ob in bpy.data.objects:
            if any(s_word in ob.name for s_word in safe_words):
                for word in safe_words:
                    if word in ob.name:
                        new_name = str(uuid.uuid4())[0:6] + word
                        ob.name = new_name
                        ob.data.name = new_name
            
            else:
                new_name = str(uuid.uuid4())[0:10]
                ob.name = new_name
                ob.data.name = new_name  
                          
        return {'FINISHED'}
    
    
    
class AITeeth_OT_open_disclosure(bpy.types.Operator):
    """Random_rename_models"""
    bl_idname = "ai_teeth.open_disclosures"
    bl_label = "Read Disclosures"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    def execute(self,context):
        
        disclosure_files_path = os.path.dirname(os.path.abspath(__file__))
        
        file_path = os.path.join(disclosure_files_path, "upload_disclosure.txt")
        
        bpy.ops.text.open(filepath = file_path)
        
        Report = bpy.data.texts.get("upload_disclosure.txt")
        
        old_windows = [w for w in context.window_manager.windows]
        
        bpy.ops.screen.area_dupli('INVOKE_DEFAULT')
        
        new_window = [w for w in context.window_manager.windows if w not in old_windows][0]
        
        screen = new_window.screen
        areas = [area for area in screen.areas]
        types = [area.type for area in screen.areas]
        
        if 'TEXT_EDITOR' not in types:
            
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    print('found the new 3d view')
                    break 
            
            area.type = 'TEXT_EDITOR'
            #bpy.ops.view3d.toolshelf() #close the first toolshelf               
            #override = context.copy()
            #override['area'] = area
            #override['window'] = new_window
            
            #bpy.ops.screen.screen_full_area(override)
           
        
     
        
        area.spaces[0].text = Report
        #override = context.copy()
        #override['area'] = area
        #bpy.ops.text.jump(override, line=1)
        
                          
        return {'FINISHED'}
    
    

    
def register():
    #bpy.utils.register_class(AI_OT_preprocess)
    bpy.utils.register_class(AITeeth_OT_anonymize_names)
    bpy.utils.register_class(AITeeth_OT_open_disclosure)
    #bpy.utils.register_class(AITeeth_OT_select_verts_by_salience_color)
    #bpy.utils.register_class(AITeeth_OT_remove_small_parts_selection)
    #bpy.utils.register_class(AITeeth_OT_dilate_erode_selection)
    #bpy.utils.register_class(AITeeth_OT_skeletonize_selection)
    #bpy.utils.register_class(AITeeth_OT_partition_and_color)
    
def unregister():
    #bpy.utils.unregister_class(AI_OT_preprocess)
    bpy.utils.unregister_class(AITeeth_OT_anonymize_names)
    bpy.utils.unregister_class(AITeeth_OT_open_disclosure)
    #bpy.utils.unregister_class(AITeeth_OT_select_verts_by_salience_color)
    #bpy.utils.unregister_class(AITeeth_OT_remove_small_parts_selection)
    #bpy.utils.unregister_class(AITeeth_OT_dilate_erode_selection)
    #bpy.utils.unregister_class(AITeeth_OT_skeletonize_selection)
    #bpy.utils.unregister_class(AITeeth_OT_partition_and_color)
    
