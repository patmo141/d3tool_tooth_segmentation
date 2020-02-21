'''
Created on Sep 1, 2019

@author: Patrick

adapted from animation nodes usage of openvdb addon
'''
import time
import bmesh

from .vdb_remesh import vdb_remesh, read_bmesh, write_fast, write_slow


def remesh_bme(bme, 
              isovalue = 0.0, 
              adaptivity = 0.0, 
              only_quads = False, 
              voxel_size = .25,
              filter_iterations = 0,
              filter_width = 4,
              filter_sigma = 1.0,
              grid = None,
              write_method = 'FAST'):
    
    ngons = [f for f in bme.faces if len(f.verts) > 4]
    if len(ngons):
        bmesh.ops.triangulate(
                        bme, faces=ngons, quad_method=0, ngon_method=0
                    )
    nverts, ntris, nquads = read_bmesh(bme)
    new_mesh, cache_grid = vdb_remesh(
            nverts,
            ntris,
            nquads,
            isovalue,
            (adaptivity / 100.0) ** 2,
            only_quads,
            voxel_size,
            filter_iterations,
            filter_width,
            "blur",
            filter_sigma,
            grid = None,
        )
    
    write_time = time.time()
    if write_method =='FAST':
        remesh = write_fast(*new_mesh)
        remesh_bme = bmesh.new()
        remesh_bme.from_mesh(remesh)
    else:
        remesh_bme = write_slow(*new_mesh)
        
    write_finish = time.time()
    print('Took %f seconds to write with %s method' % ((write_finish - write_time), write_method))
    
    return remesh_bme

def vdb_offset(bme, offset_amount, voxel_size, isovalue):
    '''
    this is meant to negatively offset a closed, mainfold mesh
    '''
    pass
    #solidify
    #vdb_remesh
    #check for # of shells
    #if only one, ....try direct negative method
    
    #if 2 or more: 
    #strip off outer shell
    #flip normals
    
    #return
    
    
def vdb_csg_operation_stack(obs_ops):
    pass
    #ob