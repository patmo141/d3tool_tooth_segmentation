'''
Created on Nov 27, 2019

@author: Patrick
'''
import math
import time

import bpy
import bmesh
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

from d3lib.bmesh_utils.bmesh_delete import bmesh_fast_delete, bmesh_delete
from d3guard.subtrees.metaballs.vdb_tools import remesh_bme
from d3guard.subtrees.metaballs.vdb_remesh import read_bmesh, convert_vdb

from ..subtrees.bmesh_utils.bmesh_utilities_common import bme_rip_vertex, bbox_center, bound_box_bmverts, grow_selection
from ..subtrees.bmesh_utils.bmesh_utilities_common import edge_loops_from_bmedges_topo, offset_bmesh_edge_loop, collapse_ed_simple
from ..subtrees.geometry_utils.loops_tools import relax_loops_util
from ..subtrees.geometry_utils.transformations import clockwise_loop
from ..bmesh_fns import bmesh_loose_parts_faces, increase_vert_selection, decrease_vert_selection
from ..tooth_numbering import data_tooth_label
from .. import tooth_numbering

from .get_reduction_shell import make_reduction_shells
from ..subtrees.bmesh_utils.bmesh_utilities_common import new_bmesh_from_bmelements,partition_faces_between_edge_boundaries
    


def fast_bridge(bme, loop0, loop1, Z):
    
    if clockwise_loop(loop0[0], Z) != clockwise_loop(loop1[0], Z):
        loop1[0].reverse()
    
    N0 = len(loop0[0])
    N1 = len(loop1[0])
     
    print('\n\nTHERE ARE %i, %i verts\n\n' % (N0, N1))
    def next_v0(i):
        return int(math.fmod(i + 1, N0))
        
    def next_v1(i):
        return int(math.fmod(i + 1, N1))
        
    i0 = 0
    i1 = 0
    v0 = loop0[0][i0]
    v1 = loop0[0][next_v0(i0)]
    
    v2 = min(loop1[0], key = lambda x: (x.co - v0.co).length)
    offset = loop1[0].index(v2)
    v3 = loop1[0][next_v1(offset)]
    
    
    #for v in [v0, v1]:#, v3, v1]:
    #    v.select_set(True)
        
        
    new_fs = []
    iteration = 0
    while (i0 < N0 or i1 < N1) and iteration < 2000:
        iteration += 1
        
        #Tri A
        #v0--v1----vnext0
        #|  /    
        #| /  
        #v2--------v3
        
        #Tri B
        #v0------v1
        #| \    
        #|  \  
        #v2--v3----vnext1
        
        #Quad C
        #v0------v1----vnext0
        #|      /
        #|     /
        #v2---v3-----vnext1
        
        
        l_quad = (v3.co - v1.co).length
        l_tri_a = (v2.co - v1.co).length   #v0, v2, v1
        l_tri_b = (v0.co - v3.co).length   #v0, v2, v3
        
        end_type = None
        if l_tri_a <= l_quad and l_tri_a < l_tri_b:
            
            if len(set([v0, v1, v2])) != 3:
                print('FAILUER')
                continue
            
            bme.faces.new((v0, v2, v1))
            end_type = "Tri A"
            print('new_face TRIANGLE A iteration %i %i %i' % (iteration, i0, i1))
            v0 = loop0[0][next_v0(i0)]
            if i0 <= N0:
                i0 += 1
                v1 = loop0[0][next_v0(i0)]
                
            continue
            
        elif l_tri_b <= l_quad and l_tri_b < l_tri_a:
            
            print('new_face TRIANGLE B iteration  %i %i %i' % (iteration, i0, i1))
            if len(set([v0, v2, v3])) != 3:
                print('FAILUER')
                continue
            bme.faces.new((v0, v2, v3))
            end_type = "Tri B"
            v2 = loop1[0][next_v1(i1 + offset)]
            if i1 <= N1:
                i1 += 1
                v3 = loop1[0][next_v1(i1 + offset)]
                
            continue
        
        elif l_quad <= l_tri_a and l_quad <= l_tri_b:
            
            print('new_face QUAD B iteration %i %i %i' % (iteration, i0, i1))
            if len(set([v0, v1, v2, v3])) != 4:
                print('FAILUER')
            bme.faces.new((v0, v2, v3, v1))
            end_type = "QUAD"
            v0 = loop0[0][next_v0(i0)]
            if i0 <= N0:
                i0 += 1
                v1 =  loop0[0][next_v0(i0)]
            
            v2 = loop1[0][next_v1(i1 + offset)]
            if i1 <= N1:
                i1 += 1
                v3 = loop1[0][next_v1(i1 + offset)]
            
        else:
            print('NONE OF THESE THINGS ARE TRUE? %i %i %i' % (iteration, i0, i1))
            break
    
    v0.select_set(True)
    v1.select_set(True)
    v2.select_set(True)
    v3.select_set(True)
    
    print('END TYPE/LAST POLY %s %i %i %i' % (end_type, iteration, i0, i1))
    print(v0, v1, v2, v3)
    
    vs_final = set([v0, v1, v2, v3])
    final_faces = set()
    for v in [v0, v1, v2, v3]:
        for f in v.link_faces:
            if all(vl in vs_final for vl in f.verts):
                final_faces.add(f)
    if v0 == v1:
        try:
            bme.faces.new(bme.faces.new((v0, v2, v3)))
            print('FACE A END')
        except:
            print('already face A')
    if v2 == v3:
        try:
            bme.faces.new((v0, v2, v1))
            print('FAACE B END')
        except:
            print('already face B')
            
            
    return
        
