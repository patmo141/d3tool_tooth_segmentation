import math
import time
import numpy as np

import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
from mathutils.geometry import intersect_line_line

from ..subtrees.bmesh_utils.bmesh_utilities_common import bme_rip_vertex, bbox_center, bound_box_bmverts
from ..subtrees.bmesh_utils.bmesh_utilities_common import edge_loops_from_bmedges_topo

from ..subtrees.geometry_utils.transformations import calc_angle


def spline_obj_from_RDP_nodes(nodes,name, cyclic = True,):
    '''
    list of vertex coords
    closed loop or not
    name
    
    '''
    
    if name in bpy.data.objects:
        spline_obj = bpy.data.objects.get(name)
        spline_data = spline_obj.data
    
        #clear old spline data, dont remove items form list while iterating over it
        splines = [s for s in spline_data.splines]
        for s in splines:
            spline_data.splines.remove(s)
                
    else:
        spline_data = bpy.data.curves.new(name, 'CURVE')
        spline_obj = bpy.data.objects.new(name, spline_data)
        bpy.context.scene.collection.objects.link(spline_obj)
        #crv_obj.parent = self.obj
        #crv_obj.matrix_world = self.obj.matrix_world
        
    spline_obj.data.dimensions = '3D'
    spline = spline_data.splines.new('BEZIER')
    spline.bezier_points.add(count = len(nodes) - 1)
    for i,node in enumerate(nodes):
        bpt = spline.bezier_points[i]
        bpt.handle_right_type = 'AUTO'
        bpt.handle_left_type = 'AUTO'
        bpt.co = node
    
    if cyclic:
        spline.use_cyclic_u = True          
    return spline_obj
                


