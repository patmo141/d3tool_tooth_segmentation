'''
Created on Aug 18, 2016

@author: Patrick
some useful tidbits
http://blender.stackexchange.com/questions/44637/how-can-i-manually-calculate-bpy-types-posebone-matrix-using-blenders-python-ap?rq=1
http://blender.stackexchange.com/questions/1640/how-are-the-bones-assigned-to-the-vertex-groups-in-the-api?rq=1
http://blender.stackexchange.com/questions/46928/set-bone-constraints-via-python-api
http://blender.stackexchange.com/questions/40244/delete-bone-constraint-in-python
http://blender.stackexchange.com/questions/19602/child-of-constraint-set-inverse-with-python
http://blender.stackexchange.com/questions/28869/how-to-disable-loop-playback-of-animation
'''
import bpy
import bmesh
import math
from mathutils import Vector, Matrix, Color, Quaternion
from mathutils.bvhtree import BVHTree
from bpy_extras import view3d_utils

from . import bgl_utils
from . import tooth_numbering

#TODO, better system for tooth # systems
#TOOTH_NUMBERS = [11,12,13,14,15,16,17,18,
#                 21,22,23,24,25,26,27,28,
#                 31,32,33,34,35,36,37,38,
#                 41,42,43,44,45,46,47,48]


TOOTH_NUMBERS = [1,2,3,4,5,6,7,8,
                 9,10,11,12,13,14,15,16,
                 17,18,19,20,21,22,23,24,
                 25,26,27,28,29,30,31,32]


def view3d_get_size_and_mid(context):
    region = bpy.context.region
    rv3d = bpy.context.space_data.region_3d

    width = region.width
    height = region.height
    mid = Vector((width/2,height/2))
    aspect = Vector((width,height))

    return [aspect, mid]


def insertion_axis_draw_callback(self, context):
    #self.help_box.draw()
    #self.target_box.draw()
    bgl_utils.insertion_axis_callback(self,context)
 
#def rapid_label_teeth_callback(self, context):
    #self.help_box.draw()
    #self.target_box.draw()
    
        
