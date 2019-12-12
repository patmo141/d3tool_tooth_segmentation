'''
Copyright (C) 2015 Patrick Moore
patrick.moore.bu@gmail.com


Created by Patrick Moore

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

bl_info = {
    "name":        "AITooth Segmentation",
    "description": "Tools for automatically finding teeth from 3d scans",
    "author":      "Patrick Moore",
    "version":     (0, 0, 1),
    "blender":     (2, 7, 9),
    "location":    "View 3D > Tool Shelf",
    "warning":     "",  # used for warning icon and text in addons panel
    "wiki_url":    "",
    "tracker_url": "",
    "category":    "3D View"
    }

# Blender imports
import bpy
from bpy.types import Operator, AddonPreferences
from bpy.props import StringProperty, IntProperty, BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty
#TODO Preferences
#TODO Menu

#Tools
from .op_ai_teeth.ai_teeth import AITeeth_Polytrim

from . import salience
from . import helper_ops
from . import get_convex_teeth
from .operators import pick_teeth

class AISceneSettings(bpy.types.PropertyGroup):
    accept_ua = BoolProperty(name = 'Accept User Agreement', default = False, description = "Acknowledge that you have read and agree to the user agreement")
    acknowledge_upload = BoolProperty(name = 'Acknowledge Upload', default = False, description = "Acknowledge that you understand files will be transmitted to Google server")
    certify_anonymous = BoolProperty(name = 'Certify Anonymous', default = False, description = "Certify that there are no patient identifiers (name, dob etc) on the model")
    
    segmentation_quality = IntProperty(name = 'User Rating', default = -1, min = -1, max = 10, description = 'Subjective rating of quality of segmentation')
    
    demo_file = BoolProperty(name = 'Demo Files', default = False, description = "If demo file, do not precompute or upload")
    
#addon preferences
class AITeethPreferences(AddonPreferences):
    bl_idname = __name__

    addons = bpy.context.user_preferences.addons
    
    
    #cloud behavior
    upload_timeout = IntProperty(name = 'Download Timeout', default = 120, min = 30, max = 300)
    download_timeout = IntProperty(name = 'Download Timeout', default = 80, min = 10, max = 300)
    
    
    tooth_system = EnumProperty(name = 'Tooth Nomenclature', items = [('FDI', 'FDI', 'FDI'),('UNIVERSAL','UNIVERSAL','UNVERSAL')], default = 'UNIVERSAL')
    
    key_path = StringProperty(name = 'User Key File', subtype = 'FILE_PATH', default = '')
    key_string = StringProperty(name = 'User Key', subtype = 'PASSWORD',  default = '')
    
    #Segmentation Editor Behavior
    spline_preview_tess = IntProperty(name = 'Spline Teseslation', default = 20, min = 3, max = 100)
    sketch_fit_epsilon = FloatProperty(name = 'Sketch Epsilon', default = 0.25, min = 0.001, max = 10)
    patch_boundary_fit_epsilon = FloatProperty(name = 'Boundary Epsilon', default = 0.35, min = .001, max = 10)
    spline_tessellation_epsilon = FloatProperty(name = 'Spline Epsilon', default = 0.1, min = .001, max = 10)
    
    destructive = EnumProperty(name = 'Geometry Mode', items = [('DESTRUCTIVE', 'DESTRUCTIVE', 'DESTRUCTIVE'),('NON_DESTRUCTIVE','NON_DESTRUCTIVE','NON_DESTRUCTIVE')], default = 'DESTRUCTIVE')
    #2D Interaction Behavior
    non_man_snap_pxl_rad = IntProperty(name = 'Snap Radius Pixel', default = 20, min =5, max = 150)
    sel_pxl_rad = IntProperty(name = 'Select Radius Pixel', default = 10, min = 3, max = 100)
    loop_close_pxl_rad = IntProperty(name = 'Select Radius Pixel', default = 10, min = 3, max = 100)

    #Menu Colors
    menu_bg_color = FloatVectorProperty(name="Menu Backgrounng Color", description="FLoating Menu color", min=0, max=1, default=(.3,.3,.3), subtype="COLOR")
    menu_border_color = FloatVectorProperty(name="Menu Border Color", description="FLoating menu border colro", min=0, max=1, default=(.1,.1,.1), subtype="COLOR")
    deact_button_color = FloatVectorProperty(name="Button Color", description="Deactivated button color", min=0, max=1, default=(.5,.5,.5), subtype="COLOR")
    act_button_color = FloatVectorProperty(name="Active Button Color", description="Activated button color", min=0, max=1, default=(.2,.2,1), subtype="COLOR")
    
    
    #Geometry Colors
    act_point_color = FloatVectorProperty(name="Active Point Color", description="Selected/Active point color", min=0, max=1, default=(.2,.7,.2), subtype="COLOR")
    act_patch_color = FloatVectorProperty(name="Active Patch Color", description="Selected/Active patch color", min=0, max=1, default=(.2,.7,.2), subtype="COLOR")
    spline_default_color = FloatVectorProperty(name="Spline Color", description="Spline color", min=0, max=1, default=(.2,.2,.7), subtype="COLOR")
    hint_color = FloatVectorProperty(name="Hint Color", description="Hint Geometry color", min=0, max=1, default=(.5,1,.5), subtype="COLOR")
    bad_segment_color = FloatVectorProperty(name="Active Button Color", description="Activated button color", min=0, max=1, default=(1,.6,.2), subtype="COLOR")
    bad_segment_hint_color = FloatVectorProperty(name="Bad Segment Hint", description="Bad segment hint color", min=0, max=1, default=(1,0,0), subtype="COLOR")
    
    
    def draw(self, context):
        layout = self.layout
        layout.label(text="AI Teeth Peferences")
        #layout.prop(self, "mat_lib")
        
        row = layout.row()
        row.label('Labelling Settings')
        row = layout.row()
        row.prop(self, "tooth_system")
        
        ## Visualization 
        row = layout.row(align=True)
        row.label("Timeout Settings")

        row = layout.row(align=True)
        row.prop(self, "upload_timeout")
        row.prop(self, "download_timeout")
        
        row = layout.row(align=True)
        row.prop(self, "key_path")

        row = layout.row(align=True)
        row.prop(self, "key_string")
        
class VIEW3D_PT_AITeeth(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type="TOOLS"
    bl_category = "Tooth Segmentation"
    bl_label = "AI Teeth Segmentation"
    bl_context = ""

    def draw(self, context):
        sce = bpy.context.scene
        layout = self.layout
        
        row = layout.row()
        row.label('Acknowledments')
        row = layout.row()
        row.operator("ai_teeth.open_disclosures", text="Read Agreement")
        row = layout.row()
        row.prop(sce.ai_settings, "accept_ua")
        row = layout.row()
        row.prop(sce.ai_settings, "acknowledge_upload")
        row = layout.row()
        row.prop(sce.ai_settings, "certify_anonymous")
        
        #split = layout.split()
        row = layout.row()
        row.operator("import_mesh.stl", text="Import Model")
        row = layout.row()
        row.operator("ai_teeth.anonymize_names", text = "Anonymize Name")
        row = layout.row()
        row.operator("aiteeth.mark_tooth_locations", text = 'Indicate Teeth')
        row = layout.row()
        row.operator("ai_teeth.cloud_preprocess_model", text = "Cloud Preprocess Model")
        row = layout.row()
        row.operator("ai_teeth.polytrim", text = "Interactive Assisted Segment")
        

        row = layout.row()
        row.label('Get Solid Teeth')
        row = layout.row()
        row.operator("ai_teeth.cloud_convex_teeth")
        

    
def register(): 
    bpy.utils.register_class(AITeethPreferences)
    bpy.utils.register_class(AITeeth_Polytrim)
    bpy.utils.register_class(VIEW3D_PT_AITeeth)
    salience.register()
    helper_ops.register()
    get_convex_teeth.register()
    pick_teeth.register()
    
    bpy.utils.register_class(AISceneSettings)
    bpy.types.Scene.ai_settings = bpy.props.PointerProperty(type = AISceneSettings)
    
def unregister():
    bpy.utils.unregister_class(AITeethPreferences)
    bpy.utils.unregister_class(AITeeth_Polytrim)
    bpy.utils.unregister_class(VIEW3D_PT_AITeeth)
    salience.unregister()
    helper_ops.unregister()
    pick_teeth.unregister()
    get_convex_teeth.unregister()
    bpy.utils.unregister_class(AISceneSettings)
    del bpy.types.scene.ai_settings
