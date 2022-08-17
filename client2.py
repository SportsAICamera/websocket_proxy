import asyncio
import websockets
import json
from datetime import datetime
import os
import glob
import cv2
import numpy as np
import base64
from enumCMD import EnumCMD

async def sendHandler(websocket):
    frame_no = 0
    img_dir = 'D:\\git\\verideal data\\V4\\A0 (Original)\\0\\'
    
    cnt = [0, 0, 0]
    time_st = datetime.now()
    for file in sorted(glob.glob(os.path.join(img_dir, "*.png"))):
        filepath = os.path.join(img_dir, file)
        img = cv2.imread(filepath)
        frame_no += 1
        data = {}
        data["no"] = frame_no
        data["cmd"] = EnumCMD.SEND_IMAGE.value
        retval, buffer = cv2.imencode('.jpg', img)
        data["scene"] = base64.b64encode(buffer).decode('utf-8')

        await websocket.send(json.dumps(data))
        print("->", frame_no)

        await asyncio.sleep(2)

    time_ed = datetime.now()
    print("Total time: {}".format(time_ed - time_st))

async def recvHandler(websocket):
    async for msg in websocket:
        data = json.loads(msg)
        frame_no = data["no"]
        cmd = EnumCMD.getEnumName(data["cmd"])
        print("<- frame_no : {}   cmd : {}".format(frame_no, cmd))

async def hello():
    # 3.20.174.14
    async with websockets.connect("ws://127.0.0.1:8765/1/0") as websocket:
        send_task = asyncio.ensure_future(
            sendHandler(websocket))
        recv_task = asyncio.ensure_future(
            recvHandler(websocket))
        done, pending = await asyncio.wait(
            [send_task, recv_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()





asyncio.run(hello())