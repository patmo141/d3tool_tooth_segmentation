'''
Created on Jun 19, 2018
@author: Patrick

I first read this method for mesh/dental mesh segmentation in the graduate
thesis of David A. Mouritsen at University of Alabam

http://www.mhsl.uab.edu/dt/2013/Mouritsen_uab_0005M_10978.pdf

The salience value chosen for this implementation is novel and not yet published.


The idea of using topological operators was described in this 2000 paper by
Christian Rossl, Leif Kobbelt, Hans-Peter Seidel
Max-Planck-Institut fur Informatik, Computer Graphics Group
https://www.aaai.org/Papers/Symposia/Spring/2000/SS-00-04/SS00-04-012.pdf

I used the following resources to help me adapt the methods to the Blender
BMesh data structure
http://www.inf.u-szeged.hu/~palagyi/skel/skel.html

for color management in the blender API
https://blenderartists.org/t/easy-way-to-access-vertex-colors-in-python-bmesh/543789/3

material management
https://blenderartists.org/t/removing-specific-material-slots/540802/13

'''
import random
import time
import uuid
import requests
import json
import os

import bpy
import bmesh
from .bmesh_fns import partition_faces_between_edge_boundaries, increase_vert_selection, decrease_vert_selection
from mathutils import Color
from .bmesh_fns import bmesh_loose_parts_verts, new_bmesh_from_bmelements
import blf

from .cloud_api.export_upload import *
from .subtrees.point_picker.functions.common import showErrorMessage

from concurrent.futures import ThreadPoolExecutor

 
def pick_verts_by_salient_color(obj, min_threshold = 0.00, max_threshold = .95):
    """Paints a single vertex where vert is the index of the vertex
    and color is a tuple with the RGB values."""

    mesh = obj.data 
    
    vcol_layer = mesh.vertex_colors.get("Salience")
    if vcol_layer == None:
        return
    
    #select and add color
    if "Salience_select" not in obj.data.vertex_colors:
        vcol = obj.data.vertex_colors.new(name = "Salience_select")
    else:
        vcol = obj.data.vertex_colors.get("Salience_select")
    
    bme = bmesh.new()
    bme.from_mesh(obj.data)
    bme.verts.ensure_lookup_table()
    bme.faces.ensure_lookup_table() 
    bme.edges.ensure_lookup_table()
    
    salience_select_color_layer = bme.loops.layers.color["Salience_select"]
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
                loop[salience_select_color_layer] = Color((1,.2, .2))  #set the color so that it can be viewed in object mode, yay
    
    for f in bme.faces:
        f.select_set(False)
    for ed in bme.edges:
        ed.select_set(False)
        
    for v in bme.verts:
        if v in to_select:
            v.select_set(True)
        else:
            v.select_set(False)   
            
    bme.select_flush_mode()
    bme.to_mesh(obj.data)
    bme.free()
    
    if "Salience" not in bpy.data.materials:
        mat = bpy.data.materials.new("Salience")
        mat.use_shadeless = True
        mat.use_vertex_color_paint = True
    else:
        mat = bpy.data.materials.get("Salience")
        mat.use_shadeless = True
        mat.use_vertex_color_paint = True
        
        
    #obj.data.vertex_colors.active = vcol
    print('setting the active vertex color')
    obj.data.vertex_colors.active = vcol
    for ind, v_color in enumerate(obj.data.vertex_colors):
        if v_color == vcol:
            break
    obj.data.vertex_colors.active_index = ind
    obj.data.vertex_colors.active = vcol
    
    print(vcol.name)
    print(obj.data.vertex_colors.active.name)
    
    #to_select = []
    #for poly in mesh.polygons:
    #    for loop_index in poly.loop_indices:
    #        loop_vert_index = mesh.loops[loop_index].vertex_index
    #        col = vcol_layer.data[loop_index].color
    #        if any([col[0] < max_threshold and col[0] > min_threshold, col[1] < max_threshold and col[1] > min_threshold, col[2] < max_threshold and col[2] > min_threshold]):
    #            to_select.append(mesh.vertices[loop_vert_index])
    
    #for v in mesh.vertices:
    #    v.select = False
    #for ed in mesh.edges:
    #    ed.select = False
    #for f in mesh.polygons:
    #    f.select = False
        
        

        
    
    
        
 
