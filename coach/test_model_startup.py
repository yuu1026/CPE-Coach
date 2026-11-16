from unittest.mock import MagicMock,patch
from django.test import SimpleTestCase
import local_model_server


class ModelStartupTests(SimpleTestCase):
    def test_busy_port_fails_before_loading_weights(self):
        server=MagicMock();server.server_bind.side_effect=OSError('port busy')
        with patch.object(local_model_server,'ExclusiveModelServer') as factory,patch.object(local_model_server,'load_model') as load:
            factory.return_value.__enter__.return_value=server
            with self.assertRaises(OSError):local_model_server.serve()
        load.assert_not_called()
        server.server_activate.assert_not_called()

    def test_success_reserves_port_before_loading_and_listening(self):
        events=[];server=MagicMock()
        server.server_bind.side_effect=lambda:events.append('reserve')
        server.server_activate.side_effect=lambda:events.append('listen')
        with patch.object(local_model_server,'ExclusiveModelServer') as factory,patch.object(local_model_server,'load_model',side_effect=lambda:(events.append('load') or ('tokenizer','model'))):
            factory.return_value.__enter__.return_value=server
            local_model_server.serve()
        self.assertEqual(events,['reserve','load','listen'])
        server.serve_forever.assert_called_once()