def clean_geom(bme):
    #make sure there are no node_verts
    #make sure no loose triangles
    
    #first pass, collect all funky edges
    funky_edges = [ed for ed in bme.edges if (len(ed.link_faces) != 2 or ed.calc_length() < .00001)]
    
    
    degenerate_eds = [ed for ed in funky_edges if len(ed.link_faces) > 2]
    zero_len_eds = [ed for ed in funky_edges if ed.calc_length() < .00001]
    loose_eds = [ed for ed in funky_edges if len(ed.link_faces) == 0]
    non_man_eds = [ed for ed in funky_edges if len(ed.link_faces) == 1]
    
    
    if len(degenerate_eds):
        print('found %i degenerate edges' % len(degenerate_eds))
        bmesh.ops.split_edges(bme, edges = degenerate_eds, verts = [])
        #now need to run again, and hopefully delete loose triangles
        return -1
    if len(zero_len_eds):
        print('dissolving zero length edges %i' % len(zero_len_eds))
        bmesh.ops.dissolve_degenerate(bme, dist = .0001, edges = zero_len_eds)  
        return -1  
    if len(loose_eds):
        loose_vs = set()
        for ed in loose_eds:
            vs = [v for v in ed.verts if len(v.link_faces) == 0]
            loose_vs.update(vs)
        print('Deleting %i loose edges' % len(loose_eds))    
        
        for ed in loose_eds:
            bme.edges.remove(ed)
        for v in loose_vs:
            bme.verts.remove(v)
        
        
    perim_verts = set()
    perim_faces = set()
    for ed in non_man_eds:
        perim_verts.update([ed.verts[0], ed.verts[1]])
        if len(ed.link_faces) == 1:
            perim_faces.add(ed.link_faces[0])
    
    #first check for loose triangles
    bad_triangles = []
    for f in perim_faces:
        check = [ed for ed in f.edges if ed in non_man_eds]
        if len(check) == 3:
            bad_triangles.append(f)
        elif len(check) ==2:
            for v in f.verts:
                if v in check[0].verts and v in check[1].verts:
                    veca = check[0].other_vert(v).co - v.co
                    vecb = check[1].other_vert(v).co - v.co
                    
                    if veca.angle(vecb) < 50 * math.pi/180:
                        print(veca.angle(vecb))
                        bad_triangles.append(f)
                
                       
    if len(bad_triangles):
        bad_verts = set()
        bad_edges = set()
        for f in bad_triangles:
            del_verts = [v for v in f.verts if len(v.link_faces) == 1]
            del_edges = [ed for ed in f.edges if len(ed.link_faces) == 1]
            bad_verts.update(del_verts)
            bad_edges.update(del_edges)
            
            
        for f in bad_triangles:
            bme.faces.remove(f)
        for ed in bad_edges:
            bme.edges.remove(ed)
        for v in bad_verts:
            bme.verts.remove(v)
        #bmesh.ops.delete(bme, geom = bad_triangles, context = 3)
        #bmesh.ops.delete(bme, geom = list(bad_edges), context = 4)
        #bmesh.ops.delete(bme, geom = list(bad_verts), context = 1)
        print('Deleting %i loose and flag/dangling triangles' % len(bad_triangles))
        
        #this affects the perimeter, will need to do another pass
        #could also remove bad_fs from perimeter fs...
        #for now laziness do another pass
        return -1
    
    
    #fill small angle coves
    #initiate the front and calc angles
    angles = {}
    neighbors = {}
    for v in perim_verts:
        ang, va, vb = calc_angle(v)
        angles[v] = ang
        neighbors[v] = (va, vb)    
         
    
    iters = 0 
    start = time.time()
    N = len(perim_verts)
    new_fs = []
    coved = False
    while len(perim_verts) > 3 and iters < 2 * N:
        iters += 1
        
        v_small = min(perim_verts, key = angles.get)
        smallest_angle = angles[v_small]
        
        va, vb = neighbors[v_small]
        
        vec_a = va.co - v_small.co
        vec_b = vb.co - v_small.co
        vec_ab = va.co - vb.co
        
        
        Ra, Rb = vec_a.length, vec_b.length
        
        R_13 = .67*Ra + .33*Rb
        R_12 = .5*Ra + .5*Rb
        R_23 = .33*Ra + .67*Rb

        vec_a.normalize()
        vec_b.normalize()
        v_13 = vec_a.lerp(vec_b, .33) #todo, verify lerp
        v_12 = vec_a.lerp(vec_b, .5)
        v_23 = vec_a.lerp(vec_b, .67)
        
        v_13.normalize()
        v_12.normalize()
        v_23.normalize()
        
        if smallest_angle < math.pi/180 * 120:
            try:
                #f = bme.faces.new((va, v_small, vb))
                f = bme.faces.new((vb, v_small, va))
                new_fs += [f]
                f.normal_update()
                coved = True
                
                #update angles and neighbors
                ang_a, vaa, vba = calc_angle(va)
                ang_b, vab, vbb = calc_angle(vb)
                
                angles[va] = ang_a
                angles[vb] = ang_b
                neighbors[va] = (vaa, vba)
                neighbors[vb] = (vab, vbb)
                perim_verts.remove(v_small)
                
            except ValueError:
                print('concavity with face on back side')
                angles[v_small] = 2*math.pi
    
    
        else:
            
            print('finished coving all small angle concavities')
            print('Coved %i verts' % len(new_fs))
            for f in new_fs:
                f.select_set(True)
            break
    if coved:
        print('Coved returning early')
        return -1
    
             
    node_verts = []
    end_verts = []
    for v in perim_verts:
        check = [ed for ed in v.link_edges if ed in non_man_eds]
        if len(check) != 2:
            if len(check) > 2:
                node_verts.append(v)
            elif len(check) == 1:
                print("found an endpoint of an unclosed loop")
                end_verts.append(v)
    
    
    if len(node_verts):
        for v in node_verts:
            bme_rip_vertex(bme, v)
        
        #ripping changes the perimeter and topology, try again
        print('ripping %i node vertices' % len(node_verts))
        return -1
         


