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
    return potential

def parse_sxdefectalign(lines):
    alignment = {}
    for line in lines:
        line = line.replace(b'=', b' ').replace(b':', b' ').split()
        if line[0] in database_cfg.sxdefectalign_output:
            (i, name) = database_cfg.sxdefectalign_output[line[0]]
            alignment[name] = float(line[i])
    return alignment


try: input = raw_input
except NameError: pass
base_match = {
    'material' : {'$all': ['mnte', 'zincblende']},
    'antiferromagnetic_label' : 'afiii',
    'locpot' : {'$exists' : True},
    'defect' : {'$exists' : False},
    'converged' : True,
    'incar.METAGGA' : 'Scan'
}
match_criteria = {
    'material' : {'$all': ['mnte', 'zincblende']},
    'antiferromagnetic_label' : 'afiii',
    'locpot' : {'$exists' : True},
    'defect' : {'$nin' : [],
                '$exists' : True},
    'alignment.vline' : {'$exists' : False},
    'incar.METAGGA' : 'Scan'
}

db, fs, client = AddDB.load_db()

base = Database_Tools.get_one(db, base_match)
runs = list(db.database.find(match_criteria).sort('defect', pymongo.ASCENDING))
base_locpot = Database_Tools.get_file(fs, base['locpot'], fix_as='LOCPOT', fix_args=Poscar.from_dict(base['poscar']))
tmp_dir = tempfile.TemporaryDirectory().name
os.mkdir(tmp_dir)
# os.chdir(tmp_dir)

for run in runs:
    print(str(run['defect']) + ' ' + str(run['defect_charge']))
    locpot = Database_Tools.get_file(fs, run['locpot'], fix_as='LOCPOT', fix_args=Poscar.from_dict(run['poscar']))
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
               '--eps', str(base['dielectric_constant']),
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

match_criteria['alignment.vline']  = {'$exists' : True}
match_criteria['alignment.align'] = {'$exists' : False}
runs = db.database.find(match_criteria)
plt.ion()
for run in runs:
    print(str(run['defect']) + ' ' + str(run['defect_charge']))
    vline = run['alignment']['vline']
    for i in range(len(vline)):
        if i == 3:
            label = 'avg'
        else:
            label = str(i)
        plt.plot(run['alignment']['vline_axis'][i], vline[i], label=label, linewidth=3)
    plt.legend()
    plt.show()
    plt.pause(1)
    average_is = input('Give ints to fit average around (or delete / d) (or pass ): \n --> ')
    plt.cla()
    if average_is == 'delete' or average_is == 'd':
        db.database.delete_one({'_id' : run['_id']})
    else:
        average_is = average_is.split()
        if average_is[0][0] == 'p':
            pass
        elif len(average_is) == 3:
            potential_i = int(average_is[2])
        else:
            raise Exception('Need to Provide exactly three numbers')
        z = run['alignment']['vline_axis'][potential_i]
        bot = np.searchsorted(z, float(average_is[0]))
        top = np.searchsorted(z, float(average_is[1]))
        mean = np.mean(vline[potential_i][bot:top])
        std = np.std(vline[potential_i][bot:top])
        alignment = run['alignment']
        alignment['align'] = mean
        alignment['alignment_quality'] = std
        print('Average  : ' + str(mean) + '\nStd.Dev. : ' + str(std))
        db.database.update_one({'_id' : run['_id']},
                               {'$set': {'alignment' : alignment}})



match_criteria['alignment.vline']  = {'$exists' : True}
match_criteria['alignment.align'] = {'$exists' : True}
match_criteria['alignment.valign'] = 0

runs = db.database.find(match_criteria).sort('defect', pymongo.ASCENDING)
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
    vline = parse_vline('vline-eV.dat')
    alignment['align'] = run['alignment']['align']
    alignment['alignment_quality'] = run['alignment']['alignment_quality']
    alignment['vline'] = run['alignment']['vline']
    alignment['vline_axis'] = run['alignment']['vline_axis']
    db.database.update_one({'_id' : run['_id']},
                           {'$set': {'alignment' : alignment}})
    os.remove(locpot)


client.close()
os.remove(base_locpot)