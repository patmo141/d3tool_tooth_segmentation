'''
Created on Dec 27, 2020

@author: Patrick
'''

'''
Created on Oct 1, 2017

@author: Patrick
'''
import os
import bpy
import itertools
from mathutils import Matrix
from io_mesh_stl import stl_utils, blender_utils


import tempfile
import zipfile

from d3webapi.D3WebAPI import D3WebAPI


def write_some_data(context, filepath, use_some_setting):
    print("running write_some_data...")
    f = open(filepath, 'w', encoding='utf-8')
    f.write("Hello World %s" % use_some_setting)
    f.close()

    return {'FINISHED'}


# ExportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ExportHelper, orientation_helper_factory, axis_conversion
from bpy.props import StringProperty, BoolProperty, EnumProperty, FloatProperty
from bpy.types import Operator

IOSTLOrientationHelper = orientation_helper_factory("IOSTLOrientationHelper", axis_forward='Y', axis_up='Z')

class D3TOOL_AI_export_segmentation_case(Operator, ExportHelper, IOSTLOrientationHelper):
    """Use this to export your splint"""
    bl_idname = "aiteeth.export_segmentation_case"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Export Case STL Files"

    # ExportHelper mixin class uses this
    
    case_name = StringProperty(
            default="_segmentation",
            options={'HIDDEN'},
            maxlen=255,  # Max internal buffer length, longer would be clamped.
            )
    
    
    filename_ext = ".stl"

    filter_glob = StringProperty(
            default="*.stl",
            options={'HIDDEN'},
            maxlen=255,  # Max internal buffer length, longer would be clamped.
            )


    use_original_coords = BoolProperty(
            name="Original Coordiantes",
            description="Export object in the original reference frame of model import",
            default=True,
            )
    
    use_selection = BoolProperty(
            name="Selection Only",
            description="Export selected objects only",
            default=False,
            )
    global_scale = FloatProperty(
            name="Scale",
            min=0.01, max=1000.0,
            default=1.0,
            )

    use_scene_unit = BoolProperty(
            name="Scene Unit",
            description="Apply current scene's unit (as defined by unit scale) to exported data",
            default=False,
            )
    ascii = BoolProperty(
            name="Ascii",
            description="Save the file in ASCII file format",
            default=False,
            )
    use_mesh_modifiers = BoolProperty(
            name="Apply Modifiers",
            description="Apply the modifiers before saving",
            default=True,
            )
    batch_mode = EnumProperty(
            name="Batch Mode",
            items=(('OFF', "Off", "All data in one file"),
                   ('OBJECT', "Object", "Each object as a file"),
                   ))
    
    
    def invoke(self, context, event):
        
        case_id = bpy.context.scene.d3ortho_case_id
        
        self.case_name += case_id
        return context.window_manager.invoke_props_dialog(self, width=300) 
    
    def draw(self, context):
        
        row = self.layout.row()
        row.prop(self, "case_name")
        
        
    def execute(self, context):
        keywords = self.as_keywords(ignore=("use_original_coords",
                                            "axis_forward",
                                            "axis_up",
                                            "use_selection",
                                            "global_scale",
                                            "check_existing",
                                            "filter_glob",
                                            "use_scene_unit",
                                            "use_mesh_modifiers",
                                            "batch_mode"
                                            ))

        scene = context.scene
        
        #gather all important assets
        
        #data_seq = [ob for ob in context.scene.objects if ob.select]
        data_seq = []
        for ob in bpy.data.objects:
            if ob.get('d3output') == 1:
                data_seq.append(ob)

        print(data_seq)
        temp_directory = tempfile.gettempdir()    
        manual_temp_directory = "C:\\Users\\paperspace\\AppData\\Local\\Temp"
        output_path = os.path.join(manual_temp_directory, self.case_name + ".zip")
        print(temp_directory)
        print(output_path)
        
        
        zf = zipfile.ZipFile(output_path, 'w')
        
        # Take into account scene's unit scale, so that 1 inch in Blender gives 1 inch elsewhere! See T42000.
        global_scale = self.global_scale
        if scene.unit_settings.system != 'NONE' and self.use_scene_unit:
            global_scale *= scene.unit_settings.scale_length

        
        global_matrix = axis_conversion(from_forward=self.axis_forward,
                                        from_up=self.axis_up,
                                        ).to_4x4() * Matrix.Scale(global_scale, 4)

        
        for ob in data_seq:
            faces = blender_utils.faces_from_mesh(ob, global_matrix, self.use_mesh_modifiers)
            
            ob_file_path = os.path.join(manual_temp_directory, bpy.path.clean_name(ob.name) + ".stl")
            stl_utils.write_stl(filepath = ob_file_path, faces=faces)
            zf.write(ob_file_path)
            
        zf.close()
        
        #TODO Save the blend file to d3tool.online
        
        #send the zip file home with them
        basename = os.path.basename(output_path)
        url = D3WebAPI.get_upload_url(basename)
        D3WebAPI.upload_file(url, output_path)
        popup_url = D3WebAPI.get_download_url(basename)
        D3WebAPI.send_popup(popup_url)


        return {'FINISHED'}



def register():
    bpy.utils.register_class(D3TOOL_AI_export_segmentation_case)
    

def unregister():
    bpy.utils.unregister_class(D3TOOL_AI_export_segmentation_case)
    