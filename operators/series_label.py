'''
Created on Dec 15, 2020

@author: Patrick
'''


import time
import math
import os

import bpy
import blf
import bmesh
from mathutils import Vector, Matrix, Quaternion
from bpy_extras.view3d_utils import location_3d_to_region_2d


from ..common.utils import get_settings

from d3guard.curve import LineDrawer, TextLineDrawer
from d3guardl.textbox import TextBox
from d3guard.common_drawing import outline_region
from d3guard.bmesh_fns import join_objects, bmesh_loose_parts, new_bmesh_from_bmelements, join_bmesh



        

t_topo = {}
t_topo['FACES'] = 56
t_topo['EDGES'] = 113
t_topo['VERTS'] = 58
        

def convexify_list(L_cos, direction):
    print('convexify list')
    n = len(L_cos)
    new_list = L_cos.copy()
    
    for i in range(1, n-1):
        l0 = L_cos[i]
        l_m1 = L_cos[i-1]
        l_p1 = L_cos[i+1]
        mid = .5 * (l_m1 + l_p1)
        
        delta = mid - l0
        
        if delta.dot(direction) > 0:
            new_list[i] = mid

    return new_list


def round_corner(r, segments, corner_type = 'UR'):
    '''
    radius - radius of corner Float
    segments - number of segments Int
    coner - string in 'UR', 'UL', 'LL', 'LR'
    '''
    
    if corner_type == 'UR': theta_0 = 0
    elif corner_type == 'UL': theta_0 = math.pi/2
    elif corner_type == 'LL': theta_0 = math.pi
    elif corner_type == 'LR': theta_0 = 3/2 * math.pi
    else: theta_0 = 0
    
    d_theta = (math.pi/2)/segments
    
    verts = []
    for i in range(0, segments + 1):
        verts += [r * Vector(((math.cos(theta_0 + i*d_theta), math.sin(theta_0 + i*d_theta), 0)))]
                      
    return verts
    
    
