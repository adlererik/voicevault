#!/usr/bin/env python3
"""Read-only native identity/geometry gate for a returned Quilter board.

Run with KiCad's bundled Python. Passing this gate does not qualify routing:
original-rule refill/DRC, laser geometry and electrical review remain required.
"""
import argparse,collections,hashlib,json
from pathlib import Path
import pcbnew


def fingerprint(f):
    return dict(value=f.GetValue(),library=str(f.GetFPID().GetLibNickname())+':'+str(f.GetFPID().GetLibItemName()),
        pose=[f.GetPosition().x,f.GetPosition().y,f.GetOrientationDegrees()%360,f.GetLayer()],
        pads=sorted((p.GetNumber(),p.GetNetname(),p.GetPosition().x,p.GetPosition().y,
            p.GetSize().x,p.GetSize().y,p.GetDrillSize().x,p.GetDrillSize().y,
            int(p.GetShape()),int(p.GetAttribute()),tuple(p.GetLayerSet().Seq())) for p in f.Pads()))


def copper_key(t):
    q=lambda n:round(n/100)
    pt=lambda v:(q(v.x),q(v.y))
    if isinstance(t,pcbnew.PCB_VIA):
        return ('via',t.GetNetname(),pt(t.GetPosition()),q(t.GetWidth(t.TopLayer())),q(t.GetDrillValue()),int(t.TopLayer()),int(t.BottomLayer()))
    ends=tuple(sorted((pt(t.GetStart()),pt(t.GetEnd()))))
    if isinstance(t,pcbnew.PCB_ARC):return ('arc',t.GetNetname(),int(t.GetLayer()),q(t.GetWidth()),ends,pt(t.GetMid()))
    return ('track',t.GetNetname(),int(t.GetLayer()),q(t.GetWidth()),ends)


def outline_key(board):
    q=lambda n:round(n/100)
    pt=lambda v:(q(v.x),q(v.y))
    return sorted((int(g.GetShape()),tuple(sorted((pt(g.GetStart()),pt(g.GetEnd())))))
        for g in board.GetDrawings() if g.GetLayer()==pcbnew.Edge_Cuts)


def inspect(source,candidate):
    before={f.GetReference():fingerprint(f) for f in source.GetFootprints()}
    after={f.GetReference():fingerprint(f) for f in candidate.GetFootprints()}
    failures=[]
    if before.keys()!=after.keys():failures.append(dict(check='component references',missing=sorted(before.keys()-after.keys()),extra=sorted(after.keys()-before.keys())))
    for ref in sorted(before.keys()&after.keys()):
        a,z=before[ref],after[ref]
        for field in ['value','library']:
            if a[field]!=z[field]:failures.append(dict(check=field,component=ref))
        if a['pose'][2:]!=z['pose'][2:] or any(abs(x-y)>100 for x,y in zip(a['pose'][:2],z['pose'][:2])):failures.append(dict(check='placement',component=ref))
        if len(a['pads'])!=len(z['pads']):failures.append(dict(check='pad count',component=ref));continue
        for p,q in zip(a['pads'],z['pads']):
            if p[:2]!=q[:2] or p[8:]!=q[8:] or any(abs(x-y)>100 for x,y in zip(p[2:8],q[2:8])):failures.append(dict(check='pad identity/net/geometry',component=ref,pin=p[0]))
    # This is an identity gate; exact original antenna boundaries must survive.
    def areas(board):
        rows=[]
        for z in board.Zones():
            if not z.GetIsRuleArea():continue
            poly=z.Outline();contours=[]
            for i in range(poly.OutlineCount()):
                c=poly.COutline(i);contours.append(tuple((c.CPoint(j).x,c.CPoint(j).y) for j in range(c.PointCount())))
            rows.append((z.GetZoneName(),tuple(z.GetLayerSet().Seq()),z.GetDoNotAllowTracks(),z.GetDoNotAllowVias(),z.GetDoNotAllowZoneFills(),tuple(contours)))
        return sorted(rows)
    if areas(source)!=areas(candidate):failures.append(dict(check='exact antenna rule areas',action='Review and restore trusted native reservations before proceeding'))
    if source.GetCopperLayerCount()!=candidate.GetCopperLayerCount():failures.append(dict(check='copper layer count'))
    if outline_key(source)!=outline_key(candidate):failures.append(dict(check='board outline'))
    original_copper=collections.Counter(copper_key(x) for x in source.GetTracks())
    actual_copper=collections.Counter(copper_key(x) for x in candidate.GetTracks())
    missing=original_copper-actual_copper
    if missing:failures.append(dict(check='protected input copper',missing_items=sum(missing.values()),action='Review split/merged or changed geometry before any acceptance'))
    original_vias={copper_key(x) for x in source.GetTracks() if isinstance(x,pcbnew.PCB_VIA)}
    known_nets={p.GetNetname() for f in source.GetFootprints() for p in f.Pads() if p.GetNetname()}
    for t in candidate.GetTracks():
        if not t.GetNetname() or t.GetNetname() not in known_nets:failures.append(dict(check='unknown copper net',net=t.GetNetname()))
        if isinstance(t,pcbnew.PCB_VIA) and copper_key(t) not in original_vias:
            if t.GetViaType()!=pcbnew.VIATYPE_THROUGH or (t.TopLayer(),t.BottomLayer())!=(pcbnew.F_Cu,pcbnew.B_Cu):failures.append(dict(check='unexpected new via span/process',net=t.GetNetname()))
    return dict(result='fail' if failures else 'pass',failures=failures,components=len(after),pads=sum(len(x['pads']) for x in after.values()),tolerance_nm=100,
        original_copper_items=sum(original_copper.values()),candidate_copper_items=sum(actual_copper.values()),

        scope='Footprint/pad/net/placement/antenna/outline and protected-copper identity; not full copper/electrical/manufacturing qualification',manufacturing_ready=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--self-check',action='store_true');a=p.parse_args()
    sb=pcbnew.LoadBoard(str(a.source.resolve()));cb=pcbnew.LoadBoard(str(a.candidate.resolve()));result=inspect(sb,cb)
    if a.self_check:
        assert not inspect(sb,sb)['failures'],'Positive control failed'
        pad=next(p for f in cb.GetFootprints() for p in f.Pads() if p.GetNetname() and p.GetNumber());old=pad.GetNetCode();pad.SetNetCode(0)
        assert any(x['check']=='pad identity/net/geometry' for x in inspect(sb,cb)['failures']),'Substituted pad net was not detected'
        pad.SetNetCode(old)
        area=next(z for z in cb.Zones() if z.GetIsRuleArea());flag=area.GetDoNotAllowTracks();area.SetDoNotAllowTracks(not flag)
        assert any(x['check']=='exact antenna rule areas' for x in inspect(sb,cb)['failures']),'Antenna rule mutation missed'
        area.SetDoNotAllowTracks(flag)
        track=next(iter(cb.GetTracks()));cb.Remove(track)
        assert any(x['check']=='protected input copper' for x in inspect(sb,cb)['failures']),'Missing fixed copper missed'
        cb.Add(track);cb.BuildConnectivity()
        result['negative_controls']=['In-memory pad-net substitution detected','Antenna restriction mutation detected','Removed protected copper detected'];result['controls_restore_without_saving']=True
    result.update(source_sha256=hashlib.sha256(a.source.read_bytes()).hexdigest(),candidate_sha256=hashlib.sha256(a.candidate.read_bytes()).hexdigest())
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));return bool(result['failures'])

if __name__=='__main__':raise SystemExit(main())
