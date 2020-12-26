'''
Created on Aug 9, 2019

@author: Patrick
'''
import math
import random

import bpy
import bmesh
from mathutils import Vector, Matrix
from bpy.props import *
# Addon imports

from ..subtrees.point_picker.operators.points_picker import VIEW3D_OT_points_picker
from ..subtrees.point_picker.operators.points_picker.points_picker_datastructure import D3Point
from ..subtrees.point_picker.subtrees.addon_common.common import ui
from ..subtrees.point_picker.functions.common import showErrorMessage

from ..common.utils import get_settings
from ..tooth_numbering import fdi_to_uni, uni_to_fdi, preference_tooth_label, data_tooth_label


upper_perm = ['1','2','3','4','5','6','7','8','9','10','11','12','13','14','15','16']
upper_prim = ['A','B','C','D','E','F','G','H','I','J']
lower_perm = ['17','18','19','20','21','22','23','24','25','26','27','28','29','30','31','32']
lower_prim = ['K','L','M','N','O','P','Q','R','S','T']
  
class AITEETH_OT_label_mandibular_teeth(bpy.types.Operator):
    """ Click on the desired teeth"""
    bl_idname = "aiteeth.mark_lower_tooth_locations"
    bl_label = "AI Mark Lower Tooth Locations"
    bl_description = "Indicate points to identify each tooth"
    
    @classmethod
    def poll(cls, context):
        if not context.scene.models_oriented: return False
        
        if context.scene.d3ortho_lowerjaw in bpy.data.objects:
            return True
        
        return False
    
    
    def execute(self,context):
        
        
        ob = bpy.data.objects.get(context.scene.d3ortho_lowerjaw)
        
        context.scene.objects.active = ob
        ob.select = True
        ob.hide = False
        bpy.ops.view3d.viewnumpad(type = 'TOP')
        bpy.ops.aiteeth.mark_tooth_locations("INVOKE_DEFAULT")
        
        return {'FINISHED'}
    
class AITEETH_OT_label_maxillary_teeth(bpy.types.Operator):
    """ Click on the desired teeth"""
    bl_idname = "aiteeth.mark_upper_tooth_locations"
    bl_label = "AI Mark Upper Tooth Locations"
    bl_description = "Indicate points to identify each tooth"
    
    @classmethod
    def poll(cls, context):
        
        if not context.scene.models_oriented: return False
        
        if context.scene.d3ortho_upperjaw in bpy.data.objects:
            return True
        
        return False
    
    
    def execute(self,context):
        
        
        ob = bpy.data.objects.get(context.scene.d3ortho_upperjaw)
        
        context.scene.objects.active = ob
        ob.select = True
        bpy.ops.view3d.viewnumpad(type = 'BOTTOM')
        bpy.ops.aiteeth.mark_tooth_locations("INVOKE_DEFAULT")
        
        return {'FINISHED'}
        
