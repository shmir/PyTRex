
import sys
import pytest
import logging
import json

from trex.trex_app import TrexApp


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
        trex.server.reserve_ports(ports, force=True)
