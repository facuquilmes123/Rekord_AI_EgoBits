import unittest,tempfile,hashlib,xml.etree.ElementTree as ET
from pathlib import Path
from egobits.core import Library,PlanOptions,PlanningError,plan,export_xml,harmonic_score,normalize_key
from egobits.policy import capability,State,NativeWriterUnavailable
ROOT=Path(__file__).resolve().parents[1]
class CoreTests(unittest.TestCase):
 def setUp(self):self.lib=Library(ROOT/'examples/library.xml')
 def test_union_deduplicates_ids(self):self.assertEqual(len(self.lib.pool(['ROOT/X','ROOT/Y'])),6)
 def test_harmonic_plan_rises(self):
  r=plan(self.lib.pool(['ROOT/X','ROOT/Y']),PlanOptions(count=4))
  self.assertEqual(r['track_ids'],['1','2','3','4'])
  self.assertTrue(all(x['bpm_delta']>=0 for x in r['transitions']))
 def test_missing_energy_is_not_invented(self):
  with self.assertRaises(PlanningError):plan(self.lib.pool(['ROOT/X']),PlanOptions(count=3,mode='energy'))
 def test_impossible_is_not_partial(self):
  with self.assertRaises(PlanningError):plan(self.lib.pool(['ROOT/X','ROOT/Y']),PlanOptions(count=5))
 def test_bad_options(self):
  for v in [0,-1,101]:
   with self.assertRaises(PlanningError):PlanOptions(count=v)
 def test_key_wrap(self):self.assertEqual(harmonic_score('12A','1A'),.85)
 def test_key_relative(self):self.assertEqual(harmonic_score('Am','C'),.9)
 def test_unknown_key_is_unknown(self):self.assertIsNone(harmonic_score('','8A'))
 def test_conventional_keys(self):
  self.assertEqual(normalize_key('G♯ minor'),'1A');self.assertEqual(normalize_key('C major'),'8B')
 def test_unknown_playlist(self):
  with self.assertRaises(PlanningError):self.lib.pool(['X'])
 def test_export_preserves_source_and_cues(self):
  before=self.lib.source.read_bytes();r=plan(self.lib.pool(['ROOT/X','ROOT/Y']),PlanOptions(count=4))
  with tempfile.TemporaryDirectory() as td:
   target=Path(td)/'set.xml';export_xml(self.lib,r,'Peña & <Club>',target)
   out=Library(target)
   self.assertEqual(len(out.tracks),4)
   self.assertIsNotNone(out.nodes['1'].find('POSITION_MARK'))
   self.assertEqual(out.nodes['1'].get('Location'),self.lib.nodes['1'].get('Location'))
   self.assertEqual(self.lib.source.read_bytes(),before)
   with self.assertRaises(FileExistsError):export_xml(self.lib,r,'again',target)
 def test_source_overwrite_denied(self):
  with self.assertRaises(PlanningError):export_xml(self.lib,{'track_ids':['1']},'bad',self.lib.source)
 def test_export_rejects_invalid_track_id(self):
  with tempfile.TemporaryDirectory() as td:
   src=Path(td)/'input.xml'
   src.write_bytes(self.lib.source.read_bytes().replace(b'TrackID="1"',b'TrackID="abc"').replace(b'Key="1"',b'Key="abc"'))
   lib=Library(src)
   with self.assertRaisesRegex(PlanningError,'TrackID'):
    export_xml(lib,{'track_ids':['abc']},'bad',Path(td)/'output.xml')
 def test_doctype_denied(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'bad.xml';p.write_text('<!DOCTYPE test><DJ_PLAYLISTS/>')
   with self.assertRaises(PlanningError):Library(p)
 def test_bad_energy_denied(self):
  with self.assertRaises(PlanningError):Library(self.lib.source,{'1':{'value':float('nan'),'source':'manual'}})
 def test_energy_order(self):
  lib=Library(self.lib.source,{str(i):{'value':i*2,'source':'manual'} for i in range(1,5)})
  r=plan(lib.pool(['ROOT/X','ROOT/Y']),PlanOptions(count=4,mode='energy'))
  self.assertEqual(r['track_ids'],['1','2','3','4'])
 def test_open_native_write_denied(self):
  self.assertFalse(capability('playlist.apply_native',State.OPEN,writer_certified=True,backup_verified=True,revision_matches=True).enabled)
 def test_unknown_native_write_denied(self):
  self.assertFalse(capability('playlist.apply_native',State.UNKNOWN,writer_certified=True,backup_verified=True,revision_matches=True).enabled)
 def test_backup_failure_denies(self):
  self.assertFalse(capability('playlist.apply_native',State.CLOSED,writer_certified=True,revision_matches=True).enabled)
 def test_stale_revision_denies(self):
  self.assertFalse(capability('playlist.apply_native',State.CLOSED,writer_certified=True,backup_verified=True).enabled)
 def test_closed_unsupported_writer_denies(self):
  self.assertFalse(capability('playlist.apply_native',State.CLOSED,backup_verified=True,revision_matches=True).enabled)
 def test_live_stale_denies(self):self.assertFalse(capability('recommend.live',State.OPEN,snapshot=True).enabled)
 def test_unknown_tool_denied(self):self.assertFalse(capability('shell.execute',State.CLOSED).enabled)
 def test_stub_never_writes(self):
  with self.assertRaises(NotImplementedError):NativeWriterUnavailable().apply()
if __name__=='__main__':unittest.main()
