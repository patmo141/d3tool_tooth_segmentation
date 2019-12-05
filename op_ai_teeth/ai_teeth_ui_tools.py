'''
Created on Oct 10, 2015

@author: Patrick

https://blender.stackexchange.com/questions/15172/turn-weight-paintvertex-groups-into-vertex-paint
'''
import bmesh
import bpy
import time
import math

from ..bmesh_fns import edge_loops_from_bmedges_old, ensure_lookup, new_bmesh_from_bmelements, grow_selection
from ..bmesh_fns import partition_faces_between_edge_boundaries, increase_vert_selection, decrease_vert_selection, bmesh_loose_parts_faces, bmesh_loose_parts_verts
from ..bmesh_fns import edge_loops_from_bmedges_old, flood_selection_by_verts, flood_selection_edge_loop, ensure_lookup
from ..bmesh_fns import flood_selection_edge_loop_report

from ..common.utils import get_matrices
from ..common.rays import get_view_ray_data, ray_cast, ray_cast_path, ray_cast_bvh
from ..common.colors import get_random_color

from .ai_teeth_datastructure import InputNetwork, InputPoint, InputSegment, SplineSegment, CurveNode, BMFacePatch

import bgl
from bpy_extras import view3d_utils
from mathutils import Vector, kdtree, Color
from mathutils.geometry import intersect_point_line
from mathutils.bvhtree import BVHTree

from ..common.maths import Point, Direction, XForm
from ..common.bezier import CubicBezierSpline
from ..common.simplify import simplify_RDP
from ..geodesic import geodesic_walk
from ..salience import skeletonize_vert_set
from ..cloud_api.export_upload import *
import uuid

