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
import copy
from Helpers import isint
import subprocess
import File_Management
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
    if True not in [compressed_filename in filename.upper() for compressed_filename in database_cfg.compressed_files]:
        with open(filepath, 'rb') as f:
            fileID = fs.put(f)
    else:
        with open(Database_Tools.compress(filepath), 'rb') as f:
            fileID = fs.put(f)
    return fileID

def entry_exists(database, info):
    """
    Check if entry exists based on the contents of the documents.  Does not compare files, or subdoccument classes
    i.e. Poscar, Kpoints, and Incar
    :type database: pymongo.collection.Collection
    :type info: dict
    :rtype: bool
    """
    info = copy.deepcopy(info)
    # Ensure ts_label is done correctly
    if 'jobtype' in info and info['jobtype'] == 'ts' and 'ts_label' not in info:
        info['ts_label'] = {'$exists' : False}

    # files will always be different since they have differen fileID
    # do not check that the files are identical
    if 'files' in info:
        for file in info['files']:
            info[file] = {'$exists' : True}
    if '_id' in info:
        id = info['_id']
        del info['_id']
    else:
        id = ''

    if 'incar' in info:
        for item in info['incar']:
            if item not in ['SYSTEM']:
                info['incar.{}'.format(item)] = info['incar'][item]
    # Remove POSCAR, INCAR, and KPOINTS which do not match correctly
    for item in ['poscar', 'kpoints', 'incar', 'poscars']:
        if item in info:
            info[item] = {'$exists' : True}

    r = list(database.find(info))
    if len(r) > 1:
        print(info)
        return True
    elif len(r) == 1 and str(id) != str(r[0]['_id']):
        print(info)
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
    client_ip = '127.0.0.1:27017'
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

def add_charged_defect(collection, material, directory, other_info, other_files=[], check_convergence=True, ignore_unconverged=False):
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
        add_dir(collection, material, os.path.join(directory,dir), other_info, other_files + [('locpot', os.path.join(directory, dir, 'LOCPOT'))], check_convergence=check_convergence, ignore_unconverged=ignore_unconverged)

def add_NEB(collection, material, directory, other_info={}, other_files=[]):
    '''

    :param collection: str
        Name of Collection for Database
    :param material: str
        name of Material that will be added to database
    :param directory: str
        NEB directory that will be added to Database
    :param other_info:
        other_info that can be included
    :param other_files:
        other_files that can be included, most files included here will be added from all image directories
    :return: pymongo.results.InsertOneResult
    '''

    from pymatgen.analysis.transition_state import NEBAnalysis

    # preparing variables
    incar = Incar.from_file(os.path.join(directory, 'INCAR'))
    images = incar['IMAGES']
    subdirs = [ str(i).zfill(2) for i in range(images+2) ]

    # Setting up NEB files
    os.chdir(directory)
    # nebbarrier = File_Management.file_to_dict(subprocess.check_output('nebbarrier.pl ; cat neb.dat', shell=True),
    #                                             ['Image', 'Distance', 'Energy', 'Spring Forces' , 'Image_Duplicate'] )
    # nebef      = File_Management.file_to_dict(subprocess.check_output(['nebef.pl']),
    #                                           ['Image', 'Force', 'Energy-Absolute', 'Energy-Relative'] )
    # nebefs     = File_Management.file_to_dict(subprocess.check_output(['nebefs.pl']).replace(b'Rel Energy', b'Rel_Energy')) # Splits on whitespace, label must be one word

    other_info['images'] = images
    # other_info['nebbarrier'] = nebbarrier
    # other_info['nebef'] = nebef
    # other_info['nebefs'] = nebefs

    neb = NEBAnalysis.from_dir('.')
    other_info['energy'] = max(neb.energies)
    other_info['energies'] = list(neb.energies)
    max_i = list(neb.energies).index(max(neb.energies))
    new_files = []
    for i in range(images+2):
        dir = str(i).zfill(2)
        other_info['poscar_{}'.format(dir)] = Poscar.from_file('{}/{}'.format(dir,'POSCAR')).as_dict()
        for name, location in other_files:
            new_files.append(('{}_{}'.format(name,dir), '{}/{}'.format(dir,location)))

    (db, fs, client) = load_db()
    if entry_exists(db[collection], {'energy' : max(neb.energies), 'energies' : list(neb.energies)}):
        print('Identical Entry Exists')
        client.close()
        return False
    client.close()
    add_vasp_run(collection, material, 'INCAR', 'KPOINTS', 'POTCAR', os.path.join(str(max_i).zfill(2), 'CONTCAR'), 'vasprun.xml', other_info=other_info, other_files=new_files)
    return

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
                     os.path.join(dir, 'POTCAR'), os.path.join(dir, 'CONTCAR'), os.path.join(dir, 'vasprun.xml'),
                     other_info=other_info, other_files=other_files, check_convergence=check_convergence)

