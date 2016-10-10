#!/usr/bin/env python

import argparse
from Classes_Custodian import *
import pymongo
import pymongo.collection
import gridfs
import database_cfg
from bson import ObjectId
import fnmatch
import os
import sys
import bz2
import Database_Tools

SCRAP = '/home/ryan/scratch/temp'

try: input = raw_input
except NameError: pass

def delete(database, fs, id):
    """

    :type database: pymongo.collection.Collection
    :param fs: gridfs.GridFS
    :param id: ObjectId
    :return: None
    """
    single_keys = ['min1', 'min2']
    multiple_keys = ['mep1', 'mep2', 'mepc']
    if type(id) == type('str') or type(id) == type(u'str'):
        id = ObjectId(id)
    run = database.find_one({'_id' : id})
    if run == None:
        print('Run {} could not be deleted'.format(str(id)))
        return
    if 'files' in run:
        files = run['files']
        for f in files:
            try:
                fs.delete(ObjectId(run[f]))
            except:
                if f == 'kpoints':
                    pass
                else:
                    print('Failed to Delete ' + f)
    for key in single_keys:
        if key in run:
            delete(database, fs, run[key])
    for key in multiple_keys:
        if key in run:
            for run_id in run[key]:
                delete(database, fs, run_id)

    database.delete_one({'_id' : id})

def add_file(fs, filepath, filename=''):
    if filename.upper() not in database_cfg.compressed_files:
        with open(filepath, 'rb') as f:
            fileID = fs.put(f)
    else:
        with open(Database_Tools.compress(filepath)) as f:
            fileID = fs.put(f)
    return fileID

def entry_exists(database, info):
    """
    :type database: pymongo.collection.Collection
    :type info: dict
    :rtype: bool
    """
    info = info.copy()
    if 'jobtype' in info and info['jobtype'] == 'ts' and 'ts_label' not in info:
        info['ts_label'] = {'$exists' : False}
    if 'files' in info:
        for file in info['files']:
            try:
                del info[file]
            except:
                pass
    if '_id' in info:
        id = info['_id']
        del info['_id']
    else:
        id = ''

    r = list(database.find(info))
    if len(r) > 1:
        return True
    elif len(r) == 1 and str(id) != str(r[0]['_id']):
        return True
    else:
        return False

def analyze_DATABASE_file(database_files=[], labels=[], tags={}):
    files = []
    required_tags = {}
    if database_files:
        for database_file in database_files:
            with open(database_file, 'r') as dbf:
                for line in dbf:
                    line = line.strip().lower()
                    if line in database_cfg.database_spec:
                        labels.append(line)
                    else:
                        line_list = line.split()
                        if len(line.split()) > 1:
                            tags[line_list[0]] = line_list[1:]
                        elif len(line.split()) == 1:
                            print('ERROR:  Tag provided without value.  Tag is :' + line)

    tags['labels'] = labels
    for label in labels:
        for tag in database_cfg.database_spec[label].keys():
            if tag == 'files':
                for f in database_cfg.database_spec[label]['files']:
                    if f not in files:
                        files.append(f)
            else:
                if database_cfg.database_spec[label][tag] != None:
                    tags[tag] = database_cfg.database_spec[label][tag]
                elif tag in required_tags:
                    required_tags[tag].append(label)
                else:
                    required_tags[tag] = [label]

    for tag in required_tags.keys():
        if tag not in tags:
            tags[tag] = input('Please provide value for "' + tag + '" tag.  Required because of following label(s) : '
                              + ' and '.join(required_tags[tag]) + '\n-->  ').split()
    return (tags, files)

def load_db(database_name='ryan'):
    client_ip = '10.0.2.2:27018'
    client = pymongo.MongoClient(client_ip)
    db = client[database_name]
    fs = gridfs.GridFS(db)
    return (db, fs, client)

def get_kpoint_info(kpoints):
    kpoints = Kpoints.from_file(kpoints)
    kpoints_str = 'x'.join(map(str, kpoints.kpts[0]))
    return {'kpoints_str' : kpoints_str if kpoints_str != '1x1x1' else [kpoints_str, 'gamma'],
            'kpoints_array' : kpoints.kpts[0]}

def get_incar_info(incar, elements=None):
    incar = Incar.from_file(incar)
    info = {}
    for value in database_cfg.incar:
        if value in incar:
            info[value] = incar[value]
            if value == 'LDAU' and elements:
                for i in range(len(elements)):
                    info[elements[i] + '_U'] = incar['LDAUU'][i]
    return info

