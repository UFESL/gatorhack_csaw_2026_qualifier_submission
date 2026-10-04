"""Fit analytic geometry to the original scans; retain transformations and residuals."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'deps'))
import json
import numpy as np
from scipy.optimize import least_squares
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from audit_meshes import metrics

OUT = Path(__file__).resolve().parent
RNG = np.random.default_rng(2026)


def fit_plane_ransac(points,prior,threshold=.12,iterations=250):
    p = points[RNG.choice(len(points), min(7000,len(points)), replace=False)]
    best = None
    for _ in range(iterations):
        a,b,c = p[RNG.choice(len(p),3,replace=False)]
        n = np.cross(b-a,c-a)
        n /= np.linalg.norm(n)
        if abs(n@prior)<.97:
            continue
        if n@prior<0:
            n = -n
        d = a@n
        mask = np.abs(p@n-d)<threshold
        score = mask.sum()
        if best is None or score>best[0]:
            best = score,n,d
    _,n,d = best
    for _ in range(4):
        close = points[np.abs(points@n-d)<threshold]
        center = close.mean(0)
        _,_,vh = np.linalg.svd(close-center,full_matrices=False)
        n = vh[-1]
        if n@prior<0: n=-n
        d=center@n
    return n,d,len(close),float(np.sqrt(np.mean((close@n-d)**2)))


def frame(n):
    x=np.array([1.,0,0]);x-=n*(x@n);x/=np.linalg.norm(x)
    return np.column_stack((x,np.cross(n,x),n))


def circle_fit(p,initial):
    def residual(x):
        return np.linalg.norm(p[:,:2]-x[:2],axis=1)-x[2]
    r=least_squares(residual,initial,loss='soft_l1',f_scale=.08)
    return r.x,residual(r.x)


def tower():
    data=np.load(OUT/'Tower_scan.npz');v=data['vertices'];f=data['faces']
    _,b=np.linalg.eigh(np.cov(v.T));n=b[:,-1]
    if n[1]<0:n=-n
    basis=frame(n);p=(v-v.mean(0))@basis
    # Fit the side wall, excluding the two caps and the edge/brim regions.
    side=(p[:,2]>np.quantile(p[:,2],.2))&(p[:,2]<np.quantile(p[:,2],.8))
    sidep=v[side]-v.mean(0)
    initial=np.r_[n[0]/n[1],n[2]/n[1],0.,0.,6.3]
    def residual(x):
        axis=np.array([x[0],1.,x[1]]);axis/=np.linalg.norm(axis)
        base=frame(axis);q=sidep@base
        return np.linalg.norm(q[:,:2]-x[2:4],axis=1)-x[4]
    result=least_squares(residual,initial,loss='soft_l1',f_scale=.08)
    x=result.x;n=np.array([x[0],1.,x[1]]);n/=np.linalg.norm(n)
    basis=frame(n);p=(v-v.mean(0))@basis;p[:,:2]-=x[2:4]
    lower=p[p[:,2]<np.quantile(p[:,2],.12)]
    upper=p[p[:,2]>np.quantile(p[:,2],.88)]
    cap_lo=float(np.median(lower[:,2]));cap_hi=float(np.median(upper[:,2]))
    p[:,2]-=cap_lo
    origin=v.mean(0)+basis@np.r_[x[2:4],cap_lo]
    result={'diameter':float(2*x[4]),'height':cap_hi-cap_lo,'axis':n.tolist(),'origin':origin.tolist(),
        'basis':basis.tolist(),'side_fit_rmse':float(np.sqrt(np.mean(residual(x)**2))),
        'side_abs_residual_percentiles':np.percentile(np.abs(residual(x)),[50,90,95,99]).tolist(),
        'lower_cap_z_percentiles':np.percentile(lower[:,2]-cap_lo,[5,50,95]).tolist(),
        'upper_cap_z_percentiles':np.percentile(upper[:,2]-cap_lo,[5,50,95]).tolist()}
    np.savez_compressed(OUT/'Tower_aligned.npz',vertices=p,faces=f)
    plot('Tower_aligned',p,None)
    print('TOWER',json.dumps(result),flush=True)
    return result


def box():
    data=np.load(OUT/'Box_scan.npz');v=data['vertices'];f=data['faces'];colors=data['colors']
    tris=v[f];normals=np.cross(tris[:,1]-tris[:,0],tris[:,2]-tris[:,0]);normals/=np.linalg.norm(normals,axis=1)[:,None]
    _,b=np.linalg.eigh(np.cov(v.T));n=b[:,0]
    if n[2]<0:n=-n
    centroids=tris.mean(axis=1)
    aligned=np.abs(normals@n)>.985
    n,d,count,rmse=fit_plane_ransac(centroids[aligned],n)
    basis=frame(n);p=(v-v.mean(0))@basis
    flat_z=(centroids-v.mean(0))@n
    bins=np.arange(flat_z.min()-.05,flat_z.max()+.05,.08)
    h,e=np.histogram(flat_z[aligned],bins)
    peaks=np.argsort(h)[::-1][:20]
    print('BOX PLANES',[(round(float((e[i]+e[i+1])/2),3),int(h[i])) for i in peaks],flush=True)
    # Circle consensus on near-vertical body surfaces; radius range excludes ports/bosses.
    wall=centroids[np.abs(normals@n)<.15]
    q=(wall-v.mean(0))@basis
    sample=q[RNG.choice(len(q),min(14000,len(q)),replace=False)]
    best=None
    for _ in range(600):
        a,b,c=sample[RNG.choice(len(sample),3,replace=False),:2]
        try:
            center=np.linalg.solve(2*np.vstack((b-a,c-a)),np.array([b@b-a@a,c@c-a@a]))
        except np.linalg.LinAlgError:
            continue
        radius=np.linalg.norm(a-center)
        if not 26<radius<36 or np.linalg.norm(center)>12:
            continue
        error=np.abs(np.linalg.norm(sample[:,:2]-center,axis=1)-radius)
        score=(error<.25).sum()
        if best is None or score>best[0]:best=score,center,radius
    _,center,radius=best
    close=np.abs(np.linalg.norm(q[:,:2]-center,axis=1)-radius)<.5
    circle,residual=circle_fit(q[close],np.r_[center,radius])
    p[:,:2]-=circle[:2]
    radial=np.linalg.norm(p[:,:2],axis=1)
    # The source outer circle normally has the stronger consensus. Preserve both shells.
    bins=np.arange(25,37,.06);h,e=np.histogram(radial,bins)
    peaks=np.argsort(h)[::-1][:25]
    print('BOX RADII',[(round(float((e[i]+e[i+1])/2),3),int(h[i])) for i in peaks],flush=True)
    floor_z=float(np.median(flat_z[np.abs(flat_z-(d-v.mean(0)@n))<.16]))
    p[:,2]-=floor_z
    origin=v.mean(0)+basis@np.r_[circle[:2],floor_z]
    result={'basis':basis.tolist(),'origin':origin.tolist(),'plane_normal':n.tolist(),
        'plane_fit_rmse':rmse,'plane_inlier_faces':count,'body_circle_fit':circle.tolist(),
        'body_radius_fit_rmse':float(np.sqrt(np.mean(residual**2))),
        'aligned_span':np.ptp(p,axis=0).tolist(),'aligned_min':p.min(0).tolist(),'aligned_max':p.max(0).tolist()}
    np.savez_compressed(OUT/'Box_aligned_initial.npz',vertices=p,faces=f,colors=colors)
    plot('Box_aligned_initial',p,colors)
    print('BOX',json.dumps(result),flush=True)
    return result


def plot(name,p,c):
    idx=RNG.choice(len(p),min(len(p),70000),replace=False)
    fig,axes=plt.subplots(1,3,figsize=(18,6),layout='constrained')
    for ax,(a,b) in zip(axes,[(0,1),(0,2),(1,2)]):
        ax.scatter(p[idx,a],p[idx,b],s=.3,c=c[idx]/255 if c is not None else p[idx,2],cmap=None if c is not None else 'viridis')
        ax.set_aspect('equal');ax.set_xlabel('XYZ'[a]);ax.set_ylabel('XYZ'[b]);ax.grid(alpha=.2)
        ax.set_title(name)
    fig.savefig(OUT/f'{name}.png',dpi=140);plt.close(fig)


if __name__=='__main__':
    fits={'Tower':tower(),'Box':box()}
    (OUT/'geometry_fits.json').write_text(json.dumps(fits,indent=2))
