#!/usr/bin/env python3
"""Package tracked B0 sources for feasibility review, never an assembly order."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[2]
DESIGN=ROOT/'hardware/rev-b'
OUT=ROOT/'.lab-runs/hardware/exports/VoiceVault-B0-JLCPCB-feasibility-NOT-FOR-ORDER.zip'


def main():
    status=json.loads((DESIGN/'STATUS.json').read_text())
    if status['manufacturing_ready']:
        raise SystemExit('This preflight workflow is for an unreleased design; use the reviewed release workflow instead.')
    report_path=ROOT/'hardware/evidence/2026-11-12/report.json'
    report=json.loads(report_path.read_text())
    layout=next(c for c in report['checks'] if c['check']=='Draft electrical/layout state')
    if (status['unrouted_connections']!=layout['unrouted'] or
            status['routed_tracks_or_vias']!=layout['tracks_and_vias']):
        raise SystemExit('Status and checked native routing counts disagree.')
    for name,expected in report['source_hashes'].items():
        if hashlib.sha256((DESIGN/name).read_bytes()).hexdigest()!=expected:
            raise SystemExit('Checked snapshot is stale: '+name)
    tracked=subprocess.check_output(['git','ls-files','-z','--','hardware/rev-b','hardware/tools',
        'hardware/evidence/2026-11-12','hardware/reference/tools.json','hardware/README.md',
        'hardware/requirements-mcp.txt','hardware/requirements-design.txt','hardware/mcp','hardware/open','hardware/check'],cwd=ROOT)
    names=sorted(n.decode() for n in tracked.split(b'\0') if n)
    if any(Path(n).suffix.lower() in ['.gbr','.gtl','.gbl','.drl','.pos'] for n in names):
        raise SystemExit('Manufacturing exports do not belong in this preflight bundle.')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    stamp=int(subprocess.check_output(['git','show','-s','--format=%ct','HEAD'],cwd=ROOT,text=True))
    root_name='VoiceVault-B0-FEASIBILITY-ONLY'
    checksums={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
    readme=f'''VOICEVAULT B0 — FEASIBILITY / SOURCING REVIEW ONLY

NOT A MANUFACTURING ORDER. DO NOT FABRICATE OR ASSEMBLE FROM THIS BUNDLE.

This contains native KiCad circuit/placement sources, current component
requirements, source notices and scoped model/check evidence. There is no
manufacturing Gerber/drill/CPL release and no authorization to order parts.

Current design: 296 electrical components, 14 probe pads, four mounting holes,
provisional 70 x 45mm / six layers / 1.0mm. {status['unrouted_connections']} connections remain unrouted.
Draft copper contains {status['routed_tracks_or_vias']} track/via items; routing is incomplete.
Exact component variants, HDI stackup/pad process and procurement acceptance
are incomplete. Nothing here proves physical function or device security.

Start with hardware/rev-b/JLCPCB_SOURCING_REQUEST.md and README.md.
Please confirm feasible HDI construction and exact core-part availability,
with no automatic substitutions, before final routing. Distinguish populated
PCB assembly from display/coil/actuator/NTC/harness/battery/enclosure work.

Open hardware/rev-b/voicevault-standalone-b0.kicad_pro to inspect the CAD.
SHA256SUMS.json records every selected source file. Native CAD hashes also
appear in the dated evidence report. The source checkout commit is recorded
in BUNDLE.json. Upstream and component-library licenses remain applicable.
'''
    metadata=dict(purpose='FEASIBILITY REVIEW ONLY - NOT FOR ORDER',source_checkout_commit=commit,
                  source_file_count=len(names),manufacturing_ready=False,
                  reported_unrouted_connections=status['unrouted_connections'],
                  requested_completed_prototypes=4,destination_country='Sweden',
                  purchases_authorized=False,order_submission_authorized=False,
                  limitations=report['blockers'])
    date=datetime.fromtimestamp(stamp,timezone.utc).timetuple()[:6]
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        def put(name,data,executable=False):
            info=zipfile.ZipInfo(root_name+'/'+name,date_time=date)
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(0o100755 if executable else 0o100644)<<16
            archive.writestr(info,data)
        for name in names:put(name,(ROOT/name).read_bytes(),bool((ROOT/name).stat().st_mode & 0o111))
        put('READ-ME-FIRST.txt',readme.encode())
        put('BUNDLE.json',(json.dumps(metadata,indent=2)+'\n').encode())
        put('SHA256SUMS.json',(json.dumps(checksums,indent=2)+'\n').encode())
    with zipfile.ZipFile(OUT) as archive:
        if archive.testzip() is not None:raise RuntimeError('Archive integrity check failed')
        for name,expected in checksums.items():
            if hashlib.sha256(archive.read(root_name+'/'+name)).hexdigest()!=expected:
                raise RuntimeError('Archive source checksum mismatch')
    print(OUT)
    print(f'{OUT.stat().st_size:,} bytes; {len(names)} tracked source/evidence files; archive and checksums verified.')


if __name__=='__main__':main()