def round_box_grid(width, height, r_corner, corner_segments, x_res, y_res, make_bmesh = True):
    '''
    width = width of box
    height = height of box
    r_corner = corner radius
    corner_segments = number of steps of the corner
    x_res = target resolution size, will be rounded to create even number of segments
    y_res = target resolution size, will be rounded to create even number of segments
    '''
    
    #prevent over beveling
    r_corner = min(r_corner, .9 * width/2)
    r_corner = min(r_corner, .9 * height/2)
    
    #TODO prevent under tesselating
    nx = math.floor(max((width - 2 * r_corner)/x_res, 4))
    ny = math.floor(max((height - 2 * r_corner)/y_res, 4))
    
    dx = (width - 2 * r_corner)/nx
    dy = (height - 2 * r_corner)/ny
    
    
    bme = bmesh.new()
    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()

    bmverts = []
    bmfaces = []
    
    corner_mxs = {}
    corner_mxs['UR'] = Matrix.Translation(Vector((width/2 - r_corner, height/2 - r_corner, 0)))
    corner_mxs['UL'] = Matrix.Translation(Vector((-width/2 + r_corner, height/2 - r_corner, 0)))
    corner_mxs['LL'] = Matrix.Translation(Vector((-width/2 + r_corner, -height/2 + r_corner, 0)))
    corner_mxs['LR'] = Matrix.Translation(Vector((width/2 - r_corner, -height/2 + r_corner, 0)))
    
    
    g_dict = {}
    
    for corner in ['UR','UL','LL','LR']:
        corner_bmverts = []
        c_verts = round_corner(r_corner, corner_segments, corner_type = corner)
        mx = corner_mxs[corner]
        for v in c_verts:
            corner_bmverts += [bme.verts.new(mx * v)]
            
        #corner_bmverts += [bme.verts.new(mx * Vector((0,0,0)))]
        g_dict[corner] = corner_bmverts
        #bmfaces += [bme.faces.new(corner_bmverts)]
        bmverts += corner_bmverts
    
    
    v0 = Vector((-width/2 + r_corner, -height/2 + r_corner, 0))
    
    grid_verts = []
    for j in range(0, ny+1):
        for i in range(0,nx+1):
            grid_verts += [bme.verts.new(v0 + Vector((i*dx, j * dy, 0)))]
            
    g_dict['grid_verts'] = grid_verts       
    
    
    g_dict['top_side'] = [g_dict['UL'][0]] + \
                        [bme.verts.new(Vector((-width/2 + r_corner + i * dx, height/2, 0))) for i in range(1, nx)] + \
                        [g_dict['UR'][corner_segments]]
                        
    g_dict['bottom_side'] = [g_dict['LL'][corner_segments]] + \
                            [bme.verts.new(Vector((-width/2 + r_corner + i * dx, -height/2, 0))) for i in range(1, nx)] +\
                            [g_dict['LR'][0]]
                            
    g_dict['left_side'] = [g_dict['LL'][0]] +\
                            [bme.verts.new(Vector((-width/2, -height/2 + r_corner + i * dy, 0))) for i in range(1, ny)] +\
                            [g_dict['UL'][corner_segments]]
                            
    g_dict['right_side'] = [g_dict['LR'][corner_segments]] +\
                            [bme.verts.new(Vector((width/2, -height/2 + r_corner +  i * dy, 0))) for i in range(1, ny)] +\
                            [g_dict['UR'][0]]
    
    bme.verts.ensure_lookup_table()
    
    
    #upper right corner
    bme.faces.new(g_dict['UR'] + [g_dict['grid_verts'][-1]])
    #upper left corner
    bme.faces.new(g_dict['UL'] + [g_dict['grid_verts'][len(grid_verts) - nx -1]])
    #lower left corner
    bme.faces.new(g_dict['LL'] + [g_dict['grid_verts'][0]])
    #lower right corner
    bme.faces.new(g_dict['LR'] + [g_dict['grid_verts'][nx]])
    
    #middle grid
    for j in range(0, ny):
        for i in range(0,nx):
            v0 = grid_verts[j * (nx+1) + i]
            v1 = grid_verts[j * (nx+1) + i + 1]
            v2 = grid_verts[(j+1)*(nx +1) + i + 1]
            v3 = grid_verts[(j+1)*(nx +1) + i]
            bme.faces.new([v0, v1, v2, v3])
    
    #top side
    n0 = len(grid_verts) - nx -1
    for i in range(0, nx):
        v0 = grid_verts[n0 + i]
        v1 = grid_verts[n0 + i + 1]
        v2 = g_dict['top_side'][i + 1]
        v3 = g_dict['top_side'][i]
        
        bme.faces.new([v0,v1,v2,v3])
    
    #bottom_side
    for i in range(0, nx):
        v3 = grid_verts[i]
        v2 = grid_verts[i + 1]
        v1 = g_dict['bottom_side'][i + 1]
        v0 = g_dict['bottom_side'][i]
        
        bme.faces.new([v0,v1,v2,v3])
        
        
    #left side
    for i in range(0, ny):
        v0 = g_dict['left_side'][i]
        v1 = g_dict['grid_verts'][i * (nx +1)]
        v2 = g_dict['grid_verts'][(i+1) * (nx +1)]
        v3 = g_dict['left_side'][i+1]
        
        bme.faces.new([v0,v1,v2,v3])
    
    
    #right side
    for i in range(0, ny):
        v1 = g_dict['right_side'][i]
        v0 = g_dict['grid_verts'][nx + i * (nx+1)]
        v3 = g_dict['grid_verts'][nx + (i+1) *(nx+1)]
        v2 = g_dict['right_side'][i+1]
        
        bme.faces.new([v0,v1,v2,v3])
    
    return bme, g_dict

def is_convex(bmv):
    '''
    check simple concavity of vertex
    '''
    
    convex = True
    deltas = []
    for ed in bmv.link_edges:
        v = ed.other_vert(bmv)
        
        vec = v.co - bmv.co
        depth = vec.dot(bmv.normal)
        if depth < 0: 
            convex = True
            deltas += [depth * bmv.normal]
    
    return convex, deltas

