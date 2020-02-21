'''
Created on Mar 9, 2019
@author: Patrick
patrick@d3tool.com
patrick.moore.bu@gmail.com
'''

import math
import random

import bpy
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

from ..bmesh_utils.bmesh_utilities_common import new_bmesh_from_bmelements, bbox_center, bound_box_bmverts, bmesh_loose_parts
from .offset_utilities import create_dyntopo_meta_scaffold,\
    simple_metaball_offset


def mx_from_principal_axes(X,Y, Z):
    T = Matrix.Identity(3)  #make the columns of matrix U, V, W
    T[0][0], T[0][1], T[0][2]  = X[0] ,Y[0],  Z[0]
    T[1][0], T[1][1], T[1][2]  = X[1], Y[1],  Z[1]
    T[2][0] ,T[2][1], T[2][2]  = X[2], Y[2],  Z[2]
    
    return T

def diamond_circle_grid_element(width, diamond_width):
    
    bme = bmesh.new()
    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    
    bmesh.ops.create_grid(bme, x_segments = 3, y_segments = 3, size = width/4)
    
    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    inds = [0,2,4,6,8]
    vs = [bme.verts[i] for i in inds]  #the 3 corners and the middle
    
    dw = min(.5 * diamond_width, .45 * width)
    
    geom =  bmesh.ops.bevel(bme, geom = vs, offset = dw, segments = 3, vertex_only = True)
    
    fs = geom['faces']
    bmesh.ops.delete(bme, geom = fs, context = 5)
    
    
    return bme


def diamond_grid_element(width, diamond_width):
    
    bme = bmesh.new()
    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    
    bmesh.ops.create_grid(bme, x_segments = 3, y_segments = 3, size = width/4)
    
    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    inds = [0,2,4,6,8]
    vs = [bme.verts[i] for i in inds]  #the 3 corners and the middle
    
    dw = min(.5 * diamond_width, .45 * width)
    
    geom =  bmesh.ops.bevel(bme, geom = vs, offset = dw, segments = 1, vertex_only = True)
    
    fs = geom['faces']
    bmesh.ops.delete(bme, geom = fs, context = 5)
    
    
    return bme

def diamond_net_element(width):
    '''
    Dumb because a diamond net is just bmesh.ops.create_grid but
    casting it this way allows it to fit into the same modifier
    pipeline as the others
    '''
    
    bme = bmesh.new()
    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    
    bmesh.ops.create_grid(bme, x_segments = 2, y_segments = 2, size = width/2)
    
    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    
    return bme

#https://rechneronline.de/pi/hexagon.php
def hexagon_grid_element(outer_diameter, inner_diameter):
    
    bme = bmesh.new()
    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    
    geo_outer = bmesh.ops.create_circle(bme, cap_ends = False, cap_tris = False, segments = 6, diameter = .5 * outer_diameter)
    geo_inner = bmesh.ops.create_circle(bme, cap_ends = False, cap_tris = False, segments = 6, diameter = .5 * inner_diameter)
    
    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    
    for i in range(0, 6):
        
        ind0 = i
        ind1 = int(math.fmod(i + 1, 6))
        ind2 = 6 + int(math.fmod(i + 1, 6))
        ind3 = i + 6 # 6 - 1
        bme.faces.new((bme.verts[ind0], bme.verts[ind1], bme.verts[ind2], bme.verts[ind3]))
    
    return bme
 
 
def hexagon_net_element(diameter):
    
    bme = bmesh.new()
    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    
    geo_outer = bmesh.ops.create_circle(bme, cap_ends = False, cap_tris = False, segments = 6, diameter = .5 * diameter)
    
    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    
    
    return bme 
 
