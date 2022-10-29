"""
Tests for pytrex package.
"""
import getpass
from typing import List

from trafficgenerator import TgnSutUtils, set_logger
from trafficgenerator.tgn_server import Server

from pytrex.trex_app import TrexApp


class TrexSutUtils(TgnSutUtils):
    """IxTRex SUT utilities."""

    def trex(self) -> TrexApp:
        return TrexApp(getpass.getuser(), self.sut["server"]["ip"])

    def locations(self) -> List[str]:
        return self.sut["server"]["ports"]

    def server(self) -> Server:
        name = self.sut["server"].get("name", "Trex-Server")
        host = self.sut["server"]["ip"]
        user = self.sut["server"]["user"]
        password = self.sut["server"]["password"]
        return Server(name, host, user, password)


set_logger()
