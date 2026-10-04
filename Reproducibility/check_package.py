from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'deps'))
import hashlib
import json
import zipfile
import unicodedata
import fitz
import numpy as np
import trimesh
from build_revised_models import verify_box_floor

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'Team_Name_Submission'
manifest=json.loads((OUT/'MANIFEST_SHA256.json').read_text())
for name,digest in manifest['original_inputs'].items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
for name,digest in manifest['output_files'].items():
    assert hashlib.sha256((OUT/name).read_bytes()).hexdigest()==digest,name
with zipfile.ZipFile(ROOT/'Team_Name_Submission.zip') as archive:
    assert archive.testzip() is None
    expected={'Team_Name_Submission/'+name for name in manifest['output_files']}
    expected.add('Team_Name_Submission/MANIFEST_SHA256.json')
    assert set(archive.namelist())==expected
    for name,digest in manifest['output_files'].items():
        assert hashlib.sha256(archive.read('Team_Name_Submission/'+name)).hexdigest()==digest

report=fitz.open(OUT/'Final_Report.pdf')
text='\n'.join(page.get_text() for page in report)
assert all('Step '+str(i) in text for i in range(1,10))
assert 'CSAW26' in text
assert 'unresolved' in text
assert 'CT3D.xyz' in text
assert '30 wt.%' in text and '70 wt.%' in text
assert 'Tower_revised' in text and 'Box_revised' in text
assert '0.043' in text and '0.354' in text
materials=json.loads((OUT/'Materials_Composition.json').read_text(encoding='utf8'))
assert materials['Box']['filler_weight_percent']==30
assert materials['Box']['matrix_weight_percent']==70
clues=json.loads((OUT/'Evidence/recovered_clues.json').read_text(encoding='utf8'))
assert clues['surface_markings']['Box']['text']=='30%'
dim=json.loads((OUT/'Measurements/Dimension_Measurements.json').read_text(encoding='utf8'))
assert dim['Tower']['flare']['median_radial_projection_above_baseline_mm'] > .1
profile=trimesh.load_mesh(OUT/'CAD/Tower_measured_profile.stl')
assert profile.is_volume and profile.nondegenerate_faces(height=1e-10).all()
counts=np.bincount(profile.edges_unique_inverse)
assert np.all(counts==2)
expected_radius=max(x['radius_mm'] for x in dim['Tower']['revolve_profile'])
assert abs(np.linalg.norm(profile.vertices[:,:2],axis=1).max()-expected_radius)<1e-5
assert abs(profile.extents[2]-dim['Tower']['fitted_cap_separation_mm'])<1e-5

revised=json.loads((OUT/'Evidence/revised_results.json').read_text(encoding='utf8'))
parameters=json.loads((OUT/'CAD/revised_parameters.json').read_text(encoding='utf8'))
for name in ['Tower','Box']:
    mesh=trimesh.load_mesh(OUT/f'CAD/{name}_revised.stl')
    assert mesh.is_volume and mesh.nondegenerate_faces(height=1e-10).all()
    assert len(mesh.split(only_watertight=False))==1
    assert np.all(np.bincount(mesh.edges_unique_inverse)==2)
    assert np.allclose(mesh.extents,revised[name]['geometry']['span_mm'],atol=1e-5)
    ply=trimesh.load_mesh(OUT/f'CAD/{name}_revised.ply')
    assert ply.is_volume and len(ply.faces)==len(mesh.faces)
    assert np.allclose(ply.extents,mesh.extents,atol=1e-5)
    comparison=revised[name]['same_sample_comparison']
    assert comparison['revised']['rms_mm']<comparison['initial']['rms_mm']
    assert (OUT/f'CAD/{name}_revised.scad').is_file()
    print('REVISED',name,'triangles',len(mesh.faces),'RMS',round(comparison['revised']['rms_mm'],6))
    if name=='Box':
        probes=verify_box_floor(mesh,parameters['Box'])
        saved=json.loads((OUT/'Evidence/revised_floor_probes.json').read_text(encoding='utf8'))
        assert len(saved)==len(probes) and all(x['pass'] for x in saved)
        for actual,recorded in zip(probes,saved):
            assert np.allclose(actual['surface_hits_z'],recorded['surface_hits_z'],atol=1e-5)

result_pdf=fitz.open(OUT/'Revised_Model_Results.pdf')
assert len(result_pdf)==5
result_text=unicodedata.normalize('NFKC','\n'.join(p.get_text() for p in result_pdf))
assert all(s in result_text for s in ['angular','1-mm','Z=7','25.9%','48.0%'])
for i,p in enumerate(result_pdf):
    assert len(p.get_images())>0
    p.get_pixmap(matrix=fitz.Matrix(1.2,1.2)).save(ROOT/'analysis'/f'revised_results_page_{i+1}.png')
dimension_pdf=fitz.open(OUT/'Dimension_Analysis.pdf')
dimension_text=unicodedata.normalize('NFKC','\n'.join(p.get_text() for p in dimension_pdf))
assert 'end flare' in dimension_text and 'four outlet' in dimension_text
assert 'sloped' in dimension_text and 'CAD build order' in dimension_text
assert len(dimension_pdf)>=12
assert 'Tower_revised' in dimension_text and 'Box_revised' in dimension_text
for i,p in enumerate(dimension_pdf):
    p.get_pixmap(matrix=fitz.Matrix(1.2,1.2)).save(ROOT/'analysis'/f'dimension_report_page_{i+1}.png')
drawings=fitz.open(OUT/'Restored_Parts_Drawings.pdf')
assert len(drawings)==4
for i,page in enumerate(drawings):
    assert 'Sheet '+str(i+1)+'/4' in page.get_text()
    print('DRAWING',i+1,'text_chars',len(page.get_text()))
    page.get_pixmap(matrix=fitz.Matrix(1.2,1.2)).save(ROOT/'analysis'/f'drawing_review_page_{i+1}.png')
assert 'Tower_revised' in drawings[1].get_text()
assert 'Box_revised' in drawings[2].get_text()
for i,page in enumerate(report):
    print('REPORT',i+1,'text_chars',len(page.get_text()),'images',len(page.get_images()))
    page.get_pixmap(matrix=fitz.Matrix(1.2,1.2)).save(ROOT/'analysis'/f'final_report_page_{i+1}.png')
print('PASS: Input/output hashes, archive CRC/contents, all reports/drawings, revised STL/PLY topology and bounds, fit improvement, and actual Box floor probes.')