def make_grid_object(outer_diameter, inner_diameter, thickness, grid_repeats, method, add_bevel = True):
    
    
    assert method in {'DIAMOND', 'DIAMOND_CIRCLE', 'HEXAGON', 'HEXAGON_NET', "DIAMOND_NET"}
    if method == "DIAMOND":
        grid_fn = diamond_grid_element
    elif method == "DIAMOND_CIRCLE":
        grid_fn = diamond_circle_grid_element
    elif method == "HEXAGON":
        grid_fn = hexagon_grid_element
       
    elif method == "HEXAGON_NET":
        grid_fn = hexagon_net_element
    elif method == 'DIAMOND_NET':
        grid_fn = diamond_net_element
        
           
    if "NET" in method:
        bme_grid = grid_fn(outer_diameter)
    else:
        bme_grid = grid_fn(outer_diameter, inner_diameter)
    
    me = bpy.data.meshes.new('grid')
    ob = bpy.data.objects.new('Grid', me)
    bme_grid.to_mesh(me)
    
    bme_grid.free()
    
    
    if "HEXAGON" not in method:
        m1 = ob.modifiers.new('XArray', type = 'ARRAY')
        m1.count = grid_repeats
        m1.relative_offset_displace[0] = 1.0
        m1.relative_offset_displace[1] = 0.0
        m1.use_merge_vertices = True
        
        m2 = ob.modifiers.new('YArray', type = 'ARRAY')
        m2.count = grid_repeats
        m2.relative_offset_displace[0] = 0.0
        m2.relative_offset_displace[1] = 1.0
        m2.use_merge_vertices = True
    else:
        m1 = ob.modifiers.new('XArray', type = 'ARRAY')
        m1.count = grid_repeats
        m1.relative_offset_displace[0] = 1.0
        m1.relative_offset_displace[1] = 0.0
        m1.use_merge_vertices = True
        
        m2 = ob.modifiers.new('YArray', type = 'ARRAY')
        m2.count = 2
        m2.relative_offset_displace[0] = .5/float(grid_repeats)
        m2.relative_offset_displace[1] = .75
        m2.use_merge_vertices = True
        
        m3 = ob.modifiers.new('YArray2', type = 'ARRAY')
        m3.count = int(math.ceil(grid_repeats/2))
        m3.relative_offset_displace[0] = 0
        m3.relative_offset_displace[1] = 1 - 1/7  #first person to email me a proof of why this works I will mail you a $100 gift card.
        m3.use_merge_vertices = True
    
    
    if "NET" not in method:
        mthick = ob.modifiers.new('Solid', type = 'SOLIDIFY')
        mthick.thickness = thickness 
    
        if add_bevel:
            modb = ob.modifiers.new('bevel', type = "BEVEL")
            modb.segments = 2
        ob.data.update()
    
    

    return ob
    
    
def honeycomb_bme(bme, hole_radius, offset = .1, bvh = None, ):
    '''
    bme should be a scaffold with approximate vert spacing of 1/2 the
    desired cell major size and then a catmul clark subdivision
    
     Dissolving triangle fans into NGons creates
    cells with radius approximatly the vert spacing of the scaffold
    
    offset is a percentage of the cell size that the the cell will be extruded inward
    
    '''
    
    if bvh == None:
        bvh = BVHTree.FromBMesh(bme)
    
    dissolve_verts = [v for v in bme.verts if len(v.link_edges) > 5]
    
    iters = 0
    while len(dissolve_verts) and iters < 4:
        iters += 1
        bmesh.ops.dissolve_verts(bme, verts = dissolve_verts)
        bme.verts.ensure_lookup_table()
        dissolve_verts = [v for v in bme.verts if len(v.link_edges) > 5]
    
    dissolve_verts = [v for v in bme.verts if len(v.link_edges) > 4]     
    iters = 0
    while len(dissolve_verts) and iters < 4:
        iters += 1
        bmesh.ops.dissolve_verts(bme, verts = dissolve_verts)
        bme.verts.ensure_lookup_table()
        dissolve_verts = [v for v in bme.verts if len(v.link_edges) > 4]
        
    dissolve_verts = [v for v in bme.verts if len(v.link_edges) > 3]     
    iters = 0
    while len(dissolve_verts) and iters < 4:
        iters += 1
        bmesh.ops.dissolve_verts(bme, verts = dissolve_verts)
        bme.verts.ensure_lookup_table()
        dissolve_verts = [v for v in bme.verts if len(v.link_edges) > 3]
          
    dissolve_fs = [f for f in bme.faces if len(f.verts) <= 4]
    bmesh.ops.dissolve_faces(bme, faces = dissolve_fs)
    
    dissolve_vs =  [v for v in bme.verts if len(v.link_edges) == 2]
    bmesh.ops.dissolve_verts(bme, verts = dissolve_vs)
    
    
    
    perim_faces = set()
    for ed in bme.edges:
        if len(ed.link_faces) == 1:
            perim_faces.add(ed.link_faces[0])
            
    
    fs = [f for f in bme.faces if len(f.verts) > 4 and f not in perim_faces]
    geom = bmesh.ops.extrude_discrete_faces(bme, faces = fs)
    
    central_faces = set()
    bme_round_holes = bmesh.new()
    
    for f in geom['faces']:
        if len(f.verts) < 5: continue
        mid = f.calc_center_bounds()
        A = f.calc_area()
        R = math.sqrt(A/math.pi)  #approximate radius
        
        if R < .75 * hole_radius: continue
        
        s_factor = hole_radius/R
        s_factor = min(.8, s_factor)  #don't scale the holes bigger than their container
        s_factor = max(.1, s_factor)
        
        no = f.normal
        v_max = max(f.verts, key = lambda x: (x.co - mid).length)
        X = v_max.co - mid
        X.normalize()
        Y = no.cross(X)
        Rmx = mx_from_principal_axes(X, Y, no)
        Rmx = Rmx.to_4x4()
        snap = bvh.find_nearest(mid)
        T = Matrix.Translation(snap[0])
        
        bmesh.ops.create_circle(bme_round_holes, 
                                cap_ends = True, 
                                cap_tris = False,
                                segments = 6, 
                                diameter = s_factor * R, 
                                matrix = T*Rmx)
        
        
        for v in f.verts:
            #scale verts to make average hole size match the the desired hole size
            delta = v.co - mid
            v.co = mid + s_factor * delta
        
        central_faces.add(f)
    
    
    hole_bme  = new_bmesh_from_bmelements(central_faces)
    
    for f in central_faces:
        bme.faces.remove(f)
    

    return hole_bme, bme_round_holes
    

