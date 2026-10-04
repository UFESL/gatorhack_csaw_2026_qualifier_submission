# Dimension measurements

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
