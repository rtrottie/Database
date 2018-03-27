import uuid
import os

incar = ['ENCUT', 'EDIFF', 'ISIF', 'ISYM', 'LDAU', 'ISPIN', 'EDIFFG', 'ISMEAR', 'NUPDOWN']
default_files = ['POSCAR', 'CONTCAR', 'OUTCAR', 'vasprun.xml']
bader_files = [('bader_acf', 'ACF.dat'),         ('bader_bcf', 'BCF.dat'),         ('bader_avf', 'AVF.dat'),
               ('bader_mag_acf', 'ACF_mag.dat'), ('bader_mag_bcf', 'BCF_mag.dat'), ('bader_mag_avf', 'AVF_mag.dat')]
compressed_files = ['LOCPOT', 'CHG', 'CHGCAR', 'VASPRUN', 'OUTCAR', 'DOSCAR', 'PROCAR']

database_spec = {'ts'           : {'ts_type' : None, 'job_type' : 'ts', 'files' : bader_files},
                 'relaxation'   : {'job_type' : 'relaxation', 'files' : bader_files},
                 'convergence_study'  : {'job_type' : 'convergence', 'convergence_type' : None},
                 'dos'          : {'job_type' : 'dos', 'files' : [('procar', 'PROCAR'), ('doscar', 'DOSCAR')] + bader_files},
                 'doped'        : {'pure_material_elements' : None, 'dopant_atoms' : None, 'dopant_location' : None},
                 'adsorption'   : {'adsorbate_name' : None, 'adsorbate_atoms' : None, 'adsorption_description' : None},
                 'defect'       : {'defect_type' : None, 'defect_location' : None},
                 'charged_defect':{'defect_center' : None, 'defect_charge' : None, 'defect' : None},
                 'surface'      : {'surface_cut' : None, 'surface_termination' : None},
                 'mep'          : {'job_type': 'mep', 'files' : bader_files},
                 'antiferromagnetic' : {'antiferromagnetic_label': None},
                 'unit_cell'    : {}
}

sxdefectalign_output = {                    # definitions to scrape information from sxdefectalign output
    b'vAlign'    : (-2, 'valign'),           # first word is output keyword, tuple has format:
    b'eAlign'    : (-2, 'ealign'),           #       (index of number, desired name for number)
    b'Isolated'  : (-1, 'energy_isolated'),
    b'Periodic'  : (-1, 'energy_periodic'),
    b'Difference': (-1, 'difference'),
    b'Defect'    : (-5, 'correction'),
    b'Calculation':(-1, 'epsilon')
}

for path in ['/home/ryan/scratch/', '/export/home/mongodb/scratch', 'D:/Users/RyanTrottier/Documents/Scrap']:
    if os.path.exists(path):
        scrap_dir = path
        break

def scrap():
    return os.path.join(scrap_dir, 'temp.' + str(uuid.uuid4()))