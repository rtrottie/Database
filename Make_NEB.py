import pymongo
import gridfs
from Database_Tools import get_lowest_spin
import os
import View_Structures
from Classes_Pymatgen import *
os.environ['VASP_PSP_DIR'] = '/home/ryan/Documents/PMG'


client_ip = '10.0.2.2:27018'

try: input = raw_input
except NameError: pass

match_criteria = {
    'converged': True,
    'defect_type': 'v-o',
    'material': 'hercynite',
    'ts_label': {'$exists': False}
}

start_match = {
    'defect_location' : 'origin',
}
final_match = {
    'defect_location' : '90',
}

atoms = ['sc', 'ti', 'v', 'cr', 'mn', 'fe', 'co', 'ni', 'cu', 'zn']
locations = ['origin', '90']
# for (atom, location) in [('sc', 'subsurface'), ('ti', 'nearest'), ('ti', 'subsurface'), ('v', 'nearest'),
#                          ('v', 'subsurface'), ('mn', 'nearest'), ('cu', 'nearest'), ('zn', 'active'), ('zn', 'nearest')]:
#     pass
for atom in atoms:
  for location in locations:
    print atom + ' ' + location
    if atom == 'fe':
        match_criteria['dopant_atoms']    = {'$exists': False}
    else:
        match_criteria['dopant_atoms']    = atom


    client = pymongo.MongoClient(client_ip)
    db = client.ryan
    fs = gridfs.GridFS(db)
    runs = db.database.find(match_criteria)

    start_start = get_lowest_spin(db, fs, match_criteria, start_match)
    final_final = get_lowest_spin(db, fs, match_criteria, final_match)

    start_nupdown = start_start['incar']['NUPDOWN']
    final_nupdown = final_final['incar']['NUPDOWN']

    start_final = get_lowest_spin(db, fs, match_criteria, [final_match, {'incar.NUPDOWN' : start_nupdown}])
    final_start = get_lowest_spin(db, fs, match_criteria, [start_match, {'incar.NUPDOWN' : final_nupdown}])

    if start_nupdown == final_nupdown:
        runs = [(start_start, start_final)]
    else:
        runs = [(start_start, start_final), (final_start, final_final)]

    to_remove = ['IOPT', 'REQUIRE', 'STAGE_NAME', 'STAGE_NUMBER', 'NUPDOWN']

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
            'IMAGES' : 7

        }
        incar = Incar.from_dict(start['incar'])
        potcar = Potcar(start['potcar'])
        kpoints = Kpoints.gamma_automatic()
        images = Poscar.from_dict(start['poscar']).structure.interpolate(Poscar.from_dict(final['poscar']).structure, nimages=9, autosort_tol=1)
        for option in to_remove:
            if option in incar:
                del incar[option]
        incar.update(to_update)

        run

        for (item, name) in [(incar, 'INCAR'),
                             (potcar, 'POTCAR'),
                             (kpoints, 'KPOINTS')]:
            item.write_file(os.path.join(base, name))

        for i in range(len(images)):
            folder = os.path.join(base, str(i).zfill(2))
            if not os.path.exists(folder):
                os.mkdir(folder)
            Poscar(images[i]).write_file(os.path.join(folder, 'POSCAR'))


    if not os.path.exists(folder):
        os.mkdir(folder)

