from .common.utils import get_settings


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
