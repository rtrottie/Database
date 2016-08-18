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
    'job_type' : 'ts',
            'ts_label' : {'$all' : ['hydride', 'dissociation'],
                          '$nin' : ['full']
            },

    'converged': True,
    'material': 'hercynite',
    'dopant_atoms' : {'$exists' : False}
}

start_match = {
    'defect_location' : 'origin',
}
final_match = {
    'defect_location' : '90',
}
ts_match = {
    'job_type' : 'ts',
            'ts_label' : {'$all' : ['hydride', 'dissociation'],
                          '$nin' : ['full']
            }
}
atoms = ['sc', 'ti', 'v', 'cr', 'mn', 'fe', 'co', 'ni', 'cu', 'zn']
atoms = ['fe']
locations = ['origin', '90']
cwd = os.path.abspath('.')

for atom in atoms:
    print atom
    if atom == 'fe':
        match_criteria['dopant_atoms']    = {'$exists': False}
        match_criteria['dopant_location']    = {'$exists': False}
    else:
        match_criteria['dopant_atoms']    = atom
        match_criteria['dopant_location']    = 'active'


    client = pymongo.MongoClient(client_ip)
    db = client.ryan
    fs = gridfs.GridFS(db)

    run = get_lowest_spin(db, match_criteria)

    to_remove = ['IOPT', 'REQUIRE', 'STAGE_NAME', 'STAGE_NUMBER', 'ICHAIN']

    if run:
        base = os.path.join('/home/ryan/scrap/dim', atom.lower())
        if not os.path.exists(base):
            os.mkdir(base)

        to_update = {
            'SYSTEM': ' '.join(['Herc-b', atom.upper(), 'dim']),
            'POTIM': 0,
            'IOPT' : 7,
            'ICHAIN': 2,
            'NSW': 5000,
            'NELM': 100,
            'NPAR': 3,
        }
        incar = Incar.from_dict(run['incar'])
        potcar = Potcar(run['potcar'])
        poscar = Poscar.from_dict(run['poscar'])
        kpoints = Kpoints.gamma_automatic((1,1,1))
        for option in to_remove:
            if option in incar:
                del incar[option]
        incar.update(to_update)

        run_folder = base
        if not os.path.exists(run_folder):
            os.mkdir(run_folder)

        for (item, name) in [(incar, 'INCAR'),
                             (potcar, 'POTCAR'),
                             (kpoints, 'KPOINTS'),
                             (poscar, 'POSCAR')]:
            item.write_file(os.path.join(run_folder, name))
        with open(os.path.join(run_folder, 'MODECAR'), 'w') as modecar:
            with fs.get(run['modecar']) as f:
                modecar.write(f.read())

