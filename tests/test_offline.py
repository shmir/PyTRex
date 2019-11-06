
import sys
import pytest
import logging

from trex.trex_app import TrexApp


@pytest.fixture(scope='module')
def logger():
    logger = logging.getLogger('trex')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))
    yield logger


@pytest.fixture(scope='module')
def app(pytestconfig, logger):
    trex = TrexApp(logger)
    trex.connect(pytestconfig.getoption('chassis'))
    yield trex
    trex.disconnect()


class TestOffline:

    def test_hello_world(self, app):
        pass

    def test_reserve_ports(self, client):
        pass
