"""Read the complete challenge PLY files without discarding hidden annotations."""
from pathlib import Path
import hashlib
import json
import re

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'analysis'


def read_ply(path):
    annotations = []
    with path.open(encoding='utf-8') as f:
        header = []
        for lineno, line in enumerate(f, 1):
            header.append(line.rstrip())
            if line.strip().startswith('end_header'):
                if line.strip() != 'end_header':
                    annotations.append({'line': lineno, 'text': line.strip()})
                break
        nv = int(next(x for x in header if x.startswith('element vertex')).split()[2])
        nf = int(next(x for x in header if x.startswith('element face')).split()[2])
        props = [x for x in header[:next(i for i,x in enumerate(header) if x.startswith('element face'))] if x.startswith('property')]
        nprops = len(props)
        vertices = np.empty((nv, 3), dtype=np.float64)
        colors = np.empty((nv, 3), dtype=np.uint8) if nprops == 6 else None
        for i in range(nv):
            line = next(f)
            lineno += 1
            tokens = line.split()
            vertices[i] = [float(x) for x in tokens[:3]]
            if colors is not None:
                colors[i] = [int(x) for x in tokens[3:6]]
            if len(tokens) != nprops:
                annotations.append({'line': lineno, 'element': 'vertex', 'index': i, 'text': line.strip(), 'suffix': ' '.join(tokens[nprops:])})
        faces = np.empty((nf, 3), dtype=np.int32)
        for i in range(nf):
            line = next(f)
            lineno += 1
            tokens = line.split()
            assert tokens[0] == '3', (path, lineno, tokens[:4])
            faces[i] = [int(x) for x in tokens[1:4]]
            if len(tokens) != 4:
                annotations.append({'line': lineno, 'element': 'face', 'index': i, 'text': line.strip()})
        trailing = f.read()
        if trailing.strip():
            annotations.append({'line': lineno+1, 'element': 'trailing', 'text': trailing})
    return vertices, faces, colors, header, annotations


def metrics(v, f):
    assert np.isfinite(v).all()
    assert f.min() >= 0 and f.max() < len(v)
    edges = np.sort(np.vstack((f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]])), axis=1)
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    graph = coo_matrix((np.ones(len(unique)), (unique[:, 0], unique[:, 1])), shape=(len(v), len(v)))
    ncomp, labels = connected_components(graph, directed=False)
    triangles = v[f]
    area = np.linalg.norm(np.cross(triangles[:, 1]-triangles[:, 0], triangles[:, 2]-triangles[:, 0]), axis=1)/2
    lengths = np.linalg.norm(v[unique[:, 0]]-v[unique[:, 1]], axis=1)
    eigval, eigvec = np.linalg.eigh(np.cov(v.T))
    basis = eigvec[:, ::-1]
    pca = (v-v.mean(axis=0)) @ basis
    top = np.argsort(np.bincount(labels))[::-1][:10]
    comps = []
    for label in top:
        vi = np.flatnonzero(labels == label)
        fi = np.flatnonzero(labels[f[:, 0]] == label)
        comps.append({'label': int(label), 'vertices': len(vi), 'faces': len(fi), 'min': v[vi].min(axis=0).tolist(), 'max': v[vi].max(axis=0).tolist()})
    return {'vertices': len(v), 'faces': len(f), 'min': v.min(axis=0).tolist(), 'max': v.max(axis=0).tolist(),
        'span': np.ptp(v, axis=0).tolist(), 'pca_span': np.ptp(pca, axis=0).tolist(), 'pca_basis': basis.tolist(),
        'connected_components': ncomp, 'largest_components': comps, 'boundary_edges': int((counts==1).sum()),
        'nonmanifold_edges': int((counts>2).sum()), 'degenerate_faces': int((area<1e-10).sum()),
        'duplicate_faces': int(len(f)-len(np.unique(np.sort(f, axis=1), axis=0))),
        'edge_length_percentiles': np.percentile(lengths,[0,50,90,99,100]).tolist(),
        'surface_area': float(area.sum()), 'signed_volume': float(np.einsum('ij,ij->i',triangles[:,0],np.cross(triangles[:,1],triangles[:,2])).sum()/6)}, labels


def write_ply(path, v, f, colors=None):
    with path.open('w', newline='\n') as out:
        out.write('ply\nformat ascii 1.0\ncomment Sanitized challenge scan; coordinates retain source units.\n')
        out.write(f'element vertex {len(v)}\nproperty float x\nproperty float y\nproperty float z\n')
        if colors is not None:
            out.write('property uchar red\nproperty uchar green\nproperty uchar blue\n')
        out.write(f'element face {len(f)}\nproperty list uchar int vertex_indices\nend_header\n')
        if colors is None:
            np.savetxt(out, v, fmt='%.8g')
        else:
            np.savetxt(out, np.column_stack((v,colors)), fmt=['%.8g']*3+['%d']*3)
        np.savetxt(out, np.column_stack((np.full(len(f),3),f)),fmt='%d')


def render(name,v,f,c):
    rng = np.random.default_rng(42)
    idx = rng.choice(len(v), min(40000,len(v)),replace=False)
    fig = plt.figure(figsize=(15,5),layout='constrained')
    for i,(a,b) in enumerate([(0,1),(0,2),(1,2)]):
        ax = fig.add_subplot(1,3,i+1)
        ax.scatter(v[idx,a],v[idx,b],s=.3,c=c[idx]/255 if c is not None else v[idx,3-a-b],cmap='viridis' if c is None else None)
        ax.set_aspect('equal')
        ax.set_xlabel('XYZ'[a]); ax.set_ylabel('XYZ'[b]);ax.set_title(name)
    fig.savefig(OUT/f'{name}_scan_views.png',dpi=160)
    plt.close(fig)
    fig = plt.figure(figsize=(8,8))
    ax = fig.add_subplot(projection='3d')
    ax.scatter(*v[idx].T,s=.3,c=c[idx]/255 if c is not None else v[idx,2],cmap='viridis' if c is None else None)
    ax.set_box_aspect(np.ptp(v,axis=0));ax.view_init(20,-60)
    ax.set_xlabel('X');ax.set_ylabel('Y');ax.set_zlabel('Z');ax.set_title(name+' original scan')
    fig.savefig(OUT/f'{name}_scan_3d.png',dpi=140)
    plt.close(fig)


def main():
    summaries = {}
    for name in ['Boat','Tower','Box']:
        path = ROOT/f'{name}.ply'
        v,f,c,h,a = read_ply(path)
        m,labels = metrics(v,f)
        m.update({'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size, 'annotations': a,'header':h})
        summaries[name] = m
        np.savez_compressed(OUT/f'{name}_scan.npz',vertices=v,faces=f,colors=c if c is not None else np.empty((0,3)),labels=labels)
        write_ply(OUT/f'{name}_sanitized.ply',v,f,c)
        render(name,v,f,c)
        print(name,json.dumps(m),flush=True)
    (OUT/'audit.json').write_text(json.dumps(summaries,indent=2))


if __name__ == '__main__':
    main()
