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

atom = 'sc'
location = 'nearest'
for (atom, location) in [('sc', 'subsurface'), ('ti', 'nearest'), ('ti', 'subsurface'), ('v', 'nearest'),
                         ('v', 'subsurface'), ('mn', 'nearest'), ('cu', 'nearest'), ('zn', 'active'), ('zn', 'nearest')]:
    match_criteria = {
        'material' : 'hercynite',
        'kpoints_str' : 'gamma'
    }
    start_match = {
        'adsorption_description' : {
            '$all' : ['water', 'adsorbed']
        }
    }
    final_match = {
        'adsorption_description' : {
            '$all' : ['hydride', 'dissociated']
        }
    }
    to_remove = ['IOPT', 'REQUIRE', 'STAGE_NAME', 'STAGE_NUMBER', 'NUPDOWN']

    client = pymongo.MongoClient(client_ip)
    db = client.ryan
    fs = gridfs.GridFS(db)
    runs = db.database.find(match_criteria)

    start = get_lowest_spin(db, fs, match_criteria, start_match)
    final = get_lowest_spin(db, fs, match_criteria, final_match)

    to_update = {
        'SYSTEM'    : ' '.join(['Herc', atom.upper() + '-' + location[0], 'gsm']),
        'POTIM'     : 0,
        'NSW'       : 0,
        'NPAR'      : 2,
        'AUTO_NUPDOWN': ['nup', str(start['incar']['NUPDOWN']), str(final['incar']['NUPDOWN'])],
        'AUTO_NUPDOWN_ITERS' : 10
    }


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