def split_solidify_remesh(context, txt_ob, solidify_depth = 1, remesh_level = 5):
    '''
    convert text object to mesh
    solidify it
    remesh it by parts
    '''
    
    #we will save this mesh to keep as the final mesh
    final_me = txt_ob.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        
    bme = bmesh.new()
    bme.from_mesh(final_me)
    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    
    #bullshit it doesn't work
    #print('dissolving degeneration')
    #ret = bmesh.ops.dissolve_degenerate(bme, dist = .001, edges = bme.edges[:])
    #print(ret)
    
    
    bmesh.ops.beautify_fill(bme, faces = bme.faces[:], edges = bme.edges[:])
    characters = bmesh_loose_parts(bme, selected_faces = None, max_iters = 200)
    
    
    start = time.time()
    
    temp_obs = []  #all objects to be deleted at end
    temp_meshes = []
    
    
    remesh_obs = []
    remesh_bmes = []
    
    for ch in characters:
        bme_ch = new_bmesh_from_bmelements(ch)
        
        
        bme_ch.verts.ensure_lookup_table()
        bme_ch.edges.ensure_lookup_table()
        bme_ch.faces.ensure_lookup_table()
        
        t_me = bpy.data.meshes.new('Dummy')
        t_ob = bpy.data.objects.new('Dummy', t_me)
        bme_ch.to_mesh(t_me)
        
        t_me.update()
        context.scene.objects.link(t_ob)
        
        smod = t_ob.modifiers.new('Solidify', type = 'SOLIDIFY')
        smod.offset = 0
        smod.thickness = solidify_depth
        
        rmod = t_ob.modifiers.new('Remesh', type = 'REMESH')
        rmod.octree_depth = remesh_level
        
        bme_ch.free()
        remesh_obs.append(t_ob)
    
    context.scene.update()
    for ob in remesh_obs:
        bme_re = bmesh.new()
        bme_re.from_object(ob, context.scene)
        
        remesh_bmes.append(bme_re)
        
        bme_re.verts.ensure_lookup_table()
        bme_re.faces.ensure_lookup_table()
        
        ob.modifiers.clear()
        context.scene.objects.unlink(ob)
        
        me = ob.data
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)
    
    bme_final = bmesh.new()
    bme_final.verts.ensure_lookup_table()
    for bme_re in remesh_bmes:
        join_bmesh(bme_re, bme_final)
        bme_re.free()
        
    ob_final = bpy.data.objects.new(txt_ob.name + "_mesh", final_me)
    bme_final.to_mesh(final_me)
    final_me.update()
    ob_final.matrix_world = txt_ob.matrix_world
    context.scene.objects.link(ob_final)
    return ob_final

def stencil_text_callback(self, context):  
    self.help_box.draw()
    self.crv.draw(context)
    r,g,b = 1, 1, 1
    outline_region(context.region,(r,g,b,1)) 
    
            
