'''
Created on Dec 26, 2019

@author: Patrick
'''
from ..tooth_numbering import data_tooth_label
from .. import tooth_numbering
'''
Created on Nov 27, 2020

@author: Patrick
'''

import bpy

from ..common.utils import get_settings



from ..tooth_numbering import upper_right, upper_left, lower_left, lower_right, upper_view_order, lower_view_order, data_tooth_label
    
    
    
def get_convex(teeth):
    convex_teeth = [bpy.data.objects.get(ob.name + " Convex") for ob in teeth if ob.name + " Convex" in bpy.data.objects]     
    return convex_teeth

       
def get_roots(teeth):
    roots = [bpy.data.objects.get(ob.name.split(' ')[0] + " root_prep") for ob in teeth if ob.name + " root_prep" in bpy.data.objects]
    return roots
  
  
def get_thimbles(teeth):
    thimbles = [bpy.data.objects.get(ob.name + " thimble_prep") for ob in teeth if ob.name + " thimble_prep" in bpy.data.objects]
    return thimbles
  
def get_teeth(context):                                     
    
    selected_teeth = [ob for ob in context.scene.objects if ob.type == 'MESH' and 'tooth' in ob.data.name and ob.select]
    all_teeth = [ob for ob in context.scene.objects if ob.type == 'MESH' and 'tooth' in ob.data.name]
    upper_teeth = [ob for ob in all_teeth if data_tooth_label(ob.name) in tooth_numbering.upper_teeth]
    lower_teeth = [ob for ob in all_teeth if data_tooth_label(ob.name) in tooth_numbering.lower_teeth]
    
    
    
    return all_teeth, selected_teeth, upper_teeth, lower_teeth
      
            
