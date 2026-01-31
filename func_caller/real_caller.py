import json
import socket
from .base import FuncCaller
from robot_mobile_platform.ax_robot import goto_poi as _goto_poi_func
from jaka_screw.real.robot_tools import Arm_move
from robot_mobile_platform.audio_player import play_audio as _play_audio

class RealFuncCaller(FuncCaller):
    def __init__(self):
        try:
            # 创建一个 UDP 套接字
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # 并不需要真的连接，只要目标地址格式正确即可
            s.connect(('8.8.8.8', 80))
            # 获取套接字自己的 IP 地址
            self.host_ip = s.getsockname()[0]
        finally:
            s.close()

    def get_point(self) -> str:
        return "系统定位反馈有两个螺丝，螺丝位置在2"

    def arm_move(self, type: str) -> str:
        return Arm_move(type)

    def goto_poi(self, name: str) -> str:
        # 调用真实机器人接口
        res = _goto_poi_func(name)
        return json.dumps(res, ensure_ascii=False)
    
    def play_audio(self, url: str) -> str:
        # 调用真实音频播放接口
        res = _play_audio(f"http://{self.host_ip}:8000/audio/{url}")
        return json.dumps(res, ensure_ascii=False)