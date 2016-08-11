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

    start_start = get_lowest_spin(db, match_criteria, start_match)
    final_final = get_lowest_spin(db, match_criteria, final_match)

    start_nupdown = start_start['incar']['NUPDOWN']
    final_nupdown = final_final['incar']['NUPDOWN']

    start_final = get_lowest_spin(db, match_criteria, [final_match, {'incar.NUPDOWN' : start_nupdown}])
    final_start = get_lowest_spin(db, match_criteria, [start_match, {'incar.NUPDOWN' : final_nupdown}])

    if start_nupdown == final_nupdown:
        runs = [(start_start, start_final)]
    else:
        runs = [(start_start, start_final), (final_start, final_final)]

    to_remove = ['IOPT', 'REQUIRE', 'STAGE_NAME', 'STAGE_NUMBER']

    base = os.path.join('/home/ryan/scrap/neb', atom.lower())
    if not os.path.exists(base):
        os.mkdir(base)

    for (start, final) in runs:
        to_update = {
            'SYSTEM': ' '.join(['Herc-b', atom.upper(), str(start['incar']['NUPDOWN']), 'neb']),
            'POTIM': 0,
            'IOPT' : 7,
            'ICHAIN': 0,
            'NSW': 5000,
            'NELM': 100,
            'NPAR': 3,
            'IMAGES' : 7,
        }
        incar = Incar.from_dict(start['incar'])
        potcar = Potcar(start['potcar'])
        kpoints = Kpoints.gamma_automatic()
        images = Poscar.from_dict(start['poscar']).structure.interpolate(Poscar.from_dict(final['poscar']).structure, nimages=8, autosort_tol=1)
        for option in to_remove:
            if option in incar:
                del incar[option]
        incar.update(to_update)

        run_folder = os.path.join(base, str(start['incar']['NUPDOWN']).replace('-', 'n'))
        if not os.path.exists(run_folder):
            os.mkdir(run_folder)

        for (item, name) in [(incar, 'INCAR'),
                             (potcar, 'POTCAR'),
                             (kpoints, 'KPOINTS')]:
            item.write_file(os.path.join(run_folder, name))

        for i in range(len(images)):
            folder = os.path.join(base, run_folder, str(i).zfill(2))
            if not os.path.exists(folder):
                os.mkdir(folder)
            if i == 0:
                with open(os.path.join(folder, 'OUTCAR'), 'w') as outcar_file:
                    with fs.get(start['outcar']) as outcar_fs:
                        outcar_file.write(outcar_fs.read())
            elif i == len(images)-1:
                with open(os.path.join(folder, 'OUTCAR'), 'w') as outcar_file:
                    with fs.get(final['outcar']) as outcar_fs:
                        outcar_file.write(outcar_fs.read())

            Poscar(images[i]).write_file(os.path.join(folder, 'POSCAR'))
        os.chdir(run_folder)
        sub = subprocess.Popen(['/home/ryan/bin/nebavoid.pl', '1.35'])
        sub.wait()
        sub = subprocess.Popen(['/home/ryan/bin/nebmovie.pl'])
        sub.wait()
        os.chdir(cwd)


    if not os.path.exists(folder):
        os.mkdir(folder)