def add_multiple_convergence(collection, material, directories=['.'], suffixes=[''], other_info_function=None, other_info={}, other_files=[], check_convergence=True):
    '''

    :param collection: str
        Name of Collection for Database
    :param material: str
        name of Material that will be added to database
    :param directories: str list
        directories from which to find VASP output files.  Each run will be added separatly
    :param suffixes:
        suffixes from which to find VASP output files in a given directory.  Each run will be added separatly
    :param other_info_function: function
        function that takes the directory, suffix, and other_info directory and adds information to be stored in database
    :param other_info: dict
        Other identifying info that will be included in database documet
    :param other_files: list
        Other files that should be stored
    :param check_convergence: bool
        Check for convergence (Default True).  If convergence is not found and this is True, do not add run to DB
    :return:
    '''
    info = []
    for directory in directories:
        for suffix in suffixes:
            def loc(f):             # function to make filename
                return os.path.join(directory, '{}{}'.format(f,suffix))
            if other_info_function:
                other_info = other_info_function(directory, suffix, other_info)
            info.append(add_vasp_run(collection=collection, material=material, incar=loc('INCAR'), kpoints=loc('KPOINTS'),
                                     potcar='POTCAR', contcar=loc('CONTCAR'), vasprun=loc('vasprun.xml'),
                                     other_info=other_info, other_files=[ (n, loc(f)) for (n, f) in other_files ],
                                     check_convergence=check_convergence))
    return info

def add_encut_convergence(collection, material, directory, other_info, other_files):
    suffix = [ f.replace('CONTCAR', '') for f in os.listdir(directory) if 'CONTCAR.encut' in f ]
    def other_info_function(directory, suffix, other_info):
        other_info = copy.deepcopy(other_info) # copy other_info to avoid overwritting
        other_info['encut_convergence'] = int(suffix.replace('.encut.',''))
        return other_info
    return add_multiple_convergence(collection, material, directories=[directory], suffixes=suffix,
                                    other_info_function=other_info_function, other_info=other_info, other_files=other_files,
                                    check_convergence=True)

def add_kpoints_convergence(collection, material, directory, other_info, other_files):
    suffix = [ f.replace('CONTCAR', '') for f in os.listdir(directory) if 'CONTCAR.kpoints' in f ]
    def other_info_function(directory, suffix, other_info):
        other_info = copy.deepcopy(other_info) # copy other_info to avoid overwritting
        other_info['kpoints_convergence'] = suffix.replace('.kpoints.','').split('x')
        return other_info
    return add_multiple_convergence(collection, material, directories=[directory], suffixes=suffix,
                                    other_info_function=other_info_function, other_info=other_info, other_files=other_files,
                                    check_convergence=True)