#https://blender.stackexchange.com/questions/92406/circular-order-of-edges-around-vertex
# Return edges around param vertex in counter-clockwise order

def connectedEdgesFromVertex_CCW(vertex):

    vertex.link_edges.index_update()
    first_edge = vertex.link_edges[0]

    edges_CCW_order = []

    edge = first_edge
    while edge not in edges_CCW_order:
        edges_CCW_order.append(edge)
        edge = rightEdgeForEdgeRegardToVertex(edge, vertex)

    return edges_CCW_order

# Return the right edge of param edge regard to param vertex
def rightEdgeForEdgeRegardToVertex(edge, vertex):
    right_loop = None

    for loop in edge.link_loops:
        if loop.vert == vertex:
            right_loop = loop
            break
    return loop.link_loop_prev.edge


def skeletonize_vert_set(sel_verts, allow_tails = False):

    '''
    bme  - BMesh with a selection of verts
    allow_tails - Bool.  If set to True, all peninsulas will be removed.
    '''
    
    
    if isinstance(sel_verts, list):
        skeleton = set(sel_verts)
    
    elif isinstance(sel_verts, set):
        #set are mutable, so this prevents changing the input
        skeleton = sel_verts.copy()
    
    #store the sorted 1 ring neighbors
    print('starting neighbrhood storage')
    disk_dict = {}
    for v in skeleton:
        disk_dict[v] = [ed.other_vert(v) for ed in connectedEdgesFromVertex_CCW(v)]
    
    print('finished neighbrhood storage')
    
    
    
    centers = set()  #centers, not sure we need this
    complex = set()  #all complex vertices, which shall not be removed
    to_scratch = set()  #the verts to be removed at the end of an iteration
    border = set() #all perimeter vertices
    
    
    def complexity(v):
        disk = disk_dict[v]
        changes = 0
        current = disk[-1] in skeleton
        
        for v_disk in disk:
            if (v_disk in skeleton) != current:
                changes += 1
                current = v_disk in skeleton     
        return changes
    
    def is_boundary(v):
        return not all([ed.other_vert(v) in skeleton for ed in v.link_edges])
        
        
    #cache complexity at first pass
    
    print('caching complexity')
    complexity_dict = {}
    for v in skeleton:
        if is_boundary(v):
            border.add(v)
            
            K = complexity(v)
            complexity_dict[v] = K
            if K >= 4:
                complex.add(v)
    
            
    print('finished caching complexity')
    print("There are %i complex verts" % len(complex))
    print("there are %i boundary verts" % len(border))
    
    border.difference_update(complex)
    
    print("there are %i boundary verts" % len(border))
    
    changed = True
    iterations = 0
    
    new_border = set()
    
    L = len(skeleton)  #we are going to go vert by vert and pluck it off and update locally the complexity as we go.
    
    
    while iterations < L and ((len(border) != 0) or (len(new_border) != 0))and changed == True:     
        
        iterations += 1
        v = border.pop()
        skeleton.remove(v)
        
        neighbors = disk_dict[v]
        
        for v_disk in neighbors:
            if v_disk not in skeleton: continue
        
            
            if len([ed.other_vert(v_disk) in skeleton for ed in v_disk.link_edges]) == 2:
                print('found a tail')
                if v_disk in border:
                    border.remove(v_disk)
                if v_disk in new_border:
                    new_border.remove(v_disk)
                changed = True
    
            
            if  allow_tails and v_disk in complex: continue  #complex verts are always complex
            
            K = complexity(v_disk)  #recalculate complexity
            if K >= 4:
                complex.add(v_disk)
                if v_disk in border:
                    border.remove(v_disk)
                if v_disk in new_border:
                    new_border.remove(v_disk)
                changed = True
            else:
                if v_disk not in border:
                    new_border.add(v_disk)
                changed = True
                
        if len(border) == 0 and len(new_border) != 0:
            #by doing this, we scratch all of the most outer layer
            #before proceding to the next layer
            border = new_border
            new_border = set()
  
    del disk_dict
    
    return skeleton
    