class OPENDENTAL_OT_add_bone_roots(bpy.types.Operator):
    """Set the axis and direction of the roots for crowns from view"""
    bl_idname = "opendental.add_bone_roots"
    bl_label = "Add bone roots"
    bl_options = {'REGISTER','UNDO'}
    
    @classmethod
    def poll(self,context):
        if context.mode != 'OBJECT':
            return False
        else:
            return True
        
    def set_axis(self, context, event):
        
        if not self.target:
            return
        
        empty_name = self.target.name.split(' ')[0] + ' root_empty'
        if empty_name in context.scene.objects:
            ob = context.scene.objects[empty_name]
            ob.empty_draw_type = 'SINGLE_ARROW'
            ob.empty_draw_size = 10
        else:
            ob = bpy.data.objects.new(empty_name, None)
            ob.empty_draw_type = 'SINGLE_ARROW'
            ob.empty_draw_size = 10
            context.scene.objects.link(ob)
            
        coord = (event.mouse_region_x, event.mouse_region_y)
        v3d = context.space_data
        rv3d = v3d.region_3d
        view_vector = view3d_utils.region_2d_to_vector_3d(context.region, rv3d, coord)
        ray_origin = view3d_utils.region_2d_to_origin_3d(context.region, rv3d, coord)
        ray_target = ray_origin + (view_vector * 1000)

        res, loc, no, ind, obj, mx = context.scene.ray_cast(ray_origin, view_vector)
        
        if res:
            if obj != self.target:
                return
                
            ob.location = loc
        else:
            return
            
        if ob.rotation_mode != 'QUATERNION':
            ob.rotation_mode = 'QUATERNION'
            
        vrot = rv3d.view_rotation    
        ob.rotation_quaternion = vrot
                   
    def advance_next_prep(self,context):
        if self.target == None:
            self.target = self.units[0]
            
        ind = self.units.index(self.target)
        prev = int(math.fmod(ind + 1, len(self.units)))
        self.target = self.units[prev]
        self.message = "Set axis for %s" % self.target.name
        context.area.header_text_set(self.message)
        #self.target_box.raw_text = self.message
        #self.target_box.format_and_wrap_text()
        #self.target_box.fit_box_width_to_text_lines()

        for obj in context.scene.objects:
            obj.select = False
        
        self.target.select = True
        context.space_data.region_3d.view_location = self.target.location
        
              
    def select_prev_unit(self,context):
        if self.target == None:
            self.target = self.units[0]
            
        ind = self.units.index(self.target)
        prev = int(math.fmod(ind - 1, len(self.units)))
        self.target = self.units[prev]
        self.message = "Set axis for %s" % self.target.name
        #self.target_box.raw_text = self.message
        #self.target_box.format_and_wrap_text()
        #self.target_box.fit_box_width_to_text_lines()

        for obj in context.scene.objects:
            obj.select = False
        
        self.target.select = True
        context.space_data.region_3d.view_location = self.target.location
                       
    def update_selection(self,context):
        if not len(context.selected_objects):
            self.message = "Right Click to Select"
            self.target = None
            return
        
        if context.selected_objects[0] not in self.units:
            self.message = "Selected Object must be tooth"      
            self.target = None
            return

        self.target = context.selected_objects[0]
        self.message = "Set axis for %s" % self.target.name
        #self.target_box.raw_text = self.message
        #self.target_box.format_and_wrap_text()
        #self.target_box.fit_box_width_to_text_lines()
        
    def empties_to_bones(self,context):
        bpy.ops.object.select_all(action = 'DESELECT')
        
        arm_ob = bpy.data.objects['Roots']
        arm_ob.select = True
        context.scene.objects.active = arm_ob
        bpy.ops.object.mode_set(mode = 'EDIT')
        
        for ob in self.units:
            e = context.scene.objects.get(ob.name.split(' ')[0] + ' root_empty')
            b = arm_ob.data.edit_bones.get(ob.name.split(' ')[0] + ' root')
            
            if e != None and b != None:
                b.transform(ob.matrix_world)
                #b.transform(e.matrix_world) #this gets the local x,y,z in order
                Z = e.matrix_world.to_quaternion() * Vector((0,0,1))
                #b.tail.xyz = e.location
                #b.head.xyz = e.location - 16 * Z
                b.head.xyz = ob.location
                b.tail.xyz = ob.location - 16 * Z
                
                
                b.head_radius = 1.5
                b.tail_radius = 2.5
                
                e.empty_draw_type = 'PLAIN_AXES'
                e.empty_draw_size = 10
                #no let's keep the empty
                #context.scene.objects.unlink(e)
                #e.user_clear()
                #bpy.data.objects.remove(e)
            else:
                print('missing bone or empty')
                    
        bpy.ops.object.mode_set(mode = 'OBJECT')
        
           
    def modal_main(self, context, event):
        # general navigation
        nmode = self.modal_nav(event)
        if nmode != '':
            return nmode  #stop here and tell parent modal to 'PASS_THROUGH'

        if event.type in {'RIGHTMOUSE'} and event.value == 'PRESS':
            self.update_selection(context)
            return 'pass'
        
        elif event.type == 'RIGHTMOUSE' and event.value == 'RELEASE':
            self.update_selection(context)
            if len(context.selected_objects):
                context.space_data.region_3d.view_location = context.selected_objects[0].location
            return 'main'
        
        elif event.type in {'LEFTMOUSE'} and event.value == 'PRESS':
            self.set_axis(context, event)
            self.advance_next_prep(context)
            return 'main'
        
        elif event.type in {'DOWN_ARROW'} and event.value == 'PRESS':
            self.select_prev_unit(context)
            return 'main'
        
        elif event.type in {'UP_ARROW'} and event.value == 'PRESS':
            self.advance_next_prep(context)
            return 'main'
                    
        elif event.type in {'ESC'}:
            #keep track of and delete new objects? reset old transforms?
            return'cancel'
        
        elif event.type in {'RET'} and event.value == 'PRESS':
            self.empties_to_bones(context)
            return 'finish'
        
        return 'main'
        
    def modal_nav(self, event):
        events_nav = {'MIDDLEMOUSE', 'WHEELINMOUSE','WHEELOUTMOUSE', 'WHEELUPMOUSE','WHEELDOWNMOUSE'} #TODO, better navigation, another tutorial
        handle_nav = False
        handle_nav |= event.type in events_nav

        if handle_nav: 
            return 'nav'
        return ''

    def modal(self, context, event):
        context.area.tag_redraw()

        FSM = {}    
        FSM['main']    = self.modal_main
        FSM['pass']    = self.modal_main
        FSM['nav']     = self.modal_nav
        
        nmode = FSM[self.mode](context, event)

        if nmode == 'nav': 
            return {'PASS_THROUGH'}
        
        if nmode in {'finish','cancel'}:
            #clean up callbacks
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'FINISHED'} if nmode == 'finish' else {'CANCELLED'}
        if nmode == 'pass':
            self.mode = 'main'
            return {'PASS_THROUGH'}
        
        if nmode: self.mode = nmode
        
        return {'RUNNING_MODAL'}
     
    def invoke(self, context, event):
        
        
        if context.space_data.region_3d.is_perspective:
            #context.space_data.region_3d.is_perspective = False
            bpy.ops.view3d.view_persportho()
            
        if context.space_data.type != 'VIEW_3D':
            self.report({'WARNING'}, "Active space must be a View3d")
            return {'CANCELLED'}

        #gather all the teeth in the scene TODO, keep better track
        self.units = []
        
        for i in TOOTH_NUMBERS:
            ob = context.scene.objects.get(str(i) + ' Convex')
            if ob != None and not ob.hide:
                self.units.append(ob)
            
        if not len(self.units):
            self.report({'ERROR'}, "There are no teeth in the scene!, Teeth must be named 2 digits eg 11 or 46")
            return {'CANCELLED'}
        
        self.target = self.units[0]
        self.message = "Set axis for %s" %self.target.name
        context.area.header_text_set(self.message)
          
        #check for an armature
        bpy.ops.object.select_all(action = 'DESELECT')
        if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode = 'OBJECT')
                
        if context.scene.objects.get('Roots'):
            root_arm = context.scene.objects.get('Roots')
            root_arm.select = True
            root_arm.hide = False
            context.scene.objects.active = root_arm
            bpy.ops.object.mode_set(mode = 'EDIT')
            
            for ob in self.units:
                if ob.name + 'root' not in root_arm.data.bones:
                    bpy.ops.armature.bone_primitive_add(name = ob.name.split(' ')[0] + ' root')
            
        else:
            root_data = bpy.data.armatures.new('Roots')
            root_arm = bpy.data.objects.new('Roots',root_data)
            context.scene.objects.link(root_arm)
            
            root_arm.select = True
            context.scene.objects.active = root_arm
            bpy.ops.object.mode_set(mode = 'EDIT')
            
            for ob in self.units:
                bpy.ops.armature.bone_primitive_add(name = ob.name.split(' ')[0] + ' root')
        
        bpy.ops.object.mode_set(mode = 'OBJECT')
        root_arm.select = False
        self.units[0].select = True
            
        help_txt = "Right click to select a tooth \n Align View with root, mes and distal\n Up Arrow and Dn Arrow to select different units \n Left click in middle of prep to set axis \n Enter to finish \n ESC to cancel"
        ##self.help_box = TextBox(context,500,500,300,200,10,20,help_txt)
        #self.help_box.fit_box_width_to_text_lines()
        #self.help_box.fit_box_height_to_text_lines()
        #self.help_box.snap_to_corner(context, corner = [1,1])
        
        aspect, mid = view3d_get_size_and_mid(context)
        #self.target_box = TextBox(context,mid[0],aspect[1]-20,300,200,10,20,self.message)
        #self.target_box.format_and_wrap_text()
        #self.target_box.fit_box_width_to_text_lines()
        #self.target_box.fit_box_height_to_text_lines()
        
        self.mode = 'main'
        context.window_manager.modal_handler_add(self)
        self._handle = bpy.types.SpaceView3D.draw_handler_add(insertion_axis_draw_callback, (self, context), 'WINDOW', 'POST_PIXEL')
        return {'RUNNING_MODAL'}


 