class D3SLEEP_OT_stencil_serial_number(bpy.types.Operator):
    """Click and draw a line to place text on the model"""
    bl_idname = "d3sleep.stencil_serial_number"
    bl_label = "Stencil Serial Number"
    bl_options = {'REGISTER', 'UNDO'}
    
    jaw_mode = bpy.props.EnumProperty(name = 'Jaw', items = (('MAX', 'MAX','MAX'), ('MAND', 'MAND','MAND')), default = 'MAX')
    
    @classmethod
    def poll(cls,context):
        if context.object == None: return False
        if context.object.type != 'MESH': return False
        
        return True
    
    def modal_nav(self, event):
        events_nav = {'MIDDLEMOUSE', 'WHEELINMOUSE','WHEELOUTMOUSE', 'WHEELUPMOUSE','WHEELDOWNMOUSE'} #TODO, better navigation, another tutorial
        handle_nav = False
        handle_nav |= event.type in events_nav

        if handle_nav: 
            return 'nav'
        return ''
    
    def modal_main(self,context,event):
        # general navigation
        nmode = self.modal_nav(event)
        if nmode != '':
            return nmode  #stop here and tell parent modal to 'PASS_THROUGH'

        if event.type == 'MOUSEMOVE':
            
            x, y = event.mouse_region_x, event.mouse_region_y
            self.crv.hover(context, x, y)
            if len(self.crv.screen_pts) != 2:
                self.crv.calc_text_values()
            return 'main'
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            #if len(self.crv.screen_pts) >= 2: return 'main' #can't add more
            
            if len(self.crv.screen_pts) == 0:
                context.window.cursor_modal_set('CROSSHAIR')
            
                #help_txt = "Left Click again to place end of line"
                #self.help_box.raw_text = help_txt
                #self.help_box.format_and_wrap_text()
                
            #if len(self.crv.screen_pts) == 1:
                #help_txt = "Left Click to end the text"
                #self.help_box.raw_text = help_txt
                #self.help_box.format_and_wrap_text()
                
            x, y = event.mouse_region_x, event.mouse_region_y
            
            res = self.crv.click_add_point(context, x,y)
            return 'main'
        
        if event.type == 'B'  and event.value == 'PRESS':
            self.create_and_project_base(context)
            return 'main'            
        
        if event.type == 'P' and event.value == 'PRESS':
            self.create_and_project_text(context)
            return 'main'
        
        
        #if event.type == 'G' and event.value == 'PRESS':
        #    self.crv.project_grid(context, res = 4)
        #    return 'main'
        
        
        if event.type == 'RIGHTMOUSE'  and event.value == 'PRESS':
            
            x, y = event.mouse_region_x, event.mouse_region_y
            
            v3d = context.space_data
            rv3d = v3d.region_3d
            rot = rv3d.view_rotation
            
            X = rot * Vector((1,0,0))
            Y = rot * Vector((0,1,0))
            Z = rot * Vector((0,0,1))
            
            loc, no = self.crv.ray_cast_pt(context, (x,y))
            if loc.length < .0001 and no.length < .0001: return 'main'

            if loc == None: return 'main'
            no_mx = self.crv.snap_ob.matrix_world.inverted().transposed().to_3x3()
            world_no = no_mx * no
            
            
            
            world_no_aligned = world_no - world_no.dot(X) * X
            world_no_aligned.normalize()
            
            angle = world_no_aligned.angle(Z)
            
            if world_no.dot(Y) > 0:
                angle = -1 * angle
            R_mx = Matrix.Rotation(angle, 3, X)
            R_quat = R_mx.to_quaternion()
            rv3d.view_rotation = R_quat * rot
            
            return 'main'
               
        if event.type == 'LEFT_ARROW' and event.value == 'PRESS':
            print('reset old matrix')
            v3d = context.space_data
            rv3d = v3d.region_3d
            rv3d.view_rotation = self.last_view_rot
            rv3d.view_location = self.last_view_loc
            rv3d.view_matrix = self.last_view_matrix
            rv3d.view_distance = self.last_view_distance
            
            rv3d.update()
            return 'main'
        
        if event.type == 'RET' and event.value == 'PRESS':
            if len(self.crv.screen_pts) != 2:
                return 'main'
            
            if not len(self.crv.projected_points):
                self.create_and_project_text(context)
            
            self.finalize_text(context)    
            self.finish(context)
            return 'finish'
            
        elif event.type == 'ESC' and event.value == 'PRESS':
            return 'cancel' 

        return 'main'
    
        
    def modal(self, context, event):
        context.area.tag_redraw()
        
        FSM = {}    
        FSM['main']    = self.modal_main
        FSM['nav']     = self.modal_nav
        
        nmode = FSM[self.mode](context, event)
        
        if nmode == 'nav': 
            return {'PASS_THROUGH'}
        
        if nmode in {'finish','cancel'}:
            #clean up callbacks
            self.bme.free()
            context.window.cursor_modal_restore()
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'FINISHED'} if nmode == 'finish' else {'CANCELLED'}
        
        if nmode: self.mode = nmode
        
        return {'RUNNING_MODAL'}

    def invoke(self,context, event):
        prefs = get_settings()
       
        label_message = '0'
        
        if self.jaw_mode == 'MAX':
            Model = bpy.data.objects.get('Upper Gingiva')
            txt_name = "Serial Text MAX"
            label_name = "Serial Label MAX"
        
        if self.jaw_mode == 'MAND':
            Model = bpy.data.objects.get('Lower Gingiva')
            txt_name = "Serial Text MAND"
            label_name = "Serial Label MAND"
            
                 
        
                
        for ob in bpy.data.objects:
            ob.select = False
            ob.hide = True
            
        Model.select = True
        Model.hide = False
        
        #bpy.ops.view3d.view_selected()
        #get font id
        font_file = ''
        print('THIS IS THE FONT FILE')
        print(font_file)
        if len(font_file) > 0 and os.path.exists(font_file):
            font_id = blf.load(font_file)
        else:
            font_id = 0
        
        if len(font_file) >0 and os.path.exists(font_file):
            #get the font data
            found_font = False
            for f in bpy.data.fonts:
                if f.filepath == font_file:
                    bfont = f
                    found_font = True
            if not found_font:
                bpy.data.fonts.load(font_file)
                for f in bpy.data.fonts:
                    if f.filepath == font_file:
                        bfont = f
        else:
            if len(bpy.data.fonts) >= 1:
                bfont = bpy.data.fonts[0]
            else:
                dummy = bpy.data.curves.new('dummy', type = 'FONT')
                bfont = bpy.data.fonts[0]
                
                
        self.crv = TextLineDrawer(context,snap_type ='OBJECT', snap_object = Model, msg = label_message, f_id = font_id)
        self.use_base = False
        
        #TODO, tweak the modifier as needed
        help_txt = "INTERACTIVE LABEL STENCIL\n\n-  LeftClick and move mouse to define a line across your model \n-  The line will stick to your mouse until you Left Click again\n-  A preview of the text label will follow your line\n  -press 'ENTER' to project the text onto your model and finish the operator.\n\nADVANCED USAGE\n\n-RightMouse in the middle of the label to snap your view perpendicular to the model surface, you may need to adjust the position slightly\n-  You can press 'B' to project a text base onto the obect.  You can then alter your view to inspect the text projection.\n-  You can press 'P' to project the  text onto the object without leaving the operator.  You can then alter your view to inspect the text projection.\n-  LEFT_ARROW key to snap back to the original view, you can then modify your viewing angle and press 'P' again.  When satisfied, press 'ENTER' to finish."
        
        self.help_box = TextBox(context,500,500,300,200,10,20,help_txt)
        self.help_box.snap_to_corner(context, corner = [1,1])

        self.bme= bmesh.new()
        self.bme.from_mesh(Model.data)
        self.ob = Model
        self.base_ob = None
        self.cursor_updated = True
        
        #get new text data and object in the scene
        
        if txt_name not in bpy.data.curves:
            self.txt_crv = bpy.data.curves.new(txt_name, type = 'FONT')
            self.txt_crv.font = bfont
            self.txt_crv_ob = bpy.data.objects.new(txt_name, self.txt_crv)
            context.scene.objects.link(self.txt_crv_ob)
            context.scene.update()
        else:
            self.txt_crv = bpy.data.curves.get(txt_name)
            self.txt_crv.font = bfont
            self.txt_crv_ob = bpy.data.objects.get(txt_name)
            context.scene.update()
            
              
        self.txt_crv_ob.hide = True
        
            
        self.txt_me_data = self.txt_crv_ob.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')    
        
        
        
        if label_name not in bpy.data.objects:
            self.txt_me_ob = bpy.data.objects.new(label_name, self.txt_me_data)
            context.scene.objects.link(self.txt_me_ob)
          
        else:
            self.txt_me_ob = bpy.data.objects.get(label_name)
            self.text_me_ob.data = self.txt_me_data
            
        
        self.txt_crv.align_x = 'LEFT'
        self.txt_crv.align_y = 'BOTTOM'    
        self.txt_crv.body = label_message  #TODO hook up to property
        
        
        context.space_data.show_manipulator = False
        
        self.mode = 'main'
        self._handle = bpy.types.SpaceView3D.draw_handler_add(stencil_text_callback, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self) 
        
        v3d = context.space_data
        rv3d = v3d.region_3d
        
        self.last_view_rot = rv3d.view_rotation
        self.last_view_loc = rv3d.view_location
        self.last_view_matrix = rv3d.view_matrix.copy()
        self.last_view_distance = rv3d.view_distance
        
        
        return {'RUNNING_MODAL'}

    def create_and_project_base(self, context):
        
        self.crv.project_line(context, res = 20)
        
        if len(self.crv.projected_points) == 0:
            return
        
        self.use_base = True
        v3d = context.space_data
        rv3d = v3d.region_3d
        self.last_view_rot = rv3d.view_rotation
        self.last_view_loc = rv3d.view_location
        self.last_view_matrix = rv3d.view_matrix.copy()
        self.last_view_distance = rv3d.view_distance

        
        width = (self.crv.projected_points[-1] - self.crv.projected_points[0]).length
        y_x = self.crv.text_dimensions[1]/self.crv.text_dimensions[0]
        height = y_x * width
        
        base_bme, g_dict = round_box_grid(width+2, height+2, 1, 12, .25, .25, make_bmesh=True)
        base_ob = bpy.data.objects.get('Text Base ' + self.jaw_mode)
        
        if base_ob == None:
            base_me = bpy.data.meshes.new('Text Base ' + self.jaw_mode)
            base_ob = bpy.data.objects.new('Text Base ' + self.jaw_mode,base_me)
            context.scene.objects.link(base_ob)
            base_bme.to_mesh(base_me)
            
            mod = base_ob.modifiers.new('Remesh', type = 'REMESH')
            mod.mode = 'SMOOTH'
            mod.octree_depth = 7
            
            mod2 = base_ob.modifiers.new('Smooth', type = 'SMOOTH')
            mod2.factor = 1
            mod2.iterations = 10
            
        else:
            base_ob = bpy.data.objects.get('Text Base ' + self.jaw_mode)
            
        base_ob.parent = self.ob    
        base_ob.hide = False    
        loc = self.crv.projected_points[0]
        
        T = Matrix.Translation(loc)
       
        R = self.crv.calc_matrix(context)
        loc_cube = self.crv.projected_points[10] + R * Vector((0,1,0)) * height/2
        Tcube = Matrix.Translation(loc_cube)
        
        mx_pad = Tcube * R
        imx_pad = mx_pad.inverted()
        base_ob.matrix_world = mx_pad 
        

        for v in base_bme.verts:
            point_2d = location_3d_to_region_2d(context.region, context.space_data.region_3d, mx_pad * v.co)
            loc, no = self.crv.ray_cast_pt(context, point_2d)
            
            v.co = imx_pad * self.crv.snap_ob.matrix_world * loc + .25 * Vector((0,0,1))
               
        g_dict = bmesh.ops.extrude_face_region(base_bme, geom = base_bme.faces[:])
        vs  = [ele for ele in g_dict['geom'] if isinstance(ele, bmesh.types.BMVert)]
        for v in vs:
            v.co -= Vector((0,0,1))
            
        out_geom = bmesh.ops.convex_hull(base_bme, input = base_bme.verts[:], use_existing_faces = True)
        
        unused_geom = out_geom['geom_interior']
        
        del_v = [ele for ele in unused_geom if isinstance(ele, bmesh.types.BMVert)]
        del_e = [ele for ele in unused_geom if isinstance(ele, bmesh.types.BMEdge)]
        del_f = [ele for ele in unused_geom if isinstance(ele, bmesh.types.BMFace)]
        
        #these must go
        bmesh.ops.delete(base_bme, geom = del_v, context = 1)
        #bmesh.ops.delete(bme, geom = del_e, context = )
        bmesh.ops.delete(base_bme, geom = del_f, context = 5)
        
        
        base_bme.to_mesh(base_ob.data)
        base_ob.data.update()
        
        self.base_ob = base_ob
        return True
    
    
    def create_and_project_text(self, context):
        
        prefs = get_settings()
        
        if self.use_base:
            base_ob = bpy.data.objects.get('Text Base ' + self.jaw_mode)
            if 'Base Union' not in self.crv.snap_ob.modifiers:
                mod = self.crv.snap_ob.modifiers.new('Base Union', type = 'BOOLEAN')
                mod.operation = 'UNION'
                mod.object = base_ob
            context.scene.update() #update the boolean so re-raycasting works
            base_ob.hide = True
            
        self.crv.project_line(context, res = 20)
        
        if len(self.crv.projected_points) == 0:
            return
        
        v3d = context.space_data
        rv3d = v3d.region_3d
        self.last_view_rot = rv3d.view_rotation
        self.last_view_loc = rv3d.view_location
        self.last_view_matrix = rv3d.view_matrix.copy()
        self.last_view_distance = rv3d.view_distance
            
        txt_ob = self.txt_crv_ob
        txt_ob.matrix_world = Matrix.Identity(4)
        
        #base_ob = bpy.data.objects.get('Text Base')
        #if base_ob == None:
        #    base_me = bpy.data.meshes.new('Text Base')
        #    base_ob = bpy.data.objects.new('Text Base',base_me)
        #    context.scene.objects.link(base_ob)
        #    base_bme = bmesh.new()
        #    base_bme.from_mesh(base_me)
        #    bmesh.ops.create_cube(base_bme)
        #    base_bme.to_mesh(base_me)
        #    base_bme.free()
            
        bbox = txt_ob.bound_box[:]
        bbox_vs = []
        for v in bbox:
            bbox_vs += [Vector(v)]
        
        v_max_x= max(bbox_vs, key = lambda x: x[0])
        v_min_x = min(bbox_vs, key = lambda x: x[0])
        v_max_y= max(bbox_vs, key = lambda x: x[1])
        v_min_y = min(bbox_vs, key = lambda x: x[1])
        
        X_dim = v_max_x[0] - v_min_x[0]
        Y_dim = v_max_y[1] - v_min_y[1]
        
        print("The text object has %f length" % X_dim)
        
        #really need a path and bezier class for this kind of stuff
        proj_path_len = 0
        s_v_map = {}
        s_v_map[0.0] = 0
        for i in range(0,19):
            seg = self.crv.projected_points[i + 1] - self.crv.projected_points[i]
            proj_path_len += seg.length
            s_v_map[proj_path_len] = i+1
        
        
        def find_path_len_v(s_len):
            '''
            Get the interpolated position along a polypath
            at a given length along the path.
            '''
            p_len = 0
            
            for i in range(0, 19):
                seg = self.crv.projected_points[i + 1] - self.crv.projected_points[i]
                p_len += seg.length
                
                if p_len > s_len:
                    delta = p_len - s_len
                    vec = seg.normalized()
                    
                    v = self.crv.projected_points[i] + delta * vec
        
                    return v, vec
            return self.crv.projected_points[i+1], seg.normalized()
        
        #place the text object on the path
        s_factor = proj_path_len/X_dim
        
        cube_factor_x = proj_path_len + 2
        cube_factor_y = s_factor * Y_dim + 2
        
        S = Matrix.Scale(s_factor, 4)
        #S_cube = Matrix.Scale(1, 4)
        #S_cube[0][0] = cube_factor_x
        #S_cube[1][1] = cube_factor_y
        loc = self.crv.projected_points[0]
        
        T = Matrix.Translation(loc)
       
        R = self.crv.calc_matrix(context)
        #loc_cube = self.crv.projected_points[10] + R * Vector((0,1,0)) * Y_dim
        #Tcube = Matrix.Translation(loc_cube)
        
        txt_ob.matrix_world = T * R * S
        #base_ob.matrix_world = Tcube * R * S_cube    
        me = txt_ob.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        
        bme = bmesh.new()
        bme.from_mesh(me)
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        #bullshit it doesn't work
        #print('dissolving degeneration')
        #ret = bmesh.ops.dissolve_degenerate(bme, dist = .001, edges = bme.edges[:])
        #print(ret)
        
        print('beauty faces')
        bmesh.ops.beautify_fill(bme, faces = bme.faces[:], edges = bme.edges[:])
        
        
        characters = bmesh_loose_parts(bme, selected_faces = None, max_iters = 200)
        
        #parameterize each character based on it's center of mass in the x direction
        #eg, it's length down the curve path
        
        ts = []
        path_pts = []
        for fs in characters:
            vs = set()
            com = Vector((0,0,0))
            for f in fs:
                vs.update(f.verts[:])
            for v in vs:
                com += v.co
            com *= 1/len(vs)
            
            world_com = T * R * S * com
            point_2d = location_3d_to_region_2d(context.region, context.space_data.region_3d, world_com)
            loc, no = self.crv.ray_cast_pt(context, point_2d)
            
            world_projected_com = self.crv.snap_ob.matrix_world * loc
            
            #self.crv.projected_points += [world_projected_com]
            
            world_delta = world_projected_com - world_com
            
            local_delta = (R * S).inverted().to_3x3() * world_delta
            
            
            ts += [com[0]/X_dim]
            
            path_pt, path_tan = find_path_len_v(com[0]/X_dim * proj_path_len)
            
            local_tan = (R * S).inverted().to_3x3() * path_tan
            
            angle_dif = Vector((1,0,0)).angle(local_tan)
            
            if local_tan.cross(Vector((1,0,0))).dot(Vector((0,1,0))) < 0:
                angle_dif *= -1
                
            r_prime = Matrix.Rotation(-angle_dif, 4, 'Y')
            print('The angle difference is %f' % angle_dif)
            #translate to center
            for v in vs:
                v.co -= com
                
                v.co = r_prime * v.co
                
                v.co += com + local_delta    
                
        #text mesh
        
        bme.to_mesh(me)
        self.txt_me_ob.data = me
        
        if self.txt_me_data != None:
            self.txt_me_data.user_clear()
            bpy.data.meshes.remove(self.txt_me_data)
            
        self.txt_me_data = me
        
        self.txt_me_ob.matrix_world = T * R * S
        bme.free()
        
        if 'Solidify' not in self.txt_me_ob.modifiers:
            mod = self.txt_me_ob.modifiers.new('Solidify',type = 'SOLIDIFY')
            mod.offset = 0.001
        
        else:
            mod = self.txt_me_ob.modifiers.get('Solidify')
            
        mod.thickness = 2 * prefs.text_emboss_depth * 1/s_factor #TODO put as setting
        
        return True
    
    
    def finalize_text(self,context):
        
        context.scene.objects.unlink(self.txt_crv_ob)
        bpy.data.objects.remove(self.txt_crv_ob)
        bpy.data.curves.remove(self.txt_crv)
        
        
        if self.use_base:
            mod = self.ob.modifiers.get('Base Union')
            self.ob.modifiers.remove(mod)
            imx = self.ob.matrix_world.inverted()
            
            
            bme_base = bmesh.new()
            bme_base.from_object(self.base_ob, context.scene)
            bme_base.transform(self.base_ob.matrix_world)
            bme_base.transform(imx)
            
            bme_base.from_mesh(self.ob.data)  #read in the shell data
            bme_base.to_mesh(self.ob.data)  #push the combined object back in
            context.scene.objects.unlink(self.base_ob)
            me = self.base_ob.data
            bpy.data.objects.remove(self.base_ob)
            bpy.data.meshes.remove(me)
        return
        
        
            
    def finish(self, context):
        #settings = get_settings()
        context.window.cursor_modal_restore()
        #tracking.trackUsage("D3Splint:StencilText",None)
        


    
def register():
    bpy.utils.register_class(D3SLEEP_OT_stencil_serial_number)

   
def unregister():
    bpy.utils.unregister_class(D3SLEEP_OT_stencil_serial_number)