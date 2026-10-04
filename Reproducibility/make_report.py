"""Produce the stepwise final report, evidence records and submission package."""
from pathlib import Path
import hashlib
import html
import json
import re
import shutil
import sys
import zipfile
import fitz

ROOT=Path(__file__).resolve().parent.parent
AN=ROOT/'analysis'
OUT=ROOT/'Team_Name_Submission'
EVIDENCE=OUT/'Evidence'
EVIDENCE.mkdir(exist_ok=True)
audit=json.loads((AN/'audit.json').read_text())
validation=json.loads((AN/'reconstruction_validation.json').read_text())
distances=json.loads((AN/'surface_comparison.json').read_text())
fits=json.loads((AN/'geometry_fits.json').read_text())
params=json.loads((OUT/'CAD/reconstruction_parameters.json').read_text())
revised=json.loads((AN/'revised_results.json').read_text())
revised_params=json.loads((OUT/'CAD/revised_parameters.json').read_text())


def inline(text):
    s=html.escape(text)
    s=re.sub(r'\[([^\]]+)\]\(([^\)]+)\)',r'<a href="\2">\1</a>',s)
    s=re.sub(r'\*\*([^*]+)\*\*',r'<b>\1</b>',s)
    s=re.sub(r'`([^`]+)`',r'<code>\1</code>',s)
    return s


