import math

import bpy
import bmesh
from mathutils import Matrix, Vector, Color
import loops_tools
from mathutils.bvhtree import BVHTree

 
def face_neighbors(bmface):
    neighbors = []
    for ed in bmface.edges:
        neighbors += [f for f in ed.link_faces if f != bmface]
        
    return neighbors

def face_neighbors_by_vert(bmface):
    neighbors = []
    for v in bmface.verts:
        neighbors += [f for f in v.link_faces if f != bmface]
        
    return neighbors 
 
def flood_selection_faces(bme, selected_faces, seed_face, expansion_mode = 'VERTEX', max_iters = 1000):
    '''
    bme - bmesh
    selected_faces - should create a closed face loop to contain "flooded" selection
    if an empty set, selection will grow to non manifold boundaries
    seed_face - a BMFace within/out selected_faces loop, or a LIST of faces
    expansion_mode = 'VERTEX' or 'EDGE' will epxand based on edge.link_faces or v.link_faces
    max_iters - maximum recursions to select_neightbors
    
    returns:
        -a set of BMFaces
    '''
    total_selection = set([f for f in selected_faces])
    levy = set([f for f in selected_faces])  #it's funny because it stops the flood :-)

    if expansion_mode == 'VERTEX':
        neighbor_fn = face_neighbors_by_vert
    else:
        neighbor_fn = face_neighbors
        
        
    if isinstance(seed_face, bmesh.types.BMFace):
        new_faces = set(neighbor_fn(seed_face)) - levy
        
    elif isinstance(seed_face, list):
        new_candidates = set()
        for f in seed_face:
            new_candidates.update(neighbor_fn(f))   
        new_faces = new_candidates - total_selection
        total_selection |= new_faces
    
    elif isinstance(seed_face, set):
        new_candidates = set()
        for f in seed_face:
            new_candidates.update(neighbor_fn(f))   
        new_faces = new_candidates - total_selection
        total_selection |= new_faces
            
    iters = 0
    while iters < max_iters and new_faces:
        iters += 1
        new_candidates = set()
        for f in new_faces:
            new_candidates.update(neighbor_fn(f))
            
        new_faces = new_candidates - total_selection
        
        if new_faces:
            total_selection |= new_faces    
    if iters == max_iters:
        print('max iterations reached')    
    return total_selection   
    
def bmesh_loose_parts(bme, selected_faces = None, max_iters = 100): 
    '''
    bme - BMesh
    selected_faces = list, set or None
    max_iters = maximum amount
    
    return - list of lists of BMFaces
    '''
    if selected_faces == None:
        total_faces = set(bme.faces[:])
    else:
        if isinstance(selected_faces, list):
            total_faces = set(selected_faces)
        elif isinstance(selected_faces, set):
            total_faces = selected_faces.copy()
            
        else:
            #raise exception
            return []
        
    islands = []
    iters = 0
    while len(total_faces) and iters < max_iters:
        iters += 1
        seed = total_faces.pop()
        island = flood_selection_faces(bme, {}, seed, max_iters = 10000)
        islands += [island]
        total_faces.difference_update(island)
    
    return islands
 
def bme_rip_vertex(bme, bmvert):
    
    fs = [f for f in bmvert.link_faces]
    
    for f in fs:
        vs = [v for v in f.verts]  #these come in order
        new_v = bme.verts.new(bmvert.co)
        
        #find the ripping vert
        ind = vs.index(bmvert)
        #replace it with the new vertex
        vs[ind] = new_v
        
        #create a new face
        new_f = bme.faces.new(vs)
        
    bmesh.ops.delete(bme, geom = [bmvert], context = 1)
    
    
