'''
Created on Aug 9, 2019

@author: Patrick
'''
import math
import random

import bpy
from mathutils import Vector, Matrix

# Addon imports

#from common_utilities import get_settings


from d3guard.subtrees.points_picker.operators.points_picker import VIEW3D_OT_points_picker
from d3guard.subtrees.points_picker.subtrees.addon_common.common import ui
from d3guard.subtrees.custom_sculpt.functions.common.reporting import showErrorMessage


class D3ORTHO_OT_orient_model(VIEW3D_OT_points_picker):
    """ Orient Model to Occlusal Plane """
    bl_idname = "d3ortho.orient_model"
    bl_label = "Orient Model(s)"
    bl_description = "Indicate points to define the occlusal plane"

    #############################################
    # overwriting functions from wax drop

    @classmethod
    def can_start(cls, context):
        """ Start only if editing a mesh """
        return context.object is not None

    
    def start_pre(self):
        
        upper_ob = bpy.data.objects.get(bpy.context.scene.d3ortho_upperjaw)
        lower_ob = bpy.data.objects.get(bpy.context.scene.d3ortho_lowerjaw)
        
        if upper_ob:
            self.model = self.context.object
            
        elif lower_ob and upper_ob == None:
            self.model = lower_ob
    
        
        self.obs_unhide = []
        
        for ob in bpy.data.objects:
            if not ob.hide:
                self.obs_unhide.append(ob)
            ob.select = False
            ob.hide = True
            
        self.model.select = True
        self.model.hide = False
        
        bpy.ops.view3d.viewnumpad(type = 'FRONT')
        bpy.ops.view3d.view_selected()

        bpy.context.space_data.show_manipulator = False
        bpy.context.space_data.transform_manipulators = {'TRANSLATE'}
        v3d = bpy.context.space_data
        v3d.pivot_point = 'MEDIAN_POINT'
   
    def resetLabels(self):  #must override this becuase we have pre-defineid label names
        return          
    def add_point_post(self, pt_added):
        labels = ["Right Molar", "Left Molar", "Incisal Edge", "Midline"]
        
        if len(self.b_pts) > 4:
            self.b_pts = self.b_pts[0:4]
            return
        
        used_labels = []
        unlabeled_points = []
        for pt in self.b_pts:
            if pt.label in labels:
                used_labels += [pt.label]
            else:
                unlabeled_points += [pt]
                
        print(used_labels)
        for label in used_labels:
            labels.remove(label)
                
        for i, pt in enumerate(unlabeled_points):
            pt.label = labels[i]
        
        if len(labels) > 1:
            self.win_obvious_instructions.visible = True
            self.win_obvious_instructions.hbf_title.set_label('Click ' + labels[1])  
        else:
            self.win_obvious_instructions.visible = False      

    def remove_point_post(self):
        labels = ["Right Molar", "Left Molar", "Incisal Edge", "Midline"]
        
        if len(self.b_pts) > 4:
            self.b_pts = self.b_pts[0:4]
            return

        for pt in self.b_pts:
            if pt.label in labels:
                labels.remove(pt.label)
        if len(labels) >= 1:
            self.win_obvious_instructions.visible = True
            self.win_obvious_instructions.hbf_title.set_label('Click ' + labels[0])  
        else:
            self.win_obvious_instructions.visible = False    
        
        
        
    def get_transform_data(self):
        '''
        mx and imx are the world matrix and it's inverse of the  model
        '''
        bp_rm = [bpt for bpt in self.b_pts if bpt.label == 'Right Molar'][0]
        bp_lm = [bpt for bpt in self.b_pts if bpt.label == 'Left Molar'][0]
        bp_ie = [bpt for bpt in self.b_pts if bpt.label == 'Incisal Edge'][0]
        bp_ml = [bpt for bpt in self.b_pts if bpt.label == 'Midline'][0]
        
        v_R = bp_rm.location #R molar
        v_L = bp_lm.location #L molar 
        v_I = bp_ie.location #Incisal Edge
        v_M = bp_ml.location #midline
        
        mx_data = {}
        
        #calculate the center (still in model local coordinates
        center = 1/3 * (v_R + v_L + v_I)
        T = Matrix.Translation(center)
        
        molar_mid = .5 * (v_R + v_L)
        

        ##Calculate the plane normal, and the rotation matrix that
        #orientes to that plane.
        vec_R =  v_R - v_L #vector pointing from left to right
        vec_R.normalize()
        
        vec_L = v_L - v_R #vector pointing from right to left
        vec_L.normalize()
        
        vec_I = v_I - v_R  #incisal edge frpm righ
        vec_I.normalize()
        
        vec_M = v_M -v_R   #midlind from right
        vec_M.normalize()
        
        Z = vec_I.cross(vec_L)  #The normal of the occlusal plane in Model LOCAL space
        Z.normalize()
                
        #X = v_M - center  #center point to midline  #OLD WAY
        #X = X - X.dot(Z) * Z #minus any component in occlusal plane normal direction 
        #X.normalize()
        
        Y = molar_mid - v_M   #center point to midline pointing posterior
        Y = Y - Y.dot(Z) * Z #minus any component in occlusal plane normal direction 
        Y.normalize()
        
        #Y = Z.cross(X)
        #Y.normalize()
        X = Y.cross(Z) #NEW/LPS
        X.normalize()
        
        #FORMER conventions was X-> Forward, Y-< Left, Z Up
        #NEW/Standard  LPS ->  X LEFT, Y posterior, Z up

        R = Matrix.Identity(3)  #make the columns of matrix U, V, W
        R[0][0], R[0][1], R[0][2]  = X[0] ,Y[0],  Z[0]
        R[1][0], R[1][1], R[1][2]  = X[1], Y[1],  Z[1]
        R[2][0] ,R[2][1], R[2][2]  = X[2], Y[2],  Z[2] 
        R = R.to_4x4()
        iR = R.inverted()
        ### NOW WE HAVE THE OCCLUSAL PLANE DESCRIBED
        
        
        mx_data['Occlusal Plane Matrix'] = R
        mx_data['Occlusal Plane iMatrix'] = iR
        
        #The Midine Poistion at the height of the incisal edge
        #Or the Incial Edge positiong projected onto the midline
        #v_M_corrected = v_I - (v_I - center).dot(Y) * Y
        v_M_corrected = v_I - (v_I - molar_mid).dot(X) * X 
        
        center = 1/3 * (v_R + v_L + v_M_corrected)
        mx_center = Matrix.Translation(center)
        imx_center = mx_center.inverted()
        mx_data['center'] = mx_center
        
        
        #Matrices assoicated with the oclusal plane cant
        #Lets Calculate the matrix transform for
        #the Fox plane cant from the user preferences
        X_w = Vector((1,0,0))
        Y_w = Vector((0,1,0))
        Z_w = Vector((0,0,1))
        
        op_angle = 0.0
        #Fox_R = Matrix.Rotation(op_angle * math.pi /180, 3, 'Y')  #The Y axis represents a line drawn through the centers of condyles from right to left
        Fox_R = Matrix.Rotation(op_angle * math.pi /180, 3, 'X')  #The X axis represents a line drawn through the centers of condyles from right to left
        Z_fox = Fox_R * Z_w
        #X_fox = Fox_R * X_w
        Y_fox = Fox_R * Y_w
        
        R_fox = Matrix.Identity(3)  #make the columns of matrix U, V, W
        R_fox[0][0], R_fox[0][1], R_fox[0][2]  = X_w[0] ,Y_fox[0],  Z_fox[0]
        R_fox[1][0], R_fox[1][1], R_fox[1][2]  = X_w[1], Y_fox[1],  Z_fox[1]
        R_fox[2][0] ,R_fox[2][1], R_fox[2][2]  = X_w[2], Y_fox[2],  Z_fox[2]
        R_fox = R_fox.to_4x4()
        
        mx_data['Fox Plane'] = R_fox
        
        #average distance from campers plane to occlusal
        #plane is 30 mm
        #file:///C:/Users/Patrick/Downloads/CGBCC4_2014_v6n6_483.pdf
        
        center = R_fox * iR * center
        v_ant = R_fox * iR * v_M_corrected
        
        mx_mount = T * R_fox
        
        mx_data['Mount'] = mx_mount
        
        
        return mx_data  
    
    def next(self):
        
        if len(self.b_pts) < 4:
            showErrorMessage("You have not marked all of the landmarks")
            return
        
        self.done()
               
        
    def getLabel(self, idx):
        return "P %(idx)s" % locals()


    #############################################

    def end_commit(self):
        mx_data = self.get_transform_data()
        
        mx_mount = mx_data["Mount"]
        iR = mx_data['Occlusal Plane iMatrix']
        
        
        name = "MX_Orig_" + self.model.name
        if name in bpy.data.objects:
            empty1 = bpy.data.objects.get(name)
        else:
            empty1 = bpy.data.objects.new(name, None)
        
        name = "MX_Plane_" + self.model.name
        if name in bpy.data.objects:
            empty1 = bpy.data.objecst.get(name)
        else:
            empty2 = bpy.data.objects.new(name, None)
    
        upper_ob = bpy.data.objects.get(bpy.context.scene.d3ortho_upperjaw)
        lower_ob = bpy.data.objects.get(bpy.context.scene.d3ortho_lowerjaw)
        
        #prevent accidental selection
        empty1.hide_select = True
        empty2.hide_select = True
        
        self.context.scene.objects.link(empty1)
        self.context.scene.objects.link(empty2)
        
        empty1.parent = self.model
        empty2.parent = self.model
        
        empty1.matrix_world = self.model.matrix_world   #put this one at the object orign
        empty2.matrix_world = mx_mount
        
        imx = mx_mount.inverted()
        
        for ob in self.obs_unhide:
            ob.hide = False
            
        
        if upper_ob:
            upper_ob.matrix_world = mx_mount * iR 
        
        if lower_ob:
            lower_ob.matrix_world = mx_mount * iR
    ####  Enhancing UI ############
    
    def ui_setup_post(self):
        #####  Hide Existing UI Elements  ###
        self.info_panel.visible = False
        self.tools_panel.visible = False
        
        
        self.info_panel = self.wm.create_window('Landmarks Help',
                                                {'pos':9,
                                                 'movable':True,
                                                 'bgcolor':(0.50, 0.50, 0.50, 0.90)})

        collapse_container = self.info_panel.add(ui.UI_Collapsible('Instructions     ', collapsed=False))
        self.inst_paragraphs = [collapse_container.add(ui.UI_Markdown('', min_size=(100,10), max_size=(250, 50))) for i in range(6)]
        
        self.new_instructions = {
            
            "Add": "Left click to place a point",
            "Grab": "Hold left-click on a point and drag to move it along the surface of the mesh",
            "Remove": "Right Click to remove a point",
            "Requirements": "Click the Right Molar, Left Molar, Incisal Edge and then Midline"
        }
        
        for i,val in enumerate(['Add', 'Grab', 'Remove', "Requirements"]):
            self.inst_paragraphs[i].set_markdown(chr(65 + i) + ") " + self.new_instructions[val])

        
        
        self.win_obvious_instructions = self.wm.create_window('Click Right Molar', {'pos':8, "vertical":False, "padding":15, 'movable':True, 'bgcolor':(0.50, 0.50, 0.50, 0.5), 'border_color':(0.50, 0.50, 0.50, 0.9), "border_width":4.0})
        self.win_obvious_instructions.hbf_title.fontsize = 20
        
        win_next_back = self.wm.create_window(None, {'pos':2, "vertical":False, "padding":15, 'movable':True, 'bgcolor':(0.50, 0.50, 0.50, 0.0), 'border_color':(0.50, 0.50, 0.50, 0.9), "border_width":4.0})
        next_back_container = win_next_back.add(ui.UI_Container(vertical = False, background = (0.50, 0.50, 0.50, 0.90)))
        #next_back_frame = next_back_container.add(ui.UI_Frame('', vertical = False, equal = True, separation = 4))#, background = (0.50, 0.50, 0.50, 0.90)))
            
        #back_button = next_back_container.add(ui.UI_Button('Back', mode_backer, margin = 10))
        #back_button.label.fontsize = 20
            
        #cancel_button = next_back_frame.add(ui.UI_Button('Cancel', lambda:self.done(cancel=True), margin=0))
        cancel_button = next_back_container.add(ui.UI_Button('Cancel', lambda:self.done(cancel=True), margin=10))
        cancel_button.label.fontsize = 20
        calc_plane_button = next_back_container.add(ui.UI_Button('Finish', self.next, margin = 10))
        calc_plane_button.label.fontsize = 20
        
        #next_button = next_back_frame.add(ui.UI_Button('Next', mode_stepper, margin = 0))
        
        
        self.set_ui_text()
        
        
def register():
    bpy.utils.register_class(D3ORTHO_OT_orient_model)
    
   
    
def unregister():
    bpy.utils.unregister_class(D3ORTHO_OT_orient_model)
