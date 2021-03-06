# AUTOGENERATED! DO NOT EDIT! File to edit: 00_core.ipynb (unless otherwise specified).

__all__ = ['is_code', 'get_codes', 'get_metadata', 'create_requirements', 'is_property', 'add_cell_to_properties',
           'files_in_properties', 'get_properties_from_cells', 'fast_experiment']

# Cell
from nbdev.export import check_re,read_nb
from pathlib import Path
import re
import os
import platform

# Cell
_re_blank_code = re.compile(r"""
# Matches any line with #export or #exports without any module name:
^         # beginning of line (since re.MULTILINE is passed)
\s*       # any number of whitespace
\#\s*     # # then any number of whitespace
code  # export or exports
\s*       # any number of whitespace
$         # end of line (since re.MULTILINE is passed)
""", re.IGNORECASE | re.MULTILINE | re.VERBOSE)

_re_mod_code = re.compile(r"""
# Matches any line with #export or #exports with a module name and catches it in group 1:
^         # beginning of line (since re.MULTILINE is passed)
\s*       # any number of whitespace
\#\s*     # # then any number of whitespace
code  # export or exports
\s*       # any number of whitespace
(\S+)     # catch a group with any non-whitespace chars
\s*       # any number of whitespace
$         # end of line (since re.MULTILINE is passed)
""", re.IGNORECASE | re.MULTILINE | re.VERBOSE)

# Cell
def is_code(cell: dict, default="main.py") -> str:
    """Checks if `cell` is to be exported and returns the name of the module to export it if provided.

    Parses the cell of a Jupyter Notebook, checks if it has the #code tag,
    and returns the name of the module it is associated with, otherwise returns
    None.

    Args:
        cell: dict of the JSON of the cell
        default: name of the default module where all #code will be added
    Returns:
        The string of the name of the cell it is associated if #code is present,
        else None
    """
    if check_re(cell, _re_blank_code):
        return default
    tst = check_re(cell, _re_mod_code)
    return os.path.sep.join(tst.groups()[0].split('.')).replace("\\",".").replace("/",".") if tst else None

# Cell
from collections import defaultdict

def get_codes(fn:str,default:str = "main.py") -> dict:
    """Returns a dictionary where each key contains the name
    of the module, and the value is the code in it."""
    nb = read_nb(fn)

    module_to_code = defaultdict(str)

    module_to_code[default] = ""

    for cell in nb["cells"]:
        code = is_code(cell,default)
        if code:
            module_to_code[code] += cell["source"]

    return dict(module_to_code)

# Cell
def get_metadata() -> dict:
    """Returns metadata about the current running environment."""
    data = {
        "os":os.name,
        "system":platform.system(),
        "release":platform.release(),
        "python_version":platform.python_version()
    }
    return data

# Cell
def create_requirements(fn):
    """Create requirements file"""
    # Convert the notebook to a python file
    os.system(f"jupyter nbconvert --to=python {fn}")

    # Create the requirements file
    os.system("pipreqs ./ --force")

# Cell
_re_blank_property = re.compile(r"""
# Matches any line with #export or #exports without any module name:
^         # beginning of line (since re.MULTILINE is passed)
\s*       # any number of whitespace
\#\s*     # # then any number of whitespace
property  # export or exports
\s*       # any number of whitespace
$         # end of line (since re.MULTILINE is passed)
""", re.IGNORECASE | re.MULTILINE | re.VERBOSE)

_re_obj_def = re.compile(r"""
# Catches any 0-indented object definition (bla = thing) with its name in group 1
^          # Beginning of a line (since re.MULTILINE is passed)
([^=\s]*)  # Catching group with any character except a whitespace or an equal sign
\s*=       # Any number of whitespace followed by an =
""", re.MULTILINE | re.VERBOSE)

# Cell
def is_property(cell):
    "Check if `cell` is to be exported and returns the name of the module to export it if provided"
    if check_re(cell, _re_blank_property):
        return True
    else:
        return False

def add_cell_to_properties(cell: dict,properties: dict,globs:dict):
    """Adds all variables in the cell to the properties"""
    objs = _re_obj_def.findall(cell["source"])

    objs = {obj : globs[obj] for obj in objs}

    properties.update(objs)

# Cell
def files_in_properties(properties:dict):
    """Returns the list of files from properties"""
    files = []
    for key,val in properties.items():
        if isinstance(val,Path) and val.is_file():
            files.append(str(val))
    return files

# Cell
def get_properties_from_cells(fn: str,globs:dict,return_files:bool = True,):
    """Gets the properties from all #property cells"""

    nb = read_nb(fn)

    properties = {}

    for cell in nb["cells"]:
        if is_property(cell):
            add_cell_to_properties(cell,properties,globs=globs)

    files = files_in_properties(properties)
    return properties,files

# Cell
from contextlib import contextmanager
from neptune.projects import Project
from neptune.experiments import Experiment

@contextmanager
def fast_experiment(project: Project,nb_name:str,globs:dict,return_files: bool = True,
                    default:str = "main.py",**kwargs) -> Experiment:
    """Creates a Neptune ML experiment, wrapped with meta data.

    Args:
        project: Neptune Project
        nb_name: str name of the current notebook to be recorded
        globs: dict of the global variables. Simply set globs = globals() and then pass it.
        return_files: bool, True if we want to send files recorded in the parameters.
        default: str name of the default code
        kwargs: additional args passed to Neptune ML when the experiment is created

    Returns:
        exp: Neptune ML experiment
    """
    # First we get the code cells
    codes = get_codes(nb_name,default=default)

    # We write them in separate files
    for fn,code in codes.items():
        with open(fn,"w") as file:
            file.write(code)

    codes = list(codes.keys())

    # We get the properties
    properties,files = get_properties_from_cells(nb_name,globs=globs,return_files=return_files)
    metadata = get_metadata()
    properties.update(metadata)
    properties["nb_name"] = nb_name

    # We convert the dict keys to string
    for k,v in properties.items():
        properties[k] = str(v)

    exp = project.create_experiment(params=properties,upload_source_files=codes,**kwargs)

    # We create the requirements file and send it
    create_requirements(nb_name)
    exp.send_artifact("requirements.txt")

    for fn in files:
        exp.send_artifact(fn)

    yield exp

    exp.stop()

    # We remove the code files
    for fn in codes:
        os.remove(fn)

    os.remove("requirements.txt")