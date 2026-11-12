#!/usr/bin/env python3
"""Place the unrouted B0 draft with explicit interface/keepout constraints.

This is a courtyard floorplan, not a routed or manufacturable release. Component
heights, flex bends, RF tuning and actual stackup still need review.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / 'hardware/rev-b'
BOARD = DESIGN / 'voicevault-standalone-b0.kicad_pcb'
CACHE = ROOT / '.lab-cache/hardware/placement-b0'
CAD = ['flatpak', 'run', '--user', '--command=python3', 'org.kicad.KiCad']


def native(mode):
    import pcbnew
    board = pcbnew.LoadBoard(str(BOARD))
    assert not list(board.GetTracks()) and not list(board.Zones()), 'Never erase routed work.'
    def signature():
        return sorted((fp.GetReference(), p.GetNumber(), p.GetNetname())
                      for fp in board.GetFootprints() for p in fp.Pads())
    before = signature()
    if mode == 'export':
        result = {}
        for fp in board.GetFootprints():
            original = fp.GetOrientationDegrees()
            original_back = fp.GetLayer() == pcbnew.B_Cu
            states = {}
            drills = {}
            for back in [False, True]:
                if (fp.GetLayer() == pcbnew.B_Cu) != back:
                    fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
                boxes = {}
                for angle in [0, 90, 180, 270]:
                    fp.SetOrientationDegrees(angle)
                    box = fp.GetBoundingBox(False, False)
                    pos = fp.GetPosition()
                    boxes[str(angle)] = [round(v / 1e6, 5) for v in
                        [box.GetLeft()-pos.x, box.GetTop()-pos.y, box.GetRight()-pos.x, box.GetBottom()-pos.y]]
                    drills[f'{back}-{angle}'] = [
                        [(pad.GetPosition().x-pos.x)/1e6, (pad.GetPosition().y-pos.y)/1e6,
                         pad.GetSize().x/1e6, pad.GetSize().y/1e6]
                        for pad in fp.Pads() if pad.GetDrillSize().x > 0]
                states['back_boxes' if back else 'boxes'] = boxes
            if (fp.GetLayer() == pcbnew.B_Cu) != original_back:
                fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
            fp.SetOrientationDegrees(original)
            result[fp.GetReference()] = dict(**states, drills=drills, value=fp.GetValue())
        (CACHE / 'geometry.json').write_text(json.dumps(result, indent=2)+'\n')
        return
    poses = json.loads((CACHE / 'poses.json').read_text())
    assert set(poses) == {f.GetReference() for f in board.GetFootprints()}
    for fp in board.GetFootprints():
        pose = poses[fp.GetReference()]
        back = pose['back']
        if (fp.GetLayer() == pcbnew.B_Cu) != back:
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetOrientationDegrees(pose['angle'])
        if 'origin' in pose:
            x, y = pose['origin']
        else:
            box = fp.GetBoundingBox(False, False)
            pos = fp.GetPosition()
            x = pose['left'] - (box.GetLeft()-pos.x)/1e6
            y = pose['top'] - (box.GetTop()-pos.y)/1e6
        fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
        # Dense reference designators remain available on assembly/Fab layers.
        fp.Reference().SetLayer(pcbnew.B_Fab if back else pcbnew.F_Fab)
        fp.Reference().SetVisible(True)
        fp.Value().SetLayer(pcbnew.B_Fab if back else pcbnew.F_Fab)
        fp.Value().SetVisible(False)
    for drawing in board.GetDrawings():
        if isinstance(drawing, pcbnew.PCB_TEXT):
            drawing.SetLayer(pcbnew.Dwgs_User)
    assert signature() == before, 'Placement altered a pad/net assignment.'
    board.BuildConnectivity()
    pcbnew.SaveBoard(str(BOARD), board)
    print(f'Placed {len(poses)} footprints; every pad/net assignment preserved.')


def pack():
    from rectpack.maxrects import MaxRectsBssf
    from rectpack.geometry import Rectangle
    geometry = json.loads((CACHE/'geometry.json').read_text())
    circuit = json.loads((DESIGN/'circuits.json').read_text())
    pages = {part['ref']: page['name'] for page in circuit['pages'] for part in page['parts']}
    # Interfaces remain physically accessible on a serviceable prototype.
    fixed = {
        'U1': (58,47,0,False), 'U6': (42,34,0,False),
        'X201': (38.3,35,0,False), 'X202': (46,33,0,False),
        'X301': (49.5,52,0,False), 'X302': (50,39,0,False),
        'U601': (43,48,0,False), 'C611': (43,55,0,False), 'C612': (43,61,0,False),
        'U3': (51,58.7,0,False), 'L1': (59,54.8,0,False),
        'L2': (55,58.7,0,False), 'L8': (51,55.6,0,False),
        # Keep secure elements out of the MCU's rear-side via escape field.
        'U5': (47,55.5,0,True), 'U11': (73,45,0,True), 'U8': (65.8,45,0,True),
        'U7': (84,56,0,True), 'U10': (86,44.5,0,False),
        'U201': (44.5,35,0,True), 'U202': (53,35,0,True),
        'U402': (73,54,0,True), 'U1002': (71.1,38,0,True), 'U1003': (79.6,38,0,True),
        'J101': (61,56,0,True), 'J102': (43,45,0,True),
        'J401': (86,55.7,0,False), 'J501': (56,65.4,0,False),
        'J601': (32,67.7,90,False), 'J701': (67,28.6,0,False), 'J702': (87.2,28.6,0,False),
        'J502': (38,64.2,0,True), 'J503': (35,48,0,True),
        'J901': (28.2,61.5,90,True), 'J902': (28.2,55.3,90,True),
        'J801': (85.4,40,0,False), 'J1001': (91.5,38,0,False),
        'SW301': (88,31,0,True), 'SW302': (86.7,38.5,90,True),
        'SW503': (28.1,36.66,90,False), 'SW601': (30.1,46.6,90,False),
    }
    # Move the lower-left mounting boss clear of the bottom-facing audio jack.
    hole_xy = {'H1':(46,28),'H2':(92,44),'H3':(46,67),'H4':(74,67)}
    fixed.update({ref:(*xy,0,False) for ref,xy in hole_xy.items()})
    fixed['AE201'] = (28,27.5,180,False)
    x0,y0,width,height = 25.4,25.4,69.2,44.2
    bins = [MaxRectsBssf(width,height,rot=True), MaxRectsBssf(width,height,rot=True)]
    used = [[],[]]; poses = {}; margin=.08
    def reserve(side, x,y,w,h,ref):
        rect=Rectangle(x-x0,y-y0,w,h)
        if rect.left < -1e-5 or rect.bottom < -1e-5 or rect.right > width+1e-5 or rect.top > height+1e-5:
            raise RuntimeError(f'Fixed interface outside usable outline: {ref} {x,y,w,h}')
        for previous,name in used[side]:
            if rect.intersects(previous) and not (name==ref or name.startswith(ref+'-hole')):
                raise RuntimeError(f'Fixed courtyard overlap: {ref} / {name}')
        bins[side]._split(rect); bins[side]._remove_duplicates(); used[side].append((rect,ref))
    for side in [0,1]:
        reserve(side,25.4,25.4,13.5,6.5,'BLE-ground-clearance')
        for ref,(x,y) in hole_xy.items():reserve(side,x-2.6,y-2.6,5.2,5.2,ref)
    for ref,(x,y,angle,back) in fixed.items():
        if ref.startswith('H'):continue
        for dx,dy,w,h in geometry[ref]['drills'][f'{back}-{angle}']:
            reserve(1-int(back), x+dx-w/2-.1, y+dy-h/2-.1, w+.2, h+.2, ref+'-hole')
    for ref,(x,y,angle,back) in fixed.items():
        assert ref in geometry, ref
        poses[ref]=dict(origin=[x,y],angle=angle,back=back)
        if ref.startswith('H') or ref=='AE201':continue
        l,t,r,b=geometry[ref]['back_boxes' if back else 'boxes'][str(angle)]
        # Mirroring does not change dimensions; the native apply phase computes
        # the exact mirrored offset for automatically placed parts.
        reserve(int(back),x+l-margin,y+t-margin,r-l+2*margin,b-t+2*margin,ref)
    anchors={'power':('U3',False),'secure':('U11',True),'radio':('U6',False),
             'radio-interface':('U201',True),'control':('U1',False),
             'microsd':('U402',True),'power-entry':('U3',True),
             'audio-codec':('U601',False),'audio-power':('U601',False),'headset':('U601',False),
             'display':('J701',False),'backlight':('U9',False),'haptic':('U10',False),
             'qi':('U5',True),'qi-control':('U5',True),'nfc':('U7',True),
             'nfc-matching':('U7',True),'nfc-interface':('U1002',True)}
    # Missing anchor chips are placed first, then large parts before small ones.
    remaining=[ref for ref in geometry if ref not in poses]
    def area(ref):
        l,t,r,b=geometry[ref]['boxes']['0'];return (r-l)*(b-t)
    remaining.sort(key=lambda ref:(not ref.startswith(('U','Q')), -area(ref)))
    for ref in remaining:
        anchor, preferred=anchors.get(pages.get(ref,''),('U1',True))
        if ref in ['C27','C107','C22','C23','C24']:anchor,preferred='L1',False
        if ref in ['C201','C202']:anchor,preferred='X201',False
        if ref in ['C210','C211']:anchor,preferred='X202',False
        if ref in ['C301','C302']:anchor,preferred='X301',False
        if ref in ['C303','C304']:anchor,preferred='X302',False
        if ref in ['C91','C92','Q2','R19','R20','R21','R22','R106','C120']:anchor,preferred='U8',True
        a=poses.get(anchor,poses['U1']);ax,ay=a.get('origin',[a.get('left',58),a.get('top',47)])
        options=[]
        for side,bin_ in enumerate(bins):
            for angle in [0,90]:
                l,t,r,b=geometry[ref]['boxes'][str(angle)];w,h=r-l+2*margin,b-t+2*margin
                for free in bin_._max_rects:
                    if w>free.width or h>free.height:continue
                    for x,y in [(free.left,free.bottom),(free.right-w,free.bottom),(free.left,free.top-h),(free.right-w,free.top-h)]:
                        dist=(x+x0+w/2-ax)**2+(y+y0+h/2-ay)**2
                        score=dist+(0 if side==int(preferred) else 120)+.01*(free.width*free.height-w*h)
                        options.append((score,side,angle,x,y,w,h))
        if not options:raise RuntimeError('No legal courtyard space for '+ref)
        _,side,angle,x,y,w,h=min(options)
        rect=Rectangle(x,y,w,h);bins[side]._split(rect);bins[side]._remove_duplicates();used[side].append((rect,ref))
        poses[ref]=dict(left=x+x0+margin,top=y+y0+margin,angle=angle,back=bool(side))
    (CACHE/'poses.json').write_text(json.dumps(poses,indent=2)+'\n')
    print(f'Floorplan proposal: {len(poses)} footprints, {sum(p["back"] for p in poses.values())} on rear.')


def main():
    p=argparse.ArgumentParser();p.add_argument('--native',choices=['export','apply']);args=p.parse_args()
    CACHE.mkdir(parents=True,exist_ok=True)
    if args.native:return native(args.native)
    from kipy import KiCad
    client=KiCad(socket_path='ipc://'+str(Path.home()/'.var/app/org.kicad.KiCad/cache/vv-pcb/kicad/api.sock'),timeout_ms=5000)
    board=client.get_board()
    assert (Path(board.document.project.path)/board.name).resolve()==BOARD
    assert not board.get_tracks() and not board.get_vias() and not board.get_zones(), 'Preserve routed work.'
    board.save()
    backup=CACHE/('backup-'+datetime.now().strftime('%Y%m%d-%H%M%S'));backup.mkdir()
    shutil.copyfile(BOARD,backup/BOARD.name)
    subprocess.run(CAD+[str(Path(__file__).resolve()),'--native','export'],check=True)
    pack()
    subprocess.run(CAD+[str(Path(__file__).resolve()),'--native','apply'],check=True)
    board.revert()
    print('Open KiCad editor reloaded. This is a floorplan; routing and physical/DFM checks remain open.')

if __name__=='__main__':main()