def skeletonize_selection(bme, allow_tails = False):

    '''
    bme  - BMesh with a selection of verts
    allow_tails - Bool.  If set to True, all peninsulas will be removed.
    '''
    selected_verts = [v for v in bme.verts if v.select]
    
    #store the sorted 1 ring neighbors
    print('starting neighbrhood storage')
    disk_dict = {}
    for v in selected_verts:
        disk_dict[v] = [ed.other_vert(v) for ed in connectedEdgesFromVertex_CCW(v)]
    
    print('finished neighbrhood storage')
    
    skeleton = set(selected_verts)
    
    centers = set()  #centers, not sure we need this
    complex = set()  #all complex vertices, which shall not be removed
    to_scratch = set()  #the verts to be removed at the end of an iteration
    border = set() #all perimeter vertices
    
    
    def complexity(v):
        disk = disk_dict[v]
        changes = 0
        current = disk[-1] in skeleton
        
        for v_disk in disk:
            if (v_disk in skeleton) != current:
                changes += 1
                current = v_disk in skeleton     
        return changes
    
    def is_boundary(v):
        return not all([ed.other_vert(v) in skeleton for ed in v.link_edges])
        
        
    #cache complexity at first pass
    
    print('caching complexity')
    complexity_dict = {}
    for v in skeleton:
        if is_boundary(v):
            border.add(v)
            
            K = complexity(v)
            complexity_dict[v] = K
            if K >= 4:
                complex.add(v)
    
            
    print('finished caching complexity')
    print("There are %i complex verts" % len(complex))
    print("there are %i boundary verts" % len(border))
    
    border.difference_update(complex)
    
    print("there are %i boundary verts" % len(border))
    
    changed = True
    iterations = 0
    
    new_border = set()
    
    L = len(skeleton)  #we are going to go vert by vert and pluck it off and update locally the complexity as we go.
    
    
    while iterations < L and ((len(border) != 0) or (len(new_border) != 0))and changed == True:     
        
        iterations += 1
        v = border.pop()
        skeleton.remove(v)
        
        neighbors = disk_dict[v]
        
        for v_disk in neighbors:
            if v_disk not in skeleton: continue
        
            
            if len([ed.other_vert(v_disk) in skeleton for ed in v_disk.link_edges]) == 2:
                print('found a tail')
                if v_disk in border:
                    border.remove(v_disk)
                if v_disk in new_border:
                    new_border.remove(v_disk)
                changed = True
    
            
            if  allow_tails and v_disk in complex: continue  #complex verts are always complex
            
            K = complexity(v_disk)  #recalculate complexity
            if K >= 4:
                complex.add(v_disk)
                if v_disk in border:
                    border.remove(v_disk)
                if v_disk in new_border:
                    new_border.remove(v_disk)
                changed = True
            else:
                if v_disk not in border:
                    new_border.add(v_disk)
                changed = True
                
        if len(border) == 0 and len(new_border) != 0:
            #by doing this, we scratch all of the most outer layer
            #before proceding to the next layer
            border = new_border
            new_border = set()
            
    print('There are %i complex verts after pruning' % len(complex))
    
    for v in bme.verts:
        v.select_set(False)
    for ed in bme.edges:
        ed.select_set(False)
    for f in bme.faces:
        f.select_set(False)
    bme.select_flush_mode()
    
    for v in skeleton:
        v.select_set(True)       

    print("There are %i verts to scratch" % len(to_scratch))
  
    del disk_dict