def get_vasprun_info(vasprun):
    try:
        vasprun = Vasprun(vasprun, parse_eigen=False, parse_dos=False)
        info = {'converged'             : vasprun.converged,
                'converged_electronic'  : vasprun.converged_electronic,
                'converged_ionic'       : vasprun.converged_ionic,
                'energy'                : float(vasprun.final_energy)
        }
    except:
        info = {'converged'             : False,
                'converged_electronic'  : False,
                'converged_ionic'       : False,
        }
    return info

def add_charged_defect(collection, material, directory, other_info, other_files=[]):
    print('Adding a Charged defect, must be in charged defect cell or directory with ... n3 n2 n1 0 1 2 3 ...')
    if os.path.exists(os.path.join(directory, 'INCAR')):  # is run directory
        dirs = [('', int(other_info['defect_charge'][0]))]
    else:  # must go to children ... n3 n2 n1 0 1 2 3 ... to find runs
        dirs = []
        for dir in [name for name in os.listdir(directory) if os.path.isdir(name)]:  # for every directory
            try:
                dirs.append((dir, int(dir.replace('n','-')))) # n is used in place of - for filesystem compatibility make sure it is a valid dir
            except:
                pass
    for (dir, charge) in dirs:
        print(dir)
        # print('Compressing LOCPOT...')
        # with open(os.path.join(directory, dir, 'LOCPOT')) as f: # compress LOCPOT
        #     with bz2.BZ2File(os.path.join(directory, dir, 'LOCPOT.tar.bz2'), 'w') as b:
        #         b.write(f.read())
        # print('Compressed')
        other_info['defect_charge'] = charge
        add_dir(collection, material, os.path.join(directory,dir), other_info, other_files + [('locpot', os.path.join(directory, dir, 'LOCPOT'))])

def add_MEP(collection, material, directory, other_info, other_files=[]):
    (db, fs, client) = load_db()
    document = {}
    document['files'] = []
    print('Adding a Charged defect, must be in meps directory with mep1 mep2 mepc')
    main_dirs = [('mep1', 1), ('mep2', 2), ('mepc', 'c')]
    for main_dir, side in main_dirs:
        print(main_dir)
        document[main_dir] = []
        if main_dir == 'mep1' or main_dir == 'mep2':
            vasprun_file = os.path.join(main_dir, 'MEP.xml')
            v = Vasprun(vasprun_file)
            fileID = add_file(fs, vasprun_file, 'vasprun')
            document['vasprun_{}'.format(side)] = fileID
            document['files'].append('vasprun_{}'.format(side))
        else:
            for i in range(2):
                document['POSCAR_{}'.format(i)] = Poscar.from_file(os.path.join(main_dir, 'POSCAR.1')).as_dict()
        dirs = []
        for dir in [name for name in os.listdir(os.path.join(directory, main_dir)) if os.path.isdir(os.path.join(directory, main_dir, name))]:  # for every directory
            try:
                dirs.append((os.path.join(main_dir, dir), int(dir))) # n is used in place of - for filesystem compatibility make sure it is a valid dir
            except:
                pass
        for (dir, stage) in dirs:
            print(dir)
            try:
                other_info['MEP_position'] = stage
                other_info['MEP_main_dir'] = main_dir
                other_info['MEP_side'] = side
                if os.path.exists(os.path.join(directory, dir, 'vasprun.xml')):
                    id = add_dir(collection, material, os.path.join(directory, dir), other_info=other_info, other_files=other_files).inserted_id
                document[main_dir].append(id)
            except Exception as e:
                for k, v in document.items():
                    if type(v) == ObjectId:
                        if 'vasprun' in k:
                            fs.delete(v)
                        else:
                            delete(db[collection], fs, v)
                if 'mep' in k:
                    for run_id in v:
                        try:
                            delete(db[collection], fs, run_id)
                        except:
                            pass
                print('Failed to Add MEP run, all files have been deleted')
                raise e
    other_info.update(document)
    db[collection].insert_one(document)

def add_nupdown_convergence(collection, material, directory, other_info={}, other_files=[], check_convergence=True):
    dirs = []
    print('Adding NUPDOWN Convergence.  Assuming dir/nupdown/{{ nupdown_# }} convention (may provide any parent/child of this structure)')

    if os.path.exists(os.path.join(directory, 'nupdown')):                                                              # Getting (nupdown dir, nupdown) in a list
        for dir in [dir for dir in os.listdir(os.path.join(directory, 'nupdown')) if os.path.isdir(os.path.join(directory, 'nupdown', dir))]:
            try:
                dirs.append((os.path.join(directory, 'nupdown', dir), int(dir.replace('n', '-'))))
            except:
                pass
    else:
        for dir in [name for name in os.listdir(directory) if os.path.isdir(name)]:
            try:
                dirs.append((dir, int(dir)))
            except:
                pass
    if len(dirs) == 0:
        dirs.append((directory, Incar.from_file('INCAR')['NUPDOWN']))

    for (dir, nupdown) in dirs:
        other_info['NUPDOWN'] = nupdown
        add_vasp_run(collection, material, os.path.join(dir, 'INCAR'), os.path.join(dir, 'KPOINTS'),
                     os.path.join(dir, 'POTCAR'), os.path.join(dir, 'CONTCAR'), os.path.join(dir, 'OUTCAR'), os.path.join(dir, 'vasprun.xml'),
                     other_info=other_info, other_files=other_files, check_convergence=check_convergence)

