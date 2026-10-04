"""Measure nonideal source geometry and write reproducible CAD dimension data."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / 'deps'))
import csv
import json
import numpy as np
from scipy.optimize import least_squares
import trimesh
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from fit_geometry import fit_plane_ransac
from audit_meshes import write_ply

ROOT = Path(__file__).resolve().parent.parent
AN = ROOT / 'analysis'
OUT = ROOT / 'Team_Name_Submission'
MEAS = OUT / 'Measurements'
MEAS.mkdir(exist_ok=True)
FITS = json.loads((AN / 'geometry_fits.json').read_text())
PARAM = json.loads((OUT / 'CAD/reconstruction_parameters.json').read_text())
plt.rcParams.update({'font.size': 9, 'axes.grid': True, 'grid.alpha': .2})


def save_csv(name, rows):
    with (MEAS / name).open('w', newline='', encoding='utf8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class Scan:
    def __init__(self, name):
        data = np.load(AN / (name + '_aligned.npz'))
        self.p = data['vertices']
        self.f = data['faces']
        self.tri = self.p[self.f]
        self.c = self.tri.mean(1)
        self.n = np.cross(self.tri[:, 1] - self.tri[:, 0], self.tri[:, 2] - self.tri[:, 0])
        self.n /= np.linalg.norm(self.n, axis=1)[:, None]
        self.zlo = self.tri[:, :, 2].min(1)
        self.zhi = self.tri[:, :, 2].max(1)
        original = np.load(AN / (name + '_scan.npz'))['vertices']
        frame = np.asarray(FITS[name]['basis'])
        origin = np.asarray(FITS[name]['origin'])
        error = np.max(np.abs((original - origin) @ frame - self.p))
        assert error < 1e-9
        self.frame = {'source_origin': origin.tolist(), 'basis_columns': frame.tolist(),
                      'row_vector_formula': 'local = (source - origin) @ basis',
                      'inverse_formula': 'source = local @ basis.T + origin',
                      'max_frame_reconstruction_error': float(error),
                      'source_vertex_bounds_local': [self.p.min(0).tolist(), self.p.max(0).tolist()],
                      'source_vertex_span': np.ptp(self.p, axis=0).tolist()}

    def section(self, z, face_filter=None):
        ids = np.flatnonzero((self.zlo < z) & (self.zhi > z))
        if face_filter is not None:
            ids = ids[face_filter[ids]]
        t = self.tri[ids]
        pieces = []
        for a, b in [(0, 1), (1, 2), (2, 0)]:
            va, vb = t[:, a], t[:, b]
            cross = (va[:, 2] - z) * (vb[:, 2] - z) < 0
            aa, bb = va[cross], vb[cross]
            fraction = (z - aa[:, 2]) / (bb[:, 2] - aa[:, 2])
            pieces.append(aa + fraction[:, None] * (bb - aa))
        if not any(len(x) for x in pieces):
            return np.empty((0, 3))
        return np.unique(np.round(np.vstack(pieces), 9), axis=0)


def angular_medians(points, center=(0, 0), bins=72):
    q = points[:, :2] - center
    radius = np.linalg.norm(q, axis=1)
    angle = np.mod(np.arctan2(q[:, 1], q[:, 0]), 2 * np.pi)
    labels = np.floor(angle * bins / (2 * np.pi)).astype(int)
    result = np.full(bins, np.nan)
    for i in range(bins):
        if (labels == i).any():
            result[i] = np.median(radius[labels == i])
    return result


def model_check(mesh):
    counts = np.bincount(mesh.edges_unique_inverse)
    record = {'watertight': bool(mesh.is_watertight),
              'consistent_winding': bool(mesh.is_winding_consistent),
              'boundary_edges': int((counts == 1).sum()),
              'nonmanifold_edges': int((counts > 2).sum()),
              'degenerate_faces': int((~mesh.nondegenerate_faces(height=1e-10)).sum()),
              'positive_volume': bool(mesh.volume > 0),
              'span_mm_assuming_shared_units': mesh.extents.tolist()}
    assert record['watertight'] and record['consistent_winding'] and record['positive_volume']
    assert record['boundary_edges'] == record['nonmanifold_edges'] == record['degenerate_faces'] == 0
    return record


def tower_measurements():
    scan = Scan('Tower')
    radius0 = FITS['Tower']['diameter'] / 2
    height = FITS['Tower']['height']
    z_values = np.r_[np.arange(.25, 23.51, .25), 23.75, 24.0]
    rows, grids = [], []
    side_faces = np.abs(scan.n[:, 2]) < .92
    for z in z_values:
        points = scan.section(float(z), side_faces)
        points = points[np.linalg.norm(points[:, :2], axis=1) > 5.3]
        if len(points) < 25:
            continue
        initial = angular_medians(points)
        valid = np.isfinite(initial)
        # Equal-angle sampling prevents dense scan patches dominating the fit.
        theta = (np.arange(72) + .5) * 2 * np.pi / 72
        equal = initial[valid, None] * np.column_stack((np.cos(theta[valid]), np.sin(theta[valid])))
        fit = least_squares(lambda x: np.linalg.norm(equal - x[:2], axis=1) - x[2],
                            [0, 0, radius0], loss='soft_l1', f_scale=.05).x
        rr = angular_medians(points, fit[:2])
        fixed = angular_medians(points)
        vals = rr[np.isfinite(rr)]
        diameters = rr + np.roll(rr, 36)
        opposed = diameters[np.isfinite(diameters)]
        row = {'z_mm': float(z), 'section_points': len(points),
               'angular_coverage_percent': float(100 * np.isfinite(rr).mean()),
               'circle_center_x_mm': float(fit[0]), 'circle_center_y_mm': float(fit[1]),
               'fitted_circle_diameter_mm': float(2 * fit[2]),
               'median_radius_from_fixed_axis_mm': float(np.nanmedian(fixed)),
               'fixed_axis_radius_p05_mm': float(np.nanpercentile(fixed, 5)),
               'fixed_axis_radius_p95_mm': float(np.nanpercentile(fixed, 95)),
               'opposed_width_min_mm': float(np.min(opposed)) if len(opposed) else None,
               'opposed_width_max_mm': float(np.max(opposed)) if len(opposed) else None,
               'opposed_width_spread_mm': float(np.ptp(opposed)) if len(opposed) else None,
               'angular_radius_residual_p95_mm': float(np.percentile(np.abs(vals - fit[2]), 95))}
        rows.append(row)
        grids.append(fixed)
    save_csv('Tower_sections.csv', rows)
    angular_rows = [{'z_mm': row['z_mm'], 'angle_deg': float((j + .5) * 5),
                     'radius_mm': float(grids[i][j]) if np.isfinite(grids[i][j]) else '',
                     'radial_deviation_from_baseline_mm': float(grids[i][j] - radius0) if np.isfinite(grids[i][j]) else ''}
                    for i, row in enumerate(rows) for j in range(72)]
    save_csv('Tower_angular_radius_grid.csv', angular_rows)
    reliable = [r for r in rows if r['angular_coverage_percent'] >= 85 and r['z_mm'] <= 23.5]
    peak = max((r for r in reliable if r['z_mm'] < 4), key=lambda r: r['median_radius_from_fixed_axis_mm'])
    bump = peak['median_radius_from_fixed_axis_mm'] - radius0
    partial_supported = [r for r in rows if r['angular_coverage_percent'] >= 70]
    band = [r['z_mm'] for r in partial_supported if r['z_mm'] < 4 and r['median_radius_from_fixed_axis_mm'] - radius0 > .10]
    half_band = [r['z_mm'] for r in partial_supported if r['z_mm'] < 4 and r['median_radius_from_fixed_axis_mm'] - radius0 >= bump / 2]
    peak_grid = grids[rows.index(peak)]
    valid = np.isfinite(peak_grid)
    angular_bump_coverage = float(100 * np.mean(peak_grid[valid] - radius0 > .10))
    bump_record = {'peak_section_z_mm': peak['z_mm'],
                   'median_peak_diameter_about_fixed_axis_mm': 2 * peak['median_radius_from_fixed_axis_mm'],
                   'median_radial_projection_above_baseline_mm': bump,
                   'peak_section_radius_p05_p95_mm': [peak['fixed_axis_radius_p05_mm'], peak['fixed_axis_radius_p95_mm']],
                   'sections_with_median_radial_excess_over_0_10_mm': band,
                   'sampled_half_height_band_mm': [min(half_band), max(half_band)],
                   'sampled_half_height_band_width_mm': max(half_band) - min(half_band),
                   'peak_covered_angles_with_radial_excess_over_0_10_mm_percent': angular_bump_coverage,
                   'threshold_note': 'Bands are sampled at 0.25 mm; boundaries are not interpolated. Incomplete lower edge limits the inferred full extent.',
                   'interpretation': 'End flare is measured geometry; its origin as intentional design, print deformation, damage or scan distortion is unresolved.'}
    # A secondary CAD option retains the median end flare. Circumferential
    # asymmetry remains in the angular CSV rather than being asserted as design.
    profile_sections = [r for r in rows if r['z_mm'] >= .5 and r['z_mm'] <= 23.5 and r['angular_coverage_percent'] >= 70]
    knots = [[r['median_radius_from_fixed_axis_mm'], r['z_mm']] for r in profile_sections]
    knots = [[radius0, 0.0]] + knots + [[radius0, height]]
    coverage_by_z = {r['z_mm']: r['angular_coverage_percent'] for r in rows}
    profile_rows = [{'z_mm': z, 'radius_mm': radius, 'diameter_mm': 2 * radius,
                     'angular_coverage_percent': coverage_by_z.get(z),
                     'basis': 'completed planar cap endpoint using baseline radius' if z in [0.0, height] else 'median of observed 5-degree angular bins; partial if coverage below 85%'}
                    for radius, z in knots]
    save_csv('Tower_revolve_profile.csv', profile_rows)
    polygon = np.array([[0, 0]] + knots + [[0, height], [0, 0]])
    mesh = trimesh.creation.revolve(polygon, sections=192)
    mesh.merge_vertices()
    if mesh.volume < 0:
        mesh.invert()
    check = model_check(mesh)
    cad = OUT / 'CAD'
    mesh.export(cad / 'Tower_measured_profile.stl')
    write_ply(cad / 'Tower_measured_profile.ply', mesh.vertices, mesh.faces)
    loaded = trimesh.load_mesh(cad / 'Tower_measured_profile.stl')
    model_check(loaded)
    code = '// Measured-profile alternative; units assumed mm. Retains median end flare.\n'
    code += '// Axisymmetry and planar cap completion are reconstruction choices. See Dimension_Analysis.pdf.\n'
    code += '$fn=192;\nprofile=' + json.dumps(polygon.tolist()) + ';\nrotate_extrude() polygon(points=profile);\n'
    (cad / 'Tower_measured_profile.scad').write_text(code, encoding='utf8')
    rng = np.random.default_rng(2026)
    sample = scan.p[rng.choice(len(scan.p), 18000, replace=False)]
    comparisons = {}
    for name, candidate in [('ideal_cylinder', trimesh.load_mesh(cad / 'Tower_reconstructed.stl')),
                            ('measured_profile', loaded)]:
        dd = []
        for start in range(0, len(sample), 600):
            dd.append(trimesh.proximity.closest_point(candidate, sample[start:start + 600])[1])
        dd = np.concatenate(dd)
        low = (sample[:, 2] < 2) & (np.linalg.norm(sample[:, :2], axis=1) > 5.8)
        comparisons[name] = {'same_sample_rms_mm': float(np.sqrt(np.mean(dd ** 2))),
                             'same_sample_p95_mm': float(np.percentile(dd, 95)),
                             'lower_end_side_sample_count': int(low.sum()),
                             'lower_end_side_rms_mm': float(np.sqrt(np.mean(dd[low] ** 2))),
                             'note': 'Same 18,000 scan vertices for both candidates. One-way distances cannot validate missing geometry.'}
    fig, axes = plt.subplots(1, 3, figsize=(14, 5), layout='constrained')
    z = np.array([r['z_mm'] for r in rows])
    median = np.array([r['median_radius_from_fixed_axis_mm'] for r in rows])
    p05 = np.array([r['fixed_axis_radius_p05_mm'] for r in rows])
    p95 = np.array([r['fixed_axis_radius_p95_mm'] for r in rows])
    for ax in axes[:2]:
        ax.plot(2 * median, z, color='#147c83', label='Median section diameter')
        ax.fill_betweenx(z, 2 * p05, 2 * p95, color='#147c83', alpha=.18, label='2 x angular radius P05-P95')
        ax.axvline(2 * radius0, color='#d57729', ls='--', label='Earlier ideal cylinder')
        ax.set_xlabel('Diameter / twice angular radius [mm, assumed]')
        ax.set_ylabel('Height above fitted lower cap [mm, assumed]')
    axes[0].set_title('Tower: measured profile'); axes[0].set_ylim(0, height + .2)
    axes[1].set_title('Lower-end flare detail'); axes[1].set_ylim(0, 4)
    for ax in axes[:2]:
        ax.set_xlim(12.0, 13.6)
    axes[1].annotate(f'Peak near Z={peak["z_mm"]:.2f}\nMedian radial excess {bump:.3f}',
                     (2 * peak['median_radius_from_fixed_axis_mm'], peak['z_mm']),
                     xytext=(12.25, 2.8), arrowprops={'arrowstyle': '->'}, fontsize=8)
    axes[0].legend(fontsize=7, loc='upper right')
    matrix = np.array(grids) - radius0
    im = axes[2].imshow(matrix, origin='lower', aspect='auto', extent=[0, 360, z.min(), z.max()],
                        cmap='coolwarm', vmin=-.3, vmax=.3)
    axes[2].set_title('Variation around circumference')
    axes[2].set_xlabel('Angle from local +X toward +Y [degrees]')
    axes[2].set_ylabel('Height Z [mm, assumed]')
    fig.colorbar(im, ax=axes[2], label='Radial deviation from baseline [mm]')
    fig.savefig(AN / 'Tower_dimension_profile.png', dpi=180); plt.close(fig)
    return {'coordinate_frame': scan.frame, 'baseline_diameter_mm': 2 * radius0,
            'fitted_cap_separation_mm': height, 'flare': bump_record,
            'section_spacing_mm': .25, 'angular_bin_width_degrees': 5,
            'sections': rows, 'revolve_profile': profile_rows,
            'profile_variant_topology': check, 'model_comparison': comparisons,
            'unresolved': ['Physical unit scale without shared-export assumption', 'Cause of the measured flare',
                           'Missing cap/edge surfaces', 'Whether circumferential asymmetry should be retained in design']}


def box_measurements():
    scan = Scan('Box'); par = PARAM['Box']; fit = FITS['Box']
    c, n = scan.c, scan.n
    r = np.linalg.norm(c[:, :2], axis=1)
    theta = np.arctan2(c[:, 1], c[:, 0])
    radial = np.sum(n[:, :2] * c[:, :2], axis=1) / np.maximum(r, 1e-9)
    away = np.abs(np.sin(2 * theta)) > .65
    for boss in par['bosses']:
        away &= np.linalg.norm(c[:, :2] - boss['center'], axis=1) > boss['outer_radius'] + 1
    walls = away & (r > 24) & (r < 34)
    selections = {'outer': walls & (radial > .75), 'inner': walls & (radial < -.75)}
    sections = []
    for z in np.arange(3, 26.1, 1):
        row = {'z_mm': float(z)}
        for key, mask in selections.items():
            points = scan.section(float(z), mask)
            if len(points) >= 10:
                radii = np.linalg.norm(points[:, :2], axis=1)
                row.update({key + '_points': len(points), key + '_median_radius_mm': float(np.median(radii)),
                            key + '_radius_p05_mm': float(np.percentile(radii, 5)),
                            key + '_radius_p95_mm': float(np.percentile(radii, 95))})
            else:
                row.update({key + '_points': len(points), key + '_median_radius_mm': None,
                            key + '_radius_p05_mm': None, key + '_radius_p95_mm': None})
        sections.append(row)
    save_csv('Box_wall_sections.csv', sections)
    floor = (n[:, 2] > .85) & (r < 23) & (c[:, 2] > 1) & (c[:, 2] < 7)
    fn, offset, inliers, rmse = fit_plane_ransac(c[floor], np.array([0., 0., 1.]), threshold=.18, iterations=400)
    floor_residual = c[floor] @ fn - offset
    inside = np.abs(floor_residual) < .18
    observed_floor = c[floor][inside]
    floor_y0 = observed_floor[np.abs(observed_floor[:, 1]) < 2]
    floor_record = {'normal': fn.tolist(), 'plane_offset_mm': float(offset),
                    'height_at_body_center_mm': float(offset / fn[2]),
                    'tilt_degrees_to_outer_bottom': float(np.degrees(np.arccos(fn[2]))),
                    'consensus_faces': inliers, 'candidate_faces': int(floor.sum()),
                    'consensus_rms_mm': rmse,
                    'all_candidate_abs_residual_p95_mm': float(np.percentile(np.abs(floor_residual), 95)),
                    'observed_consensus_xy_bounds_mm': [observed_floor[:, :2].min(0).tolist(), observed_floor[:, :2].max(0).tolist()],
                    'observed_consensus_z_range_mm': [float(observed_floor[:, 2].min()), float(observed_floor[:, 2].max())],
                    'observed_y0_strip_x_range_mm': [float(floor_y0[:, 0].min()), float(floor_y0[:, 0].max())],
                    'cad_planar_floor_height_mm': par['bottom_thickness'],
                    'basis': 'Independent local consensus plane through visible interior floor. Curvature/warp and partial coverage limit interpretation.'}
    normal = np.array(par['rim_plane_normal']); rim_offset = par['rim_center_height'] * normal[2]
    port_rows = []
    for port, pf in zip(par['ports'], fit['port_cylinder_fits']):
        end = np.array(port['end_center']); direction = np.array(port['direction'])
        a = np.dot(direction[:2], direction[:2]); b = -2 * np.dot(end[:2], direction[:2])
        cc = np.dot(end[:2], end[:2]) - par['outer_radius'] ** 2
        roots = np.roots([a, b, cc]); positive = [float(x.real) for x in roots if abs(x.imag) < 1e-8 and x.real >= 0]
        exposed = min(positive)
        record = {'port': port['axis'] + ('+' if port['sign'] > 0 else '-'),
                  'end_x_mm': float(end[0]), 'end_y_mm': float(end[1]), 'end_z_mm': float(end[2]),
                  'direction_x': float(direction[0]), 'direction_y': float(direction[1]), 'direction_z': float(direction[2]),
                  'inclination_degrees_to_bottom': float(np.degrees(np.arcsin(direction[2]))),
                  'centerline_length_outside_circular_body_mm': exposed,
                  'cad_stock_length_mm': 24.0, 'cad_bore_cutter_depth_mm': 28.0,
                  'cad_outer_diameter_mm': 23.0, 'cad_bore_diameter_mm': 20.0,
                  'raw_outer_cylinder_fit_diameter_mm': 2 * pf['outer_radius'],
                  'raw_inner_cylinder_fit_diameter_mm': 2 * pf['inner_radius'],
                  'outer_fit_inlier_points': pf['outer_inliers'], 'inner_fit_inlier_points': pf['inner_inliers'],
                  'end_plane_fit_rms_mm': pf['end_plane_rmse'],
                  'diameter_evidence': 'Common CAD diameters are inferred. Raw partial fits are diagnostic, not certified per-port dimensions.'}
        port_rows.append(record)
    save_csv('Box_ports.csv', port_rows)
    boss_rows = []
    for i, boss in enumerate(par['bosses']):
        xy = np.array(boss['center']); top = (rim_offset - xy @ normal[:2]) / normal[2]
        q = c[:, :2] - xy; rr = np.linalg.norm(q, axis=1)
        inward = np.sum(n[:, :2] * q, axis=1) / np.maximum(rr, 1e-9)
        bore = (rr < 3) & (rr > .3) & (inward < -.5) & (np.abs(n[:, 2]) < .75)
        record = {'boss': i + 1, 'center_x_mm': float(xy[0]), 'center_y_mm': float(xy[1]),
                  'cad_outer_diameter_mm': 2 * boss['outer_radius'], 'cad_opening_diameter_mm': 2 * boss['opening_radius'],
                  'cad_top_center_z_mm': float(top), 'cad_base_z_mm': par['bottom_thickness'],
                  'cad_height_at_center_mm': float(top - par['bottom_thickness']),
                  'cad_hole_bottom_z_mm': boss['blind_hole_bottom'],
                  'cad_hole_depth_at_center_mm': float(top - boss['blind_hole_bottom']),
                  'observed_bore_candidate_faces': int(bore.sum()),
                  'observed_bore_candidate_z_min_mm': float(c[bore, 2].min()) if bore.any() else None,
                  'observed_bore_candidate_z_max_mm': float(c[bore, 2].max()) if bore.any() else None,
                  'opening_basis': 'symmetry completion from boss 2' if i == 0 else 'fit to better-preserved upper opening',
                  'hole_depth_basis': 'Assumed Z=7; no continuous observed bore establishes blind depth or through-hole status.'}
        boss_rows.append(record)
    save_csv('Box_bosses.csv', boss_rows)
    features = [
        {'feature': 'body_outside_diameter', 'value_mm': 2 * par['outer_radius'], 'basis': 'fitted circular idealization'},
        {'feature': 'chamber_inside_diameter', 'value_mm': 2 * par['inner_radius'], 'basis': 'fitted circular idealization'},
        {'feature': 'radial_wall_thickness', 'value_mm': par['outer_radius'] - par['inner_radius'], 'basis': 'difference of CAD radii'},
        {'feature': 'cad_bottom_thickness', 'value_mm': par['bottom_thickness'], 'basis': 'median floor estimate used by existing CAD'},
        {'feature': 'new_floor_consensus_center_height', 'value_mm': floor_record['height_at_body_center_mm'], 'basis': 'independent visible-surface plane fit; different from flat CAD floor'},
        {'feature': 'rim_center_height', 'value_mm': par['rim_center_height'], 'basis': 'fitted slanted rim'},
        {'feature': 'rim_min_height_on_cad_body', 'value_mm': par['rim_center_height'] - par['outer_radius'] * np.linalg.norm(normal[:2]) / normal[2], 'basis': 'calculated from rim plane'},
        {'feature': 'rim_max_height_on_cad_body', 'value_mm': par['rim_center_height'] + par['outer_radius'] * np.linalg.norm(normal[:2]) / normal[2], 'basis': 'calculated from rim plane'}]
    save_csv('Box_features.csv', features)
    fig, axes = plt.subplots(1, 3, figsize=(14, 5), layout='constrained')
    for key, color in [('outer', '#147c83'), ('inner', '#d57729')]:
        zz = np.array([x['z_mm'] for x in sections if x[key + '_median_radius_mm'] is not None])
        vals = [x[key + '_median_radius_mm'] for x in sections if x[key + '_median_radius_mm'] is not None]
        axes[0].plot(2 * np.array(vals), zz, 'o-', color=color, label=key + ' observed sectors', ms=3)
        cone = fit[key + '_cone']
        axes[0].plot(2 * (cone['intercept'] + cone['slope'] * zz), zz, '--', color=color, label=key + ' trend fit')
    axes[0].set_xlabel('Diameter / twice sector radius [mm, assumed]'); axes[0].set_ylabel('Height Z [mm, assumed]')
    axes[0].set_title('Box wall profiles'); axes[0].legend(fontsize=7)
    x = np.linspace(-par['outer_radius'], par['outer_radius'], 100)
    rim_z = (rim_offset - normal[0] * x) / normal[2]
    floor_z = (offset - fn[0] * x) / fn[2]
    axes[1].plot(x, rim_z, label='Rim plane at Y=0')
    axes[1].plot(x, floor_z, ls=':', color='#d57729', label='Floor plane extrapolation')
    xs = np.linspace(floor_y0[:, 0].min(), floor_y0[:, 0].max(), 100)
    axes[1].plot(xs, (offset - fn[0] * xs) / fn[2], color='#d57729', label='Floor fit within observed X span')
    axes[1].axhline(par['bottom_thickness'], ls='--', color='#d57729', label='Existing CAD floor')
    axes[1].axhline(0, color='k', lw=1, label='Outer-bottom datum')
    axes[1].set_xlabel('X [mm, assumed]'); axes[1].set_ylabel('Z [mm, assumed]'); axes[1].set_title('Rim and floor measurements')
    axes[1].legend(fontsize=7)
    th = np.linspace(0, 2 * np.pi, 300)
    for rad in [par['outer_radius'], par['inner_radius']]:
        axes[2].plot(rad * np.cos(th), rad * np.sin(th), color='#147c83')
    for i, boss in enumerate(par['bosses']):
        xy = np.array(boss['center'])
        for rad in [boss['outer_radius'], boss['opening_radius']]:
            axes[2].plot(xy[0] + rad * np.cos(th), xy[1] + rad * np.sin(th), color='#d57729')
        axes[2].text(xy[0], xy[1] + 6, f'Boss {i+1}', ha='center')
    for p in port_rows:
        label = p['port']; end = np.array([p['end_x_mm'], p['end_y_mm']]); direction = np.array([p['direction_x'], p['direction_y']])
        start = end - 24 * direction
        axes[2].plot([start[0], end[0]], [start[1], end[1]], color='#233843')
        axes[2].plot(*end, 'ko', ms=3); axes[2].text(end[0], end[1], label)
    axes[2].set_aspect('equal'); axes[2].set_xlabel('X [mm, assumed]'); axes[2].set_ylabel('Y [mm, assumed]')
    axes[2].set_title('CAD feature coordinate map')
    fig.savefig(AN / 'Box_dimension_features.png', dpi=180); plt.close(fig)
    return {'coordinate_frame': scan.frame, 'body_features': features,
            'rim_plane': {'normal': normal.tolist(), 'offset_mm': float(rim_offset),
                          'center_height_mm': par['rim_center_height'],
                          'tilt_degrees': float(np.degrees(np.arccos(normal[2])))},
            'interior_floor_consensus': floor_record,
            'wall_trends': {key: {'radius_at_z_zero_mm': fit[key + '_cone']['intercept'],
                                  'radius_slope_mm_per_mm': fit[key + '_cone']['slope'],
                                  'apparent_draft_degrees': float(np.degrees(np.arctan(fit[key + '_cone']['slope']))),
                                  'all_selected_face_rms_mm': fit[key + '_cone']['rmse']}
                            for key in ['outer', 'inner']},
            'wall_sections': sections, 'ports': port_rows, 'bosses': boss_rows,
            'rim_and_body_cad_parameters': par,
            'unresolved': ['Independent physical unit scale', 'Original nominal dimensions and tolerances',
                           'True per-port diameters in missing regions', 'Blind versus through mounting holes and their depth',
                           'Original fillet/chamfer radii', 'Whether apparent taper, warp and uneven ports are design or distortion']}


def main():
    tower = tower_measurements()
    print('Tower flare', json.dumps(tower['flare']), flush=True)
    box = box_measurements()
    print('Box floor', json.dumps(box['interior_floor_consensus']), flush=True)
    result = {'units': 'Scan coordinate units interpreted as millimetres under the shared-export-unit assumption',
              'scale_basis': {'reference': 'Known 3DBenchy nominal 60 x 31 x 48 mm',
                              'boat_diagnostic_scale': json.loads((AN / 'boat_registration.json').read_text())['diagnostic_scale'],
                              'applied_tower_box_scale_factor': 1.0,
                              'qualification': 'No independent physical unit is encoded in Tower/Box PLY. Shared units with Boat are assumed.'},
              'method': 'Intersections with actual source triangles; equal-angle radius medians; robust local surface fits; explicit CAD completions.',
              'scatter_note': 'Percentile bands describe spatial scan variation, not manufacturing tolerances or statistical confidence intervals.',
              'Tower': tower, 'Box': box}
    (MEAS / 'Dimension_Measurements.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf8')
    print('Saved dimension measurements and optional Tower measured-profile CAD.', flush=True)


if __name__ == '__main__':
    main()
