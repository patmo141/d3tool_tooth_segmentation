'''
Created on Oct 11, 2015

@author: Patrick
'''
import bpy

import time
import random

from bpy_extras import view3d_utils

from ..cookiecutter.cookiecutter import CookieCutter
from ..common import ui
from ..common.blender import show_error_message
from ..common.ui import Drawing

from .ai_teeth_datastructure import InputPoint, SplineSegment, CurveNode


class AITeeth_UI_Init():
    def ui_setup(self):
        self.instructions = {
            "add": "Left-click on the mesh to add a new point",
            "add (extend)": "Left-click to add new a point connected to the selected point. The green line will visualize the new segments created",
            "add (insert)": "Left-click on a segment to insert a new a point. The green line will visualize the new segments created",
            "close loop": "Left-click on the outer hover ring of existing point to close a boundary loop",
            "select": "Left-click on a point to select it",
            "sketch": "Hold Shift + left-click and drag to sketch in a series of points",
            "sketch extend": "Hover near an existing point, Shift + Left-click and drag to sketch in a series of points",
            "delete": "Right-click on a point to remove it",
            "delete (disconnect)": "Ctrl + right-click will remove a point and its connected segments",
            "tweak": "left click and drag a point to move it",
            "tweak confirm": "Release to place point at cursor's location",
            "paint": "Left-click to paint",
            "paint extend": "Left-click inside and then paint outward from an existing patch to extend it",
            "paint greedy": "Painting from one patch into another will remove area from 2nd patch and add it to 1st",
            "paint mergey": "Painting from one patch into another will merge the two patches",
            "paint remove": "Right-click and drag to delete area from patch",
            "seed add": "Left-click within a boundary to indicate it as patch segment",
            "segmentation" : "Left-click on a patch to select it, then use the segmentation buttons to apply changes"
        }

        #def mode_getter():
        #    return self._state
        #def mode_setter(m):
        #    self.fsm_change(m)
        #def mode_change():
        #    nonlocal salience_edit_container, precut_container, segmentation_container, paint_radius
        #    m = self._state
        #    salience_edit_container.visible = (m in {'salience_edit'})
        #    precut_container.visible = (m in {'spline', 'seed', 'region'})
        #    paint_radius.visible = (m in {'region', 'salience_edit'})
        #    no_options.visible = not (m in {'region','salience_edit'})
        #    segmentation_container.visible = (m in {'segmentation'})
        #self.fsm_change_callback(mode_change)

        def radius_getter():
            return self.brush_radius
        def radius_setter(v):
            self.brush_radius = max(0.1, int(v*10)/10)
            if self.brush:
                self.brush.radius = self.brush_radius

        def filter_getter():
            return self.mask_threshold
        def filter_setter(v):
            v = max(0.8, int(v*10000)/10000)
            self.mask_threshold = min(1.0, v)
            
        
        def rating_setter(r):
            sce = bpy.context.scene
            if hasattr(sce, "ai_settings"):
                sce.ai_settings.segmentation_quality = int(r)

            return
        
        def rating_getter():
            sce = bpy.context.scene
            if hasattr(sce, "ai_settings"):
                return sce.ai_settings.segmentation_quality
            else: 
                return -1
            
        
        
        
             
        def mode_stepper():
            print('Stepping modes')
            print(self.workflow_step)
            if self.workflow_step == 'THRESHOLD':
                #moving into merge patches
                self.skeletonize_salience_verts()
                
                if not self.check_seeded_patches():
                    return
                
                
                if len(self.seed_faces):
                    self.skeleton_to_patches_seeded()
                else:
                    self.skeleton_to_patches()
                
                self.fsm_change('region')
                self.workflow_step = 'REFINE PATCHES' 
                self.paint_mode = 'GREEDY'
                self.win_obvious_instructions.hbf_title.set_label('Refine Patches')
                self.salience_tools.visible = False
                self.patches_window.visible = True
                return
            
            #elif self.workflow_step == 'MERGE PATCHES':
            #    #moving into refine patches
            #    self.paint_mode = 'GREEDY'
            #    self.win_obvious_instructions.hbf_title.set_label('Paint Patches')
            #    self.workflow_step = 'REFINE PATCHES'
            #    print(self.workflow_step)
                #we remain in the 'region' state
            #    return
                
                
            elif self.workflow_step == 'REFINE PATCHES':
                self.workflow_step = 'RATE_SEGMENTATION'
                self.rating_window.visible = True
                self.salience_tools.visible = False
                self.win_obvious_instructions.visible = False
                
                return
                
            elif self.workflow_step == 'RATE_SEGMENTATION':
                
                if bpy.context.scene.ai_settings.segmentation_quality == -1:
                    show_error_message('Please rate the quality of the segmentatino first.')
                    return
                
                #finishing up
                #spearate and solidify each patch not the gums
                print('SELF.DONE')
                self.done()
                finish = time.time()
                print('Entire workflow took %f seconds' % (finish - self.start_time))
                self.set_final_vis()
                return
                
                
        
        def mode_backer():
            if self.workflow_step == 'THRESHOLD':
                #we are just getting started, so go back
                self.done(cancle = True) #cancel it
                bpy.ops.aiteeth.mark_tooth_locations("INVOKE_DEFAULT")
                return
                
            
            if self.workflow_step == 'MERGE PATCHES':
                self.patches_window.visible = False
                self.salience_tools.visible = True
                #go back to threshold
                self.salience_verts = set()
                self.skeleton = set()
                self.skeleton_points = []
                self.has_skeletonized = False
                self.paint_mode = 'MERGE'
                self.clear_patches()
                
                self.fsm_change('salience_edit')
                #migh need to clear the color layer
                self.pick_verts_by_salience_color()
                self.initialize_face_patches_from_seeds()
                self.dilate_salience_verts()
                self.erode_salience_verts()
                self.remove_seeds_from_salience()
                self.remove_salience_vert_islands()
        
        
                self.workflow_step = 'THRESHOLD'
                return

                
            if self.workflow_step == 'REFINE PATCES':
                
                self.workflow_step = 'MERGE_PATCHES'
                self.paint_mode = 'MERGE'
                return
                

        self.win_obvious_instructions = self.wm.create_window('Feature Detection', {'pos':8, "vertical":False, "padding":15, 'movable':True, 'bgcolor':(0.50, 0.50, 0.50, 0.5), 'border_color':(0.50, 0.50, 0.50, 0.9), "border_width":4.0})
        self.win_obvious_instructions.hbf_title.fontsize = 20
        
        
        
        #MENU FOR EDITING FEATURE DETECTION
        self.salience_tools  = self.wm.create_window('Filter Features', {'pos':7, 'movable':True, 'bgcolor':(0.50, 0.50, 0.50, 0.90)})
        salience_edit_container = self.salience_tools.add(ui.UI_Container(rounded=1))
        salience_tools = salience_edit_container.add(ui.UI_Frame('Filter Input', fontsize=16, spacer=0))
        salience_tools.add(ui.UI_Number("Paint radius", radius_getter, radius_setter))
        salience_tools.add(ui.UI_Number('Filter Threshold', filter_getter, filter_setter, update_multiplier = .001))
        salience_tools.add(ui.UI_Button('Refilter', self.pick_verts_by_salience_color, tooltip='Expand the ROI'))
        salience_tools.add(ui.UI_Button('Dilate', self.dilate_salience_verts, tooltip='Expand the ROI'))#, align=-1, icon=ui.UI_Image('delete_patch32.png', width=32, height=32)))
        salience_tools.add(ui.UI_Button('Erode', self.erode_salience_verts, tooltip='Erode the ROI'))#, align=-1, icon=ui.UI_Image('separate32.png', width=32, height=32)))
        salience_tools.add(ui.UI_Button('Skeletonize', self.skeletonize_salience_verts, tooltip='Find ROI Skeleton'))#, icon=ui.UI_Image('duplicate32.png', width=32, height=32)))
        
        
        
        
        self.patches_window  = self.wm.create_window('Edit Patches', {'pos':7, 'movable':True, 'bgcolor':(0.50, 0.50, 0.50, 0.90)})
        patches_edit_container = self.patches_window.add(ui.UI_Container(rounded=1))
        patches_tools = patches_edit_container.add(ui.UI_Frame('Paint Control', fontsize=16, spacer=0))
        patches_tools.add(ui.UI_Number("Paint radius", radius_getter, radius_setter))
        self.patches_window.visible = False
        
        win_next_back = self.wm.create_window(None, {'pos':2, "vertical":False, "padding":15, 'movable':True, 'bgcolor':(0.50, 0.50, 0.50, 0.0), 'border_color':(0.50, 0.50, 0.50, 0.9), "border_width":4.0})
        next_back_container = win_next_back.add(ui.UI_Container(vertical = False, background = (0.50, 0.50, 0.50, 0.90)))
        #next_back_frame = next_back_container.add(ui.UI_Frame('', vertical = False, equal = True, separation = 4))#, background = (0.50, 0.50, 0.50, 0.90)))
        
        back_button = next_back_container.add(ui.UI_Button('Back', mode_backer, margin = 10))
        back_button.label.fontsize = 20
        
        #cancel_button = next_back_frame.add(ui.UI_Button('Cancel', lambda:self.done(cancel=True), margin=0))
        cancel_button = next_back_container.add(ui.UI_Button('Cancel', lambda:self.done(cancel=True), margin=10))
        cancel_button.label.fontsize = 20
        next_button = next_back_container.add(ui.UI_Button('Next', mode_stepper, margin = 10))
        next_button.label.fontsize = 20
        

        self.rating_window = self.wm.create_window('Poor<--- Rate Segmentation ---> Perfect', {'pos':5, 'movable':True, 'bgcolor':(0.50, 0.50, 0.50, 0.90)})
        rating_container = self.rating_window.add(ui.UI_Container(vertical = False, background = (0.50, 0.50, 0.50, 0.90)))
        rating = rating_container.add(ui.UI_Options(rating_getter, rating_setter,margin = 4, separation= 4, vertical = False))
        rating.add_option(' 0 ', value = 0)
        rating.add_option(' 1 ', value = 1)
        rating.add_option(' 2 ', value = 2)
        rating.add_option(' 3 ', value = 3)
        rating.add_option(' 4 ', value = 4)
        rating.add_option(' 5 ', value = 5)
        rating.add_option(' 6 ', value = 6)
        rating.add_option(' 7 ', value = 7)
        rating.add_option(' 8', value = 8)
        rating.add_option('  9 ', value = 9)
        rating.add_option(' 10', value = 10)
        
        for op in rating.options: 
            print(op.label)
            print(op.ui_item)
            
            for element in op.ui_item.ui_items:  #elemenets in the UI_Container
                element.fontsize = 20
        
            op.ui_item._recalc_size()
        self.rating_window.visible = False
        
        
    # XXX: Fine for now, but will likely be irrelevant in future
    def ui_text_update(self):
        '''
        updates the text in the info box
        '''
        pass
        #if self._state == 'spline':
        #    if self.input_net.is_empty:
        #        self.set_ui_text_no_points()
        #    elif self.input_net.num_points == 1:
        #        self.set_ui_text_1_point()
        #    elif self.input_net.num_points > 1:
        #        self.set_ui_text_multiple_points()
        #    elif self.grabber and self.grabber.in_use:
        #        self.set_ui_text_grab_mode()

        #elif self._state == 'region':
        #    self.set_ui_text_paint()
        #elif self._state == 'seed':
        #    self.set_ui_text_seed_mode()

        #elif self._state == 'segmentation':
        #    self.set_ui_text_segmetation_mode()

        #else:
        #    self.reset_ui_text()

    # XXX: Fine for now, but will likely be irrelevant in future
    def set_ui_text_no_points(self):
        ''' sets the viewports text when no points are out '''
        self.reset_ui_text()
        self.inst_paragraphs[0].set_markdown('A) ' + self.instructions['add'])
        self.inst_paragraphs[1].set_markdown('B) ' + self.instructions['sketch'])

    def set_ui_text_1_point(self):
        ''' sets the viewports text when 1 point has been placed'''
        self.reset_ui_text()
        self.inst_paragraphs[0].set_markdown('A) ' + self.instructions['add (extend)'])
        self.inst_paragraphs[1].set_markdown('B) ' + self.instructions['delete'])
        self.inst_paragraphs[2].set_markdown('C) ' + self.instructions['sketch extend'])
        self.inst_paragraphs[3].set_markdown('C) ' + self.instructions['select'])
        self.inst_paragraphs[4].set_markdown('D) ' + self.instructions['tweak'])
        #self.inst_paragraphs[5].set_markdown('E) ' + self.instructions['add (disconnect)'])
        self.inst_paragraphs[6].set_markdown('F) ' + self.instructions['delete (disconnect)'])

        #self.inst_paragraphs[4].set_markdown('E) ' + self.instructions['add (disconnect)'])


    def set_ui_text_multiple_points(self):
        ''' sets the viewports text when there are multiple points '''
        self.reset_ui_text()
        self.inst_paragraphs[0].set_markdown('A) ' + self.instructions['add (extend)'])
        self.inst_paragraphs[1].set_markdown('B) ' + self.instructions['add (insert)'])
        self.inst_paragraphs[2].set_markdown('C) ' + self.instructions['delete'])
        self.inst_paragraphs[3].set_markdown('D) ' + self.instructions['delete (disconnect)'])
        self.inst_paragraphs[4].set_markdown('E) ' + self.instructions['sketch'])
        self.inst_paragraphs[5].set_markdown('F) ' + self.instructions['tweak'])
        self.inst_paragraphs[6].set_markdown('G) ' + self.instructions['close loop'])

    def set_ui_text_grab_mode(self):
        ''' sets the viewports text during general creation of line '''
        self.reset_ui_text()
        self.inst_paragraphs[0].set_markdown('A) ' + self.instructions['tweak confirm'])

    def set_ui_text_seed_mode(self):
        ''' sets the viewport text during seed selection'''
        self.reset_ui_text()
        self.inst_paragraphs[0].set_markdown('A) ' + self.instructions['seed add'])

    def set_ui_text_segmetation_mode(self):
        ''' sets the viewport text during seed selection'''
        self.reset_ui_text()
        self.inst_paragraphs[0].set_markdown('A) ' + self.instructions['segmentation'])

    def set_ui_text_paint(self):
        self.reset_ui_text()
        self.inst_paragraphs[0].set_markdown('A) ' + self.instructions['paint'])
        self.inst_paragraphs[1].set_markdown('B) ' + self.instructions['paint extend'])
        self.inst_paragraphs[2].set_markdown('C) ' + self.instructions['paint remove'])
        self.inst_paragraphs[3].set_markdown('D) ' + self.instructions['paint mergey'])

    def reset_ui_text(self):
        for inst_p in self.inst_paragraphs:
            inst_p.set_markdown('')