#TODO Where to put this? Its customized for specificly this case
#but could be useful for others in a less specific format
def partition_and_color(ob, context, sep, merge_small = True, merge_limit = 3000):  
    
    # get mat create.
    mat = bpy.data.materials.get("Partition")
    if not mat:
        mat = bpy.data.materials.new("Partition")
        mat.use_vertex_color_paint = True
    
    if "Partition" not in ob.data.vertex_colors:
        vcol = ob.data.vertex_colors.new(name = "Partition")
    else:
        vcol = ob.data.vertex_colors.get("Partition")
            
    bme = bmesh.new()
    bme.from_mesh(ob.data)
    
    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    
    perim_verts  = set([v for v in bme.verts if v.select])
    perim_edges = set([ed for ed in bme.edges if (ed.verts[0] in perim_verts and ed.verts[1] in perim_verts)])
    
    
    print('starting island region growing')
    
    face_islands = partition_faces_between_edge_boundaries(bme, [], perim_edges, max_iters = 100)
    
    face_islands.sort(key = len)
    
    print('%i islands were found' % len(face_islands))
    
    #for li in me.polygons[0].loop_indices:
    #    me.vertex_colors.active.data[li].color
    
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
        
         
    for isl in face_islands:
        rgb = [random.random() for i in range(3)]
        
        for f in isl:
            mface = ob.data.polygons[f.index]  #bmesh and mesh need to be synced
            for idx in mface.loop_indices:
                vcol.data[idx].color = rgb
    
    if sep:
        for i, isl in enumerate(face_islands):
            
            out_bme = new_bmesh_from_bmelements(isl)
            new_me = bpy.data.meshes.new(ob.name + str(i))
            new_ob = bpy.data.objects.new(ob.name + str(i), new_me)
            context.scene.objects.link(new_ob)
            new_ob.matrix_world = ob.matrix_world
            out_bme.to_mesh(new_me)
            out_bme.free()
    #todo make that vertex color active
    
    
    #bme.to_mesh(C.object.data)
    bme.free()
    
    ob.data.vertex_colors.active = vcol
    for ind, v_color in enumerate(ob.data.vertex_colors):
        if v_color == vcol:
            break
    ob.data.vertex_colors.active_index = ind
    

def dilate_erode(bme, selected_verts, dilations, erosions, dilate_first = True):
    if dilate_first:
        first_fn = increase_vert_selection
        first_steps = dilations
            
        second_fn = decrease_vert_selection
        second_steps = erosions
            
    else:
        first_fn = decrease_vert_selection
        first_steps = erosions
            
        second_fn = increase_vert_selection
        second_steps = dilations
    
    
    updated_selection = first_fn(bme, selected_verts, first_steps)
    final_selection = second_fn(bme, updated_selection, second_steps)
    
    return final_selection


   
#simple test operator   

def ping_server(job_id):
    url = "http://104.196.199.206:7777/api/job_details?job_id=" + job_id #1569930574014
    ret_json = json.loads(requests.get(url).text)
    return ret_json
    
def draw_callback_px(self, context):

    font_id = 0  # XXX, need to find out how best to get this.
    # draw some text
    blf.position(font_id, 25, 250, 0)
    blf.size(font_id, 30, 72)
    blf.draw(font_id, 'Press Escape to cancel')
    
    
    blf.position(font_id, 25, 200, 0)
    blf.size(font_id, 30, 72)
    blf.draw(font_id, self.msg)


