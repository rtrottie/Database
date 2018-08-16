#!/usr/bin/env python

import pymongo
import gridfs
import subprocess
from Classes_Pymatgen import *
import Database_Tools
from Helpers import isint
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




try: input = raw_input
except NameError: pass
match_criterias_functional = [
{
    'locpot' : {'$exists' : True},
    'defect' : {'$nin' : [],
                '$exists' : True},
    'incar.METAGGA' : 'Scan'
},

{
    'material' : {'$all': ['mnte', 'nickeline']},
    'antiferromagnetic_label' : 'afi',
    'locpot' : {'$exists' : True},
    'defect' : {'$nin' : [],
                '$exists' : True},
'incar.LHFCALC' : True
},
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
    ('zincblende', 'afi'),
    ('zincblende', 'afiii')
]
match_criterias = []
for match_criteria_functional in match_criterias_functional:
    for material, spin in match_criterias_material:
        match_criteria = copy.deepcopy(match_criteria_functional)
        match_criteria['material'] = {'$all': ['mnte', material]}
        match_criteria['antiferromagnetic_label'] = spin
        match_criterias.append(match_criteria)

match_criterias = [
{'material' : 'hercynite',
                  # 'job_type' : 'relaxation',
                  'energy' : {'$exists' : True},
                  'labels' : {'$nin' : ['surface'], '$all' : ['charged_defect']},
                    'defect' : 'o-int',
                'adsorption_description': {'$exists': False},
        'poscar.structure.sites.100' : {'$exists' : True},
                 }
]

if __name__ == '__main__':
    db, fs, client = AddDB.load_db()
    for match_criteria in match_criterias:
        base_match = copy.deepcopy(match_criteria)
        base_match['defect'] = {'$exists' : False}
        base_match = {
    'material' : 'hercynite',
    'defect' : {'$exists' : False},
#     'jobtype' : 'relaxation',
    'labels' : {'$nin' : ['surface', 'convergence_study', 'ts']},
    'poscar.structure.sites.100' : {'$exists' : True},
    'locpot' : {'$exists' : True}
}
        print(base_match)
        base = Database_Tools.get_one(db, base_match)

        base_poscar = Poscar.from_dict(base['poscar'])
        base_poscar.write_file('POSCAR')
        Database_Tools.get_file(fs, base['outcar'], fix_as='outcar', new_file='OUTCAR')

        eps = base['eps_electronic'] + base['eps_ionic']

        # Third Order Correction
        command=['3rdO']
        process = subprocess.Popen(command, stdout=subprocess.PIPE)
        process.wait()
        output = process.stdout.read()
        E_3 = float(output.split()[-1])
        print(E_3)

        # Potential Alignment
        deviation = 0.5
        command = ['grepot', 'OUTCAR']
        process = subprocess.Popen(command, stdout=subprocess.PIPE)
        process.wait()
        natoms = base_poscar.natoms
        total_atoms = sum(natoms)
        atom_potentials = [None] * total_atoms
        with open('potal.dat') as f:
            for line in f.readlines():
                line = line.strip().split()
                if isint(line[0]):
                    for i in range(0, len(line), 2):
                        atom_potentials[int(line[i]) - 1] = float(line[i + 1])
        # pot = [None] * len(natoms)
        pot = {}
        for i in range(len(natoms)):

            bot = sum(natoms[0:i])
            top = sum(natoms[0:i + 1])
            # pot[i] = str(np.mean(potential[bot:top]))
            if max(atom_potentials[bot:top]) - min(atom_potentials[bot:top]) > deviation / 2:
                raise Exception('Potentials Not consistent')
            pot[base_poscar.site_symbols[i]] = str(np.mean(atom_potentials[bot:top]))
        print(pot)
#         with open('potal.in', 'w') as f:
#             f.write('''{}
# {}
# {}
# {}'''.format(len(natoms), ' '.join(pot), ' '.join([str(x) for x in natoms]), deviation))



        runs = list(db.database.find(match_criteria).sort('defect', pymongo.ASCENDING))
        print(len(runs))
        for run in runs:
            print(str(run['defect']) + ' ' + str(run['defect_charge']))
            charge = run['defect_charge']
            defect_poscar = Poscar.from_dict(run['poscar'])
            defect_poscar.write_file('POSCAR')
            Database_Tools.get_file(fs, run['outcar'], fix_as='outcar', new_file='OUTCAR')
            defect_natoms = defect_poscar.natoms

            with open('potal.in', 'w') as f:
                f.write('''{}
{}
{}
{}'''.format(len(defect_natoms), ' '.join([ pot[x] for x in defect_poscar.site_symbols ]), ' '.join([str(x) for x in defect_natoms]), deviation))

            command = ['grepot', 'OUTCAR']
            process = subprocess.Popen(command, stdout=subprocess.PIPE)
            process.wait()

            command = ['potal']
            process = subprocess.Popen(command, stdout=subprocess.PIPE)
            process.wait()
            output = process.stdout.read()
            potential_alignment = float(output.split()[0])
            print(potential_alignment)

            tewen = base['ewald_h']
            csh = E_3 / tewen
            correction = {'potential_alignment' : potential_alignment,
                          'E_ic' : (1 + csh*(1-1/eps))*charge**2*tewen/eps}
            db.database.update_one({'_id': run['_id']},
                                   {'$set': {'correction_lany': correction}})
            continue

        client.close()