from .common.utils import get_settings

upper_perm = ['1','2','3','4','5','6','7','8','9','10','11','12','13','14','15','16']
upper_prim = ['A','B','C','D','E','F','G','H','I','J']
lower_perm = ['17','18','19','20','21','22','23','24','25','26','27','28','29','30','31','32']
lower_prim = ['K','L','M','N','O','P','Q','R','S','T']



upper_right = ['1','2','3','4','5','6','7','8']
upper_left = ['9','10','11','12','13','14','15','16']
lower_left = ['17','18','19','20','21','22','23','24']
lower_right = ['25','26','27','28','29','30','31','32']


upper_view_order = upper_right + upper_left
lower_view_order = [ele for ele in reversed(lower_right)] + [ele for ele in reversed(lower_left)]

upper_teeth = set(upper_perm + upper_prim)
lower_teeth = set(lower_perm + lower_prim)

univ_to_FDI = {}
univ_to_FDI['1'] = '18'
univ_to_FDI['2'] = '17'
univ_to_FDI['3'] = '16'
univ_to_FDI['4'] = '15'
univ_to_FDI['5'] = '14'
univ_to_FDI['6'] = '13'
univ_to_FDI['7'] = '12'
univ_to_FDI['8'] = '11'
univ_to_FDI['9'] = '21'
univ_to_FDI['10'] = '22'
univ_to_FDI['11'] = '23'
univ_to_FDI['12'] = '24'
univ_to_FDI['13'] = '25'
univ_to_FDI['14'] = '26'
univ_to_FDI['15'] = '27'
univ_to_FDI['16'] = '28'            
univ_to_FDI['17'] = '38'
univ_to_FDI['18'] = '37'
univ_to_FDI['19'] = '36'
univ_to_FDI['20'] = '35'
univ_to_FDI['21'] = '34'
univ_to_FDI['22'] = '33'
univ_to_FDI['23'] = '32'
univ_to_FDI['24'] = '31'
univ_to_FDI['25'] = '41'
univ_to_FDI['26'] = '42'
univ_to_FDI['27'] = '43'
univ_to_FDI['28'] = '44'
univ_to_FDI['29'] = '45'
univ_to_FDI['30'] = '46'
univ_to_FDI['31'] = '47'
univ_to_FDI['32'] = '48' 
univ_to_FDI['A'] = '55'
univ_to_FDI['B'] = '54'
univ_to_FDI['C'] = '53'
univ_to_FDI['D'] = '52'
univ_to_FDI['E'] = '51'
univ_to_FDI['F'] = '61'
univ_to_FDI['G'] = '62'
univ_to_FDI['H'] = '63'
univ_to_FDI['I'] = '64'
univ_to_FDI['J'] = '65'
univ_to_FDI['K'] = '75'
univ_to_FDI['L'] = '74'
univ_to_FDI['M'] = '73'
univ_to_FDI['N'] = '72'
univ_to_FDI['O'] = '71'
univ_to_FDI['P'] = '81'
univ_to_FDI['Q'] = '82'
univ_to_FDI['R'] = '83'
univ_to_FDI['S'] = '84'
univ_to_FDI['T'] = '85'

FDI_to_univ = {v: k for k, v in univ_to_FDI.items()}


def mes_dis_relation(a, b):
    '''
    only takes permanent tooth labels in preferencial nomenclature
    
    returns the relationship between teeth a and b
    
    returns mesial if a is mesial to b
    returns distal if a is distal to b
    '''
    
    #get the label in "univeral 1 to 32 system"
    name_a = data_tooth_label(a)
    name_b = data_tooth_label(b)
    
    if name_a == name_b:
        return -1
    
    #just do all the scenarios
    if name_a in upper_perm and name_b not in upper_perm:
        print("ERROR, teeth not in same arch")
        return -1
    if name_a in lower_perm and name_b not in lower_perm:
        print("ERROR, teeth not in same arch")
        return -1
    
    #UPPER RIGHT + UPPER RIGHT
    if name_a in upper_right and name_b in upper_right:
        if int(name_a) < int(name_b):
            return 'DISTAL'
        else:
            return 'MESIAL'
    #UPPER RIGHT to UPPER LEFT    
    if name_a in upper_right and name_b in upper_left:
        return 'MESIAL'
    
    #UPPER LEFT to UPPER LEFT  
    if name_a in upper_left and name_b in upper_left:
        if int(name_a) > int(name_b):
            return 'DISTAL'
        else:
            return 'MESIAL'
        
    #UPPER LEFT to UPPER RIGHT   
    if name_a in upper_right and name_b in upper_left:
        return 'MESIAL'
        
    
    #LOWER LEFT + LOWER LEFT
    if name_a in lower_left and name_b in lower_left:
        if int(name_a) < int(name_b):
            return 'DISTAL'
        else:
            return 'MESIAL'
    #LOWER LEFT to LOWER RIGHT  
    if name_a in lower_left and name_b in lower_right:
        return 'MESIAL'
    
    #LOWER RIGHT to LOWER RIGHT  
    if name_a in lower_right and name_b in lower_right:
        if int(name_a) > int(name_b):
            return 'DISTAL'
        else:
            return 'MESIAL'
        
    #LOWER RIGHT LEFT to LOWER LEFT   
    if name_a in lower_right and name_b in lower_left:
        return 'MESIAL'
    
    print('unacounted for')
    return -1
    
    

def uni_to_fdi(tooth_label):
    
    if tooth_label not in univ_to_FDI:
        #raise exception
        return 'INVALID'
    
    return univ_to_FDI[tooth_label]

def fdi_to_uni(tooth_label):
    
    if tooth_label not in FDI_to_univ:
        #raise exception
        return 'INVALID'
    
    return FDI_to_univ[tooth_label]


def preference_tooth_label(tooth_label):
    '''
    takes a universal tooth number (string) and returns
    the string for the tooth numbering system based on user preferences
    '''
    prefs = get_settings()
    if prefs.tooth_system == 'UNIVERSAL':
        return tooth_label
    else:
        return uni_to_fdi(tooth_label)
    
    
def data_tooth_label(tooth_label):
    '''
    always returns the universal system name
    assumes the incoming label matches the preferences
    '''
    
    prefs = get_settings()
    if prefs.tooth_system == 'FDI':
        return fdi_to_uni(tooth_label)
    
    else:
        return tooth_label