class AITeeth_OT_tooth_dies_popup(bpy.types.Operator):
    """Mark Teeth for Extraction"""
    bl_idname = "ai_teeth.mark_die_teeth"
    bl_label = "Mark Removable Dies"
    #bl_options = {'REGISTER', 'UNDO'}
    
    
    
    @classmethod
    def poll(cls, context):
        
        return True
    
    def check(self, context):
        
        
        for ob in self.upper_teeth + self.lower_teeth:
            if ob.get('EXTRACT') == 1:
                ob.hide = True
                for child in ob.children:
                    child.hide = True
                
                print('EXTRACTED Teeth')    
                continue
                
            if (ob.get('REMOVABLE_DIE') == 1) != ob.select:
                ob['REMOVABLE_DIE'] = ob.select
                
            
            ob.hide = ob.select
            for child in ob.children:
                if child.type == 'EMPTY':
                    child.hide = True
                elif "root_prep" in child.name:
                    child.hide = ob.get('REMOVABLE_DIE') == 0
                    child.show_x_ray = ob.get('REMOVABLE_DIE') == 1
                    if ob.get('REMOVABLE_DIE'):
                        child.draw_type = 'WIRE'
                    else:
                        child.draw_type = 'SOLID'
                else:
                    child.hide = ob.select
                    
        return True
    
    
    def update_teeth(self, context):
        
        
        all, sel, upper, lower = get_teeth(context)
        
        all = get_convex(all)
        sel = get_convex(sel)

        
        
        self.upper_teeth.sort(key = lambda x: upper_view_order.index(data_tooth_label(x.name.split(' ')[0])))
        self.lower_teeth.sort(key = lambda x: lower_view_order.index(data_tooth_label(x.name.split(' ')[0])))
        
        self.upper_right_teeth = [x for x in self.upper_teeth if data_tooth_label(x.name.split(' ')[0]) in upper_right]
        self.upper_left_teeth = [x for x in self.upper_teeth if data_tooth_label(x.name.split(' ')[0]) in upper_left]
        
        self.lower_left_teeth = [x for x in self.lower_teeth if data_tooth_label(x.name.split(' ')[0]) in lower_left]
        self.lower_right_teeth = [x for x in self.lower_teeth if data_tooth_label(x.name.split(' ')[0]) in lower_right]
        
        
        
        
    def invoke(self, context, event):
        
        self.hidden_obs = [ob for ob in bpy.data.objects if ob.hide]
        self.visible_obs = [ob for ob in bpy.data.objects if not ob.hide]
        for ob in bpy.data.objects:
            ob.hide = True
            ob.select = False
            
        all, sel, upper, lower = get_teeth(context)

                
        self.upper_teeth = get_convex(upper)
        self.lower_teeth = get_convex(lower)
        
        for ob in self.upper_teeth + self.lower_teeth:
            if ob.get('REMOVABLE_DIE') == None:
                #create the custom ID prop
                ob['REMOVABLE_DIE'] = False
                
            else:
                print('ALREADY HAS IT')
                ob.hide = ob.get('REMOVABLE_DIE') == 1
                ob.select = ob.get('REMOVABLE_DIE') == 1
                
            if ob.get('REMOVABLE_DIE') != None:
                ob.hide = ob.get('REMOVABLE_DIE') == True
                
                if ob.get('REMOVABLE_DIE') == 1:
                    for child in ob.children:
                        if 'root_prep' in child.name:
                            child.draw_type = 'WIRE'
                            child.show_x_ray = True
                
        
        
        self.upper_teeth.sort(key = lambda x: upper_view_order.index(data_tooth_label(x.name.split(' ')[0])))
        self.lower_teeth.sort(key = lambda x: lower_view_order.index(data_tooth_label(x.name.split(' ')[0])))
        
        self.upper_right_teeth = [ele for ele in self.upper_teeth if data_tooth_label(ele.name.split(' ')[0]) in upper_right]
        self.upper_left_teeth = [ele for ele in self.upper_teeth if data_tooth_label(ele.name.split(' ')[0]) in upper_left]
        
        self.lower_left_teeth = [ele for ele in self.lower_teeth if data_tooth_label(ele.name.split(' ')[0]) in lower_left]
        self.lower_right_teeth = [ele for ele in self.lower_teeth if data_tooth_label(ele.name.split(' ')[0]) in lower_right]
        
        
        self.upper_gingiva = bpy.data.objects.get('Upper Gingiva')
        self.lower_gingiva = bpy.data.objects.get('Lower Gingiva')
        
        self.upper_model = bpy.data.objects.get(context.scene.d3ortho_upperjaw)
        self.lower_model = bpy.data.objects.get(context.scene.d3ortho_lowerjaw)
        
        if bpy.data.objects.get('Lower Gingiva'):
            lg = bpy.data.objects.get('Lower Gingiva')
            
            lg.hide = False
            
        if bpy.data.objects.get('Upper Gingiva'):
            ug = bpy.data.objects.get('Upper Gingiva')
            ug.hide = False
        
        return context.window_manager.invoke_props_dialog(self, width = 700)
        
    def execute(self, context):
        print('EXECUTE')
        
        for ob in self.hidden_obs:
            ob.hide = True
        for ob in self.visible_obs:
            ob.hide = False
            
        for ob in self.upper_teeth + self.lower_teeth:
            ob.select = False
            
            if ob.get('REMOVABLE_DIE') == 1:
                ob.hide = True
                for child in ob.children:
                    if "root_prep" not in child.name:
                        child.hide = True
                    else:
                        child.hide = False

            
        return {'FINISHED'}
    
    def draw(self, context):
        
        
        
        row = self.layout.row()
        row.label('Make Removable Dies')
        
        row = self.layout.row()
        split = row.split(percentage = .5)
        
        col1 = split.column()
        rowUR = col1.row()
        
        for ob in self.upper_right_teeth:
            rowUR.prop(ob, "select", text = ob.name)
        rowLR = col1.row()
        for ob in self.lower_right_teeth:
            rowLR.prop(ob, "select", text = ob.name)
        
        col2 = split.column()
        rowUL = col2.row()
        for ob in self.upper_left_teeth:
            rowUL.prop(ob, "select", text = ob.name)
        rowLL = col2.row()
        for ob in self.lower_left_teeth:
            rowLL.prop(ob, "select", text = ob.name)   

            
 
            

def register():
    bpy.utils.register_class(AITeeth_OT_tooth_dies_popup)
    

def unregister():
    bpy.utils.unregister_class(AITeeth_OT_tooth_dies_popup)