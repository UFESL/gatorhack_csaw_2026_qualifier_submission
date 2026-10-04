from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'deps'))
import json
import numpy as np
import trimesh
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.backends.backend_pdf import PdfPages

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'Team_Name_Submission'
AN=ROOT/'analysis'
PARAM=json.loads((OUT/'CAD/reconstruction_parameters.json').read_text())
REVISED=json.loads((OUT/'CAD/revised_parameters.json').read_text())
RESULTS=json.loads((AN/'revised_results.json').read_text())
VALID=json.loads((AN/'reconstruction_validation.json').read_text())
INK='#233843';ACCENT='#147c83'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.titlesize':11})


def project(ax,m,horizontal,vertical,title,limits=None,dim=True,nominal=None):
    x=np.asarray(horizontal,dtype=float);y=np.asarray(vertical,dtype=float);view=np.cross(x,y)
    tri=m.triangles
    depth=tri.mean(1)@view
    facing=m.face_normals@view>1e-7
    idx=np.flatnonzero(facing);idx=idx[np.argsort(depth[idx])]
    pts=np.stack((tri[idx]@x,tri[idx]@y),axis=-1)
    light=np.array([.3,.5,1.]);light/=np.linalg.norm(light)
    shade=np.clip(.78+.2*(m.face_normals[idx]@light),.55,.98)
    # Mild depth shading makes cavity floors distinguishable from upper rims
    # in orthographic views without altering the geometric projection.
    near_far=m.vertices@view
    depth_fraction=(depth[idx]-near_far.min())/max(np.ptp(near_far),1e-9)
    shade*=.82+.18*depth_fraction
    rgb=np.array([.63,.72,.75])[None,:]*shade[:,None]
    coll=PolyCollection(pts,facecolors=rgb,edgecolors=rgb,linewidths=.08,antialiased=False,rasterized=True)
    ax.add_collection(coll)
    vp=np.column_stack((m.vertices@x,m.vertices@y));low=vp.min(0);high=vp.max(0);span=high-low
    margin=max(span.max()*.16,2)
    ax.set_xlim(low[0]-margin,high[0]+margin*1.4);ax.set_ylim(low[1]-margin,high[1]+margin)
    ax.set_aspect('equal');ax.axis('off');ax.set_title(title,color=INK,pad=8)
    if limits:ax.set_xlim(*limits[0]);ax.set_ylim(*limits[1])
    if dim:
        labels=nominal or [f'{span[0]:.2f}',f'{span[1]:.2f}']
        dimension(ax,(low[0],low[1]),(high[0],low[1]),-margin*.52,labels[0])
        dimension(ax,(high[0],low[1]),(high[0],high[1]),margin*.52,labels[1])
    return low,high


def dimension(ax,a,b,offset,label):
    a=np.array(a,dtype=float);b=np.array(b,dtype=float)
    tangent=(b-a)/np.linalg.norm(b-a);normal=np.array([-tangent[1],tangent[0]])
    # Horizontal dimensions use offset along Y; vertical dimensions along X.
    if abs(tangent[0])>.5:normal=np.array([0,1.])
    else:normal=np.array([1.,0])
    aa=a+offset*normal;bb=b+offset*normal
    for point,tip in [(a,aa),(b,bb)]:ax.plot([point[0],tip[0]],[point[1],tip[1]],color=ACCENT,lw=.6)
    ax.annotate('',xy=aa,xytext=bb,arrowprops={'arrowstyle':'<->','lw':.8,'color':ACCENT,'shrinkA':0,'shrinkB':0})
    mid=(aa+bb)/2
    ax.text(*mid,label,ha='center',va='center',color=ACCENT,fontsize=9,bbox={'facecolor':'white','edgecolor':'none','pad':1})


def page(title,sheet,subtitle):
    fig=plt.figure(figsize=(11.69,8.27))
    fig.text(.05,.94,title,size=16 if len(title)>55 else 18,weight='bold',color=INK)
    fig.text(.05,.903,subtitle,size=9,color='#53656e')
    fig.add_artist(plt.Line2D([.05,.95],[.885,.885],transform=fig.transFigure,color=ACCENT,lw=1))
    fig.text(.05,.04,'CSAW 2026 Hack3D | Reconstruction drawing | Units: mm | Orthographic views | NTS',size=8,color=INK)
    fig.text(.95,.04,f'Sheet {sheet}/4',ha='right',size=8,color=INK)
    return fig


def save(fig,pdf,name):
    pdf.savefig(fig,dpi=200)
    fig.savefig(AN/f'{name}.png',dpi=130)
    plt.close(fig)


