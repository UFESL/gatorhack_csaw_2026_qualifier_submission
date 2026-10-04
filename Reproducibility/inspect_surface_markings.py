"""Render source-mesh surface clues without changing any source or CAD file."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / 'deps'))
import json
import numpy as np
import trimesh
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection

AN = Path(__file__).resolve().parent
ROOT = AN.parent


def projection(ax, vertices, faces, horizontal, vertical, title, colors=None):
    x, y = np.array(horizontal), np.array(vertical)
    view = np.cross(x, y)
    tri = vertices[faces]
    normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    normals /= np.maximum(np.linalg.norm(normals, axis=1)[:, None], 1e-12)
    centers = tri.mean(1)
    ids = np.flatnonzero(normals @ view > 1e-7)
    ids = ids[np.argsort(centers[ids] @ view)]
    points = np.stack((tri[ids] @ x, tri[ids] @ y), axis=-1)
    if colors is not None:
        rgb = colors[faces[ids]].mean(1) / 255.0
    else:
        light = view + .6 * x + .3 * y
        light = light / np.linalg.norm(light)
        intensity = np.clip(.35 + .58 * (normals[ids] @ light), .1, .95)
        # Recessed letter floors have the same normal as the base. Include
        # shallow height contrast so orthographic lighting retains the text.
        bottom = centers[ids, 2] < .8
        intensity[bottom] -= np.clip(centers[ids[bottom], 2], 0, .35) * 1.25
        intensity = np.clip(intensity, .1, .95)
        rgb = np.repeat(intensity[:, None], 3, axis=1)
    ax.add_collection(PolyCollection(points, facecolors=rgb, edgecolors=rgb,
                      linewidths=.04, antialiased=False, rasterized=True))
    vp = np.column_stack((vertices @ x, vertices @ y))
    low, high = vp.min(0), vp.max(0)
    margin = (high - low).max() * .035
    ax.set_xlim(low[0] - margin, high[0] + margin)
    ax.set_ylim(low[1] - margin, high[1] + margin)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title(title, fontsize=12, pad=10)


def main():
    boat = np.load(AN / 'Boat_aligned.npz')
    box = np.load(AN / 'Box_aligned.npz')
    reference = trimesh.load_mesh(AN / '3DBenchy_reference.stl')
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    projection(axes[0, 0], boat['vertices'], boat['faces'], [1, 0, 0], [0, -1, 0],
               'Boat source scan: underside lettering')
    projection(axes[0, 1], reference.vertices, reference.faces, [1, 0, 0], [0, -1, 0],
               'Official 3DBenchy reference: underside lettering')
    projection(axes[1, 0], box['vertices'], box['faces'], [1, 0, 0], [0, -1, 0],
               'Box source scan: outer bottom, original RGB', box['colors'])
    projection(axes[1, 1], box['vertices'], box['faces'], [1, 0, 0], [0, 1, 0],
               'Box source scan: open chamber, original RGB', box['colors'])
    fig.tight_layout()
    fig.savefig(AN / 'surface_markings.png', dpi=180)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.5))
    projection(axes[0], boat['vertices'], boat['faces'], [1, 0, 0], [0, -1, 0],
               'Boat source scan: underside lettering')
    projection(axes[1], reference.vertices, reference.faces, [1, 0, 0], [0, -1, 0],
               'Official 3DBenchy reference: CT3D.xyz')
    fig.tight_layout()
    fig.savefig(AN / 'Boat_surface_marking.png', dpi=180)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 7))
    theta = np.deg2rad(240)
    projection(ax, box['vertices'], box['faces'],
               [np.cos(theta), -np.sin(theta), 0], [-np.sin(theta), -np.cos(theta), 0],
               'Box source scan: outer-bottom percentage marking', box['colors'])
    fig.tight_layout()
    fig.savefig(AN / 'Box_surface_marking.png', dpi=200)
    plt.close(fig)
    clues = {
        'Boat': {'surface': 'underside', 'text': 'CT3D.xyz',
                 'evidence_image': 'surface_markings.png',
                 'reference_match': 'Same lettering in the original Creative Tools 3DBenchy STL',
                 'meaning': 'Original model branding and shallow first-layer calibration lettering'},
        'Box': {'surface': 'outer bottom', 'text': '30%',
                'evidence_image': 'Box_surface_marking.png',
                'encoding': 'Source PLY vertex RGB channels; visible surface annotation',
                'nominal_cenosphere_weight_percent': 30,
                'nominal_hdpe_weight_percent': 70,
                'basis': 'Weight-fraction interpretation inferred from main.pdf section 3.1 pilot study, HDPE30',
                'limitations': 'The marking gives no fraction basis by itself; wt.% is inferred from the linked paper, not a chemical assay.'}
    }
    (AN / 'surface_markings.json').write_text(json.dumps(clues, indent=2), encoding='utf8')
    print('Saved source-surface evidence images and clue record.')


if __name__ == '__main__':
    main()
