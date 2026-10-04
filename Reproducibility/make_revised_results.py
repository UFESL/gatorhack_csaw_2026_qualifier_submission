"""Create comparison figures and the revised-model results report."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / 'deps'))
import json
import shutil
import numpy as np
import trimesh
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from make_drawings import project
from measure_dimensions import Scan
from make_dimension_report import table, number, write_pdf

ROOT = Path(__file__).resolve().parent.parent
AN = ROOT / 'analysis'
OUT = ROOT / 'Team_Name_Submission'
PARAM = json.loads((OUT / 'CAD/revised_parameters.json').read_text())
RESULT = json.loads((AN / 'revised_results.json').read_text())
DATA = json.loads((OUT / 'Measurements/Dimension_Measurements.json').read_text())
plt.rcParams.update({'font.size': 11, 'axes.titlesize': 13, 'axes.labelsize': 10, 'legend.fontsize': 8})
COLORS = {'initial': '#d57729', 'revised': '#147c83', 'median_revolve': '#805c9b'}


def save(fig, name):
    fig.savefig(AN / name, dpi=190, bbox_inches='tight')
    plt.close(fig)
    shutil.copy2(AN / name, OUT / 'Evidence' / name)


def overview():
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout='constrained')
    vx = np.array([.70710678, -.70710678, 0]); vy = np.array([.40824829, .40824829, .81649658])
    for j, name in enumerate(['Tower', 'Box']):
        mesh = trimesh.load_mesh(OUT / 'CAD' / (name + '_revised.stl'))
        project(axes[0, j], mesh, vx, vy, name + ' revised CAD', dim=False)
        project(axes[1, j], mesh, vx, vy, name + ': original scan points over revised CAD', dim=False)
        points = np.load(AN / (name + '_revised_comparison.npz'))['sample_points']
        axes[1, j].scatter(points @ vx, points @ vy, s=.8, alpha=.28, color='#c03b33', rasterized=True)
    fig.suptitle('Final revised models and surviving source geometry\nCoordinates use the same fitted local frames; source point gaps remain visible', fontsize=14)
    save(fig, 'Revised_models_overview.png')


def tower_figure():
    par = PARAM['Tower']; scan = Scan('Tower'); rings = np.array(par['radius_grid_mm'])
    z = np.array(par['z_levels_mm']); angle = np.radians(par['angle_degrees_from_x_toward_y'])
    fig, axes = plt.subplots(1, 3, figsize=(12, 5.3), layout='constrained')
    points = scan.p[::2]
    axes[0].scatter(points[:, 0], points[:, 2], s=.5, color='#a4aeb2', alpha=.5, rasterized=True, label='Original scan projection')
    xx = rings * np.cos(angle)
    axes[0].plot(xx.min(1), z, color=COLORS['revised'], label='Revised X envelope')
    axes[0].plot(xx.max(1), z, color=COLORS['revised'])
    r0 = par['reference_body_diameter_mm'] / 2
    for sign in [-1, 1]:
        axes[0].plot([sign * r0, sign * r0], [0, z[-1]], '--', color=COLORS['initial'], label='Initial cylinder' if sign == 1 else None)
    axes[0].set_xlabel('X [mm, assumed]'); axes[0].set_ylabel('Z [mm, assumed]')
    axes[0].set_title('Whole-height silhouette'); axes[0].legend(loc='upper right')
    theta = np.linspace(0, 2 * np.pi, 300)
    for ax, height in zip(axes[1:], [1.0, 12.0]):
        section = scan.section(height, np.abs(scan.n[:, 2]) < .92)
        section = section[np.linalg.norm(section[:, :2], axis=1) > 5.3]
        i = int(np.argmin(np.abs(z - height))); rr = rings[i]
        ax.scatter(section[:, 0], section[:, 1], s=5, color='#929ba0', label='Source section', rasterized=True)
        ax.plot(r0 * np.cos(theta), r0 * np.sin(theta), '--', color=COLORS['initial'], label='Initial cylinder')
        xy = np.column_stack((rr * np.cos(angle), rr * np.sin(angle)))
        xy = np.vstack((xy, xy[0]))
        ax.plot(xy[:, 0], xy[:, 1], color=COLORS['revised'], label='Revised angular section')
        ax.set_aspect('equal'); ax.set_xlabel('X [mm, assumed]'); ax.set_ylabel('Y [mm, assumed]')
        ax.set_title(f'Section at Z={height:.2f} mm'); ax.legend(loc='lower left')
    save(fig, 'Tower_revised_geometry.png')


def floor_height(x, y):
    p = PARAM['Box']; n = np.array(p['floor_plane_normal'])
    plane = (p['floor_plane_offset_mm'] - n[0] * x - n[1] * y) / n[2]
    return np.maximum(p['assumed_minimum_floor_thickness_mm'], plane)


def box_figure():
    par = PARAM['Box']; scan = Scan('Box'); c = scan.c; n = scan.n
    radius = np.linalg.norm(c[:, :2], axis=1)
    patch = (n[:, 2] > .85) & (radius < 23) & (c[:, 2] > 1) & (c[:, 2] < 7)
    points = c[patch]
    mesh = trimesh.load_mesh(OUT / 'CAD/Box_revised.stl')
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout='constrained')
    x = np.linspace(-27.6, 27.6, 300); floor_n = np.array(par['floor_plane_normal'])
    unbounded = (par['floor_plane_offset_mm'] - floor_n[0] * x) / floor_n[2]
    observed = points[np.abs(points[:, 1]) < .8]
    axes[0, 0].scatter(observed[:, 0], observed[:, 2], s=2, color='#7f898e', alpha=.4, label='Source patch near Y=0', rasterized=True)
    axes[0, 0].axhline(2.59, ls='--', color=COLORS['initial'], label='Initial flat floor')
    axes[0, 0].plot(x, unbounded, ':', color='#9a7370', label='Measured plane extrapolation')
    axes[0, 0].plot(x, floor_height(x, 0), color=COLORS['revised'], lw=2, label='Revised protected floor')
    axes[0, 0].axhline(0, color='k', lw=.7)
    axes[0, 0].set_xlabel('X at Y=0 [mm]'); axes[0, 0].set_ylabel('Z [mm]')
    axes[0, 0].set_title('Floor shape and completed minimum'); axes[0, 0].legend()
    zz = np.linspace(0, 30, 150)
    for key, color, old_r in [('outer', '#147c83', 29.76), ('inner', '#805c9b', 27.61)]:
        r0 = par[key + '_radius_at_z_zero_mm']; slope = par[key + '_radius_slope']
        axes[0, 1].plot(2 * (r0 + slope * zz), zz, color=color, label='Revised ' + key + ' trend')
        axes[0, 1].axvline(2 * old_r, color=color, ls='--', alpha=.6, label='Initial ' + key + ' D')
        rows = DATA['Box']['wall_sections']; rows = [r for r in rows if r[key + '_median_radius_mm'] is not None]
        axes[0, 1].scatter([2 * r[key + '_median_radius_mm'] for r in rows], [r['z_mm'] for r in rows],
                           s=12, color=color, marker='x', label='Observed ' + key + ' sectors')
    axes[0, 1].set_xlabel('Diameter / twice sector radius [mm]'); axes[0, 1].set_ylabel('Z [mm]')
    axes[0, 1].set_title('Measured wall trends used by revised CAD'); axes[0, 1].legend(fontsize=7)
    segments = trimesh.intersections.mesh_plane(mesh, [0, 1, 0], [0, 0, 0])
    axes[1, 0].add_collection(LineCollection(segments[:, :, [0, 2]], colors='#233843', linewidths=.7))
    axes[1, 0].plot(x, floor_height(x, 0), color=COLORS['revised'], lw=2, label='Protected interior floor')
    axes[1, 0].axhline(0, color=COLORS['initial'], ls='--', label='Outside-bottom datum')
    axes[1, 0].set_xlim(-34, 34); axes[1, 0].set_ylim(-3, 33); axes[1, 0].set_aspect('equal')
    axes[1, 0].set_xlabel('X [mm]'); axes[1, 0].set_ylabel('Z [mm]')
    axes[1, 0].set_title('Actual revised mesh section at Y=0'); axes[1, 0].legend(fontsize=7)
    grid = np.linspace(-27.5, 27.5, 120); xx, yy = np.meshgrid(grid, grid)
    zz = floor_height(xx, yy); zz[xx ** 2 + yy ** 2 > 27.5 ** 2] = np.nan
    cf = axes[1, 1].contourf(xx, yy, zz, levels=np.linspace(1, 5.6, 15), cmap='viridis', alpha=.7)
    sampled = points[::40]
    axes[1, 1].scatter(sampled[:, 0], sampled[:, 1], s=2, color='k', alpha=.65, label='Observed floor-patch samples')
    axes[1, 1].contour(xx, yy, (par['floor_plane_offset_mm'] - floor_n[0] * xx - floor_n[1] * yy) / floor_n[2],
                       levels=[1], colors='#d57729', linewidths=2)
    axes[1, 1].set_aspect('equal'); axes[1, 1].set_xlabel('X [mm]'); axes[1, 1].set_ylabel('Y [mm]')
    axes[1, 1].set_title('Completed floor map; 1-mm boundary in orange'); axes[1, 1].legend(fontsize=7)
    fig.colorbar(cf, ax=axes[1, 1], label='Revised floor Z [mm]')
    save(fig, 'Box_revised_floor_and_walls.png')


def features_figure():
    par = PARAM['Box']; mesh = trimesh.load_mesh(OUT / 'CAD/Box_revised.stl')
    fig, axes = plt.subplots(1, 3, figsize=(12, 5.5), layout='constrained')
    project(axes[0], mesh, [1, 0, 0], [0, 1, 0], 'Box plan: outlet and boss positions', dim=False)
    for p in par['ports']:
        e = p['end_center']; label = p['axis'] + ('+' if p['sign'] > 0 else '-')
        axes[0].plot(e[0], e[1], 'o', color='#d57729', ms=4)
        axes[0].text(e[0], e[1], ' ' + label, color='#d57729', fontsize=11)
    for i, b in enumerate(par['bosses']):
        xy = b['center']; axes[0].plot(*xy, 'o', color='#b33f3f', ms=4)
        axes[0].text(xy[0], xy[1] + 6, f'B{i+1}', color='#b33f3f', ha='center')
    for i, (ax, boss) in enumerate(zip(axes[1:], par['bosses'])):
        cx, cy = boss['center']; seg = trimesh.intersections.mesh_plane(mesh, [0, 1, 0], [0, cy, 0])
        pts = seg[:, :, [0, 2]].copy(); pts[:, :, 0] -= cx
        ax.add_collection(LineCollection(pts, colors='#233843', linewidths=.9))
        u = np.linspace(-6, 6, 80); x = cx + u
        ax.plot(u, floor_height(x, cy), color='#147c83', label='Floor at boss')
        ax.axhline(7, color='#b33f3f', ls='--', label='Assumed hole-bottom Z=7')
        ax.set_xlim(-6, 6); ax.set_ylim(0, 32)
        ax.set_xlabel('X relative to boss center [mm]'); ax.set_ylabel('Z [mm]')
        ax.set_title(f'B{i+1}: actual mesh section through center')
        ax.legend(fontsize=7, loc='upper right')
    save(fig, 'Box_revised_feature_locations.png')


def errors_figure():
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout='constrained')
    for j, name in enumerate(['Tower', 'Box']):
        data = np.load(AN / (name + '_revised_comparison.npz'))
        labels = ['initial', 'revised'] + (['median_revolve'] if name == 'Tower' else [])
        for label in labels:
            dd = np.sort(data[label + '_distance']); percent = 100 * (np.arange(len(dd)) + 1) / len(dd)
            axes[0, j].plot(dd, percent, color=COLORS[label], label=label.replace('_', ' '))
        axes[0, j].set_xlim(0, .45 if name == 'Tower' else 3.2); axes[0, j].set_ylim(0, 100)
        axes[0, j].set_xlabel('Exact scan-point to nearest model-triangle distance [mm]')
        axes[0, j].set_ylabel('Cumulative sample percentage')
        axes[0, j].set_title(name + ': same-sample error distributions'); axes[0, j].legend(loc='lower right')
        p = data['sample_points']; d = data['revised_distance']; a, b = (0, 2) if name == 'Tower' else (0, 1)
        vmax = .2 if name == 'Tower' else 1.5
        image = axes[1, j].scatter(p[:, a], p[:, b], c=d, cmap='viridis', vmin=0, vmax=vmax,
                                    s=2, rasterized=True, alpha=.85)
        axes[1, j].set_aspect('equal'); axes[1, j].set_xlabel('XYZ'[a] + ' [mm]'); axes[1, j].set_ylabel('XYZ'[b] + ' [mm]')
        axes[1, j].set_title(name + f': revised distance map (colors clipped at {vmax:g} mm)')
        fig.colorbar(image, ax=axes[1, j], label='Distance [mm]')
    save(fig, 'Revised_fit_error_distributions.png')


def document():
    sections = []
    comp_rows = []
    for name in ['Tower', 'Box']:
        c = RESULT[name]['same_sample_comparison']
        comp_rows.append([name, number(c['initial']['rms_mm'], 4), number(c['revised']['rms_mm'], 4),
                          number(RESULT[name]['rms_reduction_percent'], 1) + '%', number(c['revised']['p95_mm'], 4)])
    sections.append(f'''# Revised Tower and Box model results

**Final CAD files:** `CAD/Tower_revised.stl`, `.ply`, `.scad` and `CAD/Box_revised.stl`, `.ply`, `.scad`. Boat continues to use its restored reference geometry. The earlier cylinder, median revolve and flat-floor Box are retained for comparison. All lengths assume the shared scan units are millimetres.

![Final solids and source points in their fitted local frames. The red points are original scan samples; missing source regions are not validated by an overlay.](Evidence/Revised_models_overview.png)

{table(['Part', 'Initial RMS (mm)', 'Revised RMS (mm)', 'RMS reduction', 'Revised P95 (mm)'], comp_rows)}

Compare exactly the same 18,000 source vertices per part against actual exported STL triangles, using seed 2026. Improvements show better agreement with captured geometry; they do not establish original design intent or recover hidden surfaces. Both revised STLs reimport as one closed material component with consistent winding, positive volume, zero open/nonmanifold edges and zero degenerate triangles.
''')
    par = PARAM['Tower']; geom = RESULT['Tower']['geometry']
    sections.append(f'''## Tower: retained flare and angular section variation

![Source projection and two horizontal sections. The angular loft follows observed section shapes rather than replacing them with circles.](Evidence/Tower_revised_geometry.png)

The final Tower connects {par['section_count_including_completed_caps']} sections with {par['angular_samples_per_section']} angles per section. Observed angular medians retain both the lower flare and circumferential variation. Unobserved bins are filled by periodic linear interpolation; the planar cap endpoints use the fitted baseline circle. Section coordinates and completion labels are in `Measurements/Tower_revised_sections.csv`; the exact radius grid is in `CAD/revised_parameters.json`.

{table(['Quantity', 'Revised value'], [
    ['Reference body diameter', number(par['reference_body_diameter_mm']) + ' mm'],
    ['Median flare peak diameter', number(par['median_flare_peak_diameter_mm']) + ' mm near Z=1'],
    ['Actual X/Y/Z envelope', ' x '.join(number(x) for x in geom['span_mm']) + ' mm'],
    ['Exported vertices / triangles', f'{geom["vertices"]:,} / {geom["faces"]:,}'],
    ['Geometric volume', number(geom['volume_mm3'], 1) + ' mm^3'],
])}

The median flare diameter differs from the maximum asymmetric envelope. The source dimensions are measured; interpolation, end completion and the unknown cause of the irregularities remain reconstruction qualifications. The editable OpenSCAD source defines the loft point/radius grid and polygon faces. Face ordering follows the [OpenSCAD user manual](https://en.wikibooks.org/wiki/OpenSCAD_User_Manual/Constructed_Solids). Actual STL geometry was validated; an OpenSCAD executable was not available for a separate compiler/render check.
''')
    par = PARAM['Box']; fn = par['floor_plane_normal']
    sections.append(f'''## Box: tapered walls and physically bounded floor

![Measured floor patch, completed floor, wall trends and an actual mesh section. The orange map line marks the assumed minimum-thickness transition.](Evidence/Box_revised_floor_and_walls.png)

The revised body and chamber follow `R_outer(Z)={par['outer_radius_at_z_zero_mm']:.6f}{par['outer_radius_slope']:+.6f}*Z` and `R_inner(Z)={par['inner_radius_at_z_zero_mm']:.6f}{par['inner_radius_slope']:+.6f}*Z`. The rim still uses the measured sloped plane. The protected floor is:

```text
Z_floor(X,Y) = max(1.0, ({par['floor_plane_offset_mm']:.9f}
                     - ({fn[0]:.9f})*X - ({fn[1]:.9f})*Y) / {fn[2]:.9f})
```

At the body center the floor is Z={par['floor_center_height_mm']:.3f} mm. The 1-mm lower bound is an explicit completion assumption in missing areas, not a recovered nominal thickness. Inside the body, low socket-bore cutters are clipped to this floor; outside the body, their full circular bores are retained. The unseen transition is a conservative completion. Body-plane taper trends are also extended through unobserved wall regions; their original design intent remains unknown.
''')
    b = PARAM['Box']; port_rows = [[p['axis'] + ('+' if p['sign'] > 0 else '-'), *[number(v, 3) for v in p['end_center']]] for p in b['ports']]
    boss_rows = [[i+1, number(p['visible_floor_at_center_z_mm']), number(p['top_at_center_z_mm']),
                  number(p['height_above_floor_at_center_mm']), number(p['assumed_hole_depth_at_center_mm'])] for i, p in enumerate(b['bosses'])]
    sections.append(f'''## Box: outlet locations, mounting bosses and hidden completions

![Final plan and two actual mounting-boss sections. The dashed red hole bottoms are assumed Z=7, not measured hidden surfaces.](Evidence/Box_revised_feature_locations.png)

{table(['Outlet', 'End X (mm)', 'End Y (mm)', 'End Z (mm)'], port_rows)}

Outlet directions, common OD 23 / bore 20 mm, unequal end positions and overlap lengths remain the documented measured/inferred definitions. The floor-protection transition is new; hidden bore transitions and original fillet radii remain unknown.

{table(['Boss', 'Floor at center Z', 'Top at center Z', 'Height above floor', 'Assumed hole depth'], boss_rows)}

Boss X/Y coordinates and outside/opening diameters remain the earlier fits. The first opening still uses symmetry and both hole bottoms remain at assumed Z=7. Boss solids join the material below the sloped floor; their visible height is measured from the new floor, not the old constant Z=2.59. The revised Box envelope is {' x '.join(number(x) for x in RESULT['Box']['geometry']['span_mm'])} mm. Full definitions are in `CAD/revised_parameters.json` and `Box_revised.scad`.
''')
    rows = []
    for name in ['Tower', 'Box']:
        for label in ['initial', 'revised']:
            x = RESULT[name]['same_sample_comparison'][label]
            rows.append([name + ' ' + label, number(x['rms_mm'], 4), number(x['median_mm'], 4),
                         number(x['p95_mm'], 4), number(x['p99_mm'], 4), number(x['within_1_mm_percent'], 2) + '%'])
    sections.append(f'''## Validation: numerical improvement and its limits

![Same-point cumulative error curves and source-point distance maps. Saturated map colors represent larger distances; table quantiles retain the full values.](Evidence/Revised_fit_error_distributions.png)

{table(['Model', 'RMS mm', 'Median mm', 'P95 mm', 'P99 mm', 'Within 1 mm'], rows)}

Both final material boundaries pass watertightness, winding, positive-volume, single-component, degenerate-face, nonmanifold-edge and actual STL reimport checks. Vertical probes through the Box away from bosses verify the implemented sloped floor and protected 1-mm completion against the intended formula; outside-bottom hits remain Z=0.

These are one-way distances to surviving source data. Features were fitted using the same scan, so this measures reconstruction agreement, not an independent manufacturing validation. The maximum Box distance remains approximately {RESULT['Box']['same_sample_comparison']['revised']['max_mm']:.3f} mm in poorly matched areas. Hidden hole depths, original fillets, missing angular regions and absolute units without the shared-export assumption remain unresolved. No physical print or dimensional inspection was performed.
''')
    (OUT / 'Revised_Model_Results.md').write_text('\n\n'.join(sections), encoding='utf8')
    (AN / 'revised_report_sections.json').write_text(json.dumps(sections, indent=2), encoding='utf8')
    write_pdf(sections, filename='Revised_Model_Results.pdf', title='Revised Tower and Box CAD Models - Geometry and Scan Comparison Results')


def main():
    overview(); tower_figure(); box_figure(); features_figure(); errors_figure(); document()
    print('Created five revised-model figures and results report.', flush=True)


if __name__ == '__main__':
    main()
