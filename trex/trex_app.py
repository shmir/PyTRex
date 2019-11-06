"""
Classes and utilities that represents TRex GUI application.

:author: yoram@ignissoft.com
"""

import getpass

from trafficgenerator.tgn_app import TgnApp
from trafficgenerator.tgn_utils import ApiType
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

    def connect(self, ip, port=4501, async_port=4500, virtual=False):
        """ Connect to TRex server.

        :param ip: TRex server IP
        :param port: RPC port
        :param async_port: Async port
        :virtual: ???
        """

        self.connection_info = {'username': self.username,
                                'server': ip,
                                'sync_port': port,
                                'async_port': async_port,
                                'virtual': virtual}

        # async event handler manager
        self.event_handler = EventsHandler(self)
        self.conn = Connection(self.connection_info, self.logger, self)
        self.conn.connect()

    def disconnect(self):
        self.conn.disconnect()

    def _get_api_h(self):
        return self.conn.get_api_h()
        self.event_handler = EventsHandler(self)

    # transmit request on the RPC link
    def _transmit(self, method_name, params=None, api_class='core'):
        return self.conn.rpc.transmit(method_name, params, api_class)

    # transmit batch request on the RPC link
    def _transmit_batch(self, batch_list):
        return self.conn.rpc.transmit_batch(batch_list)
