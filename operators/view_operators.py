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
    roots = [bpy.data.objects.get(ob.name + " root_prep") for ob in teeth if ob.name + " root_prep" in bpy.data.objects]
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
    

class AITeeth_OT_tooth_vis_popup(bpy.types.Operator):
    """Process model for shell reduction"""
    bl_idname = "ai_teeth.tooth_vis_popup"
    bl_label = "Tooth Vis Pop"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    tooth_type = bpy.props.EnumProperty(name = 'Element Type', 
                                        items = (('ORIGINAL','ORIGINAL','ORIGINAL'), ('CONVEX','CONVEX','CONVEX'), ('ROOT', 'ROOT', 'ROOT'), ('THIMBLE', 'THIMBLE', 'THIMBLE')),
                                        default = 'CONVEX')

    show_unselected = bpy.props.BoolProperty(name = 'Show Unselected', default = True)

    @classmethod
    def poll(cls, context):
        
        return True
    
    def check(self, context):
        return True
    
    def invoke(self, context, event):
        
        all, sel, upper, lower = get_teeth(context)
        
        self.upper_teeth = upper
        self.lower_teeth = lower
        
        
        self.upper_teeth.sort(key = lambda x: upper_view_order.index(data_tooth_label(x.name)))
        self.lower_teeth.sort(key = lambda x: lower_view_order.index(data_tooth_label(x.name)))
        
        self.upper_right_teeth = [ele for ele in self.upper_teeth if data_tooth_label(ele.name) in upper_right]
        self.upper_left_teeth = [ele for ele in self.upper_teeth if data_tooth_label(ele.name) in upper_left]
        
        self.lower_left_teeth = [ele for ele in self.lower_teeth if data_tooth_label(ele.name) in lower_left]
        self.lower_right_teeth = [ele for ele in self.lower_teeth if data_tooth_label(ele.name) in lower_right]
        
        context.scene.objects.active = None
        for ob in bpy.data.objects:
            ob.select = False
        
        #print(self.upper_teeth)
        #print(self.lower_teeth)
        
        print(self.upper_right_teeth)
        
        print(self.upper_left_teeth)
        
        print(self.lower_left_teeth)
        
        print(self.lower_right_teeth)
        
        return context.window_manager.invoke_props_dialog(self, width = 700)
        
    def execute(self, context):
         
        return {'FINISHED'}
    
    def draw(self, context):
        row = self.layout.row()
        row.label('Visibility')
        
        row = self.layout.row()
        split = row.split(percentage = .5)
        
        col1 = split.column()
        rowUR = col1.row()
        for ob in self.upper_right_teeth:
            rowUR.prop(ob, "hide", text = ob.name)
        rowLR = col1.row()
        for ob in self.lower_right_teeth:
            rowLR.prop(ob, "hide", text = ob.name)
        
        col2 = split.column()
        rowUL = col2.row()
        for ob in self.upper_left_teeth:
            rowUL.prop(ob, "hide", text = ob.name)
        rowLL = col2.row()
        for ob in self.lower_left_teeth:
            rowLL.prop(ob, "hide", text = ob.name)



            
            
