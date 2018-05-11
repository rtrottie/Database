import pymongo
import gridfs
import subprocess
from Classes_Pymatgen import *
import Database_Tools
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import database_cfg
import AddDB
import os
from time import sleep
import tempfile
import copy
from Get_Alignment import match_criterias, parse_sxdefectalign, base_match


db, fs, client = AddDB.load_db()
for match_criteria in match_criterias:

    # base_match = copy.deepcopy(match_criteria)
    # base_match['defect'] = {'$exists' : False}
    print(base_match)


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
        plt.pause(4)
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



client.close()