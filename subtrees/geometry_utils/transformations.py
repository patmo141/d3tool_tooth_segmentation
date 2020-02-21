'''
Helper tools for transformations
'''
import random
import math
import time

from mathutils import Vector, Matrix, Quaternion

#TODO put these somewhere.  addon_common.transform?
# calculate a best-fit plane to the given vertices
#modified from looptoos script
def calculate_plane(locs, itermax = 500, debug = False):
    '''
    args: 
    vertex_locs - a list of type Vector
    return:
    normal of best fit plane
    '''
    if debug:
        start = time.time()
        n_verts = len(locs)
    
    # calculating the center of masss
    com = Vector()
    for loc in locs:
        com += loc
    com /= len(locs)
    x, y, z = com
    
    # creating the covariance matrix
    mat = Matrix(((0.0, 0.0, 0.0),
                  (0.0, 0.0, 0.0),
                  (0.0, 0.0, 0.0),
                   ))
    for loc in locs:
        mat[0][0] += (loc[0]-x)**2
        mat[1][0] += (loc[0]-x)*(loc[1]-y)
        mat[2][0] += (loc[0]-x)*(loc[2]-z)
        mat[0][1] += (loc[1]-y)*(loc[0]-x)
        mat[1][1] += (loc[1]-y)**2
        mat[2][1] += (loc[1]-y)*(loc[2]-z)
        mat[0][2] += (loc[2]-z)*(loc[0]-x)
        mat[1][2] += (loc[2]-z)*(loc[1]-y)
        mat[2][2] += (loc[2]-z)**2
    
    # calculating the normal to the plane
    normal = False
    try:
        mat.invert()
    except:
        if sum(mat[0]) == 0.0:
            normal = Vector((1.0, 0.0, 0.0))
        elif sum(mat[1]) == 0.0:
            normal = Vector((0.0, 1.0, 0.0))
        elif sum(mat[2]) == 0.0:
            normal = Vector((0.0, 0.0, 1.0))
    if not normal:
        # warning! this is different from .normalize()
        iters = 0
        vec = Vector((1.0, 1.0, 1.0))
        vec2 = (mat * vec)/(mat * vec).length
        while vec != vec2 and iters < itermax:
            iters+=1
            vec = vec2
            vec2 = mat * vec
            if vec2.length != 0:
                vec2 /= vec2.length
        if vec2.length == 0:
            vec2 = Vector((1.0, 1.0, 1.0))
        normal = vec2


    if debug:
        if iters == itermax:
            print("looks like we maxed out our iterations")
        print("found plane normal for %d verts in %f seconds" % (n_verts, time.time() - start))
    
    return Vector((x,y,z)), normal   


def random_axes_from_normal(z):
    Z = z.normalized()
    x = Vector((random.random(), random.random(), random.random()))
    X = x - x.dot(Z)*Z
    X.normalize()
    
    Y = Z.cross(X)
    
    return X, Y, Z


def r_matrix_from_principal_axes(X, Y, Z):
    
    T = Matrix.Identity(3)  #make the columns of matrix U, V, W
    T[0][0], T[0][1], T[0][2]  = X[0] ,Y[0],  Z[0]
    T[1][0], T[1][1], T[1][2]  = X[1], Y[1],  Z[1]
    T[2][0] ,T[2][1], T[2][2]  = X[2], Y[2],  Z[2]
    
    return T

#TODO, put this somewhere logical and useful
def vector_angle_between(v0, v1, vcross):
    a = v0.angle(v1)
    d = v0.cross(v1).dot(vcross)
    return a if d>0 else 2*math.pi - a

def sort_objects_by_angles(vec_about, l_objs, l_vecs):
    '''
    sort a list of objects, around a normal vector,
    with a corresponding list of vectors.
    the first object, vector pair will remain the 0th item in the list
    and others will be sorted relative to it
    '''
    if len(l_objs) <= 1:  return l_objs
    o0,v0 = l_objs[0],l_vecs[0]
    l_angles = [0] + [vector_angle_between(v0,v1,vec_about) for v1 in l_vecs[1:]]
    l_inds = sorted(range(len(l_objs)), key=lambda i: l_angles[i])
    return [l_objs[i] for i in l_inds]