def catmul_to_hexagons(bme):
    '''
    expects an evenly triangulated bmesh, to dissolve triangles in to hexagons
    '''
    
    dissolve_verts = [v for v in bme.verts if len(v.link_edges) > 5]
    
    iters = 0
    while len(dissolve_verts) and iters < 4:
        iters += 1
        bmesh.ops.dissolve_verts(bme, verts = dissolve_verts)
        bme.verts.ensure_lookup_table()
        dissolve_verts = [v for v in bme.verts if len(v.link_edges) > 5]
    
    dissolve_verts = [v for v in bme.verts if len(v.link_edges) > 4]     
    iters = 0
    while len(dissolve_verts) and iters < 4:
        iters += 1
        bmesh.ops.dissolve_verts(bme, verts = dissolve_verts)
        bme.verts.ensure_lookup_table()
        dissolve_verts = [v for v in bme.verts if len(v.link_edges) > 4]
        
    dissolve_verts = [v for v in bme.verts if len(v.link_edges) > 3]     
    iters = 0
    while len(dissolve_verts) and iters < 4:
        iters += 1
        bmesh.ops.dissolve_verts(bme, verts = dissolve_verts)
        bme.verts.ensure_lookup_table()
        dissolve_verts = [v for v in bme.verts if len(v.link_edges) > 3]
          
    dissolve_fs = [f for f in bme.faces if len(f.verts) <= 4]
    bmesh.ops.dissolve_faces(bme, faces = dissolve_fs)
    
    dissolve_vs =  [v for v in bme.verts if len(v.link_edges) == 2]
    bmesh.ops.dissolve_verts(bme, verts = dissolve_vs)
    
    
    return
    
        
