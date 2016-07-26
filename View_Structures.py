import os
import pymongo
import gridfs
import Vis
import subprocess
from bson import ObjectId
from Classes_Pymatgen import *
from pymatgen.core import *
import ase.io
from ase import Atoms
import database_cfg
from AddDB import load_db

SCRATCH = '/home/ryan/scratch/scratch.cif'
os.environ['VESTA_DIR'] = '/home/ryan/programs/VESTA-x86_64'

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
    return subprocess.Popen(['jmol', filename], stdout=subprocess.PIPE)

def view(run):
    p = Poscar.from_dict(run['poscar'])
    p = Vis.open_in_Jmol(p.structure)
    return p

if __name__ == '__main__':
    match_criteria = {
        'material'  : 'gaas',
        'defect'    : 'as-ga'

    }
    sort_criteria = [
        ("energy", pymongo.ASCENDING)
    ]

    db, fs, client = load_db()

    runs = list(db.database.find(match_criteria).sort(sort_criteria))[0:10]
    # runs = sorted(runs, cmp=lambda x,y : Element(x['elements'][2]).number - Element(y['elements'][2]).number)

    print(runs[0].potcar)
    print(len(runs))
    view_multiple(runs)