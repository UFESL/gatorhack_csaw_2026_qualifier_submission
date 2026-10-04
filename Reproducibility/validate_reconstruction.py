from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'deps'))
import json
import numpy as np
import trimesh

ROOT=Path(__file__).resolve().parent.parent
AN=ROOT/'analysis'
RNG=np.random.default_rng(2026)
results={}
for name in ['Boat','Tower','Box']:
    mesh=trimesh.load_mesh(ROOT/'Team_Name_Submission/CAD'/f'{name}_reconstructed.stl')
    scan=np.load(AN/f'{name}_aligned.npz')['vertices']
    sample=scan[RNG.choice(len(scan),min(18000,len(scan)),replace=False)]
    distances=[]
    for start in range(0,len(sample),600):
        _,distance,_=trimesh.proximity.closest_point(mesh,sample[start:start+600])
        distances.append(distance)
    distance=np.concatenate(distances)
    results[name]={'sampled_scan_vertices':len(sample),'exact_triangle_distance_percentiles_mm':np.percentile(distance,[50,90,95,99,100]).tolist(),
        'all_sample_rms_mm':float(np.sqrt(np.mean(distance**2))),
        'within_0_5_mm_percent':float(100*np.mean(distance<=.5)),
        'within_1_0_mm_percent':float(100*np.mean(distance<=1)),
        'note':'One-way scan-to-model distances. Missing scan regions cannot validate reconstructed internal features.'}
    print(name,json.dumps(results[name]),flush=True)
(AN/'surface_comparison.json').write_text(json.dumps(results,indent=2))
