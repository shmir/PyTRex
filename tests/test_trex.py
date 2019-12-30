
import os
import sys
import pytest
import logging
import json

from scapy.layers.l2 import Ether
from scapy.layers.inet import IP

from pytrex.trex_app import TrexApp
from pytrex.trex_port import PortState
from pytrex.trex_stream import TrexRateType, TrexTxType
from pytrex.trex_statistics_view import TrexPortStatistics, TrexStreamStatistics
from pytrex.trex_stl_packet_builder_scapy import STLPktBuilder


@pytest.fixture(scope='module')
def logger():
    logger = logging.getLogger('trex')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))
    yield logger


@pytest.fixture(scope='module')
def trex(pytestconfig, logger):
    trex = TrexApp(logger)
    trex.connect(pytestconfig.getoption('chassis'))
    yield trex
    trex.disconnect()


@pytest.fixture(scope='module')
def ports(pytestconfig):
    yield pytestconfig.getoption('ports')


class TestOffline:

    def test_hello_world(self, trex):
        pass

    def test_inventory(self, trex):
        sys_info = trex.server.get_system_info()
        supported_cmds = trex.server.get_supported_cmds()
        print(f'server: {sys_info["core_type"]}')
        for port in sys_info['ports']:
            print(f'\tport: {port["description"]}')
        print(f'commands: {supported_cmds}')

    def test_reserve_ports(self, trex, ports):
        trex_ports = trex.server.reserve_ports(ports, force=True)
        assert len(trex_ports) == 2

    def test_load_streams(self, trex, ports):
        trex_port = list(trex.server.reserve_ports(ports, force=True).values())[0]
        trex_port.remove_all_streams()
        assert trex_port.get_port_state() == PortState.Idle
        trex_port.load_streams(os.path.dirname(__file__) + '/profiles/test_profile_1.yaml')
        trex_port.write_streams()
        assert trex_port.get_port_state() == PortState.Streams

    def test_traffic(self, trex, ports):
        trex_ports = trex.server.reserve_ports(ports, force=True)
        tx_port = list(trex_ports.values())[0]
        rx_port = list(trex_ports.values())[1]
        tx_port.remove_all_streams()
        tx_port.load_streams(os.path.dirname(__file__) + '/profiles/test_profile_1.yaml')
        tx_port.write_streams()

        tx_port.clear_stats()
        rx_port.clear_stats()
        tx_port_stats = tx_port.read_stats()
        rx_port_stats = rx_port.read_stats()
        print(json.dumps(tx_port_stats, indent=2))
        print(json.dumps(rx_port_stats, indent=2))
        assert tx_port_stats['opackets'] == 0
        assert rx_port_stats['ipackets'] == 0

        trex.server.start_transmit(True, tx_port)
        tx_port_stats = tx_port.read_stats()
        rx_port_stats = rx_port.read_stats()
        print(json.dumps(tx_port_stats, indent=2))
        print(json.dumps(rx_port_stats, indent=2))
        assert tx_port_stats['opackets'] == 300
        assert rx_port_stats['ipackets'] == 300

    def test_bidir_traffic(self, trex, ports):
        trex_ports = trex.server.reserve_ports(ports, force=True)
        port_0 = list(trex_ports.values())[0]
        port_1 = list(trex_ports.values())[1]
        port_0.remove_all_streams()
        port_0.load_streams(os.path.dirname(__file__) + '/profiles/test_profile_1.yaml')
        port_0.write_streams()
        port_1.remove_all_streams()
        port_1.load_streams(os.path.dirname(__file__) + '/profiles/test_profile_2.yaml')
        port_1.write_streams()

        trex.server.clear_stats()
        trex.server.start_transmit(True)
        port_0_stats = port_0.read_stats()
        port_1_stats = port_1.read_stats()
        print(json.dumps(port_0_stats, indent=2))
        print(json.dumps(port_1_stats, indent=2))
        assert port_0_stats['ipackets'] == 300
        assert port_1_stats['ipackets'] == 300

        port_stats_view = TrexPortStatistics(trex.server)
        port_stats_view.read()
        print(port_stats_view.statistics.dumps(indent=2))

    def test_streams(self, trex, ports):
        trex_ports = trex.server.reserve_ports(ports, force=True)
        port_0 = list(trex_ports.values())[0]
        port_1 = list(trex_ports.values())[1]
        port_0.remove_all_streams()
        port_0.load_streams(os.path.dirname(__file__) + '/profiles/test_profile_1.yaml')
        port_0.write_streams()
        port_1.remove_all_streams()
        port_1.load_streams(os.path.dirname(__file__) + '/profiles/test_profile_2.yaml')
        port_1.write_streams()
        stream_0 = list(trex.server.ports[0].streams.values())[0]

        stream_stats_view = TrexStreamStatistics(trex.server)
        stream_stats_view.read()
        print(stream_stats_view.statistics.dumps(indent=2))
        assert stream_stats_view.statistics[stream_0]['tx']['tb'] == 0
        assert not stream_stats_view.statistics[stream_0]['rx']

        trex.server.clear_stats()
        trex.server.start_transmit(True)
        stream_stats_view.read()
        print(stream_stats_view.statistics.dumps(indent=2))
        assert stream_stats_view.statistics[stream_0]['tx']['tp'] == 100
        assert stream_stats_view.statistics[stream_0]['rx'][port_1]['rp'] == 100

        trex.server.clear_stats()
        trex.server.start_transmit(True)
        stream_stats_view.read()
        assert stream_stats_view.statistics[stream_0]['tx']['tp'] == 100
        assert stream_stats_view.statistics[stream_0]['rx'][port_1]['rp'] == 100

        # Add stream and re-write.
        port_0.add_stream('name_stream')
        port_0.write_streams()

    def test_packets(self, trex, ports):
        trex_ports = trex.server.reserve_ports(ports, force=True, reset=True)
        tx_port = list(trex_ports.values())[0]
        rx_port = list(trex_ports.values())[1]
        stream_0 = tx_port.add_stream('s1')
        stream_1 = tx_port.add_stream('s2')

        stream_0.set_rate(TrexRateType.pps, 50)
        stream_0.set_tx_type(TrexTxType.single_burst, packets=100)
        stream_0.set_next('s2')
        packet = STLPktBuilder(pkt=Ether(src='11:11:11:11:11:11') / IP(src='10.10.10.10'))
        stream_0.set_packet(packet)

        stream_1.set_rate(TrexRateType.pps, 50)
        stream_1.set_tx_type(TrexTxType.multi_burst, packets=200, ibg=0.0, count=1)
        packet = STLPktBuilder(pkt=Ether(src='22:22:22:22:22:22') / IP(src='20.20.20.20'))
        stream_1.set_packet(packet)

        tx_port.write_streams()
        trex.server.clear_stats()
        trex.server.start_capture()
        trex.server.start_transmit(True, tx_port)
        tx_port_stats = tx_port.read_stats()
        rx_port_stats = rx_port.read_stats()
        print(json.dumps(tx_port_stats, indent=2))
        print(json.dumps(rx_port_stats, indent=2))
        assert tx_port_stats['opackets'] == 300
        assert rx_port_stats['ipackets'] == 300
        packets = trex.server.stop_capture()
        assert len(packets[rx_port]) == 300
        assert len(rx_port.capture.packets) == 300
        print(rx_port.capture.packets[0])
        assert rx_port.capture.packets[0]['scapy'].src in ['11:11:11:11:11:11', '22:22:22:22:22:22']
        assert rx_port.capture.packets[0]['scapy'].payload.src in ['10.10.10.10', '20.20.20.20']
