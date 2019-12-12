import bpy
import os
import shutil
import time
import requests
import uuid
from threading import Thread


if bpy.app.version[1] >= 80:
    temp_path = bpy.context.preferences.filepaths.temporary_directory
else:
    temp_path = bpy.context.user_preferences.filepaths.temporary_directory

#current_file = bpy.data.filepath


def define_paths():
    temp_path = bpy.context.user_preferences.filepaths.temporary_directory
    current_file = bpy.data.filepath
    return temp_path, current_file

def make_temp():
    bpy.ops.wm.save_mainfile(compress = True)
    temp_path, current_file = define_paths()
    name = '{}_{}_{}'.format('export', int(time.time()*1000), os.path.basename(current_file))
    shutil.copy(current_file, os.path.join(temp_path, name))
    return os.path.join(temp_path, name)

def make_temp_limited(data_blocks):
    
    
    
    temp_path, current_file = define_paths()
    name = '{}_{}_{}'.format('export', int(time.time()*1000), os.path.basename(current_file))
    
    sent_data_blocks_path = os.path.join(temp_path, name)
    
    bpy.data.libraries.write(sent_data_blocks_path, data_blocks, fake_user=True, compress = True)

    return sent_data_blocks_path
    
    
def delete_current_temp():
    temp_path, current_file = define_paths()
    for blend in os.listdir(temp_path):
        if 'export_' in blend:
            if os.path.basename(current_file) in blend:
                print('deleting', blend)
                #os.remove(os.path.join(temp_path, blend))

def delete_all_temp():
    temp_path, current_file = define_paths()
    for blend in os.listdir(temp_path):
        if 'export_' in blend:
            print('Deleting', blend)
            os.remove(os.path.join(temp_path, blend))

def upload(server, temp_file, file_name):
    temp_path, current_file = define_paths()
    def thread():
        signed_url = requests.get(server, {'file_name': file_name}).text
        response = requests.put(signed_url, open(temp_file, 'rb'))
        delete_current_temp()
        return response
    Thread(target=thread).start()


def upload_nonthreaded(server, temp_file, file_name):
    temp_path, current_file = define_paths()

    signed_url = requests.get(server, {'file_name': file_name}).text
    response = requests.put(signed_url, open(temp_file, 'rb'))
    delete_current_temp()
    return response


def download(server, file_name):
    def thread():
        signed_url = requests.get(server, {'file_name': file_name}).text
        data = requests.get(signed_url).content #text?
        with open(os.path.join(temp_path, file_name), 'wb') as f:
            f.write(data)
        return os.path.join(temp_path, file_name)
    Thread(target=thread).start()


def download_nonthreaded(server, file_name):
    signed_url = requests.get(server, {'file_name': file_name}).text
    print(signed_url)
    data = requests.get(signed_url).content
    with open(os.path.join(temp_path, file_name), 'wb') as f:
        f.write(data)
    return os.path.join(temp_path, file_name)
    
#Upload
'''
server = 'http://127.0.0.1:7776/'
location = make_temp()
name = 'Blend_test.blend'
upload(server, location, name)
'''

#Download
'''
server = 'http://127.0.0.1:7776/download'
name = 'uuid_patricks_blend.blend'
download(server, name)
'''