def simple_angle(v, Z = None):
    
    va = v.link_edges[0].other_vert(v)
    vb = v.link_edges[1].other_vert(v)
    
    Va = va.co - v.co
    Vb = vb.co - v.co
    
    if Z:
        Va = Va - Va.dot(Z) * Z
        Vb = Vb - Vb.dot(Z) * Z
    
    Va.normalize()
    Vb.normalize()
    if Va.dot(Vb) < .01:
        return math.pi
    
    a_mag = Va.cross(Vb)    
    return math.asin(a_mag.length)

def duplicate_loop(bme, loop):
    verts = loop[0]
    edges = loop[1]
    
    new_verts_map = {}
    new_verts_list = []
    for v in verts:
        v_new =  bme.verts.new(v.co)
        new_verts_map[v] = v_new
        new_verts_list.append(v_new)
    
    new_edges = []
    for ed in edges:
        new_edges.append(bme.edges.new([new_verts_map[ed.verts[0]], new_verts_map[ed.verts[1]]]))
        
    return [new_verts_list, new_edges]
    
    
def collapse_to_resolution(bme, ed_loop, length):
    
    #collapse to 0.5mm resolution
    untested_edges = set(ed_loop)
    final_edges = set()
    while len(untested_edges):
        ed = untested_edges.pop()
        
        if ed.calc_length() < length:
            eds_new, eds_removed  = collapse_ed_simple(bme, ed)
            untested_edges.update(eds_new)
            untested_edges.difference_update(eds_removed)
            final_edges.difference_update(eds_removed) #new edges may be subsequently removed
     
        else: 
            final_edges.add(ed)
    
    dup_edges = list(final_edges)
    
    bme.verts.index_update()
    bme.edges.index_update()
    bme.verts.ensure_lookup_table()        
    bme.edges.ensure_lookup_table()
    
    loops = edge_loops_from_bmedges_topo(bme, dup_edges)
    biggest_loop = max(loops, key = lambda x: len(x[0])) 
    return biggest_loop
    



