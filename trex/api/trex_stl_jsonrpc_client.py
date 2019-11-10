
import json
from threading import Lock

import zmq
from .trex_stl_types import RC, RC_ERR, RC_OK
from ..common import random_id_gen
from ..zipmsg import ZippedMsg


# sub class to describe a batch
class BatchMessage:
    def __init__(self, rpc_client):
        self.rpc_client = rpc_client
        self.batch_list = []

    def add(self, method_name, params=None, api_class='core'):

        id, msg = self.rpc_client.create_jsonrpc_v2(
            method_name, params, api_class, encode=False)
        self.batch_list.append(msg)

    def invoke(self, block=False, chunk_size=500000, retry=0):
        if not self.rpc_client.connected:
            return RC_ERR("Not connected to server")

        if chunk_size:
            response_batch = RC()
            size = 0
            new_batch = []
            for msg in self.batch_list:
                size += len(json.dumps(msg))
                new_batch.append(msg)

                if size > chunk_size:
                    batch_json = json.dumps(new_batch)
                    response_batch.add(self.rpc_client.send_msg(batch_json))
                    size = 0
                    new_batch = []
            if new_batch:
                batch_json = json.dumps(new_batch)
                response_batch.add(self.rpc_client.send_msg(batch_json))
            return response_batch
        else:
            batch_json = json.dumps(self.batch_list)
            return self.rpc_client.send_msg(batch_json, retry=retry)


# JSON RPC v2.0 client
class JsonRpcClient:

    def __init__(self, default_server, default_port, client):
        self.get_api_h = client._get_api_h
        self.logger = client.logger
        self.connected = False

        # default values
        self.port = default_port
        self.server = default_server

        self.id_gen = random_id_gen()
        self.zipper = ZippedMsg()

        self.lock = Lock()

    def get_connection_details(self):
        rc = {}
        rc['server'] = self.server
        rc['port'] = self.port

        return rc

    # batch messages

    def create_batch(self):
        return BatchMessage(self)

    def create_jsonrpc_v2(self, method_name, params=None, api_class='core', encode=True):
        msg = {}
        msg["jsonrpc"] = "2.0"
        msg["method"] = method_name
        msg["id"] = next(self.id_gen)
        msg["params"] = params if params is not None else {}

        # if this RPC has an API class - add it's handler
        if api_class:
            msg["params"]["api_h"] = self.get_api_h()[api_class]

        # pdb.set_trace()
        if encode:
            return id, json.dumps(msg)
        else:
            return id, msg

    def invoke_rpc_method(self, method_name, params=None, api_class='core', retry=0):
        if not self.connected:
            return RC_ERR("Not connected to server")

        id, msg = self.create_jsonrpc_v2(method_name, params, api_class)

        return self.send_msg(msg, retry=retry)

    def send_msg(self, msg, retry=0):
        # REQ/RESP pattern in ZMQ requires no interrupts during the send
        with self.lock:
            rc = self.__send_msg(msg, retry)
        if rc.bad():
            raise Exception(rc.err())
        return rc

    def __send_msg(self, msg, retry=0):
        # print before
        pretty_json = json.dumps(json.loads(msg), indent=4, separators=(',', ': '), sort_keys=True)
        self.logger.debug(f'Sending Request To Server:\n{pretty_json}\n')

        # encode string to buffer
        buffer = msg.encode("utf-8", "ignore")

        if self.zipper.check_threshold(buffer):
            response = self.send_raw_msg(
                self.zipper.compress(buffer), retry=retry)
        else:
            response = self.send_raw_msg(buffer, retry=retry)

        if not response:
            return response
        elif self.zipper.is_compressed(response):
            response = self.zipper.decompress(response)

        # return to string
        response = response.decode()

        # print after
        pretty_json = json.dumps(json.loads(response), indent=4, separators=(',', ': '), sort_keys=True)
        self.logger.debug(f'Server Response:\n{pretty_json}\n')

        # process response(batch and regular)
        try:
            response_json = json.loads(response)
        except(TypeError, ValueError):
            return RC_ERR("*** [RPC] - Failed to decode response from server")

        if isinstance(response_json, list):
            return self.process_batch_response(response_json)
        else:
            return self.process_single_response(response_json)

    # low level send of string message

    def send_raw_msg(self, msg, retry=0):
        try:
            return self._send_raw_msg_safe(msg, retry)
        except KeyboardInterrupt as e:
            # must restore the socket to a sane state
            self.reconnect()
            raise e

    def _send_raw_msg_safe(self, msg, retry):

        retry_left = retry
        while True:
            try:
                # pdb.set_trace()
                if isinstance(msg, str):
                    msg = msg  # .encode("utf-8", "ignore")

                if isinstance(msg, bytes):
                    self.socket.send(msg)
                else:
                    return RC_ERR("*** [RPC] - failed to understand message to server")
                break
            except zmq.Again:
                retry_left -= 1
                if retry_left < 0:
                    self.disconnect()
                    return RC_ERR("*** [RPC] - Failed to send message to server")

        retry_left = retry
        while True:
            try:
                response = self.socket.recv()
                break
            except zmq.Again:
                retry_left -= 1
                if retry_left < 0:
                    self.disconnect()
                    return RC_ERR("*** [RPC] - Failed to get server response from {0}"
                                  .format(self.transport))

        return response

    # processs a single response from server

    def process_single_response(self, response_json):

        if(response_json.get("jsonrpc") != "2.0"):
            return RC_ERR("Malformed Response({0})".format(str(response_json)))

        # error reported by server
        if("error" in response_json):
            if "specific_err" in response_json["error"]:
                return RC_ERR(response_json["error"]["specific_err"])
            else:
                return RC_ERR(response_json["error"]["message"])

        # if no error there should be a result
        if("result" not in response_json):
            return RC_ERR("Malformed Response({0})".format(str(response_json)))

        return RC_OK(response_json["result"])

    # process a batch response

    def process_batch_response(self, response_json):
        rc_batch = RC()

        for single_response in response_json:
            rc = self.process_single_response(single_response)
            rc_batch.add(rc)

        return rc_batch

    def disconnect(self):
        if self.connected:
            self.socket.close(linger=0)
            self.context.destroy(linger=0)
            self.connected = False
            return RC_OK()
        else:
            return RC_ERR("Not connected to server")

    def connect(self, server=None, port=None):
        if self.connected:
            self.disconnect()

        self.context = zmq.Context()

        self.server = server if server else self.server
        self.port = port if port else self.port

        #  Socket to talk to server
        self.transport = "tcp://{0}:{1}".format(self.server, self.port)

        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(self.transport)

        self.socket.setsockopt(zmq.SNDTIMEO, 10000)
        self.socket.setsockopt(zmq.RCVTIMEO, 10000)

        self.connected = True

    def reconnect(self):
        # connect using current values
        return self.connect()

    def is_connected(self):
        return self.connected

    def __del__(self):
        if hasattr(self, "context"):
            self.context.destroy(linger=0)