def delta_angles(vec_about, l_vecs):
    '''
    will find the difference betwen each element and the next element in the list
    this is a foward difference.  Eg delta[n] = item[n+1] - item[n]
    
    deltas should add up to 2*pi
    '''
    
    v0 = l_vecs[0]
    l_angles = [0] + [vector_angle_between(v0,v1,vec_about) for v1 in l_vecs[1:]]
    
    L = len(l_angles)
    
    deltas = [l_angles[n + 1] - l_angles[n] for n in range(0, L-1)] + [2*math.pi - l_angles[-1]]
    return deltas


def calc_angle(v):
                
    #use link edges and non_man eds
    eds_non_man = [ed for ed in v.link_edges if len(ed.link_faces) == 1]
    if len(eds_non_man) == 0:
        print('this is not a hole perimeter vertex')
        return 2 * math.pi, None, None
    
        
    eds_all = [ed for ed in v.link_edges]
    
    #shift list to start with a non manifold edge if needed
    base_ind = eds_all.index(eds_non_man[0])
    eds_all = eds_all[base_ind:] + eds_all[:base_ind]
    
    #vector representation of edges
    eds_vecs = [ed.other_vert(v).co - v.co for ed in eds_all]
    
    if len(eds_non_man) != 2:
        print("more than 2 non manifold edges, loop self intersects or there is a dangling edge")
        return 2 * math.pi, None, None
    
    
    va = eds_non_man[0].other_vert(v)
    vb = eds_non_man[1].other_vert(v)
    
    Va = va.co - v.co
    Vb = vb.co - v.co
    
    if Va.length < .00001 or Vb.length < .00001:
        print("zero length edge")
        return 2 * math.pi, None, None
    
    angle = Va.angle(Vb)
    
    #check for connectivity
    if len(eds_all) == 2:
        if any([ed.other_vert(va) == vb for ed in vb.link_edges]):
            #already a tri over here
            #print('va and vb connect')
            return 2 * math.pi, None, None
    
        elif any([f in eds_non_man[0].link_faces for f in eds_non_man[1].link_faces]):
            #print('va and vb share face')
            return 2 * math.pi, None, None
        
        else: #completely regular situation
            
            if Va.cross(Vb).dot(v.normal) < 0:
                print('keep normals consistent reverse')
                return angle, vb, va
            else:
                return angle, va, vb
    
    elif len(eds_all) > 2:
        #sort edges ccw by normal, starting at eds_nm[0]
        eds_sorted = sort_objects_by_angles(v.normal, eds_all, eds_vecs)
        vecs_sorted = [ed.other_vert(v).co - v.co for ed in eds_sorted]
        deltas = delta_angles(v.normal, vecs_sorted)
        ed1_ind = eds_sorted.index(eds_non_man[1])
        
        #delta_forward = sum(deltas[:ed1_ind])
        #delta_reverse = sum(deltas[ed1_ind:])
        
        if Va.cross(Vb).dot(v.normal) > 0:
        
            if ed1_ind == 1:
            

                return angle, va, vb
            
            elif ed1_ind == (len(eds_sorted) - 1):
                
                return 2*math.pi - angle, vb, va
            
            else:
                #PROBLEMS!
                #print("Sorted angle is %i in the list" % ed1_ind)
                return angle, va, vb
        
        else:
                
            if ed1_ind == 1:
                return 2*math.pi - angle, va, vb
            
            elif ed1_ind == (len(eds_sorted) - 1):
                return angle, vb, va
            
            else:
                #PROBLEMS!
                #print("BIG BIG PROBLEMS")
                return angle, vb, va

def clockwise_loop(vert_loop, z):
    
    
    vcoords = [v.co for v in vert_loop]
    vcoords += [vcoords[0], vcoords[1]]
    l = len(vcoords)
    curl = 0
    
    for n in range(0,l-2):
        #Vec representation of the two edges
        V0 = (vcoords[n+1] - vcoords[n])
        V1 = (vcoords[n+2] - vcoords[n+1])
        
        ##XY projection
        T0 = V0 - V0.project(z)
        T1 = V1 - V1.project(z)
        
        cross = T0.cross(T1)        
        sign = 1
        if cross.dot(z) < 0:
            sign = -1
        
        rot = T0.rotation_difference(T1)  
        ang = rot.angle
        curl = curl + ang*sign
        

    if curl < 0:
        return False
    else:
        return True
    
