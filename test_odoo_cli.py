import unittest
from unittest.mock import patch
import odoo_cli as cli


class Safety(unittest.TestCase):
    def test_auth_requires_matching_identity_and_cookie(self):
        with patch.object(cli, 'LOGIN', 'user@example.com'):
            with patch.object(cli, 'rpc', return_value=({'uid': 7, 'username': 'other@example.com'}, 'session_id=test')):
                with self.assertRaises(cli.OdooError):
                    cli.auth('test-password')
            with patch.object(cli, 'rpc', return_value=({'uid': 7, 'username': cli.LOGIN}, '')):
                with self.assertRaises(cli.OdooError):
                    cli.auth('test-password')
            with patch.object(cli, 'rpc', return_value=({'uid': 7, 'username': cli.LOGIN}, 'session_id=test; Path=/; HttpOnly')):
                session = cli.auth('test-password')
                self.assertEqual(session['session_id'], 'test')
                self.assertNotIn('password', session)

    def test_response_size_limit(self):
        from io import BytesIO
        with self.assertRaises(cli.OdooError):
            cli.read_limited(BytesIO(b'x' * (2 * 1024 * 1024 + 1)))

    def test_redirects_refused(self):
        self.assertIsNone(cli.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.example.com'))

    def test_mutations_blocked_before_network(self):
        with patch.object(cli, 'rpc') as network:
            for method in ['write', 'create', 'unlink', 'action_archive']:
                with self.assertRaises(cli.OdooError):
                    cli.call('project.task', method, [], {}, {})
            network.assert_not_called()

    def test_sensitive_models_blocked(self):
        with self.assertRaises(cli.OdooError):
            cli.call('res.users.apikeys', 'search_read', [], {}, {})

    def test_query_contract(self):
        with patch.object(cli, 'rpc', return_value=([{'id': 7}], '')) as network:
            self.assertEqual(cli.call('project.task', 'read', [[7]], {}, {'session_id': 'test'}), [{'id': 7}])
            self.assertEqual(network.call_args.args[1]['args'], [[7]])


if __name__ == '__main__':
    unittest.main()
