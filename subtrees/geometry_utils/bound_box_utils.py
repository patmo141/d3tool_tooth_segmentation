'''
Created on Sep 11, 2019

@author: Patrick
'''
import bpy

from mathutils import Vector, Matrix

def bound_box_vectors(vs):
    bounds = []
    for i in range(0,3):
        components = [v[i] for v in vs]
        low = min(components)
        high = max(components)
        bounds.append((low,high))

    return bounds


def get_bbox_center(ob, world = True):
    
    if world:
        mx = ob.matrix_world
    else:
        mx = Matrix.Identity(3)
        
    box_center = Vector((0,0,0))
    for v in ob.bound_box:
        box_center += mx * Vector(v)
    box_center *= 1/8
    
    return box_center

def bbox_to_lattice(scene, ob):
    
    mx = ob.matrix_world
    loc = get_bbox_center(ob, world=True)
    size = Vector((ob.dimensions[0], ob.dimensions[1], ob.dimensions[2]))
    
    lat_data = bpy.data.lattices.new(ob.name[0:2] + "_control")
    
    
    lat = bpy.data.objects.new(lat_data.name, lat_data)
    
    
    lat.location = loc
    lat.scale = 1.05*size
    lat.layers[1] = True
    lat.layers[0] = True
    
    
    if lat.rotation_mode != 'QUATERNION':
        lat.rotation_mode = 'QUATERNION'
        
    
    lat.rotation_quaternion = mx.to_quaternion()
    
    lat.update_tag()
    scene.objects.link(lat)
    
    scene.update()
    lat.data.points_u = 3
    lat.data.points_v = 3
    lat.data.points_w = 3
    
    
    lat_mod = ob.modifiers.new('Lattice','LATTICE')
    
    lat_mod.object = lat
    return lat  #in case you want to delete it after youe apply it.