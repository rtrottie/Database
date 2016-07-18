import os
import pymongo
import gridfs
import View_Structures
import AddDB
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
    'ts_type' : {'$exists' : True},
    'ts_label': {'$exists' : False},
}

client = pymongo.MongoClient(client_ip)
db = client.ryan
fs = gridfs.GridFS(db)
runs = db.database.find(match_criteria)
for run in runs:
    print run['dopant_atoms'][0] + ' ' + run['dopant_location'][0]

    p = View_Structures.view_multiple([db.database.find_one({'_id' : ObjectId(run['min1'])}),
                                       run,
                                       db.database.find_one({'_id': ObjectId(run['min2'])})], fs)
    label = input('Label this TS or "delete" : \n --> ')

    if label == 'delete':
        db.database.delete_one({'_id' : run['_id']})
    elif label:
        db.database.update_one({'_id' : run['_id']},
                               {'$set': {'ts_label' : label.split()}})
        if AddDB.entry_exists(db.database, db.database.find_one({'_id' : run['_id']})):
            # AddDB.delete(db.database, fs, run['_id'])
            print('Duplicate - Check runs and delete')

client.close()