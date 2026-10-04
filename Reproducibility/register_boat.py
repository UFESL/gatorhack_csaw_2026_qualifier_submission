"""Match the surviving boat scan to the official 3DBenchy reference using trimmed ICP."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'deps'))
import itertools
import json
import numpy as np
import trimesh
from scipy.spatial import cKDTree
from fit_geometry import plot

OUT=Path(__file__).resolve().parent
RNG=np.random.default_rng(2026)


def pca(p):
    _,e=np.linalg.eigh(np.cov(p.T));return e[:,::-1]


def fit_rigid(p,q):
    pc=p.mean(0);qc=q.mean(0)
    u,_,vh=np.linalg.svd((p-pc).T@(q-qc))
    d=np.eye(3);d[-1,-1]=np.linalg.det(u@vh)
    r=u@d@vh
    return r,qc-pc@r


if __name__=='__main__':
    scan=np.load(OUT/'Boat_scan.npz');v=scan['vertices'];f=scan['faces']
    ref=trimesh.load_mesh(OUT/'Boat_reference_clean.stl')
    surface,_=trimesh.sample.sample_surface(ref,180000,seed=2026)
    target=np.vstack((ref.vertices,surface))
    tree=cKDTree(target)
    source=v[RNG.choice(len(v),10000,replace=False)]
    sb=pca(source);tb=pca(surface);sc=source.mean(0);tc=surface.mean(0)
    candidates=[]
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product([-1,1],repeat=3):
            r=sb@np.diag(signs)@tb[:,perm].T
            if np.linalg.det(r)<.99:continue
            t=tc-sc@r
            p=source@r+t
            for _ in range(28):
                dist,idx=tree.query(p,workers=-1)
                keep=dist<np.quantile(dist,.80)
                dr,dt=fit_rigid(p[keep],target[idx[keep]])
                p=p@dr+dt;r=r@dr;t=t@dr+dt
            dist,_=tree.query(p,workers=-1)
            score=float(np.sqrt(np.mean(np.sort(dist)[:8000]**2)))
            candidates.append((score,r,t))
    score,r,t=min(candidates,key=lambda x:x[0])
    source=v[RNG.choice(len(v),45000,replace=False)];p=source@r+t
    for _ in range(70):
        dist,idx=tree.query(p,workers=-1);keep=dist<np.quantile(dist,.9)
        dr,dt=fit_rigid(p[keep],target[idx[keep]])
        p=p@dr+dt;r=r@dr;t=t@dr+dt
        if np.linalg.norm(dt)<1e-5 and np.linalg.norm(dr-np.eye(3))<1e-5:break
    aligned=v@r+t
    dist,_=tree.query(aligned,workers=-1)
    # A similarity fit is a diagnostic; output CAD keeps the official dimensions.
    from scipy.optimize import least_squares
    idx=tree.query(aligned,workers=-1)[1]
    good=dist<np.quantile(dist,.9)
    scale=float(np.sum(aligned[good]*target[idx[good]])/np.sum(aligned[good]**2))
    report={'scan_to_reference_row_rotation':r.tolist(),'translation':t.tolist(),
        'nearest_sample_distance_percentiles':np.percentile(dist,[50,90,95,99,100]).tolist(),
        'trimmed_90_percent_rmse':float(np.sqrt(np.mean(dist[dist<=np.quantile(dist,.9)]**2))),
        'diagnostic_scale':scale,'reference_span':ref.extents.tolist(),
        'reference_bounds':ref.bounds.tolist(),'reference_volume':float(ref.volume),
        'note':'Distances are to dense sampled reference surface and reference vertices, not exact triangle distances.'}
    np.savez_compressed(OUT/'Boat_aligned.npz',vertices=aligned,faces=f)
    (OUT/'boat_registration.json').write_text(json.dumps(report,indent=2))
    plot('Boat_aligned',aligned,None)
    print(json.dumps(report),flush=True)