def honeycomb_hole_bme_reduce(bme, hole_spacing, hole_diameter, hole_segments = 4, offset = .1, bvh = None):
    '''
    bme should be a scaffold with vert spacing more dense than desired hole spacing
    desired cell major size and then a catmul clark subdivision
    
     Dissolving triangle fans into NGons creates
    cells with radius approximatly the vert spacing of the scaffold
    
    after that, points will be sorted by "closeness"  and overpacked points
    discarded
    
    offset is a percentage of the cell size that the the cell will be extruded inward
    
    '''
    
    if bvh == None:
        bvh = BVHTree.FromBMesh(bme)
    
    dissolve_verts = [v for v in bme.verts if len(v.link_edges) > 5]
    
    iters = 0
    while len(dissolve_verts) and iters < 4:
        iters += 1
        bmesh.ops.dissolve_verts(bme, verts = dissolve_verts)
        bme.verts.ensure_lookup_table()
        dissolve_verts = [v for v in bme.verts if len(v.link_edges) > 5]
    
    dissolve_verts = [v for v in bme.verts if len(v.link_edges) > 4]     
    iters = 0
    while len(dissolve_verts) and iters < 4:
        iters += 1
        bmesh.ops.dissolve_verts(bme, verts = dissolve_verts)
        bme.verts.ensure_lookup_table()
        dissolve_verts = [v for v in bme.verts if len(v.link_edges) > 4]
        
    dissolve_verts = [v for v in bme.verts if len(v.link_edges) > 3]     
    iters = 0
    while len(dissolve_verts) and iters < 4:
        iters += 1
        bmesh.ops.dissolve_verts(bme, verts = dissolve_verts)
        bme.verts.ensure_lookup_table()
        dissolve_verts = [v for v in bme.verts if len(v.link_edges) > 3]
          
    dissolve_fs = [f for f in bme.faces if len(f.verts) <= 4]
    bmesh.ops.dissolve_faces(bme, faces = dissolve_fs)
    
    dissolve_vs =  [v for v in bme.verts if len(v.link_edges) == 2]
    bmesh.ops.dissolve_verts(bme, verts = dissolve_vs)
    
    
    
    perim_faces = set()
    perim_verts = set()
    for ed in bme.edges:
        if len(ed.link_faces) == 1:
            perim_faces.add(ed.link_faces[0])
            perim_verts.update([ed.verts[0], ed.verts[1]])
            
    
    fs = [f for f in bme.faces if len(f.verts) > 4 and f not in perim_faces]
   
    #Now reduce to target spacing
    discard_fs = set()  #faces we will remove
    f_map = {}  #map of index in the kd tree to actual face
    f_centers = {}  #map of f.calc_center_bounds() to prevent calcing it every iterati n
    
    kd = KDTree(len(fs))
    for i, f in enumerate(fs):
        v = f.calc_center_bounds()
        kd.insert(v, i)
        f_map[i] = f
        f_centers[f] = v
            
    kd.balance()
    
    kd_perim = KDTree(len(perim_verts))
    
    for i, v in enumerate(list(perim_verts)):
        kd_perim.insert(v.co, i)
    
    kd_perim.balance()
    
    
    #discard all perimeter close faces
    #check closeness to perimeter
    for f in fs:
        edge_neighbors = kd_perim.find_range(f_centers[f], 1.5 * hole_diameter)
        if len(edge_neighbors) > 0:
            discard_fs.add(f)  
    
    def crowding_factor(f):
        
        neighbors = kd.find_range(f_centers[f], .95*hole_spacing)  #tolerance
        
        n_crowded = 0
        
        for loc, ind, dist in neighbors:
            
            if f_map[ind] in discard_fs: continue
            n_crowded += 1
            #how many non_removed neighbors are there?
             
        return n_crowded
        
        
    def reduce_step():  #trash any
        
        n_removed = 0
        random.shuffle(fs)
        for f in fs:
            if f in discard_fs: continue
            
            if crowding_factor(f) > 1:  #remember, it finds itself in the KD!
                discard_fs.add(f)
                n_removed += 1
                
        return n_removed
            
    
    
    reduce_more = True
    iters = 0
    while reduce_more and iters < 30:
        print('reducing')
        iters += 1
        reduce_more = reduce_step() > 1
    
    
    bme_round_holes = bmesh.new()
    
    for f in fs:
        if len(f.verts) < 5: continue
        if f in discard_fs: continue
        
        mid = f.calc_center_bounds()  #face_centers[f]
        #A = f.calc_area()
        #R = math.sqrt(A/math.pi)  #approximate radius
        
        #if R < .75 * hole_radius: continue
        
        #s_factor = hole_radius/R
        #s_factor = min(.8, s_factor)  #don't scale the holes bigger than their container
        #s_factor = max(.1, s_factor)
        
        no = f.normal
        v_max = max(f.verts, key = lambda x: (x.co - mid).length)
        X = v_max.co - mid
        X.normalize()
        Y = no.cross(X)
        Rmx = mx_from_principal_axes(X, Y, no)
        Rmx = Rmx.to_4x4()
        snap = bvh.find_nearest(mid)
        T = Matrix.Translation(snap[0])
        
        bmesh.ops.create_circle(bme_round_holes, 
                                cap_ends = True, 
                                cap_tris = True,
                                segments = 20, 
                                diameter = hole_diameter, 
                                matrix = T*Rmx)
        
    
    

    return bme_round_holes      
 
 
 