class AITeeth_OT_cloud_process(bpy.types.Operator):
    """Upload model to cloud process feature detection"""
    bl_idname = "ai_teeth.cloud_preprocess_model"
    bl_label = "Cloud Process Salience"

    _timer = None

    @classmethod
    def poll(cls, context):
        if not context.object: return False
        if len(context.object.children) == 0: return False  #seeds
        if "Salience" in context.object.data.vertex_colors: return False #already did it
        return True
        
    def invoke(self, context, event):
        
        
        
        
        obs = [ob for ob in bpy.data.objects if ob.type == 'MESH']
        
        
        max_ob = max(obs, key = lambda x: len(x.data.vertices))
        if len(max_ob.data.vertices) > 250000:
            showErrorMessage('Model has too many vertices!  Decimate to below 250,000 verts')
            return {'CANCELLED'}
        
        if len([ob for ob in obs if "seed" not in ob.name])>1:
            showErrorMessage('There are too many models in the scene!  Make sure to only have 1 model to process at a time')
            return {'CANCELLED'}
        
        
        if not context.scene.ai_settings.accept_ua:
            showErrorMessage('You must accept the User Agreement to proceed!')
            return {'CANCELLED'}
        
        if not context.scene.ai_settings.acknowledge_upload:
            showErrorMessage('You must acknowledge model will be uploaded')
            return {'CANCELLED'}
        
        if not context.scene.ai_settings.certify_anonymous:
            showErrorMessage('You must certify that the models are anonymous')
            return {'CANCELLED'}
        
        
        self.msg = 'Uploading File...'
        
        wm = context.window_manager
        self._timer = wm.event_timer_add(.5, context.window)
        wm.modal_handler_add(self)
        args = (self, context)
        self._handle = bpy.types.SpaceView3D.draw_handler_add(draw_callback_px, args, 'WINDOW', 'POST_PIXEL')

        
        self.executor = ThreadPoolExecutor()  
        self.future = self.executor.submit(self.upload_job)
                
        self.start_time = time.time()
        self.last_check = time.time()
        
        
        self.job_id = ''
        self.file_name = ''
        return {'RUNNING_MODAL'}
    
    def modal(self, context, event):
        context.area.tag_redraw()
        
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self.cancel(context)
            return {'CANCELLED'}

        
        if event.type == 'TIMER':
            time_elapsed = str(time.time() - self.start_time)[0:4]
            if self.future.done():
                
                (j_id, file_name, result) = self.future.result()
                print(j_id, file_name, result)
                if result == 'SUCCESS':
                    self.job_id = j_id 
                    self.file_name = file_name
                
                else:
                    self.cancel(context)
            else:
                
                self.msg = 'Uploading File...' + time_elapsed + 'sec'
                return {'RUNNING_MODAL'} 
               
            if (time.time() - self.last_check) < 3.0: return {'RUNNING_MODAL'}
            # change theme color, silly!
            ret_dict = ping_server(self.job_id)
          
            print(ret_dict)
            
            self.msg = "Job is " + ret_dict['status'] + " on server..." + time_elapsed + 'sec'
            
            if ret_dict['status'] == 'error':
                self.cancel(context)
                
            elif ret_dict['status'] == 'finished':
                
                #download_the_file
                server = 'http://104.196.199.206:7776/download'
                dl_name = '{}{}'.format("computed_", self.file_name)
                print(dl_name)
                downloaded_file_path = download_nonthreaded(server, dl_name)
                print(downloaded_file_path)
                tmp_path, cur_file = define_paths()
               
                fullBlendPath = os.path.join(tmp_path, dl_name)
                
                
                #assets_path = join(dirname(abspath(__file__)), "data_assets")
                #fullBlendPath = join(assets_path, 'articulator.blend')
                #print(assets_path)
                print(fullBlendPath)
                print(os.path.exists(fullBlendPath))
    
    
                ob_orig = context.object
                ob_name = ob_orig.name
                me = ob_orig.data
                
                children = [child for child in ob_orig.children]
                context.scene.objects.active = None
                context.scene.objects.unlink(ob_orig)
                bpy.data.objects.remove(ob_orig)
                bpy.data.meshes.remove(me)
                
                obpath = fullBlendPath + '\\Object\\'
                bpy.ops.wm.append(filepath = fullBlendPath,
                                          directory = obpath,
                                          filename = ob_name)
                
                ob = bpy.data.objects.get(ob_name)
                ob.select = True
                context.scene.objects.active = ob
                
                for child in children:
                    child.parent = ob
                #orig_data_names = lambda: None
                #with bpy.data.libraries.load(fullBlendPath) as (data_from, data_to):
                #    for attr in dir(data_to):
                #        setattr(data_to, attr, getattr(data_from, attr))
                #        attrib = getattr(data_from, attr)
                #        if len(attrib) > 0:
                #            setattr(orig_data_names, attr, attrib.copy())
                
                self.execute(context)
                bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
                context.window_manager.event_timer_remove(self._timer)
                return {'FINISHED'}

        return {'RUNNING_MODAL'}

    def execute(self, context):
        print('WE DID IT')
        return {'FINISHED'}

    def cancel(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self._timer)
        bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        return {'CANCELLED'}
    
    
    def upload_job(self):
        
        start = time.time()
        location = make_temp()
        server = 'http://104.196.199.206:7776/'
            
        prefix = str(uuid.uuid4())[0:8]
        name = prefix + '_segmentation.blend'
        ret_val = upload_nonthreaded(server, location, name)
            
        if 'FAILED' in ret_val:
            return (None, None, 'FAILED')
              
        job_submit_url =  "http://104.196.199.206:7777/api/blender_job?name={}&input={}".format(name, name)    
        job_id = requests.get(job_submit_url).text
    
        return (job_id, name, 'SUCCESS')
            
