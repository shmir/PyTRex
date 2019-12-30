"""
Base classes and utilities for all Xena Manager (Xena) objects.

:author: yoram@ignissoft.com
"""

from trafficgenerator.tgn_object import TgnObject

from .api.trex_stl_types import RC


class TrexObject(TgnObject):
    """ Base class for all Trex objects. """

    def __init__(self, **data):
        """ Create TRex object. """
        if data['parent']:
            self.username = data['parent'].username
            self.session_id = data['parent'].session_id
            self.server = data['parent'].server
            if data['parent']._data.get('index') is not None:
                data['objRef'] = f'{data["objType"]}/{data["parent"].index}'
                if 'index' in data:
                    data['objRef'] += f'{data["index"]}'
            else:
                data['objRef'] = f'{data["objType"]}/{data["index"]}'
        super().__init__(**data)

    def transmit(self, method_name, params=None, api_class='core') -> RC:
        return self.api.rpc.transmit(method_name, params, api_class)

    def transmit_batch(self, batch_list):
        return self.api.rpc.transmit_batch(batch_list)
