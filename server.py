import asyncio
from enum import Enum
from multiprocessing.reduction import send_handle
import websockets
from threading import Thread
from time import sleep
import argparse, configparser
import sys 
import json
import base64
from enumCMD import EnumCMD

config = configparser.ConfigParser()
config.read('config.ini')

class DataQueue:
    def __init__(self):
        self.TAG = "[DataQueue]"
        self.buf = asyncio.Queue()

    async def push(data):
        self.buf.put(data)
    
    async def pop(data):
        return self.buf.get()

class StreamSource:
    def __init__(self, uid):
        self.st = self.ed = 0
        self.sz = 3
        self.buf = [[] for x in range(self.sz)]
        self.frame_no = [[] for x in range(self.sz)]
        self.no = 0

        self.writingStatus = False
        self.uid = uid


    def buf_next(self, cur):
        if cur+1 == self.sz:
            return 0
        return cur + 1
    def buf_prev(self, cur):
        if cur == 0:
            return self.sz - 1
        return cur - 1
    def buf_len(self):
        if self.st < self.ed:
            return self.ed - self.st
        else:
            return self.ed - self.st + self.sz

    def push_buf(self, data, no):
        if self.buf_next(self.ed) == self.st:
            self.st = self.buf_next(self.st)

        self.buf[self.ed] = data
        self.frame_no[self.ed] = no
        self.ed = self.buf_next(self.ed)
        # print("pushed", self.st, self.ed)

    def read_buf(self, prev_frame):
        if self.st == self.ed:
        #    print("0")
            return None
        sst = self.buf_next(self.st)
        if sst == self.ed:
        #    print("0")
            return None

        cur_frame = prev_frame + 1
        pos = sst
        last = self.buf_prev(self.ed)
        #return [self.buf[self.st], 0]

        if cur_frame <= self.frame_no[sst]:
            pos = sst
        #    print("1")
        elif cur_frame > self.frame_no[last]:
        #    print("2")
            return None
        else:
        #   print("3")
            while pos != self.ed and self.frame_no[pos]< prev_frame:
                pos = self.buf_next(pos)
            if pos == self.ed:
                return None
        ret = self.buf[pos]
        # print("read success")
        #    self.st = self.buf_next(self.st)
        return [ret, self.frame_no[pos]]

    def start(self):
        self.writingStatus = 1
            
    def isWriting(self):
        if self.writingStatus == 1:
            return True
        return False

class StreamManager:
    def __init__(self):
        self.websock_rooms = {}
        self.stream_pool = {}

    def addWebsocket(self, uid, websocket):
        if uid in self.websock_rooms:
            self.websock_rooms[uid].add(websocket)
            return self.getStreamsource(uid)

        print("uid ", uid, "creating new Video Stream")

        self.websock_rooms[uid] = set()
        self.websock_rooms[uid].add(websocket)

        return self.getStreamsource(uid)

    def removeWebsocket(self, uid, websocket):
        if uid in self.websock_rooms:
            self.websock_rooms[uid].remove(websocket)

    def getStreamsource(self, uid):
        if uid not in self.stream_pool:
            streamsource = StreamSource(uid)
            self.stream_pool[uid] = streamsource
        else:
            streamsource = self.stream_pool[uid]
        return streamsource

class WebsocketProxy:
    streamManager = StreamManager()
    def __init__(self):
        self.TAG = "[WebsocketProxy]"

    async def sendHandler(websocket, fr_path, to_path):
        send_prev_frame = -1
        TAG = "[{} -> {}] : ".format(fr_path, to_path)
        streamsource = WebsocketProxy.streamManager.getStreamsource(fr_path)

        try:
            while True:
                send_obj = await websocket.recv()
                if send_obj is None:
                    await asyncio.sleep(0.1)
                    continue

                data = json.loads(send_obj)
                send_new_frame = data["no"]
                str_cmd = EnumCMD.getEnumName(data["cmd"])
                if send_new_frame <= send_prev_frame:
                    await asyncio.sleep(0.05)
                    continue
                send_prev_frame = send_new_frame
                streamsource.push_buf(send_obj, send_prev_frame)
                print(TAG, str_cmd, send_prev_frame)
                await asyncio.sleep(0.05)
        except Exception as e:
            print(TAG, "Err2", e)
        finally:
            # WebsocketProxy.streamManager.removeWebsocket(fr_path, websocket)
            print(TAG, "Disconnected!")

    async def recvHandler(websocket, fr_path, to_path):
        recv_prev_frame = -1
        TAG = "[{} <- {}] : ".format(fr_path, to_path)
        streamsource = WebsocketProxy.streamManager.getStreamsource(to_path)

        try:
            while True:
                recv_obj = streamsource.read_buf(recv_prev_frame)
                if recv_obj is None:
                    await asyncio.sleep(0.1)
                    continue

                jsondata, recv_new_frame = recv_obj
                if recv_new_frame <= recv_prev_frame:
                    await asyncio.sleep(0.1)
                    continue

                recv_prev_frame = recv_new_frame
                data = json.loads(jsondata)
                # print(len(data))
                str_cmd = EnumCMD.getEnumName(data["cmd"])
                if len(data) == 0:
                    await asyncio.sleep(0.1)
                    continue

                await websocket.send(json.dumps(data))
                print(TAG, str_cmd, recv_prev_frame)
                await asyncio.sleep(0.05)
        except Exception as e:
            print(TAG, "Err2", e)
        finally:
            print(TAG, "Disconnected!")


    async def inoutHandler(websocket, path):
        print("[inoutHandler] New Websocket!", path)
        vals = path.split('/')
        try:
            fr_path = int(vals[1])
            to_path = int(vals[2])
        except:
            print("[inoutHandler] URL Error!", path)
            return

        TAG = "[{} => {}] : ".format(fr_path, to_path)



        send_task = asyncio.ensure_future(
            WebsocketProxy.sendHandler(websocket, fr_path, to_path))
        recv_task = asyncio.ensure_future(
            WebsocketProxy.recvHandler(websocket, fr_path, to_path))
        done, pending = await asyncio.wait(
            [send_task, recv_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()



if __name__ == "__main__":
    import platform
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    stream_port = int(config['STREAM']['stream_port'])
    start_inn_out_server = websockets.serve(WebsocketProxy.inoutHandler, port=stream_port, max_size= 10 * 1024 * 1024, max_queue=20)

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError as ex:
        print(ex)
        loop = asyncio.new_event_loop()
    loop.run_until_complete(start_inn_out_server)
    loop.run_forever()
