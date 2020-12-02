'''
Created on May 18, 2018

@author: Patrick
'''
import math

import bpy
import bmesh
from mathutils import Vector, Matrix

from ..subtrees.geometry_utils.transformations import r_matrix_from_principal_axes




#todo load/save to json
button_presets = {'preset_premolar' : {"wi": 4.0, "wg" : 4.0, "hg" : 1.5,"hi" : 1.5, "dig": 2.5,
                "theta_i": 10.0, "theta_g":10.0, "theta_m":10.0, "theta_d":10.0, "theta_warp":0.0, "theta_curve": 35},

            'vertical_bar_small' : {"wi": 2.0, "wg" : 2.0, "hg" : 1.5,"hi" : 1.5, "dig": 3.5,
                "theta_i": 10.0, "theta_g":10.0, "theta_m":10.0, "theta_d":10.0, "theta_warp":0.0, "theta_curve": 25},
            'vertical_bar_med' : {"wi": 2.5, "wg" : 2.5, "hg" : 1.5,"hi" : 1.5, "dig": 4.5,
                "theta_i": 10.0, "theta_g":10.0, "theta_m":10.0, "theta_d":10.0, "theta_warp":0.0, "theta_curve": 25},
            'preset_central' : {"wi": 4.0, "wg" : 4.0, "hg" : 1.5,"hi" : 1.5, "dig": 2.5,
                "theta_i": 10.0, "theta_g":10.0, "theta_m":10.0, "theta_d":10.0, "theta_warp":0.0, "theta_curve": 35},
            'preset_square_small' : {"wi": 4.0, "wg" : 4.0, "hg" : 1.5,"hi" : 1.5, "dig": 4.0,
                "theta_i": 10.0, "theta_g":10.0, "theta_m":10.0, "theta_d":10.0, "theta_warp":0.0, "theta_curve": 35},
            'preset_premolar' : {"wi": 4.0, "wg" : 4.0, "hg" : 1.5,"hi" : 1.5, "dig": 2.5,
                "theta_i": 10.0, "theta_g":10.0, "theta_m":10.0, "theta_d":10.0, "theta_warp":0.0, "theta_curve": 35}
            }



attachment_items = []
for key in button_presets.keys():
    attachment_items.append((key, key, ''))

def generate_trap_prizm_bme(wi, wg, hg, hi, dig, theta_i, theta_g, theta_m, theta_d, p_warp, p_curve):
    '''
    wi = incisal width of trapezoid
    wg = ginigval width of trapezoid
    hg = thickness in facial direction at the gingival or button
    hi = thickness in facial direciton at the incisal of button
    dig = the incisal/gingival height of the button
    
    theta_i = angle of the incisal face of the button in radians
    theat_g = angle of the gingival face of the button in radians
    theta_m = angle of the mesial face of the button in radians
    theat_d = angle of the distal face of the button in radians
    
    pb = parabolic curvature factor along the facial
    '''
    bme = bmesh.new()
    
    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    
    v0 = Vector((-wg/2, -dig/2, 0))
    v1 = Vector((wg/2, -dig/2, 0))
    v2 = Vector((wi/2, dig/2, 0))
    v3 = Vector((-wi/2, dig/2, 0))
    v4 = Vector((-wg/2 + math.sin(theta_m)*hg, -dig/2 + math.sin(theta_g)*hg, hg)) #
    v5 = Vector((wg/2 - math.sin(theta_d)*hg, -dig/2 + math.sin(theta_g)*hg, hg))#
    v6 = Vector((wi/2 - math.sin(theta_d)*hi, dig/2 - math.sin(theta_i)*hi, hi))
    v7 = Vector((-wi/2 + math.sin(theta_m)*hi, dig/2 - math.sin(theta_i)*hi, hi))
    
    V0 = bme.verts.new(v0)
    V1 = bme.verts.new(v1)
    V2 = bme.verts.new(v2)
    V3 = bme.verts.new(v3)
    V4 = bme.verts.new(v4)
    V5 = bme.verts.new(v5)
    V6 = bme.verts.new(v6)
    V7 = bme.verts.new(v7)
    
    f0 = bme.faces.new((V0,V3,V2,V1))
    f1 = bme.faces.new((V0,V4,V7,V3))
    f2 = bme.faces.new((V1,V5,V4,V0))
    f3 = bme.faces.new((V2,V6,V5,V1))
    f4 = bme.faces.new((V3,V7,V6,V2))
    f5 = bme.faces.new((V4,V5,V6,V7))
    
    bme.faces.ensure_lookup_table()

    bmesh.ops.subdivide_edges(bme, edges = bme.edges[:], cuts = 8, use_grid_fill = True)
    
    
    for v in bme.verts:
        r = abs(v.co[1] + dig/2)
        factor = (r/dig)**(3/2)
        
        print(math.sin(p_warp))
        v.co[0] += factor * math.sin(p_warp) * r
        v.co[1] -= factor * (1 - math.cos(p_warp))* r
    
    
    for v in bme.verts:
        r = abs(v.co[0])
        factor = (r/wg)**(3/2)
        v.co[2] -= factor * math.sin(p_curve) * r
          
    return bme

