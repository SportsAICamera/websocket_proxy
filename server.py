import asyncio
import websockets
from threading import Thread
from time import sleep
import argparse, configparser
import sys 
import json
import base64

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

    async def innHandler(websocket, path):
        TAG = "[innHandler]"
        print(TAG, " New Websocket ", path)
        vals = path.split('/')
        if len(vals) < 2:
            return

        svideoId = vals[1]
        if svideoId == "":
            svideoId = "1"

        try:
            videoId = int(svideoId)
        except:
            print(TAG, "convert error!")
            return

        # Save Websocket Connection
        streamsource = WebsocketProxy.streamManager.getStreamsource(videoId)
        prev_frame = -1

        try:
            while True:
                ret = await websocket.recv()
                if ret is None:
                    await asyncio.sleep(0.1)
                    continue
                data = json.loads(ret)
                new_frame = data["frame_no"]
                if new_frame <= prev_frame:
                    await asyncio.sleep(0.05)
                    continue
                prev_frame = new_frame
                streamsource.push_buf(ret, prev_frame)
                print("<-", prev_frame)
                await asyncio.sleep(0.05)
        except Exception as e:
            print("innHandler err2", e)
        finally:
            print("Disconnected innStream {}".format(videoId))

    async def outHandler(websocket, path):
        TAG = "[outHandler]"
        print(TAG, " New Websocket ", path)
        vals = path.split('/')
        if len(vals) < 3:
            return

        svideoId = vals[1]
        sstreamId = vals[2]
        if svideoId == "":
            svideoId = "1"
        if sstreamId == "":
            sstreamId = "0"

        try:
            videoId = int(svideoId)
        except:
            print(TAG, "convert error!")
            return

        try:
            streamId = int(sstreamId)
            if streamId > 3:
                streamId = 3
            if streamId < 1:
                streamId = 1
        except:
            print("convert error!")
            return

        # Save Websocket Connection
        streamsource = WebsocketProxy.streamManager.addWebsocket(videoId, websocket)
        prev_frame = -1

        try:
            while True:
                ret = streamsource.read_buf(prev_frame)
                if ret is None:
                    await asyncio.sleep(0.1)
                    continue

                jsondata, new_frame = ret
                if new_frame <= prev_frame:
                    await asyncio.sleep(0.05)
                    continue
                prev_frame = new_frame

                data = json.loads(jsondata)
                # print(len(data))
                if len(data) == 0:
                    await asyncio.sleep(0.1)
                    continue
                
                try:
                    send_obj = {}
                    send_obj["scene"] = data["scene"]
                    send_obj["frame"] = data["frame_no"]
                except Exception as e:
                    print("outHandler err2", e)
                await websocket.send(json.dumps(send_obj))
                print("->", prev_frame)
                # time_save_1 = time.time()
                #        print('FPS:', (time_save_1 - time_save_0))
                await asyncio.sleep(0.05)
        except Exception as e:
            print("outHandler err3", e)
        finally:
            print("Disconnected video {}/{}".format(videoId, streamId))
            WebsocketProxy.streamManager.removeWebsocket(videoId, websocket)

if __name__ == "__main__":

    import platform
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    innstream_port = int(config['STREAM']['innstream_port'])
    outstream_port = int(config['STREAM']['outstream_port'])

    start_inn_server = websockets.serve(WebsocketProxy.innHandler, port=innstream_port, max_size= 10 * 1024 * 1024, max_queue=20)
    start_out_server = websockets.serve(WebsocketProxy.outHandler, port=outstream_port, max_size= 10 * 1024 * 1024, max_queue=20)

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError as ex:
        print(ex)
        loop = asyncio.new_event_loop()
    # loop = asyncio.get_event_loop()
    # loop = asyncio.new_event_loop()
    # asyncio.set_event_loop(loop)
    loop.run_until_complete(start_inn_server)
    loop.run_until_complete(start_out_server)
    loop.run_forever()

    # periodic_inn_task = asyncio.create_task(start_inn_server)
    # periodic_out_task = asyncio.create_task(start_out_server)
    # await asyncio.gather(periodic_inn_task, periodic_out_task)
