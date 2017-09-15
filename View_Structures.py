import os
import pymongo
import gridfs
import Vis
import subprocess
from Database_Tools import get_lowest_spin
from bson import ObjectId
from Classes_Pymatgen import *
from pymatgen.core import *
from pymatgen.io.vasp.sets import *
import ase.io
from ase import Atoms
import database_cfg
from AddDB import load_db

# SCRATCH = '/home/ryan/scratch/scratch.cif'
# os.environ['VESTA_DIR'] = '/home/ryan/programs/VESTA-x86_64'

def view_multiple(runs):
    structs = []
    for run in runs:
        p = Poscar.from_dict(run['poscar'])
        filename = database_cfg.scrap()
        p.write_file(filename)
        with open(filename) as f:
            structs.append(ase.io.read(f, format='vasp'))
        os.remove(filename)
    filename = database_cfg.scrap() + '.cif'
    ase.io.write(filename, structs)
    return Vis.view(filename)

def view(run, program='jmol'):
    p = Poscar.from_dict(run['poscar'])
    filename = database_cfg.scrap() + '.cif'
    p.write_file(filename)
    p = Vis.view(filename, program)
    return p

if __name__ == '__main__':
    match_criteria = {
    'material' : 'hercynite',
    'job_type' : 'relaxation',
    'dopant_atoms' : {'$exists' : False},
    'adsorption_description' : 'hydride',
    'labels' : {'$all' : ['surface'],
                '$nin': ['defect', 'doped']}




    }

    # match_criteria['dopant_atoms'] = {'$exists' : False}
    # match_criteria['dopant_location'] = {'$exists' : False}

    sort_criteria = [
        ("energy", pymongo.ASCENDING)
    ]

    db, fs, client = load_db()

    runs = list(db.database.find(match_criteria))[:10]
    #runs = [get_lowest_spin(db, match_criteria, )]
    # runs = sorted(runs, cmp=lambda x,y : Element(x['elements'][2]).number - Element(y['elements'][2]).number)

    print(len(runs))
    print(runs[0])
    # for run in runs:
    #     print run['energy']
    view_multiple(runs)
    client.close()