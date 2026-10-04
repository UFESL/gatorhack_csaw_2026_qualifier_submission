"""Build reconstructed, closed CAD meshes and editable OpenSCAD models."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'deps'))
import json
import shutil
import numpy as np
import trimesh
from scipy.optimize import least_squares
from audit_meshes import write_ply

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'Team_Name_Submission'
CAD=OUT/'CAD'
CAD.mkdir(parents=True,exist_ok=True)
AN=ROOT/'analysis'
fits=json.loads((AN/'geometry_fits.json').read_text())


def slanted_cylinder(radius,center,bottom,normal,offset,segments=192):
    theta=np.arange(segments)*2*np.pi/segments
    xy=np.column_stack((radius*np.cos(theta),radius*np.sin(theta)))+center
    top=(offset-xy@normal[:2])/normal[2]
    ct=(offset-np.asarray(center)@normal[:2])/normal[2]
    v=np.vstack((np.column_stack((xy,np.full(segments,bottom))),np.column_stack((xy,top)),
        [*center,bottom],[*center,ct]))
    f=[]
    for i in range(segments):
        j=(i+1)%segments
        f.extend([[i,j,segments+j],[i,segments+j,segments+i],
            [2*segments,j,i],[2*segments+1,segments+i,segments+j]])
    m=trimesh.Trimesh(vertices=v,faces=f,process=False)
    assert m.is_volume
    return m


def cylinder_between(radius,a,b):
    a=np.asarray(a);b=np.asarray(b);direction=b-a;length=np.linalg.norm(direction)
    transform=trimesh.geometry.align_vectors([0,0,1],direction/length)
    transform[:3,3]=(a+b)/2
    return trimesh.creation.cylinder(radius=radius,height=length,sections=192,transform=transform)


def fit_bosses():
    d=np.load(AN/'Box_aligned.npz');p=d['vertices'];f=d['faces']
    t=p[f];n=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);n/=np.linalg.norm(n,axis=1)[:,None]
    c=t.mean(1)
    bosses=[]
    for guess in [[-15.5,17.0],[18.0,-17.0]]:
        delta=np.linalg.norm(c[:,:2]-guess,axis=1)
        mask=(delta<6.5)&(np.abs(n[:,2])<.4)&(c[:,2]>21)&(np.linalg.norm(c[:,:2],axis=1)<27)
        q=c[mask,:2]
        def residual(x):
            rad=np.linalg.norm(q-x[:2],axis=1)
            errs=np.column_stack((rad-x[2],rad-x[3]))
            return errs[np.arange(len(errs)),np.abs(errs).argmin(1)]
        result=least_squares(residual,[*guess,1.5,4.5],bounds=([guess[0]-3,guess[1]-3,.8,3.5],[guess[0]+3,guess[1]+3,2.5,6]),loss='soft_l1',f_scale=.12).x
        bosses.append({'center':np.round(result[:2],2).tolist(),'outer_radius':round(float(result[3]),2),
            'opening_radius':round(float(result[2]),2),'fit_abs_residual_p95':float(np.percentile(np.abs(residual(result)),95)),
            'blind_hole_bottom':7.0,'hole_depth_evidence':'Bottom at z=7 mm is an explicit reconstruction assumption; the scan does not resolve blind-hole depth.'})
    # The first boss is partially absent. Its fit reaches a bound, so complete
    # its bore by symmetry using the better observed second boss opening.
    bosses[0]['opening_radius']=bosses[1]['opening_radius']
    bosses[0]['opening_evidence']='Inferred by symmetry from the better preserved second boss.'
    return bosses


def mesh_stats(mesh):
    counts=np.bincount(mesh.edges_unique_inverse)
    return {'vertices':len(mesh.vertices),'faces':len(mesh.faces),'boundary_edges':int((counts==1).sum()),
        'nonmanifold_edges':int((counts>2).sum()),'degenerate_faces':int((~mesh.nondegenerate_faces(height=1e-10)).sum()),
        'watertight':bool(mesh.is_watertight),'consistent_winding':bool(mesh.is_winding_consistent),
        'positive_volume':bool(mesh.volume>0),'volume_mm3':float(mesh.volume),'surface_area_mm2':float(mesh.area),
        'bounds_mm':mesh.bounds.tolist(),'span_mm':mesh.extents.tolist()}


def build_box():
    box=fits['Box'];normal=np.asarray(box['rim_plane_fit']['normal']);height=round(box['rim_plane_fit']['center_height'],2)
    offset=height*normal[2]
    outer_radius=round(box['outer_cone']['intercept'],2)
    inner_radius=round(box['inner_cone']['intercept'],2)
    floor=round(box['inside_floor_percentiles'][1],2)
    bosses=fit_bosses()
    params={'outer_radius':outer_radius,'inner_radius':inner_radius,'bottom_thickness':floor,
        'rim_center_height':height,'rim_plane_normal':normal.tolist(),
        'socket_outer_radius':11.50,'socket_bore_radius':10.00,'bosses':bosses,
        'inferred_features':['Common socket OD 23.00 mm and bore 20.00 mm are inferred across missing/occluded outlets.','Blind-hole depth is not resolved by the scan; bore stops at z=7.00 mm.','The partially missing first boss bore is inferred by symmetry from the better preserved second boss.','Circular walls are idealizations; measured port axes and the slanted rim are retained.']}
    solids=[slanted_cylinder(outer_radius,[0,0],0,normal,offset)]
    cutters=[cylinder_between(inner_radius,[0,0,floor],[0,0,100])]
    ports=[]
    for port in box['port_cylinder_fits']:
        pn=np.asarray(port['direction']);end=np.asarray(port['end_center'])
        # Preserve measured outlet positions and axes, while using a common
        # inferred diameter to complete surfaces absent from the scan.
        endpoint=end
        start=end-pn*24
        solids.append(cylinder_between(params['socket_outer_radius'],start,endpoint))
        cutters.append(cylinder_between(params['socket_bore_radius'],end-pn*28,end+pn*.1))
        ports.append({'axis':port['axis'],'sign':port['sign'],'direction':pn.tolist(),
            'end_center':endpoint.tolist(),'start_center':start.tolist()})
    shell=trimesh.boolean.difference([trimesh.boolean.union(solids,engine='manifold'),
        trimesh.boolean.union(cutters,engine='manifold')],engine='manifold')
    additions=[]
    holes=[]
    for boss in bosses:
        additions.append(slanted_cylinder(boss['outer_radius'],boss['center'],floor,normal,offset))
        holes.append(cylinder_between(boss['opening_radius'],[*boss['center'],boss['blind_hole_bottom']],[*boss['center'],60]))
    mesh=trimesh.boolean.difference([trimesh.boolean.union([shell]+additions,engine='manifold'),
        trimesh.boolean.union(holes,engine='manifold')],engine='manifold')
    from manifold3d import Manifold,Mesh
    solid=Manifold(Mesh(np.asarray(mesh.vertices,dtype=np.float32),np.asarray(mesh.faces,dtype=np.uint32)))
    simplified=solid.simplify(1e-5).to_mesh()
    mesh=trimesh.Trimesh(vertices=np.asarray(simplified.vert_properties)[:,:3],faces=np.asarray(simplified.tri_verts),process=False)
    params['ports']=ports
    lines=['// Box reconstruction. Dimensions are mm; inferred features are documented in the report.',
        '$fn=192;',f'body_r={outer_radius};',f'cavity_r={inner_radius};',f'floor_t={floor};',f'rim_h={height};',
        f'rim_normal={normal.tolist()};',f'bosses={[[*b["center"],b["outer_radius"],b["opening_radius"],b["blind_hole_bottom"]] for b in bosses]};',
        f'ports={[[p["start_center"],p["end_center"]] for p in ports]};',
        '''
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
''']
    (CAD/'Box_reconstructed.scad').write_text('\n'.join(lines),encoding='utf8')
    return mesh,params


if __name__=='__main__':
    boat=trimesh.load_mesh(AN/'Boat_reference_clean.stl')
    (CAD/'Boat_reconstructed.scad').write_text('// Official 3DBenchy geometry, topology repaired; dimensions mm.\nimport("Boat_reconstructed.stl");\n')
    diameter=round(fits['Tower']['diameter'],2);height=round(fits['Tower']['height'],2)
    tower=cylinder_between(diameter/2,[0,0,0],[0,0,height])
    (CAD/'Tower_reconstructed.scad').write_text(f'// Scan-fitted dimensions, mm. Ideal cylinder; scan edge flare is omitted.\n$fn=192;\ncylinder(d={diameter},h={height});\n')
    box,params=build_box()
    results={}
    for name,mesh in [('Boat',boat),('Tower',tower),('Box',box)]:
        stats=mesh_stats(mesh)
        assert stats['watertight'] and stats['consistent_winding'] and stats['positive_volume']
        assert stats['boundary_edges']==0 and stats['nonmanifold_edges']==0 and stats['degenerate_faces']==0
        mesh.export(CAD/f'{name}_reconstructed.stl')
        write_ply(CAD/f'{name}_reconstructed.ply',mesh.vertices,mesh.faces)
        # Check the actual exported file, including STL welding/serialization.
        loaded=trimesh.load_mesh(CAD/f'{name}_reconstructed.stl')
        assert loaded.is_volume and loaded.nondegenerate_faces(height=1e-10).all()
        stats['export_roundtrip_passed']=True
        results[name]=stats
        print(name,json.dumps(stats),flush=True)
    parameters={'Boat':{'nominal_length':60.0,'nominal_width':31.0,'nominal_height':48.0,
        'source':'Official CreativeTools/3DBenchy Single-part STL; tessellated bounding box differs by a few micrometres.'},
        'Tower':{'diameter':diameter,'height':height,'dimensions':'Fitted physical scan dimensions; original nominal design dimensions are not supplied.'},'Box':params}
    (OUT/'CAD'/'reconstruction_parameters.json').write_text(json.dumps(parameters,indent=2))
    (AN/'reconstruction_validation.json').write_text(json.dumps(results,indent=2))
