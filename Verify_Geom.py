import os
import pymongo
import gridfs
import View_Structures
import ase.io
import Vis
import subprocess
from bson import ObjectId
import time
import signal
from Classes_Pymatgen import *

client_ip = '10.0.2.2'

try: input = raw_input
except NameError: pass

match_criteria = {'material': 'hercynite', 'adsorption_description': {'$all': ['hydrogen', 'gas']}, 'dopant_location': 'active', 'labels': {'$in': ['dos']}, 'dimer_min': {'$exists': False}, 'dopant_atoms': 'sc'}


client = pymongo.MongoClient(client_ip)
db = client.ryan
fs = gridfs.GridFS(db)
runs = list(db.database.find(match_criteria))
print(len(runs))
for run in runs:
    p = View_Structures.view(run, fs)
    label = input('Verify this state (y/n) (1/0) or "delete" : \n --> ')

    if label == 'delete' or label == 'd':
        db.database.delete_one({'_id' : run['_id']})
        print('DELETED')
    elif label == 'y' or label == '1':
        db.database.update_one({'_id' : run['_id']},
                               {'$set': {'verified_geometry' : True}})

client.close()