def add_vasp_run(collection, material, incar, kpoints, potcar, contcar, outcar, vasprun, other_info={}, other_files=[], force=False, check_convergence=True):
    (db, fs, client) = load_db()
    collection = db[collection]
    p = Poscar.from_file(contcar)
    pot = Potcar.from_file(potcar)
    info = {
        'material' : material,
        'elements' : p.site_symbols,
        'potcar'   : pot.symbols,
        'potcar_functional' : pot.functional
    }
    files = [('outcar', outcar), ('vasprun', vasprun)] + other_files

    info['incar'] = Incar.from_file(incar)
    info['poscar'] = p.as_dict()
    info['kpoints'] = Kpoints.from_file(kpoints).as_dict()
    info.update(get_vasprun_info(vasprun))
    info.update(other_info)
    if not info['converged'] and check_convergence:
        continueP = input('Run is not Converged.  Add Anyway? (y/n)\n --> ')
        if continueP == 'y' or continueP == 'yes':
            pass
        else:
            print('Did not Select y/yes to add')
            client.close()
            return


    if entry_exists(collection, info) and not force:
        print('Identical Entry Exists')
        client.close()
        return False
    else:
        info['files'] = []
        for (filename, filepath) in files:
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                fileID = add_file(fs, filepath, filename)
                info[filename] = fileID
                info['files'].append(filename)
            else:
                info[filename] = 'none'
        result = collection.insert_one(info)
        print('Added')
        client.close()
        return result

def add_dimer_run(collection, material, directory, other_info={}, other_files = [], force=False):
    print('Adding Dimer Run.  mins Folder must exist')
    dinfo = {'dimer_min' : True}
    other_info['min1'] = add_dir(collection, material, os.path.join(directory, 'mins', 'min1'), dinfo, force=True).inserted_id
    other_info['min2'] = add_dir(collection, material, os.path.join(directory, 'mins', 'min2'), dinfo, force=True).inserted_id

    modecar = os.path.join(directory, 'NEWMODECAR') if os.path.exists(os.path.join(directory, 'NEWMODECAR')) \
                                                       and os.path.getsize(os.path.join(directory, 'NEWMODECAR')) > 0 \
              else os.path.join(directory, 'MODECAR')
    other_files.append(('modecar', modecar))
    attempt = add_dir(collection, material, directory, other_info=other_info, other_files=other_files, force=force)
    if attempt:
        return attempt
    else:
        (db, fs, client) = load_db()
        collection = db[collection]
        delete(collection, fs, other_info['min1'])
        delete(collection, fs, other_info['min2'])
        client.close()
        return False

def add_gsm_run(collection, material, directory, other_info={}, other_files = [], force=False):
    (db, fs, client) = load_db()
    collection = db[collection]
    images = []
    energies = []
    image_dir = [x for x in os.listdir('scratch') if fnmatch.fnmatch(x, 'IMAGE.*')]
    image_dir.sort()
    for dir in image_dir:
        image = add_dir(collection, material, dir, other_info={}, other_files=[], force=True)
        print('{ "_id" : "' + str(image) + '" }')
        images.append(image)
        energies.append(collection.find_one({'_id' : image}))
    ts_i = energies.index(max(energies))
    return collection.insert_one()

