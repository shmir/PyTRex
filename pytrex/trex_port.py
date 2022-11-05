"""
Classes and utilities that represents TRex port.
"""
import re
import time
from copy import deepcopy
from enum import Enum
from typing import Dict, List, Optional

from trafficgenerator import TgnError

from pytrex.api import RpcCmdData
from pytrex.trex_capture import TrexCapture, TrexCaptureMode
from pytrex.trex_object import TrexObject
from pytrex.trex_stream import TrexStream, TrexYamlLoader

MASK_ALL = (1 << 64) - 1


def decode_multiplier(val, allow_update=False, divide_count=1):

    factor_table = {None: 1, "k": 1e3, "m": 1e6, "g": 1e9}
    pattern = r"^(\d+(\.\d+)?)(((k|m|g)?(bpsl1|pps|bps))|%)?"

    # do we allow updates ?  +/-
    if not allow_update:
        pattern += "$"
        match = re.match(pattern, val)
        op = None
    else:
        pattern += r"([\+\-])?$"
        match = re.match(pattern, val)
        if match:
            op = match.group(7)
        else:
            op = None

    result = {}

    if not match:
        return None

    # value in group 1
    value = float(match.group(1))

    # decode unit as whole
    unit = match.group(3)

    # k,m,g
    factor = match.group(5)

    # type of multiplier
    m_type = match.group(6)

    # raw type(factor)
    if not unit:
        result["type"] = "raw"
        result["value"] = value

    # percentage
    elif unit == "%":
        result["type"] = "percentage"
        result["value"] = value

    elif m_type == "bps":
        result["type"] = "bps"
        result["value"] = value * factor_table[factor]

    elif m_type == "pps":
        result["type"] = "pps"
        result["value"] = value * factor_table[factor]

    elif m_type == "bpsl1":
        result["type"] = "bpsl1"
        result["value"] = value * factor_table[factor]

    if op == "+":
        result["op"] = "add"
    elif op == "-":
        result["op"] = "sub"
    else:
        result["op"] = "abs"

    if result["op"] != "percentage":
        result["value"] = result["value"] / divide_count

    return result


class PortState(Enum):
    """Port states. Enum names are the port states used in RPC."""

    DOWN = 0
    IDLE = 1
    STREAMS = 2
    TX = 3
    PAUSE = 4
    PCAP_TX = 5


