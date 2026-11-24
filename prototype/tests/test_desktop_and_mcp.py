import unittest
import json
from pathlib import Path
from unittest.mock import patch
from egobits.adapters.xml_adapter import Library
from egobits import mcp_server
from egobits.mcp_server import (
    system_status,
    list_playlists,
    search_tracks,
    plan_playlist,
    compare_playlists_tool,
    audit_library_tool,
    duplicates_tool,
    set_current_state
)
from egobits.policy import State
from egobits.desktop import ProcessMonitor, TrayStateManager, NotificationConfig

class DesktopAndMcpTests(unittest.TestCase):
    def setUp(self):
        fixture = Library(Path(__file__).resolve().parents[1] / 'examples/library.xml')
        patcher = patch.object(mcp_server, '_LIB', fixture)
        patcher.start()
        self.addCleanup(patcher.stop)
        set_current_state(State.OPEN)

    def test_mcp_system_status(self):
        st = system_status()
        self.assertEqual(st['status'], 'online')
        self.assertEqual(st['rekordbox_state'], 'open')
        self.assertTrue(st['snapshot_loaded'])

    def test_mcp_list_playlists(self):
        res = list_playlists()
        self.assertIn('playlists', res)
        paths = [p['path'] for p in res['playlists']]
        self.assertIn('ROOT/X', paths)
        self.assertIn('ROOT/Y', paths)

    def test_mcp_search_tracks(self):
        res = search_tracks(query='Motor', limit=10)
        self.assertEqual(res['total'], 1)
        self.assertEqual(res['tracks'][0]['title'], 'Motor')

    def test_mcp_plan_playlist(self):
        res = plan_playlist(['ROOT/X', 'ROOT/Y'], count=4, mode='bpm')
        self.assertEqual(len(res['track_ids']), 4)
        self.assertEqual(res['mode'], 'bpm')

    def test_mcp_plan_playlist_flexible(self):
        res = plan_playlist(['ROOT/X', 'ROOT/Y'], count=10, mode='bpm', allow_insufficient=True)
        self.assertEqual(len(res['track_ids']), 6)
        self.assertTrue(res['adjustments'])

    def test_mcp_compare_tool(self):
        res = compare_playlists_tool('ROOT/X', 'ROOT/Y')
        self.assertEqual(res['common_count'], 1)

    def test_process_monitor_forced_state(self):
        mon = ProcessMonitor()
        mon.force_state('open')
        self.assertEqual(mon.check_state(), 'open')
        mon.force_state('closed')
        self.assertEqual(mon.check_state(), 'closed')

    def test_tray_notification_manager(self):
        mon = ProcessMonitor()
        mon.force_state('open')
        cfg = NotificationConfig(enabled=True, opt_in=True, min_frequency_seconds=10)
        mgr = TrayStateManager(mon, cfg)

        self.assertTrue(mgr.can_dispatch_notification())
        dispatched = mgr.dispatch_suggestion('Tema sugerido: +1 BPM', {'id': '2'})
        self.assertTrue(dispatched)

        # Inmediatamente después, debe ser bloqueado por la frecuencia mínima
        self.assertFalse(mgr.can_dispatch_notification())

if __name__ == '__main__':
    unittest.main()
