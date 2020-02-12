#----------------------------------------------------------
# File bgl_utils.py
#----------------------------------------------------------
'''
update Feb 10, 2020
Created on Nov 20, 2012

@author: Patrick R. Moore
'''
import bpy
import bgl
import blf
import math
import time
import os

from . import button_data
from bpy_extras import view3d_utils 

from math import fmod
from mathutils.geometry import intersect_line_line_2d
from mathutils import Vector, Matrix
from bpy_extras.image_utils import load_image


def scale_vec_mult(a,b):
    '''
    performs item wise multiplication return Vec(a0*b0,a1*b1)
    '''
    out = Vector(a[0]*b[0],a[1]*b[1])
    return out

#generates a quad scaled, rotated and translated to be passsed to glVertex2f
def make_quad(width, height, x, y ,ang):
    '''
    args: 
    width, height, x, y, float
    ang: float in radians
    return: list of Vectors
    '''
    
    a = width/2
    b = height/2
    #primitive
    p0 = Vector((-a,-b))
    p1 = Vector((-a, b))
    p2 = Vector((a, b))
    p3 = Vector((a,-b))
    
    #put them in a list
    verts = [p0,p1,p2,p3]
    
    #rotation
    rmatrix = Matrix.Rotation(ang,2)

    #rotate them and tranlsate
    for i in range(0,len(verts)):
        vert = rmatrix*verts[i] + Vector((x,y))
        verts[i]=vert
    
    return verts

def quad_size_from_circle(r,n,spacer = 0):
    '''
    args-
    r: size of circle
    n: number of pie segments
    space: buffer space between segments in radians.Eg, 2 degrees is ~.035 radians
    '''
    #total arc available for each slice
    arc = 2*math.pi/n - spacer
    
    #length of arc..and this is why we use radians ladies and gents = arc*r
    arc_len = arc * r
    
    #now some fuzzy math here....make the diag of the quad = arcleng
    #a good approximation when arc is small, bad when arc is large
    #trig...a^2 + b^2 = c^2  => square a = b so 2a^2 = c^2
    size = arc_len/math.pow(2,.5)
    
    return size
    

def view3d_get_size_and_mid(context):
    region = bpy.context.region
    rv3d = bpy.context.space_data.region_3d

    width = region.width
    height = region.height
    mid = Vector((width/2,height/2))
    aspect = Vector((width,height))

    return [aspect, mid]

def plane_get_information(ob):  
    img_name = ob.material_slots[0].material.textures_slots[0].texture.image.name
    location = ob.location
    scale = ob.scale
    rot = ob.rotation
    
def image_quad(img,color,verts):
    img.gl_load(bgl.GL_NEAREST, bgl.GL_NEAREST)
    bgl.glBindTexture(bgl.GL_TEXTURE_2D, img.bindcode)
    bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MIN_FILTER, bgl.GL_NEAREST)
    bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MAG_FILTER, bgl.GL_NEAREST)
    bgl.glEnable(bgl.GL_TEXTURE_2D)
    bgl.glEnable(bgl.GL_BLEND)
    #bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)
    bgl.glColor4f(color[0], color[1], color[2], color[3])
    bgl.glBegin(bgl.GL_QUADS)
    #http://h30097.www3.hp.com/docs/base_doc/DOCUMENTATION/V51B_HTML/MAN/MAN3/2025____.HTM
    bgl.glTexCoord2f(0,0)
    bgl.glVertex2f(verts[0][0],verts[0][1])
    bgl.glTexCoord2f(0,1)
    bgl.glVertex2f(verts[1][0],verts[1][1])
    bgl.glTexCoord2f(1,1)
    bgl.glVertex2f(verts[2][0],verts[2][1])
    bgl.glTexCoord2f(1,0)
    bgl.glVertex2f(verts[3][0],verts[3][1])
    bgl.glEnd()
    bgl.glDisable(bgl.GL_BLEND)
    bgl.glDisable(bgl.GL_TEXTURE_2D)
    
