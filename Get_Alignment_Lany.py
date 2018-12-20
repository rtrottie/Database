#!/usr/bin/env python

import pymongo
import gridfs
import subprocess
from Classes_Pymatgen import *
import Database_Tools
from Helpers import isint, get_corresponding_atom_i
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

match_criteria = {'material' : 'hercynite',
                  # 'job_type' : 'relaxation',
                  'energy' : {'$exists' : True},
                  'labels' : {'$nin' : ['surface'], '$all' : ['charged_defect']},
                    'defect' : 'o-vac',
                'adsorption_description': {'$exists': False},
        'poscar.structure.sites.100' : {'$exists' : True},
                  'correction_lany' : {'$exists' : False},
                 }


ewald_h = {
    'hercynite' : 2.006,
}

eps_all = {
    'hercynite' : 11.49,
}

deviation = 0.5

def get_correction_from_run(db, fs, base, eps=None):
    base_poscar = Poscar.from_dict(base['poscar'])
    base_poscar.write_file('POSCAR')
    Database_Tools.get_file(fs, base['outcar'], fix_as='outcar', new_file='OUTCAR')
    Database_Tools.get_file(fs, base['vasprun'], fix_as='outcar', new_file='vasprun.xml')
    v = Vasprun('vasprun.xml')

    if not eps:
        eps = base['eps_electronic'] + base['eps_ionic']

    # Third Order Correction
    command = ['3rdO']
    process = subprocess.Popen(command, stdout=subprocess.PIPE)
    process.wait()
    output = process.stdout.read()
    E_3 = float(output.split()[-1])
    # print(E_3)

    # Potential Alignment
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
        max_pot = max(atom_potentials[bot:top])
        min_pot = min(atom_potentials[bot:top])
        if max_pot - min_pot >  deviation / 2:
            # prompt = input('Potentials not consistent, average anyway? (y/n) ->  ')
            prompt = 'y'
            print('Potentials not consistent, averaging anyway?')
            if prompt != 'y':
                raise Exception('Potentials Not consistent')
            else:
                atoms = set(base_poscar.site_symbols)
                pot = {}
                for atom in atoms:
                    pot[atom] =  str(np.mean([ atom_potentials[i] for i, a in enumerate(base_poscar.structure) if str(a.specie)==atom ]))

        pot[base_poscar.site_symbols[i]] = str(np.mean(atom_potentials[bot:top]))
    # print(pot)
    #         with open('potal.in', 'w') as f:
    #             f.write('''{}
    # {}
    # {}
    # {}'''.format(len(natoms), ' '.join(pot), ' '.join([str(x) for x in natoms]), deviation))


    return eps, pot, E_3, v.efermi, atom_potentials

def set_correction_of_run(db, fs, run, base, eps, pot, E_3, efermi, tewen, debug=False):
    charge = run['defect_charge']
    defect_poscar = Poscar.from_dict(run['poscar'])
    defect_poscar.write_file('POSCAR')
    Database_Tools.get_file(fs, run['outcar'], fix_as='outcar', new_file='OUTCAR')
    defect_natoms = defect_poscar.natoms

    command = ['grepot', 'OUTCAR']
    process = subprocess.Popen(command, stdout=subprocess.PIPE)
    process.wait()

    if type(pot) == dict:
        with open('potal.in', 'w') as f:
            f.write('''{}
        {}
        {}
        {}'''.format(len(defect_natoms), ' '.join([pot[x] for x in defect_poscar.site_symbols]),
                     ' '.join([str(x) for x in defect_natoms]), deviation))


        command = ['potal']
        process = subprocess.Popen(command, stdout=subprocess.PIPE)
        process.wait()
        output = process.stdout.read()
        potential_alignment = float(output.split()[0])

    elif type(pot) == list:
        # Potential Alignment
        natoms = defect_poscar.natoms
        total_atoms = sum(natoms)
        atom_potentials = [None] * total_atoms
        with open('potal.dat') as f:
            for line in f.readlines():
                line = line.strip().split()
                if isint(line[0]):
                    for i in range(0, len(line), 2):
                        atom_potentials[int(line[i]) - 1] = float(line[i + 1])
        base_poscar = Poscar.from_dict(base['poscar'])
        corresponding_atoms = get_corresponding_atom_i(base_poscar.structure, defect_poscar.structure)
        base_potentials = pot
        potential_alignment = []
        for i,j in corresponding_atoms:
            diff = atom_potentials[j] - base_potentials[i]
            if abs(diff) < deviation:
                potential_alignment.append(diff)
        potential_alignment = np.mean(potential_alignment)

    else:
        raise Exception('Pot is Wrong Type')


    csh = E_3 / tewen
    correction = {
        'potential_alignment' : potential_alignment,
        'E_ic' : (1 + csh*(1-1/eps))*charge**2*tewen/eps,
        'efermi' : efermi,
    }

    if not debug:
        db.database.update_one({'_id': run['_id']},
                               {'$set': {'correction_lany': correction}})
        pass
    else:
        try:
            print(run['correction_lany'])
        except:
            pass
        print(correction)
    return

if __name__ == '__main__':
    db, fs, client = AddDB.load_db()
    runs = list(db.database.find(match_criteria).sort('defect', pymongo.ASCENDING))
    print(len(runs))
    for run in runs:

        print(str(run['defect']) + ' ' + str(run['defect_charge']))
        print(str(run['defect_type']))
        defect_type = run['defect_type']
        to_remove = []
        for element in defect_type:
            if ('o-vac' in element) or ('vac-o' in element):
                to_remove.append(element)
        for element in to_remove:
            defect_type.remove(element)
        if defect_type == []:
            defect_type = {'$exists': False}
        else:
            defect_type = {'$all': defect_type, '$nin': ['o-vac']}

        labels = run['labels']
        base_match = {
    'material' : 'hercynite',
    'defect_type' : defect_type,
    'defect' : {'$exists' : False},
    # 'jobtype' : 'relaxation',
    'labels' : {'$nin' : ['surface', 'convergence_study', 'ts']},
    'poscar.structure.sites.100' : {'$exists' : True}
}
        if 'compensating_defect' in run:
            base_match['compensating_defect'] = run['compensating_defect']

        base = Database_Tools.get_one(db, base_match)
        print(base_match)
        eps = eps_all['hercynite']
        eps, pot, E_3, efermi, atom_potentials = get_correction_from_run(db, fs, base, eps=eps)
        set_correction_of_run(db, fs, run, base, eps, atom_potentials, E_3, efermi, ewald_h['hercynite'], debug=False)

    client.close()