def create_open_shell(bme, ob, sub_g): 

    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    bme.verts.index_update() 
    
    perim_edges = [ed for ed in bme.edges if len(ed.link_faces) == 1]
    loops = edge_loops_from_bmedges_topo(bme, perim_edges)
    biggest_loop = max(loops, key = lambda x: len(x[0]))  #THERE MIGHT BE two loops
    
    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    bme.verts.index_update() 
    
    new_loop = duplicate_loop(bme, biggest_loop)
    
    
    smooth_verts = increase_vert_selection(biggest_loop[0], iterations = 4)
    
    ###
    ###  RELAX AND COLLAPSE THE LOOP
    ###
    #relax the border a little and resnap it
    for ind in range(0,5):
        bmesh.ops.smooth_vert(bme, factor = 0.5, verts = new_loop[0], use_axis_x = True, use_axis_y = True, use_axis_z = True)
        bmesh.ops.smooth_vert(bme, factor = 0.5, verts = biggest_loop[0], use_axis_x = True, use_axis_y = True, use_axis_z = True)   
    
    #snap it
    for v in new_loop[0]:
        res, loc, no, ind = ob.closest_point_on_mesh(v.co)
        v.co = loc + .1 * no
    #relax it again
    relax_loops_util(bme, new_loop[1], 5, influence = 1.0)
    
    new_loop = collapse_to_resolution(bme, new_loop[1], .25)
     
    #extrude downlard .5mm
    for v in new_loop[0]:
        v.co += Vector((0,0,sub_g))
        
    #connect   
    fast_bridge(bme, biggest_loop, new_loop, Vector((0,0,1)))
    
    for ind in range(0,10):
        bmesh.ops.smooth_vert(bme, factor = 0.5, verts = list(smooth_verts), use_axis_x = True, use_axis_y = True, use_axis_z = True)   
    
    
    bmesh.ops.recalc_face_normals(bme, faces = bme.faces[:])
           
