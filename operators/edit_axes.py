'''
Created on Feb 19, 2020

@author: Patrick
'''
import bpy
import bmesh
import math
from mathutils import Matrix, Vector


from ..subtrees.addon_common.cookiecutter.cookiecutter import CookieCutter
from ..subtrees.addon_common.common.decorators import PersistentOptions



def in_region(reg, x, y):
    #first, check outside of area
    if x < reg.x: return False
    if y < reg.y: return False
    if x > reg.x + reg.width: return False
    if y > reg.y + reg.height: return False
    
    return True


 
def create_axis_vis():
    
    ob = bpy.data.objects.get('Empty View')
    if not ob:
        me = bpy.data.meshes.new('Empty View')
        ob = bpy.data.objects.new('Empty View',me)
        bpy.context.scene.objects.link(ob)
    
    bme = bmesh.new()
    
    mxy = Matrix.Rotation(math.pi/2, 4, 'X')
    mxx = Matrix.Rotation(math.pi/2, 4, 'Y')
    bmesh.ops.create_cone(bme, cap_ends=True, cap_tris=False, segments=24, diameter1=0.5, diameter2=0.5, depth=20)
    bmesh.ops.create_cone(bme, cap_ends=True, cap_tris=False, segments=24, diameter1=0.5, diameter2=0.5, depth=20, matrix = mxx)
    bmesh.ops.create_cone(bme, cap_ends=True, cap_tris=False, segments=24, diameter1=0.5, diameter2=0.5, depth=20, matrix = mxy)
    
    bme.to_mesh(ob.data)
    bme.free()
    return ob
    
class D3Ortho_OT_adjust_axes(CookieCutter):
    """ Allows easy adjustment of axes"""
    operator_id    = "d3ortho.adjust_axes"
    bl_idname      = "d3ortho.adjust_axes"
    bl_label       = "Adjust Axes"
    bl_description = "Use to adjust the long axis for optimal gingival sim"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "TOOLS"

    
    default_keymap = {
        "commit": {"RET"},
        "cancel": {"ESC"},
    }
    
    ################################################
    # CookieCutter Operator methods

    @classmethod
    def can_start(cls, context):
        """ Start only if editing a mesh """
        return True

    def start(self):
        """ Custom Sculpt Mode is starting """
        scn = bpy.context.scene
        bpy.ops.ed.undo_push()  # push current state to undo
        self.start_pre()
        
        
        #get or create axis vis
        self.axis_vis = create_axis_vis()
        
        self.teeth = [ob for ob in bpy.data.objects if 'Convex' in ob.name]
        
        if len(self.teeth) == 0:
            self.done(cancel = True)
            return
        
        
        bpy.context.space_data.show_manipulator = True
        bpy.context.space_data.transform_manipulators = {'ROTATE'}
        bpy.context.space_data.transform_orientation = 'LOCAL'
        
        self.set_view(self.teeth[0])
        

        #self.ui_setup()
        #self.ui_setup_post()
        #self.start_post()


    def set_view(self, ob):
        
        for obj in bpy.data.objects:
            obj.hide = True
            obj.select = False
        
        
        root = bpy.data.objects.get(ob.name.split(' ')[0] + ' root_empty')
        root.hide = False
        root.hide_select = False
        root.select = True
        
        
        self.axis_vis.parent = root
        self.axis_vis.matrix_world = root.matrix_world
        self.axis_vis.hide_select = False
        self.axis_vis.select = True
        self.axis_vis.hide = False
        
        ob.hide = False
        ob.hide_select = False
        ob.select = True
        
        
        bpy.context.scene.objects.active = root
        
        bpy.ops.view3d.localview()
        bpy.ops.screen.region_quadview()
        
        #prevent clicking on these objects
        self.axis_vis.hide_select = True
        self.axis_vis.select = False
        
        ob.hide_select = True
        ob.select = False
        
        
        
    def end_commit(self):
        """ Commit changes to mesh! """
        bpy.ops.object.mode_set(mode='OBJECT')
        self.end_commit_post()
        
    def end_cancel(self):
        """ Cancel changes """
        #bpy.ops.object.mode_set(mode=self.starting_mode)
        bpy.ops.ed.undo()   # undo everything
   
    def end(self):
        """ Restore everything, because we're done """
        self.manipulator_restore()
        self.header_text_restore()
        self.cursor_modal_restore()
        #bpy.ops.view3d.toolshelf()  # show tool shelf
        # bpy.ops.screen.back_to_previous()
    
    def update(self):
        """ Check if we need to update any internal data structures """
        pass

    def should_pass_through(self, context, event):
        print('check pass through')
        #first, check outside of area
        if event.mouse_x < context.area.x: return False
        if event.mouse_y < context.area.y: return False
        if event.mouse_x > context.area.x + context.area.width: return False
        if event.mouse_y > context.area.y + context.area.height: return False
    
        #make sure we are in the window region, not the header, tools or UI
        for reg in context.area.regions:
            if in_region(reg, event.mouse_x, event.mouse_y) and reg.type != "WINDOW":
                return False
            
        print('passing through')
        return True

    ###################################################
    # class methods

    def do_something(self):
        pass

    def do_something_else(self):
        pass

    #############################################
    # Subclassing functions for override

    def start_pre(self):
        pass
    
    def ui_setup_post(self):
        pass

    def start_post(self):
        pass

    def end_commit_post(self):
        pass

    #############################################
    
    @CookieCutter.FSM_State("main")
    def modal_main(self):
        #self.cursor_modal_set("CROSSHAIR")

        #if self.actions.pressed("commit"):   
        #    self.end_commit()
        #    return

        if self.actions.pressed("cancel"):
            self.done(cancel=True)
            return
        
        
def register():
    bpy.utils.register_class(D3Ortho_OT_adjust_axes)
    
def unregister():    
    bpy.utils.unregister_class(D3Ortho_OT_adjust_axes)
    