class AITeeth_OT_select_verts_by_salience_color(bpy.types.Operator):
    """Select mesh vertice by the vertex color"""
    bl_idname = "cut_mesh.select_verts_salience_color"
    bl_label = "Cut Mesh Select salience Occlusion"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    min_threshold = bpy.props.FloatProperty(default = 0.0)
    max_threshold = bpy.props.FloatProperty(default = 0.95)
    def execute(self,context):
        if context.object:
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode = 'OBJECT')
            
            pick_verts_by_salience_color(context.object,min_threshold = self.min_threshold, max_threshold = self.max_threshold)
            
        return {'FINISHED'}


class AITeeth_OT_dilate_erode_selection(bpy.types.Operator):
    """Grow and shrink selection iteratively"""
    bl_idname = "cut_mesh.dilate_and_erode"
    bl_label = "Cut Mesh Dilate and Erode Selection"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    dilate_first = bpy.props.BoolProperty(default = True)
    dilation_steps = bpy.props.IntProperty(default = 2)
    erosion_steps = bpy.props.IntProperty(default = 2)
    finalize = bpy.props.BoolProperty(default = False)
    
    def invoke(self,context, event):
        
        return context.window_manager.invoke_props_dialog(self, 200)
    
    def execute(self,context):
        
        
        bme = bmesh.new()
        bme.from_mesh(context.object.data)
        
        selected_verts = [v for v in bme.verts if v.select]
        
        final_sel = dilate_erode(bme, selected_verts, self.dilation_steps, self.erosion_steps, dilate_first = self.dilate_first)
        
        if "Salience_dilate_erode" not in bme.loops.layers.color:
            vcol_layer = bme.loops.layers.color.new("Salience_dilate_erode")
        else:
            vcol_layer = bme.loops.layers.color["Salience_dilate_erode"]
            
        white = Color((1.0,1.0,1.0))
        red = Color((1.0, .2, .2))
        
        for v in bme.verts:
            for f in v.link_faces:
                for loop in f.loops:
                    if loop.vert in final_sel:
                        loop[vcol_layer] = red
                    else:
                        loop[vcol_layer] = white
        
        if self.finalize:
            for v in bme.verts:
                if v in final_sel:
                    v.select_set(True)
                else:
                    v.select_set(False)
            bme.select_flush_mode()
            
        bme.to_mesh(context.object.data)
        bme.free()
        for i, vc in enumerate(context.object.data.vertex_colors):
            if vc.name == "Salience_dilate_erode":
                context.object.data.vertex_colors.active = vc
                context.object.data.vertex_colors.active_index = i
                break
        
        return {'FINISHED'}
    
    
class AITeeth_OT_skeletonize_selection(bpy.types.Operator):
    """Skeletonize Selection to one vertex width path"""
    bl_idname = "cut_mesh.skeletonize_selection"
    bl_label = "Cut Mesh Skeletonize Selection"
    bl_options = {'REGISTER', 'UNDO'}
    
    allow_tails = bpy.props.BoolProperty(name = 'Allow Tails', default = False, description = 'If False, will only allow loops')
    def execute(self,context):
        
        if context.mode == 'OBJECT':
            bme = bmesh.new()
            bme.from_mesh(bpy.context.object.data)
            bme.verts.ensure_lookup_table()
            bme.edges.ensure_lookup_table()
            bme.faces.ensure_lookup_table()
        
        elif context.mode == 'EDIT_MESH':
            bme = bmesh.from_edit_mesh(context.object.data)
            
        else:
            self.report({'ERROR'}, 'Must be in Object or Edit Mode')
               
        skeletonize_selection(bme, allow_tails = self.allow_tails)
        
        if context.mode == 'OBJECT':
            bme.to_mesh(context.object.data)
            bme.free()
    
        else:
            bmesh.update_edit_mesh(bpy.context.object.data)
    
        return {'FINISHED'}