def region_growing_holes(bme, grow_steps, border_steps = 0):
    '''
    returns a list of locaitons of holes scattered across surface
    
    dynotop 1.5 -> 10 iterations -> 5
    dyntopo 1.5 -> 15 iterations -> 7.5
    dyntopo 1.5 -> 20 iterations -> 10
    
    
    
    '''
     

    def face_neighbors(bmface):
        neighbors = []
        
        #for v in bmface.verts:
        #    neighbors += [bf for bf in v.link_faces if bf != bmface]
        for ed in bmface.edges:
            neighbors += [bf for bf in ed.link_faces if bf != bmface]
        return neighbors

    #all faces
    islands = bmesh_loose_parts(bme, max_iters = 300)
    
    print('there are %i islands' % len(islands))
    all_faces = set(bme.faces[:])
    
    #pick a random seed
    dead_zone = set()  #all the faces inbetween the voronoi cells
    
    if border_steps > 0:
        eds = [ed for ed in bme.edges if len(ed.link_faces) == 1]
        fs = set()
        for ed in eds:
            fs.add(ed.link_faces[0])
            
        for n in range(0, border_steps):
            new_faces = set()
            for f in fs:
                new_faces.update(face_neighbors(f))
                
            fs.update(new_faces)
                
    
        dead_zone |= fs
    
    nodes = set()
    for isl in islands:
    
        seed_index = random.randint(0, len(isl))
        seed_face = bme.faces[seed_index]
        iters = 0
        if seed_face in dead_zone:
            while seed_face in dead_zone and iters < 100:
                iters += 1
                seed_index = random.randint(0, len(bme.faces))
                seed_face = bme.faces[seed_index]
                
                
        nodes.add(seed_face)
    
        local_growth = set([seed_face])  #the immediate growth from seed
        newest_faces = set(face_neighbors(seed_face)) #the last ring of faces
        for i in range(0, grow_steps):
            new_faces = set()
            for f in newest_faces:
                new_faces.update(face_neighbors(f))
        
        newest_faces = new_faces - local_growth    
        local_growth |= newest_faces
        
        #Now we have initialized a seed, and a ring around the seed
        dead_zone |= local_growth - newest_faces
        dead_zone.difference_update([seed_face])
        current_perimeter = newest_faces
        new_perimeter = set()
    
        max_iters = int(2* len(bme.faces)/grow_steps)
        
        n = 0
        new_seed = current_perimeter.pop()
    
        while n < max_iters:
            n += 1
            last_len = len(dead_zone)
            nodes.add(new_seed)
            
            local_growth = set([new_seed])
            newest_faces = set(face_neighbors(new_seed)) #initialize with the first ring neighbors around the seed
            for i in range(0, grow_steps):
                new_faces = set()
                for f in newest_faces:
                    new_faces.update(face_neighbors(f))
            
                newest_faces = new_faces - local_growth    
                local_growth |= newest_faces
                
            local_growth.difference_update(newest_faces)  #the newest outer ring
            local_growth.remove(new_seed)
            
            newest_faces -= dead_zone
            dead_zone |= local_growth
            current_perimeter.difference_update(local_growth)
            
            
            new_perimeter |= newest_faces  #once we have exhausted current perimeter
            next_seeds = current_perimeter.intersection(newest_faces)
            
            #TODO, THIS IS UGLY AND A HACK FOR POOR CODE ABOVE
            next_seeds.difference_update(nodes)  #not sure how these are getting in there
            new_perimeter.difference_update(nodes)
            current_perimeter.difference_update(nodes)
            
            if len(next_seeds):
                new_seed = next_seeds.pop()
                current_perimeter.remove(new_seed)
            elif len(current_perimeter):# > grow_steps:
                new_seed = current_perimeter.pop()
            else:
                new_perimeter |= current_perimeter  #merg in any last few
                current_perimeter = new_perimeter
                new_perimeter = set()    
            
            if len(current_perimeter) == 0 and len(new_perimeter) == 0:
                
                if len(all_faces - (dead_zone | nodes)):
                    print('anotheer island!')
                    all_faces.difference_update(dead_zone | nodes)
                    new_seed= all_faces.pop()
                
                break
                
        print('Finished this island in %i iterations' % n)
    

    return nodes
 
    
