# Hack3D reconstruction submission

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

