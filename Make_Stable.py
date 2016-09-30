import pymongo
import gridfs
from Database_Tools import get_lowest_spin
import os
import View_Structures
from Classes_Pymatgen import *
import subprocess
os.environ['VASP_PSP_DIR'] = '/home/ryan/Documents/PMG'


client_ip = '10.0.2.2:27018'

try: input = raw_input
except NameError: pass

match_criteria = {
        'job_type': {'$in' : ['relaxation']},
        'converged': True,
        'surface_cut' : {'$exists' : True},
        'material': 'hercynite',
        'adsorption_description' : {'$exists' : False},
        'dimer_min' : {'$exists' : False},
        'dopant_atoms' : {'$exists' : False},
        'dopant_location' : {'$exists' : False}
}


atoms = ['sc', 'ti', 'v', 'cr', 'mn', 'fe', 'co', 'ni', 'cu', 'zn']
atoms = ['fe']
# locations = ['origin', '90']
cwd = os.path.abspath('.')
run_folder = '/home/ryan/scrap'

for atom in atoms:
    print atom
    if atom == 'fe':
        match_criteria['dopant_atoms'] = {'$exists': False}
    else:
        match_criteria['dopant_atoms'] = atom


    client = pymongo.MongoClient(client_ip)
    db = client.ryan
    fs = gridfs.GridFS(db)
    run = get_lowest_spin(db, match_criteria)
    View_Structures.view(run)


    incar = Incar.from_dict(run['incar'])
    poscar = Poscar.from_dict(run['poscar'])
    # kpoints = Kpoints.from_dict(run['kpoints'])
    potcar = Potcar(run['potcar'])


    for (item, name) in [(incar, 'INCAR'),
                         (potcar, 'POTCAR'),
                         # (kpoints, 'KPOINTS'),
                         (poscar, 'POSCAR')]:
        item.write_file(os.path.join(run_folder, name))


