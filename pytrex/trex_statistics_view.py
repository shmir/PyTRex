
from trafficgenerator.tgn_object import TgnSubStatsDict


class TrexStatistics:

    def __init__(self, server):
        self.server = server
        self.statistics = TgnSubStatsDict()


class TrexPortStatistics(TrexStatistics):

    def read(self):
        self.statistics = TgnSubStatsDict()
        for port in self.server.ports.values():
            self.statistics[port] = port.read_stats()
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

    @classmethod
    def clear_stats(cls, server):
        rc = server.api.rpc.transmit('get_active_pgids')
        ids = rc.data()['ids']['flow_stats']
        cls.base_pgid_stats = server.api.rpc.transmit('get_pgid_stats', params={'pgids': ids}).data()['flow_stats']

    def read(self):
        rc = self.server.api.rpc.transmit('get_pgid_stats', params={'pgids': self.ids})
        pgid_stats = rc.data()['flow_stats']
        self.statistics = TgnSubStatsDict()
        for pgid, stats in pgid_stats.items():
            stream = self.stream_id_to_stream[int(pgid)]
            self.statistics[stream] = {'tx': {}, 'rx': {}}
            tx_port = stream.parent
            for name, values in stats.items():
                if name.startswith('t'):
                    value = values[str(tx_port.id)]
                    if not name.endswith('s') and hasattr(self, 'base_pgid_stats'):
                        value -= self.base_pgid_stats[pgid][name][str(tx_port.id)]
                    self.statistics[stream]['tx'][name] = value
                else:
                    for rx_port, value in values.items():
                        if not name.endswith('s') and hasattr(self, 'base_pgid_stats'):
                            value -= self.base_pgid_stats[pgid][name][str(tx_port.id)]
                        if value:
                            rx_port = self.server.ports[int(rx_port)]
                            if rx_port not in self.statistics[stream]['rx']:
                                self.statistics[stream]['rx'][rx_port] = {}
                            self.statistics[stream]['rx'][rx_port][name] = value
        return self.statistics