def add_dir(collection, material, directory, other_info={}, other_files=[], force=False):
    print(other_files)
    poscar = os.path.join(directory, 'CONTCAR') if os.path.exists(os.path.join(directory, 'CONTCAR')) and os.path.getsize(os.path.join(directory, 'CONTCAR')) > 0 else os.path.join(directory, 'POSCAR')
    other_files = [ (n, os.path.join(directory, x)) for n, x in other_files ]
    return add_vasp_run(collection, material, os.path.join(directory, 'INCAR'), os.path.join(directory, 'KPOINTS'),
                        os.path.join(directory, 'POTCAR'), os.path.join(directory, poscar), os.path.join(directory, 'OUTCAR'),
                        os.path.join(directory, 'vasprun.xml'), other_info=other_info, other_files=other_files, force=force)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--database_file', help='Location of File to specify other important database tags (PLACEHOLDER DOESNT WORK)')
    parser.add_argument('-p', '--parent_dirs', help='Number of Parent Dirs to look for DATABASE files.  Will use all found, favoring closer files. (Default: None)',
                        default=-1, type=int)
    parser.add_argument('-f', '--files', help='Extra Files to include (LOCPOT, CHG, CHGCAR, etc...)',
                        type=str, nargs='*')
    parser.add_argument('-l', '--labels', help='Labels to apply to run.  Must be one of predifined values in cfg file',
                        default=[], nargs='*')
    parser.add_argument('-m', '--material', help='Material names, usually provided with DATABASE Files (will overwrite these values if provided)',
                        nargs='*')
    parser.add_argument('-n', '--nupdown', help='Specifies this is a Nupdown run both this flag and label must be set',
                        action='store_true')
    parser.add_argument('-c', '--charged_defect', help='Specifies this is a Charged Defect run both this flag and label must be set',
                        action='store_true')
    parser.add_argument('--fn', '--force-nupdown', help='Force adding all NUPDOWN',
                        action='store_true')
    parser.add_argument('--mep', '--minimum-energy-pathway', help='add MEP run',
                        action='store_true')
    parser.add_argument('--cc', '--check_convergence', help='Don"t check convergence',
                        action='store_false')
    args = parser.parse_args()

    database_files = []
    if args.parent_dirs >= 0:
        for pdi in range(args.parent_dirs, -1, -1):
            database_file = '../' * pdi + 'DATABASE'
            if os.path.exists(database_file):
                database_files.append(database_file)
                print('Found DATABASE file in ' + os.path.abspath(database_file))

    (tags, other_files) = analyze_DATABASE_file(database_files, args.labels)
    if args.files:
        other_files = other_files + [ (s.lower(), s) for s in args.files ]
    if args.material:
        material = args.material
    elif 'material' in tags:
        material = tags.pop('material')
    else:
        material = input('Name(s) of Material?\n--> ').strip().split()

    print(tags)
    print(other_files)

    if args.nupdown and 'convergence_type' in tags and tags['convergence_type'][0] == 'nupdown':
        add_nupdown_convergence('database', material, os.path.abspath('.'), tags, other_files=other_files)
    elif args.charged_defect and 'charged_defect' in tags['labels']:
        add_charged_defect('database', material, os.path.abspath('.'), tags, other_files=other_files)
    elif args.charged_defect != 'charged_defect' in tags['labels']: # one or the other is established
        raise Exception('charged_defect must be specified twice')
    elif args.nupdown != ('convergence_type' in tags and tags['convergence_type'][0] == 'nupdown'):
        raise Exception('must specify -n flag and correctly label DATABASE file')
    # elif os.path.exists('INCAR') and 'ICHAIN' in Incar.from_file('INCAR') and Incar.from_file('INCAR')['ICHAIN'] == 2:
    #     if tags['ts_type'][0] != 'dimer':
    #         raise Exception('Dimer run, dimer ts_type must be set and ICHAIN = 2 in INCAR')
    #     add_dimer_run('database', material, os.path.abspath('.'), other_info=tags, other_files=other_files)
    elif os.path.exists('nupdown') and not args.fn:
        i = input('nupdown folder found.  Add folder or no? (y/n)\n  -->  ')
        if i.lower() == 'y':
            add_nupdown_convergence('database', material, os.path.abspath('.'), tags, check_convergence=args.cc)
        elif i.lower() == 'n':
            poscar = 'CONTCAR' if os.path.exists('CONTCAR') and os.path.getsize('CONTCAR') > 0 else 'POSCAR'
            add_vasp_run('database', material, 'INCAR', 'KPOINTS', 'POTCAR', poscar, 'OUTCAR', 'vasprun.xml', tags, other_files, check_convergence=args.cc)
        else:
            raise Exception('Must say either y or n')
    elif os.path.exists('nupdown') and args.fn:
        add_nupdown_convergence('database', material, os.path.abspath('.'), tags, other_files)
    elif args.mep:
        add_MEP('database', material, os.path.abspath('.'), tags, other_files=other_files)
    else:
        poscar = 'CONTCAR' if os.path.exists('CONTCAR') and os.path.getsize('CONTCAR') > 0 else 'POSCAR'
        add_vasp_run('database', material, 'INCAR', 'KPOINTS', 'POTCAR', poscar, 'OUTCAR', 'vasprun.xml', tags, other_files, check_convergence=args.cc)