def icons_to_blend_data(icondir, filter = ".png"):
    icon_files = [fi for fi in os.listdir(icondir) if fi.endswith(filter) ]
    for fname in icon_files:
        fpath = os.path.join(icondir,fname)
        load_image(fpath, dirname='', place_holder=False, recursive=False, ncase_cmp=True, convert_callback=None, verbose=False)
        
    
def radial_locations(r,n,x,y,offset = 0):
    '''
    r: radius of circle
    n: number of divisions
    x: x coord of center
    y: y cood or center
    offset: any angular offset
    '''
    #populate the list of vectors
    locations = [Vector((0,0))]*n
      
    for i in range(0,n):
        theta = offset + i * 2 * math.pi / n
        locx = x + r * math.cos(theta)
        locy = y + r * math.sin(theta)
        locations[i]=Vector((locx,locy))
   
    return locations

def sub_arc_loactions(r,arc,n,x,y,offset = 0):
    print("in development come back later")


def outside_loop(loop):
    '''
    args:
    loop: list of 
       type-Vector or type-tuple
    returns: 
       outside = a location outside bound of loop 
       type-tuple
    '''
       
    xs = [v[0] for v in loop]
    ys = [v[1] for v in loop]
    
    maxx = max(xs)
    maxy = max(ys)    
    bound = (1.1*maxx, 1.1*maxy)
    return bound

def point_inside_loop(loop, point):
    '''
    args:
    loop: list of vertices representing loop
        type-tuple or type-Vector
    point: location of point to be tested
        type-tuple or type-Vector
    
    return:
        True if point is inside loop
    '''    
    #test arguments type
    ptype = str(type(point))
    ltype = str(type(loop[0]))
    nverts = len(loop)
           
    if 'Vector' not in ptype:
        point = Vector(point)
        
    if 'Vector' not in ltype:
        for i in range(0,nverts):
            loop[i] = Vector(loop[i])
        
    #find a point outside the loop and count intersections
    out = Vector(outside_loop(loop))
    intersections = 0
    for i in range(0,nverts):
        a = Vector(loop[i-1])
        b = Vector(loop[i])
        if intersect_line_line_2d(point,out,a,b):
            intersections += 1
    
    inside = False
    if fmod(intersections,2):
        inside = True
    
    return inside

def make_round_box(minx, miny, maxx, maxy, rad):
       
        vec0 = [[0.195, 0.02],
               [0.383, 0.067],
               [0.55, 0.169],
               [0.707, 0.293],
               [0.831, 0.45],
               [0.924, 0.617],
               [0.98, 0.805]]
        
        #cache so we only scale the corners once
        vec = [[0,0]]*len(vec0)
        for i in range(0,len(vec0)):
            vec[i] = [vec0[i][0]*rad, vec0[i][1]*rad]
            
        verts = [[0,0]]*(9*4)
        # start with corner right-bottom
        verts[0] = [maxx-rad,miny]
        for i in range(1,8):
            verts[i]= [maxx - rad + vec[i-1][0], miny + vec[i-1][1]] #done
        verts[8] = [maxx, miny + rad]   #done
        
        #corner right-top    
        verts[9] = [maxx, maxy - rad]
        for i in range(10,17):
            verts[i]= [maxx - vec[i-10][1], maxy - rad + vec[i-10][0]]
        verts[17] = [maxx-rad, maxy]
        
        #corver left top
        verts[18] = [minx + rad, maxy]
        for i in range(19,26):
            verts[i]= [minx + rad - vec[i-19][0], maxy - vec[i-19][1]] #done
        verts[26] = [minx, maxy - rad]
        
        #corner left bottom    
        verts[27] = [maxx - rad, miny]
        for i in range(28,35):
            verts[i]= [minx + vec[i-28][1], miny + rad - vec[i-28][0]]    #done
        verts[35]=[minx + rad, miny]
        
        return verts
    
