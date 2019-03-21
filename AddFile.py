#!/usr/bin/env python

import os
from AddDB import analyze_DATABASE_file, load_db, add_file
from pymatgen.io.vasp import Incar
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    # How to Tag Data
    parser.add_argument('FILE', help='Filename to be Added to given run')
    parser.add_argument('-o', '--oid', help='OID to be added to, if not provided attempt based on Database info')

    parser.add_argument('-p', '--parent_dirs', help='Number of Parent Dirs to look for DATABASE files.  Will use all found, favoring closer files. (Default: None)',
                        default=-1, type=int)
    args = parser.parse_args()
    (db, fs, client) = load_db()

    if not args.oid:
        database_files = []
        if args.parent_dirs >= 0:
            for pdi in range(args.parent_dirs, -1, -1):
                database_file = '../' * pdi + 'DATABASE'
                if os.path.exists(database_file):
                    database_files.append(database_file)
                    print('Found DATABASE file in ' + os.path.abspath(database_file))

        (tags, other_files) = analyze_DATABASE_file(database_files)
        tag = args.FILE.replace('.', '_')
        i = Incar.from_file('INCAR') #
        for key in i.keys():
            tags['incar.{}'.format(key)] = i[key]
        matches = list(db.database.find(tags))
        if len(matches) == 0:
            raise Exception('No Matches')
        elif len(matches) == 1:
            if tag in matches[0]:
                ip = input('provided FILE exists.  Overwrite? (y/n)')
                if ip != 'y':
                    raise Exception('Input Provided != \'y\' Quitting')
            f = add_file(fs, os.path.join(os.path.abspath('.'), args.FILE), args.FILE)
            db.database.update_one({'_id': matches[0]['_id']}, {'$set': {tag : f}})
        else:
            print('Too many matches, trying to match energy')
            from Classes_Pymatgen import Vasprun
            v = Vasprun('vasprun.xml')
            tags['energy'] = v.final_energy
            matches = list(db.database.find(tags))
            if len(matches) == 1:
                if tag in matches[0]:
                    ip = input('provided FILE exists.  Overwrite? (y/n)')
                    if ip != 'y':
                        raise Exception('Input Provided != \'y\' Quitting')
                f = add_file(fs, os.path.join(os.path.abspath('.'), args.FILE), args.FILE)
                db.database.update_one({'_id': matches[0]['_id']}, {'$set': {tag : f}})
                return

            print('Too Many matches : {}'.format([ x.keys() for x in matches ]))


