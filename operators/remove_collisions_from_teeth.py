'''
Created on Dec 25, 2020

@author: Patrick
'''
import bpy
import bmesh
from mathutils.bvhtree import BVHTree

from .. import tooth_numbering


class AITeeth_OT_remove_collisions_projection(bpy.types.Operator):
    """Remove Collisions from teeth.  if using upper/lower arch filter it will remove proximal contacts.  If not using that filter, it will remove all collisions including contacts"""
    bl_idname = "ai_teeth.remove_convex_collisions"
    bl_label = "Remove Tooth Collisions"

    
    
    iterations = bpy.props.IntProperty(default = 2, min = 1, max = 5, description = 'Number of iterations')
    factor = bpy.props.FloatProperty(default = .25, min = .1, max = .5, description = 'Distance percentage per iteration')
    
    @classmethod
    def poll(cls, context):

        return True

    def invoke(self, context, event):

        
        return context.window_manager.invoke_props_dialog(self, width = 300)
    

            
    def execute(self, context):
        
        
        selected_teeth = [ob for ob in bpy.data.objects if 'Convex' in ob.name]
        upper_teeth = [ob for ob in selected_teeth if tooth_numbering.data_tooth_label(ob.name.split(' ')[0]) in tooth_numbering.upper_teeth]
        lower_teeth = [ob for ob in selected_teeth if tooth_numbering.data_tooth_label(ob.name.split(' ')[0]) in tooth_numbering.lower_teeth]
        
        main(upper_teeth, self.iterations, self.factor)
        main(lower_teeth, self.iterations, self.factor)
    
        return {'FINISHED'}
    
    
 

def main(obs, iterations, factor): 
    for ob in obs:
        ob.data.update()
        
    overlap_pairs = generate_pairs(obs)
    
    print(overlap_pairs)    
    bvhs = {}  #dictionary
    for n in range(0, iterations):
        for pair in overlap_pairs:
            
            ob0 = bpy.data.objects.get(pair[0])
            ob1 = bpy.data.objects.get(pair[1])
            decollide_pair(ob0, ob1, bvhs, factor)  #this function is altering bvhs
            
            
def decollide_pair(ob0, ob1, bvhs, factor):  

    if ob0 in bvhs:
        bvh0 = bvhs[ob0]
    else:
        bvh0 = BVHTree.FromObject(ob0, bpy.context.scene)
        bvhs[ob0] = bvh0
        
    mx0 = ob0.matrix_world
    imx0= mx0.inverted()
    mxno0 = imx0.transposed().to_3x3() 
    loc0 = mx0.to_translation()
    
    if ob1 in bvhs:
        bvh1 = bvhs[ob1]
    else:
        bvh1 = BVHTree.FromObject(ob1, bpy.context.scene)
        bvhs[ob1] = bvh1
    
    mx1 = ob1.matrix_world
    imx1= mx1.inverted()
    mxno1 = imx1.transposed().to_3x3() 
    loc1 = mx1.to_translation()

    vec_10 = loc0 - loc1
    vec_01 = loc1 - loc0
    
    
    vec0_local = mxno0 * vec_01
    vec1_local = mxno1 * vec_10
    
    ob1_contacts = set()
    if 'prox contact ' + ob1.name not in ob0.vertex_groups:
        vg = ob0.vertex_groups.new(name = 'prox contact ' + ob1.name)
    else:
        vg = ob0.vertex_groups.get('prox contact ' + ob1.name)
        
    for v in ob0.data.vertices:
        loc, no, ind, d = bvh1.ray_cast(imx1 * mx0 * v.co, vec1_local)
        if loc:
            ob1_contacts.add(v.index)
            v.co = ((1- factor) * v.co + factor * imx0 * mx1 * loc)
     
    vg.add(list(ob1_contacts), weight = 1.0, type = 'REPLACE')      
     
     
    ob0_contacts = set()
    if 'prox contact ' + ob0.name not in ob1.vertex_groups:
        vg = ob1.vertex_groups.new(name = 'prox contact ' + ob0.name)
    else:
        vg = ob1.vertex_groups.get('prox contact ' + ob0.name)  
             
    for v in ob1.data.vertices:
        loc, no, ind, d = bvh0.ray_cast(imx0 * mx1* v.co, vec0_local)
        if loc:
            v.co = ((1-factor)* v.co + factor * imx1 * mx0* loc)   
            ob0_contacts.add(v.index) 
    vg.add(list(ob0_contacts), weight = 1.0, type = 'REPLACE')
            
#find out who collides if anyone by creating BVH from
#transformed BMEsh


def generate_pairs(obs):
    
    checked_pairs = set()
    overlap_pairs = set()
    bvhs = {}

    
    for ob in obs:
        for other_ob in obs:
            if ob == other_ob: continue    

            pair = tuple(sorted([ob.name, other_ob.name]))
            if pair in checked_pairs: continue
        
            checked_pairs.add(pair)
            bme = bmesh.new()
            bme.from_mesh(ob.data)
            bme.transform(ob.matrix_world)
            
            obme = bmesh.new()
            obme.from_mesh(other_ob.data)
            obme.transform(other_ob.matrix_world)
            
            if ob in bvhs:
                bvh = bvhs[ob]
            else:
                bvh = BVHTree.FromBMesh(bme)
                bvhs[ob] = bvh
            
            if other_ob in bvhs:
                obvh = bvhs[other_ob]
            else: 
                obvh = BVHTree.FromBMesh(obme)
                bvhs[other_ob] = obvh
                 
            overlap = bvh.overlap(obvh)
            
            if len(overlap):
                print(pair)
                print('OVERLAPPED')
                overlap_pairs.add(pair)
    del bvhs            
    return overlap_pairs

def register():
    bpy.utils.register_class(AITeeth_OT_remove_collisions_projection)


def unregister():
    bpy.utils.unregister_class(AITeeth_OT_remove_collisions_projection)
  
