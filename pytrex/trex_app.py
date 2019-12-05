"""
Classes and utilities that represents TRex GUI application.

:author: yoram@ignissoft.com
"""

import random
import getpass
import time

from trafficgenerator.tgn_app import TgnApp
from trafficgenerator.tgn_utils import ApiType
from .trex_object import TrexObject
from .trex_port import TrexPort
from .api.trex_stl_conn import Connection
from .api.trex_event import EventsHandler


def run_trex(ip, user, password, path):
    raise NotImplementedError


class TrexApp(TgnApp):
    """ TrexApp object, equivalent to TRex application. """

    def __init__(self, logger, username=getpass.getuser()):
        """ Start TRex application.

        :param logger: python logger
        :param username: user name
        """
        super(self.__class__, self).__init__(logger, ApiType.socket)
        self.username = username
        self.server = None

    def connect(self, ip, port=4501, async_port=4500, virtual=False):
        """ Connect to TRex server.

        :param ip: TRex server IP
        :param port: RPC port
        :param async_port: Async port
        :virtual: ???
        """

        self.server = TrexServer(self.logger, self.username, ip, port, async_port, virtual)
        self.server.connect()
        return self.server

    def disconnect(self):
        if self.server:
            self.server.disconnect()


class TrexServer(TrexObject):
    """ Represents single TRex server. """

    def __init__(self, logger, username, ip, port=4501, async_port=4500, virtual=False):
        """
        :param logger: python logger
        :param username: user name
        :param ip: TRex server IP
        :param port: RPC port
        :param async_port: Async port
        :param virtual: ???
        """

        self.logger = logger
        self.username = username
        self.ip = ip
        self.port = port
        self.async_port = async_port
        self.virtual = virtual

        super(self.__class__, self).__init__(objType='server', index='', parent=None, objRef=None)

    def connect(self):
        """ Connect to the TRex server. """

        self.event_handler = EventsHandler(self)
        self.connection_info = {'username': self.username,
                                'server': self.ip,
                                'sync_port': self.port,
                                'async_port': self.async_port,
                                'virtual': self.virtual}
        self.api = Connection(self.connection_info, self.logger, self)
        self.api.connect()
        self.session_id = random.getrandbits(32)

    def disconnect(self):
        for port in self.ports.values():
            port.release()
        self.api.disconnect()

    def reserve_ports(self, locations, force=False, reset=True):
        """ Reserve ports and reset factory defaults.

        TRex -> Port -> Acquire.

        :param locations: list of ports locations in the form <port number> to reserve
        :param force: True - take forcefully. False - fail if port is reserved by other user
        :param reset: True - reset port, False - leave port configuration
        :return: ports dictionary (index: object)
        """
        return_dict = {}
        for location in locations:
            TrexPort(parent=self, index=location).reserve(force)
            return_dict[location] = self.ports[location]
        return return_dict

    def get_system_info(self):
        return self.api.rpc.transmit('get_system_info', {}).rc_list[0].data

    def get_supported_cmds(self):
        return self.api.rpc.transmit('get_supported_cmds', {}).rc_list[0].data

    def clear_stats(self, *ports):
        ports = ports if ports else list(self.ports.values())
        for port in ports:
            port.clear_stats()

    def start_transmit(self, blocking=False, *ports):
        """ Start traffic on list of ports.

        If possible, synchroniz start of traffic, else, strat .

        :param blocking: True - wait for traffic end, False - return after traffic start.
        :param ports: list of ports to start traffic on, if empty start on all ports.
        """

        ports = ports if ports else list(self.ports.values())

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
            start_at_ts = rc.data()['ts'] + max((time.time() - start_time), 0.5) * len(ports)
            self.logger.level = save_level
        else:
            start_at_ts = 0

        for port in ports:
            port.start_at_ts = start_at_ts
            port.start_transmit(blocking=False)

        if blocking:
            self.wait_transmit(*ports)

    def wait_transmit(self, *ports):
        ports = ports if ports else ports.keys()
        for port in ports:
            port.wait_transmit()

    def stop_transmit(self, *ports):
        ports = ports if ports else self.ports
        for port in ports:
            port.stop_transmit()

    @property
    def ports(self):
        """
        :return: dictionary {index: object} of all ports.
        """
        return {int(p.ref): p for p in self.get_objects_by_type('port')}

    def _get_api_h(self):
        return self.api.get_api_h()

    # transmit request on the RPC link
    def _transmit(self, method_name, params=None, api_class='core'):
        return self.api.rpc.transmit(method_name, params, api_class)

    # transmit batch request on the RPC link
    def _transmit_batch(self, batch_list):
        return self.api.rpc.transmit_batch(batch_list)
