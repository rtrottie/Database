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

SCRATCH = '/home/ryan/scratch/scratch.cif'
os.environ['VESTA_DIR'] = '/home/ryan/programs/VESTA-x86_64'

def view_multiple(runs, fs):
    structs = []
    for i in range(len(runs)):
        if runs[i]:
            with fs.get(ObjectId(runs[i]["contcar"])) as f:
                structs.append(ase.io.read(f, format='vasp'))
        else:
            structs.append(Atoms())
    ase.io.write(SCRATCH, structs)
    return subprocess.Popen(['jmol', SCRATCH], stdout=subprocess.PIPE)

def view(run, fs):
    with fs.get(ObjectId(run["contcar"])) as f:
        s = ''
        for chunk in f.readchunk():
            s += chunk
        p = Poscar.from_string(s)
        p = Vis.open_in_Jmol(p.structure)
    return p

if __name__ == '__main__':
    match_criteria = {
        'material' : 'hercynite',
        'dopant_location' : 'active',
        'adsorption_description' : {'$exists' : False},
        'labels' : {'$nin' : ['dos', 'nupdown']}

    }
    sort_criteria = [
        ("energy", pymongo.ASCENDING)
    ]

    client_ip = '10.0.2.2'

    client = pymongo.MongoClient(client_ip)
    db = client.ryan
    fs = gridfs.GridFS(db)
    client.close()

    runs = list(db.database.find(match_criteria).sort(sort_criteria))[0:10]
    runs = sorted(runs, cmp=lambda x,y : Element(x['elements'][2]).number - Element(y['elements'][2]).number)

    print(len(runs))
    view_multiple(runs, fs)
    print runs[11]