def simple_base_bme(bme, Z, base_height = 6.0,
                do_clean_geom = True,
                close_holes = True,
                relax_border = True):
    
    
    start = time.time()   
    clean_iterations = 0
    test = -1
    while clean_iterations < 10 and test == -1 and do_clean_geom:
        print('Cleaning iteration %i' % clean_iterations)
        clean_iterations += 1
        test = clean_geom(bme) 
    
    if do_clean_geom:
        print('took %f seconds to clean geometry and edges' % (time.time() - start))
        start = time.time()
    
    #update everything
    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    
    bme.verts.index_update()
    bme.edges.index_update()
    bme.faces.index_update()
    #bme.to_mesh(context.object.data)
    #context.object.data.update()
    #bme.free()
    #return {'FINISHED'}
    
    non_man_eds = [ed for ed in bme.edges if len(ed.link_faces) == 1 and ed.is_valid]        
    if len(non_man_eds) == 0:
        print('no perimeter loop')
        bme.free()
        return
    
    loops = edge_loops_from_bmedges_topo(bme, non_man_eds)
    
    print('took %f seconds to identify single perimeter loop' % (time.time() - start))
    start = time.time()
    
    if len(loops)>1:
        biggest_loop = max(loops, key = lambda x: len(x[0]))
        
        if close_holes:
            new_fs = []
            for v_loop in loops:
                if v_loop == biggest_loop: continue  #don't close the biggest hole
                
                fverts = v_loop[0]
                new_fs.append(bme.faces.new(fverts))
            
            print('Closed %i holes' % len(new_fs))    
            bmesh.ops.triangulate(bme, faces = new_fs)
                    
        
    else:
        biggest_loop = loops[0]
        
    loop_verts = biggest_loop[0]
    final_eds = biggest_loop[1] #the edges, in order!
    
                       
    interval = time.time()

 
    loop_locs = [v.co for v in loop_verts]
    com = bbox_center(bound_box_bmverts(loop_verts))
    
    #Z should point toward the occlusal always
    direction = 0
    for f in bme.faces:
        direction += f.calc_area() * f.normal.dot(Z)
    
    if direction < 0:           
        Z *= -1
            
    print('took %f seconds to identify average face normal' % (time.time() - start))
    start = time.time()
    
    Z.normalize()
    
    minv = min(bme.verts[:], key = lambda x: (x.co - com).dot(Z))
    maxv = max(bme.verts[:], key = lambda x: (x.co - com).dot(Z))
    
    height = abs((minv.co - maxv.co).dot(Z))
    
    flat_co = minv.co
        
    
    print('took %f seconds to identify height reference point' % (time.time() - start))
    start = time.time()
      

    ### THE FIRST EXTRUSION ###
    gdict = bmesh.ops.extrude_edge_only(bme, edges = final_eds)
    bme.edges.ensure_lookup_table()
    newer_edges = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMEdge)]
    newer_verts = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMVert)]
     
    print('took %f seconds to extrude  verts' % (time.time() - start))
    start = time.time()

    #bmesh.ops.transform(newer_verts, -.1 * Z)
    for v in newer_verts:
        v.co += .1 * Z
    
    print('took %f seconds to translate verts' % (time.time() - start))
    start = time.time()
    
    
    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    
    #if relax_border:
    #    relax_loops_util(bme, newer_edges, iterations = 10, influence = .5, override_selection = True, debug = True)
    #    print('took %f seconds to relax verts' % (time.time() - start))
    #    start = time.time()
    
    
    #FINAL EXTRUSION
    gdict = bmesh.ops.extrude_edge_only(bme, edges = newer_edges)
    bme.edges.ensure_lookup_table()
    bme.verts.ensure_lookup_table()
    base_verts = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMVert)]
    new_edges = [ele for ele in gdict['geom'] if isinstance(ele, bmesh.types.BMEdge)]
    
    new_border = [ed for ed in new_edges if len(ed.link_faces) == 1]
    
    print('took %f seconds to extrude again verts' % (time.time() - start))
    start = time.time()
    
    for v in base_verts:
        co_flat = v.co +  (flat_co - v.co).dot(Z) * Z
        v.co = co_flat - base_height * Z
    
    print('took %f seconds to translate to Z' % (time.time() - start))
    start = time.time()  
    
    #bmesh.ops.triangle_fill(bme, use_beauty=True, use_dissolve=False, edges=new_border, normal=-1*Z)
    loops = edge_loops_from_bmedges_topo(bme, new_border)  
    f = bme.faces.new(loops[0][0])
    bmesh.ops.triangulate(bme, faces = [f], ngon_method = 0)
    
    print('took %f seconds to create face' % (time.time() - start))
    start = time.time()  
    
    #base face should point away from occlusal
    #f.normal_update()
    #if f.normal.dot(Z) > 0:
    #    f.normal_flip()
    
    
    
      
        
