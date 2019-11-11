
import os
import base64
import json
import yaml

from scapy.layers.inet import IP
from scapy.layers.l2 import Dot3, Ether

from .trex_stl_exceptions import STLArgumentError, STLError
from .trex_stl_packet_builder_scapy import STLPktBuilder
from .text_opts import format_num
from .trex_object import TrexObject


# base class for TX mode
class STLTXMode:
    """ mode rate speed """

    def __init__(self, pps=None, bps_L1=None, bps_L2=None, percentage=None):
        """
        Speed can be given in packets per second(pps), L2/L1 bps, or port percent
        Use only one unit.
        you can enter pps =10000 oe bps_L1=10

        :parameters:
            pps : float
               Packets per second

            bps_L1 : float
               Bits per second L1(with IPG)

            bps_L2 : float
               Bits per second L2(Ethernet-FCS)

            percentage : float
               Link interface percent(0-100). Example: 10 is 10% of the port link setup

        .. code-block:: python

            # STLTXMode Example

            mode = STLTXCont(pps = 10)

            mode = STLTXCont(bps_L1 = 10000000) #10mbps L1

            mode = STLTXCont(bps_L2 = 10000000) #10mbps L2

            mode = STLTXCont(percentage = 10)   #10%

        """

        args = [pps, bps_L1, bps_L2, percentage]

        # default
        if all([x is None for x in args]):
            pps = 1.0
        else:
            if len([x for x in args if x is not None]) > 1:
                raise STLError(f'exactly one parameter from {args} should be provided')

        self.fields = {'rate': {}}

        if pps is not None:
            self.fields['rate']['type'] = 'pps'
            self.fields['rate']['value'] = pps

        elif bps_L1 is not None:
            self.fields['rate']['type'] = 'bps_L1'
            self.fields['rate']['value'] = bps_L1

        elif bps_L2 is not None:
            self.fields['rate']['type'] = 'bps_L2'
            self.fields['rate']['value'] = bps_L2

        elif percentage is not None:
            if not(percentage > 0 and percentage <= 100):
                raise STLArgumentError('percentage', percentage)

            self.fields['rate']['type'] = 'percentage'
            self.fields['rate']['value'] = percentage

    def to_json(self):
        return self.fields


# continuous mode
class STLTXCont(STLTXMode):
    """ Continuous mode """

    def __init__(self, **kwargs):
        """
        Continuous mode

         see :class:`trex_stl_lib.trex_stl_streams.STLTXMode` for rate

        .. code-block:: python

            # STLTXCont Example

            mode = STLTXCont(pps = 10)

        """
        super(STLTXCont, self).__init__(**kwargs)

        self.fields['type'] = 'continuous'

    @staticmethod
    def __str__():
        return "Continuous"

# single burst mode


class STLTXSingleBurst(STLTXMode):
    """ Single burst mode """

    def __init__(self, total_pkts=1, **kwargs):
        """
        Single burst mode

            :parameters:
                 total_pkts : int
                    Number of packets for this burst

         see :class:`trex_stl_lib.trex_stl_streams.STLTXMode` for rate

        .. code-block:: python

            # STLTXSingleBurst Example

            mode = STLTXSingleBurst( pps = 10, total_pkts = 1)

        """

        if not isinstance(total_pkts, int):
            raise STLArgumentError('total_pkts', total_pkts)

        super(STLTXSingleBurst, self).__init__(**kwargs)

        self.fields['type'] = 'single_burst'
        self.fields['total_pkts'] = total_pkts

    @staticmethod
    def __str__():
        return "Single Burst"

# multi burst mode


class STLTXMultiBurst(STLTXMode):
    """ Multi-burst mode """

    def __init__(self,
                 pkts_per_burst=1,
                 ibg=0.0,   # usec not SEC
                 count=1,
                 **kwargs):
        """
        Multi-burst mode

        :parameters:

             pkts_per_burst: int
                Number of packets per burst

              ibg : float
                Inter-burst gap in usec 1,000,000.0 is 1 sec

              count : int
                Number of bursts

         see :class:`trex_stl_lib.trex_stl_streams.STLTXMode` for rate

        .. code-block:: python

            # STLTXMultiBurst Example

            mode = STLTXMultiBurst(pps = 10, pkts_per_burst = 1,count 10, ibg=10.0)

        """

        if not isinstance(pkts_per_burst, int):
            raise STLArgumentError('pkts_per_burst', pkts_per_burst)

        if not isinstance(ibg, (int, float)):
            raise STLArgumentError('ibg', ibg)

        if not isinstance(count, int):
            raise STLArgumentError('count', count)

        super(STLTXMultiBurst, self).__init__(**kwargs)

        self.fields['type'] = 'multi_burst'
        self.fields['pkts_per_burst'] = pkts_per_burst
        self.fields['ibg'] = ibg
        self.fields['count'] = count

    @staticmethod
    def __str__():
        return "Multi Burst"