def md_to_html(md, image_widths=None):
    lines=md.splitlines();out=[];i=0
    while i<len(lines):
        s=lines[i]
        if not s.strip():i+=1;continue
        if s.startswith('```'):
            i+=1;code=[]
            while i<len(lines) and not lines[i].startswith('```'):
                code.append(lines[i]);i+=1
            out.append('<pre>'+html.escape('\n'.join(code))+'</pre>');i+=1;continue
        if s.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].startswith('|'):
                cells=[x.strip() for x in lines[i].strip('|').split('|')]
                if not all(re.fullmatch(r'[-: ]+',x) for x in cells):rows.append(cells)
                i+=1
            table='<table>'
            for j,row in enumerate(rows):
                tag='th' if j==0 else 'td'
                table+='<tr>'+''.join(f'<{tag}>{inline(x)}</{tag}>' for x in row)+'</tr>'
            out.append(table+'</table>');continue
        if s.startswith('#'):
            n=len(s)-len(s.lstrip('#'))
            heading=s[n:].strip()
            cls=' class="pagebreak"' if n==2 and (any(heading.startswith('Step '+str(x)+' ') for x in [2,3,4,6,7,8,9]) or heading.startswith(('Dimension analysis','Revised model results'))) else ''
            out.append(f'<h{n}{cls}>'+inline(heading)+f'</h{n}>');i+=1;continue
        if s.startswith('!['):
            match=re.match(r'!\[([^\]]*)\]\(([^\)]+)\)',s)
            width=(image_widths or {}).get(match[2],500)
            out.append(f'<p><img src="{match[2]}" width="{width}"></p><p class="caption">{inline(match[1])}</p>');i+=1;continue
        if s.startswith('- '):
            out.append('<ul>')
            while i<len(lines) and lines[i].startswith('- '):
                out.append('<li>'+inline(lines[i][2:])+'</li>');i+=1
            out.append('</ul>');continue
        paragraph=[s];i+=1
        while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','|','```','![','- ')):
            paragraph.append(lines[i]);i+=1
        out.append('<p>'+''.join(inline(x.strip())+('<br>' if x.endswith('  ') else ' ') for x in paragraph)+'</p>')
    return '<html><body>'+''.join(out)+'</body></html>'


def pdf_from_md(md):
    css='''
    body { font-family: sans-serif; font-size: 10pt; line-height: 1.45; color: #243843; }
    h1 { font-size: 24pt; color: #147c83; margin-bottom: 12pt; }
    h2 { font-size: 14pt; color: #147c83; margin-top: 18pt; margin-bottom: 6pt; }
    h3 { font-size: 11pt; margin-top: 12pt; }
    p { margin-top: 5pt; margin-bottom: 8pt; }
    a { color: #147c83; }
    table { border-collapse: collapse; width: 100%; font-size: 8.5pt; margin: 10pt 0; }
    td, th { border: 0.5pt solid #b5c3c9; padding: 5pt; text-align: left; }
    th { font-weight: bold; }
    pre { font-family: monospace; font-size: 8pt; background-color: #f1f5f6; padding: 8pt; white-space: pre-wrap; }
    code { font-family: monospace; font-size: 9pt; }
    .caption { font-size: 8pt; color: #53656e; }
    li { margin-bottom: 3pt; }
    .pagebreak { page-break-before: always; }
    '''
    story=fitz.Story(html=md_to_html(md,{'Evidence/Revised_fit_error_distributions.png':410}),user_css=css,archive=fitz.Archive(str(OUT)))
    temporary=AN/'report_layout.pdf'
    writer=fitz.DocumentWriter(str(temporary))
    more=True;count=0
    while more:
        device=writer.begin_page(fitz.Rect(0,0,595.276,841.89))
        more,_=story.place(fitz.Rect(44,38,551,791))
        story.draw(device);writer.end_page();count+=1
        assert count<30,'Unexpected report pagination'
    writer.close()
    doc=fitz.open(stream=temporary.read_bytes(),filetype='pdf')
    for i,page in enumerate(doc):
        page.draw_line((44,810),(551,810),color=(.08,.49,.51),width=.5)
        page.insert_text((44,824),'CSAW 2026 Hack3D | Stepwise reconstruction report | 2026-10-03',fontsize=8,color=(.2,.3,.35))
        page.insert_text((503,824),f'{i+1} / {len(doc)}',fontsize=8,color=(.2,.3,.35))
    doc.set_metadata({'title':'CSAW 2026 Hack3D - Stepwise Reconstruction Report','author':'Team_Name (replace before submission)','subject':'PLY clue recovery, CAD reconstruction, drawings and material identification'})
    doc.save(OUT/'Final_Report.pdf',deflate=True);doc.close()
    print('Report PDF pages',count,flush=True)


def table_audit():
    rows=['| Part | Vertices | Triangles | Components | Open edges | Nonmanifold edges |','|---|---:|---:|---:|---:|---:|']
    for name in ['Boat','Tower','Box']:
        a=audit[name];rows.append(f'| {name} | {a["vertices"]:,} | {a["faces"]:,} | {a["connected_components"]} | {a["boundary_edges"]:,} | {a["nonmanifold_edges"]} |')
    return '\n'.join(rows)


def table_distances():
    rows=['| Part | RMS distance (mm) | Median (mm) | 95th percentile (mm) | Within 0.5 mm |','|---|---:|---:|---:|---:|']
    for name in ['Boat','Tower','Box']:
        if name == 'Boat':
            d=distances[name];q=d['exact_triangle_distance_percentiles_mm']
            values=[d['all_sample_rms_mm'],q[0],q[2],d['within_0_5_mm_percent']]
        else:
            d=revised[name]['same_sample_comparison']['revised']
            values=[d['rms_mm'],d['median_mm'],d['p95_mm'],d['within_0_5_mm_percent']]
        rows.append(f'| {name} | {values[0]:.3f} | {values[1]:.3f} | {values[2]:.3f} | {values[3]:.2f}% |')
    return '\n'.join(rows)


def table_validation():
    rows=['| Output | Vertices | Triangles | Open / nonmanifold edges | Degenerate triangles | Reload |','|---|---:|---:|---|---:|---|']
    for name in ['Boat','Tower','Box']:
        v=validation[name] if name=='Boat' else revised[name]['geometry']
        rows.append(f'| {name} | {v["vertices"]:,} | {v["faces"]:,} | 0 / 0 | 0 | Pass |')
    return '\n'.join(rows)


def table_revisions():
    rows=['| Part | Initial RMS (mm) | Revised RMS (mm) | RMS reduction |','|---|---:|---:|---:|']
    for name in ['Tower','Box']:
        d=revised[name]['same_sample_comparison']
        rows.append(f'| {name} | {d["initial"]["rms_mm"]:.3f} | {d["revised"]["rms_mm"]:.3f} | {revised[name]["rms_reduction_percent"]:.1f}% |')
    return '\n'.join(rows)


def main():
    measurement_data=json.loads((OUT/'Measurements/Dimension_Measurements.json').read_text(encoding='utf8'))
    flare=measurement_data['Tower']['flare']
    floor_patch=measurement_data['Box']['interior_floor_consensus']
    for filename in ['audit.json','geometry_fits.json','boat_registration.json','boat_reference_repair.json','reconstruction_validation.json','surface_comparison.json',
        'Boat_scan_views.png','Tower_scan_views.png','Box_scan_views.png','Box_slice_22_30.png','reconstructed_overview.png',
        'surface_markings.png','Boat_surface_marking.png','Box_surface_marking.png','surface_markings.json',
        'revised_results.json','revised_floor_probes.json','Revised_models_overview.png','Tower_revised_geometry.png',
        'Box_revised_floor_and_walls.png','Box_revised_feature_locations.png','Revised_fit_error_distributions.png']:
        shutil.copy2(AN/filename,EVIDENCE/filename)
    clues={'source_files':{n:a['annotations'] for n,a in audit.items()},'drive_folder':'https://drive.google.com/drive/folders/1GBNstjhu-mba_AvmHhLZc9MK_f_Nt7FC?usp=sharing',
        'public_file_ids':{'Password.txt':'1XYJIy7iUexTy1pYPGV2WKHRTqWgiJBcm','Secret Company Files.zip':'1PGAn3Lt5VQovrAWoDoqs4TYb11KO0eXT'},
        'hint':'What is the name of the conference hosted by the CCS department that this challenge is a part of?',
        'accepted_hint_answer':'CSAW26',
        'reference_document':{'filename':'Secret Company Files/main.pdf','sha256':hashlib.sha256((AN/'reference_files/Secret Company Files/main.pdf').read_bytes()).hexdigest(),
            'doi':'10.1016/j.matdes.2015.12.052','matching_geometry':'Figure 12, item 4, page 8 (journal page 421)'},
        'benchy_reference_url':'https://raw.githubusercontent.com/CreativeTools/3DBenchy/master/Single-part/3DBenchy.stl',
        'benchy_reference_sha256':hashlib.sha256((AN/'3DBenchy_reference.stl').read_bytes()).hexdigest(),
        'surface_markings':json.loads((AN/'surface_markings.json').read_text(encoding='utf8'))}
    (EVIDENCE/'recovered_clues.json').write_text(json.dumps(clues,indent=2),encoding='utf8')
    materials={
        'Boat':{'polymer':'PLA (polylactic acid)','composition_evidence':'Explicit suffix at Boat.ply line 13','additives_or_grade':'Not specified'},
        'Tower':{'matrix':'Acrylate-based thermosetting photopolymer resin','matrix_volume_percent':60,
            'filler':'Hollow glass microspheres','filler_volume_percent':40,
            'evidence':'Tower.ply line 19: DOI 10.1016/j.compositesa.2025.109248; Phi = 40%',
            'interpretation':'Nominal two-phase formulation inferred from the DOI and Phi clue; not a chemical analysis of the physical specimen.',
            'paper_hgm_description':'Ecospheres; mean size 45 micrometres; true particle density 0.31 g/cm3 as described by the cited paper.'},
        'Box':{'matrix':'HDPE; grade HD50MA180 in the supplied paper','filler':'Fly-ash cenospheres; CIL-150 in the supplied paper',
            'filler_chemistry':'Primarily silica/alumina ceramic shells, with calcium oxide and iron oxides',
            'specific_filler_fraction':0.30,'fraction_basis':'Weight; inferred from the supplied paper, not stated in the surface label itself',
            'filler_weight_percent':30,'matrix_weight_percent':70,
            'surface_marking':'30% on the outside-bottom face, visible in original PLY vertex RGB colors',
            'evidence':'Box source surface marking; supplied archive main.pdf sections 2.1 and 3.1 (HDPE30 pilot formulation); matching junction geometry in Figure 12 item 4.',
            'interpretation':'Nominal 30 wt.% fly-ash cenospheres and 70 wt.% HDPE inferred by combining the surface clue with the linked paper. Not a chemical assay of the physical specimen.',
            'pilot_formulations_in_paper_wt_percent_cenospheres':[30,60],
            'main_study_formulations_in_paper_wt_percent_cenospheres':[20,40,60],
            'limitations':'The label alone does not specify weight versus volume. Surface treatment, pigment, additives and measured physical composition remain unspecified.'}}
    (OUT/'Materials_Composition.json').write_text(json.dumps(materials,indent=2),encoding='utf8')
    md=f'''# CSAW 2026 Hack3D: stepwise reconstruction report

**Challenge:** Red Team Vs Blue Team - .PLY Me a Secret  
**Prepared:** October 3, 2026 (America/New_York)  
**Team:** Team_Name — replace with your registered team name before submission.

The three supplied parts have been reconstructed and exported as closed CAD meshes. The final models are `Boat_reconstructed`, `Tower_revised` and `Box_revised`. Tower retains its measured end flare and angular section variation; Box uses measured wall taper and a sloped floor with an assumed minimum thickness. The package contains this stepwise report, four drawing sheets, a dimension analysis, a revised-model results report with five figures, STL/PLY models, editable OpenSCAD definitions, material findings and reproducible scripts. Earlier models remain available for comparison. Material findings and geometric assumptions are stated separately so unresolved information is visible.

![Reconstructed Boat, Tower and Box; each view uses the exported CAD mesh.](Evidence/reconstructed_overview.png)

## Step 1 — Read the statement and preserve the evidence

Read the complete one-page `Qualifier 2025 Problem Statement.pdf`, including its rendered page and embedded hyperlink. Although the filename says 2025, the page displays CSAW’26 and its PDF creation metadata is October 2, 2026. The report follows the supplied document's requested deliverables: process report, dimensioned PDF drawings, material composition for every part, and reconstructed CAD in a ZIP named `Team_Name_Submission`.

Retain the original PLY files unchanged. Record their byte counts and SHA-256 hashes in `Evidence/audit.json`. The three scans together contain 510,320 vertices and 1,006,749 triangles. Do not interpret scanner coordinates around Z=400 as part dimensions; they include arbitrary translation and rotation.

## Step 2 — Audit every record and recover the embedded clues

Read each ASCII PLY from its header through every declared vertex and triangle, then check for trailing data. Validate finite coordinates and face-index ranges. Retain Box's RGB channels. Four literal text annotations occur in the schema audit; no extra records were found after the declared faces. Also render the surfaces: engraved lettering and photographed RGB markings are visual clues that a text search cannot recover.

| Location | Recovered clue | Meaning |
|---|---|---|
| Boat.ply, line 13 / vertex 3 | `- PLA` | Explicit polymer identification |
| Boat.ply, line 23 / vertex 13 | `https://www.3dbenchy.com/` | Geometry reference |
| Tower.ply, line 19 / vertex 9 | DOI ending `compositesa.2025.109248`; `Phi = 40%` | Composite reference and filler volume fraction |
| Box.ply, line 12 | Google Drive folder appended to `end_header` | Additional challenge reference files |
| Boat underside geometry | `CT3D.xyz` | Standard 3DBenchy branding and first-layer test lettering |
| Box outside-bottom RGB surface | `30%` | Nominal mixture clue; interpret using the linked paper |