class D3Tool_OT_composite_attachment_element(bpy.types.Operator):
    """Create a composite attachment located at the 3D cursor"""
    bl_idname = "d3tool.composite_attachment"
    bl_label = "Composite Attachment"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    wi = bpy.props.FloatProperty(default = 2.0, min = 1.0, max = 6.0, description = 'Incisal width')
    wg = bpy.props.FloatProperty(default = 3.0, min = 1.0, max = 6.0, description = 'Gingival widht')
    hg = bpy.props.FloatProperty(default = 2.0, description = 'height at the gingival aspect of the button')
    hi = bpy.props.FloatProperty(default = 2.0, description = 'height at the incisal aspect of the button')
    dig = bpy.props.FloatProperty(default = 4.0, description = 'incisal gingival length of ramp')
    theta_i = bpy.props.IntProperty(default = 7, min = -30, max = 30, description = 'incisal angle of the surface')
    theta_g = bpy.props.IntProperty(default = 7,  min = -30, max = 30, description = 'gingival angle of the surface')
    theta_m =  bpy.props.IntProperty(default = 7,  min = -30, max = 30, description = 'mesial angle of the surface')
    theta_d =  bpy.props.IntProperty(default = 7,  min = -30, max = 30, description = 'distal angle of the surface')
    theta_warp =  bpy.props.IntProperty(default = 0,  min = -30, max = 30, description = 'cruvature of the attachment')
    theta_curve =  bpy.props.IntProperty(default = 10,  min = -45, max = 45, description = 'curvature of the attachment')
    
    @classmethod
    def poll(cls, context):
        
        return True
    def invoke(self, context, event):

        return context.window_manager.invoke_props_dialog(self)
        
    def execute(self, context):
        
        
        #if len(context.scene.odc_splints):
        #    n = context.scene.odc_splint_index
        #    splint = context.scene.odc_splints[n]
        #    if splint.jaw_type == 'MANDIBLE':
        #        R = Matrix.Rotation(math.pi, 4, 'X')
        #    else:
        #        R = Matrix.Identity(4)
        #else:
        
        R = Matrix.Identity(4)
            
        loc = context.scene.cursor_location
        
        
        bme = generate_trap_prizm_bme(self.wi, 
                                      self.wg, 
                                      self.hg, 
                                      self.hi, 
                                      self.dig, 
                                      math.pi * self.theta_i/180, 
                                      math.pi * self.theta_g/180,  
                                      math.pi * self.theta_m/180,  
                                      math.pi * self.theta_d/180,
                                      math.pi * self.theta_warp/180,
                                      math.pi * self.theta_curve/180)
        
        
    
        me = bpy.data.meshes.new('Composite Button')
        ob = bpy.data.objects.new('Composite Button', me)
        context.scene.objects.link(ob)
        
        T = Matrix.Translation(loc)
        ob.matrix_world = T * R
        
        b1 = ob.modifiers.new('Subdivision Surface', type = 'SUBSURF')
        b1.levels = 2

        #rm = ob.modifiers.new('Remesh', type = 'REMESH')
        #rm.octree_depth = 6
        #rm.mode = 'SMOOTH'
        
        #mat = bpy.data.materials.get("Attahcment Material")
        #if mat is None:
        #    # create material
        #    mat = bpy.data.materials.new(name="Attachment Material")
        #    mat.diffuse_color = get_settings().def_splint_color
        #    mat.use_transparency = True
        #    mat.transparency_method = 'Z_TRANSPARENCY'
        #    mat.alpha = .4
        
        #if mat.name not in ob.data.materials:
        #    ob.data.materials.append(mat)
            
            
        ob['wi'] =  self.wi
        ob['wg'] = self.wg
        ob['hg'] = self.hg
        ob['hi'] = self.hi
        ob['dig'] = self.dig
        ob['theta_i'] = self.theta_i
        ob['theta_g'] =  self.theta_g
        ob['theta_m'] = self.theta_m
        ob['theta_d'] = self.theta_d
        ob['theta_warp'] = self.theta_warp   
        ob['theta_curve'] = self.theta_curve
                               
        bme.to_mesh(me)
        bme.free()
       
        for ob in bpy.data.objects:
            ob.select = False
            
        ob.select = True
        context.scene.objects.active = ob
        if context.space_data.type == 'VIEW_3D':
            context.space_data.show_manipulator = True
            context.space_data.transform_manipulators = {'TRANSLATE','ROTATE'}
            context.space_data.transform_orientation = 'LOCAL'
                 
        return {'FINISHED'}
    


