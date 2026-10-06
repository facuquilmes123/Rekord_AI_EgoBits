import hashlib
import tempfile
import unittest
import xml.etree.ElementTree as E
from pathlib import Path
from egobits.adapters.xml_adapter import Library
from egobits.adapters.m3u8 import export_m3u8, local_path
from egobits.desktop.collection_tools import verify_duplicates, draft, insights, answer_help
from egobits.core.models import PlanningError

class CollectionWorkflowTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.a=self.root/'Música Á & uno.mp3';self.b=self.root/'Música dos.mp3'
  self.a.write_bytes(b'fixture same audio bytes');self.b.write_bytes(b'fixture same audio bytes')
  self.source=self.root/'colección.xml'
  root=E.Element('DJ_PLAYLISTS');collection=E.SubElement(root,'COLLECTION')
  for tid,path,bpm in [('1',self.a,'124'),('2',self.b,'125')]:
   track=E.SubElement(collection,'TRACK',TrackID=tid,Name='Mismo título',Artist='DJ',Genre='house',AverageBpm=bpm,Tonality='8A',TotalTime='123',Location=path.as_uri().replace('file:///','file://localhost/'))
   E.SubElement(track,'POSITION_MARK',Name='Cue',Start=tid)
  E.ElementTree(root).write(self.source,encoding='utf-8',xml_declaration=True);self.lib=Library(self.source)
 def test_m3u8_unicode_paths_and_source_preserved(self):
  before=self.source.read_bytes();result=draft(self.lib,['2','1'],self.lib.revision);out=self.root/'set.m3u8';export_m3u8(self.lib,result,'set',out)
  self.assertEqual(out.read_text(encoding='utf-8').splitlines()[0],'#EXTM3U');self.assertLess(out.read_text(encoding='utf-8').index('Música dos'),out.read_text(encoding='utf-8').index('Música Á'));self.assertEqual(self.source.read_bytes(),before)
 def test_export_never_overwrites(self):
  out=self.root/'existing.m3u8';out.write_text('original')
  with self.assertRaises(FileExistsError):export_m3u8(self.lib,draft(self.lib,['1'],self.lib.revision),'set',out)
  self.assertEqual(out.read_text(),'original')
 def test_stale_export_and_draft_rejected(self):
  with self.assertRaises(PlanningError):draft(self.lib,['1'],'wrong')
  self.source.write_bytes(self.source.read_bytes()+b' ')
  with self.assertRaises(PlanningError):export_m3u8(self.lib,{'track_ids':['1'],'source_revision':self.lib.revision},'x',self.root/'x.m3u8')
 def test_path_injection_rejected(self):
  for path in ['file://remote/music.mp3','file://localhost/C:/music%0Ainjected.mp3','file://localhost/C:/a.mp3?q=x']:
   with self.assertRaises(PlanningError):local_path(path)
 def test_same_name_different_bytes_not_confirmed(self):
  self.b.write_bytes(b'other recording')
  result=verify_duplicates(self.lib,['1','2']);self.assertEqual(result['confirmed'],[]);self.assertFalse(result['delete_enabled']);self.assertTrue(self.a.exists());self.assertTrue(self.b.exists())
 def test_identical_bytes_distinct_cues_reported(self):
  result=verify_duplicates(self.lib,['1','2']);self.assertEqual(len(result['confirmed']),1);self.assertTrue(result['confirmed'][0]['different_cues']);self.assertFalse(result['confirmed'][0]['same_file_reference']);self.assertFalse(result['delete_enabled'])
 def test_same_file_reference_is_not_separate_copy(self):
  root=E.parse(self.source);root.findall('./COLLECTION/TRACK')[1].set('Location',self.lib.tracks['1'].location);root.write(self.source,encoding='utf-8');lib=Library(self.source)
  self.assertTrue(verify_duplicates(lib,['1','2'])['confirmed'][0]['same_file_reference'])
 def test_missing_file_reports_uncertainty(self):
  self.b.unlink();r=verify_duplicates(self.lib,['1','2']);self.assertEqual(len(r['unavailable']),1);self.assertEqual(r['confirmed'],[])
 def test_unknown_draft_and_duplicate_ids_rejected(self):
  for ids in [['unknown'],['1','1']]:
   with self.assertRaises(PlanningError):draft(self.lib,ids,self.lib.revision)
  with self.assertRaises(PlanningError):verify_duplicates(self.lib,['1','unknown'])
 def test_insights_counts_account_for_collection(self):
  data=insights(self.lib);self.assertEqual(sum(data['genres'].values()),2);self.assertEqual(sum(data['bpm_distribution'].values()),2);self.assertEqual(data['missing_genre_count'],0);self.assertTrue(data['suggestions'])
 def test_hearing_question_is_grounded(self):
  reply=answer_help('podes escuchar en tiempo real lo que estoy reproduciendo?',{'telemetry_available':False});self.assertIn('Todavía no tengo',reply);self.assertIn('historial',reply);self.assertIn('master',reply)
 def test_general_audio_question_is_not_intercepted_as_agent_capability(self):
  self.assertIsNone(answer_help('Cómo escuchar la preescucha en auriculares en Rekordbox?',{'telemetry_available':False}))
