"""Module to test the main napp file."""
import json
import time
from unittest import TestCase
from unittest.mock import MagicMock, create_autospec, patch

from kytos.core.interface import Interface
from kytos.core.link import Link
from kytos.core.switch import Switch
from kytos.lib.helpers import (get_interface_mock, get_link_mock,
                               get_switch_mock, get_test_client)
from napps.kytos.topology.exceptions import RestoreError
from tests.unit.helpers import get_controller_mock, get_napp_urls


# pylint: disable=too-many-public-methods
class TestMain(TestCase):
    """Test the Main class."""

    # pylint: disable=too-many-public-methods, protected-access,C0302

    def setUp(self):
        """Execute steps before each tests.

        Set the server_name_url_url from kytos/topology
        """
        self.server_name_url = 'http://localhost:8181/api/kytos/topology'

        patch('kytos.core.helpers.run_on_thread', lambda x: x).start()
        # pylint: disable=import-outside-toplevel
        from napps.kytos.topology.main import Main
        self.addCleanup(patch.stopall)

        self.napp = Main(get_controller_mock())

    def test_get_event_listeners(self):
        """Verify all event listeners registered."""
        expected_events = ['kytos/core.shutdown',
                           'kytos/core.shutdown.kytos/topology',
                           'kytos/maintenance.start_link',
                           'kytos/maintenance.end_link',
                           'kytos/maintenance.start_switch',
                           'kytos/maintenance.end_switch',
                           '.*.network_status.updated',
                           '.*.interface.is.nni',
                           '.*.connection.lost',
                           '.*.switch.interface.created',
                           '.*.switch.interface.deleted',
                           '.*.switch.interface.link_down',
                           '.*.switch.interface.link_up',
                           '.*.switch.(new|reconnected)',
                           '.*.switch.port.created',
                           'kytos/topology.*.metadata.*']
        actual_events = self.napp.listeners()
        self.assertCountEqual(expected_events, actual_events)

    def test_verify_api_urls(self):
        """Verify all APIs registered."""
        expected_urls = [
         ({}, {'GET', 'OPTIONS', 'HEAD'}, '/api/kytos/topology/v3/interfaces'),
         ({}, {'GET', 'OPTIONS', 'HEAD'}, '/api/kytos/topology/v3/switches'),
         ({}, {'GET', 'OPTIONS', 'HEAD'}, '/api/kytos/topology/v3/links'),
         ({}, {'GET', 'OPTIONS', 'HEAD'}, '/api/kytos/topology/v3/'),
         ({'dpid': '[dpid]'}, {'POST', 'OPTIONS'},
          '/api/kytos/topology/v3/interfaces/switch/<dpid>/disable'),
         ({'dpid': '[dpid]'}, {'POST', 'OPTIONS'},
          '/api/kytos/topology/v3/interfaces/switch/<dpid>/enable'),
         ({'key': '[key]', 'interface_id': '[interface_id]'},
          {'OPTIONS', 'DELETE'},
          '/api/kytos/topology/v3/interfaces/<interface_id>/metadata/<key>'),
         ({'interface_id': '[interface_id]'}, {'POST', 'OPTIONS'},
          '/api/kytos/topology/v3/interfaces/<interface_id>/metadata'),
         ({'interface_id': '[interface_id]'}, {'GET', 'OPTIONS', 'HEAD'},
          '/api/kytos/topology/v3/interfaces/<interface_id>/metadata'),
         ({'interface_disable_id': '[interface_disable_id]'},
          {'POST', 'OPTIONS'},
          '/api/kytos/topology/v3/interfaces/<interface_disable_id>/disable'),
         ({'interface_enable_id': '[interface_enable_id]'},
          {'POST', 'OPTIONS'},
          '/api/kytos/topology/v3/interfaces/<interface_enable_id>/enable'),
         ({'dpid': '[dpid]', 'key': '[key]'}, {'OPTIONS', 'DELETE'},
          '/api/kytos/topology/v3/switches/<dpid>/metadata/<key>'),
         ({'dpid': '[dpid]'}, {'POST', 'OPTIONS'},
          '/api/kytos/topology/v3/switches/<dpid>/metadata'),
         ({'dpid': '[dpid]'}, {'GET', 'OPTIONS', 'HEAD'},
          '/api/kytos/topology/v3/switches/<dpid>/metadata'),
         ({'dpid': '[dpid]'}, {'POST', 'OPTIONS'},
          '/api/kytos/topology/v3/switches/<dpid>/disable'),
         ({'dpid': '[dpid]'}, {'POST', 'OPTIONS'},
          '/api/kytos/topology/v3/switches/<dpid>/enable'),
         ({'link_id': '[link_id]', 'key': '[key]'}, {'OPTIONS', 'DELETE'},
          '/api/kytos/topology/v3/links/<link_id>/metadata/<key>'),
         ({'link_id': '[link_id]'}, {'POST', 'OPTIONS'},
          '/api/kytos/topology/v3/links/<link_id>/metadata'),
         ({'link_id': '[link_id]'}, {'GET', 'OPTIONS', 'HEAD'},
          '/api/kytos/topology/v3/links/<link_id>/metadata'),
         ({'link_id': '[link_id]'}, {'POST', 'OPTIONS'},
          '/api/kytos/topology/v3/links/<link_id>/disable'),
         ({'link_id': '[link_id]'}, {'POST', 'OPTIONS'},
          '/api/kytos/topology/v3/links/<link_id>/enable')]

        urls = get_napp_urls(self.napp)
        self.assertEqual(expected_urls, urls)

    def test_get_link_or_create(self):
        """Test _get_link_or_create."""
        dpid_a = "00:00:00:00:00:00:00:01"
        dpid_b = "00:00:00:00:00:00:00:02"
        mock_switch_a = get_switch_mock(dpid_a, 0x04)
        mock_switch_b = get_switch_mock(dpid_b, 0x04)
        mock_interface_a = get_interface_mock('s1-eth1', 1, mock_switch_a)
        mock_interface_b = get_interface_mock('s2-eth1', 1, mock_switch_b)
        mock_interface_a.id = dpid_a
        mock_interface_b.id = dpid_b

        link = self.napp._get_link_or_create(mock_interface_a,
                                             mock_interface_b)
        self.assertEqual(link.endpoint_a.id, dpid_a)
        self.assertEqual(link.endpoint_b.id, dpid_b)

    def test_get_link_from_interface(self):
        """Test _get_link_from_interface."""
        mock_switch_a = get_switch_mock("00:00:00:00:00:00:00:01", 0x04)
        mock_switch_b = get_switch_mock("00:00:00:00:00:00:00:02", 0x04)
        mock_interface_a = get_interface_mock('s1-eth1', 1, mock_switch_a)
        mock_interface_b = get_interface_mock('s2-eth1', 1, mock_switch_b)
        mock_interface_c = get_interface_mock('s2-eth1', 2, mock_switch_b)
        mock_link = get_link_mock(mock_interface_a, mock_interface_b)
        self.napp.links = {'0e2b5d7bc858b9f38db11b69': mock_link}
        response = self.napp._get_link_from_interface(mock_interface_a)
        self.assertEqual(response, mock_link)

        response = self.napp._get_link_from_interface(mock_interface_c)
        self.assertEqual(response, None)

    def test_get_topology(self):
        """Test get_topology."""
        dpid_a = "00:00:00:00:00:00:00:01"
        dpid_b = "00:00:00:00:00:00:00:02"
        expected = {
                      "topology": {
                        "switches": {
                          "00:00:00:00:00:00:00:01": {
                            "metadata": {
                              "lat": "0.0",
                              "lng": "-30.0"
                            }
                          },
                          "00:00:00:00:00:00:00:02": {
                            "metadata": {
                              "lat": "0.0",
                              "lng": "-30.0"
                            }
                          }
                        },
                        "links": {
                          "cf0f4071be4": {
                            "id": "cf0f4071be4"
                          }
                        }
                      }
                    }

        mock_switch_a = get_switch_mock(dpid_a, 0x04)
        mock_switch_b = get_switch_mock(dpid_b, 0x04)
        mock_interface_a = get_interface_mock('s1-eth1', 1, mock_switch_a)
        mock_interface_b = get_interface_mock('s2-eth1', 1, mock_switch_b)

        mock_link = get_link_mock(mock_interface_a, mock_interface_b)
        mock_link.id = 'cf0f4071be4'
        mock_switch_a.id = dpid_a
        mock_switch_a.as_dict.return_value = {'metadata': {'lat': '0.0',
                                              'lng': '-30.0'}}
        mock_switch_b.id = dpid_b
        mock_switch_b.as_dict.return_value = {'metadata': {'lat': '0.0',
                                              'lng': '-30.0'}}

        self.napp.controller.switches = {dpid_a: mock_switch_a,
                                         dpid_b: mock_switch_b}

        self.napp.links = {"cf0f4071be4": mock_link}
        mock_link.as_dict.return_value = {"id": "cf0f4071be4"}
        api = get_test_client(self.napp.controller, self.napp)

        url = f'{self.server_name_url}/v3/'
        response = api.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.data), expected)

    @patch('napps.kytos.topology.main.StoreHouse.get_data')
    def test_load_network_status(self, mock_storehouse_get_data):
        """Test _load_network_status."""
        status = {
            'network_status': {
                'id': 'network_status',
                'links': {
                    '4d42dc08522': {
                        'enabled': True,
                        'endpoint_a': {
                            'switch': '00:00:00:00:00:00:00:01',
                            'id': '00:00:00:00:00:00:00:00:1'
                        },
                        'endpoint_b': {
                            'switch': '00:00:00:00:00:00:00:01',
                            'id': '00:00:00:00:00:00:00:00:2'
                        }
                    }
                },
                'switches': {
                    '00:00:00:00:00:00:00:01': {
                        'dpid': '00:00:00:00:00:00:00:01',
                        'enabled': True,
                        'id': '00:00:00:00:00:00:00:01',
                        'interfaces': {
                            '00:00:00:00:00:00:00:01:1': {
                                'enabled': True,
                                'lldp': True,
                                'id': '00:00:00:00:00:00:00:00:1',
                            }
                        }
                    }
                }
            }
        }
        switches_expected = {'00:00:00:00:00:00:00:01': True}
        interfaces_expected = {'00:00:00:00:00:00:00:01:1': (True, True)}
        mock_storehouse_get_data.return_value = status
        self.napp._load_network_status()
        self.assertDictEqual(switches_expected, self.napp.switches_state)
        self.assertDictEqual(interfaces_expected, self.napp.interfaces_state)
        self.assertDictEqual(status['network_status']['links'],
                             self.napp.links_state)

    # pylint: disable=too-many-locals
    def test_restore_network_status(self):
        """Test restore_network_status."""
        dpid = '00:00:00:00:00:00:00:01'
        mock_switch = get_switch_mock(dpid)
        mock_switch.id = dpid
        mock_interface = get_interface_mock('s1-eth1', 1, mock_switch)
        mock_switch.interfaces = {1: mock_interface}
        self.napp.controller.switches = {dpid: mock_switch}
        self.napp.switches_state = {dpid: True}
        self.napp.interfaces_state = {'00:00:00:00:00:00:00:01:1': (True,
                                                                    True)}

        # enable
        self.napp.restore_network_status(mock_switch)
        self.assertEqual(mock_switch.enable.call_count, 1)
        self.assertEqual(mock_interface.enable.call_count, 1)
        self.assertEqual(mock_interface.lldp, True)

        # disable
        self.napp.switches_state = {dpid: False}
        self.napp.interfaces_state = {'00:00:00:00:00:00:00:01:1': (False,
                                                                    False)}
        self.napp.restore_network_status(mock_switch)
        self.assertEqual(mock_switch.disable.call_count, 1)
        self.assertEqual(mock_interface.disable.call_count, 1)
        self.assertEqual(mock_interface.lldp, False)

    def test_restore_links(self):
        """Test restore_link."""
        dpid = '00:00:00:00:00:00:00:01'
        dpid_b = '00:00:00:00:00:00:00:02'
        link_id = '4d42dc08522'
        mock_switch_a = get_switch_mock(dpid)
        mock_switch_b = get_switch_mock(dpid_b)
        mock_interface_a_1 = get_interface_mock('s1-eth1', 1, mock_switch_a)
        mock_interface_b_1 = get_interface_mock('s2-eth1', 1, mock_switch_b)
        mock_link = get_link_mock(mock_interface_a_1, mock_interface_b_1)
        mock_link.id = link_id
        self.napp.links = {link_id: mock_link}
        self.napp.links_state = {link_id: {'enabled': True}}
        # enable link
        self.napp.restore_network_status(mock_link)
        self.assertEqual(mock_link.enable.call_count, 1)

        # disable link
        self.napp.links_state = {link_id: {"enabled": False}}
        self.napp._verified_links = []
        self.napp.restore_network_status(mock_link)
        self.assertEqual(mock_link.disable.call_count, 1)

    def test_fail_restore_link(self):
        """Test fail restore_link."""
        dpid = '00:00:00:00:00:00:00:01'
        dpid_b = '00:00:00:00:00:00:00:02'
        link_id = '4d42dc08522'
        link_id_fail = '4cd52'
        mock_switch_a = get_switch_mock(dpid)
        mock_switch_b = get_switch_mock(dpid_b)
        mock_interface_a_1 = get_interface_mock('s1-eth1', 1, mock_switch_a)
        mock_interface_b_1 = get_interface_mock('s2-eth1', 1, mock_switch_b)
        mock_link = get_link_mock(mock_interface_a_1, mock_interface_b_1)
        mock_link.id = link_id
        self.napp.links = {link_id: mock_link}
        self.napp.links_state = {link_id: {"enabled": True}}
        with self.assertRaises(RestoreError):
            self.napp._restore_link(link_id_fail)

        self.napp.links_state = {link_id_fail: {"enabled": True}}
        with self.assertRaises(RestoreError):
            self.napp._restore_link(link_id_fail)

    def test_fail_restore_switch(self):
        """Test fail restore_switch."""
        dpid = '00:00:00:00:00:00:00:01'
        dpid_fail = '00:00:00:00:00:00:00:06'
        mock_switch = get_switch_mock(dpid)
        mock_switch.id = dpid
        mock_interface = get_interface_mock('s1-eth1', 1, mock_switch)
        mock_switch.interfaces = {1: mock_interface}
        self.napp.controller.switche = {dpid: mock_switch}
        self.napp.switches_state = {dpid: True}
        self.napp.interfaces_state = {'00:00:00:00:00:00:00:01:1': (True,
                                                                    True)}

        with self.assertRaises(RestoreError):
            self.napp._restore_switch(dpid_fail)

        self.napp.switches_state = {dpid_fail: True}
        with self.assertRaises(RestoreError):
            self.napp._restore_switch(dpid_fail)

    @patch('napps.kytos.topology.main.Main.save_status_on_storehouse')
    def test_enable_switch(self, mock_save_status):
        """Test enable_switch."""
        dpid = "00:00:00:00:00:00:00:01"
        mock_switch = get_switch_mock(dpid)
        self.napp.controller.switches = {dpid: mock_switch}
        api = get_test_client(self.napp.controller, self.napp)

        url = f'{self.server_name_url}/v3/switches/{dpid}/enable'
        response = api.post(url)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(mock_switch.enable.call_count, 1)
        mock_save_status.assert_called()

        # fail case
        mock_switch.enable.call_count = 0
        dpid = "00:00:00:00:00:00:00:02"
        url = f'{self.server_name_url}/v3/switches/{dpid}/enable'
        response = api.post(url)
        self.assertEqual(response.status_code, 404, response.data)
        self.assertEqual(mock_switch.enable.call_count, 0)

    @patch('napps.kytos.topology.main.Main.save_status_on_storehouse')
    def test_disable_switch(self, mock_save_status):
        """Test disable_switch."""
        dpid = "00:00:00:00:00:00:00:01"
        mock_switch = get_switch_mock(dpid)
        self.napp.controller.switches = {dpid: mock_switch}
        api = get_test_client(self.napp.controller, self.napp)

        url = f'{self.server_name_url}/v3/switches/{dpid}/disable'
        response = api.post(url)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(mock_switch.disable.call_count, 1)
        mock_save_status.assert_called()

        # fail case
        mock_switch.disable.call_count = 0
        dpid = "00:00:00:00:00:00:00:02"
        url = f'{self.server_name_url}/v3/switches/{dpid}/disable'
        response = api.post(url)
        self.assertEqual(response.status_code, 404, response.data)
        self.assertEqual(mock_switch.disable.call_count, 0)

    def test_get_switch_metadata(self):
        """Test get_switch_metadata."""
        dpid = "00:00:00:00:00:00:00:01"
        mock_switch = get_switch_mock(dpid)
        mock_switch.metadata = "A"
        self.napp.controller.switches = {dpid: mock_switch}
        api = get_test_client(self.napp.controller, self.napp)

        url = f'{self.server_name_url}/v3/switches/{dpid}/metadata'
        response = api.get(url)
        self.assertEqual(response.status_code, 200, response.data)

        # fail case
        dpid = "00:00:00:00:00:00:00:02"
        url = f'{self.server_name_url}/v3/switches/{dpid}/metadata'
        response = api.get(url)
        self.assertEqual(response.status_code, 404, response.data)

    @patch('napps.kytos.topology.main.Main.notify_metadata_changes')
    def test_add_switch_metadata(self, mock_metadata_changes):
        """Test add_switch_metadata."""
        dpid = "00:00:00:00:00:00:00:01"
        mock_switch = get_switch_mock(dpid)
        self.napp.controller.switches = {dpid: mock_switch}
        api = get_test_client(self.napp.controller, self.napp)
        payload = {"data": "A"}

        url = f'{self.server_name_url}/v3/switches/{dpid}/metadata'
        response = api.post(url, data=json.dumps(payload),
                            content_type='application/json')
        self.assertEqual(response.status_code, 201, response.data)
        mock_metadata_changes.assert_called()

        # fail case
        dpid = "00:00:00:00:00:00:00:02"
        url = f'{self.server_name_url}/v3/switches/{dpid}/metadata'
        response = api.post(url, data=json.dumps(payload),
                            content_type='application/json')
        self.assertEqual(response.status_code, 404, response.data)

    def test_add_switch_metadata_wrong_format(self):
        """Test add_switch_metadata_wrong_format."""
        dpid = "00:00:00:00:00:00:00:01"
        api = get_test_client(self.napp.controller, self.napp)
        payload = 'A'

        url = f'{self.server_name_url}/v3/switches/{dpid}/metadata'
        response = api.post(url, data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 400, response.data)

        payload = None
        response = api.post(url, data=json.dumps(payload),
                            content_type='application/json')
        self.assertEqual(response.status_code, 415, response.data)

    @patch('napps.kytos.topology.main.Main.notify_metadata_changes')
    def test_delete_switch_metadata(self, mock_metadata_changes):
        """Test delete_switch_metadata."""
        dpid = "00:00:00:00:00:00:00:01"
        mock_switch = get_switch_mock(dpid)
        self.napp.controller.switches = {dpid: mock_switch}
        api = get_test_client(self.napp.controller, self.napp)

        key = "A"
        url = f'{self.server_name_url}/v3/switches/{dpid}/metadata/{key}'
        response = api.delete(url)
        mock_metadata_changes.assert_called()
        self.assertEqual(response.status_code, 200, response.data)

        # fail case
        key = "A"
        dpid = "00:00:00:00:00:00:00:02"
        url = f'{self.server_name_url}/v3/switches/{dpid}/metadata/{key}'
        response = api.delete(url)
        mock_metadata_changes.assert_called()
        self.assertEqual(response.status_code, 404, response.data)

    @patch('napps.kytos.topology.main.Main.save_status_on_storehouse')
    def test_enable_interfaces(self, mock_save_status):
        """Test enable_interfaces."""
        dpid = '00:00:00:00:00:00:00:01'
        mock_switch = get_switch_mock(dpid)
        mock_interface_1 = get_interface_mock('s1-eth1', 1, mock_switch)
        mock_interface_2 = get_interface_mock('s1-eth2', 2, mock_switch)
        mock_switch.interfaces = {1: mock_interface_1, 2: mock_interface_2}
        self.napp.controller.switches = {dpid: mock_switch}
        api = get_test_client(self.napp.controller, self.napp)

        interface_id = '00:00:00:00:00:00:00:01:1'
        url = f'{self.server_name_url}/v3/interfaces/{interface_id}/enable'
        response = api.post(url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(mock_interface_1.enable.call_count, 1)
        self.assertEqual(mock_interface_2.enable.call_count, 0)
        mock_save_status.assert_called()

        mock_interface_1.enable.call_count = 0
        mock_interface_2.enable.call_count = 0
        url = f'{self.server_name_url}/v3/interfaces/switch/{dpid}/enable'
        response = api.post(url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(mock_interface_1.enable.call_count, 1)
        self.assertEqual(mock_interface_2.enable.call_count, 1)

        # test interface not found
        interface_id = '00:00:00:00:00:00:00:01:3'
        mock_interface_1.enable.call_count = 0
        mock_interface_2.enable.call_count = 0
        url = f'{self.server_name_url}/v3/interfaces/{interface_id}/enable'
        response = api.post(url)
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(mock_interface_1.enable.call_count, 0)
        self.assertEqual(mock_interface_2.enable.call_count, 0)

        # test switch not found
        dpid = '00:00:00:00:00:00:00:02'
        url = f'{self.server_name_url}/v3/interfaces/switch/{dpid}/enable'
        response = api.post(url)
        self.assertEqual(response.status_code, 404, response.data)
        self.assertEqual(mock_interface_1.enable.call_count, 0)
        self.assertEqual(mock_interface_2.enable.call_count, 0)

    @patch('napps.kytos.topology.main.Main.save_status_on_storehouse')
    def test_disable_interfaces(self, mock_save_status):
        """Test disable_interfaces."""
        interface_id = '00:00:00:00:00:00:00:01:1'
        dpid = '00:00:00:00:00:00:00:01'
        mock_switch = get_switch_mock(dpid)
        mock_interface_1 = get_interface_mock('s1-eth1', 1, mock_switch)
        mock_interface_2 = get_interface_mock('s1-eth2', 2, mock_switch)
        mock_switch.interfaces = {1: mock_interface_1, 2: mock_interface_2}
        self.napp.controller.switches = {dpid: mock_switch}
        api = get_test_client(self.napp.controller, self.napp)

        url = f'{self.server_name_url}/v3/interfaces/{interface_id}/disable'
        response = api.post(url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(mock_interface_1.disable.call_count, 1)
        self.assertEqual(mock_interface_2.disable.call_count, 0)
        mock_save_status.assert_called()

        mock_interface_1.disable.call_count = 0
        mock_interface_2.disable.call_count = 0
        url = f'{self.server_name_url}/v3/interfaces/switch/{dpid}/disable'
        response = api.post(url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(mock_interface_1.disable.call_count, 1)
        self.assertEqual(mock_interface_2.disable.call_count, 1)

        # test interface not found
        interface_id = '00:00:00:00:00:00:00:01:3'
        mock_interface_1.disable.call_count = 0
        mock_interface_2.disable.call_count = 0
        url = f'{self.server_name_url}/v3/interfaces/{interface_id}/disable'
        response = api.post(url)
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(mock_interface_1.disable.call_count, 0)
        self.assertEqual(mock_interface_2.disable.call_count, 0)

        # test switch not found
        dpid = '00:00:00:00:00:00:00:02'
        url = f'{self.server_name_url}/v3/interfaces/switch/{dpid}/disable'
        response = api.post(url)
        self.assertEqual(response.status_code, 404, response.data)
        self.assertEqual(mock_interface_1.disable.call_count, 0)
        self.assertEqual(mock_interface_2.disable.call_count, 0)

    def test_get_interface_metadata(self):
        """Test get_interface_metada."""
        interface_id = '00:00:00:00:00:00:00:01:1'
        dpid = '00:00:00:00:00:00:00:01'
        mock_switch = get_switch_mock(dpid)
        mock_interface = get_interface_mock('s1-eth1', 1, mock_switch)
        mock_interface.metadata = {"metada": "A"}
        mock_switch.interfaces = {1: mock_interface}
        self.napp.controller.switches = {dpid: mock_switch}
        api = get_test_client(self.napp.controller, self.napp)

        url = f'{self.server_name_url}/v3/interfaces/{interface_id}/metadata'
        response = api.get(url)
        self.assertEqual(response.status_code, 200, response.data)

        # fail case switch not found
        interface_id = '00:00:00:00:00:00:00:02:1'
        url = f'{self.server_name_url}/v3/interfaces/{interface_id}/metadata'
        response = api.get(url)
        self.assertEqual(response.status_code, 404, response.data)

        # fail case interface not found
        interface_id = '00:00:00:00:00:00:00:01:2'
        url = f'{self.server_name_url}/v3/interfaces/{interface_id}/metadata'
        response = api.get(url)
        self.assertEqual(response.status_code, 404, response.data)

    @patch('napps.kytos.topology.main.Main.notify_metadata_changes')
    def test_add_interface_metadata(self, mock_metadata_changes):
        """Test add_interface_metadata."""
        interface_id = '00:00:00:00:00:00:00:01:1'
        dpid = '00:00:00:00:00:00:00:01'
        mock_switch = get_switch_mock(dpid)
        mock_interface = get_interface_mock('s1-eth1', 1, mock_switch)
        mock_interface.metadata = {"metada": "A"}
        mock_switch.interfaces = {1: mock_interface}
        self.napp.controller.switches = {dpid: mock_switch}
        api = get_test_client(self.napp.controller, self.napp)

        url = f'{self.server_name_url}/v3/interfaces/{interface_id}/metadata'
        payload = {"metada": "A"}
        response = api.post(url, data=json.dumps(payload),
                            content_type='application/json')
        self.assertEqual(response.status_code, 201, response.data)
        mock_metadata_changes.assert_called()

        # fail case switch not found
        interface_id = '00:00:00:00:00:00:00:02:1'
        url = f'{self.server_name_url}/v3/interfaces/{interface_id}/metadata'
        response = api.post(url, data=json.dumps(payload),
                            content_type='application/json')
        self.assertEqual(response.status_code, 404, response.data)

        # fail case interface not found
        interface_id = '00:00:00:00:00:00:00:01:2'
        url = f'{self.server_name_url}/v3/interfaces/{interface_id}/metadata'
        response = api.post(url, data=json.dumps(payload),
                            content_type='application/json')
        self.assertEqual(response.status_code, 404, response.data)

    def test_add_interface_metadata_wrong_format(self):
        """Test add_interface_metadata_wrong_format."""
        dpid = "00:00:00:00:00:00:00:01:1"
        api = get_test_client(self.napp.controller, self.napp)
        payload = 'A'

        url = f'{self.server_name_url}/v3/interfaces/{dpid}/metadata'
        response = api.post(url, data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 400, response.data)

        payload = None
        response = api.post(url, data=json.dumps(payload),
                            content_type='application/json')
        self.assertEqual(response.status_code, 415, response.data)

    def test_delete_interface_metadata(self):
        """Test delete_interface_metadata."""
        interface_id = '00:00:00:00:00:00:00:01:1'
        dpid = '00:00:00:00:00:00:00:01'
        iface_url = '/v3/interfaces/'
        mock_switch = get_switch_mock(dpid)
        mock_interface = get_interface_mock('s1-eth1', 1, mock_switch)
        mock_interface.remove_metadata.side_effect = [True, False]
        mock_interface.metadata = {"metada": "A"}
        mock_switch.interfaces = {1: mock_interface}
        self.napp.controller.switches = {'00:00:00:00:00:00:00:01':
                                         mock_switch}
        api = get_test_client(self.napp.controller, self.napp)

        key = 'A'
        url = f'{self.server_name_url}{iface_url}{interface_id}/metadata/{key}'
        response = api.delete(url)
        self.assertEqual(response.status_code, 200, response.data)

        # fail case switch not found
        key = 'A'
        interface_id = '00:00:00:00:00:00:00:02:1'
        url = f'{self.server_name_url}{iface_url}{interface_id}/metadata/{key}'
        response = api.delete(url)
        self.assertEqual(response.status_code, 404, response.data)

        # fail case interface not found
        key = 'A'
        interface_id = '00:00:00:00:00:00:00:01:2'
        url = f'{self.server_name_url}{iface_url}{interface_id}/metadata/{key}'
        response = api.delete(url)
        self.assertEqual(response.status_code, 404, response.data)

        # fail case metadata not found
        key = 'A'
        interface_id = '00:00:00:00:00:00:00:01:1'
        url = f'{self.server_name_url}{iface_url}{interface_id}/metadata/{key}'
        response = api.delete(url)
        self.assertEqual(response.status_code, 404, response.data)

    @patch('napps.kytos.topology.main.Main.save_status_on_storehouse')
    def test_enable_link(self, mock_save_status):
        """Test enable_link."""
        mock_link = MagicMock(Link)
        self.napp.links = {'1': mock_link}
        api = get_test_client(self.napp.controller, self.napp)
        mock_save_status.return_value = True

        link_id = 1
        url = f'{self.server_name_url}/v3/links/{link_id}/enable'
        response = api.post(url)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(mock_link.enable.call_count, 1)

        # fail case
        link_id = 2
        url = f'{self.server_name_url}/v3/links/{link_id}/enable'
        response = api.post(url)
        self.assertEqual(response.status_code, 404, response.data)

    @patch('napps.kytos.topology.main.Main.save_status_on_storehouse')
    def test_disable_link(self, mock_save_status):
        """Test disable_link."""
        mock_link = MagicMock(Link)
        self.napp.links = {'1': mock_link}
        api = get_test_client(self.napp.controller, self.napp)
        mock_save_status.return_value = True

        link_id = 1
        url = f'{self.server_name_url}/v3/links/{link_id}/disable'
        response = api.post(url)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(mock_link.disable.call_count, 1)

        # fail case
        link_id = 2
        url = f'{self.server_name_url}/v3/links/{link_id}/disable'
        response = api.post(url)
        self.assertEqual(response.status_code, 404, response.data)

    def test_get_link_metadata(self):
        """Test get_link_metadata."""
        mock_link = MagicMock(Link)
        mock_link.metadata = "A"
        self.napp.links = {'1': mock_link}
        msg_success = {"metadata": "A"}
        api = get_test_client(self.napp.controller, self.napp)

        link_id = 1
        url = f'{self.server_name_url}/v3/links/{link_id}/metadata'
        response = api.get(url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(msg_success, json.loads(response.data))

        # fail case
        link_id = 2
        url = f'{self.server_name_url}/v3/links/{link_id}/metadata'
        response = api.get(url)
        self.assertEqual(response.status_code, 404, response.data)

    @patch('napps.kytos.topology.main.Main.notify_metadata_changes')
    def test_add_link_metadata(self, mock_metadata_changes):
        """Test add_link_metadata."""
        mock_link = MagicMock(Link)
        mock_link.metadata = "A"
        self.napp.links = {'1': mock_link}
        payload = {"metadata": "A"}
        api = get_test_client(self.napp.controller, self.napp)

        link_id = 1
        url = f'{self.server_name_url}/v3/links/{link_id}/metadata'
        response = api.post(url, data=json.dumps(payload),
                            content_type='application/json')
        self.assertEqual(response.status_code, 201, response.data)
        mock_metadata_changes.assert_called()

        # fail case
        link_id = 2
        url = f'{self.server_name_url}/v3/links/{link_id}/metadata'
        response = api.post(url, data=json.dumps(payload),
                            content_type='application/json')
        self.assertEqual(response.status_code, 404, response.data)

    def test_add_link_metadata_wrong_format(self):
        """Test add_link_metadata_wrong_format."""
        link_id = 'cf0f4071be426b3f745027f5d22'
        api = get_test_client(self.napp.controller, self.napp)
        payload = "A"

        url = f'{self.server_name_url}/v3/links/{link_id}/metadata'
        response = api.post(url, data=payload,
                            content_type='application/json')
        self.assertEqual(response.status_code, 400, response.data)

        payload = None
        response = api.post(url, data=json.dumps(payload),
                            content_type='application/json')
        self.assertEqual(response.status_code, 415, response.data)

    @patch('napps.kytos.topology.main.Main.notify_metadata_changes')
    def test_delete_link_metadata(self, mock_metadata_changes):
        """Test delete_link_metadata."""
        mock_link = MagicMock(Link)
        mock_link.metadata = "A"
        mock_link.remove_metadata.side_effect = [True, False]
        self.napp.links = {'1': mock_link}
        api = get_test_client(self.napp.controller, self.napp)

        link_id = 1
        key = 'A'
        url = f'{self.server_name_url}/v3/links/{link_id}/metadata/{key}'
        response = api.delete(url)
        self.assertEqual(response.status_code, 200, response.data)
        mock_metadata_changes.assert_called()

        # fail case link not found
        link_id = 2
        key = 'A'
        url = f'{self.server_name_url}/v3/links/{link_id}/metadata/{key}'
        response = api.delete(url)
        self.assertEqual(response.status_code, 404, response.data)

        # fail case metadata not found
        link_id = 1
        key = 'A'
        url = f'{self.server_name_url}/v3/links/{link_id}/metadata/{key}'
        response = api.delete(url)
        self.assertEqual(response.status_code, 404, response.data)

    @patch('napps.kytos.topology.main.Main.notify_topology_update')
    @patch('napps.kytos.topology.main.Main.update_instance_metadata')
    def test_handle_new_switch(self, *args):
        """Test handle_new_switch."""
        (mock_instance_metadata, mock_notify_topology_update) = args
        mock_event = MagicMock()
        mock_switch = create_autospec(Switch)
        mock_event.content['switch'] = mock_switch
        self.napp.handle_new_switch(mock_event)
        mock_notify_topology_update.assert_called()
        mock_instance_metadata.assert_called()

    @patch('napps.kytos.topology.main.Main.notify_topology_update')
    def test_handle_connection_lost(self, mock_notify_topology_update):
        """Test handle connection_lost."""
        mock_event = MagicMock()
        mock_switch = create_autospec(Switch)
        mock_switch.return_value = True
        mock_event.content['source'] = mock_switch
        self.napp.handle_connection_lost(mock_event)
        mock_notify_topology_update.assert_called()

    @patch('napps.kytos.topology.main.Main.notify_topology_update')
    @patch('napps.kytos.topology.main.Main.update_instance_metadata')
    def test_handle_interface_up(self, *args):
        """Test handle_interface_up."""
        (mock_instance_metadata, mock_notify_topology_update) = args
        mock_event = MagicMock()
        mock_interface = create_autospec(Interface)
        mock_event.content['interface'] = mock_interface
        self.napp.handle_interface_up(mock_event)
        mock_notify_topology_update.assert_called()
        mock_instance_metadata.assert_called()

    @patch('napps.kytos.topology.main.Main.handle_interface_up')
    def test_handle_interface_created(self, mock_handle_interface_up):
        """Test handle interface created."""
        mock_event = MagicMock()
        self.napp.handle_interface_created(mock_event)
        mock_handle_interface_up.assert_called()

    @patch('napps.kytos.topology.main.Main.notify_topology_update')
    @patch('napps.kytos.topology.main.Main.handle_interface_link_down')
    def test_handle_interface_down(self, *args):
        """Test handle interface down."""
        (mock_handle_interface_link_down, mock_notify_topology_update) = args
        mock_event = MagicMock()
        mock_interface = create_autospec(Interface)
        mock_event.content['interface'] = mock_interface
        self.napp.handle_interface_down(mock_event)
        mock_handle_interface_link_down.assert_called()
        mock_notify_topology_update.assert_called()

    @patch('napps.kytos.topology.main.Main.handle_interface_down')
    def test_interface_deleted(self, mock_handle_interface_link_down):
        """Test interface deleted."""
        mock_event = MagicMock()
        self.napp.handle_interface_deleted(mock_event)
        mock_handle_interface_link_down.assert_called()

    @patch('napps.kytos.topology.main.Main._get_link_from_interface')
    @patch('napps.kytos.topology.main.Main.notify_topology_update')
    @patch('napps.kytos.topology.main.Main.update_instance_metadata')
    @patch('napps.kytos.topology.main.Main.notify_link_status_change')
    def test_interface_link_up(self, *args):
        """Test interface link_up."""
        (mock_status_change, mock_instance_metadata, mock_topology_update,
         mock_link_from_interface) = args

        now = time.time()
        mock_event = MagicMock()
        mock_interface_a = create_autospec(Interface)
        mock_interface_a.is_active.return_value = False
        mock_interface_b = create_autospec(Interface)
        mock_interface_b.is_active.return_value = True
        mock_link = create_autospec(Link)
        mock_link.get_metadata.return_value = now
        mock_link.is_active.side_effect = [False, True]
        mock_link.endpoint_a = mock_interface_a
        mock_link.endpoint_b = mock_interface_b
        mock_link_from_interface.return_value = mock_link
        content = {'interface': mock_interface_a}
        mock_event.content = content
        self.napp.link_up_timer = 1
        self.napp.handle_interface_link_up(mock_event)
        mock_topology_update.assert_called()
        mock_instance_metadata.assert_called()
        mock_status_change.assert_called()

    @patch('napps.kytos.topology.main.Main._get_link_from_interface')
    @patch('napps.kytos.topology.main.Main.notify_topology_update')
    @patch('napps.kytos.topology.main.Main.notify_link_status_change')
    def test_interface_link_down(self, *args):
        """Test interface link down."""
        (mock_status_change, mock_topology_update,
         mock_link_from_interface) = args

        mock_event = MagicMock()
        mock_interface = create_autospec(Interface)
        mock_link = create_autospec(Link)
        mock_link.is_active.return_value = True
        mock_link_from_interface.return_value = mock_link
        mock_event.content['interface'] = mock_interface
        self.napp.handle_interface_link_down(mock_event)
        mock_topology_update.assert_called()
        mock_status_change.assert_called()

    @patch('napps.kytos.topology.main.Main._get_link_or_create')
    @patch('napps.kytos.topology.main.Main.notify_topology_update')
    def test_add_links(self, *args):
        """Test add_links."""
        (mock_notify_topology_update, mock_get_link_or_create) = args
        mock_event = MagicMock()
        self.napp.add_links(mock_event)
        mock_get_link_or_create.assert_called()
        mock_notify_topology_update.assert_called()

    @patch('napps.kytos.topology.main.Main._get_switches_dict')
    @patch('napps.kytos.topology.main.StoreHouse.save_status')
    def test_save_status_on_store(self, *args):
        """Test save_status_on_storehouse."""
        (mock_save_status, mock_get_switches_dict) = args
        self.napp.save_status_on_storehouse()
        mock_get_switches_dict.assert_called()
        mock_save_status.assert_called()

    @patch('napps.kytos.topology.main.KytosEvent')
    @patch('kytos.core.buffers.KytosEventBuffer.put')
    def test_notify_switch_enabled(self, *args):
        """Test notify switch enabled."""
        dpid = "00:00:00:00:00:00:00:01"
        (mock_buffers_put, mock_event) = args
        self.napp.notify_switch_enabled(dpid)
        mock_event.assert_called()
        mock_buffers_put.assert_called()

    @patch('napps.kytos.topology.main.KytosEvent')
    @patch('kytos.core.buffers.KytosEventBuffer.put')
    def test_notify_switch_disabled(self, *args):
        """Test notify switch disabled."""
        dpid = "00:00:00:00:00:00:00:01"
        (mock_buffers_put, mock_event) = args
        self.napp.notify_switch_disabled(dpid)
        mock_event.assert_called()
        mock_buffers_put.assert_called()

    @patch('napps.kytos.topology.main.KytosEvent')
    @patch('kytos.core.buffers.KytosEventBuffer.put')
    def test_notify_topology_update(self, *args):
        """Test notify_topology_update."""
        (mock_buffers_put, mock_event) = args
        self.napp.notify_topology_update()
        mock_event.assert_called()
        mock_buffers_put.assert_called()

    @patch('napps.kytos.topology.main.KytosEvent')
    @patch('kytos.core.buffers.KytosEventBuffer.put')
    def test_notify_link_status_change(self, *args):
        """Test notify link status change."""
        (mock_buffers_put, mock_event) = args
        mock_link = create_autospec(Link)
        self.napp.notify_link_status_change(mock_link)
        mock_event.assert_called()
        mock_buffers_put.assert_called()

    @patch('napps.kytos.topology.main.KytosEvent')
    @patch('kytos.core.buffers.KytosEventBuffer.put')
    @patch('napps.kytos.topology.main.isinstance')
    def test_notify_metadata_changes(self, *args):
        """Test notify metadata changes."""
        (mock_isinstance, mock_buffers_put, mock_event) = args
        mock_isinstance.return_value = True
        mock_obj = MagicMock()
        mock_action = create_autospec(Switch)
        self.napp.notify_metadata_changes(mock_obj, mock_action)
        mock_event.assert_called()
        mock_isinstance.assert_called()
        mock_buffers_put.assert_called()

    @patch('napps.kytos.topology.main.KytosEvent')
    @patch('kytos.core.buffers.KytosEventBuffer.put')
    def test_notify_port_created(self, *args):
        """Test notify port created."""
        (mock_buffers_put, mock_kytos_event) = args
        mock_event = MagicMock()
        self.napp.notify_port_created(mock_event)
        mock_kytos_event.assert_called()
        mock_buffers_put.assert_called()

    @patch('napps.kytos.topology.main.KytosEvent')
    @patch('kytos.core.buffers.KytosEventBuffer.put')
    def test_save_metadata_on_store(self, *args):
        """Test test_save_metadata_on_store."""
        (mock_buffers_put, mock_kytos_event) = args
        mock_event = MagicMock()
        mock_switch = MagicMock()
        mock_interface = MagicMock()
        mock_link = MagicMock()
        self.napp.store_items = {'switches': mock_switch,
                                 'interfaces': mock_interface,
                                 'links': mock_link}
        # test switches
        mock_event.content = {'switch': mock_switch}
        self.napp.save_metadata_on_store(mock_event)
        mock_kytos_event.assert_called()
        mock_buffers_put.assert_called()

        # test interfaces
        mock_event.content = {'interface': mock_interface}
        self.napp.save_metadata_on_store(mock_event)
        mock_kytos_event.assert_called()
        mock_buffers_put.assert_called()

        # test link
        mock_event.content = {'link': mock_link}
        self.napp.save_metadata_on_store(mock_event)
        mock_kytos_event.assert_called()
        mock_buffers_put.assert_called()

    @patch('napps.kytos.topology.main.KytosEvent')
    @patch('kytos.core.buffers.KytosEventBuffer.put')
    def test_verify_storehouse(self, *args):
        """Test verify_storehouse."""
        (mock_buffers_put, mock_kytos_event) = args
        mock_entities = MagicMock()
        self.napp.verify_storehouse(mock_entities)
        mock_buffers_put.assert_called()
        mock_kytos_event.assert_called()

    @patch('napps.kytos.topology.main.KytosEvent')
    @patch('kytos.core.buffers.KytosEventBuffer.put')
    def test_request_retrieve_entities(self, *args):
        """Test retrive_entities."""
        (mock_buffers_put, mock_kytos_event) = args
        mock_event = MagicMock()
        mock_data = MagicMock()
        mock_error = MagicMock()
        mock_event.content = {"namespace": "test_box"}
        self.napp.request_retrieve_entities(mock_event, mock_data, mock_error)
        mock_kytos_event.assert_called()
        mock_buffers_put.assert_called()

        self.napp.request_retrieve_entities(mock_event, None, mock_error)
        mock_kytos_event.assert_called()
        mock_buffers_put.assert_called()

    @patch('napps.kytos.topology.main.Main.notify_link_status_change')
    def test_handle_link_maintenance_start(self, status_change_mock):
        """Test handle_link_maintenance_start."""
        link1 = MagicMock()
        link1.id = 2
        link2 = MagicMock()
        link2.id = 3
        link3 = MagicMock()
        link3.id = 4
        content = {'links': [link1, link2]}
        event = MagicMock()
        event.content = content
        self.napp.links = {2: link1, 4: link3}
        self.napp.handle_link_maintenance_start(event)
        status_change_mock.assert_called_once_with(link1)

    @patch('napps.kytos.topology.main.Main.notify_link_status_change')
    def test_handle_link_maintenance_end(self, status_change_mock):
        """Test handle_link_maintenance_end."""
        link1 = MagicMock()
        link1.id = 2
        link2 = MagicMock()
        link2.id = 3
        link3 = MagicMock()
        link3.id = 4
        content = {'links': [link1, link2]}
        event = MagicMock()
        event.content = content
        self.napp.links = {2: link1, 4: link3}
        self.napp.handle_link_maintenance_end(event)
        status_change_mock.assert_called_once_with(link1)

    @patch('napps.kytos.topology.main.Main.handle_link_down')
    def test_handle_switch_maintenance_start(self, handle_link_down_mock):
        """Test handle_switch_maintenance_start."""
        switch1 = MagicMock()
        interface1 = MagicMock()
        interface1.is_active.return_value = True
        interface2 = MagicMock()
        interface2.is_active.return_value = False
        interface3 = MagicMock()
        interface3.is_active.return_value = True
        switch1.interfaces = {1: interface1, 2: interface2, 3: interface3}
        switch2 = MagicMock()
        interface4 = MagicMock()
        interface4.is_active.return_value = False
        interface5 = MagicMock()
        interface5.is_active.return_value = True
        switch2.interfaces = {1: interface4, 2: interface5}
        content = {'switches': [switch1, switch2]}
        event = MagicMock()
        event.content = content
        self.napp.handle_switch_maintenance_start(event)
        self.assertEqual(handle_link_down_mock.call_count, 3)

    @patch('napps.kytos.topology.main.Main.handle_link_up')
    def test_handle_switch_maintenance_end(self, handle_link_up_mock):
        """Test handle_switch_maintenance_end."""
        switch1 = MagicMock()
        interface1 = MagicMock()
        interface1.is_active.return_value = True
        interface2 = MagicMock()
        interface2.is_active.return_value = False
        interface3 = MagicMock()
        interface3.is_active.return_value = True
        switch1.interfaces = {1: interface1, 2: interface2, 3: interface3}
        switch2 = MagicMock()
        interface4 = MagicMock()
        interface4.is_active.return_value = False
        interface5 = MagicMock()
        interface5.is_active.return_value = True
        switch2.interfaces = {1: interface4, 2: interface5}
        content = {'switches': [switch1, switch2]}
        event = MagicMock()
        event.content = content
        self.napp.handle_switch_maintenance_end(event)
        self.assertEqual(handle_link_up_mock.call_count, 5)
