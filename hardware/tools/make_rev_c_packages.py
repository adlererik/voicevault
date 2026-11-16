#!/usr/bin/env python3
"""Serialize manufacturer land-pattern geometry, not PCB component placement.

NXP SOT1969-1 figures 4/5 and TI RNM0015A land-pattern drawing are
the reviewed dimensional sources. Independent native-pad inspection remains
required; these files are not a manufacturing sign-off.
"""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DEST=ROOT/'hardware/rev-c/VoiceVault_B0.pretty'


def pad(n,x,y,w,h,mask=.05,layers='"F.Cu" "F.Paste" "F.Mask"'):
    return (f'(pad "{n}" smd roundrect (at {x} {y}) (size {w} {h}) '
        f'(layers {layers}) (roundrect_rratio 0.15) (solder_mask_margin {mask})'
        + (f' (solder_paste_margin {mask})' if mask<0 else '') + ')')


def polygon_pad(n,center,points):
    x,y=center
    xy=' '.join(f'(xy {round(a-x,6)} {round(b-y,6)})' for a,b in points)
    return (f'(pad "{n}" smd custom (at {x} {y}) (size 0.1 0.1) '
        '(layers "F.Cu" "F.Paste" "F.Mask") (solder_mask_margin -0.05) '
        '(solder_paste_margin -0.05) (options (clearance outline) (anchor rect)) '
        f'(primitives (gr_poly (pts {xy}) (width 0) (fill yes))))')


def write(name,body,half,source):
    text=f'''(footprint "{name}" (version 20241229) (generator "pcbnew")
      (layer "F.Cu") (descr "{source}; dimensional transcription, independent review pending") (attr smd)
      (fp_text reference "REF**" (at 0 {-half-0.7}) (layer "F.SilkS")
        (effects (font (size 0.8 0.8) (thickness 0.12))))
      (fp_text value "{name}" (at 0 {half+0.7}) (layer "F.Fab")
        (effects (font (size 0.6 0.6) (thickness 0.1))))
      (fp_rect (start {-half} {-half}) (end {half} {half})
        (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))
      (fp_circle (center {-half+.15} {-half+.15}) (end {-half+.22} {-half+.15})
        (stroke (width 0.1) (type default)) (fill none) (layer "F.SilkS"))
      {''.join(body)})'''
    (DEST/(name+'.kicad_mod')).write_text(text+'\n')


def main():
    DEST.mkdir(parents=True,exist_ok=True)
    nxp=[]
    for i in range(5):
        z=round(-.8+.4*i,3)
        nxp += [pad(i+1,-1.538,z,.725,.2),pad(i+6,z,1.538,.2,.725),
                pad(i+11,1.538,-z,.725,.2),pad(i+16,-z,-1.538,.2,.725)]
    nxp.append(pad(21,0,0,1.9,1.9,layers='"F.Cu" "F.Mask"'))
    for x in [-.475,.475]:
        for y in [-.475,.475]:nxp.append(pad('',x,y,.75,.75,0,layers='"F.Paste"'))
    write('NXP_SOT1969-1',nxp,2.15,'NXP 98ASA01228D rev A 2019-05-16 figures 4-5')

    ti=[]
    for i in range(4):ti.append(pad(i+1,-1.15,round(-.75+.5*i,3),.6,.25))
    ti += [pad(5,-.725,1.4,.25,.6),pad(6,-.225,1.4,.25,.6),
           pad(14,-.225,-1.4,.25,.6),pad(15,-.725,-1.4,.25,.6),
           pad(9,.775,.5,1.45,.35,-.05),pad(10,.6,0,1.8,.35,-.05),
           pad(11,.775,-.5,1.45,.35,-.05)]
    # 7/8 and 12/13 are same-net paired lands. Copper extends 0.05mm beyond
    # the recommended mask/paste opening, as RNM0015A requires for pads 7-13.
    left=[(.1,1.05),(.45,1.05),(.45,1.4),(.575,1.4),(.575,1.75),(.1,1.75)]
    right=[(.475,1.4),(.6,1.4),(.6,1.05),(.95,1.05),(.95,1.75),(.475,1.75)]
    ti += [polygon_pad(7,(.275,1.4),left),polygon_pad(8,(.775,1.4),right),
           polygon_pad(13,(.275,-1.4),[(x,-y) for x,y in left]),
           polygon_pad(12,(.775,-1.4),[(x,-y) for x,y in right])]
    write('TPS63070_RNM0015A',ti,1.95,'TI RNM0015A 4222000/B 03-2020 land pattern')
    write('Coilcraft_XFL4020',[pad(1,-1.675,0,.98,3.4),pad(2,1.675,0,.98,3.4)],
          2.45,'Coilcraft XFL4020 recommended land pattern: 2.37mm gap, 0.98x3.4mm lands')
    (DEST.parent/'package-geometry.json').write_text(json.dumps({
        'scope':'Component-library land geometry; no PCB placement or routing',
        'NXP_SOT1969-1':{'terminals':20,'ep_number':'21','pitch_mm':.4,
            'land_center_mm':1.538,'perimeter_land_mm':[.725,.2],
            'ep_copper_mm':1.9,'ep_mask_mm':2.0,'ep_paste_windows_mm':[.75,.75],
            'source':'https://www.nxp.com/docs/en/package-information/SOT1969-1.pdf'},
        'Coilcraft_XFL4020':{'terminals':2,'land_mm':[.98,3.4],'gap_mm':2.37,'pitch_mm':3.35,
            'source':'https://www.coilcraft.com/getmedia/50632d43-da1b-4cdb-8ab4-3029cab51df3/xfl4020.pdf'},
        'TPS63070_RNM0015A':{'terminals':15,'paired_same_net_lands':[['7','8'],['12','13']],
            'source':'https://www.ti.com/lit/ds/symlink/tps63070.pdf',
            'review':'Solder-mask-defined power lands transcribed; independent native/assembly review required'}
        },indent=2)+'\n')
    print('Created three package-library definitions; no PCB positions or copper routes changed.')


if __name__=='__main__':main()