def bme_linked_flat_faces(bme, start_face, angle, iter_max = 10000):
    '''
    args:
        bme - BMesh object
        start_face = BMFace
        angl - angle in degrees
    
    return:  list of BMFaces
    '''
    
    no = start_face.normal
    angl_rad = math.pi/180 * angle
    
    #intiiate the flat faces
    flat_faces = set([start_face])
    
    #how we detect flat neighbors
    def flat_neighbors(bmf):
        neighbors = set()
        for v in bmf.verts:
            neighbors.update([f for f in v.link_faces if f not in flat_faces and f != bmf])
            flat_neighbors = set([f for f in neighbors if f.normal.dot(no) > 0 and f.normal.angle(no) < angl_rad])
        return flat_neighbors
    
    
    new_faces = flat_neighbors(start_face)
    
    iters = 0
    while len(new_faces) and iters < iter_max:
        iters += 1
        flat_faces |= new_faces
        
        newer_faces = set()
        for f in new_faces:
            newer_faces |= flat_neighbors(f)
             
        new_faces = newer_faces
    
    return list(flat_faces)


def remove_undercuts(context, ob, view, world = True, smooth = True, epsilon = .000001):
    '''
    args:
      ob - mesh object
      view - Mathutils Vector
      
    return:
       Bmesh with Undercuts Removed?
       
    best to make sure normals are consistent beforehand
    best for manifold meshes, however non-man works
    noisy meshes can be compensated for with island threhold
    '''
    
        
    #careful, this can get expensive with multires
    me = ob.to_mesh(context.scene, True, 'RENDER')    
    bme = bmesh.new()
    bme.from_mesh(me)
    bme.normal_update()
    bme.verts.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    bme.faces.ensure_lookup_table()
    
    bvh = BVHTree.FromBMesh(bme)
    
    #keep track of the world matrix
    mx = ob.matrix_world
    
    if world:
        #meaning the vector is in world coords
        #we need to take it back into local
        i_mx = mx.inverted()
        view = i_mx.to_quaternion() * view
            
    face_directions = [[0]] * len(bme.faces)
    
    up_faces = set()
    overhang_faces = set()  #all faces pointing away from view
    #precalc all the face directions and store in dict
    for f in bme.faces:
        direction = f.normal.dot(view)
        
        if direction <= -epsilon:
            overhang_faces.add(f)
        else:
            up_faces.add(f)
            
        face_directions[f.index] = direction
    
    print('there are %i up_faces' % len(up_faces))
    print('there are %i down_faces' % len(overhang_faces))
    
    
    #for f in bme.faces:
    #    if f in overhangs:
    #        f.select_set(True)
    #    else:
    #        f.select_set(False)
            
    overhang_islands = [] #islands bigger than a certain threshold (by surface area?
    upfacing_islands = []
    def face_neighbors_up(bmface):
        neighbors = []
        for ed in bmface.edges:
            neighbors += [f for f in ed.link_faces if f != bmface and f in up_faces]
            
        return neighbors
    #remove smal islands from up_faces and add to overhangs
    max_iters = len(up_faces)
    iters_0 = 0
    islands_removed = 0
    
    up_faces_copy = up_faces.copy()
    while len(up_faces_copy) and iters_0 < max_iters:
        iters_0 += 1
        max_iters_1 = len(up_faces)
        seed = up_faces_copy.pop()
        new_faces = set(face_neighbors_up(seed))
        up_faces_copy -= new_faces
        
        island = set([seed])
        island |= new_faces
        
        iters_1 = 0
        while iters_1 < max_iters_1 and new_faces:
            iters_1 += 1
            new_candidates = set()
            for f in new_faces:
                new_candidates.update(face_neighbors_up(f))
            
            new_faces = new_candidates - island
        
            if new_faces:
                island |= new_faces    
                up_faces_copy -= new_faces
        if len(island) < 75: #small patch surrounded by overhang, add to overhang area
            islands_removed += 1
            overhang_faces |= island
        else:
            upfacing_islands += [island]
            
    print('%i upfacing islands removed' % islands_removed)
    print('there are now %i down faces' % len(overhang_faces))
    
    def face_neighbors_down(bmface):
        neighbors = []
        for ed in bmface.edges:
            neighbors += [f for f in ed.link_faces if f != bmface and f in overhang_faces]
            
        return neighbors
    overhang_faces_copy = overhang_faces.copy()
    
    while len(overhang_faces_copy):
        seed = overhang_faces_copy.pop()
        new_faces = set(face_neighbors_down(seed))
        island = set([seed])
        island |= new_faces
        overhang_faces_copy -= new_faces
        iters = 0
        while iters < 100000 and new_faces:
            iters += 1
            new_candidates = set()
            for f in new_faces:
                new_candidates.update(face_neighbors_down(f))
            
            new_faces = new_candidates - island
        
            if new_faces:
                island |= new_faces    
                overhang_faces_copy -= new_faces
        if len(island) > 75: #TODO, calc overhang factor.  Surface area dotted with direction
            overhang_islands += [island]
    
    for f in bme.faces:
        f.select_set(False)   
    for ed in bme.edges:
        ed.select_set(False)
    for v in bme.verts:
        v.select_set(False)
            
    island_loops = []
    island_verts = []
    del_faces = set()
    for isl in overhang_islands:
        loop_eds = []
        loop_verts = []
        del_faces |= isl
        for f in isl:
            for ed in f.edges:
                if len(ed.link_faces) == 1:
                    loop_eds += [ed]
                    loop_verts += [ed.verts[0], ed.verts[1]]
                elif (ed.link_faces[0] in isl) and (ed.link_faces[1] not in isl):
                    loop_eds += [ed]
                    loop_verts += [ed.verts[0], ed.verts[1]]
                elif (ed.link_faces[1] in isl) and (ed.link_faces[0] not in isl):
                    loop_eds += [ed]
                    loop_verts += [ed.verts[0], ed.verts[1]]
                    
            #f.select_set(True) 
        island_verts += [list(set(loop_verts))]
        island_loops += [loop_eds]
    
    bme.faces.ensure_lookup_table()
    bme.edges.ensure_lookup_table()
    
    loop_edges = []
    for ed_loop in island_loops:
        loop_edges += ed_loop
        for ed in ed_loop:
            ed.select_set(True)
    
    loops_tools.relax_loops_util(bme, loop_edges, 5)
    
    for ed in bme.edges:
        ed.select_set(False)
        
    exclude_vs = set()
    for vs in island_verts:
        exclude_vs.update(vs)
    
    smooth_verts = []    
    for v in exclude_vs:
        smooth_verts += [ed.other_vert(v) for ed in v.link_edges if ed.other_vert(v) not in exclude_vs]
            
    ret = bmesh.ops.extrude_edge_only(bme, edges = loop_edges)
    
    
    new_fs = [ele for ele in ret['geom'] if isinstance(ele, bmesh.types.BMFace)]                
    new_vs = [ele for ele in ret['geom'] if isinstance(ele, bmesh.types.BMVert)]
    
    #TODO, ray cast down to base plane?
    for v in new_vs:
        v.co -= 10*view
    
    for f in new_fs:
        f.select_set(True)
        
    bmesh.ops.delete(bme, geom = list(del_faces), context = 3)
    
    del_verts = []
    for v in bme.verts:
        if all([f in del_faces for f in v.link_faces]):
            del_verts += [v]        
    bmesh.ops.delete(bme, geom = del_verts, context = 1)
    
    
    del_edges = []
    for ed in bme.edges:
        if len(ed.link_faces) == 0:
            del_edges += [ed]
    print('deleting %i edges' % len(del_edges))
    bmesh.ops.delete(bme, geom = del_edges, context = 4) 
    bmesh.ops.recalc_face_normals(bme, faces = new_fs)
    
    bme.normal_update()
    
    new_me = bpy.data.meshes.new(ob.name + '_blockout')
    
    obj = bpy.data.objects.new(new_me.name, new_me)
    context.scene.objects.link(obj)
    
    obj.select = True
    context.scene.objects.active = obj
    
    bme.to_mesh(obj.data)
    # Get material
    mat = bpy.data.materials.get("Model Material")
    if mat is None:
        # create material
        print('creating model material')
        mat = bpy.data.materials.new(name="Model Material")
        #mat.diffuse_color = Color((0.8, .8, .8))
    
    # Assign it to object
    obj.data.materials.append(mat)
    print('Model material added')
    
    mat2 = bpy.data.materials.get("Undercut Material")
    if mat2 is None:
        # create material
        mat2 = bpy.data.materials.new(name="Undercut Material")
        mat2.diffuse_color = Color((0.8, .2, .2))
    

    obj.data.materials.append(mat2)
    mat_ind = obj.data.materials.find("Undercut Material")
    print('Undercut material is %i' % mat_ind)
    
    for f in new_faces:
        obj.data.polygons[f.index].material_index = mat_ind
            
    if world:
        obj.matrix_world = mx

    bme.free()
    del bvh
        
    return


