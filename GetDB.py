#!/usr/bin/env python

from AddDB import load_db
from Database_Tools import get_file
from Classes_Pymatgen import Poscar,Kpoints
import sys
import os

(db, fs, client) = load_db()

match_criteria = {
    'defect' : 'mn-vac',
    'defect_charge' : 2

}

matches = list(db.database.find(match_criteria))
print(len(matches))
if len(sys.argv) > 1 and sys.argv[1] == 'write':
    for match in matches[0:1]:
        name = '{}.{}'.format(''.join([x for x in match['material'] if 'mnte' not in x]), match['antiferromagnetic_label'][0])
        os.makedirs(name, exist_ok=True)
        get_file(fs, match['outcar'], fix_as='outcar', new_file=os.path.join(name, 'OUTCAR'))
        Poscar.from_dict(match['poscar']).write_file(os.path.join(name, 'POSCAR'))
        Kpoints.from_dict(match['kpoints']).write_file(os.path.join(name, 'KPOINTS'))
        print(name)