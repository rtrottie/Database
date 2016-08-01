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



atoms = ['sc', 'ti', 'v', 'cr', 'mn', 'co', 'ni', 'cu', 'zn']
locations = ['origin', '90']


match_criteria = {
    'material' : 'hercynite',
    'converged' : True,
    'labels' : {'$all' : ['surface', 'relaxation'],
                '$nin' : ['adsorption', 'ts']},
    'elements' : {'$nin' : ['H', 'h'] + atoms + [ x.capitalize() for x in atoms ]},
}

client = pymongo.MongoClient(client_ip)
db = client.ryan
fs = gridfs.GridFS(db)
runs = []
for atom in ['fe']:
    print atom
    if atom == 'fe':
        match_criteria['dopant_atoms']    = {'$exists': False}
        match_criteria['dopant_location'] = {'$exists': False}
    else:
        match_criteria['dopant_atoms']    = atom
        match_criteria['dopant_location'] = 'active'

    run = get_lowest_spin(db, fs, match_criteria)


    incar = Incar.from_dict(run['incar'])
    potcar = Potcar(run['potcar'])
    kpoints = Kpoints.gamma_automatic()
    poscar = Poscar.from_dict(run['poscar'])
    folder = os.path.join('/home/ryan/scrap', atom)
    if not os.path.exists(folder):
        os.mkdir(folder)
    for (item, name) in [(incar, 'INCAR'),
                         (potcar, 'POTCAR'),
                         (kpoints, 'KPOINTS'),
                         (poscar, 'POSCAR')]:
            item.write_file(os.path.join(folder, name))

    runs.append(run)

client.close()
from View_Structures import view_multiple
view_multiple(runs)