def add_interpolation(collection, material, directory, incar, kpoints, potcar, other_info={}, other_files=[],
                  force=False, check_convergence=True, ignore_unconverged=False):

    potcar = Potcar.from_file(potcar)
    incar = Incar.from_file(incar)
    kpoints = Kpoints.from_file(kpoints)
    files = other_files

    dirs = [x for x in os.listdir(directory) if os.path.isdir(x) and isint(x)]
    dirs.sort()
    poscars  = [Poscar.from_file(os.path.join(directory, dir, 'POSCAR')).as_dict() for dir in dirs]
    energies = []
    for dir in dirs:
        with open(os.path.join(dir, 'energy.txt')) as f:
            energies.append(float(f.read().split()[0]))

    info = {
        'material': material,
        'potcar': potcar.symbols,
        'potcar_functional': potcar.functional,
        'dirs' : dirs,
        'poscars' : poscars,
        'energies' : energies
    }

    info.update(other_info)

    info['incar'] = incar  # Incar is already a dict
    info['kpoints'] = kpoints.as_dict()


    # Check for convergence
    delta = 0.01
    max_e = max(energies)
    max_i = energies.index(max_e)
    convergedP = (max_e - energies[max_i-1] <= delta if max_i > 0 else True) and (max_e - energies[max_i+1] <= delta if max_i < len(energies)-1 else True)
    if not convergedP and check_convergence:
        if ignore_unconverged:
            print('Not Adding Unconverged Run')
            return
        continueP = input('Run is not Converged.  Add Anyway? (y/n)\n --> ')
        if continueP == 'y' or continueP == 'yes':
            pass
        else:
            print('Did not Select y/yes to add')
            return

    # Open up DB connection and check if entry exists, close if entry does exist
    (db, fs, client) = load_db()
    collection = db[collection]
    if entry_exists(collection, info) and not force:
        print('Identical Entry Exists')
        client.close()
        return False
    # Prepare Files to be added to DB
    info['files'] = []
    # print(files)
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

def add_vasp_run(collection, material, incar, kpoints, potcar, contcar, vasprun, other_info={}, other_files=[], force=False, check_convergence=True, ignore_unconverged=False):
    '''
    Adds a VASP run to the database.  All input/output files must be provided in the arguments.

    :param collection: str
        Name of Collection for Database
    :param material: str
        name of Material that will be added to database
    :param incar: str
        Location of INCAR file on disk
    :param kpoints: str
        Location of KPOINTS file on disk
    :param potcar: str
        Location of POTCAR file on disk
    :param contcar: str
        Location of CONTCAR (or POSCAR) file on disk
    :param outcar: str
        Location of OUTCAR file on disk
    :param vasprun: str
        Location of vasprun.xml file on disk
    :param other_info: dict
        Other identifying info that will be included in database documet
    :param other_files: list
        Other files that should be stored
    :param force: bool
        Add run even if duplicate enetry exists
    :param check_convergence: bool
        Check for convergence (Default True).  If convergence is not found and this is True, do not add run to DB
    :return: pymongo.results.InsertOneResult
    '''
    # Convert input strings to pymatgen file types (where applicable)  sets up other files to be stored
    poscar = Poscar.from_file(contcar)
    potcar = Potcar.from_file(potcar)
    incar = Incar.from_file(incar)
    kpoints = Kpoints.from_file(kpoints)
    files = [('vasprun', vasprun)] + other_files

    # Creating document information
    info = {
        'material' : material,
        'elements' : poscar.site_symbols,
        'potcar'   : potcar.symbols,
        'potcar_functional' : potcar.functional
    }
    info['incar'] = incar                   # Incar is already a dict
    info['poscar'] = poscar.as_dict()
    info['kpoints'] = kpoints.as_dict()
    vasprun_info = get_vasprun_info(vasprun)
    if 'energy' in other_info:
        try:
            del vasprun_info['energy']
        except:
            print('Energy not found in  vasprun.xml, likely unconverged')
    info.update(vasprun_info)
    info.update(other_info)

    # Check for convergence
    if not info['converged'] and check_convergence:
        if ignore_unconverged:
            print('Not Adding Unconverged Run')
            return
        continueP = input('Run is not Converged.  Add Anyway? (y/n)\n --> ')
        if continueP == 'y' or continueP == 'yes':
            pass
        else:
            print('Did not Select y/yes to add')
            return

    # Open up DB connection and check if entry exists, close if entry does exist
    (db, fs, client) = load_db()
    collection = db[collection]
    if entry_exists(collection, info) and not force:
        print('Identical Entry Exists')
        client.close()
        return False
    # Prepare Files to be added to DB
    info['files'] = []
    # print(files)
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

