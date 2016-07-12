from Database_Tools import *
from pymatgen.io.vasp.inputs import Potcar
from bson import ObjectId
import pymongo
import gridfs
import os
os.environ['VASP_PSP_DIR'] = '/home/ryan/Documents/PMG'

match_criteria = {'job_type' : 'ts',
            'ts_label' : {'$all' : ['hydride', 'dissociation'],
                          '$nin' : ['full']
                         },
                  'dopant_atoms' : 'ni',
                  'dopant_location' : 'active'
           }
output_folder = '/home/ryan/scrap'

client = pymongo.MongoClient('10.0.2.2')
db = client.ryan
fs = gridfs.GridFS(db)


run = get_lowest_spin(db, fs, match_criteria)

with fs.get(ObjectId(run['incar'])) as input:
    with open(os.path.join(output_folder, 'INCAR'), 'w') as output:
        output.write(input.read())
with fs.get(ObjectId(run['kpoints'])) as input:
    with open(os.path.join(output_folder, 'KPOINTS'), 'w') as output:
        output.write(input.read())
with fs.get(ObjectId(run['contcar'])) as input:
    with open(os.path.join(output_folder, 'POSCAR'), 'w') as output:
        output.write(input.read())
Potcar(run['potcar']).write_file(os.path.join(output_folder, 'POTCAR'))