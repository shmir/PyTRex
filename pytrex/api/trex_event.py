
import datetime
import re
import time
import traceback

from .trex_stl_types import listify
from ..text_opts import format_text


# an event
class Event(object):

    def __init__(self, origin, ev_type, msg):
        self.origin = origin
        self.ev_type = ev_type
        self.msg = msg

        self.ts = datetime.datetime.fromtimestamp(
            time.time()).strftime('%Y-%m-%d %H:%M:%S')

    def __str__(self):

        prefix = "[{:^}][{:^}]".format(self.origin, self.ev_type)

        return "{:<10} - {:18} - {:}".format(self.ts, prefix, format_text(self.msg, 'bold'))


# handles different async events given to the client
class EventsHandler(object):
    EVENT_PORT_STARTED = 0
    EVENT_PORT_STOPPED = 1
    EVENT_PORT_PAUSED = 2
    EVENT_PORT_RESUMED = 3
    EVENT_PORT_JOB_DONE = 4
    EVENT_PORT_ACQUIRED = 5
    EVENT_PORT_RELEASED = 6
    EVENT_PORT_ERROR = 7
    EVENT_PORT_ATTR_CHG = 8

    EVENT_SERVER_STOPPED = 100

    def __init__(self, client):
        self.client = client
        self.logger = self.client.logger

        self.events = []

        # events are disabled by default until explicitly enabled
        self.enabled = False

    # will start handling events

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    def is_enabled(self):
        return self.enabled

    # public functions

    def get_events(self, ev_type_filter=None):
        if ev_type_filter:
            return [ev for ev in self.events if ev.ev_type in listify(ev_type_filter)]
        else:
            return [ev for ev in self.events]

    def clear_events(self):
        self.events = []

    def log_warning(self, msg):
        self.__add_event_log('local', 'warning', msg)

    # events called internally

    def on_async_timeout(self, timeout_sec):
        if self.client.conn.is_connected():
            msg = 'Connection lost - Subscriber timeout: no data from TRex '
            + 'server for more than {0} seconds'.format(timeout_sec)
            self.log_warning(msg)

            # we cannot simply disconnect the connection - we mark it for disconnection
            # later on, the main thread will execute an ordered disconnection
            self.client.conn.mark_for_disconnect(msg)

    def on_async_crash(self):
        msg = 'subscriber thread has crashed:\n\n{0}'.format(
            traceback.format_exc())
        self.log_warning(msg)

        # if connected, mark as disconnected
        if self.client.conn.is_connected():
            self.client.conn.mark_for_disconnect(msg)

    def on_async_alive(self):
        pass

    def on_async_rx_stats_event(self, data, baseline):
        if not self.is_enabled():
            return

        self.client.flow_stats.update(data, baseline)

    def on_async_latency_stats_event(self, data, baseline):
        if not self.is_enabled():
            return

        self.client.latency_stats.update(data, baseline)

    # handles an async stats update from the subscriber
    def on_async_stats_update(self, dump_data, baseline):
        if not self.is_enabled():
            return

        global_stats = {}
        port_stats = {}

        # filter the values per port and general
        for key, value in list(dump_data.items()):
            # match a pattern of ports
            m = re.search(r'(.*)\-(\d+)', key)
            if m:
                port_id = int(m.group(2))
                field_name = m.group(1)
                if port_id in self.client.ports:
                    if port_id not in port_stats:
                        port_stats[port_id] = {}
                    port_stats[port_id][field_name] = value
                else:
                    continue
            else:
                # no port match - general stats
                global_stats[key] = value

        # update the general object with the snapshot
        self.client.global_stats.update(global_stats, baseline)

        # update all ports
        for port_id, data in list(port_stats.items()):
            self.client.ports[port_id].port_stats.update(data, baseline)

    # dispatcher for server async events(port started, port stopped and etc.)

    def on_async_event(self, event_id, data):
        if not self.is_enabled():
            return

        # default type info and do not show
        ev_type = 'info'
        show_event = False

        # port started
        if(event_id == self.EVENT_PORT_STARTED):
            port_id = int(data['port_id'])
            ev = "Port {0} has started".format(port_id)
            self.__async_event_port_started(port_id)

        # port stopped
        elif(event_id == self.EVENT_PORT_STOPPED):
            port_id = int(data['port_id'])
            ev = "Port {0} has stopped".format(port_id)

            # call the handler
            self.__async_event_port_stopped(port_id)

        # port paused
        elif(event_id == self.EVENT_PORT_PAUSED):
            port_id = int(data['port_id'])
            ev = "Port {0} has paused".format(port_id)

            # call the handler
            self.__async_event_port_paused(port_id)

        # port resumed
        elif(event_id == self.EVENT_PORT_RESUMED):
            port_id = int(data['port_id'])
            ev = "Port {0} has resumed".format(port_id)

            # call the handler
            self.__async_event_port_resumed(port_id)

        # port finished traffic
        elif(event_id == self.EVENT_PORT_JOB_DONE):
            port_id = int(data['port_id'])
            ev = "Port {0} job done".format(port_id)

            # call the handler
            self.__async_event_port_job_done(port_id)

            # mark the event for show
            show_event = True

        # port was acquired - maybe stolen...
        elif(event_id == self.EVENT_PORT_ACQUIRED):
            session_id = data['session_id']

            port_id = int(data['port_id'])
            who = data['who']
            force = data['force']

            # if we hold the port and it was not taken by this session - show it
            if port_id in self.client.get_acquired_ports() and session_id != self.client.session_id:
                ev_type = 'warning'

            # format the thief/us...
            if session_id == self.client.session_id:
                user = 'you'
            elif who == self.client.username:
                user = 'another session of you'
            else:
                user = "'{0}'".format(who)

            if force:
                ev = "Port {0} was forcely taken by {1}".format(port_id, user)
            else:
                ev = "Port {0} was taken by {1}".format(port_id, user)

            # call the handler in case its not this session
            if session_id != self.client.session_id:
                self.__async_event_port_acquired(port_id, who)

        # port was released
        elif(event_id == self.EVENT_PORT_RELEASED):
            port_id = int(data['port_id'])
            who = data['who']
            session_id = data['session_id']

            if session_id == self.client.session_id:
                user = 'you'
            elif who == self.client.username:
                user = 'another session of you'
            else:
                user = "'{0}'".format(who)

            ev = "Port {0} was released by {1}".format(port_id, user)

            # call the handler in case its not this session
            if session_id != self.client.session_id:
                self.__async_event_port_released(port_id)

        elif(event_id == self.EVENT_PORT_ERROR):
            port_id = int(data['port_id'])
            ev = "port {0} job failed".format(port_id)
            ev_type = 'warning'

        # port attr changed
        elif(event_id == self.EVENT_PORT_ATTR_CHG):

            port_id = int(data['port_id'])

            diff = self.__async_event_port_attr_changed(port_id, data['attr'])
            if not diff:
                return

            ev = "port {0} attributes changed".format(port_id)
            for key, (old_val, new_val) in list(diff.items()):
                ev += '\n  {key}: {old} -> {new}'.format(
                    key=key,
                    old=old_val.lower() if type(old_val) is str else old_val,
                    new=new_val.lower() if type(new_val) is str else new_val)

            ev_type = 'info'
            show_event = False

        # server stopped
        elif(event_id == self.EVENT_SERVER_STOPPED):
            ev = "Server has been shutdown - cause: '{0}'".format(
                data['cause'])
            self.__async_event_server_stopped(ev)
            ev_type = 'warning'

        else:
            # unknown event - ignore
            return

        # showed events(port job done,
        self.__add_event_log('server', ev_type, ev, show_event)

    # private functions

    # on rare cases events may come on a non existent prot
    # (server was re-run with different config)

    def __async_event_port_job_done(self, port_id):
        if port_id in self.client.ports:
            self.client.ports[port_id].async_event_port_job_done()

    def __async_event_port_stopped(self, port_id):
        if port_id in self.client.ports:
            self.client.ports[port_id].async_event_port_stopped()

    def __async_event_port_started(self, port_id):
        if port_id in self.client.ports:
            self.client.ports[port_id].async_event_port_started()

    def __async_event_port_paused(self, port_id):
        if port_id in self.client.ports:
            self.client.ports[port_id].async_event_port_paused()

    def __async_event_port_resumed(self, port_id):
        if port_id in self.client.ports:
            self.client.ports[port_id].async_event_port_resumed()

    def __async_event_port_acquired(self, port_id, who):
        if port_id in self.client.ports:
            self.client.ports[port_id].async_event_acquired(who)

    def __async_event_port_released(self, port_id):
        if port_id in self.client.ports:
            self.client.ports[port_id].async_event_released()

    def __async_event_server_stopped(self, cause):
        self.client.conn.mark_for_disconnect(cause)

    def __async_event_port_attr_changed(self, port_id, attr):
        if port_id in self.client.ports:
            return self.client.ports[port_id].async_event_port_attr_changed(attr)

    # add event to log
    def __add_event_log(self, origin, ev_type, msg, show_event=False):

        event = Event(origin, ev_type, msg)
        self.events.append(event)

        if ev_type == 'info' and show_event:
            self.logger.async_log("\n\n{0}".format(str(event)))

        elif ev_type == 'warning':
            self.logger.urgent_async_log("\n\n{0}".format(str(event)))
