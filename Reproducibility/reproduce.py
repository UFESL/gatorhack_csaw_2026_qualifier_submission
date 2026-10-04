"""Rebuild the submission in a workspace containing the four original inputs."""
from pathlib import Path
import argparse
import os
import shutil
import subprocess
import sys

parser=argparse.ArgumentParser()
parser.add_argument('--workspace',type=Path,default=Path(__file__).resolve().parents[2])
args=parser.parse_args()
root=args.workspace.resolve()
bundle=Path(__file__).resolve().parent
for name in ['Boat.ply','Tower.ply','Box.ply','Qualifier 2025 Problem Statement.pdf']:
    if not (root/name).is_file():raise SystemExit(f'Missing original input: {root/name}')
analysis=root/'analysis'
analysis.mkdir(exist_ok=True)
for source in bundle.glob('*.py'):
    if source.name!='reproduce.py':shutil.copy2(source,analysis/source.name)
env=os.environ.copy()
env['PYTHONPATH']=str(analysis/'deps')+os.pathsep+env.get('PYTHONPATH','')
env['PYTHONUTF8']='1'

def run(script):
    print('Running',script,flush=True)
    subprocess.run([sys.executable,str(analysis/script)],cwd=root,env=env,check=True)

if not (analysis/'3DBenchy_reference.stl').is_file() or not (analysis/'Secret Company Files.zip').is_file():
    run('download_references.py')
if not (analysis/'reference_files/Secret Company Files/main.pdf').is_file():
    run('extract_challenge.py')
for script in ['audit_meshes.py','repair_benchy.py','register_boat.py','fit_geometry.py','refine_geometry.py',
    'finalize_box_fits.py','build_models.py','validate_reconstruction.py','inspect_surface_markings.py',
    'measure_dimensions.py','build_revised_models.py','make_revised_results.py','make_dimension_report.py',
    'make_drawings.py','make_report.py','check_package.py']:
    run(script)
print('Rebuilt',root/'Team_Name_Submission.zip',flush=True)
