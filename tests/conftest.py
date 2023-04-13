"""
Pytest conftest for trex package testing.
"""
from typing import Iterable

import pytest
from trafficgenerator.tgn_conftest import log_level, pytest_addoption, sut  # pylint: disable=unused-import

from pytrex import TrexError
from pytrex.trex_app import TrexApp
from tests import TrexSutUtils


@pytest.fixture(scope="session")
def sut_utils(sut: dict) -> TrexSutUtils:
    """Yield the sut dictionary from the sut file."""
    return TrexSutUtils(sut)


@pytest.fixture(scope="session")
def trex(sut_utils: TrexSutUtils) -> Iterable[TrexApp]:
    """Yield connected TrexApp."""
    trex_ = sut_utils.trex()
    try:
        trex_.server.connect()
    except TrexError:
        # TODO: start TRex server.
        raise TrexError("TRex server is not running.")
    yield trex_
    if trex_.server:
        trex_.server.disconnect()


@pytest.fixture(scope="session")
def ports(sut_utils: TrexSutUtils) -> list[int]:
    """Yield TRex device under test ports locations."""
    return sut_utils.locations()
