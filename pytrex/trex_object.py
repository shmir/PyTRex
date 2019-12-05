"""
Base classes and utilities for all Xena Manager (Xena) objects.

:author: yoram@ignissoft.com
"""

from trafficgenerator.tgn_object import TgnObject, TgnObjectsDict


class TrexObject(TgnObject):
    """ Base class for all Trex objects. """

    def __init__(self, **data):
        """ Create TRex object. """
        if data['parent']:
            self.username = data['parent'].username
            self.session_id = data['parent'].session_id
            self.server = data['parent'].server
            if data['parent']._data.get('index'):
                data['objRef'] = f'{data["objType"]}/{data["parent"].index}/{data["index"]}'
            else:
                data['objRef'] = f'{data["objType"]}/{data["index"]}'
        super().__init__(**data)