def draw_outline_or_region(mode, points):
        '''
        arg: mode either bgl.GL_POLYGON or bgl.GL_LINE_LOOP
        color will need to be set beforehand using theme colors. eg
        bgl.glColor4f(self.ri, self.gi, self.bi, self.ai)
        '''
 
        bgl.glBegin(mode)
 
        # start with corner right-bottom
        for i in range(0,len(points)):
            bgl.glVertex2f(points[i][0],points[i][1])
 
        bgl.glEnd()
        
def transform_points(points,x,y,sclx,scly,rot):
    transformed = [(0,0)]*len(points)
    
    rotmx = Matrix.Rotation(rot,2)
    trans = Vector((x,y))
    for i in range(0,len(points)):
        transformed[i] = tuple(rotmx*Vector((sclx*points[i][0],scly*points[i][1]))+trans)
    
    return transformed
        
def blf_text_wrap(string, wrap, font, size, dpi, x, y):
    '''
    arg string: the text to display type: string
    arg: wrap, # of characters per line type: Int
    arg: font type: int (usually 0?)
    arg size: text size type:int
    arg dpi: text dpi to display type: int
    arg x,y location to start box (top left)
    '''
    #make sure the string divides evenly by wrap
    if len(string) < wrap:
        string += ' '*(wrap - len(string))
    else:
        string += ' '*int(fmod(len(string), wrap))
            
    blf.size(font, size, dpi)
    dimension = blf.dimensions(0, string[0:wrap-1])

    for i in range(0,math.ceil(len(string)/wrap)):
        blf.position(font,x,y-i*dimension[1],0)
        blf.draw(font, string[i*wrap:(i+1)*wrap])

def draw_polyline_from_coordinates(context, points, width, LINE_TYPE = 'GL_LINE_STRIP', color = (1,1,1,1)):  
    region = context.region  
    rv3d = context.space_data.region_3d  
  
    bgl.glColor4f(*color)  
    bgl.glLineWidth(width)
    if LINE_TYPE == "GL_LINE_STIPPLE":  
        bgl.glLineStipple(4, 0x5555)  
        bgl.glEnable(bgl.GL_LINE_STIPPLE)    
        
    
    bgl.glBegin(bgl.GL_LINE_STRIP) 
    for coord in points:  
        vector3d = (coord.x, coord.y, coord.z)  
        vector2d = view3d_utils.location_3d_to_region_2d(region, rv3d, vector3d)  
        bgl.glVertex2f(*vector2d)  
    bgl.glEnd()  
    bgl.glLineWidth(1) 

      
    return

def draw_polyline_2d_loop(context, points, scale, offset, color, LINE_TYPE):
    '''
    '''
    bgl.glColor4f(*color)  #black or white?

    if LINE_TYPE == "GL_LINE_STIPPLE":
        bgl.glLineStipple(4, 0x5555)
        bgl.glEnable(bgl.GL_LINE_STIPPLE)
        bgl.glColor4f(0.3, 0.3, 0.3, 1.0) #boring grey
    
    bgl.glBegin(bgl.GL_LINE_STRIP)
    for coord in points:
        bgl.glVertex2f(scale*coord[0]+offset[0], scale*coord[1] + offset[1])
    bgl.glVertex2f(scale*points[0][0]+offset[0], scale*points[0][1] + offset[1])
    bgl.glEnd()
    
    if LINE_TYPE == "GL_LINE_STIPPLE":
        bgl.glDisable(bgl.GL_LINE_STIPPLE)
        bgl.glEnable(bgl.GL_BLEND)  # back to uninterupted lines    
    return

def insertion_axis_callback(self,context):
    aspect, mid = view3d_get_size_and_mid(context)
    
    #place 50 pixel arrow at right edge
    path1 = transform_points(button_data.arrow_right, aspect[0]-20,mid[1],50,100,0)
    path2 = transform_points(button_data.arrow_left, 20,mid[1],50,100,0)
    
    bgl.glColor4f(*(1,1,1,1))
    draw_outline_or_region(bgl.GL_LINE_LOOP, path1)
    draw_outline_or_region(bgl.GL_LINE_LOOP, path2)
    
    #put words in the arrows
    blf.size(0,20,76)
    dimension = blf.dimensions(0,"Mesial")
    blf.position(0,aspect[0]-70-dimension[0]/2,mid[1]-dimension[1]/2,0)
    blf.draw(0,"Mesial")
    
    dimension = blf.dimensions(0,"Distal")
    blf.position(0,70-dimension[0]/2,mid[1]-dimension[1]/2,0)
    blf.draw(0,"Distal")


