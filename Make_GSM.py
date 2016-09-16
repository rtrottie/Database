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

atoms = ['sc', 'ti', 'v', 'cr', 'mn', 'fe', 'co', 'ni', 'cu', 'zn']
atoms = ['cr']
locations = ['active']
# for (atom, location) in [('sc', 'subsurface'), ('ti', 'nearest'), ('ti', 'subsurface'), ('v', 'nearest'),
#                          ('v', 'subsurface'), ('mn', 'nearest'), ('cu', 'nearest'), ('zn', 'active'), ('zn', 'nearest')]:
#     pass
for atom in atoms:
  for location in locations:
    print atom + ' ' + location
    if atom == 'fe':
        match_criteria = {
            'material': 'hercynite',
            'dopant_atoms': {'$exists' : False},
            'dopant_location': {'$exists' : False},
        }
    else:
        match_criteria = {
            'material' : 'hercynite',
            'dopant_atoms' : atom,
            'dopant_location': location,
        }
    start_match = {
        'adsorption_description' : {
            '$all' : ['water', 'adsorbed']
        },
        'ts_label' : {'$exists' : False}
    }
    final_match = {
        'adsorption_description' : {
            '$all' : ['hydride', 'full']
        },
        'ts_label' : {'$exists' : False}
    }
    to_remove = ['IOPT', 'REQUIRE', 'STAGE_NAME', 'STAGE_NUMBER', 'NUPDOWN']

    client = pymongo.MongoClient(client_ip)
    db = client.ryan
    fs = gridfs.GridFS(db)
    runs = db.database.find(match_criteria)

    start = get_lowest_spin(db, match_criteria, start_match)
    final = get_lowest_spin(db, match_criteria, final_match)

    to_update = {
        'SYSTEM'    : ' '.join(['Herc', atom.upper() + '-' + location[0], 'h-dis','gsm']),
        'POTIM'     : 0,
        'NSW'       : 0,
        'NELM'      : 100,
        'NPAR'      : 3,
        'ISTART'    : 1,
        'ICHARG'    : 1,

    }

    if start['incar']['NUPDOWN'] != final['incar']['NUPDOWN']:
        to_update['AUTO_NUPDOWN'] = ['nup', str(start['incar']['NUPDOWN']), str(final['incar']['NUPDOWN'])]
        to_update['AUTO_NUPDOWN_ITERS'] = 10
    else:
        to_update['NUPDOWN'] = start['incar']['NUPDOWN']

    incar = Incar.from_dict(start['incar'])
    potcar = Potcar(start['potcar'])
    kpoints = Kpoints.gamma_automatic()
    for option in to_remove:
        if option in incar:
            del incar[option]
    incar.update(to_update)
    pass

    base = '/home/ryan/scrap/gsm'
    folder = os.path.join(base, atom + '-' + location[0])
    if not os.path.exists(folder):
        os.mkdir(folder)
    for (item, name) in [(Poscar.from_dict(start['poscar']), 'start'), (Poscar.from_dict(final['poscar']), 'final'), (incar, 'INCAR'), (potcar, 'POTCAR'), (kpoints, 'KPOINTS')]:
        item.write_file(os.path.join(folder, name))

