# import stl_path

from scapy.layers.inet import IP, UDP
from scapy.layers.l2 import Ether

from trex_stl_lib.trex_stl_packet_builder_scapy import STLPktBuilder
from trex_stl_lib import STLStream, STLTXCont


class STLS1(object):

    def create_stream(self):

        return STLStream(
            packet=STLPktBuilder(
                        pkt=Ether()/IP(src="16.0.0.1",
                                       dst="48.0.0.1")/UDP(dport=12,
                                                           sport=1025)/(10*'x')), mode=STLTXCont())

    def get_streams(self, direction=0, **kwargs):
        # create 1 stream
        return [self.create_stream()]


# dynamic load - used for TRex console or simulator
def register():
    return STLS1()
