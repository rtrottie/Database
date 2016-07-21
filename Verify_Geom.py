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
import signal
from Classes_Pymatgen import *

client_ip = '10.0.2.2:27018'

try: input = raw_input
except NameError: pass

match_criteria = {
    'dopant_atoms': 'cu',
    'dopant_location': 'subsurface',
    'verified_geometry' : {'$exists' : False},
    'converged' : True,
    'material': 'hercynite',
    'adsorption_description': {'$exists': False},
    'dimer_min': {'$exists': False},
}


client = pymongo.MongoClient(client_ip)
db = client.ryan
fs = gridfs.GridFS(db)
runs = list(db.database.find(match_criteria).sort([("energy", pymongo.ASCENDING)]))
print(len(runs))
for run in runs:
    print run
    p = View_Structures.view(run)
    time.sleep(1.5)
    label = input('Verify this state (y/n) (1/0) or "delete" : \n --> ')

    if label == 'delete' or label == 'd':
        AddDB.delete(db.database, fs, run['_id'])
        print('DELETED')
    elif label == 'y' or label == '1':
        db.database.update_one({'_id' : run['_id']},
                               {'$set': {'verified_geometry' : True}})
    else:
        db.database.update_one({'_id' : run['_id']},
                               {'$set': {'adsorption_description' : label.split()}})

client.close()