def add_dir(collection, material, directory, other_info={}, other_files=[], force=False, check_convergence=True, ignore_unconverged=False):
    print(other_files)
    poscar = os.path.join(directory, 'CONTCAR') if os.path.exists(os.path.join(directory, 'CONTCAR')) and os.path.getsize(os.path.join(directory, 'CONTCAR')) > 0 else os.path.join(directory, 'POSCAR')
    other_files = [ (n, os.path.join(directory, x)) for n, x in other_files ]
    return add_vasp_run(collection, material, os.path.join(directory, 'INCAR'), os.path.join(directory, 'KPOINTS'),
                        os.path.join(directory, 'POTCAR'), os.path.join(directory, poscar),
                        os.path.join(directory, 'vasprun.xml'), other_info=other_info, other_files=other_files, force=force, check_convergence=check_convergence, ignore_unconverged=ignore_unconverged)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    # How to Tag Data
    parser.add_argument('-d', '--database_file', help='Location of File to specify other important database tags',
                        default=None)
    parser.add_argument('-p', '--parent_dirs', help='Number of Parent Dirs to look for DATABASE files.  Will use all found, favoring closer files. (Default: None)',
                        default=-1, type=int)
    parser.add_argument('-f', '--files', help='Extra Files to include (LOCPOT, CHG, CHGCAR, etc...)',
                        type=str, nargs='*')
    parser.add_argument('-l', '--labels', help='Labels to apply to run.  Must be one of predifined values in cfg file',
                        default=[], nargs='*')
    parser.add_argument('-m', '--material', help='Material names, usually provided with DATABASE Files (will overwrite these values if provided)',
                        nargs='*')

    # Specifc runs that will be added
    parser.add_argument('-n', '--nupdown', help='Specifies this is a Nupdown run both this flag and label must be set',
                        action='store_true')
    parser.add_argument('--convergence', help='Specifies that a convergence run is being added.  Appropriate flag and label must match',
                        type=str, default=None)
    parser.add_argument('-c', '--charged_defect', help='Specifies this is a Charged Defect run both this flag and label must be set',
                        action='store_true')
    parser.add_argument('--interpolation', help='Specifies this is a interpolation run both this flag and label must be set',
                        action='store_true')
    parser.add_argument('--fn', '--force-nupdown', help='Force adding all NUPDOWN',
                        action='store_true')
    parser.add_argument('--mep', '--minimum-energy-pathway', help='add MEP run',
                        action='store_true')
    parser.add_argument('--cc', '--check_convergence', help='Don"t check convergence',
                        action='store_false')
    parser.add_argument('--ignore_unconverged', help='Ignore Unconverged Run',
                        action='store_true')
    parser.add_argument('--neb', help='add NEB run',
                        action='store_true')
    parser.add_argument('--pc', help='add Plane Constrained run',
                        action='store_true')
    parser.add_argument('--prompt_material', help='if material isn\'t specified, prompt',
                        action='store_true')
    args = parser.parse_args()

    # Find and Parse Database Files
    database_files = []
    if args.database_file:
        database_files.append(args.database_file)
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
        if args.prompt_material:
            material = input('Name(s) of Material?\n--> ').strip().split()
        else:
            raise Exception('Material not Specified')

    print(tags)
    print(other_files)

    other_files.append(('outcar', 'OUTCAR'))

    if os.path.exists('nupdown') and not args.fn:
        i = input('nupdown folder found.  Add folder or no? (y/n)\n  -->  ')
        if i.lower() == 'y':
            add_nupdown_convergence('database', material, os.path.abspath('.'), tags, check_convergence=args.cc)
        elif i.lower() == 'n':
            # poscar = 'CONTCAR' if os.path.exists('CONTCAR') and os.path.getsize('CONTCAR') > 0 else 'POSCAR'
            # add_vasp_run('database', material, 'INCAR', 'KPOINTS', 'POTCAR', poscar, 'vasprun.xml', tags, other_files, check_convergence=args.cc)
            pass
        else:
            raise Exception('Must say either y or n')

    if 'ts_type' in tags and ('pc' in tags['ts_type'] or 'plane_constrained' in tags['ts_type']) and args.pc:
        files = [x for x in os.listdir() if ('.e' in x) or ('.o' in x)]
        files.sort()
        with open(files[-1]) as f:
            if 'Done' not in f.readlines()[-1] and args.cc:
                if args.ignore_unconverged:
                    raise Exception('Not Adding Unconverged Run')
                continueP = input('Run is not Converged.  Add Anyway? (y/n)\n --> ')
                if continueP == 'y' or continueP == 'yes':
                    pass
                else:
                    raise Exception('Did not Select y/yes to add')
    elif ('ts_type' in tags and ('pc' in tags['ts_type'] or 'plane_constrained' in tags['ts_type'])) or args.pc:
        raise Exception('pc must be specified twice')

    if args.nupdown and 'convergence_type' in tags and tags['convergence_type'][0] == 'nupdown':
        add_nupdown_convergence('database', material, os.path.abspath('.'), tags, other_files=other_files)
    elif args.charged_defect and 'charged_defect' in tags['labels']:
        add_charged_defect('database', material, os.path.abspath('.'), tags, other_files=other_files, check_convergence=args.cc, ignore_unconverged=args.ignore_unconverged)
    elif args.charged_defect != 'charged_defect' in tags['labels']: # one or the other is established
        raise Exception('charged_defect must be specified twice')

    elif args.interpolation and 'interpolation' in tags['labels']:
        add_interpolation('database', material, os.path.abspath('.'),'INCAR', 'KPOINTS', 'POTCAR', other_info=tags, other_files=other_files, check_convergence=args.cc, ignore_unconverged=args.ignore_unconverged)
    elif args.interpolation != 'interpolation' in tags['labels']: # one or the other is established
        raise Exception('interpolation must be specified twice')

    elif args.nupdown != ('convergence_type' in tags and tags['convergence_type'][0] == 'nupdown'):
        raise Exception('must specify -n flag and correctly label DATABASE file')
    # elif os.path.exists('INCAR') and 'ICHAIN' in Incar.from_file('INCAR') and Incar.from_file('INCAR')['ICHAIN'] == 2:
    #     if tags['ts_type'][0] != 'dimer':
    #         raise Exception('Dimer run, dimer ts_type must be set and ICHAIN = 2 in INCAR')
    #     add_dimer_run('database', material, os.path.abspath('.'), other_info=tags, other_files=other_files)
    # elif os.path.exists('nupdown') and not args.fn:
    #     i = input('nupdown folder found.  Add folder or no? (y/n)\n  -->  ')
    #     if i.lower() == 'y':
    #         add_nupdown_convergence('database', material, os.path.abspath('.'), tags, check_convergence=args.cc)
    #     elif i.lower() == 'n':
    #         poscar = 'CONTCAR' if os.path.exists('CONTCAR') and os.path.getsize('CONTCAR') > 0 else 'POSCAR'
    #         add_vasp_run('database', material, 'INCAR', 'KPOINTS', 'POTCAR', poscar, 'vasprun.xml', tags, other_files, check_convergence=args.cc)
    #     else:
    #         raise Exception('Must say either y or n')
    elif args.convergence:
        if 'convergence_type' not in tags or tags['convergence_type'][0] != args.convergence: # if Convergence tag and label are not set correctly
            raise Exception('Convergence _type in DATABASE file does not match --convergence provided')
        elif args.convergence == 'encut':
            add_encut_convergence('database', material, directory=os.path.abspath('.'), other_info=tags, other_files=other_files)
        elif args.convergence == 'kpoints':
            add_kpoints_convergence('database', material, directory=os.path.abspath('.'), other_info=tags, other_files=other_files)
        else:
            raise Exception('Convergence type not yet implemented')

    elif os.path.exists('nupdown') and args.fn:
        add_nupdown_convergence('database', material, os.path.abspath('.'), tags, other_files)
    elif args.mep:
        add_MEP('database', material, os.path.abspath('.'), tags, other_files=other_files)
    elif args.neb:
        add_NEB('database', material, os.path.abspath('.'), tags, other_files=other_files)
    else:
        poscar = 'CONTCAR' if os.path.exists('CONTCAR') and os.path.getsize('CONTCAR') > 0 else 'POSCAR'
        add_vasp_run('database', material, 'INCAR', 'KPOINTS', 'POTCAR', poscar, 'vasprun.xml', tags, other_files, check_convergence=args.cc, ignore_unconverged=args.ignore_unconverged)