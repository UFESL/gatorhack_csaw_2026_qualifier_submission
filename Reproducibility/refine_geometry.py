from pathlib import Path
import json
import numpy as np
from scipy.optimize import least_squares
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from fit_geometry import plot

OUT=Path(__file__).resolve().parent
fits=json.loads((OUT/'geometry_fits.json').read_text())


def robust_line(z,r):
    x=least_squares(lambda p:r-p[0]-p[1]*z,[np.median(r),0],loss='soft_l1',f_scale=.12).x
    residual=r-x[0]-x[1]*z
    return {'intercept':float(x[0]),'slope':float(x[1]),'rmse':float(np.sqrt(np.mean(residual**2))),
        'n':len(z),'absolute_residual_p95':float(np.percentile(np.abs(residual),95))}


def tower():
    data=np.load(OUT/'Tower_aligned.npz');p=data['vertices'];f=data['faces']
    t=p[f];normals=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);normals/=np.linalg.norm(normals,axis=1)[:,None]
    c=t.mean(1)
    flat=np.abs(normals[:,2])>.95
    lo=c[(c[:,2]<3)&flat,2];hi=c[(c[:,2]>21)&flat,2]
    bottom=float(np.median(lo));top=float(np.median(hi))
    p[:,2]-=bottom
    fits['Tower']['origin']=(np.asarray(fits['Tower']['origin'])+np.asarray(fits['Tower']['basis'])[:,2]*bottom).tolist()
    fits['Tower']['height']=top-bottom
    fits['Tower']['cap_plane_percentiles']={'bottom':np.percentile(lo-bottom,[5,50,95]).tolist(),'top':np.percentile(hi-bottom,[5,50,95]).tolist()}
    np.savez_compressed(OUT/'Tower_aligned.npz',vertices=p,faces=f)
    print('TOWER CAPS',json.dumps(fits['Tower']),flush=True)


def box():
    data=np.load(OUT/'Box_aligned_initial.npz');p=data['vertices'];f=data['faces'];colors=data['colors']
    p*=np.array([1,-1,-1])
    fits['Box']['basis']=(np.asarray(fits['Box']['basis'])*np.array([1,-1,-1])).tolist()
    t=p[f];normal=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);normal/=np.linalg.norm(normal,axis=1)[:,None]
    c=t.mean(1);r=np.linalg.norm(c[:,:2],axis=1);angle=np.arctan2(c[:,1],c[:,0])
    radial=np.einsum('ij,ij->i',normal[:,:2],c[:,:2])/r
    sector=np.abs(np.sin(2*angle))>.65
    side=sector&(r>24)&(r<34)&(c[:,2]>2)&(c[:,2]<26)
    outer=side&(radial>.85);inner=side&(radial<-.85)
    outer_fit=robust_line(c[outer,2],r[outer]);inner_fit=robust_line(c[inner,2],r[inner])
    fits['Box']['outer_cone']=outer_fit;fits['Box']['inner_cone']=inner_fit
    rim=(normal[:,2]>.75)&(r>28)&(r<34)&(c[:,2]>23)
    height=float(np.median(c[rim,2]));fits['Box']['height']=height
    fits['Box']['rim_plane_percentiles']=np.percentile(c[rim,2],[5,50,95]).tolist()
    floor=(normal[:,2]>.95)&(r<25)&(c[:,2]>1)&(c[:,2]<8)
    fits['Box']['inside_floor_percentiles']=np.percentile(c[floor,2],[5,50,95]).tolist() if floor.any() else []
    ports=[]
    # Ports are approximately aligned to the scanner's X/Y axes after leveling.
    for axis,sgn in [(0,1),(0,-1),(1,1),(1,-1)]:
        other=1-axis
        a=c[:,axis]*sgn
        endregion=(a>36)&(np.abs(c[:,other])<14)
        endnormal=np.abs(normal[:,axis])>.9
        end=c[endregion&endnormal]
        length=float(np.median(end[:,axis])*sgn) if len(end)>50 else float(np.quantile(p[p[:,axis]*sgn>35,axis]*sgn,.99))
        # The side surface is a circle in the transverse/height plane.
        side_region=(a>34)&(a<length-.6)&(np.abs(normal[:,axis])<.2)
        q=c[side_region][:,[other,2]]
        initial=np.array([np.median(q[:,0]),np.median(q[:,1]),11.])
        def residual(x):return np.linalg.norm(q-x[:2],axis=1)-x[2]
        best=least_squares(residual,initial,loss='soft_l1',f_scale=.2).x
        # Separate outer and inner walls by their radial normal direction.
        nr=normal[side_region][:,[other,2]]
        dot=np.einsum('ij,ij->i',q-best[:2],nr)
        groups={}
        for key,mask in [('outer',dot>3),('inner',dot<-3)]:
            pp=q[mask]
            if len(pp)<30:continue
            b=least_squares(lambda x:np.linalg.norm(pp-x[:2],axis=1)-x[2],best,loss='soft_l1',f_scale=.12).x
            groups[key]={'transverse_center':float(b[0]),'height_center':float(b[1]),'radius':float(b[2]),
                'rmse':float(np.sqrt(np.mean((np.linalg.norm(pp-b[:2],axis=1)-b[2])**2))),'n':len(pp)}
        ports.append({'axis':'XY'[axis],'sign':sgn,'end_distance':length,'end_plane_faces':len(end),'circles':groups})
    fits['Box']['ports']=ports
    np.savez_compressed(OUT/'Box_aligned.npz',vertices=p,faces=f,colors=colors)
    plot('Box_aligned',p,colors)
    fig,ax=plt.subplots(figsize=(10,6))
    ax.scatter(c[outer,2],r[outer],s=1,label='Outer wall');ax.scatter(c[inner,2],r[inner],s=1,label='Inner wall')
    ax.set_xlabel('Height from outer bottom [mm]');ax.set_ylabel('Radius [mm]');ax.grid(alpha=.2);ax.legend()
    fig.savefig(OUT/'Box_wall_profiles.png',dpi=150);plt.close(fig)
    print('BOX REFINED',json.dumps(fits['Box']),flush=True)
    for zlo,zhi in [(0,3),(3,8),(8,14),(14,22),(22,30)]:
        sel=(p[:,2]>zlo)&(p[:,2]<zhi)
        fig,ax=plt.subplots(figsize=(8,8))
        ax.scatter(p[sel,0],p[sel,1],c=colors[sel]/255,s=.3);ax.set_aspect('equal');ax.grid(alpha=.3)
        ax.set_title(f'Box slice: z={zlo}..{zhi} mm');ax.set_xlim(-53,53);ax.set_ylim(-53,53)
        fig.savefig(OUT/f'Box_slice_{zlo}_{zhi}.png',dpi=140);plt.close(fig)


if __name__=='__main__':
    tower();box();(OUT/'geometry_fits.json').write_text(json.dumps(fits,indent=2))
