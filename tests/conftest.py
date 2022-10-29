"""
Pytest conftest for trex package testing.
"""
from typing import Iterable, List

import pytest
from trafficgenerator.tgn_conftest import log_level, pytest_addoption, sut  # pylint: unused-import

from pytrex import TrexError
from pytrex.trex_app import TrexApp
from tests import TrexSutUtils


@pytest.fixture(scope="session")
def sut_utils(sut: dict) -> TrexSutUtils:
    """Yield the sut dictionary from the sut file."""
    return TrexSutUtils(sut)


@pytest.fixture(scope="session")
def trex(sut_utils: TrexSutUtils) -> Iterable[TrexApp]:
    _trex = sut_utils.trex()
    try:
        _trex.server.connect()
    except TrexError:
        server = sut_utils.server()
        server.exec_cmd("")
    yield _trex
    if _trex.server:
        _trex.server.disconnect()


@pytest.fixture(scope="session")
def ports(sut_utils: TrexSutUtils) -> List[str]:
    return sut_utils.locations()