STLStreamDstMAC_CFG_FILE = 0
STLStreamDstMAC_PKT = 1
STLStreamDstMAC_ARP = 2


class STLFlowStatsInterface(object):
    def __init__(self, pg_id):
        self.fields = {}
        self.fields['enabled'] = True
        self.fields['stream_id'] = pg_id

    def to_json(self):
        """ Dump as json"""
        return dict(self.fields)

    @staticmethod
    def defaults():
        return {'enabled': False}


class STLFlowStats(STLFlowStatsInterface):
    """ Define per stream basic stats

    .. code-block:: python

        # STLFlowStats Example

        flow_stats = STLFlowStats(pg_id = 7)

    """

    def __init__(self, pg_id):
        super(STLFlowStats, self).__init__(pg_id)
        self.fields['rule_type'] = 'stats'


class STLFlowLatencyStats(STLFlowStatsInterface):
    """ Define per stream basic stats + latency, jitter, packet reorder/loss

    .. code-block:: python

        # STLFlowLatencyStats Example

        flow_stats = STLFlowLatencyStats(pg_id = 7)

    """

    def __init__(self, pg_id):
        super(STLFlowLatencyStats, self).__init__(pg_id)
        self.fields['rule_type'] = 'latency'


class TrexStream(TrexObject):
    """ One stream object. Includes mode, Field Engine mode packet template and Rx stats

        .. code-block:: python

            # STLStream Example


            base_pkt =  Ether()/IP(src="16.0.0.1",dst="48.0.0.1")/UDP(dport=12,sport=1025)
            pad = max(0, size - len(base_pkt)) * 'x'

            STLStream( isg = 10.0, # star in delay
                       name    ='S0',
                       packet = STLPktBuilder(pkt = base_pkt/pad),
                       mode = STLTXSingleBurst( pps = 10, total_pkts = 1),
                       next = 'S1'), # point to next stream


    """

    def __init__(self, parent, index, name):
        """ Create stream object.

        :param parent: parent port
        :param index: stream index under port, zero based
        :param name: stream name
        """
        super().__init__(objType='stream', objRef=f'{parent.ref}/{index}', parent=parent, name=name)

    def config(self,
               packet=None,
               mode=STLTXCont(pps=1),
               enabled=True,
               self_start=True,
               isg=0.0,
               flow_stats=None,
               next=None,
               stream_id=None,
               action_count=0,
               random_seed=0,
               mac_src_override_by_pkt=None,
               mac_dst_override_mode=None,  # see  STLStreamDstMAC_xx
               dummy_stream=False):
        """
        Stream object

        :parameters:

                  packet :  STLPktBuilder see :class:
                  `trex_stl_lib.trex_stl_packet_builder_scapy.STLPktBuilder`
                       Template packet and field engine program. Example:
                       packet = STLPktBuilder(pkt = base_pkt/pad)

                  mode :  :class:`trex_stl_lib.trex_stl_streams.STLTXCont` or :
                  class:`trex_stl_lib.trex_stl_streams.STLTXSingleBurst`  or  :
                      class:`trex_stl_lib.trex_stl_streams.STLTXMultiBurst`

                  enabled : bool
                      Indicates whether the stream is enabled.

                  self_start : bool
                      If False, another stream activates it.

                  isg : float
                     Inter-stream gap in usec. Time to wait until the stream
                     sends the first packet.

                  flow_stats : :class:`trex_stl_lib.trex_stl_streams.STLFlowStats`
                      Per stream statistic object. See: STLFlowStats

                  next : string
                      Name of the stream to activate.

                  stream_id :
                        For use by HLTAPI.

                  action_count : uint16_t
                        If there is a next stream, number of loops before stopping.
                        Default: 0(unlimited).

                  random_seed: uint16_t
                       If given, the seed for this stream will be this value.
                       Useful if you need a deterministic random value.

                  mac_src_override_by_pkt : bool
                        Template packet sets src MAC.

                  mac_dst_override_mode=None : STLStreamDstMAC_xx
                        Template packet sets dst MAC.

                  dummy_stream : bool
                        For delay purposes, will not be sent.
        """

        if(type(mode) == STLTXCont) and(next is not None):
            raise STLError("Continuous stream cannot have a next stream ID")

        # tag for the stream and next - can be anything
        self.next = next

        # save for easy construct code from stream object
        self.mac_src_override_by_pkt = mac_src_override_by_pkt
        self.mac_dst_override_mode = mac_dst_override_mode
        self.id = stream_id

        self.fields = {}

        int_mac_src_override_by_pkt = 0
        int_mac_dst_override_mode = 0

        if mac_src_override_by_pkt is None:
            int_mac_src_override_by_pkt = 0
            if packet:
                if packet.is_default_src_mac() is False:
                    int_mac_src_override_by_pkt = 1

        else:
            int_mac_src_override_by_pkt = int(mac_src_override_by_pkt)

        if mac_dst_override_mode is None:
            int_mac_dst_override_mode = 0
            if packet:
                if packet.is_default_dst_mac() is False:
                    int_mac_dst_override_mode = STLStreamDstMAC_PKT
        else:
            int_mac_dst_override_mode = int(mac_dst_override_mode)

        self.is_default_mac = not(
            int_mac_src_override_by_pkt or int_mac_dst_override_mode)

        self.fields['flags'] = (int_mac_src_override_by_pkt & 1) + \
            ((int_mac_dst_override_mode & 3) << 1) + (int(dummy_stream) << 3)

        self.fields['action_count'] = action_count

        # basic fields
        self.fields['enabled'] = enabled
        self.fields['self_start'] = self_start
        self.fields['isg'] = isg

        if random_seed != 0:
            self.fields['random_seed'] = random_seed  # optional

        # mode
        self.fields['mode'] = mode.to_json()
        self.mode_desc = str(mode)

        # packet
        self.fields['packet'] = {}
        self.fields['vm'] = {}

        if not packet:
            packet = STLPktBuilder(pkt=Ether()/IP())
            if dummy_stream:
                self.packet_desc = 'Dummy'

        self.scapy_pkt_builder = packet
        # packet builder
        packet.compile()

        # packet and VM
        self.fields['packet'] = packet.dump_pkt()
        self.fields['vm'] = packet.get_vm_data()

        self.pkt = base64.b64decode(self.fields['packet']['binary'])

        # this is heavy, calculate lazy
        self.packet_desc = None

        if not flow_stats:
            self.fields['flow_stats'] = STLFlowStats.defaults()
        else:
            self.fields['flow_stats'] = flow_stats.to_json()

    def __repr__(self):
        s = "Stream Name: {0}\n".format(self.name)
        s += "Stream Next: {0}\n".format(self.next)
        s += "Stream JSON:\n{0}\n".format(json.dumps(
            self.fields, indent=4, separators=(',', ': '), sort_keys=True))
        return s

    def to_json(self):
        """
        Return json format
        """
        return dict(self.fields)

    def has_custom_mac_addr(self):
        """ Return True if src or dst MAC were set as custom """
        return not self.is_default_mac

    def has_flow_stats(self):
        """ Return True if stream was configured with flow stats """
        return self.fields['flow_stats']['enabled']

    def get_pkt_len(self, count_crc=True):
        """ Get packet number of bytes  """
        pkt_len = len(self.get_pkt())
        if count_crc:
            pkt_len += 4

        return pkt_len

    def get_pkt_type(self):
        """ Get packet description. Example: IP:UDP """
        if self.packet_desc is None:
            self.packet_desc = STLPktBuilder.pkt_layers_desc_from_buffer(
                self.get_pkt())

        return self.packet_desc

    @staticmethod
    def get_rate_from_field(rate_json):
        """ Get rate from json  """
        t = rate_json['type']
        v = rate_json['value']

        if t == "pps":
            return format_num(v, suffix="pps")
        elif t == "bps_L1":
            return format_num(v, suffix="bps(L1)")
        elif t == "bps_L2":
            return format_num(v, suffix="bps(L2)")
        elif t == "percentage":
            return format_num(v, suffix="%")

    def get_rate(self):
        return self.get_rate_from_field(self.fields['mode']['rate'])

    def to_pkt_dump(self):
        """ Print packet description from Scapy  """
        if self.name:
            print(("Stream Name: ", self.name))
        scapy_b = self.scapy_pkt_builder
        if scapy_b and isinstance(scapy_b, STLPktBuilder):
            dump = scapy_b.to_pkt_dump()
        else:
            print("Nothing to dump")
        return dump


