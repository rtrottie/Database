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
    'converged': True,
    'defect_type': 'v-o',
    'kpoints.kpoints' : [[2,2,2]],
    'material': 'hercynite',
    'ts_label': {'$exists': False},
    'incar.NUPDOWN' : {'$gte' : 0}
}

start_match = {
    'defect_location' : 'origin',
}
final_match = {
    'defect_location' : '90',
}

atoms = ['sc', 'ti', 'v', 'cr', 'mn', 'fe', 'co', 'ni', 'cu', 'zn']
locations = ['origin', '90']
cwd = os.path.abspath('.')

for atom in atoms:
    print atom
    if atom == 'fe':
        match_criteria['dopant_atoms']    = {'$exists': False}
    else:
        match_criteria['dopant_atoms']    = atom


    client = pymongo.MongoClient(client_ip)
    db = client.ryan
    fs = gridfs.GridFS(db)
    runs = db.database.find(match_criteria)

    start = get_lowest_spin(db, match_criteria, start_match)
    final = get_lowest_spin(db, match_criteria, final_match)

    to_remove = ['IOPT', 'REQUIRE', 'STAGE_NAME', 'STAGE_NUMBER']

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
    incar = Incar.from_dict(start['incar'])
    potcar = Potcar(start['potcar'])
    kpoints = Kpoints.gamma_automatic((2,2,2))
    for option in to_remove:
        if option in incar:
            del incar[option]
    incar.update(to_update)

    run_folder = base
    if not os.path.exists(run_folder):
        os.mkdir(run_folder)

    for (item, name) in [(incar, 'INCAR'),
                         (potcar, 'POTCAR'),
                         (kpoints, 'KPOINTS')]:
        item.write_file(os.path.join(run_folder, name))


    s = Poscar.from_dict(start['poscar']).structure

    coords = []
    for i in [9, 45, 32]:
        coords.append([s.sites[i].a, s.sites[i].b,  s.sites[i].c])

    s.translate_sites(72, np.average(coords, axis=0) - [s.sites[72].a, s.sites[72].b, s.sites[72].c])

    Poscar(s).write_file(os.path.join(base, 'POSCAR'))
    os.chdir(run_folder)
    Poscar.from_dict(start['poscar']).write_file('start')
    Poscar.from_dict(final['poscar']).write_file('final')
    sub = subprocess.Popen(['modemake.pl', 'start', 'final'])
    sub.wait()
    os.chdir(cwd)