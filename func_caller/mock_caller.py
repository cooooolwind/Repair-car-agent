import json
from .base import FuncCaller

class MockFuncCaller(FuncCaller):
    def get_point(self) -> str:
        return "系统定位反馈有两个螺丝，螺丝位置在2"

    def arm_move(self, type: str) -> str:
        val = str(type).strip()
        if val == "1":
            return "机械手状态：已向上移动并拧紧。"
        elif val == "0":
            return "机械手状态：已向下移动归位。"
        else:
            return f"错误：未知类型 {type}。"

    def goto_poi(self, name: str) -> str:
        return json.dumps({"status": "success", "message": f"Mock: Arrived at {name}"}, ensure_ascii=False)