class AITeeth_OT_remove_small_parts_selection(bpy.types.Operator):
    """Remove the smallest disconnected pieces of selection"""
    bl_idname = "cut_mesh.remove_small_selections"
    bl_label = "Cut Mesh Remove Small Selection"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    def execute(self,context):
        
        if bpy.context.mode == 'OBJECT':
            bme = bmesh.new()
            bme.from_mesh(bpy.context.object.data)
            bme.verts.ensure_lookup_table()
            bme.edges.ensure_lookup_table()
            bme.faces.ensure_lookup_table()
        
        elif context.mode == 'EDIT':
            bme = bmesh.from_edit_mesh(bpy.context.object.data)
            
        else:
            self.report({'ERROR'}, 'Must be in Object or Edit Mode')
        
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        selected_verts = [v for v in bme.verts if v.select]     
        islands = bmesh_loose_parts_verts(bme, selected_verts, max_iters = 100)
        
        
        biggest = max(islands, key = len)
        
        
        if "Salience_select" in bme.loops.layers.color:
            salience_select_color_layer = bme.loops.layers.color["Salience_select"]
            red = Color((1,0,0))
            white = Color((1,1,1))
            
            for v in bme.verts:
                if v in biggest:
                    v.select_set(True)
                    for f in v.link_faces:
                        for loop in f.loops:
                            if loop.vert == v:
                                loop[salience_select_color_layer] = red

                else:
                    v.select_set(False)
                    for f in v.link_faces:
                        for loop in f.loops:
                            if loop.vert == v:
                                loop[salience_select_color_layer] = white

        if bpy.context.mode == 'OBJECT':
            bme.to_mesh(bpy.context.object.data)
            bme.free()
    
        else:
            bmesh.update_edit_mesh(bpy.context.object.data)
    
        return {'FINISHED'}
    
class AITeeth_OT_partition_and_color(bpy.types.Operator):
    """Color the object regions along the boundaries"""
    bl_idname = "cut_mesh.partition_and_color"
    bl_label = "Cut Mesh Partition and Color"
    bl_options = {'REGISTER', 'UNDO'}
    
    separate = bpy.props.BoolProperty(default = False, description = "Split out regions into new objects")
    def execute(self,context):
        
        partition_and_color(context.object, context, sep = self.separate)
        context.space_data.viewport_shade = 'SOLID'
        context.space_data.show_textured_solid = True
        return {'FINISHED'}
    
def register():
    #bpy.utils.register_class(AI_OT_preprocess)
    bpy.utils.register_class(AITeeth_OT_cloud_process)
    #bpy.utils.register_class(AITeeth_OT_select_verts_by_salience_color)
    #bpy.utils.register_class(AITeeth_OT_remove_small_parts_selection)
    #bpy.utils.register_class(AITeeth_OT_dilate_erode_selection)
    #bpy.utils.register_class(AITeeth_OT_skeletonize_selection)
    #bpy.utils.register_class(AITeeth_OT_partition_and_color)
    
def unregister():
    #bpy.utils.unregister_class(AI_OT_preprocess)
    bpy.utils.unregister_class(AITeeth_OT_cloud_process)
    #bpy.utils.unregister_class(AITeeth_OT_select_verts_by_salience_color)
    #bpy.utils.unregister_class(AITeeth_OT_remove_small_parts_selection)
    #bpy.utils.unregister_class(AITeeth_OT_dilate_erode_selection)
    #bpy.utils.unregister_class(AITeeth_OT_skeletonize_selection)
    #bpy.utils.unregister_class(AITeeth_OT_partition_and_color)
    
