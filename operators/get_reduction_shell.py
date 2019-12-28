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


def load_from_library(blendfile_path, data_attr, filenames=None, overwrite_data=False, action="APPEND"):
    data_block_infos = list()
    orig_data_names = lambda: None
    with bpy.data.libraries.load(blendfile_path, link=action == "LINK") as (data_from, data_to):
        # if only appending some of the filenames
        if filenames is not None:
            # rebuild 'data_attr' of data_from based on filenames in 'filenames' list
            #filenames = confirm_list(filenames)
            data_group = getattr(data_from, data_attr)
            new_data_group = [data_name for data_name in data_group if data_name in filenames]
            setattr(data_from, data_attr, new_data_group)
        # append data from library ('data_from') to 'data_to'
        setattr(data_to, data_attr, getattr(data_from, data_attr))
        # store copies of loaded attributes to 'orig_data_names' object
        if overwrite_data:
            attrib = getattr(data_from, data_attr)
            if len(attrib) > 0:
                setattr(orig_data_names, data_attr, attrib.copy())
    # overwrite existing data with loaded data of the same name
    if overwrite_data:
        # get attributes to remap
        source_attr = getattr(orig_data_names, data_attr)
        target_attr = getattr(data_to, data_attr)
        for i, data_name in enumerate(source_attr):
            # check that the data doesn't match
            if not hasattr(target_attr[i], "name") or target_attr[i].name == data_name or not hasattr(bpy.data, data_attr): continue
            # remap existing data to loaded data
            data_group = getattr(bpy.data, data_attr)
            data_group.get(data_name).user_remap(target_attr[i])
            # remove remapped existing data
            data_group.remove(data_group.get(data_name))
            # rename loaded data to original name
            target_attr[i].name = data_name
    return getattr(data_to, data_attr)

    
def check_credits(key):
    
    server = 'http://104.196.199.206'
    
    url = 'http://104.196.199.206/get_credits?key={}'.format(key)
    
    print(url)
    
    raw_response = requests.get(url).text
    print(raw_response)
    
    if raw_response:
        jdict = json.loads(raw_response)
        credit_balance = jdict['credits']
    else:
        credit_balance = -1
    return credit_balance


def get_cloud_key():
    prefs = get_settings()    
    key_path = prefs.key_path
    if key_path != '' and os.path.exists(key_path):
        key_file = open(prefs.key_path)
        key_val = key_file.read()
        
    else:
        key_val = prefs.key_string
        
    return key_val


def ping_server(job_id):
    url = "http://104.196.199.206:7777/api/job_details?job_id=" + job_id #1569930574014
    ret_json = json.loads(requests.get(url).text)
    return ret_json
    
def draw_callback_px(self, context):

    font_id = 0  # XXX, need to find out how best to get this.
    # draw some text
    blf.position(font_id, 25, 250, 0)
    blf.size(font_id, 30, 72)
    blf.draw(font_id, 'Press Escape to cancel')
    
    
    blf.position(font_id, 25, 200, 0)
    blf.size(font_id, 30, 72)
    blf.draw(font_id, self.msg)

