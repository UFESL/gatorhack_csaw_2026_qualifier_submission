# Reproduce the reconstruction

Python 3.10 was used. Keep the supplied Boat.ply, Tower.ply, Box.ply and Qualifier 2025 Problem Statement.pdf in the original workspace. The driver does not modify those inputs.

From the workspace in PowerShell:

```powershell
python -m pip install --target analysis/deps -r Team_Name_Submission/Reproducibility/requirements.txt
python Team_Name_Submission/Reproducibility/reproduce.py
```

For a different workspace, supply `--workspace` with its absolute path. The four original inputs must be at that path. The driver copies these bundled scripts to its analysis directory and rebuilds Team_Name_Submission and the ZIP. It overwrites generated outputs with the same names. Network access is needed if the public Benchy and Google Drive reference files are not already cached there.

Process order:

1. audit_meshes.py reads every declared PLY record, saves embedded annotations and checks topology.
2. repair_benchy.py repairs degenerate faces and collinear T-junctions in the official reference.
3. register_boat.py aligns the scan to the reference through principal-axis candidates and trimmed ICP.
4. fit_geometry.py, refine_geometry.py and finalize_box_fits.py fit cylinder walls, planes, ports and rim.
5. build_models.py completes the shapes, exports CAD and checks actual STL reimports.
6. validate_reconstruction.py measures exact distances from 18,000 sampled scan vertices to CAD triangles.
7. inspect_surface_markings.py renders Boat's underside lettering and Box's original RGB percentage label, preserving both as evidence.
8. measure_dimensions.py intersects source triangles, measures Tower's flare and section variation, records Box feature dimensions and creates the additional Tower measured-profile CAD.
9. build_revised_models.py creates the final angular Tower loft and tapered/sloped-floor Box, validates STL exports, probes the floor and compares initial/revised models against the same source samples.
10. make_revised_results.py generates five figures and Revised_Model_Results.pdf with final definitions and comparisons.
11. make_dimension_report.py writes the measurement/CAD guide and appends the final results and figures.
12. make_drawings.py renders four drawing sheets from the final exported models.
13. make_report.py creates the stepwise PDF/Markdown report, material findings, evidence, hashes and ZIP.
14. check_package.py verifies source/output hashes, archive contents, actual revised mesh geometry and all reports/drawings.

STL imports must use millimetres under the shared-scan-unit assumption supported by Boat. PLY does not carry a standardized unit field either. Boat dimensions are official nominal values; Tower and Box are scan-fitted estimates. Use Boat_reconstructed.*, Tower_revised.* and Box_revised.* as the final models. Dimension_Analysis.pdf, Revised_Model_Results.pdf and Measurements/ record source profiles, scale qualifications, feature locations and completion choices. Tower_revised retains angular variation with periodic interpolation and baseline-circle cap completion. Box_revised follows the measured taper and floor slope with an assumed 1-mm floor minimum, protected internal bore transition and Z=7 blind-hole bottoms. Earlier cylinder, median-revolve and flat-floor versions remain comparison models. Actual STL geometry is validated; the OpenSCAD definitions were generated without a separate compiler/render check. Box's 30% RGB surface label and the paper's HDPE30 definition support a nominal 30 wt.% cenospheres / 70 wt.% HDPE formulation; the label alone does not specify the percentage basis. The report does not claim an exact original parametric CAD history or a physical manufacturing test.