class AITEETH_OT_label_teeth(VIEW3D_OT_points_picker):
    """ Click on the desired teeth"""
    bl_idname = "aiteeth.mark_tooth_locations"
    bl_label = "AI Mark Tooth Locations"
    bl_description = "Indicate points to identify each tooth"

    #############################################
    # overwriting functions from wax drop

    @classmethod
    def can_start(cls, context):
        
        if not context.object: return False
        if context.object.name == context.scene.d3ortho_upperjaw: return True
        if context.object.name == context.scene.d3ortho_lowerjaw: return True
        
        return False

    
    def start_pre(self):
        #create a container for the points
        
        if bpy.context.object.name == bpy.context.scene.d3ortho_upperjaw:
            self.seg_type = 'MAX_PERM'
        
        elif bpy.context.object.name == bpy.context.scene.d3ortho_lowerjaw:
            self.seg_type = 'MAND_PERM'
            
        self.build_labels()
        
        for ob in bpy.data.objects:
            if ob != bpy.context.object:
                ob.hide = True
                
        bpy.context.object.hide = False
        pass

    def build_labels(self):
        
        if self.seg_type == 'MAX_PERM':
            label_list = upper_perm
            self.active_label = preference_tooth_label('2')
        elif self.seg_type == 'MAX_PRIM':
            label_list = upper_prim
            self.active_label = preference_tooth_label('A')
        elif self.seg_type == 'MAX_MIXED':
            label_list = upper_perm + upper_prim
            self.active_label = preference_tooth_label('3')
        elif self.seg_type == 'MAND_PERM':
            label_list = lower_perm
            self.active_label = preference_tooth_label('18')
        elif self.seg_type == 'MAND_PRIM':
            label_list = lower_prim
            self.active_label = preference_tooth_label('K')
        elif self.seg_type == 'MAND_MIXED':
            label_list = lower_perm + lower_prim
            self.active_label = preference_tooth_label('19')
        
        self.labels = [preference_tooth_label(name) for name in label_list]
        
    def start_post(self):
        
        scn = bpy.context.scene
        ob = bpy.context.object
        mx = bpy.context.object.matrix_world
        imx = mx.inverted()
        
        name = "seed" + self.seg_type

            
        if name in bpy.data.objects:
            container = bpy.data.objects.get(name)
            container_mesh = container.data
        
            bme = bmesh.new()
            bme.from_mesh(container_mesh)
            key1 = bme.verts.layers.string.get('label')
            for v in bme.verts:
                new_point = D3Point(location=mx * v.co,surface_normal= Vector((0,0,1)), view_direction=Vector((0,0,1)), source_object=ob)
                self.b_pts.append(new_point)
                
                #custom data layer
                if key1:
                    new_point.label = v[key1].decode()
        
       
     
       
    def skip_label(self):
        n = self.labels.index(self.active_label)
        n_next = int(math.fmod(n+1, len(self.labels)))
        self.active_label = self.labels[n_next]
        self.win_obvious_instructions.hbf_title.set_label('Click ' + self.active_label)    
          
    def resetLabels(self):  #must override this becuase we have pre-defineid label names
        return          
    
    def add_point_post(self, pt_added):
        
        #check for relabel
        labels = [pt.label for pt in self.b_pts]
        if self.active_label in labels:
            #delete old poitn
            del_pt = [pt for pt in self.b_pts if pt.label == self.active_label][0]
            self.b_pts.remove(del_pt)
        
        
        new_pt = self.b_pts[-1]    
        new_pt.label = self.active_label  
    
        
        n = self.labels.index(self.active_label)
        n_next = int(math.fmod(n+1, len(self.labels)))
        self.active_label = self.labels[n_next] 
        
        
        self.win_obvious_instructions.visible = True
        self.win_obvious_instructions.hbf_title.set_label('Click ' + self.active_label)     
        
    
    def move_point_post(self, pt):
        self.active_label = pt.label
        self.skip_label()
             
        
    def getLabel(self, idx):
        return "P %(idx)s" % locals()

    #def get_matrix_world_for_point(self, pt):
    #   
    #    if pt.label == "Replacement Point":
    #        #Z = pt.view_direction * Vector((0,0,1))  #TODO until pt.view_direction is not a quaternion
    #        Z = -pt.view_direction
    #    else:
    #        Z = pt.surface_normal
           
    #    x_rand = Vector((random.random(), random.random(), random.random()))
    #    x_rand.normalize()

    #    if abs(x_rand.dot(Z)) > .9:
    #        x_rand = Vector((random.random(), random.random(), random.random()))
    #        x_rand.normalize()
    #    X = x_rand - x_rand.dot(Z) * Z
    #    X.normalize()

    #    Y = Z.cross(X)

    #    R = Matrix.Identity(3)  #make the columns of matrix U, V, W
    #    R[0][0], R[0][1], R[0][2]  = X[0] ,Y[0],  Z[0]
    #    R[1][0], R[1][1], R[1][2]  = X[1], Y[1],  Z[1]
    #    R[2][0] ,R[2][1], R[2][2]  = X[2], Y[2],  Z[2]
    #    R = R.to_4x4()

    #    if pt.label == "Replacement Point":
    #        T = Matrix.Translation(pt.location + 2 * Z)
    #    else:
    #        T = Matrix.Translation(pt.location)

    #    return T * R
    #############################################

    #def end_commit(self):
    #push all points into the empty
    #start up the next intearctive tool    
    
    def end_commit(self):
        """ Commit changes to mesh! """
        scn = bpy.context.scene
        mx = bpy.context.object.matrix_world
        imx = mx.inverted()
        
        name = name = "seed" + self.seg_type
        
        bme = bmesh.new()
        bme.verts.ensure_lookup_table()
       
        if name in bpy.data.objects:
            container = bpy.data.objects.get(name)
            container_mesh = container.data
        else:
            container_mesh = bpy.data.meshes.new(name)
            container = bpy.data.objects.new(name, container_mesh)
            scn.objects.link(container)
            container.parent = bpy.context.object
        
        key1 = bme.verts.layers.string.new('label')
        print(key1)
        for pt in self.b_pts:
            v = bme.verts.new(imx * pt.location)
            
            #store label in vertex data layer
            v[key1] = pt.label.encode()
            
            #point_obj = bpy.data.objects.new(pt.label, None)
            #point_obj.location = pt.location
            #scn.objects.link(point_obj)
        bme.to_mesh(container_mesh)
        bme.free()
        
        
        if self.seg_type == 'MAX_PERM':
            bpy.context.scene.upper_teeth_marked = True
        if self.seg_type == 'MAND_PERM':
            bpy.context.scene.lower_teeth_marked = True
        
    ####  Enhancing UI ############
    
    def ui_setup_post(self):
        #####  Hide Existing UI Elements  ###
        self.info_panel.visible = False
        self.tools_panel.visible = False
        
        
        self.info_panel = self.wm.create_window('Tooth Selection Help',
                                                {'pos':9,
                                                 'movable':True,
                                                 'bgcolor':(0.50, 0.50, 0.50, 0.90)})

        collapse_container = self.info_panel.add(ui.UI_Collapsible('Instructions     ', collapsed=False))
        self.inst_paragraphs = [collapse_container.add(ui.UI_Markdown('', min_size=(100,10), max_size=(250, 50))) for i in range(6)]
        
        self.new_instructions = {
            
            "Add": "Left click to place a point",
            "Grab": "Hold left-click on a point and drag to move it along the surface of the mesh",
            "Remove": "Right Click to remove a point",
            "Requirements": "Clicking each tooh wil help automatic algorithm find the tooth accurately.   This step can be skipped"
        }
        
        for i,val in enumerate(['Add', 'Grab', 'Remove', "Requirements"]):
            self.inst_paragraphs[i].set_markdown(chr(65 + i) + ") " + self.new_instructions[val])

        
        buttons_container = self.info_panel.add(ui.UI_Container())
        buttons_frame = buttons_container.add(ui.UI_Frame('Teeth Input'))
        
        
        def mode_getter():
            return self.seg_type
        def mode_setter(m):
            self.seg_type = m
            self.build_labels()
            self.win_obvious_instructions.hbf_title.set_label('Click ' + self.active_label)     
        
        segmentation_mode = buttons_frame.add(ui.UI_Options(mode_getter, mode_setter))
        segmentation_mode.add_option('Maxillary Permmant', value='MAX_PERM')
        segmentation_mode.add_option('Maxillary Mixed', value='MAX_MIXED')
        segmentation_mode.add_option('Mandibular Permanent', value='MAND_PERM')
        segmentation_mode.add_option('Mandibular Mixed', value = 'MAND_MIXED')
        segmentation_mode.add_option('Maxillary Primary', value = 'MAX_PRIM')
        segmentation_mode.add_option('Mandibular Primary', value = 'MAND_PRIM')
        
        self.win_obvious_instructions = self.wm.create_window('Click On ' + self.active_label, {'pos':8, "vertical":False, "padding":15, 'movable':True, 'bgcolor':(0.50, 0.50, 0.50, 0.5), 'border_color':(0.50, 0.50, 0.50, 0.9), "border_width":4.0})
        self.win_obvious_instructions.hbf_title.fontsize = 20
        
        win_next_back = self.wm.create_window(None, {'pos':2, "vertical":False, "padding":15, 'movable':True, 'bgcolor':(0.50, 0.50, 0.50, 0.0), 'border_color':(0.50, 0.50, 0.50, 0.9), "border_width":4.0})
        next_back_container = win_next_back.add(ui.UI_Container(vertical = False, background = (0.50, 0.50, 0.50, 0.90)))
        #next_back_frame = next_back_container.add(ui.UI_Frame('', vertical = False, equal = True, separation = 4))#, background = (0.50, 0.50, 0.50, 0.90)))
            
        #back_button = next_back_container.add(ui.UI_Button('Back', mode_backer, margin = 10))
        #back_button.label.fontsize = 20
            
        #cancel_button = next_back_frame.add(ui.UI_Button('Cancel', lambda:self.done(cancel=True), margin=0))
        cancel_button = next_back_container.add(ui.UI_Button('Cancel', lambda:self.done(cancel=True), margin=10))
        cancel_button.label.fontsize = 20
        next_tooth = next_back_container.add(ui.UI_Button('Skip Tooth', self.skip_label, margin = 10))
        next_tooth.label.fontsize = 20
        finish_button = next_back_container.add(ui.UI_Button('Finish', lambda:self.done(cancel=False), margin=10))
        finish_button.label.fontsize = 20
        #next_button = next_back_frame.add(ui.UI_Button('Next', mode_stepper, margin = 0))
        self.set_ui_text()
        
        
def register():
    bpy.utils.register_class(AITEETH_OT_label_teeth)
    bpy.utils.register_class(AITEETH_OT_label_maxillary_teeth)
    bpy.utils.register_class(AITEETH_OT_label_mandibular_teeth)
    
     
def unregister():
    bpy.utils.unregister_class(AITEETH_OT_label_teeth)
    bpy.utils.unregister_class(AITEETH_OT_label_maxillary_teeth)
    bpy.utils.unregister_class(AITEETH_OT_label_mandibular_teeth)