// Revised Box: tapered walls and bounded measured floor. Units assumed mm.
$fn=192;
outer_r0=29.759358425590474;
outer_k=-0.0027143294964203256;
inner_r0=27.609980039054637;
inner_k=-0.008294729738950337;
rim_h=27.1;
rim_n=[0.11868937481308282, 7.40746171702944e-05, 0.9929314310764015];
floor_h=2.2181930621888224;
floor_n=[0.11591547745465479, -0.00245703761722621, 0.9932560420418326];
floor_min=1.0;
ports=[[[23.947295991824355, -0.5125007755288479, 10.067887129364646], [47.92010244194342, -0.9033968292067444, 8.994690418435733]], [[-24.80578310593778, 1.2927821637505987, 12.605409859605263], [-48.72716380485029, 1.7599487202733886, 14.489368687754844]], [[-0.6575573369797785, 15.9879882989651, 11.978291472185509], [0.5931834919079235, 39.95313994370516, 11.650947580282885]], [[-0.562931811798567, -25.3618653897868, 11.902826038271654], [-0.8587536491756527, -49.35513744271558, 12.387991612769437]]];
bosses=[[-16.9, 16.41, 4.52, 1.85, 7.0], [17.75, -16.55, 4.91, 1.85, 7.0]];

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