class TrexYamlLoader:

    def __init__(self, port, yaml_file):
        self.port = port
        self.yaml_path = os.path.dirname(yaml_file)
        self.yaml_file = yaml_file

    def __parse_packet(self, packet_dict):

        packet_type = set(packet_dict).intersection(['binary', 'pcap'])
        if len(packet_type) != 1:
            raise STLError(
                "Packet section must contain either 'binary' or 'pcap'")

        if 'binary' in packet_type:
            try:
                pkt_str = base64.b64decode(packet_dict['binary'])
            except TypeError:
                raise STLError("'binary' field is not a valid packet format")

            builder = STLPktBuilder(pkt_buffer=pkt_str)

        elif 'pcap' in packet_type:
            pcap = os.path.join(self.yaml_path, packet_dict['pcap'])

            if not os.path.exists(pcap):
                raise STLError("'pcap' - cannot find '{0}'".format(pcap))

            builder = STLPktBuilder(pkt=pcap)

        return builder

    def __parse_mode(self, mode_obj):
        if not mode_obj:
            return None

        rate_type = mode_obj.get('rate').get('type')
        rate_value = mode_obj.get('rate').get('value')
        if rate_type not in ['pps', 'bps_L1', 'bps_L2', 'percentage']:
            raise STLError("'rate' must contain exactly one from 'pps', 'bps_L1', 'bps_L2', 'percentage'")

        rate = {rate_type: rate_value}

        mode_type = mode_obj.get('type')

        if mode_type == 'continuous':
            mode = STLTXCont(**rate)

        elif mode_type == 'single_burst':
            defaults = STLTXSingleBurst()
            mode = STLTXSingleBurst(total_pkts=mode_obj.get('total_pkts',defaults.fields['total_pkts']), **rate)

        elif mode_type == 'multi_burst':
            defaults = STLTXMultiBurst()
            mode = STLTXMultiBurst(pkts_per_burst=mode_obj.get('pkts_per_burst', defaults.fields['pkts_per_burst']),
                                   ibg=mode_obj.get('ibg', defaults.fields['ibg']),
                                   count=mode_obj.get('count', defaults.fields['count']),
                                   **rate)

        else:
            raise STLError(
                "mode type can be 'continuous', 'single_burst' or 'multi_burst")

        return mode

    def __parse_flow_stats(self, flow_stats_obj):

        # no such object
        if not flow_stats_obj or flow_stats_obj.get('enabled') is False:
            return None

        pg_id = flow_stats_obj.get('stream_id')
        if pg_id is None:
            raise STLError(
                "Enabled RX stats section must contain 'stream_id' field")

        return STLFlowStats(pg_id=pg_id)

    def __parse_stream(self, yaml_object):
        s_obj = yaml_object['stream']

        # parse packet
        packet = s_obj.get('packet')
        if not packet:
            raise STLError("YAML file must contain 'packet' field")

        builder = self.__parse_packet(packet)

        # mode
        mode = self.__parse_mode(s_obj.get('mode'))

        # rx stats
        flow_stats = self.__parse_flow_stats(s_obj.get('flow_stats'))

        # create the stream
        stream = self.port.add_stream(name=yaml_object.get('name'))
        stream.config(packet=builder,
                      mode=mode,
                      flow_stats=flow_stats,
                      enabled=s_obj.get('enabled', True),
                      self_start=s_obj.get('self_start', True),
                      isg=s_obj.get('isg', 0.0),
                      next=yaml_object.get('next'),
                      action_count=s_obj.get('action_count', 0),
                      mac_src_override_by_pkt=s_obj.get('mac_src_override_by_pkt', 0),
                      mac_dst_override_mode=s_obj.get('mac_src_override_by_pkt', 0))

        # hack the VM fields for now
        if 'vm' in s_obj:
            stream.fields['vm'].update(s_obj['vm'])

        return stream

    def parse(self):
        with open(self.yaml_file, 'r') as f:
            # read YAML and pass it down to stream object
            yaml_str = f.read()

            try:
                objects = yaml.safe_load(yaml_str)
            except yaml.parser.ParserError as e:
                raise STLError(str(e))

            streams = [self.__parse_stream(object) for object in objects]

            return streams