class AITeeth_UI_Tools():
    '''
    Functions/classes helpful with user interactions in polytrim
    '''

    class SketchManager():
        '''
        UI tool for managing sketches made by user.
        * Intermediary between polytrim_states and Network
        '''
        def __init__(self, input_net, spline_net, net_ui_context, network_cutter):
            self.sketch = []
            self.input_net = input_net
            self.spline_net = spline_net
            self.network_cutter = network_cutter
            self.net_ui_context = net_ui_context
            self.stroke_smoothing = 0.75  # 0: no smoothing. 1: no change
            self.sketch_curpos = (0, 0)
            self.bez_data = []
            
        def has_locs(self): return len(self.sketch) > 0
        has_locs = property(has_locs)

        def get_locs(self): return self.sketch

        def reset(self): self.sketch = []

        def add_loc(self, x, y):
            ''' Add's a screen location to the sketch list '''
            self.sketch.append((x,y))

        def smart_add_loc(self, x, y):
            ''' Add's a screen location to the sketch list based on smart stuff '''
            (lx, ly) = self.sketch[-1]
            ss0,ss1 = self.stroke_smoothing ,1-self.stroke_smoothing  #First data manipulation
            self.sketch += [(lx*ss0+x*ss1, ly*ss0+y*ss1)]

        def is_good(self):
            ''' Returns whether the sketch attempt should/shouldn't be added to the InputNetwork '''
            # checking to see if sketch functionality shouldn't happen
            if len(self.sketch) < 5 and self.net_ui_context.ui_type == 'DENSE_POLY': return False
            return True

        def finalize(self, context, start_pnt, end_pnt=None):
            ''' takes sketch data and adds it into the data structures '''

            print('Finalizing sketching', start_pnt, end_pnt)
            if not isinstance(end_pnt, InputPoint) or isinstance(end_pnt, CurveNode):
                end_pnt = None
            if not isinstance(start_pnt, InputPoint) or isinstance(start_pnt, CurveNode):
                prev_pnt = None
            else:
                prev_pnt = start_pnt

            #FINALIZE INPUT NET MODE
            if isinstance(start_pnt, InputPoint):
                for ind in range(0, len(self.sketch) , 5):
                    if not prev_pnt:
                        if self.input_net.num_points == 1: new_pnt = self.input_net.points[0]
                        else: new_pnt = start_pnt
                    else:
                        pt_screen_loc = self.sketch[ind]  #in screen space
                        view_vector, ray_origin, ray_target = get_view_ray_data(context, pt_screen_loc)  #a location and direction in WORLD coordinates
                        #loc, no, face_ind =  ray_cast(self.net_ui_context.ob,self.net_ui_context.imx, ray_origin, ray_target, None)  #intersects that ray with the geometry
                        loc, no, face_ind =  ray_cast_bvh(self.net_ui_context.bvh,self.net_ui_context.imx, ray_origin, ray_target, None)
                        if face_ind != None:
                            new_pnt = self.input_net.create_point(self.net_ui_context.mx * loc, loc, view_vector, face_ind)
                    if prev_pnt:
                        print(prev_pnt)
                        seg = InputSegment(prev_pnt,new_pnt)
                        self.input_net.segments.append(seg)

                        #self.network_cutter.precompute_cut(seg)
                        #seg.make_path(self.net_ui_context.bme, self.input_net.bvh, self.net_ui_context.mx, self.net_ui_context.imx)
                    prev_pnt = new_pnt
                if end_pnt:
                    seg = InputSegment(prev_pnt,end_pnt)
                    self.input_net.segments.append(seg)

            #FINALIZE CURVE NETWORK MODE
            else:
                sketch_3d = []
                other_data = []
                for pt in self.sketch:
                    view_vector, ray_origin, ray_target = get_view_ray_data(context, pt)  #a location and direction in WORLD coordinates
                        #loc, no, face_ind =  ray_cast(self.net_ui_context.ob,self.net_ui_context.imx, ray_origin, ray_target, None)  #intersects that ray with the geometry
                    loc, no, face_ind =  ray_cast_bvh(self.net_ui_context.bvh,self.net_ui_context.imx, ray_origin, ray_target, None)
                    if face_ind != None:
                            sketch_3d += [self.net_ui_context.mx * loc]
                            other_data += [(loc, view_vector, face_ind)]

                feature_inds = simplify_RDP(sketch_3d, .25)  #TODO, sketch threshold

                new_points = []
                new_segs = []
                for ind in feature_inds:
                    if not prev_pnt:
                        if self.spline_net.num_points == 1: new_pnt = self.spline_net.points[0]
                        else: new_pnt = start_pnt
                    else:
                        loc3d = sketch_3d[ind]
                        loc, view_vector, face_ind = other_data[ind]
                        new_pnt = self.spline_net.create_point(loc3d, loc, view_vector, face_ind)
                        new_points += [new_pnt]
                    if prev_pnt:
                        print(prev_pnt)
                        seg = SplineSegment(prev_pnt,new_pnt)
                        self.spline_net.segments.append(seg)
                        new_segs += [seg]
                        #self.network_cutter.precompute_cut(seg)
                        #seg.make_path(self.net_ui_context.bme, self.input_net.bvh, self.net_ui_context.mx, self.net_ui_context.imx)
                    prev_pnt = new_pnt
                if end_pnt:
                    seg = SplineSegment(prev_pnt,end_pnt)
                    self.spline_net.segments.append(seg)
                    new_segs += [seg]
                for p in new_points:
                    p.calc_handles()
                for seg in new_segs:
                    seg.calc_bezier()
                    seg.tessellate()
                    seg.tessellate_IP_error(.01)


        def finalize_bezier(self, context):
            
            stroke3d = []
            for ind in range(0, len(self.sketch) , 5):
                pt_screen_loc = self.sketch[ind]  #in screen space
                view_vector, ray_origin, ray_target = get_view_ray_data(context, pt_screen_loc)  #a location and direction in WORLD coordinates
                    #loc, no, face_ind =  ray_cast(self.net_ui_context.ob,self.net_ui_context.imx, ray_origin, ray_target, None)  #intersects that ray with the geometry
                loc, no, face_ind =  ray_cast_bvh(self.net_ui_context.bvh,self.net_ui_context.imx, ray_origin, ray_target, None)
                if face_ind != None:
                    stroke3d += [self.net_ui_context.mx * loc]
                    
            #print(stroke3d)
            cbs = CubicBezierSpline.create_from_points([stroke3d], .05)
            cbs.tessellate_uniform(lambda p,q:(p-q).length, split=20)
            L = cbs.approximate_totlength_tessellation()
            n = L/2  #2mm spacing long strokes?
            #print(cbs.tessellation)
            
            self.bez_data = []
            for btess in cbs.tessellation:
                self.bez_data += [pt.as_vector() for i,pt,d in btess]


    class PaintBrush():  #TODO replace with widget, this is a coars placeholder
        #active patch?  meaning we are updating a selection
        def __init__(self, net_ui_context, radius=1.5, color=(0.8, 0.1, 0.3), vcolor_name = "patches"):
            self.net_ui_context = net_ui_context
            self.xform = XForm(self.net_ui_context.ob.matrix_world)
            self.radius = radius
            self.brush_color = Color(color)
            #self.brush_rad_pixel = 40
            self.geom_accum = set()  #FACES

            
            
            if not self.net_ui_context.bme.loops.layers.color.get(vcolor_name):
                vcol_layer = self.net_ui_context.bme.loops.layers.color.new(vcolor_name)
            else:
                vcol_layer = self.net_ui_context.bme.loops.layers.color.get(vcolor_name)
                
            self.vcol = vcol_layer
                
            self.points = [(math.cos(math.radians(t)), math.sin(math.radians(t))) for t in range(0,361,10)]

        def ray_hit(self, pt_screen, context):
            view_vector, ray_origin, ray_target = get_view_ray_data(context, pt_screen)  #a location and direction in WORLD coordinates
            return ray_cast_bvh(self.net_ui_context.bvh, self.net_ui_context.imx, ray_origin, ray_target, None)

        def absorb_geom(self, context, pt_screen_loc):
            loc, no, face_ind = self.ray_hit(pt_screen_loc, context)
            if not loc: return

            close_geom = self.net_ui_context.bvh.find_nearest_range(loc, self.radius)
            fs = [self.net_ui_context.bme.faces[ind] for  _,_,ind,_ in close_geom]
            self.color_geom(fs)
            self.geom_accum.update(fs)

        def absorb_geom_geodesic(self, context, pt_screen_loc):
            loc, no, face_ind = self.ray_hit(pt_screen_loc, context)
            if not loc: return

            #can do old mapping if bme has been altered
            seed = self.net_ui_context.bme.faces[face_ind]
            geos, fixed_vs, close, far = geodesic_walk(self.net_ui_context.bme, seed, loc, min_dist=self.radius)
            fs_in = set()
            fs_out = set()
            for v in fixed_vs:
                for f in v.link_faces:
                    if f in fs_in or f in fs_out: continue
                    if all([v in fixed_vs for v in f.verts]):
                        fs_in.add(f)
                    else:
                        fs_out.add(f)

            self.color_geom(fs_in)
            self.geom_accum.update(fs_in)

        def color_geom(self, faces):
            for f in faces:
                for loop in f.loops:
                    loop[self.vcol] = self.brush_color

        def color_all_geom(self):
            self.color_geom(self.geom_accum)

        def draw_postview(self, context, pt_screen):
            loc,no,_ = self.ray_hit(pt_screen, context)
            if not loc: return
            loc = self.xform.l2w_point(loc)
            no = self.xform.l2w_normal(no)
            tr = Vector((0,0,1)) if abs(no.z) < 0.9 else Vector((1,0,0))
            tx = Direction(no.cross(tr))
            ty = Direction(no.cross(tx))
            cr,cg,cb = self.brush_color

            bgl.glDepthRange(0, 0.99999)    # squeeze depth just a bit
            bgl.glDepthMask(bgl.GL_FALSE)   # do not overwrite depth
            bgl.glEnable(bgl.GL_BLEND)
            bgl.glEnable(bgl.GL_DEPTH_TEST)
            bgl.glLineWidth(2.0) # self.drawing.line_width(2.0)
            bgl.glPointSize(3.0) # self.drawing.point_size(3.0)

            ######################################
            # draw in front of geometry

            bgl.glDepthFunc(bgl.GL_LEQUAL)

            bgl.glColor4f(cr, cg, cb, 1.0)       # outer ring
            bgl.glBegin(bgl.GL_LINE_STRIP)
            for mx,my in self.points:
                p = loc + (tx * mx + ty * my) * self.radius
                bgl.glVertex3f(*p)
            bgl.glEnd()

            bgl.glColor4f(cr, cg, cb, 0.1)     # inner ring
            bgl.glBegin(bgl.GL_LINE_STRIP)
            for mx,my in self.points:
                p = loc + (tx * mx + ty * my) * (self.radius * 0.5)
                bgl.glVertex3f(*p)
            bgl.glEnd()

            bgl.glColor4f(1, 1, 1, 0.25)    # center point
            bgl.glBegin(bgl.GL_POINTS)
            bgl.glVertex3f(*loc)
            bgl.glEnd()

            ######################################
            # draw behind geometry (hidden below)

            bgl.glDepthFunc(bgl.GL_GREATER)

            bgl.glColor4f(cr, cg, cb, 0.05)    # outer ring
            bgl.glBegin(bgl.GL_LINE_STRIP)
            for mx,my in self.points:
                p = loc + (tx * mx + ty * my) * self.radius
                bgl.glVertex3f(*p)
            bgl.glEnd()

            bgl.glColor4f(cr, cg, cb, 0.01)   # inner ring
            bgl.glBegin(bgl.GL_LINE_STRIP)
            for mx,my in self.points:
                p = loc + (tx * mx + ty * my) * (self.radius * 0.5)
                bgl.glVertex3f(*p)
            bgl.glEnd()

            ######################################
            # reset to defaults

            bgl.glDepthFunc(bgl.GL_LEQUAL)
            bgl.glDepthMask(bgl.GL_TRUE)
            bgl.glDepthRange(0, 1)




    class GrabManager():
        '''
        UI tool for managing input point grabbing/moving made by user.
        * Intermediary between polytrim_states and Network
        '''
        def __init__(self, input_net, net_ui_context, network_cutter):
            self.net_ui_context = net_ui_context
            self.input_net = input_net
            self.network_cutter = network_cutter

            self.grab_point = None
            self.original_point = None
            self.backup_data = {}
        def in_use(self): return self.grab_point != None
        in_use = property(in_use)

        def initiate_grab_point(self):
            self.grab_point = self.net_ui_context.selected
            self.backup_data =  self.grab_point.duplicate_data()

        def move_grab_point(self,context,mouse_loc):
            ''' Moves location of point'''
            d = self.net_ui_context.hovered_mesh
            n = self.net_ui_context.hovered_near
            
            if d and self.grab_point:
                print(n)
                if n[0] == 'NON_MAN_ED' and len(self.grab_point.link_segments) == 1:
                    imx = self.net_ui_context.imx
                    ed, world_loc = n[1]
                    face = ed.link_faces[0]
                    
                    self.grab_point.set_values(world_loc, imx * world_loc, d["view"], face.index)
                    self.grab_point.bmface = face
                    self.grab_point.seed_geom = ed  #we have ensure it's not a non manifold
                    self.grab_point.bmedge = ed #unused, but will in future
                
                else:                
                    self.grab_point.set_values(d["world loc"], d["local loc"], d["view"], d["face index"])
                    self.grab_point.bmface = self.input_net.bme.faces[d["face index"]]
                    self.grab_point.seed_geom = None  #we have ensure it's not a non manifold
                    self.grab_point.bmedge = None #unused, but will in future
                
                
                #update bezier preview and snap to surface
                if isinstance(self.grab_point, CurveNode):
                    self.grab_point.calc_handles()
                    for seg in self.grab_point.link_segments:
                        seg.is_inet_dirty = True
                        node = seg.other_point(self.grab_point)
                        node.calc_handles()
                        node.update_splines()
                        
        
                    self.snap_splines()
                    
        def snap_splines(self):
            
            #moving one point affects 4 splines
            
            # -----(n-2)========(n-1)=======N========(n+1)=========(n+2)------
            
            segs = set()
            for seg in self.grab_point.link_segments:
                segs.add(seg)
                if not seg.other_point(self.grab_point): continue
                p_other = seg.other_point(self.grab_point)
                for seg1 in p_other.link_segments:
                    segs.add(seg1)
                    
            for update_seg in segs:
                snap_pts = []
                for loc in update_seg.draw_tessellation:
                    snap = self.net_ui_context.closest_world_loc(loc)
                    if snap: snap_pts += [snap]
            
                update_seg.draw_tessellation = snap_pts
                        
        def grab_cancel(self):
            ''' returns variables to their status before grab was initiated '''
            if not self.grab_point: return
            for key in self.backup_data:
                setattr(self.grab_point, key, self.backup_data[key])
            
            if isinstance(self.grab_point, CurveNode):
                self.grab_point.calc_handles()
                for seg in self.grab_point.link_segments:
                    seg.is_inet_dirty = False
                    node = seg.other_point(self.grab_point)
                    node.calc_handles()
                    node.update_splines()
                         
            self.grab_point = None #TODO BROKEN
            return

        def finalize(self, context):
            ''' sets new variables based on new location '''
            if not self.grab_point: return
            
            if isinstance(self.net_ui_context.selected, InputPoint):
                for seg in self.net_ui_context.selected.link_segments:
                    seg.path = []
                    seg.needs_calculation = True
                    seg.calculation_complete = False

            else:
                self.net_ui_context.selected.update_input_point(self.input_net)
                self.net_ui_context.selected.calc_handles()
                for seg in self.net_ui_context.selected.link_segments:
                    node = seg.other_point(self.net_ui_context.selected)
                    node.calc_handles()
                    node.update_splines()
                
                print(len(self.grab_point.link_segments))
                print(self.grab_point.face_index)
                print(self.grab_point.seed_geom)
                
            self.grab_point = None


            return

    class NetworkUIContext():
        '''
        UI tool for storing data depending on where mouse is located
        * Intermediary between polytrim_states and Network
        '''
        def __init__(self, context, ui_type='DENSE_POLY', geometry_mode = 'DESTRUCTIVE'):
            self.context = context
            self.input_net = None
            self.geometry_mode = geometry_mode
            
            
            #### I DONT KNOW THAT THIS NEEDS TO GO IN NET UI CONTEXT ####
            self.ob = context.object
            self.ob.hide = False
            context.scene.render.engine = 'BLENDER_RENDER'
            context.space_data.show_manipulator = False
            context.space_data.viewport_shade = 'SOLID'  #TODO until smarter drawing
            context.space_data.show_textured_solid = True #TODO until smarter patch drawing
            #context.space_data.show_textured_solid = False  #show sculpt mask 
            if "patches" not in bpy.data.materials:
                mat = bpy.data.materials.new("patches")
                mat.use_shadeless = True
                mat.use_vertex_color_paint = True
            else:
                mat = bpy.data.materials.get("patches")
                mat.use_shadeless = True
                mat.use_vertex_color_paint = True
        
            if "patches" not in self.ob.data.materials:
                self.ob.data.materials.append(mat)
                self.ob.material_slots[0].material = mat
            
            
            self.bme = bmesh.new()
            
            #we are going to make destructive edits into a copy of the mesh
            #then at the end, if we are in destructive mode, we delete backup
            #mesh and keep edited mesh, otherwise we delete edited mesh and put
            #backup mesh back in place
            copy_me = self.ob.data.copy()
            self.backup_data = self.ob.data
            self.ob.data = copy_me
            
            self.bme.from_mesh(self.ob.data)    
            ensure_lookup(self.bme)
            start = time.time()
            self.bvh = BVHTree.FromBMesh(self.bme)
            finish = time.time()
            
            print('took %f seconds to build BVH' % (finish-start))
            self.mx, self.imx = get_matrices(self.ob) 
            self.mx_norm = self.imx.transposed().to_3x3() #local directions to global
            self.imx_norm = self.imx.to_3x3() #global direction to local
            
            
            if ui_type not in {'SPARSE_POLY','DENSE_POLY', 'BEZIER'}: self.ui_type = 'SPARSE_POLY'
            else: self.ui_type = ui_type

            self.mouse_loc = None

            self.hovered_mesh = {}

            # TODO: Organize everything below this
            self.selected = None
            self.snap_element = None
            self.connect_element = None
            self.closest_ep = None
            self.hovered_near = [None, -1]

            self.kd = None
            self.non_man_bmverts = []
            self.find_non_man()
            self.non_man_eds = [ed.index for ed in self.bme.edges if not ed.is_manifold]
            self.non_man_ed_loops = edge_loops_from_bmedges_old(self.bme, self.non_man_eds)
        
        
        def inspect_print(self):
            print(self.selected)
            print(self.snap_element)
            print(self.connect_element)
            print(self.closest_ep) 
            print(self.hovered_near)
            
        def update_bvh(self):
            
            start = time.time()
            del self.bvh
            self.bvh = BVHTree.FromBMesh(self.bme)
            finish = time.time()
            
            print('updated BVH in %f seconds' % (finish-start))
                
        def has_non_man(self): return len(self.non_man_bmverts) > 0
        def is_hovering_mesh(self): 
            if self.hovered_mesh: return self.hovered_mesh["face index"] != -1
            return False
        has_non_man = property(has_non_man)
        is_hovering_mesh = property(is_hovering_mesh)

        def closest_world_loc(self, loc):
            local_loc = self.imx * loc
            loc, no, face_ind, d =  self.bvh.find_nearest(local_loc)
            
            if loc:
                return self.mx * loc
            else:
                return None
            
            
        def find_non_man(self):
            non_man_eds = [ed.index for ed in self.bme.edges if not ed.is_manifold]
            non_man_ed_loops = edge_loops_from_bmedges_old(self.bme, non_man_eds)
            non_man_points = []
            for loop in non_man_ed_loops:
                non_man_points += [self.ob.matrix_world * self.bme.verts[ind].co for ind in loop]
                self.non_man_bmverts += [self.bme.verts[ind].index for ind in loop]
            if non_man_points:
                self.kd = kdtree.KDTree(len(non_man_points))
                for i, v in enumerate(non_man_points):
                    self.kd.insert(v, i)
                self.kd.balance()
            else:
                self.kd = None

        def set_network(self, input_net): self.input_net = input_net

        def update(self, mouse_loc):
            self.mouse_loc = mouse_loc
            self.ray_cast_mouse()

            #self.nearest_non_man_loc()

        def ray_cast_mouse_ob(self):
            view_vector, ray_origin, ray_target= get_view_ray_data(self.context, self.mouse_loc)
            loc, no, face_ind = ray_cast(self.ob, self.imx, ray_origin, ray_target, None)
            if face_ind == -1: self.hovered_mesh = {}
            else:
                self.hovered_mesh["world loc"] = self.mx * loc
                self.hovered_mesh["local loc"] = loc
                self.hovered_mesh["normal"] = no
                self.hovered_mesh["face index"] = face_ind
                self.hovered_mesh["view"] = view_vector

        
        def ray_cast_mouse(self):
            view_vector, ray_origin, ray_target= get_view_ray_data(self.context, self.mouse_loc)
            loc, no, face_ind = ray_cast_bvh(self.bvh, self.imx, ray_origin, ray_target, None)
            if face_ind == None: self.hovered_mesh = {}
            else:
                self.hovered_mesh["world loc"] = self.mx * loc
                self.hovered_mesh["local loc"] = loc
                self.hovered_mesh["normal"] = no
                self.hovered_mesh["face index"] = face_ind
                self.hovered_mesh["view"] = view_vector
              
        def nearest_non_man_loc(self):
            '''
            finds nonman edges and verts nearby to cursor location
            '''
            if self.has_non_man and self.hovered_mesh:
                co3d, index, dist = self.kd.find(self.mx * self.hovered_mesh["local loc"])

                #get the actual non man vert from original list
                close_bmvert = self.bme.verts[self.non_man_bmverts[index]] #stupid mapping, unreadable, terrible, fix this, because can't keep a list of actual bmverts
                close_eds = [ed for ed in close_bmvert.link_edges if not ed.is_manifold]
                if len(close_eds) == 2:
                    bm0 = close_eds[0].other_vert(close_bmvert)
                    bm1 = close_eds[1].other_vert(close_bmvert)

                    a0 = bm0.co
                    b   = close_bmvert.co
                    a1  = bm1.co

                    inter_0, d0 = intersect_point_line(self.hovered_mesh["local loc"], a0, b)
                    inter_1, d1 = intersect_point_line(self.hovered_mesh["local loc"], a1, b)

                    region = self.context.region
                    rv3d = self.context.region_data
                    loc3d_reg2D = view3d_utils.location_3d_to_region_2d
                    mouse_v = Vector(self.mouse_loc)

                    screen_0 = loc3d_reg2D(region, rv3d, self.mx * inter_0)
                    screen_1 = loc3d_reg2D(region, rv3d, self.mx * inter_1)
                    screen_v = loc3d_reg2D(region, rv3d, self.mx * b)

                    if screen_0 and screen_1 and screen_v:
                        screen_d0 = (mouse_v - screen_0).length
                        screen_d1 = (mouse_v - screen_1).length
                        screen_dv = (mouse_v - screen_v).length

                        #TODO, decid how to handle when very very close to vertcies
                        if 0 < d0 <= 1 and screen_d0 < 20:
                            self.hovered_near = ['NON_MAN_ED', (close_eds[0], self.mx*inter_0)]
                            return
                        elif 0 < d1 <= 1 and screen_d1 < 20:
                            self.hovered_near = ['NON_MAN_ED', (close_eds[1], self.mx*inter_1)]
                            return
                
                        else:
                            self.hovered_near = [None, (None, None)]
                    else:
                            self.hovered_near = [None, (None, None)]    
            else:
                self.hovered_near = [None, (None, None)]

        def nearest_endpoint(self, mouse_3d_loc):
            def dist3d(ip):
                return (ip.world_loc - mouse_3d_loc).length

            endpoints = [ip for ip in self.input_net.points if ip.is_endpoint]
            if len(endpoints) == 0: return None

            return min(endpoints, key = dist3d)



    def pick_verts_by_salience_color(self, min_threshold = 0.00):
        """Paints a single vertex where vert is the index of the vertex
        and color is a tuple with the RGB values."""
    
        max_threshold = self.mask_threshold
        start = time.time()
        mesh = self.net_ui_context.ob.data 
        
        vcol_layer = mesh.vertex_colors.get("Salience")
        if vcol_layer == None:
            return
        
        bme = self.net_ui_context.bme
        
        
        if "salience" not in bme.verts.layers.float:
            salience_layer = bme.verts.layers.float.new("salience")
        else:
            salience_layer = bme.verts.layers.float["salience"]
        
        if "patches" not in bme.loops.layers.color:
            salience_select_color_layer = bme.loops.layers.color.new("patches")
        else:
            salience_select_color_layer = bme.loops.layers.color["patches"]
        
        
        salience_bake_color_layer = bme.loops.layers.color["Salience"]
        
        to_select = set()  
        for f in bme.faces: 
            for loop in f.loops:
                col = loop[salience_bake_color_layer]
                loop.vert[salience_layer] = min(math.sqrt(col[0]**2 + col[1]**2 + col[2]**2), loop.vert[salience_layer])
                
                if any([(col[0] < max_threshold and col[0] > min_threshold),
                        (col[1] < max_threshold and col[1] > min_threshold),
                        (col[2] < max_threshold and col[2] > min_threshold)]):
                    #loop.vert.select_set(True)  #actually select the vert
                    to_select.add(loop.vert)
                    
                    loop[salience_select_color_layer] = Color((1,.2, .2))  #set the color so that it can be viewed in object mode, yay
                else:
                    loop[salience_select_color_layer] = Color((1,1,1))

        self.salience_verts.update(to_select)

             
        self.net_ui_context.bme.to_mesh(mesh)
        self.net_ui_context.ob.data.update()  #perhaps push the colo?
        
        
        
        #obj.data.vertex_colors.active = vcol
        print('setting the active vertex color')
        
        #select and add color
        if "patches" in mesh.vertex_colors:   
            vcol = mesh.vertex_colors.get("patches")
            mesh.vertex_colors.active = vcol
            for ind, v_color in enumerate(mesh.vertex_colors):
                if v_color == vcol:
                    break
            mesh.vertex_colors.active_index = ind
            mesh.vertex_colors.active = vcol
            vcol.active_render = True
        
        else:
            print('maybe we need to make vcolor first')
        print(mesh.vertex_colors.active)
        finish = time.time()
        print('Filtered Salience by threshold %f seconds' % (finish-start))
    
    def mask_verts_by_salience_color(self, min_threshold = 0.00, max_threshold = .95):
        """Picks all verts that have value between min and max threshold"""
    
        start = time.time()
        mesh = self.net_ui_context.ob.data 
        
        vcol_layer = mesh.vertex_colors.get("Salience")
        if vcol_layer == None:
            return
        
        bme = self.net_ui_context.bme
        bme.verts.ensure_lookup_table()
        mask = bme.verts.layers.paint_mask.verify()
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        salience_bake_color_layer = bme.loops.layers.color["Salience"]
        
        to_select = set()  
        for f in bme.faces: 
            for loop in f.loops:
                col = loop[salience_bake_color_layer]
                if any([(col[0] < max_threshold and col[0] > min_threshold),
                        (col[1] < max_threshold and col[1] > min_threshold),
                        (col[2] < max_threshold and col[2] > min_threshold)]):
                    #loop.vert.select_set(True)  #actually select the vert
                    to_select.add(loop.vert)
                    #loop[salience_select_color_layer] = Color((1,.2, .2))  #set the color so that it can be viewed in object mode, yay
        

        self.salience_verts.update(to_select)

        for v in bme.verts:
            if v in to_select:
                v[mask] = 1.0
            else:
                v[mask] = 0.0
                
             
        bme.to_mesh(mesh)
        mesh.update()  #perhaps push the colo?
        
    
        finish = time.time()
        print('selected and maxked verts in %f seconds' % (finish-start))
        bpy.ops.object.mode_set(mode = 'SCULPT')
              
    def dilate_salience_mask_verts(self):
        
        start = time.time()
        self.salience_verts = increase_vert_selection(self.salience_verts)
        finish = time.time()
        print('Dilated selection on %f seconds' % (finish-start))
        
        bme = self.net_ui_context.bme
        start = time.time()
        mask = bme.verts.layers.paint_mask.verify()
        for v in bme.verts:
            if v in self.salience_verts:
                v[mask] = 1.0
            else:
                v[mask] = 0.0
                
        self.net_ui_context.bme.to_mesh(mesh)
        self.net_ui_context.ob.data.update()  
        
        finish = time.time()
        print('updated paint mask in %f seconds' % (finish-start))
                  
    def dilate_salience_verts(self):
        
        
        #might get smarter and actually record the new verts only
        self.salience_verts = increase_vert_selection(self.salience_verts)

        vcol_layer = self.net_ui_context.bme.loops.layers.color["patches"]
            
        white = Color((1.0,1.0,1.0))
        red = Color((1.0, .2, .2))
        
        start = time.time()
        #let's assume self.salience_verts is now bigger than it was before
        seen_faces = set()
        for v in self.salience_verts:
            for f in v.link_faces:
                if f in seen_faces: continue
                seen_faces.add(f)
                for loop in f.loops:
                    if loop.vert in self.salience_verts:
                        loop[vcol_layer] = red
                    else:
                        loop[vcol_layer] = white
                        
                        
        finish = time.time()
        print('colored the whole bmesh in %f seconds smart method' % (finish-start))
        
        
        start = time.time()
        self.net_ui_context.bme.to_mesh(self.net_ui_context.ob.data)
        finish = time.time()
        print('updated the bmesh in %f secons' % (finish-start))
                  
    def erode_salience_verts(self):
        
        smaller_verts = decrease_vert_selection(self.salience_verts)
        #diff_verts = self.salience_verts - smaller_verts
        
        vcol_layer = self.net_ui_context.bme.loops.layers.color["patches"]
            
        white = Color((1.0,1.0,1.0))
        red = Color((1.0, .2, .2))
        
        start = time.time()
        seen_faces = set()
        for v in self.salience_verts:
            for f in v.link_faces:
                if f in seen_faces: continue
                for loop in f.loops:
                    if loop.vert in smaller_verts:
                        loop[vcol_layer] = red
                    else:
                        loop[vcol_layer] = white
        
        finish = time.time()
        print('took %f seconds to recolor the contrated region' % (finish-start))
        self.salience_verts = smaller_verts                
        self.net_ui_context.bme.to_mesh(self.net_ui_context.ob.data) 
               
    def get_seed_faces(self):
        if len(self.context.object.children) == 0: return [], {}
        
        seed_faces = []
        seed_labels = dict()
        
        #silly naming convention from pick points operator, see "pick_teeth.py"
        name = "seed" + self.context.object.name 
        if len(name) > 10:
            name = name[0:10]
    
        if name in bpy.data.objects:  #make sure the seed object exists
            container = bpy.data.objects.get(name)
            container_mesh = container.data
        
            bme = bmesh.new()
            bme.from_mesh(container_mesh)
            key1 = bme.verts.layers.string.get('label')
            for v in bme.verts:
                
                loc, no, f_ind, d = self.net_ui_context.bvh.find_nearest(v.co)  #assume we packed the verts in local space of the source ob
                seed_face = self.net_ui_context.bme.faces[f_ind]
                seed_faces += [seed_face]
                #custom data layer
                if key1:
                    seed_labels[seed_face] = v[key1].decode()  #instead, possibly create data layer on the source bmesh
    
            self.seed_faces = seed_faces
            self.seed_labels = seed_labels
            print(seed_labels)
            
    def initialize_face_patches_from_seeds(self):
        if "patches" not in self.input_net.bme.loops.layers.color:
            vcol_layer = self.input_net.bme.loops.layers.color.new("patches")
        else:
            vcol_layer = self.input_net.bme.loops.layers.color["patches"]
            
            
        for f in self.seed_faces:
            label = self.seed_labels[f]
            loc = f.calc_center_bounds()
            world_loc  = self.net_ui_context.mx * loc
            
            
            r_color = get_random_color()
        
            new_patch = BMFacePatch(f, loc, world_loc, vcol_layer, r_color, label = label)
            
            initial_patch = grow_selection(self.input_net.bme, [f], max_iters = 10)
            new_patch.patch_faces = initial_patch
            new_patch.color_patch()
            self.network_cutter.face_patches += [new_patch]
    
    def remove_seeds_from_salience(self):
        patch_verts = set()
        
        for patch in self.network_cutter.face_patches:
            for f in patch.patch_faces:
                patch_verts.update(f.verts[:])
        
        
        
        
        vcol_layer = self.net_ui_context.bme.loops.layers.color["patches"]  
        white = Color((1.0,1.0,1.0))
        red = Color((1.0, .2, .2))
        seen_faces = set()
        for v in patch_verts:
            for f in v.link_faces:
                if f in seen_faces: continue
                for loop in f.loops:
                    if loop.vert in patch_verts:
                        loop[vcol_layer] = white
                                
        self.salience_verts.difference_update(patch_verts)
        
        self.net_ui_context.bme.to_mesh(self.net_ui_context.ob.data)
          
    def remove_salience_vert_islands(self, min_size = 1000):
        islands = bmesh_loose_parts_verts(self.net_ui_context.bme, self.salience_verts, max_iters = 2000)
        
        large_islands = set()
        for isl in islands:
            if len(isl) > min_size:
                large_islands.update(isl)
        
        vcol_layer = self.net_ui_context.bme.loops.layers.color["patches"]  
        white = Color((1.0,1.0,1.0))
        red = Color((1.0, .2, .2))    
        seen_faces = set()
        for v in self.salience_verts:
            for f in v.link_faces:
                if f in seen_faces: continue
                for loop in f.loops:
                    if loop.vert in large_islands:
                        loop[vcol_layer] = red  #note, when doing this the other way its very cool
                    else:
                        loop[vcol_layer] = white
                                
       
        
        self.net_ui_context.bme.to_mesh(self.net_ui_context.ob.data)
        self.salience_verts = large_islands
          
    def check_seed_patches_against_skeleton(self):    
        orphan_seeds = []
        patch_to_seed_map = dict()
        multi_seed_patches = []
        
        biggest_patch = max(self.network_cutter.face_patches, key = lambda x: len(x.patch_faces)) #the gingiva
        for f in self.seed_faces:
            print('Checkign seed ' + self.seed_labels[f])
            for patch in self.network_cutter.face_patches:
                if f in patch.patch_faces: 
                    if patch == biggest_patch:
                        orphan_seeds.append(f)
                        print(self.seed_labels[f] + ' is an orpahn')
                        
                    else:
                        if patch in patch_to_seed_map.keys():
                            if patch not in multi_seed_patches: #perhaps a set instead of dict?
                                multi_seed_patches.append(patch)
                            fs = patch_to_seed_map[patch]
                            fs.append(f)
                            patch_to_seed_map[patch] = fs
                        else:  
                            patch_to_seed_map[patch] = [f] #a list in case of multi seeds in one patch
                    
                   
        
       
        print('there are %i orphan seeds' % len(orphan_seeds))
        for f in orphan_seeds:
            print(self.seed_labels[f])
            
        print('there are %i patches with multiple seeds' % len(multi_seed_patches))
        for p in multi_seed_patches:
            print(patch_to_seed_map[p])
            if p not in patch_to_seed_map.keys(): continue
            seeds = patch_to_seed_map[p]
            for sface in seeds:
                print(self.seed_labels[sface])
             
    def skeletonize_salience_verts(self):
        self.skeleton = skeletonize_vert_set(self.salience_verts)
        self.skeleton_points = [self.net_ui_context.mx * v.co for v in self.skeleton]
        self.has_skeletonized = True
    
    def skeletonize_with_tailes(self):
        self.skeleton = skeletonize_vert_set(self.salience_verts, allow_tails = True)
        self.skeleton_points = [self.net_ui_context.mx * v.co for v in self.skeleton]
        self.has_skeletonized = True
    
    def find_skeleton_edges(self):
        #find the edges in the skeleton
        seen_eds = set()
        perim_eds = set()
        for v in self.skeleton:
            for ed in v.link_edges:
                if ed in seen_eds: continue
                seen_eds.add(ed)
                if ed.verts[0] in self.skeleton and ed.verts[1] in self.skeleton:
                    perim_eds.add(ed)
                    
        return perim_eds
    
    def check_seeded_patches(self): 
        
        if len(self.seed_faces) == 0: return True #no seeds, user is advanced
        
        perim_eds = self.find_skeleton_edges()            
        overflowed_pathces = []
        topo_data = {}
        
        self.skeletonize_salience_verts()
        #grow the seeded patches within the skeleton
        for patch in self.network_cutter.face_patches:
            
            fs, iters, topo_dict =  flood_selection_edge_loop_report(self.net_ui_context.bme, perim_eds, patch.seed_face, max_iters = 200)
            
            topo_data[patch] = topo_dict
            
            patch.patch_faces = fs
            #patch.color_patch()
            
            print(patch.label)
            print(iters)
    
            if iters > 199:
                overflowed_pathces.append(patch)
                
        print('there are %i overflowed patches' % len(overflowed_pathces))
        
        #go through and check overlapping
        overlaps = []
        for patch in self.network_cutter.face_patches:
            overlap_patches = []
            for other_patch in self.network_cutter.face_patches:
                if other_patch == patch: continue
                overlap = patch.patch_faces.intersection(other_patch.patch_faces)
                if len(overlap):
                    print('Found overlapping patch')
                    overlap_patches.append(other_patch)
            
            if len(overlap_patches): 
                overlaps += [patch]
        
        
        print('There are %i overlapped patches' % len(overlaps))
        
        self.bad_patches = set(overflowed_pathces + overlaps)
        
        
        if len(self.bad_patches): return False
        else: return True
                                            
    def skeleton_to_patches_seeded(self):
        
        
        perim_eds = self.find_skeleton_edges()            
        
        
        overflowed_pathces = []
        
        topo_data = {}
        
        print('Reality check on patches')
        print([len(p.patch_faces) for p in self.network_cutter.face_patches])
        
        #grow the seeded patches within the skeleton
        for patch in self.network_cutter.face_patches:
            
            fs, iters, topo_dict =  flood_selection_edge_loop_report(self.net_ui_context.bme, perim_eds, patch.seed_face, max_iters = 200)
            
            topo_data[patch] = topo_dict
            
            patch.patch_faces = fs
            patch.color_patch()
            
            print(patch.label)
            print(iters)
    
            if iters > 199:
                overflowed_pathces.append(patch)
                
    
        print('Reality check on patches')
        print([len(p.patch_faces) for p in self.network_cutter.face_patches])
        
        #go through and check overlapping
        overlaps = {}
        for patch in self.network_cutter.face_patches:
            overlap_patches = []
            for other_patch in self.network_cutter.face_patches:
                if other_patch == patch: continue
                overlap = patch.patch_faces.intersection(other_patch.patch_faces)
                if len(overlap):
                    print('Found overlapping patch')
                    overlap_patches.append(other_patch)
            
            if len(overlap_patches): 
                overlaps[patch] = overlap_patches
         
        print('Reality check on patches after checking overlap')
        print([len(p.patch_faces) for p in self.network_cutter.face_patches]) 
        #remove geometry that is significantly different in growth ring
        #hwhen bounded by skeleton, vs bounded by salience vert
        
        ed_limits = set()
        seen_eds = set()
        raw_skeleton = skeletonize_vert_set(self.salience_verts, allow_tails = True)
        for v in raw_skeleton:
            for ed in v.link_edges:
                if ed in seen_eds: continue
                seen_eds.add(ed)
                if ed.other_vert(v) in self.salience_verts:
                        ed_limits.add(ed)
            
        topo_data_limited = {}
        for patch in overlaps.keys():
            fs, iters, topo_dict_limited =  flood_selection_edge_loop_report(self.net_ui_context.bme, ed_limits, patch.seed_face, max_iters = 150)
            
            topo_dict_unlimited = topo_data[patch]
            
            to_remove = []
            for f in patch.patch_faces:
                if f not in topo_dict_unlimited:
                    #consider removing
                    to_remove.append(f)
                    continue
                if f not in topo_dict_limited:
                    #print('WHY is this face not in the topology map?')
                    continue
                
                rank_0 = topo_dict_limited[f]
                rank_1 = topo_dict_unlimited[f]
                
                if rank_0 - rank_1 > 1: #meaning it took 3 more iterations to get there, then 
                    to_remove.append(f)
        
            patch.patch_faces.difference_update(to_remove)
            patch.color_patch()
        
        print('Reality check on patches after removing overlap?')
        print([len(p.patch_faces) for p in self.network_cutter.face_patches]) 
        
        
        
        
        #now, go and remove overlaps based on proximity to the seed
        for patch in overlaps.keys():
            print('overlapping?')
            other_patches = overlaps[patch] 
            
            topo_dict_p = topo_data[patch]
            
            for op in other_patches:
                topo_dict_op = topo_data[op]
                overlapping_region = patch.patch_faces.intersection(op.patch_faces)
                for f in overlapping_region:
                    
                    if f not in topo_dict_p:
                        if f in patch.patch_faces:
                            patch.patch_faces.remove(f)
                        continue
                    
                    if f not in topo_dict_op:
                        if f in other_patch.patch_faces:
                            other_patch.patch_faces.remove(f)
                        continue
                    
                    rank_0 = topo_dict_p[f]
                    rank_1 = topo_dict_op[f]
                    
                    if rank_0 < rank_1:
                        op.patch_faces.remove(f)
                    else:
                        patch.patch_faces.remove(f)
                    
        for patch in overlaps.keys():
            patch.color_patch()            
            
        if len(overflowed_pathces):
            #regrow each patch and record the level of each growth ring
            
            #regrow each patch using the salience_vert large island and record teh level of each growth ring
            
            print('There are overflowed patches')
            for p in overflowed_pathces: 
                print(p.label)
        
        
        
        
        gingiva = set(self.net_ui_context.bme.faces[:])
        all_teeth = set()
        
            
            
        
        self.net_ui_context.bme.to_mesh(self.net_ui_context.ob.data) 
        
                
        #refine things
            #check for overlap with other overflowed patches
            
            #filter out overflowed faces by ratio of seeded gr
            
            #fitle
    
    def skeleton_to_patches(self):
        
        merge_small = True
        merge_limit = 3000
        
        
        #Find all the edges which represent the connectivity
        #of the vertex skeleton
        start = time.time()
        seen_eds = set()
        perim_eds = set()
        for v in self.skeleton:
            for ed in v.link_edges:
                if ed in seen_eds: continue
                seen_eds.add(ed)
                if ed.verts[0] in self.skeleton and ed.verts[1] in self.skeleton:
                    perim_eds.add(ed)
        
        finish = time.time()  
        print('found perim edges in %f seconds method 1' % (finish-start)) 
            
        print('starting island region growing')
        
        #grow regions which are surrounded by the skeleton edges
        face_islands = partition_faces_between_edge_boundaries(self.net_ui_context.bme, [], perim_eds, max_iters = 100)
        face_islands.sort(key = len)
    
        print('Starting face coloring by region')
    
        def find_border_neigbor_islands(isl):
            '''
            test boundary edges
            might be nice to create an ilsand strucutre witch maps each face back to its
            resident island, and would prevent a if ___ in ____ check of all islands every time.
            
            '''
            #one way, search all edges
            seen_edges = set()
            neighbor_faces = set()
            
            #iterate the faces since we have them
            for f in isl:
                for ed in f.edges:
                    if ed in seen_edges: continue
                    for lf in ed.link_faces:
                        if lf not in isl:
                            neighbor_faces.add(lf)
                            
                    seen_edges.add(ed)
            
            neighbor_islands = []
            while len(neighbor_faces):
                test_f = neighbor_faces.pop()
                for island in face_islands:
                    if test_f in island:
                        neighbor_islands += [(island, len(island & neighbor_faces))]
                        neighbor_faces -= island
                        
            return neighbor_islands
        
        
        if merge_small:
            small_islands = [isl for isl in face_islands if len(isl)  < merge_limit]
            small_islands.sort(key = len)
            
            #merge small islands into their biggest neighbor, staring at smallest and working up.
            for isl in small_islands:
                
                neighboring_islands = find_border_neigbor_islands(isl)
                biggest, border_strength = max(neighboring_islands, key = lambda x: x[1])
                biggest |= isl
                face_islands.remove(isl)

        if "patches" not in self.input_net.bme.loops.layers.color:
            vcol_layer = self.input_net.bme.loops.layers.color.new("patches")
        else:
            vcol_layer = self.input_net.bme.loops.layers.color["patches"]
        
        face_islands.sort(key = len) 
        face_islands.reverse()
        for n, isl in enumerate(face_islands):
            for f in isl:  #get a random f out of the set
                break
            loc = f.calc_center_bounds()
            world_loc  = self.net_ui_context.mx * loc
            
            if n == 0:
                r_color = Color((.9, .4, .5))  #pinkish gingiva
            else:
                r_color = get_random_color()
            new_patch = BMFacePatch(f, loc, world_loc, vcol_layer, r_color)
            new_patch.patch_faces = isl
            new_patch.color_patch()
            self.network_cutter.face_patches += [new_patch]
        
        self.net_ui_context.bme.to_mesh(self.net_ui_context.ob.data) 
           
        self.check_seed_patches_against_skeleton()  
         
    def click_add_point(self, context, mouse_loc, connect=True):
        '''
        this will add a point into the trim line
        close the curve into a cyclic curve
        
        #Need to get smarter about closing the loop
        '''
        def none_selected(): self.net_ui_context.selected = None # TODO: Change this weird function in function shizz
        
        view_vector, ray_origin, ray_target= get_view_ray_data(context,mouse_loc)
        #loc, no, face_ind = ray_cast(self.net_ui_context.ob, self.net_ui_context.imx, ray_origin, ray_target, none_selected)
        loc, no, face_ind = ray_cast_bvh(self.net_ui_context.bvh, self.net_ui_context.imx, ray_origin, ray_target, none_selected)
        
        if loc == None: 
            print("Here")
            return

        if self.net_ui_context.hovered_near[0] and 'NON_MAN' in self.net_ui_context.hovered_near[0]:
            bmed, wrld_loc = self.net_ui_context.hovered_near[1] # hovered_near[1] is tuple (BMesh Element, location?)
            ip1 = self.closest_endpoint(wrld_loc)

            self.net_ui_context.selected = self.input_net.create_point(wrld_loc, self.net_ui_context.imx * wrld_loc, view_vector, bmed.link_faces[0].index)
            self.net_ui_context.selected.seed_geom = bmed
            self.net_ui_context.selected.bmedge = bmed  #UNUSED BUT PREPARING FOR FUTURE

            if ip1:
                seg = InputSegment(self.net_ui_context.selected, ip1)
                self.input_net.segments.append(seg)
                self.network_cutter.precompute_cut(seg)
                #seg.make_path(self.net_ui_context.bme, self.input_net.bvh, self.net_ui_context.mx, self.net_ui_context.imx)
        
        #Add a New Point at end
        elif (self.net_ui_context.hovered_near[0] == None) and (self.net_ui_context.snap_element == None):  #adding in a new point at end, may need to specify closest unlinked vs append and do some previs
            print("Here 11")
            closest_endpoint = self.closest_endpoint(self.net_ui_context.mx * loc)
            self.net_ui_context.selected = self.input_net.create_point(self.net_ui_context.mx * loc, loc, view_vector, face_ind)
            print('create new point')
            
            if len(self.spline_net.points):
                last_node = self.spline_net.points[-1]
                new_node = self.spline_net.create_point(self.net_ui_context.mx * loc, loc, view_vector, face_ind)
                self.spline_net.connect_points(new_node, last_node)
                new_node.update_splines()
                last_node.update_splines()  #this is going to update the spline twice?
            else:
                new_node = self.spline_net.create_point(self.net_ui_context.mx * loc, loc, view_vector, face_ind)
                   
            if closest_endpoint and connect:
                self.input_net.connect_points(self.net_ui_context.selected, closest_endpoint)
                self.network_cutter.precompute_cut(self.input_net.segments[-1])  #<  Hmm...not very clean.  

        elif self.net_ui_context.hovered_near[0] == None and self.net_ui_context.snap_element != None:  #adding in a new point at end, may need to specify closest unlinked vs append and do some previs
            print("Here 2")
            closest_endpoints = self.closest_endpoints(self.net_ui_context.snap_element.world_loc, 2)

            if closest_endpoints == None:
                #we are not quite hovered_near but in snap territory
                return

            if len(closest_endpoints) < 2:
                return

            seg = InputSegment(closest_endpoints[0], closest_endpoints[1])
            self.input_net.segments.append(seg)
            self.network_cutter.precompute_cut(seg)
            #seg.make_path(self.net_ui_context.bme, self.input_net.bvh, self.net_ui_context.mx, self.net_ui_context.imx)

        elif self.net_ui_context.hovered_near[0] == 'POINT':
            self.net_ui_context.selected = self.net_ui_context.hovered_near[1]

        elif self.net_ui_context.hovered_near[0] == 'EDGE':  #TODO, actually make InputSegment as hovered_near
            point = self.input_net.create_point(self.net_ui_context.mx * loc, loc, view_vector, face_ind)
            old_seg = self.net_ui_context.hovered_near[1]
            self.input_net.insert_point(point, old_seg)
            self.net_ui_context.selected = point
            self.network_cutter.update_segments()


    def add_spline(self, endpoint0, endpoint1):
        assert endpoint0.is_endpoint and endpoint1.is_endpoint
        seg = SplineSegment(endpoint0, endpoint1)
        self.spline_net.segments.append(seg)
        
        endpoint0.calc_handles()
        endpoint1.calc_handles()
            
        endpoint0.update_splines()
        endpoint1.update_splines()
        
        
        self.spline_net.push_to_input_net(self.net_ui_context, self.input_net)
        self.network_cutter.update_segments_async()
        return seg

    def add_point(self, p2d):
        mx = self.net_ui_context.mx
        imx = self.net_ui_context.imx
        loc, no, face_ind = self.ray_cast_source(p2d, in_world=False)
        if not loc: return None
        view_vector, ray_origin, ray_target = get_view_ray_data(self.context, p2d)
        
        #add an input node on non manifold edge of mesh
        if self.net_ui_context.hovered_near[0] and 'NON_MAN' in self.net_ui_context.hovered_near[0]:
            bmed, wrld_loc = self.net_ui_context.hovered_near[1]
            p = self.spline_net.create_point(wrld_loc,imx * wrld_loc, view_vector, bmed.link_faces[0].index)
            p.seed_geom = bmed
            p.bmedge = bmed #UNUSED, but preparing for future
        else:
            p = self.spline_net.create_point(mx * loc, loc, view_vector, face_ind)

        return p
    
    
    def insert_spline_point(self, p2d):
        mx = self.net_ui_context.mx
        imx = self.net_ui_context.imx
        loc, no, face_ind = self.ray_cast_source(p2d, in_world=False)
        if not loc: return None
        view_vector, ray_origin, ray_target = get_view_ray_data(self.context, p2d)
    
        
        p = self.spline_net.create_point(mx * loc, loc, view_vector, face_ind)
         
        #place holder for later hovering the tessellated line segments    
        #old_discrete_seg = self.net_ui_context.hovered_near[1]
        #old_spline_seg = old_discrete_seg.parent_spline
        seg = self.net_ui_context.hovered_near[1]
        n0, n1 = seg.n0, seg.n1   
        self.spline_net.insert_point(p, seg)
        seg.clear_input_net_references(self.input_net)
        for node in [n0, p, n1]:
            node.calc_handles()
        
        #n00 ----- n0 ------ p ------ n1-----n11 
        for node in [n0, n1]:  #because n0 and n1 connect to p,  this updates 4 splines
            node.update_splines()
        
        self.spline_net.push_to_input_net(self.net_ui_context, self.input_net)
        self.network_cutter.update_segments_async()
        self.network_cutter.validate_cdata()
        return p
    
    def ray_cast_source(self, p2d, in_world=True):
        context = self.context
        view_vector, ray_origin, ray_target = get_view_ray_data(context, p2d)
        mx,imx = self.net_ui_context.mx,self.net_ui_context.imx
        itmx = imx.transposed()
        loc, no, face_ind = ray_cast_bvh(self.net_ui_context.bvh, imx, ray_origin, ray_target)
        return (mx * loc if loc and in_world else loc, itmx * no if no and in_world else no, face_ind)

    def ray_cast_source_hit(self, p2d):
        return self.ray_cast_source(p2d, in_world=False)[0] != None

    def click_add_spline_point(self, context, mouse_loc, connect=True):
        '''
        this will add a point into the trim line
        close the curve into a cyclic curve
        
        #Need to get smarter about closing the loop
        '''
        def none_selected(): self.net_ui_context.selected = None # TODO: Change this weird function in function shizz
        
        view_vector, ray_origin, ray_target= get_view_ray_data(context,mouse_loc)
        #loc, no, face_ind = ray_cast(self.net_ui_context.ob, self.net_ui_context.imx, ray_origin, ray_target, none_selected)
        loc, no, face_ind = ray_cast_bvh(self.net_ui_context.bvh, self.net_ui_context.imx, ray_origin, ray_target, none_selected)
        
        if not loc: return

        #Add a new edge_point?
        if self.net_ui_context.hovered_near[0] and 'NON_MAN' in self.net_ui_context.hovered_near[0]:
            bmed, wrld_loc = self.net_ui_context.hovered_near[1] # hovered_near[1] is tuple (BMesh Element, location?)
            ip1 = self.closest_spline_endpoint(wrld_loc)

            self.net_ui_context.selected = self.spline_net.create_point(wrld_loc, self.net_ui_context.imx * wrld_loc, view_vector, bmed.link_faces[0].index)
            self.net_ui_context.selected.seed_geom = bmed
            self.net_ui_context.selected.bmedge = bmed  #UNUSED, but preparing for future

            self.net_ui_context.selected.update_splines()
                
            if ip1:
                seg = SplineSegment(self.net_ui_context.selected, ip1)
                self.spline_net.segments.append(seg)
                ip1.update_splines()
                #self.network_cutter.precompute_cut(seg)
                #seg.make_path(self.net_ui_context.bme, self.input_net.bvh, self.net_ui_context.mx, self.net_ui_context.imx)
        
        #Add a New Point at end free chains
        elif (self.net_ui_context.hovered_near[0] == None) and (self.net_ui_context.snap_element == None):  #adding in a new point at end, may need to specify closest unlinked vs append and do some previs
            
            closest_endpoint = self.closest_spline_endpoint(self.net_ui_context.mx * loc)
            self.net_ui_context.selected = self.spline_net.create_point(self.net_ui_context.mx * loc, loc, view_vector, face_ind)
            print('create new point')
                
            if closest_endpoint and connect:
                self.spline_net.connect_points(self.net_ui_context.selected, closest_endpoint)
                self.net_ui_context.selected.update_splines()
                closest_endpoint.update_splines() 

        elif self.net_ui_context.hovered_near[0] == 'POINT CONNECT' and self.net_ui_context.snap_element != None:  #adding in a new point at end, may need to specify closest unlinked vs append and do some previs
            print("Here 2")
            closest_endpoints = self.closest_spline_endpoints(self.net_ui_context.snap_element.world_loc, 2)
            # bail if we did not find at least two nearby endpoints
            if len(closest_endpoints) < 2: return
            seg = SplineSegment(closest_endpoints[0], closest_endpoints[1])
            self.spline_net.segments.append(seg)
            closest_endpoints[0].update_splines()
            closest_endpoints[1].update_splines()

            #self.network_cutter.precompute_cut(seg)
            #seg.make_path(self.net_ui_context.bme, self.input_net.bvh, self.net_ui_context.mx, self.net_ui_context.imx)

        elif self.net_ui_context.hovered_near[0] == 'POINT':
            self.net_ui_context.selected = self.net_ui_context.hovered_near[1]

        elif self.net_ui_context.hovered_near[0] == 'EDGE':  #TODO, actually make InputSegment as hovered_near
            point = self.spline_net.create_point(self.net_ui_context.mx * loc, loc, view_vector, face_ind)
            old_seg = self.net_ui_context.hovered_near[1]
            self.spline_net.insert_point(point, old_seg)
            old_seg.clear_input_net_references(self.input_net)
            self.net_ui_context.selected = point
            
            point.update_splines()
            for node in old_seg.points:
                node.update_splines()
            
            
        self.spline_net.push_to_input_net(self.net_ui_context, self.input_net, all_segs = True)
        self.network_cutter.update_segments_async()

    def inspect_things(self):
        '''
        container for random stuff to help debug
        '''
        print(self.net_ui_context.selected)
        
        if isinstance(self.net_ui_context.selected, CurveNode):
            cn = self.net_ui_context.selected
            print(cn.link_segments)
            print(cn.bmface)
        
    # TODO: Clean this up
    def click_delete_point(self, mode = 'mouse', disconnect=False):
        '''
        removes point from the trim line
        '''
        if mode == 'mouse':
            if self.net_ui_context.hovered_near[0] != 'POINT': return

            self.input_net.remove_point(self.net_ui_context.hovered_near[1], disconnect) 
            self.network_cutter.update_segments()

            if self.input_net.is_empty or self.net_ui_context.selected == self.net_ui_context.hovered_near[1]:
                self.net_ui_context.selected = None

        else: #hard delete with x key
            if not self.net_ui_context.selected: return
            self.input_net.remove(self.net_ui_context.selected, disconnect= True)

    def click_delete_spline_point(self, mode = 'mouse', disconnect=False):
        '''
        removes point from the trim line
        '''
        if mode == 'mouse':
            if self.net_ui_context.hovered_near[0] != 'POINT': return
            curve_point = self.net_ui_context.hovered_near[1]  #CurveNode

            #Clear the CurveNode to InputNetwork mappings and delete corresponding
            #elements
            for seg in curve_point.link_segments:
                seg.clear_input_net_references(self.input_net)
            if curve_point.input_point in self.input_net.points:
                self.input_net.remove_point(curve_point.input_point, disconnect)
            #Remove CurveNode from SplineNetwork
            connected_points = self.spline_net.remove_point(curve_point, disconnect)  #returns the new points on either side, connected or not
            print('there are %i connected points')
            for node in connected_points:  #need all point handles updated first, becuae of how auto handles use neighboring points
                node.calc_handles()   
            for node in connected_points:  #this actually doubly updaes the middle segment, but it's just bez interp, no cutting
                node.update_splines()
                
            self.spline_net.push_to_input_net(self.net_ui_context, self.input_net, all_segs = False)
            self.network_cutter.update_segments_async()
            self.network_cutter.validate_cdata()
            if self.spline_net.is_empty or self.net_ui_context.selected == self.net_ui_context.hovered_near[1]:
                self.net_ui_context.selected = None
                
        #Let's avoid hotkeys for now
        # else: #hard delete with x key
        #     if not self.net_ui_context.selected: return
        #     self.spline_net.remove(self.net_ui_context.selected, disconnect= True)
    
    def click_add_seed(self):
        
        if self.net_ui_context.hovered_mesh == {}: return
        
        face_ind = self.net_ui_context.hovered_mesh['face index']
        world_loc = self.net_ui_context.hovered_mesh['world loc']
        local_loc = self.net_ui_context.hovered_mesh['local loc']
        self.network_cutter.add_seed(face_ind, world_loc, local_loc)
    
    
    
    def click_enter_salience_paint(self, delete = False):
        if self.net_ui_context.hovered_mesh == {}: return
        
        face_ind = self.net_ui_context.hovered_mesh['face index']
        world_loc = self.net_ui_context.hovered_mesh['world loc']
        local_loc = self.net_ui_context.hovered_mesh['local loc']
        
        if delete:
            self.brush.brush_color = Color((1,1,1))
        
        #use this vcolor to paint on
        if "patches" not in self.net_ui_context.bme.loops.layers.color:
            vcol_layer = self.net_ui_context.bme.loops.layers.color.new("patches")
        else:
            vcol_layer = self.net_ui_context.bme.loops.layers.color["patches"]
        
        self.brush.vcol = vcol_layer
        
    def salience_paint_confirm(self):
        new_salience_verts = set()
        for f in self.brush.geom_accum:
            new_salience_verts.update([v for v in f.verts])
        
        self.salience_verts.update(new_salience_verts)
        
        return
    
    def salience_paint_confirm_subtract(self):
        new_salience_verts = set()
        for f in self.brush.geom_accum:
            new_salience_verts.update([v for v in f.verts])
        
        print(len(self.salience_verts))
        self.salience_verts.difference_update(new_salience_verts)
        print(len(self.salience_verts))
        return
    
    
    def click_enter_paint(self, delete = False):
        
        if self.net_ui_context.hovered_mesh == {}: return
        
        face_ind = self.net_ui_context.hovered_mesh['face index']
        world_loc = self.net_ui_context.hovered_mesh['world loc']
        local_loc = self.net_ui_context.hovered_mesh['local loc']
        
        f= self.net_ui_context.bme.faces[face_ind] 
         
        self.network_cutter.active_patch = None  #TODO, this should already be none..should we enforce it?
        for patch in self.network_cutter.face_patches:
            if f in patch.patch_faces:  #just change the color but don't add a duplicate
                self.network_cutter.active_patch = patch
                self.brush.brush_color = patch.color
                print('found the active patch')
        
        if delete:
            self.brush.brush_color = Color((1,1,1))
        if self.network_cutter.active_patch == None and not delete:
            self.network_cutter.add_patch_start_paint(face_ind, world_loc, local_loc)
    
         
    def paint_confirm_greedy(self):
        '''
        destroy all Iput elements touched by brush
        add brush accum geometry to active patch
        remove brush accumg geometry from other patches
        '''
        
        
        print('paint confirm')
        
        self.network_cutter.validate_cdata()
        
        #First, remove geom accum from other patches
        remove_patches = []
        for patch in self.network_cutter.face_patches:
            if patch == self.network_cutter.active_patch:continue
            
            if not patch.patch_faces.isdisjoint(self.brush.geom_accum):
                patch.paint_modified = True
            patch.patch_faces.difference_update(self.brush.geom_accum)
            if len(patch.patch_faces) == 0:
                remove_patches += [patch]
            patch.validate_seed()
            
        for patch in remove_patches:
            self.network_cutter.face_patches.remove(patch)

        #Destroy all Discrete Network Elements touched by brush
        remove_points = []
        for ip in self.input_net.points:
            if ip.bmface in self.brush.geom_accum:
                remove_points += [ip]
                
        print('removing %i input points' % len(remove_points))
        for ip in remove_points:
            self.input_net.remove_point(ip, disconnect = True)
            
        remove_segs = []        
        for seg in self.input_net.segments:
            if seg not in self.network_cutter.cut_data: continue #uh oh
            if not self.brush.geom_accum.isdisjoint(self.network_cutter.cut_data[seg]['face_set']):                           
                remove_segs += [seg]
        
        for seg in remove_segs:
            self.input_net.remove_segment(seg)
    
        print('removing %i input segments' % len(remove_segs))
        
        #Destroy all Spline Network Elements touched by brush
        remove_nodes = []
        for node in self.spline_net.points:
            if node.bmface in self.brush.geom_accum:
                #self.spline_net.remove_point(node, disconnect = True)
                remove_nodes += [node]
                
        for node in remove_nodes:
            #the seg is about to get deleted because it's node is gone
            #so we will loose the opportuity to clear out the children
            #segments
            for seg in node.link_segments:
                seg.clear_input_net_references(self.input_net)
            #actually delete the node
            self.spline_net.remove_point(node, disconnect = True)
            node.clear_input_net_references(self.input_net)  #Should  not be any
            
        remove_splines = set()   
        for spline in self.spline_net.segments:
            for ip_seg in spline.input_segments:
                if ip_seg not in self.input_net.segments:
                    #remove the associated SPLINE segment  #TODO get smarter later 
                    remove_splines.add(spline)
                    
        for spline in remove_splines:
            self.spline_net.remove_segment(spline)            
            spline.clear_input_net_references(self.input_net) #if the spline parent is gone, we take all children away from the border too....#TRUMP?        
        
        #loose_nodes = []     
        #for node in self.spline_net.points:
        #    if len(node.link_segments) == 0:
        #        loose_nodes += [node]
                
        #print('deleting %i loose nodes' % len(loose_nodes))       
        #for node in loose_nodes:
        #    self.spline_net.remove_point(node)

        self.network_cutter.active_patch.patch_faces |= self.brush.geom_accum
        self.network_cutter.active_patch.paint_modified = True
        
        
        #TODO, remove the destroyed elements from the patch references
        
        self.network_cutter.active_patch.color_patch()
        self.network_cutter.validate_cdata()
        
        
        return
      
    def paint_confirm_mergey(self):
        '''
        destroy all Iput elements touched by brush
        add brush accum geometry to active patch
        merge any patches touched into active patch
        this prevents adjacnet patches until we have the cutting mechancis
        to support it
        '''
        
        
        print('paint confirm')
        
        if len(self.brush.geom_accum) == 0: return  #that was easy
        
        self.network_cutter.validate_cdata()
        
        AP = self.network_cutter.active_patch
        
        #First, identify touched patches
        merge_patches = []
        
        for patch in self.network_cutter.face_patches:
            if patch == AP: continue
            if not patch.patch_faces.isdisjoint(self.brush.geom_accum):
                merge_patches += [patch]
        
        #merge them all together    
        for patch in merge_patches:
            AP.patch_faces.update(patch.patch_faces)
            AP.input_net_segments += patch.input_net_segments
            AP.ip_points += patch.ip_points
            AP.spline_net_segments += patch.spline_net_segments
            AP.curve_nodes += patch.curve_nodes
            self.network_cutter.face_patches.remove(patch)

        #Destroy all Discrete Network Elements touched by brush
        remove_points = []
        for ip in self.input_net.points:
            if ip.bmface in self.brush.geom_accum:
                remove_points += [ip]
                
        print('removing %i input points' % len(remove_points))
        for ip in remove_points:
            self.input_net.remove_point(ip, disconnect = True)
            
        remove_segs = []        
        for seg in self.input_net.segments:
            if seg not in self.network_cutter.cut_data: continue #uh oh
            if not self.brush.geom_accum.isdisjoint(self.network_cutter.cut_data[seg]['face_set']):                           
                remove_segs += [seg]
        
        for seg in remove_segs:
            self.input_net.remove_segment(seg)
    
        print('removing %i input segments' % len(remove_segs))
        
        #Destroy all Spline Network Elements touched by brush
        remove_nodes = []
        for node in self.spline_net.points:
            if node.bmface in self.brush.geom_accum:
                #self.spline_net.remove_point(node, disconnect = True)
                remove_nodes += [node]
                
        for node in remove_nodes:
            #the seg is about to get deleted because it's node is gone
            #so we will loose the opportuity to clear out the children
            #segments
            for seg in node.link_segments:
                seg.clear_input_net_references(self.input_net)
            #actually delete the node
            self.spline_net.remove_point(node, disconnect = True)
            node.clear_input_net_references(self.input_net)  #Should  not be any
            
        remove_splines = set()   
        for spline in self.spline_net.segments:
            for ip_seg in spline.input_segments:
                if ip_seg not in self.input_net.segments:
                    #remove the associated SPLINE segment  #TODO get smarter later 
                    remove_splines.add(spline)
                    
        for spline in remove_splines:
            self.spline_net.remove_segment(spline)            
            spline.clear_input_net_references(self.input_net) #if the spline parent is gone, we take all children away from the border too....#TRUMP?        
        
        #join the brush geom!
        self.network_cutter.active_patch.patch_faces |= self.brush.geom_accum
        self.network_cutter.active_patch.paint_modified = True
        
        #ensure no 0 face paches
        remove_patches = []
        for patch in self.network_cutter.face_patches:
            if len(patch.patch_faces) == 0:
                remove_patches += [patch]
            
        for patch in remove_patches:
            self.network_cutter.face_patches.remove(patch)
                
        #TODO, remove the destroyed elements from the patch references
        self.network_cutter.active_patch.color_patch()
        self.network_cutter.validate_cdata()  #we have just removed a bunch of input network elements

        return

    def paint_confirm_subtract(self):
        '''
        destroy all Input elements touched by brush
        remove brush accum geometry from all patches
        '''
        
        
        print('paint confirm subtract')
        
        if len(self.brush.geom_accum) == 0: return  #that was easy
        
        self.network_cutter.validate_cdata()
        
        #First, identify touched patches 
        for patch in self.network_cutter.face_patches:
            if not patch.patch_faces.isdisjoint(self.brush.geom_accum):
                print('removing brush geom from patch')
                patch.patch_faces.difference_update(self.brush.geom_accum)
                if patch.validate_seed():
                    patch.world_loc = self.net_ui_context.mx * patch.local_loc
                patch.paint_modified = True
                patch.uncolor_patch()
                patch.color_patch()
        
        #ensure no 0 face paches
        remove_patches = []
        for patch in self.network_cutter.face_patches:
            if len(patch.patch_faces) == 0:
                remove_patches += [patch]
            
        for patch in remove_patches:
            self.network_cutter.face_patches.remove(patch)
            
        #Destroy all Discrete Network Elements touched by brush
        remove_points = []
        for ip in self.input_net.points:
            if ip.bmface in self.brush.geom_accum:
                remove_points += [ip]
                
        for ip in remove_points:
            self.input_net.remove_point(ip, disconnect = True)
            
        remove_segs = []        
        for seg in self.input_net.segments:
            if seg not in self.network_cutter.cut_data: continue #uh oh
            if not self.brush.geom_accum.isdisjoint(self.network_cutter.cut_data[seg]['face_set']):                           
                remove_segs += [seg]
        
        for seg in remove_segs:
            self.input_net.remove_segment(seg)
    
        #Destroy all Spline Network Elements touched by brush
        remove_nodes = []
        for node in self.spline_net.points:
            if node.bmface in self.brush.geom_accum:
                #self.spline_net.remove_point(node, disconnect = True)
                remove_nodes += [node]
                
        for node in remove_nodes:
            #the seg is about to get deleted because it's node is gone
            #so we will loose the opportuity to clear out the children
            #segments
            for seg in node.link_segments:
                seg.clear_input_net_references(self.input_net)
            #actually delete the node
            self.spline_net.remove_point(node, disconnect = True)
            node.clear_input_net_references(self.input_net)  #Should  not be any
            
        remove_splines = set()   
        for spline in self.spline_net.segments:
            for ip_seg in spline.input_segments:
                if ip_seg not in self.input_net.segments:
                    #remove the associated SPLINE segment  #TODO get smarter later 
                    remove_splines.add(spline)
                    
        for spline in remove_splines:
            self.spline_net.remove_segment(spline)            
            spline.clear_input_net_references(self.input_net) #if the spline parent is gone, we take all children away from the border too....#TRUMP?        
        

        self.network_cutter.validate_cdata()  #we have just removed a bunch of input network elements

        return      
                                  
    def paint_exit(self):
        print('paint exit')
        
        #create new splines around newly created patches
        self.network_cutter.create_spline_network_from_skeleton_patches(self.spline_net)
        
        #fit splines to modified boundaries of existing patches
        #self.network_cutter.update_painted_face_patches_splines(self.spline_net)
        
        #now push all the splines back to input net and preview the cuts
        print('\n\nPushing to input net')
        self.spline_net.push_to_input_net(self.net_ui_context, self.input_net)
        self.network_cutter.update_segments_async()
        
        #Do this for now
        self.net_ui_context.bme.to_mesh(self.net_ui_context.ob.data)
        
    # TODO: Make this a NetworkUIContext function
    
    def clear_patches(self):
        
        to_remove = self.network_cutter.face_patches[:]
        for p in to_remove:
            p.uncolor_patch()
            self.network_cutter.face_patches.remove(p)
            
    def delete_active_patch(self):
    
    
        if self.network_cutter.active_patch == None: return
        if self._state != 'segmentation': return
        #for now, use an active patch input style
        #if self.net_ui_context.hovered_mesh == {}: return
        #face_ind = self.net_ui_context.hovered_mesh['face index']
        #world_loc = self.net_ui_context.hovered_mesh['world loc']
        #local_loc = self.net_ui_context.hovered_mesh['local loc']
        #patch = self.network_cutter.find_patch_post_cut(face_ind, world_loc, local_loc)
        
        #verts = set()
        #edges = set()
        #for f in patch.faces:
            #verts.update(f.verts)
            #edges.update(ed.verts)
        
        patch = self.network_cutter.active_patch    
        del_vs = [v for v in self.net_ui_context.bme.verts if all([f in patch.patch_faces for f in v.link_faces])]
        del_eds = [ed for ed in self.net_ui_context.bme.edges if all([f in patch.patch_faces for f in ed.link_faces])]
        
        bme = self.net_ui_context.bme  
        
        for f in patch.patch_faces: 
            bme.faces.remove(f)
        
        for ed in del_eds:
            bme.edges.remove(ed)
                
        for v in del_vs:
            bme.verts.remove(v)
            
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        self.network_cutter.active_patch = None   
        self.network_cutter.face_patches.remove(patch)
        bme.to_mesh(self.net_ui_context.ob.data)
        
        #update BVH?  hmmmm....

    def active_patch_to_vgroup(self):
    
    
        if self.network_cutter.active_patch == None: return
        if self._state != 'segmentation': return
        #for now, use an active patch input style
        #if self.net_ui_context.hovered_mesh == {}: return
        #face_ind = self.net_ui_context.hovered_mesh['face index']
        #world_loc = self.net_ui_context.hovered_mesh['world loc']
        #local_loc = self.net_ui_context.hovered_mesh['local loc']
        #patch = self.network_cutter.find_patch_post_cut(face_ind, world_loc, local_loc)
        
        #verts = set()
        #edges = set()
        #for f in patch.faces:
            #verts.update(f.verts)
            #edges.update(ed.verts)
        
        patch = self.network_cutter.active_patch    
        bme = self.net_ui_context.bme  
        
        group_vs = [v for v in bme.verts if all([f in patch.patch_faces for f in v.link_faces])]
        
        ob = self.net_ui_context.ob
        vg = ob.vertex_groups.new('segmentation')
        
        vg.add([v.index for v in group_vs], 1, type = 'REPLACE')
        self.network_cutter.active_patch = None
        self.network_cutter.face_patches.remove(patch)
        bme.to_mesh(self.net_ui_context.ob.data)
          
    def split_active_patch(self):
    
    
        if self.network_cutter.active_patch == None: return
        #for now, use an active patch input style
        #if self.net_ui_context.hovered_mesh == {}: return
        #face_ind = self.net_ui_context.hovered_mesh['face index']
        #world_loc = self.net_ui_context.hovered_mesh['world loc']
        #local_loc = self.net_ui_context.hovered_mesh['local loc']
        #patch = self.network_cutter.find_patch_post_cut(face_ind, world_loc, local_loc)
        
        #verts = set()
        #edges = set()
        #for f in patch.faces:
            #verts.update(f.verts)
            #edges.update(ed.verts)
        
        patch = self.newtork_cutter.active_patch    
        
        patch.find_boundary_edges()  #this should probbaly happen at regino growing time anyway
        
        bme = self.net_ui_context.bme 
        eds = patch.find_all_boundary_edges()
        bmesh.ops.split_edges(bme, eges = list(eds))
            
        self.newtork_cutter.active_patch = None    
        self.network_cutter.face_patches.remove(patch)
        self.net_ui_context.bme.to_mesh(self.net_ui_context.ob.data)
    
    
    def separate_active_patch(self):
    
    
        if self.network_cutter.active_patch == None: return
        #for now, use an active patch input style
        #if self.net_ui_context.hovered_mesh == {}: return
        #face_ind = self.net_ui_context.hovered_mesh['face index']
        #world_loc = self.net_ui_context.hovered_mesh['world loc']
        #local_loc = self.net_ui_context.hovered_mesh['local loc']
        #patch = self.network_cutter.find_patch_post_cut(face_ind, world_loc, local_loc)
        
        #verts = set()
        #edges = set()
        #for f in patch.faces:
            #verts.update(f.verts)
            #edges.update(ed.verts)
        
        patch = self.network_cutter.active_patch    
        
        new_bme = new_bmesh_from_bmelements(patch.patch_faces)
        name = self.net_ui_context.ob.name + "_patch"
        new_me = bpy.data.meshes.new(name)
        new_ob = bpy.data.objects.new(name, new_me)
        new_ob.matrix_world = self.net_ui_context.mx
        new_bme.to_mesh(new_me)
        new_bme.free()
        bpy.context.scene.objects.link(new_ob)
                
        bme = self.net_ui_context.bme 

        del_vs = [v for v in bme.verts if all([f in patch.patch_faces for f in v.link_faces])]
        del_eds = [ed for ed in bme.edges if all([f in patch.patch_faces for f in ed.link_faces])]        
        bme = self.net_ui_context.bme  
        for f in patch.patch_faces: 
            bme.faces.remove(f)
        
        for ed in del_eds:
            bme.edges.remove(ed)
                
        for v in del_vs:
            bme.verts.remove(v)
            
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        self.network_cutter.active_patch = None
        self.network_cutter.face_patches.remove(patch)
        self.net_ui_context.bme.to_mesh(self.net_ui_context.ob.data)
        
    def duplicate_active_patch(self):

        if self.network_cutter.active_patch == None: return
        patch = self.network_cutter.active_patch    
        patch.uncolor_patch()
        
        new_bme = new_bmesh_from_bmelements(patch.patch_faces)
        name = self.net_ui_context.ob.name + "_patch"
        new_me = bpy.data.meshes.new(name)
        new_ob = bpy.data.objects.new(name, new_me)
        new_ob.matrix_world = self.net_ui_context.mx
        new_bme.to_mesh(new_me)
        new_bme.free()
        bpy.context.scene.objects.link(new_ob)
        
        self.network_cutter.active_patch = None
        self.network_cutter.face_patches.remove(patch)
        self.net_ui_context.bme.to_mesh(self.net_ui_context.ob.data) 
                  
    def closest_endpoint(self, pt3d):
        def dist3d(point):
            return (point.world_loc - pt3d).length

        endpoints = [ip for ip in self.input_net.points if ip.is_endpoint]
        if len(endpoints) == 0: return None

        return min(endpoints, key = dist3d)
    
    # TODO: Make this a NetworkUIContext function
    
    def closest_spline_endpoint(self, pt3d):
        def dist3d(point):
            return (point.world_loc - pt3d).length

        endpoints = [ip for ip in self.spline_net.points if ip.is_endpoint]
        if len(endpoints) == 0: return None

        return min(endpoints, key = dist3d)
    
    # TODO: Also NetworkUIContext function
    def closest_endpoints(self, pt3d, n_points):
        #in our application, at most there will be 100 endpoints?
        #no need for accel structure here
        n_points = max(0, n_points)

        endpoints = [ip for ip in self.input_net.points if ip.is_endpoint] #TODO self.endpoints?

        if len(endpoints) == 0: return None
        n_points = min(n_points, len(endpoints))

        def dist3d(point):
            return (point.world_loc - pt3d).length

        endpoints.sort(key = dist3d)

        return endpoints[0:n_points+1]

    def closest_spline_endpoints(self, pt3d, n_points):
        #in our application, at most there will be 100 endpoints?
        #no need for accel structure here
        n_points = max(0, n_points)

        endpoints = [ip for ip in self.spline_net.points if ip.is_endpoint] #TODO self.endpoints?
        if len(endpoints) == 0: return []
        n_points = min(n_points, len(endpoints))

        def dist3d(point): return (point.world_loc - pt3d).length

        endpoints.sort(key = dist3d)
        return endpoints[0:n_points+1]
 
    def cache_to_bmesh(self):
        
        simple_model = bpy.data.objects.get(self.net_ui_context.ob.name + "_simple")
        bme_simple = bmesh.new()
     
        bme_simple.from_mesh(simple_model.data)
        bme_simple.verts.ensure_lookup_table()
        bme_simple.faces.ensure_lookup_table()    
            
        bme_cache = bmesh.new()
        node_to_bmv = {}
        
        #edge_id = bme_cache.verts.layers.int.new('edgepoint')
        
        edgepoints = set()
        imx = self.net_ui_context.imx
        bvh = self.net_ui_context.bvh
        
        for node in self.spline_net.points:
            
            bmv = bme_cache.verts.new(imx * node.world_loc)
            #bmv.normal = node.view
            node_to_bmv[node] = bmv
            
            if node.is_edgepoint():
                edgepoints.add(bmv)
            #    bmv[edge_id] = 1
            #else:
            #    bmv[edge_id] = 0
        for seg in self.spline_net.segments:
            bmv0 = node_to_bmv[seg.n0]
            bmv1 = node_to_bmv[seg.n1]
            
            bme_cache.edges.new((bmv0, bmv1))
            
            
            
            
            
        bmesh.ops.subdivide_edges(bme_cache, edges = bme_cache.edges[:], cuts = 3)
        
        normal_map = {}
        for v in bme_cache.verts:
            loc, no, ind, d = bvh.find_nearest(v.co)
            if loc:
                v.co = loc
                normal_map[v] = bme_simple.faces[ind].normal
            
            
            
            
        geom = bmesh.ops.extrude_edge_only(bme_cache, edges = bme_cache.edges[:]) 
        
        extrude_vs = set([ele for ele in geom['geom'] if isinstance(ele, bmesh.types.BMVert)])
        for v in bme_cache.verts:
            if v not in extrude_vs:
                v.co += .5 * normal_map[v]
            
        for v in bme_cache.verts:
            if v in extrude_vs:
                neighbors = set([ed.other_vert(v) for ed in v.link_edges])
                neighbors.difference_update(extrude_vs)
                
                v_across = neighbors.pop()
                
                v.co += 1.0 * (v.co - v_across.co)
                

        
        if 'Teeth Divider' not in bpy.data.objects:
            margin_me = bpy.data.meshes.new('Teeth Divider')
            margin_ob = bpy.data.objects.new('Teeth Divider', margin_me)
            margin_ob.matrix_world = self.net_ui_context.mx
            bpy.context.scene.objects.link(margin_ob)
            
            edge_point_group = margin_ob.vertex_groups.new('edgpoints')
            
        else:
            margin_ob = bpy.data.objects.get('Teeth Divider')
            margin_me = margin_ob.data
            edge_point_group = margin_ob.vertex_groups.get('edgpoints')
        
        margin_ob.hide = False
        bme_cache.verts.ensure_lookup_table()
        bme_cache.verts.index_update()
        
            
        bme_cache.to_mesh(margin_me)
        edgepoint_inds = [bmv.index for bmv in edgepoints]
        edge_point_group.remove([i for i in range(0, len(bme_cache.verts))])
        edge_point_group.add(edgepoint_inds, 1, type = 'REPLACE')
        
        self.split_bvh = BVHTree.FromBMesh(bme_cache)
        bme_cache.free()
        bme_simple.free()
    
    def break_apart_mesh(self):
        overlap = self.net_ui_context.bvh.overlap(self.split_bvh)
    
        del_fs = set([self.net_ui_context.bme.faces[pair[0]] for pair in overlap])
        
        all_edges = set()
        all_verts = set()
        for f in del_fs:
            all_edges.update(f.edges[:])
            all_verts.update(f.verts[:])
        
        del_edges = set()
        for ed in all_edges:
            if all([f in del_fs for f in ed.link_faces]):
                del_edges.add(ed)
        
        del_verts = set()
        for v in all_verts:
            if all([f in del_fs for f in v.link_faces]):
                del_verts.add(v)
            
        for f  in del_fs:
            self.net_ui_context.bme.faces.remove(f)
        for ed in del_edges:
            self.net_ui_context.bme.edges.remove(ed)
        for v in del_verts:
            self.net_ui_context.bme.verts.remove(v)
            
        self.net_ui_context.bme.to_mesh(self.net_ui_context.ob.data)
        self.net_ui_context.ob.data.update()
    
    def separate_and_solidify(self):
        
        #islands = bmesh_loose_parts_faces(self.net_ui_context.bme, max_iters = 1000)
        
        #islands.sort(key = len)
        
        
        patches = self.network_cutter.face_patches[:]
        patches.sort(key = lambda x: len(x.patch_faces))
        
        
        
        mat = bpy.data.materials.get("patches")
        
        
        if len(self.seed_faces):
            
            gingiva = set(self.net_ui_context.bme.faces[:])
            
            all_teeth = set()
            
            
        
        
        
            for i, p in enumerate(patches[0:len(patches)]): #skip the end island, which is the biggest
                isl = p.patch_faces
                gingiva.difference_update(isl) #this tooth is no longer part of the gingiva
                all_teeth.update(isl)
                new_bme = new_bmesh_from_bmelements(isl)
                
                name = p.label
                new_me = bpy.data.meshes.new(name)
                new_ob = bpy.data.objects.new(name, new_me)
                new_ob.matrix_world = self.net_ui_context.mx
                new_bme.to_mesh(new_me)
                new_bme.free()
                bpy.context.scene.objects.link(new_ob)
                
                new_ob.data.materials.append(mat)
                vcol = new_ob.data.vertex_colors.new(name = "patches")
                color = p.color
                for f in new_ob.data.polygons:
                    for loop_index in f.loop_indices:
                        vcol.data[loop_index].color = color
                
            
            perim_eds = set()
            all_eds = set()
            for f in all_teeth:
                all_eds.update(f.edges[:])
            for ed in all_eds:
                if not all([lf in all_teeth for lf in ed.link_faces]):
                    perim_eds.add(ed)
                
            all_islands = partition_faces_between_edge_boundaries(self.net_ui_context.bme, gingiva, perim_eds, max_iters = 1000)
            
            print('there are %i gingival islands')
            
            
            final_gingiva = set()
            small_islands = []
            for isl in all_islands:
                if len(isl) > 500:
                    final_gingiva.update(isl)
                else:
                    small_islands.append(isl)
                    
            new_bme = new_bmesh_from_bmelements(final_gingiva)
                
            name = 'gingiva'
            new_me = bpy.data.meshes.new(name)
            new_ob = bpy.data.objects.new(name, new_me)
            new_ob.matrix_world = self.net_ui_context.mx
            new_bme.to_mesh(new_me)
            new_bme.free()
            bpy.context.scene.objects.link(new_ob)
                
            new_ob.data.materials.append(mat)
            vcol = new_ob.data.vertex_colors.new(name = "patches")
            color = Color((.9, .4, .5))  #pinkish 
            for f in new_ob.data.polygons:
                for loop_index in f.loop_indices:
                    vcol.data[loop_index].color = color
                
                
                
        else:         
            for i, p in enumerate(patches[0:len(patches)]): #skip the end island, which is the biggest
                isl = p.patch_faces
                new_bme = new_bmesh_from_bmelements(isl)
                
                if i == len(patches) -1:
                    name = "Ginigva"
                else:
                    name = "Tooth"
                new_me = bpy.data.meshes.new(name)
                new_ob = bpy.data.objects.new(name, new_me)
                new_ob.matrix_world = self.net_ui_context.mx
                new_bme.to_mesh(new_me)
                new_bme.free()
                bpy.context.scene.objects.link(new_ob)
                
                new_ob.data.materials.append(mat)
                vcol = new_ob.data.vertex_colors.new(name = "patches")
                color = p.color
                for f in new_ob.data.polygons:
                    for loop_index in f.loop_indices:
                        vcol.data[loop_index].color = color
                
            #new_ob.hide = True    
            
            #ob_names = [ob.name for ob in bpy.data.objects]
            
            #if i == len(patches) -1:
            #    new_ob.hide = False
            #else:
            #    bpy.context.scene.objects.active = new_ob
                #bpy.ops.ai_teeth.convexify_tooth_shell()
                #detect the new object
                #for ob in bpy.data.objects:
                #    if ob.name not in ob_names:
                #        break
                
                #ob.data.materials.append(mat)
                #vcol = ob.data.vertex_colors.new(name = "patches")
                #for f in ob.data.polygons:
                #    for loop_index in f.loop_indices:
                #        vcol.data[loop_index].color = color
            
                #ob.hide = False
                #new_ob.hide = True
            
        
    # TODO: NetworkUIContext??
    def closest_point_3d_linear(self, seg, pt3d):
        '''
        will return the closest point on a straigh line segment
        drawn between the two input points
       
        If the 3D point is not within the infinite cylinder defined
        by 2 infinite disks placed at each input point and orthogonal
        to the vector between them, will return None
       
       
       
        A_pt3d              B_pt3d
          .                    .
          |                    |              
          |                    |              
          |                    |               
          |       ip0._________x_________.ip1   
         
         
         A_pt3d will return None, None.  B_pt3d will return 3d location at orthogonal intersection and the distance
         
         else, will return a tupple (location of intersection, %along line from ip0 to ip1
         
         happens in the world coordinates
       
        '''

        if isinstance(seg, SplineSegment):
            intersect3d = intersect_point_line(pt3d, seg.n0.world_loc, seg.n1.world_loc)
        else:
            intersect3d = intersect_point_line(pt3d, seg.ip0.world_loc, seg.ip1.world_loc)

        if intersect3d == None: return (None, None)

        dist3d = (intersect3d[0] - pt3d).length

        if  (intersect3d[1] < 1) and (intersect3d[1] > 0):
            return (intersect3d[0], dist3d)

        return (None, None)

    def enter_poly_mode(self):
        if self._state == 'main': return
        
        if self._state == 'paint main':
            del self.brush
            self.brush = None
            self.paint_exit()
            self.fsm_change('main')
    
        elif self._state == 'seed':
            self.fsm_change('main')
            
            
    def enter_paint_mode(self):
        self.fsm_change('paint entering')
                
    def find_network_cycles_button(self):
        self.input_net.find_network_cycles()
    
    def knife_stepwise_prepare_button(self):
        self.network_cutter.knife_gometry_stepper_prepare()
        
    def knife_step_button(self):
        self.network_cutter.knife_geometry_step()
        self.net_ui_context.bme.to_mesh(self.net_ui_context.ob.data)
         
    def compute_cut_button(self):
        self.network_cutter.knife_geometry4()
        
        self.network_cutter.find_perimeter_edges()
        for patch in self.network_cutter.face_patches:
            patch.grow_seed(self.input_net.bme, self.network_cutter.boundary_edges)
            patch.color_patch()
        self.net_ui_context.bme.to_mesh(self.net_ui_context.ob.data)
        
        self._sate_next = 'segmentation'
        
    def enter_seed_select_button(self):
        self.fsm_change('seed')
        self.cursor_modal_set('EYEDROPPER')
        return
    
       
    def hover(self, select_radius = 12, snap_radius = 24): #TDOD, these radii are pixels? Shoudl they be settings?
        '''
        finds points/edges/etc that are near ,mouse
         * hovering happens in mixed 3d and screen space, 20 pixels thresh for points, 30 for edges 40 for non_man
        '''

        # TODO: update self.hover to use Accel2D?
        mouse = self.actions.mouse
        context = self.context

        mx, imx = get_matrices(self.net_ui_context.ob)
        loc3d_reg2D = view3d_utils.location_3d_to_region_2d
        # ray tracing
        view_vector, ray_origin, ray_target = get_view_ray_data(context, mouse)
        #loc, no, face_ind = ray_cast(self.net_ui_context.ob, imx, ray_origin, ray_target, None)
        loc, no, face_ind = ray_cast_bvh(self.net_ui_context.bvh, imx, ray_origin, ray_target, None)
        self.net_ui_context.snap_element = None
        self.net_ui_context.connect_element = None

        if self.input_net.is_empty:
            self.net_ui_context.hovered_near = [None, -1]
            self.net_ui_context.nearest_non_man_loc()
            return
        
        if face_ind == -1 or face_ind == None: 
            self.net_ui_context.closest_ep = None
            return
        else: self.net_ui_context.closest_ep = self.closest_endpoint(mx * loc)

        #find length between vertex and mouse
        def dist(v):
            if v == None:
                print('v off screen')
                return 100000000
            diff = v - Vector(mouse)
            return diff.length

        #find length between 2 3d points
        def dist3d(v3):
            if v3 == None:
                return 100000000
            delt = v3 - self.net_ui_context.ob.matrix_world * loc
            return delt.length

        #closest_3d_loc = min(self.input_net.world_locs, key = dist3d)
        closest_ip = min(self.input_net.points, key = lambda x: dist3d(x.world_loc))
        pixel_dist = dist(loc3d_reg2D(context.region, context.space_data.region_3d, closest_ip.world_loc))

        if pixel_dist  < select_radius:
            #print('point is hovered_near')
            #print(pixel_dist)
            self.net_ui_context.hovered_near = ['POINT', closest_ip]  #TODO, probably just store the actual InputPoint as the 2nd value?
            self.net_ui_context.snap_element = None
            return

        elif pixel_dist >= select_radius and pixel_dist < snap_radius:
            #print('point is within snap radius')
            #print(pixel_dist)
            if closest_ip.is_endpoint:
                self.net_ui_context.snap_element = closest_ip

                #print('This is the close loop scenario')
                closest_endpoints = self.closest_endpoints(self.net_ui_context.snap_element.world_loc, 2)

                #print('these are the 2 closest endpoints, one should be snap element itself')
                #print(closest_endpoints)
                if closest_endpoints == None:
                    #we are not quite hovered_near but in snap territory
                    return

                if len(closest_endpoints) < 2:
                    #print('len of closest endpoints not 2')
                    return

                self.net_ui_context.connect_element = closest_endpoints[1]

            return


        if self.input_net.num_points == 1:  #why did we do this? Oh because there are no segments.
            self.net_ui_context.hovered_near = [None, -1]
            self.net_ui_context.snap_element = None
            return

        ##Check distance between ray_cast point, and segments
        distance_map = {}
        for seg in self.input_net.segments:  #TODO, may need to decide some better naming and better heirarchy
  
            close_loc, close_d = self.closest_point_3d_linear(seg, self.net_ui_context.ob.matrix_world * loc)
            if close_loc  == None:
                distance_map[seg] = 10000000
                continue

            distance_map[seg] = close_d

        if self.input_net.segments:
            closest_seg = min(self.input_net.segments, key = lambda x: distance_map[x])

            a = loc3d_reg2D(context.region, context.space_data.region_3d, closest_seg.ip0.world_loc)
            b = loc3d_reg2D(context.region, context.space_data.region_3d, closest_seg.ip1.world_loc)

            if a and b:  #if points are not on the screen, a or b will be None
                intersect = intersect_point_line(Vector(mouse).to_3d(), a.to_3d(),b.to_3d())
                dist = (intersect[0].to_2d() - Vector(mouse)).length_squared
                bound = intersect[1]
                if (dist < select_radius**2) and (bound < 1) and (bound > 0):
                    self.net_ui_context.hovered_near = ['EDGE', closest_seg]
                    return

        ## Multiple points, but not hovering over edge or point.
        self.net_ui_context.hovered_near = [None, -1]

        self.net_ui_context.nearest_non_man_loc()


    def hover_spline(self, select_radius=12, snap_radius=24): #TODO, these radii are pixels? Should they be settings?
        '''
        finds points/edges/etc that are near ,mouse
         * hovering happens in mixed 3d and screen space, 20 pixels thresh for points, 30 for edges 40 for non_man
        '''

        self.net_ui_context.snap_element    = None
        self.net_ui_context.connect_element = None
        self.net_ui_context.hovered_near    = [None, -1]
        self.net_ui_context.hovered_dist2D  = float('inf')
        self.net_ui_context.closest_ep      = None

        # TODO: update self.hover to use Accel2D?
        mouse = self.actions.mouse
        mouse_vec = Vector(mouse)
        context = self.context
        mx, imx = get_matrices(self.net_ui_context.ob)
        loc3d_reg2D = view3d_utils.location_3d_to_region_2d

        if self.spline_net.is_empty:
            # no points to be near
            self.net_ui_context.nearest_non_man_loc()
            return

        # ray tracing
        view_vector, ray_origin, ray_target = get_view_ray_data(context, mouse)
        #loc, no, face_ind = ray_cast(self.net_ui_context.ob, imx, ray_origin, ray_target, None)
        loc,_,face_ind = ray_cast_bvh(self.net_ui_context.bvh, imx, ray_origin, ray_target, None)

        # bail if we did not hit the source
        if face_ind == -1 or face_ind == None: return

        loc = mx * loc      # transform loc to world
        self.net_ui_context.closest_ep = self.closest_spline_endpoint(loc)

        # find length between vertex and mouse
        def dist(v): return (v - mouse_vec).length if v else float('inf')
        # find length between 2 3d points
        def dist3d(v3): return (v3 - loc).length if v3 else float('inf')

        #closest_3d_loc = min(self.spline_net.world_locs, key = dist3d)
        closest_ip = min(self.spline_net.points, key = lambda x: dist3d(x.world_loc))
        pixel_dist = dist(loc3d_reg2D(context.region, context.space_data.region_3d, closest_ip.world_loc))

        if pixel_dist < select_radius:
            # the mouse is hovering over a point
            self.net_ui_context.hovered_near = ['POINT', closest_ip]  #TODO, probably just store the actual InputPoint as the 2nd value?
            self.net_ui_context.hovered_dist2D = pixel_dist
            return

        if select_radius <= pixel_dist < snap_radius:
            # the mouse is near a point (just outside of hovering)
            #if closest_ip.is_endpoint:
                # only care about endpoints at this moment
                #self.net_ui_context.snap_element = closest_ip
                #self.net_ui_context.hovered_dist2D = pixel_dist
                #print('This is the close loop scenario')
                #closest_endpoints = self.closest_spline_endpoints(self.net_ui_context.snap_element.world_loc, 2)
                # bail if we did not find at least two nearby endpoints
                #if len(closest_endpoints) < 2: return
                #self.net_ui_context.hovered_near = ['POINT CONNECT', closest_ip]
                #self.net_ui_context.connect_element = closest_endpoints[1]
                
            
            # only care about endpoints at this moment
            self.net_ui_context.snap_element = closest_ip
            self.net_ui_context.hovered_dist2D = pixel_dist
            #print('This is the close loop scenario')
            closest_endpoints = self.closest_spline_endpoints(self.net_ui_context.snap_element.world_loc, 2)
            # bail if we did not find at least two nearby endpoints
            if len(closest_endpoints) < 2: return
            self.net_ui_context.hovered_near = ['POINT CONNECT', closest_ip]
            self.net_ui_context.connect_element = closest_endpoints[1]
                
            return

        # bail if there are only one num_points (no segments)
        if self.spline_net.num_points == 1: return

        ##Check distance between ray_cast point, and segments
        distance_map = {}
        #notice InputNet not SplineNet!  We could also check against BMFaceMap for the cut data
        for seg in self.input_net.segments:  #TODO, may need to decide some better naming and better hierarchy
            close_loc, close_d = self.closest_point_3d_linear(seg, loc)
            distance_map[seg] = close_d if close_loc else float('inf')

        if self.input_net.segments:
            closest_seg = min(self.input_net.segments, key = lambda x: distance_map[x])

            a = loc3d_reg2D(context.region, context.space_data.region_3d, closest_seg.ip0.world_loc)
            b = loc3d_reg2D(context.region, context.space_data.region_3d, closest_seg.ip1.world_loc)

            if a and b:  #if points are not on the screen, a or b will be None
                intersect = intersect_point_line(mouse_vec.to_3d(), a.to_3d(),b.to_3d())
                dist = (intersect[0].to_2d() - mouse_vec).length_squared
                bound = intersect[1]
                if (dist < select_radius**2) and (bound < 1) and (bound > 0):
                    spline_seg = closest_seg.parent_spline
                    self.net_ui_context.hovered_near = ['EDGE', spline_seg]
                    return
        ## Multiple points, but not hovering over edge or point.

        self.net_ui_context.nearest_non_man_loc()


    def hover_patches(self): #TODO, these radii are pixels? Should they be settings?
        '''
        finds the patch associated under the mouse
        '''

        
        # TODO: update self.hover to use Accel2D?
        mouse = self.actions.mouse
        mouse_vec = Vector(mouse)
        context = self.context
        mx, imx = get_matrices(self.net_ui_context.ob)
        loc3d_reg2D = view3d_utils.location_3d_to_region_2d

        if len(self.network_cutter.face_patches) == 0:
            self.net_ui_context.hovered_near = [None, None]
            return

        # ray tracing
        view_vector, ray_origin, ray_target = get_view_ray_data(context, mouse)
        #loc, no, face_ind = ray_cast(self.net_ui_context.ob, imx, ray_origin, ray_target, None)
        loc,_,face_ind = ray_cast_bvh(self.net_ui_context.bvh, imx, ray_origin, ray_target, None)

        # bail if we did not hit the source
        if face_ind == -1 or face_ind == None:
            self.net_ui_context.hovered_near = [None, None]
            return

        #find if we hit a patch
        patch = self.network_cutter.find_patch_post_cut(face_ind, mx * loc, loc)
        
        if patch != None:
            self.net_ui_context.hovered_near = ['PATCH', patch]
        else:
            self.net_ui_context.hovered_near = [None, None]
            
    
    def end_commit(self):
        print('end commit')
        self.separate_and_solidify()
        
        location = make_temp()
        server = 'http://104.196.199.206:7775/'    
        prefix = str(uuid.uuid4())[0:8]
        name = prefix + '_seg_finished.blend'
        
        if not self.context.scene.ai_settings.demo_file:
            ret_val = upload(server, location, name)  #uploads in backgorund
            
            
        if self.net_ui_context.geometry_mode == 'DESTRUCTIVE':
            bpy.data.meshes.remove(self.net_ui_context.backup_data)
            
        else:
            del_data = self.net_ui_context.ob.data
            self.net_ui_context.ob.data = self.net_ui_context.backup_data
            bpy.data.meshes.remove(del_data)
            
        self.net_ui_context.bme.free() #and other cleanup?
        finish = time.time()
        print('Entire workflow took %f seconds' % (finish - self.start_time))
        
    def end_cancel(self):
        print('end cancel')
        del_data = self.net_ui_context.ob.data  #remember we swapped the data at the init
        self.net_ui_context.ob.data = self.net_ui_context.backup_data
        bpy.data.meshes.remove(del_data)
            
        self.net_ui_context.bme.free()
        
        
    def set_final_vis(self):
        vcol = self.net_ui_context.ob.data.vertex_colors.get('patches')
        self.net_ui_context.ob.data.vertex_colors.remove(vcol)
        bpy.context.space_data.show_textured_solid = True
        for ob in bpy.data.objects:
            if "Tooth" in ob.name and "Convex" not in ob.name:
                ob.hide = True
                
        self.net_ui_context.ob.hide = True
                
                
                
                