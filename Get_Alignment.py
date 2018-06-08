#!/usr/bin/env python

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
import shutil

def parse_vline(vline):
    potential = {
        'z' : [],
        'V' : {
            'long_range' : [],
            'reference'   : [],
            'short_range': []
        }
    }
    with open(vline) as f:
        for line in f.readlines():
            line = line.split()
            if len(line) == 0:    # End of File
                break
            elif len(line) == 1:  # Break between sr potential and lr
                pass
            elif len(line) == 2:  # Short range potential section
                potential['z'].append(float(line[0]))
                potential['V']['long_range'].append(float(line[1]))
            elif len(line) == 3:  # Long range potential section
                potential['V']['reference'].append(float(line[1]))
                potential['V']['short_range'].append(float(line[2]))
    # print(potential)
    return potential

def parse_sxdefectalign(lines):
    alignment = {}
    for line in lines:
        # print(line)
        line = line.replace(b'=', b' ').replace(b':', b' ').split()
        if len(line) > 0 and line[0] in database_cfg.sxdefectalign_output:
            (i, name) = database_cfg.sxdefectalign_output[line[0]]
            alignment[name] = float(line[i])
    print(alignment)
    return alignment


try: input = raw_input
except NameError: pass
# match_criteria = {
#     'material' : {'$all': ['mnte', 'zincblende']},
#     'antiferromagnetic_label' : 'afiii',
#     'locpot' : {'$exists' : True},
#     'defect' : {'$nin' : [],
#                 '$exists' : True},
#     'alignment.vline' : {'$exists' : False},
#     'incar.METAGGA' : 'Scan'
# }
#
match_criterias_functional = [
{
    'locpot' : {'$exists' : True},
    'defect' : {'$nin' : [],
                '$exists' : True},
    'incar.METAGGA' : 'Scan'
},

# {
#     'material' : {'$all': ['mnte', 'nickeline']},
#     'antiferromagnetic_label' : 'afi',
#     'locpot' : {'$exists' : True},
#     'defect' : {'$nin' : [],
#                 '$exists' : True},
# 'incar.LHFCALC' : True
# },
{
    'material' : {'$all': ['mnte', 'nickeline']},
    'antiferromagnetic_label' : 'afi',
    'locpot' : {'$exists' : True},
    'defect' : {'$nin' : [],
                '$exists' : True},
'incar.LDAU' : True
},
    ]

match_criterias_material = [
    ('nickeline' , 'afi'),
    ('wurtzite', 'afiii'),
    ('wurtzite', 'afiv'),
    # ('zincblende', 'afi'),
    # ('zincblende', 'afiii')
]
match_criterias = []
for match_criteria_functional in match_criterias_functional:
    for material, spin in match_criterias_material:
        match_criteria = copy.deepcopy(match_criteria_functional)
        match_criteria['material'] = {'$all': ['mnte', material]}
        match_criteria['antiferromagnetic_label'] = spin
        match_criterias.append(match_criteria)


if __name__ == '__main__':
    db, fs, client = AddDB.load_db()
    for match_criteria in match_criterias:
        base_match = copy.deepcopy(match_criteria)
        base_match['defect'] = {'$exists' : False}

        print(base_match)


        base = Database_Tools.get_one(db, base_match)
        runs = list(db.database.find(match_criteria).sort('defect', pymongo.ASCENDING))
        base_locpot = Database_Tools.get_file(fs, base['locpot'], fix_as='LOCPOT', fix_args=Poscar.from_dict(base['poscar']))
        shutil.copy(base_locpot, 'LOCPOT.base')
        tmp_dir = tempfile.TemporaryDirectory().name
        os.mkdir(tmp_dir)

        for run in runs:
            print(str(run['defect']) + ' ' + str(run['defect_charge']))
            locpot = Database_Tools.get_file(fs, run['locpot'], fix_as='LOCPOT', fix_args=Poscar.from_dict(run['poscar']))
            shutil.copy(locpot, 'LOCPOT.defect')
            # avg = np.array(0)
            vline_energies = []
            vline_z = []
            command = ['sxdefectalign', '--vasp',
                       '--average', '5',
                       # '-a' + str(i+1),
                       '--vref', base_locpot,
                       '--vdef', locpot,
                       '--ecut', str(run['incar']['ENCUT']*0.073498618),
                       '--center', ','.join(run['defect_center']), '--relative',
                       '--eps', str(np.mean([base['eps_electronic_tddft'], base['eps_electronic_ip']]) + base['eps_ionic']),
                       '-q', str(-run['defect_charge'])]
            process = subprocess.Popen(command, stdout=subprocess.PIPE)
            process.wait()
            output = process.stdout.readlines()
            alignment = parse_sxdefectalign(output)

            for i in range(3):
                vline = parse_vline('vline-eV-a{}.dat'.format(i))
                # plt.plot(vline['z'], vline['V']['short_range'], label=str(i))
                vline_energies.append(list(vline['V']['short_range']))
                vline_z.append(list(vline['z']))
                # avg = avg + vline['V']['short_range']
            # avg = avg/3
            # vline_energies.append(list(avg))
            alignment['vline'] = vline_energies
            alignment['vline_axis'] = vline_z
            db.database.update_one({'_id' : run['_id']},
                                   {'$set': {'alignment' : alignment}})
            os.remove(locpot)

        client.close()
        os.remove(base_locpot)