class OPENDENTAL_OT_confirm_transforms_for_teeth (bpy.types.Operator):
    """Confirm tooth orientations"""
    bl_idname = "opendental.confirm_tooth_orientations"
    bl_label = "Confirm Tooth Transforms"
    bl_options = {'REGISTER','UNDO'}
    
    
    @classmethod
    def poll(self,context):
        return context.mode == 'OBJECT'
    
    def execute(self, context):
        
        teeth = [ob for ob in bpy.data.objects if 'Convex' in ob.name]
        
        for ob in teeth:
            name = ob.name.split(' ')[0] + ' root_empty'
            axis = bpy.data.objects.get(name)
            mx = axis.matrix_world.copy()
            rmx = mx.to_3x3().to_4x4()
            irmx = rmx.inverted()
            
            T,R,S = ob.matrix_world.decompose()
            
            Rmx = R.to_matrix().to_4x4()
            Tmx = Matrix.Translation(T)
            ob.data.transform(irmx)
            
            ob.matrix_world = Tmx * rmx * Rmx
            axis.matrix_world = mx  #because axis is a child of the tooth
        return {'FINISHED'}
    
class OPENDENTAL_OT_empties_to_armature(bpy.types.Operator):
    """Confirm tooth orientations"""
    bl_idname = "d3ortho.empties_to_armature"
    bl_label = "Empties to Armature"
    bl_options = {'REGISTER','UNDO'}
    
    
    @classmethod
    def poll(self,context):
        return context.mode == 'OBJECT'
    
        
    def execute(self, context):
        
        teeth = [ob for ob in bpy.data.objects if 'Convex' in ob.name]
        
        bpy.ops.object.select_all(action = 'DESELECT')
        
        arm_ob = bpy.data.objects.get('Roots')
        
        if not arm_ob:
        
            root_data = bpy.data.armatures.new('Roots')
            arm_ob = bpy.data.objects.new('Roots',root_data)
            context.scene.objects.link(arm_ob)
            
        arm_ob.select = True
        context.scene.objects.active = arm_ob
        bpy.ops.object.mode_set(mode = 'EDIT')
        
        for ob in teeth:
            if ob.name + 'root' not in arm_ob.data.bones:
                bpy.ops.armature.bone_primitive_add(name = ob.name.split(' ')[0] + ' root')
            
        bpy.ops.armature.bone_primitive_add(name = "Non Movable")
        for ob in teeth:
            e = context.scene.objects.get(ob.name.split(' ')[0] + ' root_empty')
            b = arm_ob.data.edit_bones.get(ob.name.split(' ')[0] + ' root')
            
            if e != None and b != None:
                b.transform(ob.matrix_world)
                #b.transform(e.matrix_world) #this gets the local x,y,z in order
                Z = e.matrix_world.to_quaternion() * Vector((0,0,-1))
                #b.tail.xyz = e.location
                #b.head.xyz = e.location - 16 * Z
                b.head.xyz = ob.location
                b.tail.xyz = ob.location - 16 * Z
                
                
                b.head_radius = 1.5
                b.tail_radius = 2.5
                
                e.empty_draw_type = 'PLAIN_AXES'
                e.empty_draw_size = 10
                #no let's keep the empty
                #context.scene.objects.unlink(e)
                #e.user_clear()
                #bpy.data.objects.remove(e)
            else:
                print('missing bone or empty')
                    
        bpy.ops.object.mode_set(mode = 'OBJECT')
            
        return {'FINISHED'}


