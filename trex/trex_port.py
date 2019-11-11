"""
Classes and utilities that represents TRex port.

:author: yoram@ignissoft.com
"""

import re
import time
from enum import Enum

from .trex_object import TrexObject
from .trex_stream import TrexStream, TrexYamlLoader
from .trex_statistics_view import CPortStats
from .api.trex_stl_types import RpcCmdData


MASK_ALL = ((1 << 64) - 1)


def decode_multiplier(val, allow_update=False, divide_count=1):

    factor_table = {None: 1, 'k': 1e3, 'm': 1e6, 'g': 1e9}
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
        result['type'] = 'raw'
        result['value'] = value

    # percentage
    elif unit == '%':
        result['type'] = 'percentage'
        result['value'] = value

    elif m_type == 'bps':
        result['type'] = 'bps'
        result['value'] = value * factor_table[factor]

    elif m_type == 'pps':
        result['type'] = 'pps'
        result['value'] = value * factor_table[factor]

    elif m_type == 'bpsl1':
        result['type'] = 'bpsl1'
        result['value'] = value * factor_table[factor]

    if op == "+":
        result['op'] = "add"
    elif op == "-":
        result['op'] = "sub"
    else:
        result['op'] = "abs"

    if result['op'] != 'percentage':
        result['value'] = result['value'] / divide_count

    return result


class PortState(Enum):
    Down = 'down'
    Idle = 'idle'
    Streams = 'streams'
    Tx = 'tx'
    Pause = 'pause'
    Pcap_Tx = 'pcap_tx'


class TrexPort(TrexObject):
    """ Represents TRex port. """

    def __init__(self, parent, index):
        """ Create port object.

        :param parent: parent chassis.
        :param index: port index, zero based
        """
        super().__init__(objType='port', objRef=index, parent=parent)

    def reserve(self, force=False):
        """ Reserve port.

        TRex -> Port -> [Force] Acquire.

        :param force: True - take forcefully, False - fail if port is reserved by other user
        """

        params = {"port_id": int(self.ref),
                  "user": self.username,
                  "session_id": self.session_id,
                  "force": force}
        rc = self.api.rpc.transmit("acquire", params)
        self.handler = rc.data()

    def release(self):
        """ Release port.

        TRex -> Port -> Release Acquire.
        """
        self.transmit('release')

    #
    # Streams.
    #

    def remove_all_streams(self):
        self.transmit('remove_all_streams')

    def add_stream(self, name):
        return TrexStream(self, index=len(self.streams), name=name)

    def load_streams(self, yaml_file):
        """ Load streams from YAML file.

        :param yaml_file: full path to yaml profile file.
        """
        yaml_loader = TrexYamlLoader(self, yaml_file)
        yaml_loader.parse()

    def save_streams(self, yaml_file):
        """ Save streams to YAML file.

        :param yaml_file: full path to yaml profile file.
        """
        raise NotImplementedError()

    def write_streams(self):
        """ Write all streams to server. """
        batch = []
        for name, stream in self.streams.items():
            stream_id = list(self.streams.keys()).index(name) + 1
            next_id = list(self.streams.keys()).index(stream.next) + 1 if stream.next else -1

            stream_json = stream.to_json()
            stream_json['next_stream_id'] = next_id

            params = {"handler": self.handler,
                      "port_id": int(self.ref),
                      "stream_id": stream_id,
                      "stream": stream_json}

            cmd = RpcCmdData('add_stream', params, 'core')
            batch.append(cmd)

        self.api.rpc.transmit_batch(batch)

    @property
    def streams(self):
        """
        :return: dictionary {name: object} of all streams.
        """
        return {str(s): s for s in self.get_objects_by_type('stream')}

    #
    # Control.
    #

    def get_port_state(self):
        rc = self.transmit('get_port_status')
        return PortState(rc.data()['state'].lower())

    def is_transmitting(self):
        return self.get_port_state() in [PortState.Tx, PortState.Pcap_Tx]

    def start_transmit(self, mul, duration, force, mask=MASK_ALL, start_at_ts=0):

        if self.get_port_state() == PortState.Idle:
            raise Exception('unable to start traffic - no streams attached to port')

        params = {"mul": mul,
                  "duration": duration,
                  "force": force,
                  "core_mask": mask,
                  'start_at_ts': start_at_ts}
        self.transmit("start_traffic", params)

    def stop_transmit(self):
        self.transmit('stop_traffic')
        self.wait_transmit()

    def wait_transmit(self):
        while self.is_transmitting():
            time.sleep(1)

    #
    # Statistics.
    #

    def clear_stats(self):
        values = self.transmit('get_port_xstats_values').data()
        names = self.transmit('get_port_xstats_names').data()
        self.base_stats = dict(zip(names['xstats_names'], values['xstats_values']))

    def get_stats(self):
        xvalues = self.transmit('get_port_xstats_values').data()
        values = self.transmit('get_port_stats').data()

    #
    # Private.
    #

    def transmit(self, command, params={}):
        """ Transmit RPC command.

        :param command: RPC command
        :param params: command parameters
        """
        params['port_id'] = int(self.ref)
        params['handler'] = self.handler
        return self.api.rpc.transmit(command, params)
