import threading
import unittest
from unittest.mock import Mock, patch
from egobits.desktop.process_close import RekordboxCloser, inventory
from egobits.core.models import PlanningError


class ClosingTests(unittest.TestCase):
    def setUp(self):
        self.writer=Mock();self.writer.lock=threading.Lock()
        self.monitor=Mock();self.monitor.check_native_state.return_value='open'
        self.closer=RekordboxCloser(lambda:{},self.monitor,self.writer)
        self.rows=[{'pid':1,'name':'rekordbox.exe','path':'C:/verified/rekordbox.exe','started':1}]

    def test_confirmed_normal_close_and_single_use(self):
        with patch('egobits.desktop.process_close.inventory',side_effect=[self.rows,self.rows,[]]), patch('egobits.desktop.process_close.request_close',return_value={1}) as close, patch('egobits.desktop.process_close.time.sleep'):
            ticket=self.closer.prepare();self.monitor.check_native_state.return_value='closed'
            result=self.closer.close(ticket['token'],True)
            self.assertEqual(result['state'],'closed');close.assert_called_once_with(self.rows)
            with self.assertRaises(PlanningError):self.closer.close(ticket['token'],True)
        self.assertFalse(self.writer.lock.locked())

    def test_changed_pid_identity_never_closes(self):
        with patch('egobits.desktop.process_close.inventory',side_effect=[self.rows,[{**self.rows[0],'started':2}]]), patch('egobits.desktop.process_close.request_close') as close:
            ticket=self.closer.prepare()
            with self.assertRaises(PlanningError):self.closer.close(ticket['token'],True)
            close.assert_not_called()

    def test_requires_confirmation_and_excludes_native_operation(self):
        with patch('egobits.desktop.process_close.inventory',return_value=self.rows):
            ticket=self.closer.prepare()
            with self.assertRaises(PlanningError):self.closer.close(ticket['token'],False)
            self.writer.lock.acquire()
            try:
                with self.assertRaises(PlanningError):self.closer.prepare()
                with self.assertRaises(PlanningError):self.closer.close(ticket['token'],True)
            finally:self.writer.lock.release()

    def test_unknown_and_expired_are_blocked(self):
        self.monitor.check_native_state.return_value='unknown'
        with self.assertRaises(PlanningError):self.closer.prepare()
        self.closer.tickets['expired']=(0,self.rows)
        with self.assertRaises(PlanningError):self.closer.close('expired',True)

    def test_unrefused_process_not_reported_closed(self):
        with patch('egobits.desktop.process_close.inventory',return_value=self.rows), patch('egobits.desktop.process_close.request_close',return_value=set()), patch('egobits.desktop.process_close.time.sleep'), patch('egobits.desktop.process_close.time.monotonic',side_effect=[0,1,2,3,20]):
            ticket=self.closer.prepare();result=self.closer.close(ticket['token'],True)
        self.assertEqual(result['state'],'open');self.assertIn('pendiente',result['reason'])

    def test_untrusted_install_path_and_other_owner_rejected(self):
        import sys
        fake=Mock();fake.Process.return_value.username.return_value='pc/user'
        row={'pid':1,'name':'rekordbox.exe','exe':'C:/untrusted/rekordbox.exe','username':'pc/user','create_time':1}
        fake.process_iter.return_value=[Mock(info=row)]
        with patch.dict(sys.modules,{'psutil':fake}),patch('egobits.desktop.process_close.os.name','nt'):
            with self.assertRaises(PlanningError):inventory({'installations':[{'path':'C:/trusted/rekordbox.exe'}]})
            row['username']='pc/other'
            with self.assertRaises(PlanningError):inventory({'installations':[{'path':'C:/untrusted/rekordbox.exe'}]})

    def test_agents_closed_after_main_to_avoid_respawn(self):
        agent={'pid':2,'name':'rekordboxAgent.exe','path':'C:/verified/rekordboxAgent.exe','started':2}
        rows=self.rows+[agent]
        with patch('egobits.desktop.process_close.inventory',side_effect=[rows,rows,[agent],[]]),patch('egobits.desktop.process_close.request_close',side_effect=[{1},{2}]) as close,patch('egobits.desktop.process_close.time.sleep'):
            ticket=self.closer.prepare();self.monitor.check_native_state.return_value='closed';result=self.closer.close(ticket['token'],True)
        self.assertEqual(close.call_args_list[0].args[0],self.rows);self.assertEqual(close.call_args_list[1].args[0],[agent]);self.assertEqual(result['state'],'closed')

    def test_force_requires_explicit_ticket_confirmation_and_remains_blocked_on_pid_change(self):
        with patch('egobits.desktop.process_close.inventory',return_value=self.rows),patch('egobits.desktop.process_close.terminate_owned',return_value={1}) as kill,patch('egobits.desktop.process_close.request_close') as normal:
            ticket=self.closer.prepare('force')
            with self.assertRaises(PlanningError):self.closer.close(ticket['token'],False)
            kill.assert_not_called()
            with patch('egobits.desktop.process_close.inventory',side_effect=[self.rows,[]]),patch('egobits.desktop.process_close.time.sleep'):
                self.monitor.check_native_state.return_value='closed';result=self.closer.close(ticket['token'],True)
            kill.assert_called_once_with(self.rows);normal.assert_not_called();self.assertTrue(result['forced'])
        with self.assertRaises(PlanningError):self.closer.prepare('arbitrary')

    def test_force_rechecks_exact_identity_before_terminating(self):
        from egobits.desktop.process_close import terminate_owned
        import psutil
        owner=Mock();owner.username.return_value='pc/user';target=Mock();target.create_time.return_value=2
        with patch.object(psutil,'Process',side_effect=lambda pid=None:owner if pid is None else target):
            with self.assertRaises(PlanningError):terminate_owned(self.rows)
        target.terminate.assert_not_called()
