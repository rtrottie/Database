import os
import pymongo
import gridfs
import View_Structures
import AddDB
import Database_Tools
import ase.io
import Vis
import subprocess
from bson import ObjectId
import time
from AddDB import load_db
import signal
from Classes_Pymatgen import *


try: input = raw_input
except NameError: pass


def get_database_info(label, atom):
    if atom == 'Fe':
        if label == 'Water':
            return {'defect_type': ['o-vac'],
                    'defect_location': 'active',
                    'adsorption_description': {'$exists': False}
                    }
        if label == 'Adsorbed':
            return {'defect_type': {'$all': ['{}-fe'.format(atom.lower())]},
                    'defect_location': 'active',
                    'adsorption_description': {'$all': ['chemisorbed', 'water']}
                    }
        if label == 'Dissociated':
            return {'defect_type': {'$exists': False},
                    'defect_location': {'$exists': False},
                    'adsorption_description': {'$all': ['dissociated', 'hydride']}
                    }
        if label == 'Adsorbed Hydrogen':
            return {'defect_type': {'$exists': False},
                    'defect_location': {'$exists': False},
                    'adsorption_description': {'$all': ['chemisorbed', 'hydrogen']}
                    }
        if label == 'Hydrogen':
            return {'defect_type': {'$exists': False},
                    'defect_location': {'$exists': False},
                    'adsorption_description': {'$exists': False}
                    }

    if label == 'Water':
        return {'defect_type': {'$all': ['{}-fe'.format(atom.lower()), 'o-vac']},
                'defect_location': 'active',
                'adsorption_description': {'$exists': False}
                }
    if label == 'Adsorbed':
        return {'defect_type': {'$all': ['{}-fe'.format(atom.lower())]},
                'defect_location': 'active',
                'adsorption_description': {'$all': ['chemisorbed', 'water']}
                }
    if label == 'Dissociated':
        return {'defect_type': {'$all': ['{}-fe'.format(atom.lower())]},
                'defect_location': 'active',
                'adsorption_description': {'$all': ['dissociated', 'hydride']}
                }
    if label == 'Adsorbed Hydrogen':
        return {'defect_type': {'$all': ['{}-fe'.format(atom.lower())]},
                'defect_location': 'active',
                'adsorption_description': {'$all': ['chemisorbed', 'hydrogen']}
                }
    if label == 'Hydrogen':
        return {'defect_type': {'$all': ['{}-fe'.format(atom.lower())],
                                '$nin': ['o-vac']},
                'defect_location': 'active',
                'adsorption_description': {'$exists': False}
                }
match_criteria = {
        'material' : 'hercynite',
        'labels' : {'$nin' : ['dos', 'nupdown'],
                    '$in'  : ['relaxation']},
        'dimer_min' : {'$exists' : False},
'verified_geometry' : {'$exists' : False}
    }
db, fs, client = load_db()
for atom in ['Al', 'Sc', 'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn']:
    for label in ['Water', 'Adsorbed', 'Dissociated', 'Adsorbed Hydrogen', 'Hydrogen']:
        match_criteria.update(get_database_info(label, atom))
        runs = list(db.database.find(match_criteria).sort([("energy", pymongo.ASCENDING)]))
        # View_Structures.view_multiple(runs)
        for run in runs:
            p = View_Structures.view(run)
            time.sleep(2)
            print(run)
            print('{} {}'.format(atom, label))
            verified = input('Verify this state (y/n) (1/0) or "delete" : \n --> ')
            p.kill()
            if verified == 'delete' or verified == 'd':
                AddDB.delete(db.database, fs, run['_id'])
                print('DELETED')
            elif verified == 'y' or verified == '1':
                db.database.update_one({'_id' : run['_id']},
                                       {'$set': {'verified_geometry' : True}})
            else:
                db.database.update_one({'_id' : run['_id']},
                                       {'$set': {'adsorption_description' : verified.split()}})

        client.close()