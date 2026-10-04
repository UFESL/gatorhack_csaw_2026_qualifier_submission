"""Produce final revised CAD from the measured sections and Box surface trends."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / 'deps'))
import csv
import json
import numpy as np
import trimesh
from manifold3d import Manifold, Mesh
from audit_meshes import write_ply
from build_models import cylinder_between, slanted_cylinder, mesh_stats

ROOT = Path(__file__).resolve().parent.parent
AN = ROOT / 'analysis'
OUT = ROOT / 'Team_Name_Submission'
CAD = OUT / 'CAD'
DATA = json.loads((OUT / 'Measurements/Dimension_Measurements.json').read_text(encoding='utf8'))


def above_plane(normal, offset, extent=240):
    normal = np.asarray(normal)
    box = trimesh.creation.box(extents=[extent, extent, extent])
    box.apply_translation([0, 0, extent / 2])
    rotation = trimesh.geometry.align_vectors([0, 0, 1], normal)
    box.apply_transform(rotation)
    box.apply_translation([0, 0, offset / normal[2]])
    return box


def slanted_cone(radius0, slope, normal, offset, sections=192):
    theta = np.arange(sections) * 2 * np.pi / sections
    cs = np.column_stack((np.cos(theta), np.sin(theta)))
    normal = np.asarray(normal)
    lateral = cs @ normal[:2]
    z = (offset - radius0 * lateral) / (normal[2] + slope * lateral)
    radius = radius0 + slope * z
    vertices = np.vstack((np.column_stack((radius0 * cs, np.zeros(sections))),
                          np.column_stack((radius[:, None] * cs, z)),
                          [0, 0, 0], [0, 0, offset / normal[2]]))
    faces = []
    for i in range(sections):
        j = (i + 1) % sections
        faces.extend([[i, j, sections + j], [i, sections + j, sections + i],
                      [2 * sections, j, i], [2 * sections + 1, sections + i, sections + j]])
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    assert mesh.is_volume
    return mesh


def tower():
    data = DATA['Tower']; angles = (np.arange(72) + .5) * 5
    radius0 = data['baseline_diameter_mm'] / 2
    height = data['fitted_cap_separation_mm']
    raw = {}
    with (OUT / 'Measurements/Tower_angular_radius_grid.csv').open(newline='', encoding='utf8') as stream:
        for row in csv.DictReader(stream):
            z = float(row['z_mm']); raw.setdefault(z, np.full(72, np.nan))
            j = int(round((float(row['angle_deg']) - 2.5) / 5))
            if row['radius_mm']:
                raw[z][j] = float(row['radius_mm'])
    zs = [0.0]; rings = [np.full(72, radius0)]; missing = []
    for row in data['sections']:
        z = row['z_mm']
        if z < .5 or z > 23.5 or row['angular_coverage_percent'] < 70:
            continue
        rr = raw[z]; observed = np.isfinite(rr)
        # Interpolate only around the circumference, periodically. The input
        # angle medians already suppress small triangulation sampling spikes.
        completed = np.interp(angles, angles[observed], rr[observed], period=360)
        missing.append({'z_mm': z, 'missing_of_72_angular_bins': int((~observed).sum())})
        zs.append(z); rings.append(completed)
    zs.append(height); rings.append(np.full(72, radius0))
    zs = np.array(zs); rings = np.array(rings)
    theta = np.radians(angles)
    vertices = np.stack((rings * np.cos(theta), rings * np.sin(theta),
                         np.broadcast_to(zs[:, None], rings.shape)), axis=-1).reshape(-1, 3)
    centers = [len(vertices), len(vertices) + 1]
    vertices = np.vstack((vertices, [0, 0, 0], [0, 0, height]))
    faces = []
    for k in range(len(zs) - 1):
        for i in range(72):
            j = (i + 1) % 72; a = k * 72; b = (k + 1) * 72
            faces.extend([[a + i, a + j, b + j], [a + i, b + j, b + i]])
    last = (len(zs) - 1) * 72
    for i in range(72):
        j = (i + 1) % 72
        faces.extend([[centers[0], j, i], [centers[1], last + i, last + j]])
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    assert mesh.is_volume
    params = {'model': 'Measured angular-section loft', 'z_levels_mm': zs.tolist(),
              'angle_degrees_from_x_toward_y': angles.tolist(), 'radius_grid_mm': rings.tolist(),
              'section_count_including_completed_caps': len(zs), 'angular_samples_per_section': 72,
              'fitted_cap_separation_mm': height, 'reference_body_diameter_mm': 2 * radius0,
              'median_flare_peak_diameter_mm': data['flare']['median_peak_diameter_about_fixed_axis_mm'],
              'missing_bins_completed_by_periodic_linear_interpolation': missing,
              'assumptions': ['Unobserved angular bins use periodic linear interpolation.',
                              'Planar end caps at fitted Z=0 and Z=height use the baseline circle.',
                              'Adjacent 0.25-mm sections are joined by straight triangle patches.',
                              'Coordinates retain the shared-scan-unit assumption.']}
    # OpenSCAD polyhedron faces use clockwise order viewed from outside;
    # STL/Trimesh use the opposite convention. Reverse each face for SCAD.
    code = '// Revised Tower: measured angular loft, mm under shared-unit assumption.\n'
    code += '// Missing angular bins and end-cap completions are documented in revised_parameters.json.\n'
    code += '// Face ordering follows the OpenSCAD User Manual/Constructed Solids.\n'
    code += 'z_levels=' + json.dumps(zs.tolist()) + ';\nangles=' + json.dumps(angles.tolist()) + ';\n'
    code += 'radii=' + json.dumps(rings.tolist()) + ';\n'
    code += 'ring_points=[for(k=[0:len(z_levels)-1]) for(j=[0:len(angles)-1]) '
    code += '[radii[k][j]*cos(angles[j]),radii[k][j]*sin(angles[j]),z_levels[k]]];\n'
    code += f'points=concat(ring_points,[[0,0,0],[0,0,{height:.12f}]]);\n'
    code += 'faces=' + json.dumps(np.asarray(faces)[:, ::-1].tolist()) + ';\n'
    code += 'polyhedron(points=points,faces=faces,convexity=10);\n'
    (CAD / 'Tower_revised.scad').write_text(code, encoding='utf8')
    with (OUT / 'Measurements/Tower_revised_sections.csv').open('w', newline='', encoding='utf8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['z_mm', 'angle_degrees', 'radius_mm', 'observation_or_completion'])
        for i, z in enumerate(zs):
            for j, angle in enumerate(angles):
                reason = ('assumed cap endpoint' if i in [0, len(zs) - 1] else
                          'observed angular median' if np.isfinite(raw[z][j]) else 'periodic interpolation')
                writer.writerow([z, angle, rings[i, j], reason])
    return mesh, params


def box():
    data = DATA['Box']; old = data['rim_and_body_cad_parameters']
    walls = data['wall_trends']; rim = data['rim_plane']; floor = data['interior_floor_consensus']
    minimum_floor = 1.0
    outer0 = walls['outer']['radius_at_z_zero_mm']; outer_k = walls['outer']['radius_slope_mm_per_mm']
    inner0 = walls['inner']['radius_at_z_zero_mm']; inner_k = walls['inner']['radius_slope_mm_per_mm']
    n = np.array(rim['normal']); offset = rim['offset_mm']
    floor_n = np.array(floor['normal']); floor_offset = floor['plane_offset_mm']
    body = slanted_cone(outer0, outer_k, n, offset)
    solids = [body]
    inner_cone = trimesh.creation.cylinder(radius=inner0, height=100, sections=192)
    # Scale each ring according to its absolute height, preserving the planar caps.
    inner_cone.apply_translation([0, 0, 50])
    z = inner_cone.vertices[:, 2]
    scale = (inner0 + inner_k * z) / inner0
    inner_cone.vertices[:, :2] *= scale[:, None]
    assert inner_cone.is_volume
    floor_space = trimesh.boolean.intersection([above_plane(floor_n, floor_offset),
                                                above_plane([0, 0, 1], minimum_floor)], engine='manifold')
    cavity = trimesh.boolean.intersection([inner_cone, floor_space], engine='manifold')
    cutters = [cavity]
    for port in old['ports']:
        d = np.array(port['direction']); end = np.array(port['end_center'])
        solids.append(cylinder_between(11.5, end - 24 * d, end))
        bore = cylinder_between(10.0, end - 28 * d, end + .1 * d)
        # Preserve the bounded chamber floor inside the body. Full bores remain
        # outside the body; the unobserved transition is an explicit completion.
        above = trimesh.boolean.intersection([bore, floor_space], engine='manifold')
        outside = trimesh.boolean.difference([bore, body], engine='manifold')
        cutters.append(trimesh.boolean.union([above, outside], engine='manifold'))
    shell = trimesh.boolean.difference([trimesh.boolean.union(solids, engine='manifold'),
                                        trimesh.boolean.union(cutters, engine='manifold')], engine='manifold')
    additions, holes, bosses = [], [], []
    for boss in old['bosses']:
        xy = np.array(boss['center'])
        floor_z = max(minimum_floor, (floor_offset - floor_n[:2] @ xy) / floor_n[2])
        top = (offset - n[:2] @ xy) / n[2]
        additions.append(slanted_cylinder(boss['outer_radius'], xy, 0, n, offset))
        holes.append(cylinder_between(boss['opening_radius'], [*xy, boss['blind_hole_bottom']], [*xy, 60]))
        bosses.append({**boss, 'visible_floor_at_center_z_mm': float(floor_z),
                       'top_at_center_z_mm': float(top), 'height_above_floor_at_center_mm': float(top - floor_z),
                       'assumed_hole_depth_at_center_mm': float(top - boss['blind_hole_bottom'])})
    mesh = trimesh.boolean.difference([trimesh.boolean.union([shell] + additions, engine='manifold'),
                                       trimesh.boolean.union(holes, engine='manifold')], engine='manifold')
    manifold = Manifold(Mesh(np.asarray(mesh.vertices, dtype=np.float32), np.asarray(mesh.faces, dtype=np.uint32)))
    simple = manifold.simplify(1e-5).to_mesh()
    mesh = trimesh.Trimesh(vertices=np.asarray(simple.vert_properties)[:, :3],
                           faces=np.asarray(simple.tri_verts), process=False)
    params = {'model': 'Tapered body/chamber with bounded measured sloped floor',
              'outer_radius_at_z_zero_mm': outer0, 'outer_radius_slope': outer_k,
              'inner_radius_at_z_zero_mm': inner0, 'inner_radius_slope': inner_k,
              'rim_plane_normal': n.tolist(), 'rim_plane_offset_mm': offset,
              'rim_center_height_mm': rim['center_height_mm'],
              'floor_plane_normal': floor_n.tolist(), 'floor_plane_offset_mm': floor_offset,
              'floor_center_height_mm': floor['height_at_body_center_mm'],
              'assumed_minimum_floor_thickness_mm': minimum_floor,
              'floor_height_formula': 'Z_floor = max(1.0, (floor_offset - floor_nx*X - floor_ny*Y) / floor_nz)',
              'socket_outer_radius_mm': 11.5, 'socket_bore_radius_mm': 10.0,
              'ports': old['ports'], 'bosses': bosses,
              'assumptions': ['Minimum floor thickness 1.0 mm completes unobserved regions and is not a measured design dimension.',
                              'Socket bores are clipped to the bounded floor inside the body; the unseen transition is completed as a protected floor intersection.',
                              'Measured taper trends are extended across missing wall sections; original draft intent is unresolved.',
                              'Common outlet OD 23 mm and bore 20 mm remain inferred.',
                              'First boss opening uses symmetry; both hole bottoms stay at assumed Z=7 mm.',
                              'No original fillet radius or manufacturing tolerance is asserted.']}
    code = '// Revised Box: tapered walls and bounded measured floor. Units assumed mm.\n$fn=192;\n'
    for key, value in [('outer_r0', outer0), ('outer_k', outer_k), ('inner_r0', inner0), ('inner_k', inner_k),
                       ('rim_h', rim['center_height_mm']), ('rim_n', n.tolist()), ('floor_h', floor['height_at_body_center_mm']),
                       ('floor_n', floor_n.tolist()), ('floor_min', minimum_floor)]:
        code += key + '=' + json.dumps(value) + ';\n'
    code += 'ports=' + json.dumps([[p['start_center'], p['end_center']] for p in old['ports']]) + ';\n'
    code += 'bosses=' + json.dumps([[*b['center'], b['outer_radius'], b['opening_radius'], b['blind_hole_bottom']] for b in old['bosses']]) + ';\n'
    code += '''
module tube_between(a,b,r) {
 d=b-a; translate(a) rotate(a=acos(d[2]/norm(d)),v=[-d[1],d[0],0]) cylinder(r=r,h=norm(d));
}
module above_plane(n,h) {
 translate([0,0,h]) rotate(a=acos(n[2]),v=[-n[1],n[0],0]) translate([-120,-120,0]) cube([240,240,240]);
}
module body() {
 difference() { cylinder(r1=outer_r0,r2=outer_r0+60*outer_k,h=60); above_plane(rim_n,rim_h); }
}
module floor_space() {
 intersection() { above_plane(floor_n,floor_h); translate([-120,-120,floor_min]) cube([240,240,240]); }
}
module full_bore(p) {
 d=(p[1]-p[0])/norm(p[1]-p[0]); tube_between(p[1]-28*d,p[1]+.1*d,10);
}
module protected_bore(p) {
 union() {
  intersection() { full_bore(p); floor_space(); }
  difference() { full_bore(p); body(); }
 }
}
module cavity() {
 intersection() {
  cylinder(r1=inner_r0,r2=inner_r0+100*inner_k,h=100);
  floor_space();
 }
}
difference() {
 union() {
  difference() {
   union() {
    body();
    for(p=ports) tube_between(p[0],p[1],11.5);
   }
   cavity();
   for(p=ports) protected_bore(p);
  }
  for(b=bosses) difference() { translate([b[0],b[1],0]) cylinder(r=b[2],h=60); above_plane(rim_n,rim_h); }
 }
 for(b=bosses) translate([b[0],b[1],b[4]]) cylinder(r=b[3],h=60);
}
'''
    (CAD / 'Box_revised.scad').write_text(code, encoding='utf8')
    return mesh, params


def validate_export(name, mesh):
    stats = mesh_stats(mesh)
    assert stats['watertight'] and stats['consistent_winding'] and stats['positive_volume']
    assert stats['boundary_edges'] == stats['nonmanifold_edges'] == stats['degenerate_faces'] == 0
    assert len(mesh.split(only_watertight=False)) == 1
    mesh.export(CAD / (name + '_revised.stl'))
    write_ply(CAD / (name + '_revised.ply'), mesh.vertices, mesh.faces)
    loaded = trimesh.load_mesh(CAD / (name + '_revised.stl'))
    assert loaded.is_volume and loaded.nondegenerate_faces(height=1e-10).all()
    stats['single_material_component'] = True; stats['stl_reimport_passed'] = True
    return loaded, stats


def verify_box_floor(mesh, params):
    """Probe the serialized material boundary away from the mounting bosses."""
    xy = np.array([[-15, 0], [-5, 0], [0, 0], [10, 0], [20, 0], [0, -12], [0, 12]], dtype=float)
    origins = np.column_stack((xy, np.full(len(xy), -10.)))
    directions = np.tile([0., 0., 1.], (len(xy), 1))
    locations, ray_indices, _ = mesh.ray.intersects_location(origins, directions, multiple_hits=True)
    n = np.array(params['floor_plane_normal'])
    records = []
    for i, point in enumerate(xy):
        hits = np.sort(locations[ray_indices == i, 2])
        expected = max(params['assumed_minimum_floor_thickness_mm'],
                       (params['floor_plane_offset_mm'] - n[:2] @ point) / n[2])
        passed = len(hits) == 2 and abs(hits[0]) < 1e-5 and abs(hits[1] - expected) < 1e-5
        assert passed, (point, hits, expected)
        records.append({'xy': point.tolist(), 'surface_hits_z': hits.tolist(),
                        'expected_floor_z': float(expected), 'pass': bool(passed)})
    return records


def compare(name, revised):
    scan = np.load(AN / (name + '_aligned.npz'))['vertices']
    rng = np.random.default_rng(2026)
    sample = scan[rng.choice(len(scan), 18000, replace=False)]
    candidates = {'initial': trimesh.load_mesh(CAD / (name + '_reconstructed.stl')), 'revised': revised}
    if name == 'Tower':
        candidates['median_revolve'] = trimesh.load_mesh(CAD / 'Tower_measured_profile.stl')
    result = {}
    details = {'sample_points': sample}
    for label, mesh in candidates.items():
        dd = []
        for start in range(0, len(sample), 600):
            dd.append(trimesh.proximity.closest_point(mesh, sample[start:start + 600])[1])
        d = np.concatenate(dd); details[label + '_distance'] = d
        record = {'sample_points': len(sample), 'rms_mm': float(np.sqrt(np.mean(d ** 2))),
                  'median_mm': float(np.median(d)), 'p95_mm': float(np.percentile(d, 95)),
                  'p99_mm': float(np.percentile(d, 99)), 'max_mm': float(d.max()),
                  'within_0_5_mm_percent': float(100 * np.mean(d <= .5)),
                  'within_1_mm_percent': float(100 * np.mean(d <= 1))}
        if name == 'Tower':
            region = (sample[:, 2] < 2) & (np.linalg.norm(sample[:, :2], axis=1) > 5.8)
        else:
            # Visible floor-patch region independent of model distance.
            region = (sample[:, 2] > 1) & (sample[:, 2] < 7) & (np.linalg.norm(sample[:, :2], axis=1) < 23)
        record['feature_region_count'] = int(region.sum())
        record['feature_region_rms_mm'] = float(np.sqrt(np.mean(d[region] ** 2)))
        result[label] = record
    np.savez_compressed(AN / (name + '_revised_comparison.npz'), **details)
    return {'same_sample_comparison': result,
            'rms_reduction_percent': float(100 * (1 - result['revised']['rms_mm'] / result['initial']['rms_mm'])),
            'distance_basis': 'Exact nearest triangles, same 18,000 original scan vertices per candidate, fixed seed 2026.',
            'limitations': 'One-way distances evaluate surviving scan agreement, not missing surfaces or original design intent.'}


def main():
    models, params = {}, {}
    for name, builder in [('Tower', tower), ('Box', box)]:
        mesh, par = builder()
        loaded, stats = validate_export(name, mesh)
        if name == 'Box':
            probes = verify_box_floor(loaded, par)
            (AN / 'revised_floor_probes.json').write_text(json.dumps(probes, indent=2), encoding='utf8')
            (OUT / 'Evidence/revised_floor_probes.json').write_text(json.dumps(probes, indent=2), encoding='utf8')
        comparisons = compare(name, loaded)
        params[name] = par; models[name] = {'geometry': stats, **comparisons}
        print(name, json.dumps(models[name]), flush=True)
    (CAD / 'revised_parameters.json').write_text(json.dumps(params, indent=2), encoding='utf8')
    (AN / 'revised_results.json').write_text(json.dumps(models, indent=2), encoding='utf8')
    (OUT / 'Evidence/revised_results.json').write_text(json.dumps(models, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