def link_ob_to_bone(jaw_ob, arm_ob):
    #jaw_ob = bpy.data.objects.get('Base Gingiva')
    #create a vertex group for every maxillary bone
    
    
    if 'Upper' in jaw_ob.name:
        tooth_names = tooth_numbering.upper_teeth
    else:
        tooth_names = tooth_numbering.lower_teeth
    for bone in arm_ob.data.bones:
        #if bone.name.startswith('1') or bone.name.startswith('2'):
        #    jaw_ob = max_ob
        #else:
        #    jaw_ob = man_ob
        #TODO clean this up    
        
        if tooth_numbering.data_tooth_label(bone.name.split(' ')[0]) not in tooth_names:
            continue
        
        if bone.name not in jaw_ob.vertex_groups:
            vg = jaw_ob.vertex_groups.new(name = bone.name)
        else:
            vg = jaw_ob.vertex_groups[bone.name]
        #make all members, weight at 0    
        vg.add([i for i in range(0,len(jaw_ob.data.vertices))], 0, type = 'REPLACE')
            
        tooth = bpy.context.scene.objects.get(bone.name.split(' ')[0] + ' Convex')
        if tooth == None: continue
        
        
        if tooth.name+'_prox' in jaw_ob.modifiers:
            mod = jaw_ob.modifiers.get(tooth.name + '_prox')
        else:
            mod = jaw_ob.modifiers.new(tooth.name + '_prox', 'VERTEX_WEIGHT_PROXIMITY')
            
        mod.target = tooth
        mod.vertex_group = bone.name
        mod.proximity_mode = 'GEOMETRY'
        mod.min_dist = 5.0 #4.5
        mod.max_dist = 0
        mod.falloff_type = 'SHARP' #'SMOOTH' #'SHARP' #'ICON_SPHERECURVE'
        mod.show_expanded = False
        #mod.mask_constant = .8  #Try this?
        
        pbone = arm_ob.pose.bones[bone.name]
        
        if 'Child Of' in pbone.constraints:
            cons = pbone.constraints['Child Of']
            cons.target = tooth
            #cons.use_rotation_z = False
        else:
            cons = pbone.constraints.new(type = 'CHILD_OF')
            cons.target = tooth
                
            arm_ob.data.bones.active = pbone.bone
            bone.select = True
            bpy.ops.object.mode_set(mode = 'POSE')
            
            context_copy = bpy.context.copy()
            context_copy["constraint"] = pbone.constraints["Child Of"]    
            bpy.ops.constraint.childof_set_inverse(context_copy, constraint="Child Of", owner='BONE')
            bpy.ops.object.mode_set(mode = 'OBJECT')
            
            cons2 = pbone.constraints.new(type = 'LIMIT_ROTATION')
            cons2.owner_space = 'LOCAL'
            cons2.use_limit_y = True
            cons2.min_y = -3 * math.pi/180
            cons2.max_y = 3 * math.pi/180
    
    if "Non Movable" not in jaw_ob.vertex_groups:
        vg = jaw_ob.vertex_groups.new(name = "Non Movable")
    else:
        vg = jaw_ob.vertex_groups.get('Non Movable')
    vg.add([i for i in range(0,len(jaw_ob.data.vertices))], 0, type = 'REPLACE')
    
    if "Non Movable" in jaw_ob.modifiers:
            mod = jaw_ob.modifiers.get("Non Movable")
    else:
        mod = jaw_ob.modifiers.new("Non MOvable", 'VERTEX_WEIGHT_PROXIMITY')
        
    mod.target = bpy.data.objects.get('Teeth Subtract')
    mod.vertex_group = bone.name
    mod.proximity_mode = 'GEOMETRY'
    mod.min_dist = 0.0 #4.5
    mod.max_dist = 7.0
    mod.falloff_type = 'SHARP' #'SMOOTH' #'SHARP' #'ICON_SPHERECURVE'
    mod.show_expanded = False
    
        
    
    #apply the prox mods
    old_me = jaw_ob.data
    me = jaw_ob.to_mesh(bpy.context.scene, apply_modifiers = True, settings = 'PREVIEW')
    jaw_ob.modifiers.clear()
    jaw_ob.data = me
    bpy.data.meshes.remove(old_me)
    
    if 'Armature' in jaw_ob.modifiers:
        mod = jaw_ob.modifiers['Armature']
        jaw_ob.modifiers.remove(mod)
    mod = jaw_ob.modifiers.new('Armature', type = 'ARMATURE')
    mod.object = arm_ob
    mod.use_vertex_groups = True  
    
