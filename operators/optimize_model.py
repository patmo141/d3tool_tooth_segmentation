import bpy
import bmesh
from bpy.props import IntProperty, FloatProperty, BoolProperty





        
        
class AITeeth_OT_optimize_model(bpy.types.Operator):
    """Get rid of lon edges and decimate Mesh to Target Vertex Count"""
    bl_idname = "ai_teeth.optimize_model"
    bl_label = "Optimize Model Density"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    max_edge_length = FloatProperty(name = 'Max Edge Length', description = 'Edges longer than this will be re-meshed', default = 0.5, min = .1 , max = 1.5)
    target_edge_length = FloatProperty(name = 'Target Edge Length',description = 'Long edges will be remeshed to this, usually smaller than Max Edge Length', default = 0.25, min = .1 , max = 1.5)
    max_verts = IntProperty(default = 125000, description = 'Target number of vertices')
    
    
    @classmethod
    def poll(cls, context):
        ob1 = bpy.data.objects.get(context.scene.d3ortho_upperjaw)
        ob2 = bpy.data.objects.get(context.scene.d3ortho_lowerjaw)
        
        if ob1 != None or ob2 != None:
            return True
        
        return False
    
    def execute(self, context):
        
        ob1 = bpy.data.objects.get(context.scene.d3ortho_upperjaw)
        ob2 = bpy.data.objects.get(context.scene.d3ortho_lowerjaw)
        
        for ob in bpy.data.objects:
            ob.select = False
            
        for ob in [ob1, ob2]:
            if ob == None: continue
            ob.select = True
            context.scene.objects.active = ob
            self.optimize_model(context, ob)
            ob.select = False
        
        context.scene.objects.active = None
            
        return {'FINISHED'}
    
    def optimize_model(self, context, ob):
    
    
        bme = bmesh.new()
        bme.from_object(ob, context.scene)
        
        
        #this is the final mode we will put back
        final_mode = context.mode
        
        #putting the object back into object mode, ensures the mask
        #layer data is up to date
        if final_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode = 'OBJECT')
            
        
        is_dyntopo = ob.use_dynamic_topology_sculpting
            
    
        bme.verts.ensure_lookup_table()
        mask = bme.verts.layers.paint_mask.verify()
    
        bme.verts.ensure_lookup_table()
        bme.edges.ensure_lookup_table()
        bme.faces.ensure_lookup_table()
        
        long_vs = set()
        for ed in bme.edges:
            if ed.calc_length() > self.max_edge_length:
                long_vs.update([ed.verts[0], ed.verts[1]])
            
            
        for v in bme.verts:
            if v in long_vs:
                v[mask] = 0.0
            else:
                v[mask] = 1.0
    
        bme.to_mesh(context.object.data) #push the mask back
        context.object.data.update()
        
        if len(long_vs):
            bme.free()
            bpy.ops.object.mode_set(mode = 'SCULPT')
        
            if ob.use_dynamic_topology_sculpting != True:
                print('\n')
                print(ob.name)
                print(ob.use_dynamic_topology_sculpting)
                print(context.object.use_dynamic_topology_sculpting)
                print('Toggling dyntopo')
                bpy.ops.sculpt.dynamic_topology_toggle()
            context.scene.tool_settings.sculpt.detail_type_method = 'CONSTANT'
            context.scene.tool_settings.sculpt.constant_detail_resolution =  min(1/(1.5*self.target_edge_length), 6)
            bpy.ops.sculpt.detail_flood_fill()
            
            bpy.ops.object.mode_set(mode = final_mode)
        
        
            bme = bmesh.new()
            bme.from_mesh(ob.data)
            bme.verts.ensure_lookup_table()
        
        
        factor = self.max_verts/len(bme.verts)
        
        if factor < 1:
            mod = ob.modifiers.new('Reduce','DECIMATE')    
            mod.ratio = min(1,factor)
            
            context.scene.update()
            me = ob.to_mesh(context.scene, apply_modifiers = True, settings = 'PREVIEW')
            
            old_me = ob.data
            ob.modifiers.clear()
            ob.data = me
            bpy.data.meshes.remove(old_me)
def register():
    bpy.utils.register_class(AITeeth_OT_optimize_model)
    
    
def unregister():
    #bpy.utils.unregister_class(AI_OT_preprocess)
    bpy.utils.unregister_class(AITeeth_OT_optimize_model)
    
    