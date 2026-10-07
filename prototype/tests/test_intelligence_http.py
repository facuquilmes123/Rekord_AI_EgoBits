import hashlib
import hmac
from unittest.mock import patch
from test_desktop_settings_api import SettingsApiTests
from egobits.desktop import service


class IntelligenceHttpTests(SettingsApiTests):
    def test_shared_read_boundary_and_forbidden_write(self):
        code,data=self.post('/api/toolbox/catalog',{});self.assertEqual(code,200)
        self.assertTrue(all(t['read_only'] for t in data['tools']))
        code,data=self.post('/api/toolbox/execute',{'name':'collection.query','arguments':{'limit':2}})
        self.assertEqual(code,200);self.assertEqual(len(data['tracks']),2)
        self.assertEqual(self.post('/api/toolbox/execute',{'name':'playlist.apply_native','arguments':{}})[0],400)

    def test_usb_apply_requires_native_hmac_and_correct_operation(self):
        preview={'token':'test-proposal','digest':'fixture-digest','operation':'usb_export'}
        body={'token':preview['token'],'approval_digest':preview['digest'],'confirmed':True}
        with patch.object(service,'approval_preview',return_value=preview),patch.object(service,'_NATIVE_APPROVAL_KEY','fixture-key'),patch.object(service._USB,'apply',return_value={'state':'applied'}) as apply:
            self.assertEqual(self.post('/api/device/export/apply',body)[0],400);apply.assert_not_called()
            body['approval_signature']=hmac.new(b'fixture-key',b'usb_export:test-proposal:fixture-digest',hashlib.sha256).hexdigest()
            self.assertEqual(self.post('/api/device/restore/apply',body)[0],400);apply.assert_not_called()
            self.assertEqual(self.post('/api/device/export/apply',body)[0],200);apply.assert_called_once_with('test-proposal')

    def test_simulation_is_not_a_production_route(self):
        code,data=self.post('/api/link/simulate',{});self.assertNotEqual(code,200)
        with patch.object(service._LINK,'interfaces',return_value=[]):
            code,data=self.post('/api/link/interfaces',{});self.assertEqual(code,200);self.assertEqual(data['interfaces'],[])
