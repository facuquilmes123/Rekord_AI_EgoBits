from contextlib import contextmanager, closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from egobits.adapters.native_collection import NativeCollection
from egobits.core.intelligence import query_tracks,get_tags,key_shift_options,shifted_key,missing_files,structure
from egobits.core.recommender import recommend,RecommendationOptions
from egobits.core.models import PlanningError


@contextmanager
def readonly(path):
    c=sqlite3.connect(Path(path).as_uri()+'?mode=ro',uri=True)
    c.execute('PRAGMA query_only=ON')
    try:yield c
    finally:c.close()


class IntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.db=self.root/'master.db'
        with closing(sqlite3.connect(self.db)) as c:
            c.executescript('''CREATE TABLE djmdContent (ID TEXT,Title TEXT,FolderPath TEXT,BPM INT,KeyID TEXT,GenreID TEXT,Rating INT,DJPlayCount TEXT,StockDate TEXT,Length INT,rb_local_deleted INT);
            CREATE TABLE djmdGenre(ID TEXT,Name TEXT); CREATE TABLE djmdKey(ID TEXT,ScaleName TEXT);
            CREATE TABLE djmdMyTag(ID TEXT,Name TEXT,ParentID TEXT);CREATE TABLE djmdSongMyTag(ContentID TEXT,MyTagID TEXT);
            CREATE TABLE djmdPlaylist(ID TEXT,Name TEXT,ParentID TEXT,Attribute INT);CREATE TABLE djmdSongPlaylist(ContentID TEXT,PlaylistID TEXT,TrackNo INT);
            CREATE TABLE djmdCue(ContentID TEXT,InMsec INT,OutMsec INT,Kind INT,Comment TEXT,ActiveLoop INT);
            INSERT INTO djmdGenre VALUES ('g','Tech House');INSERT INTO djmdKey VALUES ('k','Am');
            INSERT INTO djmdContent VALUES ('1','New','C:/fixture/a.mp3',12400,'k','g',5,'0','2026-01-02',300,0);
            INSERT INTO djmdContent VALUES ('2','Old','C:/fixture/b.mp3',12500,'k','g',3,'8','2025-01-02',300,0);
            INSERT INTO djmdContent VALUES ('3','Deleted','C:/fixture/c.mp3',12500,'k','g',5,'0','2026-01-02',300,1);
            INSERT INTO djmdMyTag VALUES ('cat','Situation','root');INSERT INTO djmdMyTag VALUES ('peak','Peak Time','cat');
            INSERT INTO djmdSongMyTag VALUES ('1','peak');
            INSERT INTO djmdPlaylist VALUES ('p','Set','root',0);INSERT INTO djmdSongPlaylist VALUES ('1','p',1);
            INSERT INTO djmdCue VALUES ('1',15000,23000,1,'Entry',1);''')
        self.provider=NativeCollection(self.db,self.root/'cache',readonly)

    def test_live_metadata_queries_and_refresh_preserve_database(self):
        before=self.db.read_bytes();lib=self.provider.load()
        result=query_tracks(lib,min_rating=4,unplayed=True,added_after='2026-01-01',tags=['Situation/Peak Time'])
        self.assertEqual([r['id'] for r in result['tracks']],['1']);self.assertEqual(len(lib.tracks),2)
        self.assertEqual(lib.playlists['ROOT/Set'],['1']);self.assertEqual(len(get_tags(lib)['tags']),2)
        self.assertEqual(before,self.db.read_bytes())
        with closing(sqlite3.connect(self.db)) as c:
            c.execute("UPDATE djmdContent SET DJPlayCount='1' WHERE ID='1'");c.commit()
        refreshed=self.provider.load(force=True)
        self.assertNotEqual(lib.revision,refreshed.revision);self.assertEqual(query_tracks(refreshed,unplayed=True)['total'],0)
        self.assertEqual(len(list((self.root/'cache').glob('*.xml'))),1)

    def test_cues_missing_files_and_validation(self):
        lib=self.provider.load();data=structure(lib,'1')
        self.assertEqual(data['hot_cues'],1);self.assertEqual(data['cues'][0]['start'],15)
        self.assertEqual(data['loops'],1);self.assertFalse(data['beatgrid_verified'])
        self.assertEqual(missing_files(lib,limit=1)['next_offset'],1)
        with self.assertRaises(PlanningError):query_tracks(lib,min_rating=6)
        with self.assertRaises(PlanningError):query_tracks(lib,added_after='not a date')

    def test_key_shift_pitch_classes_and_no_false_perfect_claim(self):
        self.assertEqual(shifted_key('Am',1),'3A') # A to Bb
        self.assertEqual(shifted_key('3A',-1),'8A')
        self.assertEqual(shifted_key('8A',12),'8A')
        choices=key_shift_options('8A','3A',2)
        self.assertEqual(choices[0]['semitones'],-1)
        self.assertNotIn(1,[c['semitones'] for c in choices]) # 10A is not compatible with 8A
        from dataclasses import replace
        lib=self.provider.load();a=lib.tracks['1'];b=replace(lib.tracks['2'],key='3A')
        self.assertEqual(recommend(a,[b],RecommendationOptions())['recommendations'],[])
        result=recommend(a,[b],RecommendationOptions(max_key_shift=2))['recommendations'][0]
        self.assertEqual(result['match_details']['key_shift_semitones'],-1)


if __name__=='__main__':unittest.main()