def make_root_prep(ob, flat_root = True, root_length = 8.0,
                                        prep_width = .75, 
                                        taper = 7.0, 
                                        sub_g = .15,
                                        angle_filtering = True):
    
    new_name = ob.name.split(' ')[0] + ' root_prep' 
    if new_name in bpy.data.objects:
        new_ob = bpy.data.objects.get(new_name)
        new_me = new_ob.data
        new_ob.hide = False
    else:
        new_me = bpy.data.meshes.new(new_name)
        new_ob = bpy.data.objects.new(new_name, new_me)
        new_ob.parent = ob
        new_ob.matrix_world = ob.matrix_world
        bpy.context.scene.objects.link(new_ob)
       
 
    new_name = ob.name.split(' ')[0] + ' thimble_prep' 
    
    if new_name in bpy.data.objects:
        thimble_ob = bpy.data.objects.get(new_name)
        thimble_me = new_ob.data
        
    else:
        thimble_me = bpy.data.meshes.new(new_name)
        thimble_ob = bpy.data.objects.new(new_name, thimble_me)
        thimble_ob.parent = ob
        thimble_ob.matrix_world = ob.matrix_world
        bpy.context.scene.objects.link(thimble_ob)
        
    new_name = ob.name.split(' ')[0] + ' open_shell' 
    
    if new_name in bpy.data.objects:
        anatomic_ob = bpy.data.objects.get(new_name)
        anatomic_me = new_ob.data
        
    else:
        anatomic_me = bpy.data.meshes.new(new_name)
        anatomic_ob = bpy.data.objects.new(new_name, anatomic_me)
        anatomic_ob.parent = ob
        anatomic_ob.matrix_world = ob.matrix_world
        bpy.context.scene.objects.link(anatomic_ob)
        
        
        
    new_name = ob.name.split(' ')[0] + ' margin_line' 
    
    if new_name in bpy.data.objects:
        margin_ob = bpy.data.objects.get(new_name)
        margin_me = margin_ob.data
        
    else:
        margin_me = bpy.data.meshes.new(new_name)
        margin_ob = bpy.data.objects.new(new_name, margin_me)
        margin_ob.parent = ob
        margin_ob.matrix_world = ob.matrix_world
        bpy.context.scene.objects.link(margin_ob)
            
    bme = bmesh.new()
    bme.from_mesh(ob.data)
    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    
    bvh = BVHTree.FromBMesh(bme)  #need this for some proximity stuff
    #####
    ## COLLECT THE UNDRESIDE VERTS ###
    ###
    vg = ob.vertex_groups.get('Under Side')
    bme_inds = set()
    for v in ob.data.vertices:
        try:
            vg.weight(v.index)
            bme_inds.add(v.index)
        except:
            pass
    inner_verts = set([bme.verts[i] for i in bme_inds])
    
    #filter verst by normal
    
    if angle_filtering:
        to_remove = []
        for v in inner_verts:
            if abs(v.normal.dot(Vector((0,0,1)))) < 0.3:
                to_remove.append(v)
    
                
        inner_verts.difference_update(to_remove)
    print('There are %i inner verts' % len(inner_verts))
    
    inner_verts = increase_vert_selection(inner_verts, iterations = 2)
    print('There are %i inner verts' % len(inner_verts))
    inner_verts = decrease_vert_selection(inner_verts, iterations = 2)
    
    print('There are %i inner verts' % len(inner_verts))
    print('There are %i total verts' % len(bme.verts))
    ###
    ### DELETE THE OTHER GEOMETRY NOT IN UNDERSIDE
    ###
    inner_fs = set()
    for v in inner_verts:
        inner_fs.update(v.link_faces[:])
   
   
    inner_eds = set() 
    for f in inner_fs:
        inner_eds.update(f.edges)
    
    perim_eds = [ed for ed in inner_eds if len([f for f in ed.link_faces if f in inner_fs]) == 1] 
    
    perim_loops = edge_loops_from_bmedges_topo(bme, perim_eds) 
    if len(perim_loops) > 1:
        islands = partition_faces_between_edge_boundaries(bme, inner_fs, perim_eds)
        inner_fs = max(islands, key = len)
        
        
    outer_fs = set(bme.faces[:]) - inner_fs #set(biggest_island)
    
    
    bme_shell = new_bmesh_from_bmelements(outer_fs)
    create_open_shell(bme_shell, ob, sub_g)
    bme_shell.to_mesh(anatomic_me)
    bme_shell.free()
    
    bmesh_delete(bme, list(outer_fs), "FACES")
    
    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    bme.verts.index_update()
    
    ####
    ### DELETE EVERYTHING EXCEPT THE PERIMETER LOOP
    ###
    print('finding edge loops')
    perim_edges = [ed for ed in bme.edges if len(ed.link_faces) == 1]
    loops = edge_loops_from_bmedges_topo(bme, perim_edges)
    
    print('THERE ARE %i LOOPS' % len(loops))
    biggest_loop = max(loops, key = lambda x: len(x[0]))  #THERE MIGHT BE two loops
    
    del_set = set(bme.verts[:]) - set(biggest_loop[0])
    bmesh_delete(bme, list(del_set), 'VERTS')
    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    bme.verts.index_update()  
    
    ###  RELAX AND COLLAPSE THE LOOP
    ###
    #relax the border a little and resnap it
    relax_loops_util(bme, bme.edges[:], 5, influence = 1.0)
    #snap it
    for v in biggest_loop[0]:
        res, loc, no, ind = ob.closest_point_on_mesh(v.co)
        v.co = loc + .1 * no
    #relax it again
    relax_loops_util(bme, biggest_loop[1], 5, influence = 1.0)
    
    biggest_loop = collapse_to_resolution(bme, biggest_loop[1], .25)
    
    relax_loops_util(bme, bme.edges[:], 5, influence = 1.0)
    for v in biggest_loop[0]:
        res, loc, no, ind = ob.closest_point_on_mesh(v.co)
        v.co = loc + .1 * no
    relax_loops_util(bme, bme.edges[:], 5, influence = 1.0)
    
    cej_com = bbox_center(bound_box_bmverts(biggest_loop[0]))

    for v in biggest_loop[0]:
        v.co += sub_g * Vector((0,0,1))
    bme.to_mesh(margin_me)
    
    #make the prep shoulder
    prep_loop = duplicate_loop(bme, biggest_loop)
    n_iters = math.ceil(prep_width/.2)
    for n in range(0, n_iters):
        #tip_loop = duplicate_loop(bme, tip_loop)
        offset_bmesh_edge_loop(bme, prep_loop[1], Vector((0,0,1)), -prep_width/n_iters, debug = True)
        
        
        bmesh.ops.smooth_vert(bme, factor = 0.5, verts = prep_loop[0], use_axis_x = True, use_axis_y = True)
        sharp_verts = [v for v in prep_loop[0] if simple_angle(v, Z = Vector((0,0,1))) < math.pi/1.8]
        smooth_iters = 0
        while len(sharp_verts) and smooth_iters < 10:
            smooth_iters += 1
            bmesh.ops.smooth_vert(bme, factor = 1.0, verts = sharp_verts, use_axis_x = True, use_axis_y = True)    
        if smooth_iters > 0: 
            print('SMOOTHED SHARP VERTS IN %i iters' % smooth_iters)
        #relax_loops_util(bme, tip_loop[1], 1 , influence = 1.0)
        prep_loop = collapse_to_resolution(bme, prep_loop[1], .15)
        
    #create and taper the prep top
    theta = taper/180 * math.pi
    step = 1.0 * math.tan(theta)  #make a 2.0mm prep height
    top_loop = duplicate_loop(bme, prep_loop)
    n_iters = math.ceil(step/.2)
    for n in range(0, n_iters):
        #tip_loop = duplicate_loop(bme, tip_loop)
        offset_bmesh_edge_loop(bme, top_loop[1], Vector((0,0,1)), -step/n_iters, debug = True)
        
        
        bmesh.ops.smooth_vert(bme, factor = 0.5, verts = top_loop[0], use_axis_x = True, use_axis_y = True)
        sharp_verts = [v for v in top_loop[0] if simple_angle(v, Z = Vector((0,0,1))) < math.pi/2]
        print('THERE ARE %i sharp verts' % len(sharp_verts))
        #for v in sharp_verts:
        #    v.select_set(True)
        bmesh.ops.smooth_vert(bme, factor = 1.0, verts = sharp_verts, use_axis_x = True, use_axis_y = True)    
        
        #relax_loops_util(bme, tip_loop[1], 1 , influence = 1.0)
        top_loop = collapse_to_resolution(bme, top_loop[1], .2)
    
    #bmesh.ops.bridge_loops(bme, edges = prep_loop[1] + top_loop[1])
    
    fast_bridge(bme, prep_loop, top_loop, Vector((0,0,1)))
    
    
    for v in top_loop[0]:
        v.co[2] -= 3.0
    
    excl_edges = set(top_loop[1] + prep_loop[1])    
    for v in top_loop[0]:
        eds_project = [ed for ed in v.link_edges if ed not in excl_edges]
        if len(eds_project) == 0: 
            print('/n/n/BAD VERT NO EDGE/n/n/')
        
        vecs_project = [v.co - ed.other_vert(v).co for ed in eds_project]
        vec = Vector((0,0,0))
        for vp in  vecs_project:
            vec += 1/len(vecs_project) * vp
        
        loc, no, ind, d = bvh.ray_cast(v.co, Vector((0,0,-1)))
        if loc:
            v.co = loc + Vector((0,0,1))
            
        else:
            loc, no, ind, d = bvh.ray_cast(v.co, Vector((0,0,1)))
            if loc:
                v.co = loc + Vector((0,0,1))
        
    #bmesh.ops.bridge_loops(bme, edges = biggest_loop[1] + prep_loop[1])
    fast_bridge(bme, biggest_loop, prep_loop, Vector((0,0,1)))
    
    bmesh.ops.recalc_face_normals(bme, faces = bme.faces[:])
    shoulder_verts = set(biggest_loop[0] + prep_loop[0])
    shoulder_fs = [f for f in bme.faces if all([v in shoulder_verts for v in f.verts[:]])]
    if shoulder_fs[0].normal.dot(Vector((0,0,1))) > 0:
        for f in bme.faces:
            f.normal_flip()
    
    bme.to_mesh(thimble_me)
    
        
    tip_loop = duplicate_loop(bme, biggest_loop)
    tip_loop = collapse_to_resolution(bme, tip_loop[1], .25)
    #relax_loops_util(bme, tip_loop[1], 10 , influence = 1.0)   
    if taper > 1:
        theta = taper/180 * math.pi
        step = root_length * math.tan(theta)
        n_iters = max(3, math.ceil(step/.05))
        print(n_iters)
        for n in range(0, n_iters):
            #tip_loop = duplicate_loop(bme, tip_loop)
            offset_bmesh_edge_loop(bme, tip_loop[1], Vector((0,0,1)), -step/n_iters, debug = True)
            
            
            bmesh.ops.smooth_vert(bme, factor = 0.5, verts = tip_loop[0], use_axis_x = True, use_axis_y = True)
            sharp_verts = [v for v in tip_loop[0] if simple_angle(v, Z = Vector((0,0,1))) < math.pi/2]
            print('THERE ARE %i sharp verts' % len(sharp_verts))
            #for v in sharp_verts:
            #    v.select_set(True)
            bmesh.ops.smooth_vert(bme, factor = 1.0, verts = sharp_verts, use_axis_x = True, use_axis_y = True)    
            
            #relax_loops_util(bme, tip_loop[1], 1 , influence = 1.0)
            tip_loop = collapse_to_resolution(bme, tip_loop[1], .2)
            
    #relax_loops_util(bme, tip_loop[1], 10 , influence = 1.0)        
    #bmesh.ops.bridge_loops(bme, edges = tip_loop[1] + biggest_loop[1])  
    fast_bridge(bme, tip_loop, biggest_loop, Vector((0,0,1)))
         
     
    for v in tip_loop[0]:
        if flat_root:
            v.co[2] = cej_com[2] + root_length
        else:
            v.co += root_length * Vector((0,0,1))  #root direction
    
    cap_f = bme.faces.new(tip_loop[0])
    top_f = bme.faces.new(top_loop[0])
    
    bmesh.ops.recalc_face_normals(bme, faces = bme.faces[:])
    if cap_f.normal.dot(Vector((0,0,1))) < 0:
        print('FLIPPIN GNORMALS' + ob.name)
        for f in bme.faces:
            f.normal_flip()
    
    
    
    geom = bmesh.ops.poke(bme, faces = [top_f])
    v = [ele for ele in geom['verts']][0]
    fs = [ele for ele in geom['faces']]
    
    loc, no, ind, d = bvh.ray_cast(v.co, Vector((0,0,-1)))
    if loc:
        v.co = loc + Vector((0,0,1))
    
    else:
        loc, no, ind, d = bvh.ray_cast(v.co, Vector((0,0,1)))
        if loc:
            v.co = loc + Vector((0,0,1))
                
               
    sub_edges = set()
    for f in fs:
        sub_edges.update(f.edges)
        
    sub_edges.difference_update(top_loop[1])
    
    gdict = bmesh.ops.subdivide_edges(bme, edges = list(sub_edges), cuts = 4)
    
    vs = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMVert)]
    fs = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMFace)]
    for v in vs:
        loc, no, ind, d = bvh.ray_cast(v.co, Vector((0,0,-1)))
        if loc:
            v.co = loc + Vector((0,0,1))
        
        else:
            loc, no, ind, d = bvh.ray_cast(v.co, Vector((0,0,1)))
            if loc:
                v.co = loc + Vector((0,0,1))
    
    #bmesh.ops.triangulate(bme, faces = fs)
    bmesh.ops.triangulate(bme, faces = bme.faces[:])
    
            
    #bme_re = remesh_bme(bme, 
    #          isovalue = 0.0, 
    #          adaptivity = 1.0, 
    #          only_quads = False, 
    #          voxel_size = .125,
    #          filter_iterations = 0,
    #          filter_width = 4,
    #          filter_sigma = 1.0,
    #          grid = None,
    #          write_method = 'FAST')
    
    #bme_re.to_mesh(new_me)     
    #bme_re.free()
    bme.to_mesh(new_me)
    thimble_ob.hide = True    
    
    #bmesh.ops.bridge_loops(bme_thimble, edges = thimble_margin[1] + thimble_prep[1])
    #bmesh.ops.bridge_loops(bme_thimble, edges = thimble_prep[1] + thimble_top[1])    
    #bmesh.ops.recalc_face_normals(bme_thimble, faces = bme_thimble.faces[:])
    
    
    bme.free()
    del bvh




