"""Write a dimension-analysis PDF and a manual CAD reconstruction guide."""
from pathlib import Path
import json
import shutil
import fitz
from make_report import md_to_html

ROOT = Path(__file__).resolve().parent.parent
AN = ROOT / 'analysis'
OUT = ROOT / 'Team_Name_Submission'
DATA = json.loads((OUT / 'Measurements/Dimension_Measurements.json').read_text(encoding='utf8'))
TOWER = DATA['Tower']; BOX = DATA['Box']
PARAM = BOX['rim_and_body_cad_parameters']


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(str(v) for v in row) + ' |' for row in rows])


def number(v, decimals=3):
    return 'unobserved' if v is None else f'{v:.{decimals}f}'


def write_pdf(sections, filename='Dimension_Analysis.pdf', title='Tower and Box - Source Dimension Analysis and CAD Reconstruction Guide'):
    css = '''
    body { font-family: sans-serif; font-size: 9.2pt; line-height: 1.35; color: #243843; }
    h1 { font-size: 21pt; color: #147c83; margin-bottom: 10pt; }
    h2 { font-size: 15pt; color: #147c83; margin-bottom: 9pt; }
    h3 { font-size: 11pt; color: #147c83; margin-top: 10pt; margin-bottom: 5pt; }
    p { margin-top: 4pt; margin-bottom: 7pt; }
    table { border-collapse: collapse; width: 100%; font-size: 7.5pt; margin: 8pt 0; }
    td, th { border: 0.5pt solid #b5c3c9; padding: 3pt; text-align: left; }
    th { font-weight: bold; }
    pre { font-family: monospace; font-size: 7.7pt; white-space: pre-wrap; background-color: #f1f5f6; padding: 7pt; }
    code { font-family: monospace; font-size: 8pt; }
    li { margin-bottom: 3pt; }
    .caption { font-size: 7.4pt; color: #53656e; }
    a { color: #147c83; }
    '''
    temporary = AN / (Path(filename).stem.lower() + '_layout.pdf')
    writer = fitz.DocumentWriter(str(temporary))
    page_count = 0
    for section in sections:
        story = fitz.Story(html=md_to_html(section), user_css=css, archive=fitz.Archive(str(OUT)))
        more = True
        while more:
            device = writer.begin_page(fitz.Rect(0, 0, 595.276, 841.89))
            more, _ = story.place(fitz.Rect(44, 38, 551, 785))
            story.draw(device); writer.end_page(); page_count += 1
            assert page_count < 25
    writer.close()
    doc = fitz.open(stream=temporary.read_bytes(), filetype='pdf')
    for i, page in enumerate(doc):
        page.draw_line((44, 806), (551, 806), color=(.08, .49, .51), width=.5)
        page.insert_text((44, 822), 'Hack3D | Dimension analysis | mm under shared-scan-unit assumption | 2026-10-03', fontsize=7.2)
        page.insert_text((510, 822), f'{i+1}/{len(doc)}', fontsize=8)
    doc.set_metadata({'title': title,
                      'author': 'Team_Name', 'subject': 'Measured flare, dimensional profiles, CAD datums and qualified completions'})
    doc.save(OUT / filename, deflate=True)
    doc.close()
    print('Dimension analysis pages', page_count, flush=True)


