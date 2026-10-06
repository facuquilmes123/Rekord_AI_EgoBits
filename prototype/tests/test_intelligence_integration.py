import json
from pathlib import Path
import socket
import struct
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock,patch
from egobits.core.models import PlanningError
from egobits.core.toolbox import execute,run_agent,direct
from egobits.telemetry.prodj_link import ProDjLink,decode,simulated_status,MAGIC
from egobits.adapters.anlz_relocate import relocate,tags
from egobits.desktop.analysis_jobs import AnalysisJobs
from test_collection_intelligence import IntelligenceTests


class ToolboxTests(IntelligenceTests):
    def test_bounded_chain_uses_real_query_ids_and_rejects_writes(self):
        lib=self.provider.load();client=Mock()
        client.generate_tool_step.side_effect=[{'tool':'collection.query','arguments':'{"min_rating":4}'},
            {'tool':'set.plan_selection','arguments':'{"track_ids":["1"],"count":1}'},{'tool':'finish','arguments':'{}'}]
        answer=run_agent(lib,'select and plan',client)
        self.assertEqual(answer['plan_result']['track_ids'],['1']);self.assertEqual(len(answer['tool_trace']),2)
        self.assertFalse(answer['applied']);self.assertEqual(client.generate_tool_step.call_count,2)
        with self.assertRaises(PlanningError):execute(lib,'playlist.apply_native',{})
        with self.assertRaises(PlanningError):execute(lib,'collection.query',{'sql':'DROP TABLE'})
        self.assertEqual(direct(lib,'pistas sin reproducir con 4 estrellas')['result']['total'],1)

    def test_cancel_and_duplicate_steps_stop(self):
        lib=self.provider.load();client=Mock();event=threading.Event();event.set()
        run_agent(lib,'q',client,cancelled=event);client.generate_tool_step.assert_not_called()
        client.generate_tool_step.return_value={'tool':'collection.tags','arguments':'{}'}
        result=run_agent(lib,'q',client);self.assertEqual(len(result['tool_trace']),1)

    def test_invalid_xml_char_is_replaced_only_in_snapshot(self):
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(self.db)) as db:db.execute('UPDATE djmdContent SET Title=? WHERE ID=?',('bad\x01title','1'));db.commit()
        before=self.db.read_bytes();lib=self.provider.load();self.assertEqual(lib.sanitized_snapshot_fields,1)
        self.assertEqual(lib.tracks['1'].title,'bad\ufffdtitle');self.assertEqual(before,self.db.read_bytes())

    def test_audio_job_persistence_cancellation_and_stale_file(self):
        from dataclasses import replace
        lib=self.provider.load();path=self.root/'audio.wav';path.write_bytes(b'audio fixture')
        lib.tracks['1']=replace(lib.tracks['1'],location=path.as_uri().replace('file:///', 'file://localhost/'));stamp=path.stat()
        value={'value':8,'source':'test','file_identity':{'path':str(path.resolve()),'size':stamp.st_size,'mtime_ns':stamp.st_mtime_ns,'inode':stamp.st_ino}}
        manager=AnalysisJobs(self.root/'measurements',lambda p,c:value)
        manager.start(lib,['1'])
        deadline=time.monotonic()+3
        while manager.snapshot()['state']=='running' and time.monotonic()<deadline:time.sleep(.01)
        self.assertEqual(manager.snapshot()['state'],'complete');self.assertEqual(manager.attach(lib).tracks['1'].energy,8)
        loaded=AnalysisJobs(self.root/'measurements');self.assertEqual(loaded.attach(lib).tracks['1'].energy,8)
        path.write_bytes(b'changed audio');self.assertIsNone(loaded.attach(lib).tracks['1'].energy)
        def slow(path,event):
            event.wait(3)
            if event.is_set():raise InterruptedError()
            return value
        manager=AnalysisJobs(self.root/'cancelled',slow);state=manager.start(lib,['1']);manager.cancel(state['job_id'])
        deadline=time.monotonic()+3
        while manager.snapshot()['state']=='running' and time.monotonic()<deadline:time.sleep(.01)
        self.assertEqual(manager.snapshot()['state'],'cancelled')


class LinkTests(unittest.TestCase):
    def test_decode_freshness_namespaces_and_simulation(self):
        now=[0];link=ProDjLink(lambda:now[0]);state=link.simulate()
        self.assertEqual(state['on_air_count'],2);self.assertTrue(state['ambiguous']);self.assertTrue(all(d['simulated'] for d in state['decks']))
        self.assertNotEqual(state['decks'][0]['media_identity'],state['decks'][1]['media_identity'])
        self.assertTrue(all(d['local_track_id'] is None for d in state['decks']))
        self.assertEqual(decode(simulated_status(),50002)['bpm'],128)
        now[0]=3;self.assertEqual(link.snapshot()['on_air_count'],0)
        with self.assertRaises(PlanningError):decode(simulated_status()[:-1],50002)
        with self.assertRaises(PlanningError):decode(b'X'*212,50002)

    def test_real_loopback_socket_lifecycle(self):
        link=ProDjLink();self.addCleanup(link.stop)
        try:link.start('127.0.0.1')
        except PlanningError:self.skipTest('UDP ports already occupied')
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sender:sender.sendto(simulated_status(),('127.0.0.1',50002))
        deadline=time.monotonic()+2
        while not link.snapshot()['decks'] and time.monotonic()<deadline:time.sleep(.02)
        self.assertEqual(len(link.snapshot()['decks']),1)
        self.assertFalse(link.snapshot()['decks'][0]['simulated']);self.assertFalse(link.snapshot()['hardware_verified'])
        self.assertEqual(link.stop()['mode'],'stopped')


class AnlzTests(unittest.TestCase):
    def test_relocate_preserves_unknown_and_obfuscated_bytes(self):
        path='/old.wav'.encode('utf-16-be')+b'\0\0'
        raw=b'PPTH'+struct.pack('>III',16,16+len(path),len(path))+path
        unknown=b'PVB2'+struct.pack('>II',12,20)+bytes(range(8))
        header=b'PMAI'+struct.pack('>II',28,28+len(raw)+len(unknown))+bytes(16)
        before=header+raw+unknown;after=relocate(before,'/Contents/new.wav')
        self.assertEqual(tags(after)[1][1][1],unknown)
        self.assertIn('/Contents/new.wav'.encode('utf-16-be'),after)
        with self.assertRaises(PlanningError):relocate(before[:-1],'/a.wav')
        cyclic=bytearray(before);cyclic[36:40]=bytes(4)
        with self.assertRaises(PlanningError):tags(cyclic)


if __name__=='__main__':unittest.main()
