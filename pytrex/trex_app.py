"""
Classes and utilities that represents TRex GUI application.
"""
import logging
import random
import time
from typing import Dict, List, Optional

from trafficgenerator import ApiType, TgnApp

from pytrex.api.trex_event import EventsHandler
from pytrex.api.trex_stl_conn import Connection
from pytrex.trex_object import TrexObject
from pytrex.trex_port import TrexCaptureMode, TrexPort
from pytrex.trex_statistics_view import TrexStreamStatistics

logger = logging.getLogger("tgn.trex")


class TrexApp(TgnApp):
    """TrexApp object, equivalent to TRex application."""

    def __init__(self, username: str, ip: str, port: int = 4501, async_port: int = 4500, virtual: bool = False) -> None:
        """Start TRex application.

        :param username: User name.
        :param ip: TRex server IP.
        :param port: TRex server RPC port.
        :param async_port: Async port
        :param virtual: ???
        """
        super().__init__(logger, ApiType.socket)
        self.server = TrexServer(username, ip, port, async_port, virtual)


class TrexServer(TrexObject):
    """Represents single TRex server."""

    def __init__(self, username: str, ip: str, port: int = 4501, async_port: int = 4500, virtual: bool = False) -> None:
        """Start TRex application.

        :param ip: TRex server IP.
        :param port: TRex server RPC port.
        :param async_port: Async port
        :param username: User name.
        :param virtual: ???
        """
        self.logger = logger
        self.username = username
        self.ip = ip
        self.port = port
        self.async_port = async_port
        self.virtual = virtual
        self.server = self
        self.event_handler: EventsHandler = None
        super().__init__(parent=None, objType="server", objRef="server")

    def connect(self) -> None:
        """Connect to the TRex server."""
        self.event_handler = EventsHandler(self)
        connection_info = {
            "username": self.username,
            "server": self.ip,
            "sync_port": self.port,
            "async_port": self.async_port,
            "virtual": self.virtual,
        }
        self.api = Connection(connection_info, self.logger, self)
        self.api.connect()
        self.session_id = random.getrandbits(32)

    def disconnect(self) -> None:
        """Release all ports and disconnect from server."""
        for port in self.ports.values():
            port.release()
        self.api.disconnect()

    def reserve_ports(self, locations: List[int], force: bool = False, reset: bool = False) -> dict[int, TrexPort]:
        """Reserve ports.

        TRex -> Port -> Acquire.

        :param locations: list of ports locations in the form <port number> to reserve
        :param force: True - take forcefully. False - fail if port is reserved by other user
        :param reset: True - reset port, False - leave port configuration
        :return: ports dictionary (location: object)
        """
        for location in locations:
            TrexPort(parent=self, index=location).reserve(force, reset)
        return self.ports

    #
    # Configuration
    #

    def get_system_info(self) -> dict:
        """Get system information from server."""
        return self.transmit("get_system_info", {})["result"]

    def get_supported_cmds(self) -> dict:
        """Get supported commands from server."""
        return self.transmit("get_supported_cmds", {})["result"]

    #
    # Control
    #

    def clear_stats(self, *ports: TrexPort) -> None:
        """Clear statistics on list of ports.

        :param ports: list of ports to start traffic on, if empty, clear all ports.
        """
        for port in ports or self.ports.values():
            port.clear_stats()
        TrexStreamStatistics.clear_stats(self)

    def start_transmit(self, blocking: bool = False, *ports: TrexPort) -> None:
        """Start traffic on list of ports.

        If possible, synchronize start of traffic, else, start.

        :param blocking: if blocking - wait for transmit end, else - return after transmit starts.
        :param ports: list of ports to start transmit on, if empty, start on all ports.
        """
        ports = ports or self.ports.values()

        synchronized = True
        if not len(ports) % 2:
            for port in ports:
                if list(self.ports.values()).index(port) ^ 1 not in list(self.ports.keys()):
                    synchronized = False
        else:
            synchronized = False

        if synchronized:
            save_level = self.logger.level
            start_time = time.time()
            rc = self.api.rpc.transmit("ping", api_class=None)
            start_at_ts = rc["result"]["ts"] + max((time.time() - start_time), 0.5) * len(ports)
            self.logger.level = save_level
        else:
            start_at_ts = 0

        for port in ports:
            port.start_at_ts = start_at_ts
            port.start_transmit(blocking=False)

        if blocking:
            self.wait_transmit(*ports)

    def stop_transmit(self, *ports: TrexPort) -> None:
        """Stop traffic on list of ports.

        :param ports: list of ports to stop transmit on, if empty, stop on all ports.
        """
        for port in ports or self.ports.values():
            port.stop_transmit()

    def wait_transmit(self, *ports: TrexPort) -> None:
        """Wait for transmit end on list of ports.

        :param ports: list of ports to wait for, if empty, wait for all ports.
        """
        for port in ports or self.ports.values():
            port.wait_transmit()
        time.sleep(4)

    def clear_capture(self, *ports: TrexPort) -> None:
        """Clear all existing capture IDs on list ports.

        :param ports: list of ports to clear capture on, if empty, clear on all ports.
        """
        for port in ports or self.ports.values():
            port.clear_capture(rx=True, tx=True)

    def start_capture(
        self, limit: int = 1000, mode: TrexCaptureMode = TrexCaptureMode.FIXED, bpf_filter: str = "", *ports: TrexPort
    ) -> None:
        """Start RX capture on list of ports.

        :param limit: limit the total number of captrured packets (for all ports) memory requierment is O(9K * limit).
        :param mode: when full, if fixed drop new packets, else (cyclic) drop old packets.
        :param bpf_filter:  A Berkeley Packet Filter pattern. Only packets matching the filter will be captured.
        :param ports: list of ports to start capture on, if empty, start on all ports.
        """
        ports = ports or self.ports.values()
        for port in ports:
            port.start_capture(
                rx=True,
                tx=False,
                limit=int(limit / len(ports)),
                mode=mode,
                bpf_filter=bpf_filter,
            )

    def stop_capture(self, limit: int = 1000, output: Optional[str] = None, *ports) -> Dict[TrexPort, List]:
        """Stop capture on list of ports.

        :param limit: limit the total number of packets that will be read from the capture buffer of all ports.
        :param output: prefix for the capture file name.
            Capture files for each port will be stored in individual output file named 'prefix-{port ID}.txt'.
        :param ports: list of ports to stop capture on, if empty, stop on all ports.
        """
        ports = ports or self.ports.values()
        packets = {}
        for port in ports:
            port_output = f"{output}-{port.id}.txt" if output else None
            packets[port] = port.stop_capture(limit=int(limit / len(ports)), output=port_output)
        return packets

    #
    # Properties
    #

    @property
    def ports(self) -> dict[int, TrexPort]:
        """Return dictionary {index: TrexPort} of all ports."""
        return {p.id: p for p in self.get_objects_by_type("port")}

    #
    # Private
    #

    def _get_api_h(self):
        return self.api.get_api_h()
