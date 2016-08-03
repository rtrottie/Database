import pymongo
import gridfs
import subprocess
from Classes_Pymatgen import *
import Database_Tools
import matplotlib.pyplot as plt
import numpy as np
import database_cfg
import AddDB

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
        line = line.replace('=', ' ').replace(':', ' ').split()
        if line[0] in database_cfg.sxdefectalign_output:
            (i, name) = database_cfg.sxdefectalign_output[line[0]]
            alignment[name] = float(line[i])
    return alignment


try: input = raw_input
except NameError: pass
base_match = {
    'material' : 'znse',
    'defect' : {'$exists' : False},
    'converged' : True
}
match_criteria = {
    'material' : 'znse',
    'locpot' : {'$exists' : True},
    'defect' : {'$nin' : [],
                '$exists' : True}
    # 'alignment.vline' : {'$exists' : False},
}

db, fs, client = AddDB.load_db()

base = Database_Tools.get_one(db, base_match)
runs = list(db.database.find(match_criteria).sort('defect', pymongo.ASCENDING))
base_locpot = Database_Tools.get_file(fs, base['locpot'], fix_as='LOCPOT', fix_args=Poscar.from_dict(base['poscar']))

os.chdir(database_cfg.scrap_dir)

for run in runs:
    print(str(run['defect']) + ' ' + str(run['defect_charge']))
    locpot = Database_Tools.get_file(fs, run['locpot'], fix_as='LOCPOT', fix_args=Poscar.from_dict(run['poscar']))
    avg = np.array(0)
    vline_energies = []
    for i in range(3):
        print('  ' + str(i))
        command = ['sxdefectalign', '--vasp',
                   '--average', '1',
                   '-a' + str(i+1),
                   '--vref', base_locpot,
                   '--vdef', locpot,
                   '--ecut', str(run['incar']['ENCUT']*0.073498618),
                   '--center', ','.join(run['defect_center']), '--relative',
                   '--eps', str(base['dielectric_constant']),
                   '-q', str(-run['defect_charge'])]
        process = subprocess.Popen(command, stdout=subprocess.PIPE)
        process.wait()
        alignment = parse_sxdefectalign(process.stdout.readlines())
        vline = parse_vline('vline-eV.dat')
        # plt.plot(vline['z'], vline['V']['short_range'], label=str(i))
        vline_energies.append(list(vline['V']['short_range']))
        avg = avg + vline['V']['short_range']
    avg = avg/3
    vline_energies.append(list(avg))
    alignment['vline'] = vline_energies
    alignment['vline_axis'] = vline['z']
    db.database.update_one({'_id' : run['_id']},
                           {'$set': {'alignment' : alignment}})
    os.remove(locpot)

match_criteria['alignment.vline']  = {'$exists' : True}
match_criteria['alignment.align'] = {'$exists' : False}
runs = db.database.find(match_criteria)
for run in runs:
    print(str(run['defect']) + ' ' + str(run['defect_charge']))
    z = run['alignment']['vline_axis']
    vline = run['alignment']['vline']
    for i in range(len(vline)):
        if i == 3:
            label = 'avg'
        else:
            label = str(i)
        plt.plot(z, vline[i], label=label, linewidth=3)
    plt.legend()
    plt.show()
    average_is = input('Give ints to fit average around (or delete / d) (or pass ): \n --> ')
    if average_is == 'delete' or average_is == 'd':
        db.database.delete_one({'_id' : run['_id']})
    else:
        average_is = average_is.split()
        if len(average_is) == 2:
            potential_i = 3
        elif len(average_is) == 3:
            potential_i = int(average_is[2])
        else:
            raise Exception('Need to Provide exactly two numbers')
        if average_is[0][0] == 'p':
            pass
        else:
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

runs = db.database.find(match_criteria)
for run in runs:
    print(str(run['defect']) + ' ' + str(run['defect_charge']))
    locpot = Database_Tools.get_file(fs, run['locpot'], fix_as='LOCPOT', fix_args=Poscar.from_dict(run['poscar']))
    avg = np.array(0)
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