def apply_mods(ob):
    
    me = ob.to_mesh(bpy.context.scene, apply_modifiers = True, settings = 'PREVIEW')
    old_data = ob.data
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(old_data)
                    
class OPENDENTAL_OT_setup_root_parenting(bpy.types.Operator):
    """Prepares model for gingival simulation"""
    bl_idname = "opendental.set_roots_parents"
    bl_label = "Set Root Parents"
    bl_options = {'REGISTER','UNDO'}
    
    link_to_cast = bpy.props.BoolProperty(default = False)
    @classmethod
    def poll(self,context):
        return context.mode == 'OBJECT'
    
    def execute(self, context):
        
        #make sure we don't mess up any animations!
        context.scene.frame_set(0)
        
        max_ob = bpy.data.objects.get('Upper Gingiva')
        mand_ob = bpy.data.objects.get('Lower Gingiva')
        arm_ob = context.scene.objects.get('Roots')
                    
        if arm_ob == None:
            self.report({'ERROR'}, "You need a 'Roots' armature, please add one or see wiki")
            return {'CANCELLED'}
        
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode = 'OBJECT')
        
        context.scene.objects.active = arm_ob
        arm_ob.select = True
        
        if max_ob:
            if len(max_ob.modifiers):
                apply_mods(max_ob)
            
            link_ob_to_bone(max_ob, arm_ob)
        if mand_ob:
            if len(max_ob.modifiers):
                apply_mods(mand_ob)
                
            link_ob_to_bone(mand_ob, arm_ob)
            
            
        for ob in bpy.data.objects:
            ob.hide = True
            if 'Convex' in ob.name:
                ob.hide = False
        if max_ob:
            max_ob.hide = False
            
        if mand_ob:
            mand_ob.hide = False       
        
        return {'FINISHED'}