class AITeeth_OT_send_cloud_reduction_shell(bpy.types.Operator):
    """Process model for shell reduction"""
    bl_idname = "ai_teeth.send_cloud_reduction_shell"
    bl_label = "Send Cloud Reduction Shell"

    _timer = None

    @classmethod
    def poll(cls, context):

        return True
        
    def invoke(self, context, event):
        
        self.msg = 'Uploading File...'
        
        wm = context.window_manager
        self._timer = wm.event_timer_add(.5, context.window)
        wm.modal_handler_add(self)
        args = (self, context)
        self._handle = bpy.types.SpaceView3D.draw_handler_add(draw_callback_px, args, 'WINDOW', 'POST_PIXEL')

        
        self.executor = ThreadPoolExecutor()  
        self.future = self.executor.submit(self.upload_job)
                
        self.start_time = time.time()
        self.last_check = time.time()
        
        self.credit_cost = 1.5
        self.job_id = ''
        self.file_name = ''
        self.job_done = False
        return {'RUNNING_MODAL'}
        
    
    def modal(self, context, event):
        context.area.tag_redraw()
        
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self.cancel(context)
            return {'CANCELLED'}

        
        if event.type == 'TIMER':
            time_elapsed = str(time.time() - self.start_time)[0:4]
            if self.future.done() and not self.job_done:
                self.job_done = True
                (j_id, file_name, result) = self.future.result()
                print(j_id, file_name, result)
                if result == 'SUCCESS':
                    self.job_id = j_id 
                    self.file_name = file_name
                    
                    return {'RUNNING_MODAL'}
                
                else:
                    self.cancel(context)
                    
                    
            elif not self.future.done() and not self.job_done:
                
                self.msg = 'Uploading File...' + time_elapsed + 'sec'
                return {'RUNNING_MODAL'} 
            
               
            if (time.time() - self.last_check) < 3.0: return {'RUNNING_MODAL'}
            self.last_check = time.time()
            # change theme color, silly!
            ret_dict = ping_server(self.job_id)
          
            print(ret_dict)
            
            self.msg = "Job is " + ret_dict['status'] + " on server..." + time_elapsed + 'sec'
            
            if ret_dict['status'] == 'error':
                self.cancel(context)
                
            elif ret_dict['status'] == 'finished':
                
                #download_the_file
                server = 'http://104.196.199.206:7776/download'
                dl_name = '{}{}'.format("computed_", self.file_name)
                print(dl_name)
                downloaded_file_path = download_nonthreaded(server, dl_name)
                print(downloaded_file_path)
                tmp_path, cur_file = define_paths()
               
                fullBlendPath = os.path.join(tmp_path, dl_name)
                
                
                #assets_path = join(dirname(abspath(__file__)), "data_assets")
                #fullBlendPath = join(assets_path, 'articulator.blend')
                #print(assets_path)
                print(fullBlendPath)
                print(os.path.exists(fullBlendPath))
    
                with bpy.data.libraries.load(fullBlendPath) as (data_from, data_to):
                    obj_list = [ob for ob in data_from.objects]
                    
                print(obj_list)
                
                obs = load_from_library(fullBlendPath, "objects", filenames=obj_list, overwrite_data=False, action="APPEND")
               
                for ob in bpy.data.objects:
                    if ob.name not in context.scene.objects:
                        context.scene.objects.link(ob)

                for ob in bpy.data.objects:
                    ob.hide = True
                
                dem_credits = requests.get("http://104.196.199.206/credit?credit={}&operation=sub&key={}".format(self.credit_cost, get_cloud_key()))
                
                Shell = bpy.data.objects.get('Shell')
                base_ob = [ob for ob in bpy.context.scene.objects if ob.type == 'MESH' and 'Salience' in ob.data.vertex_colors][0]
                
                new_me = base_ob.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
                
                #colors = [col for col in new_me.vertex_colors]
                #for col in colors:
                #    new_me.vertex_colors.remove(col)
                
                new_ob = bpy.data.objects.new('Prepped Model', new_me)
                context.scene.objects.link(new_ob)
                new_ob.matrix_world = base_ob.matrix_world
                mod = new_ob.modifiers.new('Subtract', type = 'BOOLEAN')
                mod.operation = 'DIFFERENCE'
                mod.object = Shell
        
                context.space_data.viewport_shade = 'SOLID'
                context.space_data.show_textured_solid = False
        
                bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
                context.window_manager.event_timer_remove(self._timer)
                
                return {'FINISHED'}

        return {'RUNNING_MODAL'}

    def execute(self, context):
        
        print('WE DID IT')
        return {'FINISHED'}
        

    def cancel(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self._timer)
        bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        return {'CANCELLED'}
    
    
    def upload_job(self):
        
        teeth  = set([ob for ob in bpy.data.objects if ob.type == 'MESH' and "tooth" in ob.data.name and "Convex" not in ob.name and ob.select]) #only the data we want
        #base_ob = [ob for ob in bpy.context.scene.objects if 'Salience' in ob.data.vertex_colors]
        
        #data = set(teeth + base_ob)
        
        
        start = time.time()
        location = make_temp_limited(teeth)
        server = 'http://104.196.199.206:7776/'
            
        prefix = str(uuid.uuid4())[0:8]
        name = prefix + '_reduction_shell.blend'
        ret_val = upload_nonthreaded(server, location, name)
            
        if 'FAILED' in ret_val:
            return (None, None, 'FAILED')
              
        job_submit_url =  "http://104.196.199.206:7777/api/blender_job?name={}&input={}&operation={}".format(name, name, 'make_reduction_shell')    
        job_id = requests.get(job_submit_url).text
    
        return (job_id, name, 'SUCCESS')
    
    
class AITeeth_OT_cloud_reduction_shell_credit(bpy.types.Operator):
    """Submit file to get reduction shell"""
    bl_idname = "ai_teeth.cloud_reduction_shell"
    bl_label = "Cloud Reduction Shell"

    credits_cost =  FloatProperty(name = 'Available Credits', default = 1.5)
    credits_avail = FloatProperty(name = 'Available Credits', default = 0.0)
    @classmethod
    def poll(cls, context):
        
        if len([ob for ob in bpy.data.objects if "tooth" in ob.data.name and 'Convex' not in ob.name and ob.select]) == 0: return False #no teeth to make convex
        if len([ob for ob in bpy.context.scene.objects if ob.type == 'MESH' and 'Salience' in ob.data.vertex_colors]) == 0: return False  #no objectt to subtract
        return True

    def invoke(self, context, event):
        #validate scene
        #if not valid, warn users -> cancel
        #check credits
        #show popup with credit amount, ask user if they are sure
        
        prefs = get_settings()
        
        key_path = prefs.key_path
        if key_path != '' and os.path.exists(key_path):
            key_file = open(prefs.key_path)
            key_val = key_file.read()
        
        else:
            key_val = prefs.key_string
          
        if key_val == '':
            self.credits_avail = -1.0
        else:  
            self.credits_avail = check_credits(key_val)
        
        
        return context.window_manager.invoke_props_dialog(self, width = 300)
    
    def draw(self, context):
        
        layout = self.layout
        
        row = layout.row()
        reduction_teeth = [ob for ob in bpy.data.objects if ob.type == 'MESH' and "tooth" in ob.data.name and 'Convex' not in ob.name and ob.select]
        
        row.label("You have %i teeth selected for reduction" % len(reduction_teeth))
        
        if self.credits_avail == -1.0:
            row = layout.row()
            text = "Please visit https://d3tool.com/product/cloud-credit"
            row.label(text)
        else:
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
        if self.credits_avail < self.credits_cost:
            bpy.ops.wm.url_open("INVOKE_DEFAULT", url = "https://d3tool.com/product/cloud-credit")
        else:
            bpy.ops.ai_teeth.send_cloud_reduction_shell("INVOKE_DEFAULT")
        
        #TODO, set up the modal operator
        return {'FINISHED'}



def register():
    bpy.utils.register_class(AITeeth_OT_send_cloud_reduction_shell)
    bpy.utils.register_class(AITeeth_OT_cloud_reduction_shell_credit)


def unregister():
    bpy.utils.register_class(AITeeth_OT_send_cloud_reduction_shell)
    bpy.utils.unregister_class(AITeeth_OT_cloud_reduction_shell_credit)