class AITeeth_OT_tooth_sel_popup(bpy.types.Operator):
    """Process model for shell reduction"""
    bl_idname = "ai_teeth.tooth_sel_popup"
    bl_label = "Tooth Sel Pop"
    #bl_options = {'REGISTER', 'UNDO'}
    
    tooth_type = bpy.props.EnumProperty(name = 'Element Type', 
                                        items = (('ORIGINAL','ORIGINAL','ORIGINAL'), ('CONVEX','CONVEX','CONVEX'), ('ROOT', 'ROOT', 'ROOT'), ('THIMBLE', 'THIMBLE', 'THIMBLE')),
                                        default = 'CONVEX')


    show_unselected = bpy.props.BoolProperty(name = 'Show Unselected', default = True)
    
    hide_all_others = bpy.props.BoolProperty(name = 'Hide All Other', default = True, description = 'Hide all other objects in scene while selecting items')
    
    @classmethod
    def poll(cls, context):
        
        return True
    
    def check(self, context):
        
        if self.hide_all_others:
            for ob in bpy.data.objects:
                ob.hide = True
                
        self.update_teeth(context)
        for ob in self.upper_teeth:
            if ob.select == False and self.show_unselected:
                ob.hide = True
            else:
                ob.hide = False
            
        for ob in self.lower_teeth:
            if ob.select == False and self.show_unselected:
                ob.hide = True
            else:
                ob.hide = False
                
        return True
    
    
    def update_teeth(self, context):
        
        
        all, sel, upper, lower = get_teeth(context)
        
        if self.tooth_type == 'CONVEX':
            all = get_convex(all)
            sel = get_convex(sel)
            upper = get_convex(upper)
            lower = get_convex(lower)
            
        if self.tooth_type == 'ROOT':
            all = get_roots(all)
            sel = get_roots(sel)
            upper = get_roots(upper)
            lower = get_roots(lower)
            
        if self.tooth_type == 'THIMBLE':
            all = get_thimbles(all)
            sel = get_thimbles(sel)
            upper = get_thimbles(upper)
            lower = get_thimbles(lower)
            
        for ob in all:
            ob.hide_select = False
                    
        self.upper_teeth = upper
        self.lower_teeth = lower
        
        
        self.upper_teeth.sort(key = lambda x: upper_view_order.index(data_tooth_label(x.name.split(' ')[0])))
        self.lower_teeth.sort(key = lambda x: lower_view_order.index(data_tooth_label(x.name.split(' ')[0])))
        
        self.upper_right_teeth = [x for x in self.upper_teeth if data_tooth_label(x.name.split(' ')[0]) in upper_right]
        self.upper_left_teeth = [x for x in self.upper_teeth if data_tooth_label(x.name.split(' ')[0]) in upper_left]
        
        self.lower_left_teeth = [x for x in self.lower_teeth if data_tooth_label(x.name.split(' ')[0]) in lower_left]
        self.lower_right_teeth = [x for x in self.lower_teeth if data_tooth_label(x.name.split(' ')[0]) in lower_right]
        
        
        
    def invoke(self, context, event):
        
        self.hidden_obs = [ob for ob in bpy.data.objects if ob.hide]
        self.visible_obs = [ob for ob in bpy.data.objects if not ob.hide]
        
        all, sel, upper, lower = get_teeth(context)
        
        self.upper_teeth = upper
        self.lower_teeth = lower
        
        
        self.upper_teeth.sort(key = lambda x: upper_view_order.index(data_tooth_label(x.name)))
        self.lower_teeth.sort(key = lambda x: lower_view_order.index(data_tooth_label(x.name)))
        
        self.upper_right_teeth = [ele for ele in self.upper_teeth if data_tooth_label(ele.name) in upper_right]
        self.upper_left_teeth = [ele for ele in self.upper_teeth if data_tooth_label(ele.name) in upper_left]
        
        self.lower_left_teeth = [ele for ele in self.lower_teeth if data_tooth_label(ele.name) in lower_left]
        self.lower_right_teeth = [ele for ele in self.lower_teeth if data_tooth_label(ele.name) in lower_right]
        
        
        self.upper_gingiva = bpy.data.objects.get('Upper Gingiva')
        self.lower_gingiva = bpy.data.objects.get('Lower Gingiva')
        
        self.upper_model = bpy.data.objects.get(context.scene.d3ortho_upperjaw)
        self.lower_model = bpy.data.objects.get(context.scene.d3ortho_lowerjaw)
        
        if bpy.data.objects.get('Lower Gingiva'):
            lg = bpy.data.objects.get('Lower Gingniva')
            
        
        if bpy.data.objects.get('Upper Gingiva'):
            ug = bpy.data.objects.get('Upper Gingniva')
            
            
        #print(self.upper_teeth)
        #print(self.lower_teeth)
        
        print(self.upper_right_teeth)
        
        print(self.upper_left_teeth)
        
        print(self.lower_left_teeth)
        
        print(self.lower_right_teeth)
        
        return context.window_manager.invoke_props_dialog(self, width = 700)
        
    def execute(self, context):
        
        for ob in self.hidden_obs:
            ob.hide = True
        for ob in self.visible_obs:
            ob.hide = False
        return {'FINISHED'}
    
    def draw(self, context):
        row = self.layout.row()
        row.label('Selection')
        
        row = self.layout.row()
        row.prop(self, 'tooth_type')
        
        
        row = self.layout.row()
        row.label('Gingiva')
        
        if self.upper_gingiva:
            row = self.layout.row()
            row.prop(self.upper_gingiva, "hide")
            
        
        if self.lower_gingiva:
            row = self.layout.row()
            row.prop(self.lower_gingiva, "hide")
            
            
            
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
        
        
        #for ob in self.upper_teeth:
        #    row.prop(ob, "hide", text = ob.name)
        
        #row = self.layout.row()
        #for ob in self.lower_teeth:
        #    row.prop(ob, "hide", text = ob.name)
            

def register():
    bpy.utils.register_class(AITeeth_OT_tooth_vis_popup)
    bpy.utils.register_class(AITeeth_OT_tooth_sel_popup)
    

def unregister():
    bpy.utils.register_class(AITeeth_OT_tooth_vis_popup)
    bpy.utils.register_class(AITeeth_OT_tooth_sel_popup)