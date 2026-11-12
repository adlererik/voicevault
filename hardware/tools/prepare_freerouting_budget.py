#!/usr/bin/env python3
"""Prepare a local, explicitly modified Freerouting study JAR.

Pins the original upstream archive hash and changes one connection-search budget
constant from 100000ms to 250ms. This does not make routes valid or manufacturing
ready. Fanout budgets are separate, and effective settings must be observed.
Only files under the ignored local cache are written.
"""
from zipfile import ZipFile
from pathlib import Path
import struct, hashlib,json
r=Path(__file__).resolve().parents[2];base=r/'.lab-cache/hardware/freerouting-2.5.0/freerouting.jar';out=r/'.lab-cache/hardware/routing-b0/freerouting-budget250.jar'
assert hashlib.sha256(base.read_bytes()).hexdigest()=='f6f51bb02245e8e717f9359bd260cc9c5c0b1bc0acc8b7cb2cd5b8ffeb5de3c7'
name='app/freerouting/autoroute/pipeline/AutorouteConnectionRouter.class'
with ZipFile(base) as z:
 b=bytearray(z.read(name));n=struct.unpack_from('>H',b,8)[0];i=1;p=10;replaced=[]
 while i<n:
  t=b[p];p+=1
  if t==1:s=struct.unpack_from('>H',b,p)[0];p+=2+s
  elif t in (3,4):p+=4
  elif t in (5,6):
   if t==6 and struct.unpack_from('>d',b,p)[0]==100000.0:
    replaced.append(p);struct.pack_into('>d',b,p,250.0)
   p+=8;i+=1
  elif t in (7,8,16,19,20):p+=2
  elif t in (9,10,11,12,17,18):p+=4
  elif t==15:p+=3
  else:raise ValueError(t)
  i+=1
 assert len(replaced)==1,replaced
 with ZipFile(out,'w') as o:
  for entry in z.infolist():o.writestr(entry,bytes(b) if entry.filename==name else z.read(entry.filename))
record={'upstream_sha256':hashlib.sha256(base.read_bytes()).hexdigest(),'modified_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'modified_class':name,'single_double_constant_change':{'from_ms':100000,'to_ms':250},'purpose':'Bound connection search in local exploratory routing; not an upstream release or a physical qualification','source':'https://github.com/freerouting/freerouting/blob/v2.5.0/src/main/java/app/freerouting/autoroute/pipeline/AutorouteConnectionRouter.java'}
(out.parent/'budget-patch.json').write_text(json.dumps(record,indent=2)+'\n');print(record)
