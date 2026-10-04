from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'deps'))
import json
import numpy as np
import trimesh

OUT=Path(__file__).resolve().parent
m=trimesh.load_mesh(OUT/'3DBenchy_reference.stl')
original_volume=float(m.volume)
original_faces=len(m.faces)
m.update_faces(m.nondegenerate_faces(height=1e-8))
m.update_faces(m.unique_faces())
m.remove_unreferenced_vertices()
counts=np.bincount(m.edges_unique_inverse)
boundary=m.edges_unique[counts==1]
directed=m.edges_sorted
mask=np.isin(m.edges_unique_inverse,np.flatnonzero(counts==1))
half=m.edges[mask]
next_vertex={int(a):int(b) for a,b in half}
assert len(next_vertex)==len(half), 'Boundary branches require a different repair'
unused=set(next_vertex)
loops=[]
while unused:
    start=min(unused);loop=[];a=start
    while a not in loop:
        loop.append(a);unused.remove(a);a=next_vertex[a]
    assert a==start
    loops.append(loop)
vertices=m.vertices.copy();faces=m.faces.copy();details=[]
for loop in loops:
    points=m.vertices[loop]
    # The reference has collinear T-junctions, not missing surface patches.
    # Split the adjacent long triangle edges at existing vertices. This avoids
    # closing a zero-area loop with zero-area triangles.
    axis=np.ptp(points,axis=0).argmax()
    coords=points[:,axis]
    for a,b in zip(loop,loop[1:]+loop[:1]):
        lo,hi=sorted((vertices[a,axis],vertices[b,axis]))
        middle=[loop[i] for i in np.argsort(coords) if lo+1e-10<coords[i]<hi-1e-10]
        if not middle: continue
        if vertices[a,axis]>vertices[b,axis]: middle=middle[::-1]
        fi=np.flatnonzero(np.any(faces==a,axis=1)&np.any(faces==b,axis=1))
        assert len(fi)==1
        index=int(fi[0]);third=next(int(x) for x in faces[index] if x not in (a,b))
        chain=[a]+middle+[b]
        replacement=np.asarray([[x,y,third] for x,y in zip(chain,chain[1:])])
        faces=np.vstack((np.delete(faces,index,axis=0),replacement))
    details.append({'boundary_vertices':len(loop),'span':np.ptp(points,axis=0).tolist(),
        'perimeter':float(np.linalg.norm(points-np.roll(points,-1,axis=0),axis=1).sum())})
repaired=trimesh.Trimesh(vertices=vertices,faces=faces,process=False)
assert repaired.is_watertight
assert repaired.is_winding_consistent
assert repaired.nondegenerate_faces(height=1e-10).all()
assert repaired.volume>0
repaired.export(OUT/'Boat_reference_clean.stl')
result={'source_faces':original_faces,'removed_degenerate_faces':original_faces-len(m.faces),
    'repaired_collinear_t_junctions':details,'final_vertices':len(repaired.vertices),'final_faces':len(repaired.faces),
    'watertight':bool(repaired.is_watertight),'winding_consistent':bool(repaired.is_winding_consistent),
    'original_volume':original_volume,'repaired_volume':float(repaired.volume),'bounds':repaired.bounds.tolist()}
(OUT/'boat_reference_repair.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
