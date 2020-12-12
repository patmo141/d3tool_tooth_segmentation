'''
Created on Feb 19, 2020

@author: Patrick
'''
import bpy
import bmesh
import math
from mathutils import Matrix, Vector, Color


from ..subtrees.addon_common.cookiecutter.cookiecutter import CookieCutter
from ..subtrees.addon_common.common.decorators import PersistentOptions
from ..subtrees.addon_common.common import ui


def in_region(reg, x, y):
    #first, check outside of area
    if x < reg.x: return False
    if y < reg.y: return False
    if x > reg.x + reg.width: return False
    if y > reg.y + reg.height: return False
    
    return True



def rgb_material():
    
    red = bpy.data.materials.get("red")
    if red is None:
        # create material
        red = bpy.data.materials.new(name="red")
        red.diffuse_color = Color((1, 0, 0))
    
    green = bpy.data.materials.get("green") 
    if green is None:
        # create material
        green = bpy.data.materials.new(name="green")
        green.diffuse_color = Color((0, 1, 0))
    blue = bpy.data.materials.get("blue")    
    if blue is None:
        # create material
        blue = bpy.data.materials.new(name="blue")
        blue.diffuse_color = Color((0, 0, 1))
        
    return red, green, blue   
        
 
def create_axis_vis():
    
    ob = bpy.data.objects.get('Empty View')
    if not ob:
        me = bpy.data.meshes.new('Empty View')
        ob = bpy.data.objects.new('Empty View',me)
        bpy.context.scene.objects.link(ob)
        
        red, green, blue = rgb_material()
        
        me.materials.append(red)
        me.materials.append(green)
        me.materials.append(blue)
    
    bme = bmesh.new()
    
    mxy = Matrix.Rotation(math.pi/2, 4, 'X')
    mxx = Matrix.Rotation(math.pi/2, 4, 'Y')
    
    geom = bmesh.ops.create_cone(bme, cap_ends=True, cap_tris=False, segments=24, diameter1=0.5, diameter2=0.5, depth=20)
    print(geom)
    fs = set()
    for v in geom['verts']:
        fs.update(v.link_faces[:])
    for f in fs:
        f.material_index = 0
        
    geom = bmesh.ops.create_cone(bme, cap_ends=True, cap_tris=False, segments=24, diameter1=0.5, diameter2=0.5, depth=20, matrix = mxx)
    fs = set()
    for v in geom['verts']:
        fs.update(v.link_faces[:])
    for f in fs:
        f.material_index = 1
        
        
        
    geom = bmesh.ops.create_cone(bme, cap_ends=True, cap_tris=False, segments=24, diameter1=0.5, diameter2=0.5, depth=20, matrix = mxy)
    fs = set()
    for v in geom['verts']:
        fs.update(v.link_faces[:])
    for f in fs:
        f.material_index = 2
        
        
    bme.to_mesh(ob.data)
    bme.free()
    
    
  
            
    #ob.show_xray = True    
    return ob
 
 
 
class AITeeth_OT_ortho_setup(bpy.types.Operator):
    """Generate Ortho Setup"""
    bl_idname = "ai_teeth.adjust_axes"
    bl_label = "Adjust Axes"
    
    
    def exectute(self, context):
        last_root = None
        axis_vis = create_axis_vis()
        
        
        for ob in bpy.data.objects:
            ob.hide = True
            ob.hide_select = True
            if " Convex" in ob.name or "_root" in ob.name:
                ob.hide = False
                
            if " root_empty" in ob.name:
                ob.hide_select = False
                last_root = ob
                ob.data = axis_vis.data
                
                
                
                
        
        last_root.select = True
        
        
            
            
        
            
        
