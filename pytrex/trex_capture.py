
import base64
from typing import Optional, List, Dict
from enum import Enum
from scapy.layers.l2 import Ether

from .trex_object import TrexObject


class TrexCaptureMode(Enum):
    fixed = 0
    cyclic = 1


class TrexCapture(TrexObject):

    def __init__(self, parent):
        super().__init__(objType='capture', parent=parent)

    def start(self, rx: Optional[bool] = True, tx: Optional[bool] = False, limit: Optional[int] = 1000,
              mode: Optional[TrexCaptureMode] = TrexCaptureMode.fixed, bpf_filter: Optional[str] = '') -> None:
        """ Start capture on list of ports.

        :param rx: if rx, capture RX packets, else, do not capture
        :param tx: if tx, capture TX packets, else, do not capture
        :param limit: limit the total number of captrured packets (RX and TX) memory requierment is O(9K * limit).
        :param mode: when full, if fixed drop new packets, else (cyclic) drop old packets.
        :param bpf_filter:  A Berkeley Packet Filter pattern. Only packets matching the filter will be captured.
        """

        params = {'command': 'start',
                  'limit': limit,
                  'mode': mode.name,
                  'rx': [self.parent.id] if rx else [],
                  'tx': [self.parent.id] if tx else [],
                  'filter': bpf_filter}
        rc = self.transmit("capture", params=params)
        self._data['index'] = rc.data()['capture_id']

    def stop_capture(self, limit: Optional[int] = 1000, output: Optional[str] = None):
        """ Stop catture.

        :param limit: limit the number of packets that will be read from the capture buffer.
        :param output: full path to file where capture packets will be stored, if None - do not store packets in file.
        """

        params = {'command': 'stop',
                  'capture_id': self.id}
        rc = self.transmit("capture", params=params)
        pkt_count = rc.data()['pkt_count']
        packets = self.fetch_capture_packets(min(limit, pkt_count), output)

        params = {'command': 'remove',
                  'capture_id': self.id}
        self.transmit("capture", params=params)

        return packets

    def fetch_capture_packets(self, pkt_count: [Optional[int]] = 1000, output: Optional[str] = None) -> List[Dict]:
        """ Fetch packets from existing active capture

        :parameters:

            output: str / list
                if output is a 'str' - it will be interpeted as output filename
                if it is a list, the API will populate the list with packet objects

                in case 'output' is a list, each element in the list is an object
                containing:
                'binary' - binary bytes of the packet
                'origin' - RX or TX origin
                'ts'     - timestamp relative to the start of the capture
                'index'  - order index in the capture
                'port'   - on which port did the packet arrive or was transmitted from

            pkt_count: int
                maximum packets to fetch
        """

        self.packets = []
        pending = pkt_count
        while pending > 0:
            params = {'command': 'fetch',
                      'capture_id': self.id,
                      'pkt_limit': min(50, pending)}
            rc = self.transmit("capture", params=params)

            pkts = rc.data()['pkts']
            pending = rc.data()['pending']
            start_ts = rc.data()['start_ts']

            import binascii
            # write packets
            for pkt in pkts:
                pkt['rel_ts'] = pkt['ts'] - start_ts
                pkt['binary'] = base64.b64decode(pkt['binary'])
                pkt['hex'] = binascii.hexlify(pkt['binary'])
                pkt['scapy'] = Ether(pkt['binary'])
                self.packets.append(pkt)

        if output:
            with open(output, 'w+') as f:
                for packet in self.packets:
                    str_packet = str(packet['hex'])[2:-1]
                    f.write('000000 ')
                    f.write(' '.join(a+b for a, b in zip(str_packet[::2], str_packet[1::2])))
                    f.write('\n')

        return self.packets
