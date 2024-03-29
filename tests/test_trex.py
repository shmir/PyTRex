"""
pytrex tests.
"""
import json
import logging
import os
import time
from pathlib import Path

from scapy.layers.inet import IP
from scapy.layers.l2 import Ether

from pytrex.trex_app import TrexApp
from pytrex.trex_port import PortState
from pytrex.trex_statistics_view import TrexPortStatistics, TrexStreamStatistics
from pytrex.trex_stl_packet_builder_scapy import STLPktBuilder
from pytrex.trex_stream import TrexRateType, TrexTxType

logger = logging.getLogger("tgn.trex")


def test_inventory(trex: TrexApp) -> None:
    """Test inventory and commands."""
    sys_info = trex.server.get_system_info()
    supported_cmds = trex.server.get_supported_cmds()
    logger.info(f"server: {sys_info['core_type']}")
    for port in sys_info["ports"]:
        logger.info(f"\tport: {port['description']}")
    logger.info(f"commands: {supported_cmds}")


def test_reserve_ports(trex: TrexApp, ports: list[int]) -> None:
    """Test port reservation."""
    trex_ports = trex.server.reserve_ports(ports, force=True, reset=True)
    assert len(trex_ports) == 2


def test_load_streams(trex: TrexApp, ports: list[int]) -> None:
    """Test loading streams from GUI and stl-sim."""
    port_0, port_1 = trex.server.reserve_ports(ports, force=True).values()
    port_0.remove_all_streams()
    assert port_0.get_port_state() == PortState.IDLE
    port_0.load_streams(os.path.dirname(__file__) + "/profiles/udp_2pkt_simple.yaml")
    port_0.write_streams()
    assert port_0.get_port_state() == PortState.STREAMS
    port_1.load_streams(os.path.dirname(__file__) + "/profiles/udp_2pkt_simple_gui.yaml")
    port_1.write_streams()
    assert port_1.get_port_state() == PortState.STREAMS


def test_traffic(trex: TrexApp, ports: list[int]) -> None:
    """Test traffic and port statistics."""
    trex_ports = trex.server.reserve_ports(ports, force=True)
    port_0, port_1 = list(trex_ports.values())
    port_0.remove_all_streams()
    port_0.load_streams(os.path.dirname(__file__) + "/profiles/test_profile_0.yaml")
    port_0.write_streams()
    port_1.remove_all_streams()
    port_1.load_streams(os.path.dirname(__file__) + "/profiles/test_profile_1.yaml")
    port_1.write_streams()

    trex.server.clear_stats()
    trex.server.start_transmit(True)
    time.sleep(1)

    port_stats_view = TrexPortStatistics(trex.server)
    port_stats_view.read()
    logger.info(port_stats_view.statistics.dumps(indent=2))

    port_0_stats = port_0.read_stats()
    port_1_stats = port_1.read_stats()
    logger.info(json.dumps(port_0_stats, indent=2))
    logger.info(json.dumps(port_1_stats, indent=2))
    assert port_0_stats["opackets"] == 300
    assert port_1_stats["opackets"] == 300


def test_streams(trex: TrexApp, ports: list[int]) -> None:
    """Test stream statistics."""
    trex_ports = trex.server.reserve_ports(ports, force=True)
    port_0, port_1 = list(trex_ports.values())
    port_0.remove_all_streams()
    port_0.load_streams(Path(__file__).parent.joinpath("profiles/test_profile_0.yaml"))
    port_0.write_streams()
    port_1.remove_all_streams()
    port_1.load_streams(Path(__file__).parent.joinpath("profiles/test_profile_1.yaml"))
    port_1.write_streams()
    stream_0 = list(trex.server.ports[0].streams.values())[0]

    stream_stats_view = TrexStreamStatistics(trex.server)
    stream_stats_view.read()
    print(stream_stats_view.statistics.dumps(indent=2))
    assert stream_stats_view.statistics[stream_0]["tx"]["tb"] == 0

    trex.server.clear_stats()
    trex.server.start_transmit(blocking=True)
    stream_stats_view.read()
    print(stream_stats_view.statistics.dumps(indent=2))
    assert stream_stats_view.statistics[stream_0]["tx"]["tp"] == 100
    assert 100 <= stream_stats_view.statistics[stream_0]["rx"][port_1]["rp"]

    trex.server.clear_stats()
    trex.server.start_transmit(True)
    stream_stats_view.read()
    assert stream_stats_view.statistics[stream_0]["tx"]["tp"] == 100
    assert stream_stats_view.statistics[stream_0]["rx"][port_1]["rp"] == 200

    # Add stream and re-write.
    port_0.add_stream("name_stream")
    port_0.write_streams()


def test_capture(trex: TrexApp, ports: list[int]) -> None:
    """Test capture."""
    trex_ports = trex.server.reserve_ports(ports, force=True, reset=True)
    tx_port = list(trex_ports.values())[0]
    rx_port = list(trex_ports.values())[1]
    stream_0 = tx_port.add_stream("s1")
    stream_1 = tx_port.add_stream("s2")

    stream_0.set_rate(TrexRateType.pps, 50)
    stream_0.set_tx_type(TrexTxType.single_burst, packets=100)
    stream_0.set_next("s2")
    packet = STLPktBuilder(pkt=Ether(src="11:11:11:11:11:11") / IP(src="10.10.10.10"))
    stream_0.set_packet(packet, 1, 1)

    stream_1.set_rate(TrexRateType.pps, 50)
    stream_1.set_tx_type(TrexTxType.multi_burst, packets=200, ibg=0.0, count=1)
    packet = STLPktBuilder(pkt=Ether(src="22:22:22:22:22:22") / IP(src="20.20.20.20"))
    stream_1.set_packet(packet, 1, 1)

    tx_port.write_streams()
    trex.server.clear_stats()
    trex.server.start_capture()
    trex.server.start_transmit(True, tx_port)
    tx_port_stats = tx_port.read_stats()
    rx_port_stats = rx_port.read_stats()
    print(json.dumps(tx_port_stats, indent=2))
    print(json.dumps(rx_port_stats, indent=2))
    assert tx_port_stats["opackets"] == 300
    assert 300 <= rx_port_stats["ipackets"] <= 302
    packets = trex.server.stop_capture(output="c:/temp/trex_cap")
    assert len(packets[rx_port]) == 300
    assert len(rx_port.capture.packets) == 300
    print(rx_port.capture.packets[0])
    assert rx_port.capture.packets[0]["scapy"].src in ["11:11:11:11:11:11", "22:22:22:22:22:22"]
    assert rx_port.capture.packets[0]["scapy"].payload.src in ["10.10.10.10", "20.20.20.20"]
