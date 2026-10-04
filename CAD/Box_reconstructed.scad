// Box reconstruction. Dimensions are mm; inferred features are documented in the report.
$fn=192;
body_r=29.76;
cavity_r=27.61;
floor_t=2.59;
rim_h=27.1;
rim_normal=[0.11868937481308282, 7.40746171702944e-05, 0.9929314310764015];
bosses=[[-16.9, 16.41, 4.52, 1.85, 7.0], [17.75, -16.55, 4.91, 1.85, 7.0]];
ports=[[[23.947295991824355, -0.5125007755288479, 10.067887129364646], [47.92010244194342, -0.9033968292067444, 8.994690418435733]], [[-24.80578310593778, 1.2927821637505987, 12.605409859605263], [-48.72716380485029, 1.7599487202733886, 14.489368687754844]], [[-0.6575573369797785, 15.9879882989651, 11.978291472185509], [0.5931834919079235, 39.95313994370516, 11.650947580282885]], [[-0.562931811798567, -25.3618653897868, 11.902826038271654], [-0.8587536491756527, -49.35513744271558, 12.387991612769437]]];

module tube_between(a,b,r,extend=0) {
    d=b-a;
    h=norm(d);
    translate(a) rotate(a=acos(d[2]/h),v=[-d[1],d[0],0]) cylinder(r=r,h=h+extend);
}
module above_rim() {
    // Bottom face of this rotated cube is the measured slanted rim plane.
    translate([0,0,rim_h]) rotate(a=acos(rim_normal[2]),v=[-rim_normal[1],rim_normal[0],0])
        translate([-100,-100,0]) cube([200,200,200]);
}
difference() {
    union() {
        difference() {
            union() {
                difference() { cylinder(r=body_r,h=60); above_rim(); }
                for (p=ports) tube_between(p[0],p[1],11.5);
            }
            translate([0,0,floor_t]) cylinder(r=cavity_r,h=100);
            for (p=ports) {
                d=(p[1]-p[0])/norm(p[1]-p[0]);
                tube_between(p[1]-28*d,p[1]+0.1*d,10);
            }
        }
        for (b=bosses) difference() {
            translate([b[0],b[1],floor_t]) cylinder(r=b[2],h=60-floor_t);
            above_rim();
        }
    }
    for (b=bosses) translate([b[0],b[1],b[4]]) cylinder(r=b[3],h=60);
}