def join_bmesh_map(source, target, src_trg_map = None, src_mx = None, trg_mx = None):
    '''
    
    '''
    
 
    L = len(target.verts)
    
    if not src_trg_map:
        src_trg_map = {-1:-1}
    l = len(src_trg_map)
    print('There are %i items in the vert map' % len(src_trg_map))
    if not src_mx:
        src_mx = Matrix.Identity(4)
    
    if not trg_mx:
        trg_mx = Matrix.Identity(4)
        i_trg_mx = Matrix.Identity(4)
    else:
        i_trg_mx = trg_mx.inverted()
        
        
    old_bmverts = [v for v in target.verts]  #this will store them in order
    new_bmverts = [] #these will be created in order
    
    source.verts.ensure_lookup_table()

    for v in source.verts:
        if v.index not in src_trg_map:
            new_ind = len(target.verts)
            new_bv = target.verts.new(i_trg_mx * src_mx * v.co)
            new_bmverts.append(new_bv)  #gross...append
            src_trg_map[v.index] = new_ind
            
        else:
            print('vert alread in the map %i' % v.index)
    
    lverts = old_bmverts + new_bmverts
    
    target.verts.index_update()
    target.verts.ensure_lookup_table()
    
    new_bmfaces = []
    for f in source.faces:
        v_inds = []
        for v in f.verts:
            new_ind = src_trg_map[v.index]
            v_inds.append(new_ind)
            
        if any([i > len(lverts)-1 for i in v_inds]):
            print('impending index error')
            print(len(lverts))
            print(v_inds)
            
        if target.faces.get(tuple(lverts[i] for i in v_inds)):
            print(v_inds)
            continue
        new_bmfaces += [target.faces.new(tuple(lverts[i] for i in v_inds))]
    
        target.faces.ensure_lookup_table()
    target.verts.ensure_lookup_table()

    new_L = len(target.verts)
    
    if src_trg_map:
        if new_L != L + len(source.verts) -l:
            print('seems some verts were left in that should not have been')
 
