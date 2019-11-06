import argparse
import os
import pprint
import sys

import stl_path

from trex_stl_lib.trex_stl_client import STLClient
from trex_stl_lib.trex_stl_exceptions import STLError
from trex_stl_lib.trex_stl_std import stl_map_ports
from trex_stl import STLProfile


# Basic sparta test
# it maps the ports to sides
# then it load a predefind profile 'sparta_basic'
# and attach it to both sides and inject
# at a certain rate for some time
# finally it checks that all packets arrived
def sparta_basic_test(server, mult):

    # create client
    client = STLClient(server=server)

    passed = True

    try:

        # connect to server
        client.connect()

        # take all the ports
        client.reset()
        print('Connection info:\n')
        print(client.get_connection_info())
        print('\n\n')

        # map ports - identify the routes
        table = stl_map_ports(client)
        print('\n\n')
        print('Actual mapped table(all data):\n')
        print(table)
        print('\n')

        dir_0 = [x[0] for x in table['bi']]
        dir_1 = [x[1] for x in table['bi']]

        print("Mapped ports to sides {0} <--> {1}".format(dir_0, dir_1))

        # load IMIX profile
        # print(stl_path.STL_PROFILES_PATH + '/sparta_basic.py')
        # profile = STLProfile.load_py(os.path.join(stl_path.STL_PROFILES_PATH
        #                                           + '/sparta_basic.py'))
        print('Using profile:\n')
        print(stl_path.STL_PROFILES_PATH + '/ipv4_udp_9k.pcap')
        print('\n')
        profile = STLProfile.load_pcap(os.path.join(stl_path.STL_PROFILES_PATH
                                                    + '/ipv4_udp_9k.pcap'))
        streams = profile.get_streams()

        # add both streams to ports
        client.add_streams(streams, ports=dir_0)
        client.add_streams(streams, ports=dir_1)

        # clear the stats before injecting
        client.clear_stats()

        # choose rate and start traffic for 20 seconds
        duration = 20
        print("Injecting {0} <--> {1} on total rate of '{2}' for {3} seconds"
              .format(dir_0, dir_1, mult, duration))

        client.start(ports=(dir_0 + dir_1), mult=mult, duration=duration, total=True)

        # block until done
        client.wait_on_traffic(ports=(dir_0 + dir_1))

        # read the stats after the test
        stats = client.get_stats()

        # use this for debug info on all the stats
        pprint.pprint(stats)

        # sum dir 0
        dir_0_opackets = sum([stats[i]["opackets"] for i in dir_0])
        dir_0_ipackets = sum([stats[i]["ipackets"] for i in dir_0])

        # sum dir 1
        dir_1_opackets = sum([stats[i]["opackets"] for i in dir_1])
        dir_1_ipackets = sum([stats[i]["ipackets"] for i in dir_1])

        lost_0 = dir_0_opackets - dir_1_ipackets
        lost_1 = dir_1_opackets - dir_0_ipackets

        print("\nPackets injected from {0}: {1:,}".format(dir_0, dir_0_opackets))
        print("Packets injected from {0}: {1:,}".format(dir_1, dir_1_opackets))

        print("\npackets lost from {0} --> {1}:   {2:,} pkts".format(dir_0, dir_0, lost_0))
        print("packets lost from {0} --> {1}:   {2:,} pkts".format(dir_1, dir_1, lost_1))

        if client.get_warnings():
            print("\n\n*** test had warnings ****\n\n")
            for w in client.get_warnings():
                print(w)

        if (lost_0 <= 0) and (lost_1 <= 0) and not client.get_warnings():   # less or equal
                                                                            # because we might
                                                                            # have incoming arps
                                                                            # etc.
            passed = True
        else:
            passed = False

    except STLError as e:
        passed = False
        print(e)
        sys.exit(1)

    finally:
        client.disconnect()

    if passed:
        print("\nTest has passed :-)\n")
    else:
        print("\nTest has failed :-(\n")


parser = argparse.ArgumentParser(description="Basic TRex Stateless, sending pcap traffic")
parser.add_argument('-s', '--server',
                    dest='server',
                    help='Remote trex address',
                    default='127.0.0.1',
                    type=str)
parser.add_argument('-m', '--mult',
                    dest='mult',
                    help='Multiplier of traffic, see Stateless help for more info',
                    default='30%',
                    type=str)
args = parser.parse_args()

# run the tests
sparta_basic_test(args.server, args.mult)