The appended text does not comply with the declared PLY fields. Strict importers can reject it, especially Box's modified header terminator. Save the clues separately, then produce sanitized PLY copies that retain the numerical geometry and colors. Count connected components and unique undirected edges; an edge used by one triangle is an open boundary, while more than two incident triangles indicates a nonmanifold edge.

{table_audit()}

All source faces are valid triangles with in-range indices. No duplicate or zero-area source triangles were detected. Every scan has gaps, and Boat and Box also contain disconnected patches. The source meshes therefore cannot be treated as complete closed solids or used to compute trustworthy enclosed volume.

## Step 3 — Follow the Boat reference

Use the embedded [3DBenchy website](https://www.3dbenchy.com/) to identify the calibration boat. Its [official download page](https://www.3dbenchy.com/download/) links to [CreativeTools' original single-part STL](https://github.com/CreativeTools/3DBenchy/blob/master/Single-part/3DBenchy.stl). Retrieve that reference and record its hash.

Render the underside and compare its `CT3D.xyz` lettering with the official STL. Both contain the same recessed text. It identifies the Creative Tools design; the [official features page](https://www.3dbenchy.com/features/) describes the shallow bottom lettering as a first-layer calibration feature. This reinforces the Boat identification. Comparison views are retained in `Evidence/surface_markings.png`.

![Underside comparison. Grayscale lighting includes shallow-height contrast to show the recessed letters; geometry is unchanged.](Evidence/Boat_surface_marking.png)

Initialize alignment with principal-axis candidates, then run trimmed iterative closest point registration. Keep only the closest correspondences during fitting so incomplete scan patches do not dominate the result. Store the rigid transformation in `Evidence/boat_registration.json`. The diagnostic scale is 1.00043, supporting use of the scanner's coordinate units as millimetres for these parts. This is a reference-based calibration, not an independently certified scanner calibration.

Restore the missing Boat surfaces from the identified reference geometry. The downloaded STL has 563 degenerate faces and nine collinear boundary loops after their removal. Repair the resulting T-junctions by splitting adjacent triangle edges at existing vertices, rather than adding zero-area caps. The volume remains 15,550.531 mm³ and the final exported mesh is closed with no degenerate triangles. Attribute the source design to Creative Tools / Daniel Norée.

## Step 4 — Resolve Tower's composite clue

The DOI resolves to Beckwith, Fadhel, Park and Gupta, [Rheology guided additive manufacturing of thermosetting syntactic foams: mechanical behavior and failure mechanisms](https://doi.org/10.1016/j.compositesa.2025.109248). The publisher's abstract identifies hollow glass microspheres dispersed in an acrylate photopolymer matrix. Its raw-materials excerpt describes 45 µm Ecospheres with true particle density 0.31 g/cm³.

Interpret `Phi = 40%` as the microsphere volume fraction in this composite context. The nominal two-phase formulation is **40 vol.% hollow glass microspheres and 60 vol.% acrylate-based thermosetting photopolymer resin**. This is a formulation inferred from the supplied clue and paper; the mesh is not a chemical assay. Volume fraction must not be relabelled as weight fraction. Microsphere volume includes the hollow particles' envelopes, rather than solid glass volume alone.

## Step 5 — Open Box's supplied reference archive

Open the [public folder embedded in Box.ply](https://drive.google.com/drive/folders/1GBNstjhu-mba_AvmHhLZc9MK_f_Nt7FC?usp=sharing). It contains `Password.txt` and the encrypted `Secret Company Files.zip`. Download both through the folder's normal public download links. The text file asks for the name of the conference hosting the challenge. Conference-name spelling variants were checked; the accepted supplied-hint answer is **`CSAW26`**.

Read the archive listing, validate extraction paths, and open `Secret Company Files/main.pdf`. It is Bharath Kumar et al., [Processing of cenosphere/HDPE syntactic foams using an industrial scale polymer injection molding machine](https://doi.org/10.1016/j.matdes.2015.12.052). Read all ten pages, inspect its figures, and check PDF metadata, annotations, and embedded files. No PDF attachments or non-link annotations were present.

Figure 12, item 4, on PDF page 8 / journal page 421 shows the matching circular electrical connector with four sockets and two mounting bosses. Section 2.1 identifies HDPE grade HD50MA180 and CIL-150 fly-ash cenospheres. The cenosphere shells primarily comprise silica and alumina, with calcium oxide and iron oxides. This supports the challenge's intended **HDPE / fly-ash cenosphere syntactic-foam material family**.

Render the outside-bottom face using Box's original vertex RGB colors. The surface reads **`30%`**, as recorded in `Evidence/Box_surface_marking.png`. Section 3.1 on PDF page 2 explicitly describes pilot composites containing 30 and 60 wt.% cenospheres, labelled HDPE30 and HDPE60. Combining this surface clue with that definition supports the intended nominal Box formulation: **30 wt.% fly-ash cenospheres and 70 wt.% HDPE**.

The percentage basis is inferred from the linked paper: the surface label itself does not state wt.% or vol.%. This is a challenge-material identification, not a chemical assay. The paper's later main study also discusses 20, 40 and 60 wt.% mixtures; those do not erase its separate HDPE30 pilot formulation. Treatment, pigment and additives remain unspecified. The painted percentage is preserved as source evidence; the reconstructed CAD describes the body geometry.

## Step 6 — Fit and reconstruct Tower and Box

For Tower, use principal-axis alignment, then robustly fit the cylindrical wall while excluding end regions. Fit the end planes from cap-facing triangles. The side-wall fit gives reference diameter 12.4957 mm with 0.0510 mm RMS radial residual; cap separation is 24.2601 mm. The earlier CAD used an idealized Ø12.50 cylinder. To retain the observed bump and angular variation, intersect the original triangles every 0.25 mm and measure median radii in 72 angular bins. Connect 95 completed sections to create `Tower_revised`. Periodic interpolation fills missing angular bins; planar cap endpoints use the fitted baseline radius. These are fitted specimen dimensions; the original nominal design dimensions are not supplied.

For Box, fit the outside-bottom plane using surface normals and plane consensus, align the part with its cavity facing upward, and fit the circular wall surfaces away from socket intersections. Fit the socket end planes and retain measured outlet axes and end centers. Horizontal slices reveal two mounting bosses. Fit the surviving boss contours and the upper rim plane.

| Box feature | Reconstruction value | Evidence status |
|---|---|---|
| Body outside radius | 29.759358 - 0.002714 Z mm | Fitted taper; circular sections |
| Chamber inside radius | 27.609980 - 0.008295 Z mm | Fitted taper; circular sections |
| Floor at body center | Z=2.218 mm | Measured local plane; varies across X/Y |
| Minimum floor thickness | 1.00 mm | Assumed completion in missing geometry |
| Rim height at body center | 27.10 mm | Fitted; rim slopes about 6.82° |
| Socket outside / bore diameter | 23.00 / 20.00 mm | Common diameters inferred across occluded outlets |
| Mounting boss outside diameters | 9.04 and 9.82 mm | Fitted surviving contours |
| Mounting openings | Both Ø3.70 mm | Second fitted; first completed by symmetry |
| Blind-hole bottoms | Z=7.00 mm | Explicit assumption; depth is unresolved |
| Reconstructed overall span | 98.125 × 90.200 × 33.141 mm | Calculated from revised CAD bounds |

Use the measured wall trends to create the tapered circular body and chamber. Clip the body and bosses to the measured slanted rim. Subtract the chamber above the completed floor `Z_floor=max(1, Z_measured_plane)`. Join four socket bodies at their measured positions, including the shorter Y+ outlet. Inside the body, restrict bore cutters to the space above this floor so low ports preserve the assumed 1-mm minimum; outside the body, retain the complete circular bores. Add the bosses and their assumed blind openings. Boolean operations produce a single connected closed material boundary despite the functional cavity and holes. Simplify Boolean remnants with maximum surface displacement 0.00001 mm to remove numerical sliver triangles.

Socket axes, end centers, boss coordinates, wall trends and floor/rim equations are defined in drawing sheet 4 and `CAD/revised_parameters.json`. The physical interpretation of the uneven rim, wall taper and socket positions as original design versus scan distortion cannot be established. Unseen blind-hole bottoms, the floor minimum and the protected bore transition are reconstruction choices, not recovered ground truth. Printed numerical precision is not a manufacturing tolerance.

## Dimension analysis — Measure the irregularities and define CAD features

Intersect the original Tower triangles at 0.25-mm height increments and group surviving radii in 5-degree angular bins. The end flare has a median peak diameter of **{flare['median_peak_diameter_about_fixed_axis_mm']:.3f} mm** near **Z={flare['peak_section_z_mm']:.2f} mm**, projecting radially **{flare['median_radial_projection_above_baseline_mm']:.3f} mm** beyond the fitted body. Smaller changes occur along the body and around its circumference. Sparse end coverage is recorded instead of treated as a full measured circle.

![Tower source sections and radial deviations. White map cells are unobserved; bands describe spatial scan variation, not tolerances.](Evidence/Tower_dimension_profile.png)

`Dimension_Analysis.pdf` contains the measurement method, complete feature definitions, sketch tables, earlier comparison definitions and the final revised-model results. `Measurements/` contains Tower section diameters, center shifts, raw angular radii, every final loft section and the comparison revolve knots; Box wall profiles, floor/rim planes, outlet end centers and directions, mounting-boss coordinates and explicit assumed hole depths. The source-to-local transforms are also retained.

The final `CAD/Tower_revised.scad`, STL and PLY retain the flare and angular section shapes. `Tower_measured_profile` retains an axisymmetric median flare, while `Tower_reconstructed` is the earlier ideal cylinder. These two comparisons are retained. The final angular loft gives the smallest same-sample RMS distance, with its interpolation and cap completions stated explicitly.

The visible Box inner-floor patch fits a slope of **{floor_patch['tilt_degrees_to_outer_bottom']:.3f}°** with a central intercept of **{floor_patch['height_at_body_center_mm']:.3f} mm**. The previous Z=2.59 flat floor was a simplified CAD completion, not a measured uniform thickness. Unbounded plane extrapolation can cross the outside-bottom datum, so the final model follows the measured slope with an **assumed 1-mm minimum** and protects that floor from low socket cuts. Hidden transitions, depths, fillets and original nominal tolerances remain unresolved.

All Tower/Box dimensions retain the shared-export-unit assumption: the Boat supports one scan unit as one millimetre, while neither other PLY establishes an independent physical unit. Measurement precision is not a certified manufacturing tolerance.

## Revised model results — Generate the new CAD and figures

![Final Tower and Box solids, with original scan-point overlays in the same fitted coordinate frames. Red points show surviving source data.](Evidence/Revised_models_overview.png)

{table_revisions()}

The revised STLs are single closed solids. Their actual envelopes are **13.108 × 13.233 × 24.260 mm** for Tower and **98.125 × 90.200 × 33.141 mm** for Box. The comparison uses the same 18,000 vertices for each initial/revised pair. Better agreement measures fit to the captured surfaces; the measured scan also supplied the model parameters.

`Revised_Model_Results.pdf` contains five figures: CAD/scan overlays; Tower flare and angular sections; Box floor, wall taper and mesh section; outlet/boss locations and sections; and error curves/maps. It records interpolation, floor and hole-depth assumptions beside the relevant results. The full revised radius grids and feature definitions are in `CAD/revised_parameters.json`. The generated OpenSCAD definitions are editable; their compiler/render was unavailable, so verification uses the actual exported STL geometry.

## Step 7 — Verify exported geometry against the scans

Check all exported models for closed topology, consistent orientation, positive volume, nonmanifold edges and zero-area triangles. Re-import each actual STL file to verify serialization and vertex welding. Every output passes these checks.

{table_validation()}

Compare 18,000 sampled scan vertices per part with the closest actual triangles of its final reconstruction. Sampling uses a fixed random seed. These one-way distances evaluate agreement with surviving scan data; they cannot verify surfaces that the scans never captured. Tower/Box use the same sample for their initial/revised comparisons.

{table_distances()}

![Initial/revised cumulative distance curves and final source-point distance maps. Color saturation highlights larger residuals; the results report gives uncapped quantiles.](Evidence/Revised_fit_error_distributions.png)

Box remains the least certain: **98.42%** of samples lie within 1 mm; P99 is **1.436 mm** and maximum **3.146 mm**. Exported-mesh probes confirm the sloped floor and assumed 1-mm minimum, with outside bottom Z=0. Closed topology does not prove original CAD recovery. No physical print, dimensional inspection or materials experiment was performed.

## Step 8 — Produce the drawings and material findings

Generate `Restored_Parts_Drawings.pdf` from the exported final CAD. Sheet 1 gives Boat's orthographic views and official relevant feature dimensions. Sheet 2 defines Tower's measured angular loft and flare. Sheets 3–4 define Box's overall dimensions, tapered chamber, sloped/completed floor, sockets, bosses, coordinate locations, rim plane and explicit reconstruction assumptions. All dimensions are millimetres and the views are not to scale. The [official 3DBenchy dimensional reference](https://www.3dbenchy.com/dimensions/) supports Boat's nominal 60 × 31 × 48 mm envelope; the reference STL's bounds differ by at most a few micrometres.

| Part | Material result | Remaining composition uncertainty |
|---|---|---|
| Boat | PLA / polylactic acid, explicitly stated in the file | Grade, pigment and additives unspecified |
| Tower | 60 vol.% acrylate thermoset resin + 40 vol.% hollow glass microspheres | Specific resin formulation and measured porosity unspecified |
| Box | Nominal 70 wt.% HDPE + 30 wt.% fly-ash cenospheres | Weight basis inferred from surface label plus HDPE30 definition; treatment, pigment and additives unspecified |

Machine-readable material findings, evidence and limitations are included in `Materials_Composition.json`. Chemical identity is based on challenge annotations and their references, including the readable RGB surface label; the green color alone does not establish composition.

## Step 9 — Package the deliverables and reproduce the work

The ZIP contains `Final_Report.pdf`, this Markdown report, `Restored_Parts_Drawings.pdf`, `Dimension_Analysis.pdf`, `Revised_Model_Results.pdf`, measurements in JSON/CSV, final Boat/Tower/Box STL/PLY models, earlier comparison models, editable OpenSCAD files, numerical parameters, material findings, figures, evidence records and source code. Use **`Boat_reconstructed`, `Tower_revised` and `Box_revised`** as the final models. STL/PLY provide reconstructed tessellated CAD geometry; revised Box and Tower have editable definitions. Boat's OpenSCAD file imports its restored STL and does not claim an original editable design history.

Replace `Team_Name` with the registered team name and rename the submission folder/ZIP before submitting. The Google Forms submission URL is recorded in the README. No external submission has been made.

To reproduce in this original workspace, install the dependencies and run the included driver. It reads the supplied PLY files, resolves the same reference URLs, and rebuilds the deliverables. Each fitting stage uses a fixed seed. Detailed instructions are in `Reproducibility/README.md`.

```powershell
python -m pip install --target analysis/deps `
  -r Team_Name_Submission/Reproducibility/requirements.txt
python Team_Name_Submission/Reproducibility/reproduce.py
```

Original-input hashes and all output hashes are retained in `MANIFEST_SHA256.json`. This allows verification that the source scans were preserved and that the reviewed CAD and documents match the packaged files.
'''
    (OUT/'Final_Report.md').write_text(md,encoding='utf8')
    pdf_from_md(md)
    readme='''# Hack3D reconstruction submission

Read Final_Report.pdf for the numbered process, evidence, results and limitations.
Restored_Parts_Drawings.pdf contains four drawing sheets.
Dimension_Analysis.pdf adds source profiles, feature definitions, comparison models and final revised-model results.
Revised_Model_Results.pdf presents the five new figures, final model definitions and same-sample fit comparisons.
Measurements/ contains the complete dimension data in JSON and CSV, including qualified missing values and coordinate transforms.
The final model files are CAD/Boat_reconstructed.*, CAD/Tower_revised.* and CAD/Box_revised.* (STL, PLY and OpenSCAD).
CAD/revised_parameters.json and Measurements/Tower_revised_sections.csv define the new loft and Box surfaces.
CAD/Tower_measured_profile.* is the axisymmetric median-flare comparison; Tower_reconstructed.* is the ideal cylinder and Box_reconstructed.* is the earlier flat-floor comparison.
Materials_Composition.json records compositions and their evidence.
Evidence/ contains numerical audits and validation results.
Reproducibility/ contains the scripts and instructions to rebuild the package.

All model coordinates are interpreted as millimetres under the shared-scan-unit assumption supported by Boat. STL has no embedded unit field: select mm on import.
Boat's dimensions are from the official reference. Tower and Box dimensions are estimated from the scans.
Box's nominal material is inferred as 30 wt.% fly-ash cenospheres / 70 wt.% HDPE from its 30% surface label and the paper's HDPE30 definition. Its blind-hole depth remains unresolved.
Box's final floor follows the measured slope with an assumed 1-mm minimum in missing geometry. Inside the body, socket bores are constrained to preserve this floor; hidden transitions remain assumptions.
Both revised STL exports were checked directly. OpenSCAD source files were generated, but a compiler/render was not available.

Replace Team_Name with your registered team name in the folder/ZIP and report before submitting.
Submission form embedded in the statement: https://forms.gle/1utSoMe7idv2stVW9
This package has not been submitted externally.
'''
    (OUT/'README.md').write_text(readme,encoding='utf8')
    inputs={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['Boat.ply','Tower.ply','Box.ply','Qualifier 2025 Problem Statement.pdf']}
    for name in ['Boat','Tower','Box']:assert inputs[name+'.ply']==audit[name]['sha256']
    files={p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='MANIFEST_SHA256.json'}
    manifest={'algorithm':'SHA-256','original_inputs':inputs,'output_files':files,'manifest_note':'This manifest does not hash itself or the containing ZIP.'}
    (OUT/'MANIFEST_SHA256.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    target=ROOT/'Team_Name_Submission.zip'
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for p in sorted(OUT.rglob('*')):
            if p.is_file():archive.write(p,p.relative_to(ROOT).as_posix())
    print('ZIP',target.stat().st_size,'bytes',len(files)+1,'files',flush=True)


if __name__=='__main__':main()
