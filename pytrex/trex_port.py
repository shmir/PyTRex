"""
Classes and utilities that represents TRex port.

:author: yoram@ignissoft.com
"""

import re
import time
from enum import Enum
from copy import deepcopy
from typing import Optional

from .trex_object import TrexObject
from .trex_stream import TrexStream, TrexYamlLoader
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
        super().__init__(objType='port', parent=parent, index=index)
        self.mul = decode_multiplier('1', allow_update=False, divide_count=1)
        self.duration = -1
        self.force = False
        self.mask = MASK_ALL
        self.start_at_ts = 0.0
        self.statistics = None
        self.xstatistics = None

    def reserve(self, force: Optional[bool] = False, reset: Optional[bool] = False) -> None:
        """ Reserve port.

        TRex -> Port -> [Force] Acquire.

        :param force: True - take forcefully, False - fail if port is reserved by other user
        :param reset: True - reset port, False - leave port configuration
        """

        params = {"port_id": int(self.index),
                  "user": self.username,
                  "session_id": self.session_id,
                  "force": force}
        rc = self.api.rpc.transmit("acquire", params)
        self.handler = rc.data()

        if reset:
            self.reset()

    def release(self):
        """ Release port.

        TRex -> Port -> Release Acquire.
        """
        self.transmit('release')

    def reset(self) -> None:
        self.remove_all_streams()

    #
    # Configuration.
    #

    def get_status(self):
        params = {"port_id": int(self.index),
                  "session_id": self.session_id}
        rc = self.api.rpc.transmit("get_port_status", params)
        return rc.data()

    def set_service_mode(self, enabled):
        params = {"port_id": int(self.index),
                  "session_id": self.session_id,
                  "enabled": enabled}
        self.transmit("service", params)

    #
    # Streams.
    #

    def remove_all_streams(self) -> None:
        self.del_objects_by_type('stream')
        self.transmit('remove_all_streams')

    def add_stream(self, name: str) -> TrexStream:
        """ Add stream with default configuration.

        :param name: unique stream name
        """
        return TrexStream(self, index=len(self.streams), name=name)

    def load_streams(self, yaml_file) -> None:
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

    def write_streams(self) -> None:
        """ Write all streams to server. """

        self.transmit('remove_all_streams')
        batch = []
        for name, stream in self.streams.items():
            stream_fields = deepcopy(stream.fields)
            stream_id = list(self.streams.keys()).index(name) + 1
            next_stream = stream_fields.pop('next_stream')
            stream_fields['next_stream_id'] = list(self.streams.keys()).index(next_stream) + 1 if next_stream else -1

            params = {"handler": self.handler,
                      "port_id": int(self.id),
                      "stream_id": stream_id,
                      "stream": stream_fields}
            cmd = RpcCmdData('add_stream', params, 'core')
            batch.append(cmd)

        self.api.rpc.transmit_batch(batch)

    #
    # Control.
    #

    def get_port_state(self):
        rc = self.transmit('get_port_status')
        return PortState(rc.data()['state'].lower())

    def is_transmitting(self):
        return self.get_port_state() in [PortState.Tx, PortState.Pcap_Tx]

    def start_transmit(self, blocking=False):

        if self.get_port_state() == PortState.Idle:
            raise Exception('unable to start traffic - no streams attached to port')

        params = {"mul": self.mul,
                  "duration": self.duration,
                  "force": self.force,
                  "core_mask": self.mask,
                  'start_at_ts': self.start_at_ts}
        self.transmit("start_traffic", params)

        if blocking:
            self.wait_transmit()

    def stop_transmit(self):
        self.transmit('stop_traffic')
        self.wait_transmit()

    def wait_transmit(self):
        while self.is_transmitting():
            time.sleep(1)

    def start_capture(self):
        self.set_service_mode(True)
        raise NotImplementedError()

    def stop_capture(self):
        raise NotImplementedError()

    #
    # Statistics.

    def clear_stats(self):
        values = self.transmit('get_port_xstats_values').data()
        self.stat_names = self.transmit('get_port_xstats_names').data()
        self.base_xstats = dict(zip(self.stat_names['xstats_names'], values['xstats_values']))
        self.base_stats = self.transmit('get_port_stats').data()
        self.statistics = self.base_stats
        self.xstatistics = self.base_xstats

    def read_stats(self):
        self.statistics = self.transmit('get_port_stats').data()
        for stat, value in self.statistics.items():
            if not stat.endswith('ps'):
                value -= self.base_stats[stat]
            self.statistics[stat] = value
        return self.statistics

    def read_xstats(self):
        values = self.transmit('get_port_xstats_values').data()
        self.xstatistics = dict(zip(self.stat_names['xstats_names'], values['xstats_values']))
        for stat, value in self.xstatistics.items():
            self.statistics[stat] = value - self.base_xstats[stat]
        return self.xstatistics

    #
    # Private.
    #

    def transmit(self, command, params={}):
        """ Transmit RPC command.

        :param command: RPC command
        :param params: command parameters
        """
        params['port_id'] = int(self.id)
        params['handler'] = self.handler
        return self.api.rpc.transmit(command, params)

    @property
    def streams(self):
        """
        :return: dictionary {name: object} of all streams.
        """
        return {s.name: s for s in self.get_objects_by_type('stream')}