class D3MODEL_OT_create_grid(bpy.types.Operator):
    """Create 3D Grids and Pattersl"""
    bl_idname = "d3splint.create_3d_grid"
    bl_label = "3D Grid test"
    bl_options = {'REGISTER', 'UNDO'}
    
    method = bpy.props.EnumProperty(
        description="",
        items=(("DIAMOND", "DIAMOND", "DIAMOND"),
               ("DIAMOND_AND_CIRCLE","DIAMOND_AND_CIRCLE", "DIAMOND_AND_CIRCLE"),
               ("HEXAGON","HEXAGON","HEXAGON"),
               ("HEXAGON_NET","HEXAGON_NET","HEXAGON_NET"),
               ("DIAMOND_NET","DIAMOND_NET","DIAMOND_NET")),
        default="DIAMOND",
        )
    
    width = bpy.props.FloatProperty(name = 'element width', default = 4.0, min = .5, max = 10.0)
    hole_width = bpy.props.FloatProperty(name = 'hole width', default = 1.25, min = .25, max = 9.0)
    thickness = bpy.props.FloatProperty(name = 'thickness', default = 2.0, min = .25, max = 9.0)
    grid_repeats = bpy.props.IntProperty(name = 'repeats', default = 10, min = 2, max = 50)
    
    add_bevel = bpy.props.BoolProperty(name = 'add bevel', default = True)
    def execute(self, context):
        
        
        if self.method == "DIAMOND":
            grid_fn = diamond_grid_element
        elif self.method == "DIAMOND_AND_CIRCLE":
            grid_fn = diamond_circle_grid_element
        elif self.method == "HEXAGON":
            grid_fn = hexagon_grid_element
        
        elif self.method == "HEXAGON_NET":
            grid_fn = hexagon_net_element
        elif self.method == 'DIAMOND_NET':
            grid_fn = diamond_net_element
        
           
        if "NET" in self.method:
            bme_grid = grid_fn(self.width)
        else:
            bme_grid = grid_fn(self.width, self.hole_width)

        
        me = bpy.data.meshes.new('grid')
        ob = bpy.data.objects.new('Grid', me)
        bme_grid.to_mesh(me)
        
        bme_grid.free()
        
        context.scene.objects.link(ob)
        
        if self.method not in {"HEXAGON", "HEXAGON_NET"}:
            m1 = ob.modifiers.new('XArray', type = 'ARRAY')
            m1.count = self.grid_repeats
            m1.relative_offset_displace[0] = 1.0
            m1.relative_offset_displace[1] = 0.0
            m1.use_merge_vertices = True
            
            m2 = ob.modifiers.new('YArray', type = 'ARRAY')
            m2.count = self.grid_repeats
            m2.relative_offset_displace[0] = 0.0
            m2.relative_offset_displace[1] = 1.0
            m2.use_merge_vertices = True
        else: #HEXAGON OFFSETS
            m1 = ob.modifiers.new('XArray', type = 'ARRAY')
            m1.count = self.grid_repeats
            m1.relative_offset_displace[0] = 1.0
            m1.relative_offset_displace[1] = 0.0
            m1.use_merge_vertices = True
            
            m2 = ob.modifiers.new('YArray', type = 'ARRAY')
            m2.count = 2
            m2.relative_offset_displace[0] = .5/float(self.grid_repeats)
            m2.relative_offset_displace[1] = .75
            m2.use_merge_vertices = True
            
            m3 = ob.modifiers.new('YArray2', type = 'ARRAY')
            m3.count = int(math.ceil(self.grid_repeats/2))
            m3.relative_offset_displace[0] = 0
            m3.relative_offset_displace[1] = 1 - 1/7  #first person to email me a proof of why this works I will mail you a $100 gift card.
            m3.use_merge_vertices = True
        
        if "NET" not in self.method:
            mthick = ob.modifiers.new('Solid', type = 'SOLIDIFY')
            mthick.thickness = self.thickness 
            
            if self.add_bevel:
                modb = ob.modifiers.new('bevel', type = "BEVEL")
                modb.segments = 2
            ob.data.update()
        
        return {'FINISHED'}
     
 
