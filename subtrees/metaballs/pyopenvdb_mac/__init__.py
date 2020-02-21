import os, sys
import platform

mpath = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, mpath)

if platform.python_version()[:3] == '3.7':
    from .w37.pyopenvdb import *

if platform.python_version()[:3] == '3.6':
    from .w36.pyopenvdb import *

if platform.python_version()[:3] == '3.5':
    from .w35.pyopenvdb import *