def make():
    boat=trimesh.load_mesh(OUT/'CAD/Boat_reconstructed.stl')
    tower=trimesh.load_mesh(OUT/'CAD/Tower_revised.stl')
    box=trimesh.load_mesh(OUT/'CAD/Box_revised.stl')
    with PdfPages(OUT/'Restored_Parts_Drawings.pdf') as pdf:
        fig=page('Boat | 3DBenchy',1,'Material: PLA (explicit file clue). Dimensions below are official nominal dimensions; STL tessellation has micrometre-scale bounds differences.')
        project(fig.add_axes([.06,.31,.40,.24]),boat,[1,0,0],[0,0,1],'Side / longitudinal elevation',nominal=['60.00','48.00'])
        project(fig.add_axes([.56,.55,.27,.29]),boat,[0,1,0],[0,0,1],'Transverse elevation',nominal=['31.00','48.00'])
        project(fig.add_axes([.06,.56,.40,.26]),boat,[1,0,0],[0,1,0],'Plan',nominal=['60.00','31.00'])
        fig.text(.54,.45,'Relevant nominal feature dimensions',size=11,weight='bold',color=INK)
        fig.text(.54,.416,'Chimney: OD Ø7.00; bore Ø3.00; blind depth 11.00\nRoof fore/aft span: 23.00\nFront cabin opening: 10.50 × 9.50\nRear cabin opening: ID Ø9.00; OD Ø12.00\nCargo pocket: 8.00 × 7.00; depth 9.00\nCargo box outside: 12.00 × 10.81\nHawsepipe bore: Ø4.00',size=9,color=INK,va='top',linespacing=1.65)
        fig.text(.06,.14,'Geometry restored from the official single-part 3DBenchy STL after aligning the supplied scan.\nSource: https://www.3dbenchy.com/dimensions/ | CAD author: Creative Tools / Daniel Norée.\nUse the STL for curved hull surfaces and fine lettering; no original parametric history is claimed.',size=9,color=INK,linespacing=1.5)
        save(fig,pdf,'drawing_Boat')

        fig=page('Tower | Revised measured-section loft',2,'Material: 60 vol.% acrylate-based photopolymer resin + 40 vol.% hollow glass microspheres. Lengths assume shared scan units as mm.')
        project(fig.add_axes([.08,.51,.30,.32]),tower,[1,0,0],[0,1,0],'Plan / angular-profile envelope')
        project(fig.add_axes([.49,.27,.28,.55]),tower,[1,0,0],[0,0,1],'X-Z elevation with measured flare')
        fig.text(.08,.38,'Reconstruction basis',weight='bold',size=11,color=INK)
        fig.text(.08,.342,'Reference body diameter: Ø12.496\nEnd-to-end length: 24.260\nMedian flare diameter: Ø13.029 near Z=1.00\n95 loft sections, 72 angular samples each\nPlanar cap endpoints completed at reference radius',size=9,color=INK,va='top',linespacing=1.8)
        fig.text(.08,.14,'Final model: Tower_revised. Sections retain measured angular variation; missing bins use periodic interpolation.\nDimension_Analysis.pdf and Revised_Model_Results.pdf define the profile, completions and scan-fit results.\nMaterial source: https://doi.org/10.1016/j.compositesa.2025.109248 and Tower.ply line 19.',size=9,color=INK,linespacing=1.6)
        save(fig,pdf,'drawing_Tower')

        fig=page('Box | Four-port electrical junction body',3,'Estimated scan reconstruction. Nominal material: 70 wt.% HDPE + 30 wt.% fly-ash cenospheres (surface label and linked-paper inference).')
        project(fig.add_axes([.05,.41,.42,.42]),box,[1,0,0],[0,1,0],'Open chamber / plan')
        project(fig.add_axes([.53,.58,.41,.24]),box,[1,0,0],[0,0,1],'X-Z elevation')
        project(fig.add_axes([.53,.30,.41,.24]),box,[0,1,0],[0,0,1],'Y-Z elevation')
        fig.text(.06,.27,'Core dimensions (fitted / idealized)',weight='bold',size=11,color=INK)
        p=REVISED['Box']
        fig.text(.06,.237,f'Outside D at Z=0: Ø{2*p["outer_radius_at_z_zero_mm"]:.3f}\nInside reference D at Z=0: Ø{2*p["inner_radius_at_z_zero_mm"]:.3f}\nFloor at body center: Z={p["floor_center_height_mm"]:.3f}\nMinimum completed floor: 1.00 (assumed)\nRim height at body center: {p["rim_center_height_mm"]:.2f}',size=9,color=INK,va='top',linespacing=1.6)
        fig.text(.52,.237,'Four sockets: common OD Ø23.00; bore Ø20.00 (inferred)\nTwo mounting bosses; openings Ø3.70 (first inferred by symmetry)\nPort positions and the slanted rim follow the measured scan.\nBounding dimensions include inclined sockets below Z=0.',size=9,color=INK,va='top',linespacing=1.6)
        fig.text(.06,.085,'Final model: Box_revised. Tapered walls and bounded sloped floor; Z=0 is the outside-bottom datum. Feature definitions: sheet 4.',size=8,color=INK)
        save(fig,pdf,'drawing_Box')

        fig=page('Box | Feature definition and reconstruction assumptions',4,'All dimensions in mm. Numerical feature locations define the supplied CAD; uncertain internals are explicitly identified.')
        ax=fig.add_axes([.05,.22,.47,.62]);ax.axis('off')
        lines=['Feature                         Dimension / location',
            f'Outside R(Z)                   {p["outer_radius_at_z_zero_mm"]:.6f}',
            f'                               {p["outer_radius_slope"]:+.6f} * Z',
            f'Inside R(Z)                    {p["inner_radius_at_z_zero_mm"]:.6f}',
            f'                               {p["inner_radius_slope"]:+.6f} * Z',
            f'Outside bottom plane           Z = 0.00',
            'Floor Z = max(1.00, floor-plane height) *',
            f'Floor plane n = {p["floor_plane_normal"][0]:.6f},',
            f'  {p["floor_plane_normal"][1]:.6f}, {p["floor_plane_normal"][2]:.6f}',
            f'Floor plane offset = {p["floor_plane_offset_mm"]:.6f}',
            'Socket bore / exterior         Ø20.00 / Ø23.00 *',
            'Boss 1 center                  X=-16.90, Y=16.41',
            f'Boss 1 exterior                Ø{2*p["bosses"][0]["outer_radius"]:.2f}',
            'Boss 2 center                  X=17.75, Y=-16.55',
            f'Boss 2 exterior                Ø{2*p["bosses"][1]["outer_radius"]:.2f}',
            'Both boss openings             Ø3.70 *',
            'Both blind-hole bottoms        Z = 7.00 *',
            '',
            'Rim plane (retained from scan):',
            f'{p["rim_plane_normal"][0]:.6f} X + {p["rim_plane_normal"][1]:.6f} Y +',
            f'{p["rim_plane_normal"][2]:.6f} Z = {p["rim_plane_offset_mm"]:.6f}',
            '',
            '* Floor minimum, socket diameters and hole depth',
            '  complete missing regions; first bore uses symmetry.']
        ax.text(0,1,'\n'.join(lines),fontfamily='DejaVu Sans Mono',fontsize=7.7,va='top',linespacing=1.55,color=INK)
        ax2=fig.add_axes([.55,.30,.41,.53]);ax2.axis('off')
        rows=[]
        for po in p['ports']:
            e=po['end_center'];direction=po['direction']
            rows.append([po['axis']+('+' if po['sign']>0 else '-'),f'{e[0]:.2f}',f'{e[1]:.2f}',f'{e[2]:.2f}'])
        table=ax2.table(cellText=rows,colLabels=['Port','End X','End Y','End Z'],loc='upper center',cellLoc='center')
        table.auto_set_font_size(False);table.set_fontsize(9);table.scale(1,1.7)
        ax2.text(0,.49,'Port axes (unit vectors, outward)',fontsize=10,weight='bold',color=INK)
        for i,po in enumerate(p['ports']):
            label=po['axis']+('+' if po['sign']>0 else '-')
            ax2.text(0,.43-i*.064,label+'  '+', '.join(f'{x:+.6f}' for x in po['direction']),fontsize=8.3,fontfamily='DejaVu Sans Mono',color=INK)
        ax2.text(0,.08,'Each CAD socket starts 24 mm inward from its\nend center; its bore extends 28 mm inward.\nThe chamber intersection determines exposed\nsocket length. Full values are in the parameter JSON.',fontsize=9,color=INK,linespacing=1.6)
        fig.text(.06,.15,'Measured wall/floor/rim trends are retained. Missing floor uses an assumed 1.00-mm minimum; internal bores are clipped to protect it.\nHidden transitions, original fillet radii and blind-hole depths remain unresolved. Full data and results: Revised_Model_Results.pdf.',fontsize=9,color=INK,linespacing=1.6)
        save(fig,pdf,'drawing_Box_features')

    # A clean overview for the report; view axes are derived from the same meshes.
    fig,axes=plt.subplots(1,3,figsize=(15,5),layout='constrained')
    view_x=np.array([.7071,-.7071,0]);view_y=np.array([.4082,.4082,.8165])
    for ax,name,mesh in zip(axes,['Boat','Tower','Box'],[boat,tower,box]):
        project(ax,mesh,view_x,view_y,name,dim=False)
    fig.savefig(AN/'reconstructed_overview.png',dpi=160);plt.close(fig)


if __name__=='__main__':make()
