"""
Classes and utilities that represents TRex port.

:author: yoram@ignissoft.com
"""


from .trex_object import TrexObject


class TrexPort(TrexObject):
    """ Represents TRex port. """

    def __init__(self, parent, index):
        """ Create port object.

        :param parent: parent module or chassis.
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