class OPENDENTAL_OT_adjust_roots(bpy.types.Operator):
    """Adjust root bones in edit_mode before moving teeth"""
    bl_idname = "opendental.adjust_bone_roots"
    bl_label = "Adjust Roots"
    bl_options = {'REGISTER','UNDO'}
    
    @classmethod
    def poll(self,context):
        if 'Roots' in context.scene.objects:
            return True
        else:
            return False
        
    def execute(self, context):
        
        #make sure we don't mess up any animations!
        context.scene.frame_set(0)
        
        arm_ob = context.scene.objects.get('Roots')
        context.scene.objects.active = arm_ob
        
        if context.mode == 'POSE':
            self.report({'ERROR'}, "Roots Armature is in POSE Mode, must be in OBJECT or EDIT mode")
        
        if arm_ob == None:
            self.report({'ERROR'}, "You need a 'Roots' armature, pease add one or see wiki")
            return {'CANCELLED'}
        
        bpy.ops.object.mode_set(mode = 'EDIT')
         
        return {'FINISHED'}
    
class OPENDENTAL_OT_set_treatment_keyframe(bpy.types.Operator):
    """Sets a treatment stage at this frame"""
    bl_idname = "opendental.set_movement_keyframe"
    bl_label = "Set Movement Keyframe"
    bl_options = {'REGISTER','UNDO'}
    
    def execute(self, context):
        #find obs
        obs = [ob for ob in bpy.data.objects if 'Convex' in ob.name]
        #for num in TOOTH_NUMBERS:
        #    ob = context.scene.objects.get(str(num))
        #    if ob != None and not ob.hide:
        #        obs.append(ob)
        #        continue
            
        #    for ob in context.scene.objects:
        #        if ob.name.startswith(str(num)) and not ob.hide:
        #            obs.append(ob)
        
        bpy.ops.object.select_all(action = 'DESELECT')
        for ob in obs:
            ob.select = True
        context.scene.objects.active = ob
        
        if context.scene.keying_sets.active == None:
            bpy.ops.anim.keying_set_active_set(type='BUILTIN_KSI_LocRot')
            
        bpy.ops.anim.keyframe_insert(type = 'BUILTIN_KSI_LocRot') 
        
        for ob in obs:
            fcurves = ob.animation_data.action.fcurves
            for fcurve in fcurves:
                for kf in fcurve.keyframe_points:
                    kf.interpolation = 'LINEAR'
        
        return {'FINISHED'}
       
       
#TODO update for tooth numbering       
class OPENDENTAL_OT_maxillary_view(bpy.types.Operator):
    '''Will hide all non maxillary objects'''
    bl_idname = "opendental.show_max_teeth"
    bl_label = "Show Maxillary Teeth"
    bl_options = {'REGISTER','UNDO'}

    show_master = bpy.props.BoolProperty(default = False)
    
    def execute(self, context):
        for ob in context.scene.objects:
            if ob.name.startswith('1') or ob.name.startswith('2'):
                ob.hide = False
            
            elif ('upper' in ob.name or 'Upper' in ob.name) and self.show_master:
                ob.hide = False
            elif ('maxil' in ob.name or 'Maxil' in ob.name) and self.show_master:
                ob.hide = False
            else:
                ob.hide = True              
        return {'FINISHED'}

