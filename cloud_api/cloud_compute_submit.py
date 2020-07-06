'''
Created on Nov 27, 2019

@author: Patrick
'''
import os
import time
import requests
import json
import uuid

import bpy

from export_upload import upload_nonthreaded, download_nonthreaded, define_paths, make_temp


def ping_server(job_id):
    url = "http://34.73.186.235:7777/api/job_details?job_id=" + job_id #1569930574014
    ret_json = json.loads(requests.get(url).text)
    return ret_json



class ModalCloudOperator(bpy.types.Operator):
    """Operator which submits a job and waits for it to return"""
    bl_idname = "wm.modal_cluod_operator"
    bl_label = "Modal Cloud Operator"

    _timer = None

    def invoke(self, context, event):
        
        self.upload_job(context)
        wm = context.window_manager
        self._timer = wm.event_timer_add(3.0, context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}
    
    def modal(self, context, event):
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self.cancel(context)
            return {'CANCELLED'}

        if event.type == 'TIMER':
            # change theme color, silly!
            ret_dict = ping_server(self.job_id)
            print(ret_dict)
            if ret_dict['status'] == 'error':
                self.cancel(context)
                
            elif ret_dict['status'] == 'finished':
                
                self.retrieve_data()
                
                self.execute(context)
                return {'FINISHED'}

        return {'RUNNING_MODAL'}

    
    
    def retrieve_data(self):
        #download_the_file
        server = 'http://104.196.199.206:7776/download'
        dl_name = '{}{}'.format("computed_", self.file_name)
        print(dl_name)
        downloaded_file_path = download_nonthreaded(server, dl_name)
        print(downloaded_file_path)
        tmp_path, cur_file = define_paths()
        fullBlendPath = os.path.join(tmp_path, dl_name)
        orig_data_names = lambda: None
        with bpy.data.libraries.load(fullBlendPath) as (data_from, data_to):
            for attr in dir(data_to):
                setattr(data_to, attr, getattr(data_from, attr))
                attrib = getattr(data_from, attr)
                if len(attrib) > 0:
                    setattr(orig_data_names, attr, attrib.copy())
                    
        
                    
    def execute(self, context):
        print('WE DID IT')
        return {'FINISHED'}

    def cancel(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self._timer)
    
    
    def upload_job(self,context):
        if context.object:
            start = time.time()
            location = make_temp()
            server = 'http://104.196.199.206:7776/'
            
            prefix = str(uuid.uuid4())[0:6]
            name = prefix + '_testing.blend'
            ret_val = upload_nonthreaded(server, location, name)
                 
            job_submit_url =  "http://34.73.186.235:7777/api/blender_job?name={}&input={}".format(name, name)
            self.job_id = requests.get(job_submit_url).text
            self.file_name = name
            