def general_func_callback(self,context):
    aspect, mid = view3d_get_size_and_mid(context)
        # draw some text
    blf.position(0, mid[0], mid[1]+100, 0)
    blf.size(0, 20, 72)
    blf.draw(0, self.message)
    blf_text_wrap(self.help, self.wrap, 0, 12 , 76, 10, aspect[1]-30)
    

def draw_callback_tooth_select(self, context):
    
    #draw all the buttons
    color = (1.0,1.0,1.0,1.0)
    for i in range(0,len(button_data.tooth_button_data)): #each of those is a loop        
        button = button_data.tooth_button_data[i]
        
        #check if it's in the rest_type, draw it green.
        #print(len(self.rest_lists))
        
        #draw it yellowish if it's in another type of restoration
        for j in range(0,len(self.rest_lists)):
            if button_data.tooth_button_names[i] in self.rest_lists[j]:
                color = (1.0,1.0,0.5,1.0)
                
        
        #draw it green if it's in the current type of restoration and selected
        if button_data.tooth_button_names[i] in self.rest_lists[self.rest_index]:
            color = (0.1,1.0,0.1,0.5)
        
        #draw it red if the button is hovered
        if self.tooth_button_hover[i]:
            color = (1.0,0.1,0.1,0.5)
        
        draw_polyline_2d_loop(context, button, self.menu_width, self.menu_loc, color,"GL_BLEND")
        color = (1.0,1.0,1.0,1.0)
        
    color = (1.0,1.0,1.0,1.0)
    
    for n in range(0,len(button_data.rest_button_data)): #each of those is a loop        
        button = button_data.rest_button_data[n]
        
        #draw it red if the button is selected or hovered
        if self.rest_button_select[n]:
            color = (0.1,1.0,0.1,0.5)
        
        draw_polyline_2d_loop(context, button, self.menu_width*.5, self.rest_menu_loc , color,"GL_BLEND")
        color = (1.0,1.0,1.0,1.0)    

#borrowed from edge filet from Zeffi (included with blend)  
def draw_3d_points(context, points, size, color = (1,0,0,1)):  
    region = context.region  
    rv3d = context.space_data.region_3d  
      
      
    bgl.glEnable(bgl.GL_POINT_SMOOTH)  
    bgl.glPointSize(size)  
    # bgl.glEnable(bgl.GL_BLEND)  
    bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)  
      
    bgl.glBegin(bgl.GL_POINTS)  
    # draw red  
    bgl.glColor4f(*color)      
    for coord in points:  
        vector3d = (coord.x, coord.y, coord.z)  
        vector2d = view3d_utils.location_3d_to_region_2d(region, rv3d, vector3d)  
        bgl.glVertex2f(*vector2d)  
    bgl.glEnd()  
      
    bgl.glDisable(bgl.GL_POINT_SMOOTH)  
    bgl.glDisable(bgl.GL_POINTS)  
    return

def draw_callback_crevice_walking(self,context):
    
    #draw put a big ole target over the mouse or something
    draw_3d_points(context, [self.current_bias_point], 4)
    
    #draw the user control points
    draw_3d_points(context, self.bias_points, 4)
    
    #draw the existing/confirmed walked points
    draw_3d_points(context, self.pending_path, 4)
    
    #draw the unconfirmed iterative points
    
    
if __name__ == "__main__":
    print('do something here?')
'''
def register():  
    print('register utils')
def unregister():     
    print('unregister utils')
if __name__ == "__main__":
    register()
'''  