#TODO update for tooth numbering      
class OPENDENTAL_OT_mandibular_view(bpy.types.Operator):
    '''Will hide all non mandibuar objects'''
    bl_idname = "opendental.show_man_teeth"
    bl_label = "Show Mandibular Teeth"
    bl_options = {'REGISTER','UNDO'}
    
    show_master = bpy.props.BoolProperty(default = False)
    
    def execute(self, context):
        for ob in context.scene.objects:
            if ob.name.startswith('3') or ob.name.startswith('4'):
                ob.hide = False
            
            elif ('lower' in ob.name or 'Lower' in ob.name) and self.show_master:
                ob.hide = False
            elif ('mand' in ob.name or 'Mand' in ob.name) and self.show_master:
                ob.hide = False
            else:
                ob.hide = True              
        return {'FINISHED'}
    
#TODO update for tooth numbering     
class OPENDENTAL_OT_right_view(bpy.types.Operator):
    '''Will hide all non right tooth objects'''
    bl_idname = "opendental.show_right_teeth"
    bl_label = "Show Right Teeth"
    bl_options = {'REGISTER','UNDO'}
    
    def execute(self, context):
        for ob in context.scene.objects:
            if ob.name.startswith('1') or ob.name.startswith('4'):
                ob.hide = False
            else:
                ob.hide = True              
        return {'FINISHED'}

#TODO update for tooth numbering     
class OPENDENTAL_OT_left_view(bpy.types.Operator):
    '''Will hide all non left toot objects'''
    bl_idname = "opendental.show_left_teeth"
    bl_label = "Show Left Teeth"
    bl_options = {'REGISTER','UNDO'}
    
    def execute(self, context):
        for ob in context.scene.objects:
            if ob.name.startswith('2') or ob.name.startswith('3'):
                ob.hide = False
            else:
                ob.hide = True              
        return {'FINISHED'}

       
def register():
    #bpy.utils.register_class(OPENDENTAL_OT_mandibular_view)
    #bpy.utils.register_class(OPENDENTAL_OT_maxillary_view)
    #bpy.utils.register_class(OPENDENTAL_OT_left_view)
    #bpy.utils.register_class(OPENDENTAL_OT_right_view)
    bpy.utils.register_class(OPENDENTAL_OT_add_bone_roots)
    #bpy.utils.register_class(OPENDENTAL_OT_fast_label_teeth)
    bpy.utils.register_class(OPENDENTAL_OT_adjust_roots)
    bpy.utils.register_class(OPENDENTAL_OT_setup_root_parenting)
    bpy.utils.register_class(OPENDENTAL_OT_set_treatment_keyframe)
    bpy.utils.register_class(OPENDENTAL_OT_confirm_transforms_for_teeth)
    bpy.utils.register_class(OPENDENTAL_OT_empties_to_armature)

    
    
    
def unregister():
    #bpy.utils.unregister_class(OPENDENTAL_OT_mandibular_view)
    #bpy.utils.unregister_class(OPENDENTAL_OT_maxillary_view)
    #bpy.utils.unregister_class(OPENDENTAL_OT_left_view)
    #bpy.utils.unregister_class(OPENDENTAL_OT_right_view)
    bpy.utils.unregister_class(OPENDENTAL_OT_add_bone_roots)
    #bpy.utils.unregister_class(OPENDENTAL_OT_fast_label_teeth)
    bpy.utils.unregister_class(OPENDENTAL_OT_setup_root_parenting)
    bpy.utils.unregister_class(OPENDENTAL_OT_set_treatment_keyframe)
    bpy.utils.unregister_class(OPENDENTAL_OT_confirm_transforms_for_teeth)
    bpy.utils.unregister_class(OPENDENTAL_OT_empties_to_armature)
    bpy.utils.unregister_class(OPENDENTAL_OT_adjust_roots)


    
if __name__ == "__main__":
    register()