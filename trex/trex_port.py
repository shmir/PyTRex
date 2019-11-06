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
        :param index: port index in format module/port (both 0 based)
        """

        super().__init__(objType='port', objRef=index, parent=parent)
