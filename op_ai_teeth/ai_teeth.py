'''
Created on Oct 8, 2015

@author: Patrick
'''
import bpy
import time

from ..cookiecutter.cookiecutter import CookieCutter
from ..common import ui
from ..common.ui import Drawing

from .ai_teeth_ui_init       import AITeeth_UI_Init
from .ai_teeth_states        import AITeeth_States
from .ai_teeth_ui_tools      import AITeeth_UI_Tools
from .ai_teeth_ui_draw       import AITeeth_UI_Draw
from .ai_teeth_datastructure import InputNetwork, NetworkCutter, SplineNetwork
from ..common.utils import get_settings


#ModalOperator
class AITeeth_Polytrim(AITeeth_States, AITeeth_UI_Init, AITeeth_UI_Tools, AITeeth_UI_Draw, CookieCutter):
    ''' Cut Mesh Polytrim Modal Editor '''
    ''' Note: the functionality of this operator is split up over multiple base classes '''

    operator_id    = "ai_teeth.polytrim"    # operator_id needs to be the same as bl_idname
                                            # important: bl_idname is mangled by Blender upon registry :(
    bl_idname      = "ai_teeth.polytrim"
    bl_label       = "AI Tooth Segmentation"
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_options = {'REGISTER','UNDO'}

    default_keymap = {
        # key: a human-readable label
        # val: a str or a set of strings representing the user action
        'action': {'LEFTMOUSE'},
        'sketch': {'SHIFT+LEFTMOUSE'},
        'select': {'LEFTMOUSE'},
        'connect': {'LEFTMOUSE'},
        'add point': {'LEFTMOUSE'},
        'add point (disconnected)': {'CTRL+LEFTMOUSE'},
        'cancel': {'ESC', 'RIGHTMOUSE'},
        'grab': 'G',
        'delete': {'RIGHTMOUSE'},
        'paint delete':{'CTRL+RIGHTMOUSE'},
        'delete (disconnect)': {'CTRL+RIGHTMOUSE'},
        'preview cut': 'C',
        'up': 'UP_ARROW',
        'down': 'DOWN_ARROW'
        # ... more
    }

    @classmethod
    def can_start(cls, context):
        ''' Called when tool is invoked to determine if tool can start '''
        if context.mode != 'OBJECT':
            #showErrorMessage('Object Mode please')
            return False
        if not context.object:
            return False
        if context.object.type != 'MESH':
            #showErrorMessage('Must select a mesh object')
            return False

        if context.object.hide:
            return False

        if 'Salience' not in context.object.data.vertex_colors:
            return False
        
        return True

    def window_state_restore(self, ignore_panels = False):
        pass
    
    def start(self):
        self.cursor_modal_set('CROSSHAIR')


        #bpy.ops.object.mode_set(mode = 'SCULPT')
        #if not bpy.context.object.use_dynamic_topology_sculpting:
        #    bpy.ops.sculpt.dynamic_topology_toggle()
        
        
        #self.drawing = Drawing.get_instance()
        self.drawing.set_region(bpy.context.region, bpy.context.space_data.region_3d, bpy.context.window)
        self.mode_pos        = (0, 0)
        self.cur_pos         = (0, 0)
        self.mode_radius     = 0
        self.action_center   = (0, 0)

        self.mask_threshold = .95
        
        prefs = get_settings()
        self.start_time = time.time()
        #bpy.ops.object.mode_set(mode = 'SCULPT')
        #if not model.use_dynamic_topology_sculpting:
        #    bpy.ops.sculpt.dynamic_topology_toggle()
        
        #scene = bpy.context.scene
        #paint_settings = scene.tool_settings.unified_paint_settings
        #paint_settings.use_locked_size = True
        #paint_settings.unprojected_radius = .5
        #brush = bpy.data.brushes['Mask']
        #brush.strength = 1
        #brush.stroke_method = 'SPACE'
        #scene.tool_settings.sculpt.brush = brush
        #scene.tool_settings.sculpt.use_symmetry_x = False
        #scene.tool_settings.sculpt.use_symmetry_y = False
        #scene.tool_settings.sculpt.use_symmetry_z = False
        #bpy.ops.brush.curve_preset(shape = 'MAX')
        
        #need to inject this color layer and make active before generating bmesh makes it a lot easier
        mesh = self.context.object.data
        if "patches" not in mesh.vertex_colors:
            vcol = mesh.vertex_colors.new(name = "patches")
        else:
            vcol = mesh.vertex_colors.get("patches")

        mesh.vertex_colors.active = vcol
        for ind, v_color in enumerate(mesh.vertex_colors):
            if v_color == vcol:
                break
        mesh.vertex_colors.active_index = ind
        mesh.vertex_colors.active = vcol
        vcol.active_render = True
        mesh.update()
        
        self.net_ui_context = self.NetworkUIContext(self.context, geometry_mode = 'DESTRUCTIVE')

        self.hint_bad = True   #draw obnoxious things over the bad segments
        self.input_net = InputNetwork(self.net_ui_context)
        self.spline_net = SplineNetwork(self.net_ui_context)
        self.network_cutter = NetworkCutter(self.input_net, self.net_ui_context)
        self.sketcher = self.SketchManager(self.input_net, self.spline_net, self.net_ui_context, self.network_cutter)
        self.grabber = self.GrabManager(self.input_net, self.net_ui_context, self.network_cutter)
        self.brush = None
        self.brush_radius = 0.5
        
        self.bad_patches = []
        self.seed_faces = []  #optional
        self.seed_labels = dict()
        #if sees have been previously marked, they will be in a child mesh object
        
        
        self.get_seed_faces()  #find the seed faces of each user clicked point
        self.initialize_face_patches_from_seeds() #initialize a small region around each face
        
        self.salience_verts = set()
        self.skeleton = set()
        self.skeleton_points = []
        self.has_skeletonized = False
        self.paint_mode = 'MERGE'
        self.workflow_step = 'THRESHOLD'
        
        self.pick_verts_by_salience_color()  #initiate salience_select color by dual threshold
        #self.mask_verts_by_salience_color()  #try using sculpt mask instead! 
        
        #get from preferences or override
        #TODO maybe have a "preferences" within the segmentation operator
        self.spline_preview_tess = prefs.spline_preview_tess
        self.sketch_fit_epsilon = prefs.sketch_fit_epsilon
        self.patch_boundary_fit_epsilon =  prefs.patch_boundary_fit_epsilon
        self.spline_tessellation_epsilon = prefs.spline_tessellation_epsilon

        self.ui_setup()
        self.fsm_setup()
        self.window_state_overwrite(show_only_render=False, hide_manipulator=True)
        

    def end(self):
        ''' Called when tool is ending modal '''
        self.header_text_set()
        self.cursor_modal_restore()

    def update(self):
        pass