class D3MODEL_OT_create_honeycomb(bpy.types.Operator):
    """Create Honeycomb on object surface"""
    bl_idname = "d3splint.object_honeycomb_surface"
    bl_label = "Honeycomb Object Suface"
    bl_options = {'REGISTER', 'UNDO'}
    

    hole_spacing = bpy.props.FloatProperty(name = 'element width', default = 4.0, min = 1.5, max = 8.0)
    hole_diameter  = bpy.props.FloatProperty(name = 'hole width', default = 1.0, min = .5, max = 3.0)
    thickness = bpy.props.FloatProperty(name = 'thickness', default = 2.0, min = .25, max = 9.0)
    
    snap = bpy.props.BoolProperty(name ='Snap to Source', default = True)
    snap_offset = bpy.props.FloatProperty(name = 'Snapp Offset', default = 0.0)
    
    def invoke(self, context, event):
        #return context.window_manager.invoke_props_popup(self, event)
        return context.window_manager.invoke_props_dialog(self)
    def execute(self, context):
        
        d_res = 1/self.hole_spacing
        hole_radius = min(.5 * self.hole_spacing, .5 * self.hole_diameter)
        extrude_scale = hole_radius/self.hole_spacing
                
        scaffold = create_dyntopo_meta_scaffold(context.object, d_res, return_type = 'OBJECT')
        mod = scaffold.modifiers.new('Catmul Clark', type = 'SUBSURF')
        
        mod2 = scaffold.modifiers.new('ShrinkWrap', type = 'SHRINKWRAP')
        mod2.target = context.object
        mod2.wrap_method = 'NEAREST_SURFACEPOINT'
        if abs(self.snap_offset) > .1:
            mod2.use_keep_above_surface = True
            mod2.offset = self.snap_offset
        
        me = scaffold.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        bme = bmesh.new()
        bme.from_mesh(me)
        
        hole_bme, round_bme = honeycomb_bme(bme, hole_radius, offset = extrude_scale)
        
        if 'Honeycomb' not in bpy.data.objects:
            me = bpy.data.meshes.new('Honeycomb')
            ob = bpy.data.objects.new('Honeycomb', me)
            bpy.context.scene.objects.link(ob)
            ob.show_wire = True
            ob.show_all_edges = True
            ob.matrix_world = context.object.matrix_world
        else:
            ob = bpy.data.objects.get('Honeycomb')
        bme.to_mesh(me)
        bme.free()
        
        if 'Honeycomb Holes' not in bpy.data.objects:
            me = bpy.data.meshes.new('Honeycomb Holes')
            ob = bpy.data.objects.new('Honeycomb  Holes', me)
            bpy.context.scene.objects.link(ob)
            ob.matrix_world = context.object.matrix_world
        else:
            ob = bpy.data.objects.get('Honeycomb Holes')
        round_bme.to_mesh(me)
        round_bme.free()
        
        #hole_bme.to_mesh(me)
        hole_bme.free()
        
        return {'FINISHED'}  


class D3MODEL_OT_create_metaball_honeycomb(bpy.types.Operator):
    """Create Bmesh Honeycomb"""
    bl_idname = "d3splint.object_honeycomb_surface"
    bl_label = "Honeycomb Object Suface"
    bl_options = {'REGISTER', 'UNDO'}
    

    hole_spacing = bpy.props.FloatProperty(name = 'element width', default = 4.0, min = 1.5, max = 8.0)
    hole_diameter  = bpy.props.FloatProperty(name = 'hole width', default = 1.0, min = .5, max = 3.0)
    thickness = bpy.props.FloatProperty(name = 'thickness', default = 2.0, min = .25, max = 9.0)
    
    snap = bpy.props.BoolProperty(name ='Snap to Source', default = True)
    snap_offset = bpy.props.FloatProperty(name = 'Snapp Offset', default = 0.0)
    
    def invoke(self, context, event):
        #return context.window_manager.invoke_props_popup(self, event)
        return context.window_manager.invoke_props_dialog(self)
    def execute(self, context):
        
        d_res = 1/self.hole_spacing
        hole_radius = min(.5 * self.hole_spacing, .5 * self.hole_diameter)
        extrude_scale = hole_radius/self.hole_spacing
                
        scaffold = create_dyntopo_meta_scaffold(context.object, d_res, return_type = 'OBJECT')
        mod = scaffold.modifiers.new('Catmul Clark', type = 'SUBSURF')
        
        mod2 = scaffold.modifiers.new('ShrinkWrap', type = 'SHRINKWRAP')
        mod2.target = context.object
        mod2.wrap_method = 'NEAREST_SURFACEPOINT'
        if abs(self.snap_offset) > .1:
            mod2.use_keep_above_surface = True
            mod2.offset = self.snap_offset
        
        me = scaffold.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        bme = bmesh.new()
        bme.from_mesh(me)
        
        hole_bme, round_bme = honeycomb_bme(bme, hole_radius, offset = extrude_scale)
        
        if 'Honeycomb' not in bpy.data.objects:
            me = bpy.data.meshes.new('Honeycomb')
            ob = bpy.data.objects.new('Honeycomb', me)
            bpy.context.scene.objects.link(ob)
            ob.show_wire = True
            ob.show_all_edges = True
            ob.matrix_world = context.object.matrix_world
        else:
            ob = bpy.data.objects.get('Honeycomb')
        bme.to_mesh(me)
        bme.free()
        
        if 'Honeycomb Holes' not in bpy.data.objects:
            me = bpy.data.meshes.new('Honeycomb Holes')
            ob = bpy.data.objects.new('Honeycomb  Holes', me)
            bpy.context.scene.objects.link(ob)
            ob.matrix_world = context.object.matrix_world
        else:
            ob = bpy.data.objects.get('Honeycomb Holes')
        round_bme.to_mesh(me)
        round_bme.free()
        
        #hole_bme.to_mesh(me)
        hole_bme.free()
        
        return {'FINISHED'}  
 
 