class TrexPort(TrexObject):
    """Represents TRex port."""

    def __init__(self, parent, index):
        """Create port object.

        :param parent: parent chassis.
        :param index: port index, zero based
        """
        super().__init__(parent=parent, objType="port", index=index)
        self.mul = decode_multiplier("1", allow_update=False, divide_count=1)
        self.duration = -1
        self.force = False
        self.mask = MASK_ALL
        self.start_at_ts = 0.0
        self.stat_names: dict = None
        self.base_xstats: dict = None
        self.base_stats: dict = None
        self.statistics: dict = None
        self.xstatistics: dict = None

    def reserve(self, force: Optional[bool] = False, reset: Optional[bool] = False) -> None:
        """Reserve port.

        TRex -> Port -> [Force] Acquire.
        Acquire returns port handler that must be used in subsequent port method calls.

        :param force: True - take forcefully, False - fail if port is reserved by other user
        :param reset: True - reset port, False - leave port configuration
        """
        params = {"port_id": int(self.index), "user": self.username, "session_id": self.session_id, "force": force}
        self._data["objRef"] = self.api.rpc.transmit("acquire", params)["result"]
        if reset:
            self.reset()

    def release(self):
        """Release port.

        TRex -> Port -> Release Acquire.
        """
        self.transmit("release")

    def reset(self) -> None:
        self.stop_transmit()
        self.set_promiscuous_mode(enabled=True)
        self.remove_all_streams()

    #
    # Configuration.
    #

    def get_status(self):
        params = {"session_id": self.session_id}
        rc = self.api.rpc.transmit("get_port_status", params)
        return rc["result"]

    def set_service_mode(self, enabled):
        params = {"session_id": self.session_id, "enabled": enabled}
        self.transmit("service", params)

    def set_promiscuous_mode(self, enabled):
        params = {"session_id": self.session_id, "attr": {"promiscuous": {"enabled": enabled}}}
        self.transmit("set_port_attr", params)

    #
    # Streams.
    #

    def remove_all_streams(self) -> None:
        self.del_objects_by_type("stream")
        self.transmit("remove_all_streams")

    def add_stream(self, name: str) -> TrexStream:
        """Add stream with default configuration.

        :param name: unique stream name
        """
        return TrexStream(self, index=len(self.streams), name=name)

    def load_streams(self, yaml_file) -> None:
        """Load streams from YAML file.

        :param yaml_file: full path to yaml profile file.
        """
        yaml_loader = TrexYamlLoader(self, yaml_file)
        yaml_loader.parse()

    def save_streams(self, yaml_file):
        """Save streams to YAML file.

        :param yaml_file: full path to yaml profile file.
        """
        raise NotImplementedError()

    def write_streams(self) -> None:
        """Write all streams to server."""
        self.transmit("remove_all_streams")
        batch = []
        for name, stream in self.streams.items():
            stream_fields = deepcopy(stream.fields)
            stream_id = list(self.streams.keys()).index(name) + 1
            next_stream = stream_fields.pop("next_stream")
            stream_fields["next_stream_id"] = list(self.streams.keys()).index(next_stream) + 1 if next_stream else -1

            params = {"handler": self.ref, "port_id": self.id, "stream_id": stream_id, "stream": stream_fields}
            cmd = RpcCmdData("add_stream", params, "core")
            batch.append(cmd)

        self.api.rpc.transmit_batch(batch)

    #
    # Control.
    #

    def get_port_state(self) -> PortState:
        """Get port state from server."""
        rc = self.transmit("get_port_status")
        return PortState[rc["result"]["state"].upper()]

    def is_transmitting(self) -> bool:
        """Return True if port is transmitting, else return False."""
        return self.get_port_state() in [PortState.TX, PortState.PCAP_TX]

    def start_transmit(self, blocking: Optional[bool] = False) -> None:
        """Start transmit.

        :param blocking: if blockeing - wait for transmit end, else - return after transmit starts.
        :return:
        """
        if self.get_port_state() == PortState.IDLE:
            raise TgnError("unable to start traffic - no streams attached to port")

        params = {
            "mul": self.mul,
            "duration": self.duration,
            "force": self.force,
            "core_mask": self.mask,
            "start_at_ts": self.start_at_ts,
        }
        self.transmit("start_traffic", params)

        if blocking:
            self.wait_transmit()

    def stop_transmit(self) -> None:
        """Stop transmit."""
        self.transmit("stop_traffic")
        self.wait_transmit()

    def wait_transmit(self) -> None:
        """Wait until port finishes transmition."""
        while self.is_transmitting():
            time.sleep(1)

    #
    # Statistics.
    #

    def clear_stats(self) -> None:
        """Get base counters values so read stats can subtract them from current counters values."""
        values = self.transmit("get_port_xstats_values")["result"]
        self.stat_names = self.transmit("get_port_xstats_names")["result"]
        self.base_xstats = dict(zip(self.stat_names["xstats_names"], values["xstats_values"]))
        self.base_stats = self.transmit("get_port_stats")["result"]
        self.statistics = self.base_stats
        self.xstatistics = self.base_xstats

    def read_stats(self) -> dict:
        """Read current counters values and adjust them based on base counters read before the test."""
        self.statistics = self.transmit("get_port_stats")["result"]
        for stat, value in self.statistics.items():
            if not stat.endswith("ps"):
                value -= self.base_stats[stat]
            self.statistics[stat] = value
        return self.statistics

    def read_xstats(self) -> dict:
        """Read current extended counters values and adjust them based on base counters read before the test."""
        values = self.transmit("get_port_xstats_values")["result"]
        self.xstatistics = dict(zip(self.stat_names["xstats_names"], values["xstats_values"]))
        for stat, value in self.xstatistics.items():
            self.statistics[stat] = value - self.base_xstats[stat]
        return self.xstatistics

    #
    # Capture
    #

    def clear_capture(self, rx: Optional[bool] = True, tx: Optional[bool] = False) -> None:
        """Clear existing capture IDs on the port.

        :param rx: if rx, clear RX captures, else, do not clear
        :param tx: if tx, clear TX captures, else, do not clear
        """
        rc = self.transmit("capture", {"command": "status"})
        for capture in rc["result"]:
            if rx and int(capture["filter"]["rx"]) - 1 == self.id or tx and int(capture["filter"]["tx"]) - 1 == self.id:
                params = {"command": "remove", "capture_id": capture["id"]}
                self.transmit("capture", params=params)

    def start_capture(
        self,
        rx: Optional[bool] = True,
        tx: Optional[bool] = False,
        limit: Optional[int] = 1000,
        mode: Optional[TrexCaptureMode] = TrexCaptureMode.FIXED,
        bpf_filter: Optional[str] = "",
    ) -> None:
        """Start capture.

        :param rx: if rx, capture RX packets, else, do not capture
        :param tx: if tx, capture TX packets, else, do not capture
        :param limit: limit the total number of captured packets (RX and TX) memory requierment is O(9K * limit).
        :param mode: when full, if fixed drop new packets, else (cyclic) drop old packets.
        :param bpf_filter:  A Berkeley Packet Filter pattern. Only packets matching the filter will be captured.
        """
        self.clear_capture(rx=rx, tx=tx)
        self.set_service_mode(enabled=True)
        self.capture.start(rx, tx, limit, mode, bpf_filter)

    def stop_capture(self, limit: Optional[int] = 1000, output: Optional[str] = None) -> List[Dict]:
        """Stop capture.

        :param limit: limit the number of packets that will be read from the capture buffer.
        :param output: full path to file where capture packets will be stored, if None - do not store packets in file.
            You can run text2pcap on the resulted file and then open it with wireshark.
        """
        return self.capture.stop(limit, output)

    #
    # Low level.
    #

    def transmit(self, method_name: str, params: Optional[Dict] = None) -> dict:
        """Transmit port RPC command.

        :param method_name: RPC command
        :param params: command parameters
        """
        params = params if params else {}
        params["port_id"] = self.id
        params["handler"] = self.ref
        return super().transmit(method_name, params)

    #
    # Properties.
    #

    @property
    def streams(self) -> Dict[str, "TrexPort"]:
        return {s.name: s for s in self.get_objects_by_type("stream")}

    @property
    def capture(self) -> TrexCapture:
        """Return TrexCapture object for the port."""
        if not self.get_object_by_type("capture"):
            TrexCapture(self)
        return self.get_object_by_type("capture")
