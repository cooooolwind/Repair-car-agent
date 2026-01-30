import json
from .base import FuncCaller
from robot_mobile_platform.ax_robot import goto_poi as _goto_poi_func
from jaka_screw.real.robot_tools import Arm_move

class RealFuncCaller(FuncCaller):
    def get_point(self) -> str:
        return "系统定位反馈有两个螺丝，螺丝位置在2"

    def arm_move(self, type: str) -> str:
        return Arm_move(type)

    def goto_poi(self, name: str) -> str:
        # 调用真实机器人接口
        res = _goto_poi_func(name)
        return json.dumps(res, ensure_ascii=False)