def check(sefl,context):
    return True
    
class D3Tool_OT_composite_attachment_on_tooth(bpy.types.Operator):
    """Create a composite attachment located at the 3D cursor"""
    bl_idname = "d3tool.composite_attachment_tooth"
    bl_label = "Composite Attachment 2"
    bl_options = {'REGISTER', 'UNDO'}
    
    use_preset = bpy.props.BoolProperty(default = False)
    button_preset = bpy.props.EnumProperty(name = 'Attachment Preset', items = attachment_items)
    
    wi = bpy.props.FloatProperty(default = 2.0, min = 1.0, max = 6.0, description = 'Incisal width')
    wg = bpy.props.FloatProperty(default = 3.0, min = 1.0, max = 6.0, description = 'Gingival widht')
    hg = bpy.props.FloatProperty(default = 2.0, description = 'height at the gingival aspect of the button')
    hi = bpy.props.FloatProperty(default = 2.0, description = 'height at the incisal aspect of the button')
    dig = bpy.props.FloatProperty(default = 4.0, description = 'incisal gingival length of ramp')
    theta_i = bpy.props.IntProperty(default = 7, min = -30, max = 30, description = 'incisal angle of the surface')
    theta_g = bpy.props.IntProperty(default = 7,  min = -30, max = 30, description = 'gingival angle of the surface')
    theta_m =  bpy.props.IntProperty(default = 7,  min = -30, max = 30, description = 'mesial angle of the surface')
    theta_d =  bpy.props.IntProperty(default = 7,  min = -30, max = 30, description = 'distal angle of the surface')
    theta_warp =  bpy.props.IntProperty(default = 0,  min = -30, max = 30, description = 'cruvature of the attachment')
    theta_curve =  bpy.props.IntProperty(default = 10,  min = -30, max = 30, description = 'cruvature of the attachment')
    
    @classmethod
    def poll(cls, context):
        
        return True
    
    def check(self, context):
        return True
    
    def invoke(self, context, event):

        return context.window_manager.invoke_props_dialog(self)
        
    def execute(self, context):
        
        loc = context.scene.cursor_location
        obs = [ob for ob in bpy.data.objects if 'Convex' in ob.name]
        
        best_ob = min(obs, key = lambda x: (x.location -loc).length)
        mx_ob = best_ob.matrix_world
        imx_ob = mx_ob.inverted()
        mx_norm = imx_ob.transposed().to_3x3()
        
        snap_loc, no, ind, d  = best_ob.closest_point_on_mesh(imx_ob*loc)

        
        Zglobal = mx_norm * no  #by convention, the facial of the tooth points outward
        Yglobal = mx_norm * Vector((0,0,1))  #we want the composite button to point toward the gingiva/apical
        Xglobal = Yglobal.cross(Zglobal)
        Yglobal = Zglobal.cross(Xglobal)
        #Zglobal = Xglobal.cross(Yglobal)
        
        Xglobal.normalize()
        Yglobal.normalize()
        Zglobal.normalize()
        
        R = r_matrix_from_principal_axes(Xglobal, Yglobal, Zglobal).to_4x4()
        
        
        if self.use_preset:
            
            preset_dict = button_presets[self.button_preset]
            
            for key, value in preset_dict.items():
                setattr(self, key, value)
            
        bme = generate_trap_prizm_bme(self.wi, 
                                      self.wg, 
                                      self.hg, 
                                      self.hi, 
                                      self.dig, 
                                      math.pi * self.theta_i/180, 
                                      math.pi * self.theta_g/180,  
                                      math.pi * self.theta_m/180,  
                                      math.pi * self.theta_d/180,
                                      math.pi * self.theta_warp/180,
                                      math.pi * self.theta_curve/180)
        
        
    
        name = 'CB_attach_' + best_ob.name.split('_')[0]
        
        me = bpy.data.meshes.new(name)
        ob = bpy.data.objects.new(name, me)
        context.scene.objects.link(ob)
        
        ob.parent = best_ob
        T = Matrix.Translation(loc - .75 * Zglobal)
        ob.matrix_world = T * R
        
        b1 = ob.modifiers.new('Subdivision Surface', type = 'SUBSURF')
        b1.levels = 2

        #rm = ob.modifiers.new('Remesh', type = 'REMESH')
        #rm.octree_depth = 6
        #rm.mode = 'SMOOTH'
        
        #mat = bpy.data.materials.get("Attahcment Material")
        #if mat is None:
        #    # create material
        #    mat = bpy.data.materials.new(name="Attachment Material")
        #    mat.diffuse_color = get_settings().def_splint_color
        #    mat.use_transparency = True
        #    mat.transparency_method = 'Z_TRANSPARENCY'
        #    mat.alpha = .4
        
        #if mat.name not in ob.data.materials:
        #    ob.data.materials.append(mat)
            
            
        ob['wi'] =  self.wi
        ob['wg'] = self.wg
        ob['hg'] = self.hg
        ob['hi'] = self.hi
        ob['dig'] = self.dig
        ob['theta_i'] = self.theta_i
        ob['theta_g'] =  self.theta_g
        ob['theta_m'] = self.theta_m
        ob['theta_d'] = self.theta_d
        ob['theta_warp'] = self.theta_warp   
        ob['theta_curve'] = self.theta_curve
                               
        bme.to_mesh(me)
        bme.free()
       
        for obj in bpy.data.objects:
            obj.select = False
            
        ob.select = True
        context.scene.objects.active = ob
        if context.space_data.type == 'VIEW_3D':
            context.space_data.show_manipulator = True
            context.space_data.transform_manipulators = {'TRANSLATE','ROTATE'}
            context.space_data.transform_orientation = 'LOCAL'
                 
        return {'FINISHED'}
    
    def draw(self, context):
        row = self.layout.row()
        row.prop(self, "use_preset")
            
        if self.use_preset:
            row = self.layout.row()
            row.prop(self, "button_preset")
        
        else:
            print('draw these other props')
            props = ['wi', 'wg', 'hg', 'hi', 'dig', 'theta_i', 'theta_g', 'theta_m', 'theta_d', 'theta_warp', 'theta_curve']
            for prop in props:
                row = self.layout.row()
                row.prop(self, prop)
                
                
                