def join_bmesh(source, target, src_mx = None, trg_mx = None):

    src_trg_map = dict()
    L = len(target.verts)
    if not src_mx:
        src_mx = Matrix.Identity(4)
    
    if not trg_mx:
        trg_mx = Matrix.Identity(4)
        i_trg_mx = Matrix.Identity(4)
    else:
        i_trg_mx = trg_mx.inverted()
        
        
    new_bmverts = []
    source.verts.ensure_lookup_table()

    for v in source.verts:
        if v.index not in src_trg_map:
            new_ind = len(target.verts)
            new_bv = target.verts.new(i_trg_mx * src_mx * v.co)
            new_bmverts.append(new_bv)
            src_trg_map[v.index] = new_ind
    
    
    target.verts.index_update()
    target.verts.ensure_lookup_table()

    new_bmfaces = []
    for f in source.faces:
        v_inds = []
        for v in f.verts:
            new_ind = src_trg_map[v.index]
            v_inds.append(new_ind)
            
        new_bmfaces += [target.faces.new(tuple(target.verts[i] for i in v_inds))]
    
    target.faces.ensure_lookup_table()
    target.verts.ensure_lookup_table()
    target.verts.index_update()
    
   
    target.verts.index_update()        
    target.verts.ensure_lookup_table()
    target.faces.ensure_lookup_table()
    
    new_L = len(target.verts)
    

    if new_L != L + len(source.verts):
        print('seems some verts were left out')
            

