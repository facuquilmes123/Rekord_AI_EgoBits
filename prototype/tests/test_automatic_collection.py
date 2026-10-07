import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from egobits.desktop import service
from egobits.desktop.settings import SettingsStore
from egobits.core.models import PlanningError
from egobits.adapters.xml_adapter import Library


class AutomaticCollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.db=self.root/'master.db';self.db.write_bytes(b'fixture identity')
        self.store=SettingsStore(self.root/'settings.json');self.fixture=Path(__file__).resolve().parents[1]/'examples/library.xml'
        self.lib=Library(self.fixture);self.lib.source_kind='native_snapshot';self.lib.database_path=self.db
        self.provider=Mock(database=self.db);self.provider.load.return_value=self.lib
        self.discovery={'databases':[str(self.db)],'preferred_database':str(self.db),'export_candidates':[]}
        env={k:v for k,v in os.environ.items() if k not in ('EGB_LIBRARY_XML','EGB_ENERGIES_JSON')}
        for item in (patch.dict(os.environ,env,clear=True),patch.object(service,'_SETTINGS',self.store),
                     patch.object(service,'_GLOBAL_LIB',None),patch.object(service,'_NATIVE_COLLECTION',None),
                     patch.object(service,'_CONNECTION',{}),patch.object(service,'cached_discover',return_value=self.discovery),
                     patch('egobits.adapters.native_collection.NativeCollection',return_value=self.provider),
                     patch.object(service._ANALYSIS,'attach',side_effect=lambda lib:lib)):
            item.start();self.addCleanup(item.stop)

    def test_fresh_profile_connects_native_and_persists_only_verified_path(self):
        before=self.db.read_bytes();self.assertEqual(self.store.snapshot()['collection_mode'],'auto')
        self.assertIs(service.get_or_load_library(),self.lib);self.assertEqual(self.db.read_bytes(),before)
        self.assertEqual(self.store.snapshot()['native_database'],str(self.db))
        self.assertFalse(service._CONNECTION['requires_action']);self.assertEqual(service._CONNECTION['kind'],'native')

    def test_no_database_never_loads_bundled_example(self):
        self.discovery.update(databases=[],preferred_database=None)
        with self.assertRaisesRegex(PlanningError,'No se encontró'):service.get_or_load_library()
        self.assertIsNone(service._GLOBAL_LIB);self.assertFalse(self.store.path.exists())

    def test_multiple_databases_require_choice_before_open(self):
        self.discovery.update(databases=[str(self.db),'other.db'],preferred_database=None)
        with self.assertRaisesRegex(PlanningError,'varias bases'):service.get_or_load_library()
        self.provider.load.assert_not_called();self.assertEqual(service._CONNECTION['state'],'selection_required')

    def test_failed_read_does_not_persist_or_close_rekordbox(self):
        self.provider.load.side_effect=PlanningError('Base bloqueada')
        with patch.object(service._MONITOR,'check_state',return_value='open'),patch.object(service._CLOSER,'request',create=True) as close:
            with self.assertRaisesRegex(PlanningError,'bloqueada'):service.get_or_load_library()
            close.assert_not_called()
        self.assertFalse(self.store.path.exists());self.assertIsNone(service._GLOBAL_LIB)

    def test_explicit_xml_is_retained_without_database_access(self):
        self.store.update({'collection_mode':'xml','library_xml':str(self.fixture)})
        lib=service.get_or_load_library();self.assertEqual(lib.source,self.fixture.resolve());self.provider.load.assert_not_called()

    def test_configured_xml_fallback_has_actionable_source_status(self):
        self.discovery.update(databases=[],preferred_database=None)
        self.store.update({'library_xml':str(self.fixture)})
        self.assertEqual(service.get_or_load_library().source,self.fixture.resolve())
        self.assertEqual(service._CONNECTION['state'],'fallback');self.assertTrue(service._CONNECTION['requires_action'])

    def test_legacy_preferences_migrate_to_automatic_without_losing_filters(self):
        data=self.store.snapshot();data.pop('collection_mode');data.pop('native_database')
        normalized=SettingsStore.validate(data);self.assertEqual(normalized['collection_mode'],'auto')
        self.assertEqual(normalized['recommendation'],data['recommendation'])

    def test_native_operations_follow_selected_database_among_multiple(self):
        found={'databases':['other.db',str(self.db)],'preferred_database':'other.db'}
        self.assertEqual(service.selected_native_database(self.lib,found),str(self.db))
        with self.assertRaisesRegex(PlanningError,'ya no coincide'):
            service.selected_native_database(self.lib,{'databases':['other.db']})

    def test_xml_native_target_requires_unambiguous_active_database(self):
        xml=Library(self.fixture)
        with self.assertRaisesRegex(PlanningError,'Elegí tu base'):
            service.selected_native_database(xml,{'databases':['one.db','two.db']})
        self.assertEqual(service.selected_native_database(xml,self.discovery),str(self.db))

    def test_applied_operation_refreshes_native_without_switching_to_xml(self):
        service.get_or_load_library();self.provider.load.reset_mock()
        with patch.object(service._HISTORY,'reset'),patch.object(service._AUDIO_WATCH,'stop'):
            service.activate_operation_collection({'repaired_xml':'unused-copy.xml'},'repaired_xml')
        self.provider.load.assert_called_once()
        self.assertIs(service._GLOBAL_LIB,self.lib)
        self.assertEqual(self.store.snapshot()['collection_mode'],'auto');self.assertEqual(self.store.snapshot()['library_xml'],'')
