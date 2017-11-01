import pymongo
import gridfs
import subprocess
from Classes_Pymatgen import *
import Database_Tools
import matplotlib.pyplot as plt
import numpy as np
import database_cfg
import AddDB
import os
from time import sleep
import tempfile
import copy
from Get_Alignment import match_criterias, parse_sxdefectalign


db, fs, client = AddDB.load_db()
for match_criteria in match_criterias:

    base_match = copy.deepcopy(match_criteria)
    base_match['defect'] = {'$exists' : False}
    print(base_match)
    base = Database_Tools.get_one(db, base_match)
    base_locpot = Database_Tools.get_file(fs, base['locpot'], fix_as='LOCPOT', fix_args=Poscar.from_dict(base['poscar']))
    tmp_dir = tempfile.TemporaryDirectory().name
    os.mkdir(tmp_dir)

    match_criteria['alignment.vline']  = {'$exists' : True}
    match_criteria['alignment.align'] = {'$exists' : True}
    match_criteria['alignment.valign'] = 0

    runs = db.database.find(match_criteria).sort('defect', pymongo.ASCENDING)
    runs = list(runs)
    for run in runs:
        print(str(run['defect']) + ' ' + str(run['defect_charge']))
        locpot = Database_Tools.get_file(fs, run['locpot'], fix_as='LOCPOT', fix_args=Poscar.from_dict(run['poscar']))
        command = ['sxdefectalign', '--vasp',
                   '--average', '1',
                   '--vref', base_locpot,
                   '--vdef', locpot,
                   '--ecut', str(run['incar']['ENCUT']*0.073498618),
                   '--center', ','.join(run['defect_center']), '--relative',
                   '--eps', str(base['dielectric_constant']),
                   '-q', str(-run['defect_charge']),
                   '-C', str(run['alignment']['align'])]
        process = subprocess.Popen(command, stdout=subprocess.PIPE)
        process.wait()
        alignment = parse_sxdefectalign(process.stdout.readlines())
        alignment['align'] = run['alignment']['align']
        alignment['alignment_quality'] = run['alignment']['alignment_quality']
        alignment['vline'] = run['alignment']['vline']
        alignment['vline_axis'] = run['alignment']['vline_axis']
        db.database.update_one({'_id' : run['_id']},
                               {'$set': {'alignment' : alignment}})
        os.remove(locpot)


    client.close()
    os.remove(base_locpot)