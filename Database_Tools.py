from __future__ import print_function
import pymongo
from pymongo.collection import Collection
import gridfs
import os
import shutil
import bz2
from bson import ObjectId
from Classes_Pymatgen import *
import sys
import database_cfg
import tempfile

def fix_locpot(base_locpot, poscar):
    with open(base_locpot, 'rb') as f:
        lines = f.readlines()
        lines[0] = ' '.join(poscar.site_symbols) + '\n'
        try:
            [int(x) for x in lines[5].split()]  # check if line is filled with ints
        except:
            lines.pop(5)
    with open(base_locpot, 'wb') as f:
        f.writelines(lines)
    return base_locpot

def get_one(db, match_criteria, update=None):
    '''

    :param db: Collection
    :type match_criteria: dict
    :type update: dict
    :return:
    '''

    if update:
        match_criteria = match_criteria.copy()
        match_criteria.update(update)

    matches = list(db.database.find(match_criteria))
    if len(matches) > 1:
        print('Too Many Matches for :' + str(match_criteria))
        return matches[0]
    elif len(matches) == 0:
        print('No matches found for :' + str(match_criteria))
        return None
    else:
        return matches[0]

def get_lowest_spin(db, match_criteria, updates={}):
    '''

    :param db: Collection
    :type match_criteria: dict
    :type update: dict
    :return:
    '''
    if type(updates) == type({}):
        updates = [updates]
    for update in updates:
        if 'energy' not in update or 'energy' not in match_criteria:
            update['energy'] = {'$exists' : True}
        match_criteria = match_criteria.copy()
        match_criteria.update(update)
    matches = list(db.database.find(match_criteria).sort([("energy", pymongo.ASCENDING)]))

    if len(matches) == 1:
        return matches[0]
    elif len(matches) == 0:
        return None
    else:
        try:
            nup = matches[0]['incar']['NUPDOWN']
        except:
            nup = {'$exists' : False}
        count = 0
        for match in matches:
            try:
                nup_test = match['incar']['NUPDOWN']
            except:
                nup_test = {'$exists' : False}
            if nup_test == nup:
                count += 1
        if count > 1:
            display = match_criteria.copy()
            display.update({'NUPDOWN': nup})
            print('Too Many Matches for :' + str(display))
        return matches[0]

def compress(filename):
    temp = tempfile.NamedTemporaryFile(delete=False).name
    print('Compressing ' + filename + '...', end='')
    sys.stdout.flush()
    with open(filename, 'rb') as f:  # compress LOCPOT
        with bz2.BZ2File(temp, 'wb') as b:
            b.write(f.read())
    print('Compressed')
    return temp

def get_file(fs, oid, fix_as='', fix_args=None):
    '''
    Get the file specified by oid from the specified filesystem fs.  Performs maintenace as specified by the fix_as
    setting

    :param fs: gridfs.Filesystem
        Fs to get file from
    :param oid: ObjectId
        Object ID of file to get from FS
    :param fix_as: str
        Some files should be prepared in a specific manner, this specification fixes those files
    :param fix_args:
    additional arguments required for fix
        LOCPOT  ->  requires poscar
    :rtype: str
    '''
    compressed_file = tempfile.NamedTemporaryFile(delete=False).name
    new_file = tempfile.NamedTemporaryFile(delete=False).name
    with fs.get(oid) as f:
        with open(compressed_file, 'wb') as temp:
            temp.write(f.read())
    try:
        with bz2.BZ2File(compressed_file) as b:
            with open(new_file, 'wb') as f:
                f.write(b.read())
        os.remove(compressed_file)
    except:
        new_file = compressed_file
    # if fix_as.upper() == 'LOCPOT':
    #     fix_locpot(new_file, fix_args)
    return new_file