def new_bmesh_from_bmelements(geom):
    
    out_bme = bmesh.new()
    out_bme.verts.ensure_lookup_table()
    out_bme.faces.ensure_lookup_table()
    
    faces = [ele for ele in geom if isinstance(ele, bmesh.types.BMFace)]
    verts = [ele for ele in geom if isinstance(ele, bmesh.types.BMVert)]
    
    vs = set(verts)
    for f in faces:
        vs.update(f.verts[:])
        
    src_trg_map = dict()
    new_bmverts = []
    for v in vs:
    
        new_ind = len(out_bme.verts)
        new_bv = out_bme.verts.new(v.co)
        new_bmverts.append(new_bv)
        src_trg_map[v.index] = new_ind
    
    out_bme.verts.ensure_lookup_table()
    out_bme.faces.ensure_lookup_table()
        
    new_bmfaces = []
    for f in faces:
        v_inds = []
        for v in f.verts:
            new_ind = src_trg_map[v.index]
            v_inds.append(new_ind)
            
        new_bmfaces += [out_bme.faces.new(tuple(out_bme.verts[i] for i in v_inds))]
        
    out_bme.faces.ensure_lookup_table()
    out_bme.verts.ensure_lookup_table()
    out_bme.verts.index_update()
    
   
    out_bme.verts.index_update()        
    out_bme.verts.ensure_lookup_table()
    out_bme.faces.ensure_lookup_table()
    
    return out_bme       
def join_objects(obs, name = ''):
    '''
    uses BMesh to join objects.  Advantage is that it is context
    agnostic, so no editmoe or bpy.ops has to be used.
    
    Args:
        obs - list of Blender objects
    
    Returns:
        new object with name specified.  Otherwise '_joined' will
        be added to the name of the first object in the list
    '''
    target_bme = bmesh.new()
    target_bme.verts.ensure_lookup_table()
    target_bme.faces.ensure_lookup_table()
    trg_mx = obs[0].matrix_world
    
    if name == '':
        name = obs[0].name + '_joined'
    
    for ob in obs:
        src_mx = ob.matrix_world

        if ob.data.is_editmode:
            src_bme = bmesh.from_editmesh(ob.data)
        else:
            src_bme = bmesh.new()
            if ob.type == 'MESH':
                if len(ob.modifiers):
                    src_bme.from_object(ob, bpy.context.scene)
                else:
                    src_bme.from_mesh(ob.data)
            else:
                me = ob.to_mesh(bpy.context.scene, apply_modifiers = True, settings = 'PREVIEW')
                src_bme.from_mesh(me)
                bpy.data.meshes.remove(me)
        join_bmesh(src_bme, target_bme, src_mx, trg_mx)

        src_bme.free()
    
    new_me = bpy.data.meshes.new(name)    
    new_ob = bpy.data.objects.new(name, new_me)
    new_ob.matrix_world = trg_mx
    target_bme.to_mesh(new_me)
    target_bme.free()
    return new_ob
    

def bound_box_bmverts(bmvs):
    bounds = []
    for i in range(0,3):
        components = [v.co[i] for v in bmvs]
        low = min(components)
        high = max(components)
        bounds.append((low,high))

    return bounds

def bbox_center(bounds):
    
    x = 0.5 * (bounds[0][0] + bounds[0][1])
    y = 0.5 * (bounds[1][0] + bounds[1][1])
    z = 0.5 * (bounds[2][0] + bounds[2][1])
    
    return Vector((x,y,z))
