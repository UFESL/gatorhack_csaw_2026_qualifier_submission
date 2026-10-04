from pathlib import Path
import json
import numpy as np
from scipy.optimize import least_squares
from fit_geometry import fit_plane_ransac

OUT=Path(__file__).resolve().parent
d=np.load(OUT/'Box_aligned.npz');p=d['vertices'];f=d['faces']
t=p[f];normal=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);normal/=np.linalg.norm(normal,axis=1)[:,None]
c=t.mean(1);r=np.linalg.norm(c[:,:2],axis=1);angle=np.arctan2(c[:,1],c[:,0])
rim=(np.abs(normal[:,2])>.85)&(r>27)&(r<31)&(c[:,2]>23)&(np.abs(np.sin(2*angle))>.4)
if rim.sum()>30:
    n,offset,count,error=fit_plane_ransac(c[rim],np.array([0.,0.,1]),threshold=.25)
    print('RIM',n,offset,count,error,flush=True)
else:
    n=np.array([0.,0.,1.]);offset=27.
results=[]
for axis,sign in [(0,1),(0,-1),(1,1),(1,-1)]:
    other=1-axis
    portregion=(c[:,axis]*sign>34)&(np.abs(c[:,other])<15)
    endnorm=portregion&(np.abs(normal[:,axis])>.90)
    axis_prior=np.zeros(3);axis_prior[axis]=sign
    pn,po,nfaces,perror=fit_plane_ransac(c[endnorm],axis_prior,threshold=.2)
    length=float(po/abs(pn[axis]))
    q=p[(p[:,axis]*sign>34)&(p[:,axis]*sign<length-1)&(np.abs(p[:,other])<15)]
    # Fit two coaxial cylinders to the surviving bore/exterior. End-plane normal
    # supplies the axis direction; this also accounts for slightly tilted ports.
    u=np.zeros(3);u[other]=1;u-=pn*(u@pn);u/=np.linalg.norm(u)
    vv=np.cross(pn,u)
    if vv[2]<0:vv=-vv
    proj=q@np.column_stack((u,vv))
    best=None
    for center_z in [9.,12.,15.]:
        for center_y in [-2.,0.,2.]:
            start=[center_y,center_z,10.,11.5]
            def residual(x):
                rad=np.linalg.norm(proj-x[:2],axis=1)
                rr=np.column_stack((rad-x[2],rad-x[3]));k=np.abs(rr).argmin(1)
                return rr[np.arange(len(rr)),k]
            fit=least_squares(residual,start,bounds=([-10,0,8,10.8],[10,25,10.8,13]),loss='soft_l1',f_scale=.12)
            if best is None or fit.cost<best.cost:best=fit
    x=best.x
    rad=np.linalg.norm(proj-x[:2],axis=1)
    outer_count=int((np.abs(rad-x[3])<.2).sum());inner_count=int((np.abs(rad-x[2])<.2).sum())
    center=x[0]*u+x[1]*vv
    end=center+pn*(po-center@pn)
    record={'axis':'XY'[axis],'sign':sign,'direction':pn.tolist(),'end_center':end.tolist(),
        'inner_radius':float(x[2]),'outer_radius':float(x[3]),'inner_inliers':inner_count,'outer_inliers':outer_count,
        'radius_residual_percentiles':np.percentile(np.abs(residual(x)),[50,90,95]).tolist(),
        'end_plane_rmse':perror,'end_plane_inliers':nfaces}
    results.append(record)
    print('PORT',json.dumps(record),flush=True)
fits=json.loads((OUT/'geometry_fits.json').read_text())
fits['Box']['rim_plane_fit']={'normal':n.tolist(),'center_height':float(offset/n[2])}
fits['Box']['port_cylinder_fits']=results
(OUT/'geometry_fits.json').write_text(json.dumps(fits,indent=2))
