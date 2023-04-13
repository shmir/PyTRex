"""
Base classes and utilities for all TRex objects.
"""
from typing import Dict, List, Type, Union

from trafficgenerator.tgn_object import TgnObject


class TrexObject(TgnObject):
    """Base class for all Trex objects."""

    def __init__(self, parent: Union["TrexObject", None], **data: str):
        """Create TRex object."""
        if parent:
            self.username = parent.username
            self.session_id = parent.session_id
            self.server = parent.server
            data["objRef"] = f"{parent.ref}/{data['objType']}"
            if "index" in data:
                data["objRef"] += data["index"]
        super().__init__(parent, **data)

    def transmit(self, method_name: str, params: dict = None) -> dict:
        """Transmit object command.

        :param method_name: RPC command.
        :param params: command parameters.
        """
        return self.api.rpc.transmit(method_name, params, "core")

    def transmit_batch(self, batch_list):
        return self.api.rpc.transmit_batch(batch_list)

    def get_name(self) -> str:
        pass

    def get_attributes(self) -> Dict[str, str]:
        pass

    def get_attribute(self, attribute: str) -> str:
        pass

    def get_children(self, *types: str) -> List[TgnObject]:
        pass

    def get_objects_from_attribute(self, attribute: str) -> List[TgnObject]:
        pass

    def get_obj_class(self, obj_type: str) -> Type[TgnObject]:
        pass

    def _create(self, **attributes: Dict[str, object]) -> str:
        pass
