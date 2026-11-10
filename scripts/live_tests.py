"""Regression tests for real progress, persistence and restart semantics."""
import json
import os
from pathlib import Path
import sys
import tempfile
import struct
import threading
import time
from dashboard import Trace, trace
from live_output import OutputParser, pump
from live_server import FileTrace, atomic, ensure_service, health
from unittest.mock import patch, MagicMock


def self_test():
    monitor_test()
    # A fixed address must fail explicitly rather than silently move the UI.
    with patch('live_server.health', side_effect=ValueError('another application')), patch('live_server.subprocess.Popen') as spawn:
        try: ensure_service(); assert False, 'occupied address accepted'
        except ValueError as error: assert 'no alternate port' in str(error)
        spawn.assert_not_called()
    connection=MagicMock();connection.getresponse.return_value.status=200
    connection.getresponse.return_value.read.return_value=b'{"project":"another application"}'
    with patch('live_server.http.client.HTTPConnection',return_value=connection):
        try: health(); assert False, 'unrelated service accepted'
        except ValueError: pass
    # Repeated watch/demo runs reuse an automatic opening; explicit ui can reopen.
    from lab import open_browser
    with tempfile.TemporaryDirectory() as tmp, patch('lab.RUNS',Path(tmp)), patch('lab.health',return_value={'pid':123}), patch('lab.shutil.which',return_value='/bin/xdg-open'), patch.dict(os.environ,{'DISPLAY':':0'}), patch('lab.subprocess.Popen') as spawn:
        open_browser('http://127.0.0.1:8765/',once=True)
        open_browser('http://127.0.0.1:8765/',once=True)
        assert spawn.call_count==1
        open_browser('http://127.0.0.1:8765/')
        assert spawn.call_count==2
    model=Trace(); parser=OutputParser('case',model)
    parser.feed('test works ... ')
    assert model.events[0]['action']=='case' and model.events[0]['status']=='info'
    parser.feed('ok\n'); assert any(e['status']=='pass' for e in model.events)
    parser.feed('#1024 pulse cov: 12 exec/s: 44 rss: 32Mb\n');parser.heartbeat(force=True)
    assert '1,024 fuzz' in model.events[-1]['observed']
    parser.feed('test property ... diagnostic from harness\nok\n');assert model.events[-1]['status']=='pass'
    parser.feed('test failing ... diagnostic\nFAILED\n');assert model.events[-1]['status']=='fail'
    parser.feed('x'*100000); assert len(parser.partial)<=16384
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp); run=root/'run';run.mkdir()
        trace_model=Trace(run);pointer=root/'current.json';atomic(pointer,{'directory':str(run)})
        reader=FileTrace(pointer);reader.refresh();assert reader.metadata['id']==trace_model.metadata['id']
        sample=trace('live','send','ciphertext','sent');trace_model.add(sample);reader.refresh();assert reader.events==[sample]
        with (run/'live-events.ndjson').open('a') as file:file.write('{"partial":')
        reader.refresh();assert reader.events==[sample]
        next_run=root/'next';next_run.mkdir();new=Trace(next_run);new.add(trace('next','check','running','Running'))
        atomic(pointer,{'directory':str(next_run)});reader.refresh();assert reader.metadata['id']==new.metadata['id'] and len(reader.events)==1
        observed=Trace();finished=threading.Event();error=[]
        def run_process():
            try:
                result=pump([sys.executable,'-u','-c',"import time;print('test slow ... ',end='',flush=True);time.sleep(1);print('ok',flush=True);time.sleep(1)"],cwd=root,env=os.environ.copy(),logfile=root/'child.log',name='slow',model=observed,timeout=5)
                assert result==0
            except BaseException as exc:error.append(exc)
            finally:finished.set()
        worker=threading.Thread(target=run_process);worker.start();deadline=time.monotonic()+2
        while not observed.events and time.monotonic()<deadline:time.sleep(.01)
        assert not finished.is_set() and any(e['action']=='case' and e['status']=='info' for e in observed.events),'start waited for child exit'
        worker.join(5);assert finished.is_set() and not error,error
        assert any(e['action']=='case' and e['status']=='pass' for e in observed.events)


def monitor_test():
    from audio_monitor import batch, FRAME_BYTES
    with tempfile.TemporaryDirectory() as tmp:
        directory=Path(tmp);(directory/'live').mkdir()
        model=Trace(metadata={'id':'test-run'});model.source_directory=directory
        model.add(trace('live','check','run','Running'))
        # Deliberately non-sinusoidal fixtures verify exact PCM forwarding.
        frames=[struct.pack('<I',slot)+struct.pack('<320h',*([slot-100]*320)) for slot in range(30)]
        (directory/'live/alice-monitor.pcm').write_bytes(b''.join(frames)+b'partial')
        path='/monitor?run=test-run&scenario=live&alice=-1&bob=-1'
        status,headers,body=batch(model,path)
        assert status==200 and headers['X-Alice-Cursor']=='30' and headers['X-Bob-Cursor']=='0'
        assert body==b''.join(b'\0'+frame for frame in frames[-4:])
        status,headers,body=batch(model,path.replace('alice=-1','alice=23'))
        assert body==b''.join(b'\0'+frame for frame in frames[23:])
        assert len(body)<=8*(FRAME_BYTES+1)
        assert batch(model,path.replace('test-run','wrong'))[0]==409
        for invalid in (path.replace('alice=-1','alice=999999'),path+'&file=/etc/passwd',path.replace('alice=-1','alice=x')):
            try:batch(model,invalid);assert False,'invalid query accepted'
            except ValueError:pass
        model.set_phase('timing');assert batch(model,path)[0]==204
        model.set_phase('done');assert batch(model,path)[0]==204
        model.set_phase('live');model.add(trace('live','check','run','completed','pass'))
        assert batch(model,path)[0]==204