def main():
    for name in ['Tower_dimension_profile.png', 'Box_dimension_features.png']:
        shutil.copy2(AN / name, OUT / 'Evidence' / name)
    flare = TOWER['flare']; floor = BOX['interior_floor_consensus']; rim = BOX['rim_plane']
    n = rim['normal']; fn = floor['normal']
    comparisons = TOWER['model_comparison']
    original_cad = json.loads((AN / 'reconstruction_validation.json').read_text())
    envelopes = []
    for name, measured in [('Tower', TOWER), ('Box', BOX)]:
        scan = measured['coordinate_frame']['source_vertex_span']
        cad = original_cad[name]['span_mm']
        envelopes.append([name, ' x '.join(number(x) for x in scan), ' x '.join(number(x) for x in cad)])
    sections = []
    sections.append(f'''# Tower and Box: dimension analysis

**Prepared:** October 3, 2026. This document supplements the reconstruction report and drawings. It records source-surface variation, the initial CAD comparisons, and the final revised Tower and Box models. The last five pages include the new models, all five result figures, exact final definitions and fit comparisons. Use `Tower_revised` and `Box_revised` for the final reconstructions.

### 1. Establish the scale and coordinate frames

All numerical lengths below are scan coordinate units interpreted as millimetres. The known Boat reference is nominally 60 x 31 x 48 mm and gives a diagnostic scale factor {DATA['scale_basis']['boat_diagnostic_scale']:.8f}. Tower and Box keep a scale factor of 1.0. This assumes all three files use the same export units; no independent physical unit is encoded in Tower or Box. A known physical measurement or scanner export setting is needed to establish their scale independently.

Tower's local Z follows the fitted cylinder axis, with Z=0 at the fitted lower cap. Box's local Z is normal to its outside-bottom plane, with Z=0 on that plane. X/Y define the port layout shown in the coordinate map. Rotation and translation preserve lengths. Origins and full rotation matrices are stored in `Measurements/Dimension_Measurements.json`.

```text
local_point = (source_point - source_origin) @ basis
source_point = local_point @ basis.T + source_origin
```

### 2. Measure the original triangles

Intersect actual source triangles with horizontal planes. Tower is sampled every 0.25 mm, using 72 angular bins of 5 degrees. Each bin stores a median observed radius, with missing angles left blank. Fit section circles using equal-angle samples to reduce the influence of dense scan patches. Box wall sections avoid outlet intersections and mounting bosses. Local plane and cylinder fits reduce the influence of outliers.

The dimension CSVs separate fitted source values from CAD completions. Percentile bands describe spatial variation, including distortion and scan noise. They are not manufacturing tolerances or statistical confidence intervals. Unknown nominal dimensions, fillet radii and hidden hole depths are not recoverable merely by displaying more decimals.

### 3. Distinguish envelopes from feature dimensions

{table(['Part', 'Original aligned vertex span X x Y x Z', 'Initial CAD span X x Y x Z'], envelopes)}

Source envelopes include noise, missing regions and the Tower flare. Feature-based dimensions below provide the sketch dimensions needed for CAD. `Tower_reconstructed` is the initial cylinder; `Tower_measured_profile` retains the axisymmetric median flare. `Box_reconstructed` is the initial flat-floor model. Final `Tower_revised` and `Box_revised` definitions and envelopes appear in the appended results.
''')
    sections.append(f'''## Tower: measured end flare and body variation

The source Tower is not a perfect cylinder. The lower end broadens around the circumference, then narrows toward the main body. The deviation map also records smaller angular and height-dependent changes.

![Original-triangle sections. Shading is twice the P05-P95 angular-radius range, not a tolerance. White map cells are unobserved angles.](Evidence/Tower_dimension_profile.png)

{table(['Quantity', 'Value / interpretation'], [
    ['Reference fitted body diameter', number(TOWER['baseline_diameter_mm']) + ' mm'],
    ['Fitted cap separation', number(TOWER['fitted_cap_separation_mm']) + ' mm'],
    ['Flare peak section Z', number(flare['peak_section_z_mm']) + ' mm above the lower-cap datum'],
    ['Median diameter at peak section', number(flare['median_peak_diameter_about_fixed_axis_mm']) + ' mm'],
    ['Median radial projection above baseline', number(flare['median_radial_projection_above_baseline_mm']) + ' mm'],
    ['Peak radial P05-P95', ' to '.join(number(x) for x in flare['peak_section_radius_p05_p95_mm']) + ' mm'],
    ['Sampled median excess >0.10 mm band', ' to '.join(number(x) for x in [min(flare['sections_with_median_radial_excess_over_0_10_mm']), max(flare['sections_with_median_radial_excess_over_0_10_mm'])]) + ' mm Z'],
    ['Peak angular bins above +0.10 mm', number(flare['peak_covered_angles_with_radial_excess_over_0_10_mm_percent'], 1) + '% of observed bins'],
])}

The band endpoints are 0.25-mm samples; they do not establish an exact fillet radius or flare start/end. Lower-cap edge coverage is incomplete, and radial asymmetry remains visible. The geometry supports an end flare, while its origin as intended design, manufacturing deformation, damage or scan distortion remains unresolved.
''')
    selected_z = [0, .5, .75, 1, 1.25, 1.5, 1.75, 2, 2.5, 3, 4, 8, 12, 16, 20, 23.5, TOWER['fitted_cap_separation_mm']]
    knots = TOWER['revolve_profile']
    selected = [min(knots, key=lambda r: abs(r['z_mm'] - z)) for z in selected_z]
    seen = set(); selected = [r for r in selected if not (r['z_mm'] in seen or seen.add(r['z_mm']))]
    rows = [[number(r['z_mm']), number(r['radius_mm']), number(r['diameter_mm']),
             'cap completion' if r['angular_coverage_percent'] is None else number(r['angular_coverage_percent'], 1) + '%'] for r in selected]
    sections.append(f'''## Tower: sketch dimensions and reconstruction choices

For the axisymmetric comparison retaining the median flare, create a sketch in a radial/height plane. Import all rows of `Measurements/Tower_revolve_profile.csv`, using radius as the horizontal sketch coordinate and Z as the vertical coordinate. Join successive points, close the profile to the axis at each end, and revolve it 360 degrees. The table below is an abbreviated view; the CSV contains every modelling knot. The final angular loft is defined in the appended revised results.

{table(['Z (mm)', 'Radius (mm)', 'Diameter (mm)', 'Observed angular coverage'], rows)}

The Z=0 and upper-cap endpoints use the fitted body radius to complete planar caps. Some near-end sections have less than 85% angular coverage; their partial medians are explicitly labelled in the CSV. The optional revolve is axisymmetric. It retains the circumferential median flare and diameter variation, while angular deviations remain available in `Tower_angular_radius_grid.csv`.

The final reconstruction uses section points `(r*cos(angle), r*sin(angle), Z)` and lofts through their angular shapes. `Tower_revised_sections.csv` gives the completed points' radii and labels. Missing bins use periodic linear interpolation; cap circles use the baseline radius. `Tower_sections.csv` also includes fitted circle centers and minimum/maximum observed opposed widths; those widths are approximate section chords, not a certified roundness measurement.

{table(['Same 18,000 source points', 'RMS, all points (mm)', 'RMS, lower-end side (mm)'], [
    ['Earlier ideal cylinder', number(comparisons['ideal_cylinder']['same_sample_rms_mm'], 4), number(comparisons['ideal_cylinder']['lower_end_side_rms_mm'], 4)],
    ['Measured-profile alternative', number(comparisons['measured_profile']['same_sample_rms_mm'], 4), number(comparisons['measured_profile']['lower_end_side_rms_mm'], 4)],
])}

The profile STL passes closed-topology, winding, nonmanifold-edge, degenerate-face and STL reimport checks. Agreement with observed points does not validate cap completion or establish the original design intent. Editable and exported alternatives are `CAD/Tower_measured_profile.scad`, `.stl`, and `.ply`.
''')
    feature_rows = [[x['feature'].replace('_', ' '), number(x['value_mm']), x['basis']] for x in BOX['body_features']]
    sections.append(f'''## Box: body, wall, floor and rim dimensions

The table below records the initial circular CAD dimensions and measured source features. Measured wall sections and fitted trends show departures from constant diameters. The final revised model uses the fitted taper trends described below. At low/high heights, scan coverage and intersections limit the available wall sectors.

![Measured wall profiles and CAD feature locations. The floor fit is solid only over the observed X range near Y=0; dotted parts are extrapolation.](Evidence/Box_dimension_features.png)

{table(['Feature', 'mm', 'Evidence / use'], feature_rows)}

The apparent outer/inner wall trends are `R_outer(Z)={BOX['wall_trends']['outer']['radius_at_z_zero_mm']:.6f}{BOX['wall_trends']['outer']['radius_slope_mm_per_mm']:+.6f}*Z` and `R_inner(Z)={BOX['wall_trends']['inner']['radius_at_z_zero_mm']:.6f}{BOX['wall_trends']['inner']['radius_slope_mm_per_mm']:+.6f}*Z`. Their apparent draft angles are {BOX['wall_trends']['outer']['apparent_draft_degrees']:.3f} and {BOX['wall_trends']['inner']['apparent_draft_degrees']:.3f} degrees. The source residuals are larger than much of this taper, so intentional draft is not established. Initial CAD used constant radii; revised CAD uses these trends. Full source-section values are in `Box_wall_sections.csv`.
''')
    sections.append(f'''## Box: sloped surfaces and coordinate definitions

The measured rim plane retained by CAD is:

```text
{n[0]:.9f}*X + {n[1]:.9f}*Y + {n[2]:.9f}*Z = {rim['offset_mm']:.9f}
Z_rim(X,Y) = (offset - nx*X - ny*Y) / nz
```

Its slope is {rim['tilt_degrees']:.3f} degrees relative to the outside-bottom datum. At X=Y=0, Z is {rim['center_height_mm']:.3f} mm. Use this plane to trim the body and bosses rather than assigning one height to every rim point.

An independent consensus fit to the visible inner floor gives:

```text
{fn[0]:.9f}*X + {fn[1]:.9f}*Y + {fn[2]:.9f}*Z = {floor['plane_offset_mm']:.9f}
```

Its central intercept is {floor['height_at_body_center_mm']:.3f} mm and its apparent slope is {floor['tilt_degrees_to_outer_bottom']:.3f} degrees. {floor['consensus_faces']:,} of {floor['candidate_faces']:,} selected faces support the plane within 0.18 mm; inlier RMS distance is {floor['consensus_rms_mm']:.3f} mm. The fitted patch's X/Y bounds are {floor['observed_consensus_xy_bounds_mm'][0]} to {floor['observed_consensus_xy_bounds_mm'][1]} mm. A bounding rectangle does not imply complete coverage inside it.

The initial CAD used a flat floor at Z=2.59 mm, derived from the earlier median estimate. This is a simplification, not a measured uniform thickness. The new plane describes a surviving patch; extrapolating it over the complete body can cross below the outside-bottom plane. The revised model resolves this using `Z_floor=max(1.0, Z_plane)`. The 1-mm minimum and socket-bore transition protecting it are explicit missing-geometry assumptions. The appended results show this completion, observed coverage and the actual exported mesh section.

All port end coordinates and boss centers on the next pages use this same Box datum. `Dimension_Measurements.json` contains the source-to-local transform so the measurements can be overlaid on the original PLY.
''')
    ports = BOX['ports']
    port_table = [[p['port'], number(p['end_x_mm']), number(p['end_y_mm']), number(p['end_z_mm']),
                   number(p['centerline_length_outside_circular_body_mm']), number(p['inclination_degrees_to_bottom'], 2)] for p in ports]
    direction_table = [[p['port'], number(p['direction_x'], 6), number(p['direction_y'], 6), number(p['direction_z'], 6),
                         number(p['end_plane_fit_rms_mm'])] for p in ports]
    diagnostic_table = [[p['port'], number(p['raw_outer_cylinder_fit_diameter_mm']), number(p['raw_inner_cylinder_fit_diameter_mm']),
                        p['outer_fit_inlier_points'], p['inner_fit_inlier_points']] for p in ports]
    sections.append(f'''## Box: four outlet measurements

Each port is defined by an end center E and an outward unit direction d. This retains unequal lengths, different heights and slight tilts rather than forcing four identical radial outlets.

{table(['Port', 'End X', 'End Y', 'End Z', 'Outside-body centerline length', 'Inclination (deg)'], port_table)}

Lengths are mm under the shared-unit assumption. The outside-body centerline length runs from the circular body's outer wall to the outlet end along its centerline. It is not the full stock length or every visible edge length at the curved intersection.

{table(['Port', 'Direction X', 'Direction Y', 'Direction Z', 'End-plane RMS (mm)'], direction_table)}

Both CAD versions use common outside diameter 23.00 mm and bore diameter 20.00 mm. Create the outside cylinder from `E-24*d` to `E`. Define the bore cutter of radius 10.00 from `E-28*d` to `E+0.1*d`. The initial version subtracts the full cutter. For revised CAD, clip its portion inside the body to space above the completed floor, then subtract; the outside portion retains its circular bore. The 24/28-mm lengths and hidden transition are Boolean overlap/completion choices; the body intersection defines the exposed socket length.

The partial-source cylinder fits below are diagnostics. Some hit imposed fit bounds or have poor/absent inlier support, so they must not be treated as independently recovered nominal diameters. The common diameters are inferred from the better surviving outlet surfaces.

{table(['Port', 'Raw outside fit D', 'Raw bore fit D', 'Outer inliers', 'Bore inliers'], diagnostic_table)}

X- outside fit reaches its upper radius bound; Y+ bore reaches its upper radius bound; Y- has zero bore inliers. `Box_ports.csv` records both these diagnostics and the explicit dimensions used by CAD. Port fillets, draft and hidden bore transitions remain unresolved.
''')
    bosses = BOX['bosses']
    boss_table = [[b['boss'], number(b['center_x_mm'], 2), number(b['center_y_mm'], 2), number(b['cad_outer_diameter_mm'], 2),
                  number(b['cad_opening_diameter_mm'], 2), number(b['cad_top_center_z_mm']), number(b['cad_height_at_center_mm'])] for b in bosses]
    depth_table = [[b['boss'], number(b['cad_hole_bottom_z_mm'], 2), number(b['cad_hole_depth_at_center_mm']), b['opening_basis']] for b in bosses]
    sections.append(f'''## Box: mounting bosses and manual CAD build order

{table(['Boss', 'Center X', 'Center Y', 'Outside D', 'Opening D', 'Top-center Z', 'Initial center height'], boss_table)}

Lengths are mm. The initial boss bases start at the flat floor, Z=2.59. Revised boss solids join the material below the new floor, with visible height measured from the varying floor; exact revised heights appear in the appended results. Tops are clipped by the rim plane, so height varies across each boss. The first partially missing opening was completed using the second opening diameter.

{table(['Boss', 'Assumed hole-bottom Z', 'CAD centerline depth', 'Opening basis'], depth_table)}

The Z=7 hole bottoms and corresponding depths are explicit CAD assumptions. Surviving bore fragments are discontinuous; the second boss has candidate bore faces near both the outer bottom and upper opening, but no continuous captured wall establishes a through bore. Blind/through status, countersinks and hidden depths remain unresolved. Use `Box_bosses.csv` for the definitions and observed ranges.

To reproduce the initial Box comparison model, follow this construction order:

- Create the outside circular body, radius 29.76, from Z=0 and trim its top with the rim plane.
- Join four outlet cylinders of radius 11.50 using their measured end centers and directions.
- Subtract the central chamber, radius 27.61, beginning at Z=2.59, and subtract the four radius-10.00 outlet bores.
- Add the two boss cylinders at their listed X/Y centers, starting at Z=2.59, and trim their tops to the same rim plane.
- Cut the two radius-1.85 mounting openings from the assumed Z=7.00 bottoms upward.
- Check that the material boundary is one connected closed solid, while the chamber and socket bores remain open functional cavities.

The initial implementation is `CAD/Box_reconstructed.scad`. For final CAD, use `Box_revised.scad` and `revised_parameters.json`: replace constant wall radii with the measured taper functions, subtract the chamber above `max(1, Z_plane)`, protect the internal floor from bore cutters, and join bosses to the varying-floor body. Their rim and assumed Z=7 hole bottoms remain as above. This defines a reproducible reconstruction without establishing missing fillets, nominal dimensions, tolerances or unseen holes.
''')
    sections.extend(json.loads((AN / 'revised_report_sections.json').read_text(encoding='utf8')))
    md = '\n\n'.join(sections)
    (OUT / 'Dimension_Analysis.md').write_text(md, encoding='utf8')
    write_pdf(sections)
    readme = '''# Dimension measurements

Read ../Dimension_Analysis.pdf for scale qualifications, datums, flare measurements, Box features and manual CAD steps.

All lengths are scan units interpreted as mm using the same-export-unit assumption supported by the Boat reference. Percentile bands describe scan variation, not manufacturing tolerances.

- Dimension_Measurements.json: complete qualified data, source coordinate transforms and topology/comparison checks.
- Tower_sections.csv: 0.25-mm sections, angular coverage, fitted circle centers/diameters and opposed-width variation.
- Tower_angular_radius_grid.csv: 5-degree radii for each section; blank cells are missing observations.
- Tower_revolve_profile.csv: every modelling knot for the optional median-profile revolve; cap endpoints are completed with the baseline radius.
- Tower_revised_sections.csv: final angular-loft radii at every Z/angle, with observation/interpolation/cap labels.
- Box_wall_sections.csv: sampled visible inner/outer wall sectors; blank fields are unobserved.
- Box_features.csv: initial CAD feature dimensions and the newly measured local floor intercept.
- Box_ports.csv: outlet centers/directions, inferred CAD diameters and unreliable partial-fit diagnostics.
- Box_bosses.csv: boss dimensions, sloped-top heights and explicit assumed hole depths.

Final CAD files are ../CAD/Tower_revised.* and ../CAD/Box_revised.*. Exact final sections and Box parameters are in ../CAD/revised_parameters.json. Tower uses periodic interpolation for unobserved angles and baseline-circle cap completion. Box follows measured taper and slope with an assumed 1-mm floor minimum and a floor-protecting bore transition.
Tower_measured_profile.* is the median-flare comparison; Tower_reconstructed.* and Box_reconstructed.* are the initial cylinder/flat-floor comparisons. ../Revised_Model_Results.pdf contains all five final figures and same-sample comparisons.
'''
    (OUT / 'Measurements/README.md').write_text(readme, encoding='utf8')


if __name__ == '__main__':
    main()
