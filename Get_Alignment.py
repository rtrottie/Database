import pymongo
import gridfs
import subprocess
from Classes_Pymatgen import *
import Database_Tools
import matplotlib.pyplot as plt
import numpy as np
import database_cfg

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
            alignment[name] = line[i]
    return alignment

client_ip = '10.0.2.2'
try: input = raw_input
except NameError: pass
base_match = {
    'material' : 'gaas',
    'defect' : {'$exists' : False},
    'converged' : True
}
match_criteria = {
    'material' : 'gaas',
    'converged': True,
    'defect' : {'$exists' : True},
    'alignment.vline' : {'$exists' : False},
}

client = pymongo.MongoClient(client_ip)
db = client.ryan
fs = gridfs.GridFS(db)

base = Database_Tools.get_one(db, base_match)
base_locpot = Database_Tools.get_file(fs, base['locpot'], fix_as='LOCPOT', fix_args=Poscar.from_dict(base['poscar']))

os.chdir(database_cfg.scrap_dir)

runs = db.database.find(match_criteria)
for run in runs:
    print(str(run['defect']) + ' ' + str(run['defect_charge']))
    locpot = Database_Tools.get_file(fs, run['locpot'], fix_as='LOCPOT', fix_args=Poscar.from_dict(run['poscar']))
    avg = np.array(0)
    for i in range(3):
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
        plt.plot(vline['z'], vline['V']['short_range'], label=str(i))
        avg = avg + vline['V']['short_range']
    avg = avg/3
    plt.plot(vline['z'], avg, label = 'avg', linewidth=4)
    plt.legend()
    plt.show()
    average_is = input('Give ints to fit average around (or delete / d) (or pass ): \n --> ')
    if average_is == 'delete' or average_is == 'd':
        db.database.delete_one({'_id' : run['_id']})
    else:
        average_is = average_is.split()
        if len(average_is) < 2 and 'pass' not in average_is :
            os.remove(locpot)
            raise Exception('Need to Provide exactly two numbers')
        else:
            bot = np.searchsorted(vline['z'], float(average_is[0]))
            top = np.searchsorted(vline['z'], float(average_is[1]))
            mean = np.mean(avg[bot:top])
            std = np.std(avg[bot:top])
            alignment['vline'] = list(avg)
            alignment['vline_axis'] = vline['z']
            alignment['align'] = mean
            alignment['alignment_quality'] = std
            print('Average  : ' + str(mean) + '\nStd.Dev. : ' + str(std))
            db.database.update_one({'_id' : run['_id']},
                                   {'$set': {'alignment' : alignment}})
    os.remove(locpot)

client.close()
