
import sys
import pytest
import logging
import time
import json

from pytrex.trex_app import TrexApp
from pytrex.trex_port import PortState, decode_multiplier


@pytest.fixture(scope='module')
def logger():
    logger = logging.getLogger('trex')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))
    yield logger


@pytest.fixture(scope='module')
def trex(pytestconfig, logger):
    trex = TrexApp(logger)
    trex.connect(pytestconfig.getoption('chassis'))
    yield trex
    trex.disconnect()


@pytest.fixture(scope='module')
def ports(pytestconfig):
    yield pytestconfig.getoption('ports')


class TestOffline:

    def test_hello_world(self, trex):
        pass

    def test_inventory(self, trex):
        sys_info = trex.server.get_system_info()
        supported_cmds = trex.server.get_supported_cmds()
        print(f'server: {sys_info["core_type"]}')
        for port in sys_info['ports']:
            print(f'\tport: {port["description"]}')
        print(f'commands: {supported_cmds}')

    def test_reserve_ports(self, trex, ports):
        trex_ports = trex.server.reserve_ports(ports, force=True)
        assert len(trex_ports) == 2

    def test_load_streams(self, trex, ports):
        trex_port = list(trex.server.reserve_ports(ports, force=True).values())[0]
        trex_port.remove_all_streams()
        assert trex_port.get_port_state() == PortState.Idle
        trex_port.load_streams('profiles/test_profile_1.yaml')
        trex_port.write_streams()
        assert trex_port.get_port_state() == PortState.Streams

    def test_traffic(self, trex, ports):
        trex_ports = trex.server.reserve_ports(ports, force=True)
        tx_port = list(trex_ports.values())[0]
        rx_port = list(trex_ports.values())[1]
        tx_port.remove_all_streams()
        tx_port.load_streams('profiles/test_profile_1.yaml')
        tx_port.write_streams()

        rx_port.clear_stats()
        print(json.dumps(rx_port.get_stats(), indent=2))

        mult_obj = decode_multiplier('1', allow_update=False, divide_count=1)
        tx_port.start_transmit(mul=mult_obj, duration=-1, force=False, mask=None)
        tx_port.wait_transmit()
        time.sleep(2)
        print(json.dumps(rx_port.get_stats(), indent=2))
