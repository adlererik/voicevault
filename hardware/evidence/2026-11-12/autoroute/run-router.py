import subprocess,json,time,hashlib
from pathlib import Path
r=Path.cwd();d=r/'.lab-cache/hardware/freerouting-live';jar=d/'freerouting-2.5.0.jar';assert hashlib.sha256(jar.read_bytes()).hexdigest()=='f6f51bb02245e8e717f9359bd260cc9c5c0b1bc0acc8b7cb2cd5b8ffeb5de3c7'
args=['systemd-run','--user','--scope','--quiet','--unit=voicevault-freerouting-live','-p','MemoryMax=1000M','-p','MemorySwapMax=128M','-p','CPUQuota=150%','java','-Xms128m','-Xmx640m','-XX:MaxMetaspaceSize=128m','-XX:ActiveProcessorCount=2','-Djava.awt.headless=true','-jar',str(jar),f'--user_data_path={d/"user"}','--gui.enabled=false','-de',str(d/'voicevault.dsn'),'-do',str(d/'voicevault.ses')]
(d/'command.json').write_text(json.dumps(args,indent=2)+'\n');start=time.monotonic()
with (d/'terminal.log').open('w') as log:
 result=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT)
summary=dict(exit_code=result.returncode,elapsed_seconds=round(time.monotonic()-start,2),ses_exists=(d/'voicevault.ses').is_file(),jar_sha256=hashlib.sha256(jar.read_bytes()).hexdigest())
(d/'run-result.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
