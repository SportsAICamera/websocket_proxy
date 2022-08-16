import asyncio
import websockets
import json
from datetime import datetime
import os
import glob
import cv2
import numpy as np
import base64

async def hello():
    # 3.20.174.14
    async with websockets.connect("ws://127.0.0.1:8765/1/1") as websocket:
        # Receive Initial Data Packet
        # ret = await websocket.recv()
        # recv = json.loads(ret)
        # print("<-", ret)
        # if recv["frame_no"] == 0:
        #     model_input_size = (recv["width"], recv["height"])
        #     print("model_input_size:", model_input_size)
        # else:
        #     print("Received Initial Data Packet Error!")
        #     return False

        frame_no = 0
        img_dir = 'D:\\git\\verideal data\\V4\\A0 (Original)\\0\\'
        
        cnt = [0, 0, 0]
        time_st = datetime.now()
        for file in sorted(glob.glob(os.path.join(img_dir, "*.png"))):
            filepath = os.path.join(img_dir, file)
            # filepath = "/mnt/sda2/verideal/veridealapp/app/src/main/assets/main_code2.png"
            # print(filepath)
            img = cv2.imread(filepath)
            # resized = cv2.resize(img, model_input_size)
            # cv2.imshow("input", img)
            # cv2.waitKey(0)

            # Compose & Send Data Packet
            frame_no += 1
            data = {}
            data["frame_no"] = frame_no
            retval, buffer = cv2.imencode('.jpg', img)
            data["scene"] = base64.b64encode(buffer).decode('utf-8')

            await websocket.send(json.dumps(data))
            print("->", frame_no)

            await asyncio.sleep(2)

        time_ed = datetime.now()
        print("Total time: {}".format(time_ed - time_st))



asyncio.run(hello())