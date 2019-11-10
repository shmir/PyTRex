
import sys
import os
import pytest
import json
import time
import logging

from trex_stl import STLClient, LoggerApi, Port
from trex_stl.utils.parsing_opts import decode_multiplier
from trex_stl.trex_stl_streams import STLProfile

from trex.trex_app import TrexApp


@pytest.fixture(scope='module')
def logger():
    logger = logging.getLogger('trex')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))
    yield logger


@pytest.fixture(scope='module')
def app(pytestconfig, logger):
    client = STLClient(server=pytestconfig.getoption('chassis'), verbose_level=LoggerApi.VERBOSE_HIGH)
    client.connect()
    yield client
    client.disconnect()


@pytest.fixture(scope='module')
def client(pytestconfig):
    client = STLClient(server=pytestconfig.getoption('chassis'), verbose_level=LoggerApi.VERBOSE_HIGH)
    client.connect()
    client.acquire(ports=pytestconfig.getoption('ports'), force=True, sync_streams=False)
    client.reset()
    yield client
    client.release()


class TestOffline:

    def test_hello_world(self, app):
        pass

    def test_reserve_ports(self, client):
        pass

    def test_load_profle(self, client):
        config_file = os.path.join(os.path.dirname(__file__), 'profiles', 'test_profile_1.yaml')
        profile = STLProfile.load_yaml(config_file)
        port_1 = list(client.ports.values())[0]
        port_1.add_streams(profile.get_streams())
        assert len(port_1.streams) == len(profile.streams)
        port_1.sync_streams()
        assert len(port_1.streams) == len(profile.streams)

    def test_run_traffic(self, client):
        config_file = os.path.join(os.path.dirname(__file__), 'profiles', 'test_profile_1.yaml')
        profile = STLProfile.load_yaml(config_file)
        port_1: Port = list(client.ports.values())[0]
        port_1.add_streams(profile.get_streams())
        mult_obj = decode_multiplier('1', allow_update=False, divide_count=1)
        port_1.start(mul=mult_obj, duration=-1, force=False, mask=None)
        client.wait_on_traffic()
        time.sleep(2)
        print(json.dumps(client.get_stats(), indent=2))
        print(json.dumps(port_1.get_stats(), indent=2))
        print(json.dumps(list(client.ports.values())[1].get_stats(), indent=2))
