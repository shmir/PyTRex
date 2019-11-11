"""
Classes and utilities that represents TRex port.

:author: yoram@ignissoft.com
"""


from .trex_object import TrexObject
from .trex_stream import TrexStream, TrexYamlLoader
from .api.trex_stl_types import RpcCmdData


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
        params = {"port_id": int(self.ref),
                  "handler": self.handler}
        self.api.rpc.transmit("release", params)

    def remove_all_streams(self):
        params = {"port_id": int(self.ref),
                  "handler": self.handler}
        self.api.rpc.transmit('remove_all_streams', params)

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