class D3MODEL_OT_create_metaball_grid(bpy.types.Operator):
    """Create Bmesh Honeycomb"""
    bl_idname = "d3model.object_volumetric_grid"
    bl_label = "Volumetric Grid Object"
    bl_options = {'REGISTER', 'UNDO'}
    

    hole_diameter  = bpy.props.FloatProperty(name = 'Hole Diameter', default = 6.0, min = .5, max = 10.0)
    wall_thickness = bpy.props.FloatProperty(name = 'Wall Thicknes', default = 2.0, min = .25, max = 9.0)
    
    method = bpy.props.EnumProperty(
        description="",
        items=(("HEXAGON_NET","HEXAGON_NET","HEXAGON_NET"),
               ("DIAMOND_NET","DIAMOND_NET","DIAMOND_NET")),
        default="HEXAGON_NET",
        )
    
    grid_repeats = bpy.props.IntProperty(name = 'Repeats', default = 10, min = 2, max = 50)
    resolution = bpy.props.FloatProperty(name = 'Mesh Resolution', default = .3, min = .2, max = 3.0)
    
    
    def invoke(self, context, event):
        #return context.window_manager.invoke_props_popup(self, event)
        return context.window_manager.invoke_props_dialog(self)
    
    
    def execute(self, context):
        
        
        outer_diameter = self.hole_diameter + self.wall_thickness
        ob = make_grid_object(outer_diameter, 1.0, 1.0, self.grid_repeats, self.method, False)
        
        context.scene.objects.link(ob)
        context.scene.update()
        
        
        
        me = ob.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
        
        
        bme = bmesh.new()
        bme.from_mesh(me)
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        bounds = bound_box_bmverts(bme.verts[:])
        center = bbox_center(bounds)
        print('TRANSFORMING THE GRID')
        print(center)
        T = Matrix.Translation(center)
        imx = T.inverted()
        bme.transform(imx)
        
        edge_shrink = .2
        
        metadata = bpy.data.metaballs.new('Meta Grid')
        metadata.resolution = self.resolution
        meta_obj = bpy.data.objects.new('Meta Grid', metadata)
        
        for ed in bme.edges:
            X = ed.verts[1].co - ed.verts[0].co
            r = (ed.verts[1].co - ed.verts[0].co).length
            X.normalize()
            Z = Vector((0,0,1))
            Y = Z.cross(X)
            R = Matrix.Identity(3)  #make the columns of matrix U, V, W
            R[0][0], R[0][1], R[0][2]  = X[0] ,Y[0],  Z[0]
            R[1][0], R[1][1], R[1][2]  = X[1], Y[1],  Z[1]
            R[2][0] ,R[2][1], R[2][2]  = X[2], Y[2],  Z[2]
            quat = R.to_4x4().to_quaternion()
            center = .5 * (ed.verts[0].co + ed.verts[1].co)

            
            cube = metadata.elements.new(type = 'CUBE')
            cube.co = center + 5.0 * Z
        
            cube.size_x = .5 * r
            cube.size_y = .5 * (self.wall_thickness - .2)
            cube.size_z = 5.0
            cube.radius = 0.2
            cube.stiffness = 1.0
            cube.rotation = quat
        
        context.scene.objects.link(meta_obj)
        return {'FINISHED'}  
    