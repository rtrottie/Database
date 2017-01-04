import os
# from Classes_Custodian import *
# import Generate_Surface
import AddDB


folder = '/home/ryan/globus/defect_migration/Al-Fe-1/neb/67'

AddDB.add_NEB('database', ['hercynite', 'feal2o4', folder], folder)
