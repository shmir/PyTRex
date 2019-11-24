
from trafficgenerator.tgn_object import TgnObjectsDict


class TrexStatistics:

    def __init__(self, server):
        self.server = server
        self.statistics = TgnObjectsDict()


class TextPortStatistics(TrexStatistics):

    def read(self):
        self.statistics = {}
        for index, port in self.server.ports.items():
            self.statistics[index] = port.read_stats()
        return self.statistics


class TrexStreamStatistics(TrexStatistics):

    def __init__(self, server):
        super().__init__(server)
        rc = self.server.api.rpc.transmit('get_active_pgids')
        self.ids = rc.data()['ids']['flow_stats']
        self.stream_id_to_stream = {}
        for port in server.ports.values():
            for stream in port.streams.values():
                stream_id = stream.fields['flow_stats']['stream_id']
                self.stream_id_to_stream[stream_id] = stream

    def read(self):
        rc = self.server.api.rpc.transmit('get_pgid_stats', params={'pgids': self.ids})
        pgid_stats = rc.data()['flow_stats']
