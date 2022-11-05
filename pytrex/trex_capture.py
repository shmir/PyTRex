import base64
import binascii
from enum import Enum
from typing import List, Optional

from scapy.layers.l2 import Ether

from .trex_object import TrexObject


class TrexCaptureMode(Enum):
    FIXED = 0
    CYCLIC = 1


class TrexCapture(TrexObject):
    """Per port capture operations."""

    def __init__(self, parent) -> None:
        super().__init__(parent=parent, objType="capture")
        self.packets: List[dict] = []

    def start(
        self,
        rx: Optional[bool] = True,
        tx: Optional[bool] = False,
        limit: Optional[int] = 1000,
        mode: Optional[TrexCaptureMode] = TrexCaptureMode.FIXED,
        bpf_filter: Optional[str] = "",
    ) -> None:
        """Start capture on list of ports.

        :param rx: if rx, capture RX packets, else, do not capture
        :param tx: if tx, capture TX packets, else, do not capture
        :param limit: limit the total number of captured packets (RX and TX) memory requirement is O(9K * limit).
        :param mode: when full, if fixed drop new packets, else (cyclic) drop old packets.
        :param bpf_filter:  A Berkeley Packet Filter pattern. Only packets matching the filter will be captured.
        """
        params = {
            "command": "start",
            "limit": limit,
            "mode": mode.name.lower(),
            "rx": [self.parent.id] if rx else [],
            "tx": [self.parent.id] if tx else [],
            "filter": bpf_filter,
        }
        rc = self.transmit("capture", params=params)
        self._data["index"] = rc["result"]["capture_id"]

    def stop(self, limit: int = 1000, output: Optional[str] = None) -> List[dict]:
        """Stop capture.

        :param limit: limit the number of packets that will be read from the capture buffer.
        :param output: full path to file where capture packets will be stored, if None - do not store packets in file.
        """
        params = {"command": "stop", "capture_id": self.id}
        rc = self.transmit("capture", params=params)
        pkt_count = rc["result"]["pkt_count"]
        packets = self.fetch_capture_packets(min(limit, pkt_count), output)

        params = {"command": "remove", "capture_id": self.id}
        self.transmit("capture", params=params)

        return packets

    def fetch_capture_packets(self, limit: int = 1000, output: Optional[str] = None) -> List[dict]:
        """Fetch packets from existing active capture.

        :param limit: limit the number of packets that will be read from the capture buffer.
        :param output: full path to file where capture packets will be stored, if None - do not store packets in file.
        """
        self.packets = []
        pending = limit
        while pending > 0:
            params = {"command": "fetch", "capture_id": self.id, "pkt_limit": min(50, pending)}
            rc = self.transmit("capture", params=params)

            pkts = rc["result"]["pkts"]
            pending = rc["result"]["pending"]
            start_ts = rc["result"]["start_ts"]

            # write packets
            for pkt in pkts:
                pkt["rel_ts"] = pkt["ts"] - start_ts
                pkt["binary"] = base64.b64decode(pkt["binary"])
                pkt["hex"] = binascii.hexlify(pkt["binary"])
                pkt["scapy"] = Ether(pkt["binary"])
                self.packets.append(pkt)

        if output:
            with open(output, "w+") as capture_file:
                for packet in self.packets:
                    str_packet = str(packet["hex"])[2:-1]
                    capture_file.write("000000 ")
                    capture_file.write(" ".join(a + b for a, b in zip(str_packet[::2], str_packet[1::2])))
                    capture_file.write("\n")

        return self.packets