def update_button_element(self, context):
    if self.hold_update:
        return
    
    ob = context.object    

    bme = generate_trap_prizm_bme(self.wi, 
                                  self.wg, 
                                  self.hg, 
                                  self.hi, 
                                  self.dig, 
                                  math.pi * self.theta_i/180, 
                                  math.pi * self.theta_g/180,  
                                  math.pi * self.theta_m/180,  
                                  math.pi * self.theta_d/180,
                                  math.pi * self.theta_warp/180,
                                  math.pi * self.theta_curve/180)
    
    

    ob['wi'] =  self.wi
    ob['wg'] = self.wg
    ob['hg'] = self.hg
    ob['hi'] = self.hi
    ob['dig'] = self.dig
    ob['theta_i'] = self.theta_i
    ob['theta_g'] =  self.theta_g
    ob['theta_m'] = self.theta_m
    ob['theta_d'] = self.theta_d
    ob['theta_warp'] = self.theta_warp   
    ob['theta_curve'] = self.theta_curve
                           
    bme.to_mesh(ob.data)
    bme.free()
        
class D3Tool_OT_composite_attachment_edit(bpy.types.Operator):
    """Create a composite attachment located at the 3D cursor"""
    bl_idname = "d3tool.edit_composite_attachment"
    bl_label = "Edit Selected Attachment"
    bl_options = {'REGISTER', 'UNDO'}
    
    hold_update = bpy.props.BoolProperty(default = True, description = 'Pause live update')
    
    wi = bpy.props.FloatProperty(default = 2.0, min = 1.0, max = 6.0, description = 'Incisal width', update = update_button_element)
    wg = bpy.props.FloatProperty(default = 3.0, min = 1.0, max = 6.0, description = 'Gingival widht', update = update_button_element)
    hg = bpy.props.FloatProperty(default = 2.0, description = 'height at the gingival aspect of the button', update = update_button_element)
    hi = bpy.props.FloatProperty(default = 2.0, description = 'height at the incisal aspect of the button', update = update_button_element)
    dig = bpy.props.FloatProperty(default = 4.0, description = 'incisal gingival length of ramp', update = update_button_element)
    theta_i = bpy.props.IntProperty(default = 7, min = -30, max = 30, description = 'incisal angle of the surface', update = update_button_element)
    theta_g = bpy.props.IntProperty(default = 7,  min = -30, max = 30, description = 'gingival angle of the surface', update = update_button_element)
    theta_m =  bpy.props.IntProperty(default = 7,  min = -30, max = 30, description = 'mesial angle of the surface', update = update_button_element)
    theta_d =  bpy.props.IntProperty(default = 7,  min = -30, max = 30, description = 'distal angle of the surface', update = update_button_element)
    theta_warp =  bpy.props.IntProperty(default = 0,  min = -30, max = 30, description = 'cruvature of the attachment', update = update_button_element)
    theta_curve =  bpy.props.IntProperty(default = 10,  min = -30, max = 30, description = 'cruvature of the attachment', update = update_button_element)
    
    @classmethod
    def poll(cls, context):
        
        return True
    def invoke(self, context, event):
        
        ob = context.object
        
        self.wi = ob['wi']
        self.wg = ob['wg']
        self.hg = ob['hg']
        self.hi = ob['hi']
        self.dig = ob['dig']
        self.theta_i = ob['theta_i']
        self.theta_g = ob['theta_g']
        self.theta_m = ob['theta_m'] 
        self.theta_d =  ob['theta_d']
        self.theta_warp =  ob['theta_warp']
        self.theta_curve = ob['theta_curve']

        return context.window_manager.invoke_props_dialog(self)
        
    def execute(self, context):
        
        #done in the updates
                 
        return {'FINISHED'}
    
def register():
    bpy.utils.register_class(D3Tool_OT_composite_attachment_element)
    bpy.utils.register_class(D3Tool_OT_composite_attachment_on_tooth)
    bpy.utils.register_class(D3Tool_OT_composite_attachment_edit)
   
    
def unregister():
    bpy.utils.unregister_class(D3Tool_OT_composite_attachment_element)
    bpy.utils.unregister_class(D3Tool_OT_composite_attachment_on_tooth)
    bpy.utils.unregister_class(D3Tool_OT_composite_attachment_edit)
        