class D3Ortho_OT_adjust_axes(CookieCutter):
    """ Allows easy adjustment of axes"""
    operator_id    = "d3ortho.adjust_axes"
    bl_idname      = "d3ortho.adjust_axes"
    bl_label       = "Adjust Axes"
    bl_description = "Use to adjust the long axis for optimal gingival sim"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "TOOLS"

    
    default_keymap = {
        "select": {"RIGHTMOUSE"},
        "commit": {"RET","RETURN",'ENTER'},
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
        for ob in bpy.data.objects:
            ob.select = False
        bpy.context.scene.objects.active = None
        
        if len(self.teeth) == 0:
            self.done(cancel = True)
            return
        
        
        bpy.context.space_data.show_manipulator = True
        bpy.context.space_data.transform_manipulators = {'ROTATE'}
        bpy.context.space_data.transform_orientation = 'LOCAL'
        
        self.set_view()
        

        self.ui_setup()
        #self.ui_setup_post()
        #self.start_post()


    def set_view(self):
        
        last_root = None
        for ob in bpy.data.objects:
            ob.hide = True
            ob.hide_select = True
            ob.select = False
            
            if " Convex" in ob.name or " root_empty" in ob.name:
                ob.hide = False
            else:
                ob.hide = True
                
            if " root_empty" in ob.name:
                ob.hide_select = False
                last_root = ob
                
                
        
        
        last_root.select = True
        bpy.context.scene.objects.active = last_root
        
        
        self.axis_vis.parent = last_root
        self.axis_vis.matrix_world = last_root.matrix_world
        self.axis_vis.hide_select = False
        self.axis_vis.select = True
        self.axis_vis.hide = False
       
        
        #prevent clicking on these objects
        self.axis_vis.hide_select = True
        self.axis_vis.select = False
        
        
    def end_commit(self):
        """ Commit changes to mesh! """
        
        for ob in bpy.data.objects:
            ob.show_x_ray = False
            
        bpy.context.scene.objects.unlink(self.axis_vis)
        
        upper_ob = bpy.data.objects.get(bpy.context.scene.d3ortho_upperjaw)
        lower_ob = bpy.data.objects.get(bpy.context.scene.d3ortho_lowerjaw)
        
        if upper_ob:
            upper_ob.hide = False
            
        if lower_ob:
            lower_ob.hide = False
    
        for ob in self.teeth:
            ob.hide_select = False
            ob.hide = False
            
        
        self.end_commit_post()
        
        bpy.ops.opendental.confirm_tooth_orientations()
        bpy.ops.d3ortho.empties_to_armature()
        bpy.ops.opendental.set_roots_parents()
        
        bpy.context.scene.frame_set(0)
        
        bpy.ops.opendental.set_movement_keyframe()
        
        bpy.context.scene.frame_set(50)
        
        
        
        
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
        #first, check outside of area
        if event.mouse_x < context.area.x: return False
        if event.mouse_y < context.area.y: return False
        if event.mouse_x > context.area.x + context.area.width: return False
        if event.mouse_y > context.area.y + context.area.height: return False
    
        #make sure we are in the window region, not the header, tools or UI
        for reg in context.area.regions:
            if in_region(reg, event.mouse_x, event.mouse_y) and reg.type != "WINDOW":
                return False
        
        if event.type not in {'LEFTMOUSE', 'MOUSEMOVE', 'RIGHTMOUSE'}:
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
        self.cursor_modal_set("DEFAULT")

        #if self.actions.pressed("commit"):   
        #    self.end_commit()
        #    return


        if self.actions.released("select"):  #upon selection, snap the axis vis to the root
            for ob in bpy.data.objects:
                ob.show_x_ray = False
            
            self.axis_vis.parent = bpy.context.object
            self.axis_vis.matrix_world = bpy.context.object.matrix_world
            
            if bpy.context.object.parent != None:
                bpy.context.object.parent.show_x_ray = True
            self.axis_vis.show_x_ray = True
            
            
        if self.actions.pressed("commit"):
            self.done()
            return
        
        
        if self.actions.pressed("cancel"):
            self.done(cancel=True)
            return
        
    
    def ui_setup(self):
        
        win_next_back = self.wm.create_window(None, {'pos':2, "vertical":False, "padding":15, 'movable':True, 'bgcolor':(0.50, 0.50, 0.50, 0.0), 'border_color':(0.50, 0.50, 0.50, 0.9), "border_width":4.0})
        next_back_container = win_next_back.add(ui.UI_Container(vertical = False, background = (0.50, 0.50, 0.50, 0.90)))
        #next_back_frame = next_back_container.add(ui.UI_Frame('', vertical = False, equal = True, separation = 4))#, background = (0.50, 0.50, 0.50, 0.90)))
        
        #cancel_button = next_back_frame.add(ui.UI_Button('Cancel', lambda:self.done(cancel=True), margin=0))
        cancel_button = next_back_container.add(ui.UI_Button('Cancel', lambda:self.done(cancel=True), margin=10))
        cancel_button.label.fontsize = 20
        confirm_button = next_back_container.add(ui.UI_Button('Confirm', self.done, margin = 10))
        confirm_button.label.fontsize = 20    
        
        
def register():
    bpy.utils.register_class(D3Ortho_OT_adjust_axes)
    
def unregister():    
    bpy.utils.unregister_class(D3Ortho_OT_adjust_axes)
    