def reduce_and_remesh_preps(teeth, margin_depth, axial_depth):
    voxel_size = .09
    
    for tooth in teeth:
        
        root_prep = bpy.data.objects.get(tooth.name.split(' ')[0] + ' root_prep')
        thimble_prep = bpy.data.objects.get(tooth.name.split(' ')[0] + ' thimble_prep')
        anatomic_shell = bpy.data.objects.get(tooth.name.split(' ')[0] + ' open_shell')
        margin_line = bpy.data.objects.get(tooth.name.split(' ')[0] + ' margin_line')
        
        anatomic_shell.hide = True
        thimble_prep.hide = True
        margin_line.hide = True
        
        if not root_prep: continue
        
        thimble_prep.data.update()
        mod = thimble_prep.modifiers.new('Solidify', type = 'SOLIDIFY')
        mod.thickness = margin_depth
        mod.offset = 1.0
                    
                
        if "Margin Prox" not in anatomic_shell.vertex_groups:
            vg = anatomic_shell.vertex_groups.new(name = "Margin Prox")
        else:
            vg = anatomic_shell.vertex_groups.get('Margin Prox')
        vg.add([i for i in range(0,len(anatomic_shell.data.vertices))], 0, type = 'REPLACE')
    
        anatomic_shell.data.update() 
        pmod = anatomic_shell.modifiers.new('Margin Prox', 'VERTEX_WEIGHT_PROXIMITY')

        pmod.target = margin_line
        pmod.vertex_group = "Margin Prox"
        pmod.proximity_mode = 'GEOMETRY'
        pmod.proximity_geometry = {'VERTEX'}
        pmod.min_dist = 0.2 #4.5
        pmod.max_dist = 4.5
        pmod.falloff_type = 'ICON_SPHERECURVE' #LINEAR' #'SMOOTH' #'SHARP' #'ICON_SPHERECURVE'
        pmod.show_expanded = False   
                    
        
        mod = anatomic_shell.modifiers.new('Solidify', type = 'SOLIDIFY')
        mod.thickness = 2.0 * axial_depth
        mod.offset = 0.0
        mod.vertex_group = "Margin Prox"
        mod.thickness_vertex_group = .05
        
        mod = anatomic_shell.modifiers.new('Smooth', type = 'SMOOTH')
        mod.iterations = 15
        
            
        bpy.context.scene.update()
        me_shell = anatomic_shell.to_mesh(bpy.context.scene, apply_modifiers = True, settings = 'PREVIEW')
        me_thimble = thimble_prep.to_mesh(bpy.context.scene, apply_modifiers = True, settings = 'PREVIEW')  
                
        thimble_prep.modifiers.clear()
        anatomic_shell.modifiers.clear()
        
        bme_reduction = bmesh.new()
        bme_reduction.from_mesh(me_shell)    
        bme_reduction.from_mesh(me_thimble)
        
        bme_reduction.verts.ensure_lookup_table()
        bme_reduction.edges.ensure_lookup_table()
        bme_reduction.faces.ensure_lookup_table()
        bme_reduction.normal_update()
        
        verts1, tris1, quads1 = read_bmesh(bme_reduction)         
        vdb_reduction = convert_vdb(verts1, tris1, quads1, voxel_size)
        bme_reduction.free()
        
        for _ in range(5):
            vdb_reduction.gaussian(1.0, 4)
            
        bme = bmesh.new()
        bme.from_mesh(root_prep.data)
        
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        bme.normal_update()
        
        verts0, tris0, quads0 = read_bmesh(bme)         
        vdb_prep = convert_vdb(verts0, tris0, quads0, voxel_size)
        bme.free()
        
        vdb_prep.difference(vdb_reduction, False)
        
        ve, tr, qu = vdb_prep.convertToPolygons(0.0, (3.0/100.0)**2)

        bm = bmesh.new()
        for co in ve.tolist():
            bm.verts.new(co)

        bm.verts.ensure_lookup_table()    
        bm.faces.ensure_lookup_table()    

        for face_indices in tr.tolist() + qu.tolist():
            bm.faces.new(tuple(bm.verts[index] for index in reversed(face_indices)))

        bm.normal_update()
        
        #bm.transform(root_prep.matrix_world.inverted())
        bm.to_mesh(root_prep.data)
        bm.free()
        
        del vdb_prep
        del vdb_reduction
        
        root_prep.hide = False
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        
    
        
class AITeeth_OT_root_prep(bpy.types.Operator):
    """Create roots and preparations from teeth"""
    bl_idname = "ai_teeth.root_preps"
    bl_label = "Root Preps"

    tooth_selection = bpy.props.EnumProperty(name = 'Tooth Selection', items = (('ALL_TEETH','ALL_TEETH','ALL_TEETH'), ('SELECTED_TEETH','SELECTED_TEETH','SELECTED_TEETH')))
    
    root_type = bpy.props.EnumProperty(name = 'Root Style', items = (('FLAT','FLAT','FLAT'), ('SMOOTH','SMOOTH','SMOOTH'), ('SHOULDERED','SHOULDERED','SHOULDERED')))
    root_length = bpy.props.FloatProperty(name = 'Root Length', default = 8.0)
    
    prep_teeth = bpy.props.BoolProperty(name = 'Add Prep', default = True)
    prep_type = bpy.props.EnumProperty(name = 'Prep Type', default = 'THIMBLE', items = (('THIMBLE','THIMBLE','THIMBLE'), ('ANATOMIC','ANATOMIC','ANATOMIC')))
    shoulder_width = bpy.props.FloatProperty(name = 'Shoulder Width', default = 0.7)
    anatomic_reduction = bpy.props.FloatProperty(name = 'Anatomic Reduction', default = 1.0)
    taper = bpy.props.FloatProperty(name = 'Taper', default = 7.0, min = 0.0, max = 15.0)
    sub_g = bpy.props.FloatProperty(name = 'Sub G', default = .12, min = 0.0, max = 1.0)
    angle_filtering = bpy.props.BoolProperty(name = 'Amgle Filtering', default = True)
    @classmethod
    def poll(cls, context):

        return context.scene.adjust_axes == True
   

    def invoke(self, context, event):

        
        return context.window_manager.invoke_props_dialog(self, width = 300)
    

            
    def execute(self, context):
        print('MAIN FUNCTION')
        
        bpy.context.space_data.transform_manipulators = {'TRANSLATE', 'ROTATE'}
        bpy.context.space_data.show_manipulator = True
        
        upper_ging = bpy.data.objects.get('Upper Gingiva')
        lower_ging = bpy.data.objects.get('Lower Gingiva')
        
        if lower_ging:
            lower_ging.hide = True
        if upper_ging:
            upper_ging.hide = True
            
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        
        if self.tooth_selection == 'ALL_TEETH':
            obs = [ob for ob in bpy.data.objects if 'Convex' in ob.name]
        else:
            obs = [ob for ob in bpy.data.objects if 'Convex' in ob.name and ob.select]
            
        for ob in obs:
            print('\n\n\n PREP' + ob.name)
            make_root_prep(ob, flat_root= self.root_type == 'FLAT',
                           prep_width= self.shoulder_width,
                           root_length= self.root_length,
                           taper = self.taper,
                           sub_g = self.sub_g,
                           angle_filtering = self.angle_filtering)
            print('\n\n\n')
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)


        for ob in obs:
            ob.hide = True
        if lower_ging:
            lower_ging.hide = False
        if upper_ging:
            upper_ging.hide = False
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        time.sleep(2.5)
        
        for ob in obs:
            ob.hide = False
        
        
        if self.prep_type == 'ANATOMIC':
            for ob in obs:
                ob.select = True
            
            upper_teeth = [ob for ob in obs if data_tooth_label(ob.name.split(' ')[0]) in tooth_numbering.upper_teeth]
            lower_teeth = [ob for ob in obs if data_tooth_label(ob.name.split(' ')[0]) in tooth_numbering.lower_teeth]
     
            if len(upper_teeth):
                reduce_and_remesh_preps(upper_teeth, self.shoulder_width, self.anatomic_reduction)
            
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
            
            if len(lower_teeth):
                reduce_and_remesh_preps(lower_teeth, self.shoulder_width, self.anatomic_reduction)
            
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        
        bpy.context.scene.root_preps = True
        #TODO, set up the modal operator
        return {'FINISHED'}

def register():
    bpy.utils.register_class(AITeeth_OT_root_prep)


def unregister():
    bpy.utils.unregister_class(AITeeth_OT_root_prep)

