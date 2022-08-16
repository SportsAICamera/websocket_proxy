from enum import Enum

class EnumCMD(Enum):
    NOTHING = -1

    SEND_IMAGE = 1000

    CMD_MOUSE_DOWN = 2001
    CMD_MOUSE_UP = 2002
    CMD_MOUSE_MOVE = 2003
    CMD_MOUSE_CLICK = 2004
    CMD_MOUSE_DBL_CLICK = 2005

    def getEnumName(val):
        try:
            ret = EnumCMD(int(val)).name
        except:
            ret = "Non Existing CMD"
        # print(ret)
        return ret

EnumCMD.getEnumName("1000")