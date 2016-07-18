import pymongo
import gridfs
from Database_Tools import get_lowest_spin
from Classes_Pymatgen import *


client_ip = '10.0.2.2:27018'

try: input = raw_input
except NameError: pass

folder = '/home/ryan/scrap/hydride-dissociation'
atom = 'sc'
location = 'nearest'

match_criteria = {
    'material' : 'hercynite',
    'kpoints_str' : 'gamma'
}
final_match = {
    'adsorption_description' : {
        '$all' : ['hydride', 'dissociated']
    }
}
start_match = {
    'adsorption_description' : {
        '$all' : ['water', 'adsorbed']
    }
}

client = pymongo.MongoClient(client_ip)
db = client.ryan
fs = gridfs.GridFS(db)
runs = db.database.find(match_criteria)

start = get_lowest_spin(db, fs, )