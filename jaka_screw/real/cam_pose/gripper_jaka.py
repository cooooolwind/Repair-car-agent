"""Module to control Robotiq's grippers - 完全修复泛型注解问题"""

import socket
import threading
import time
from enum import Enum
from typing import Union, Tuple, Dict  # 从typing导入Dict（Python 3.8支持）

import sys
sys.path.append('//home/robot/GRCNN')
sys.path.append('//home/robot/GRCNN/real')
class RobotiqGripper:
    """Robotiq夹爪控制类（严格符合泛型注解规范）"""
    # 变量定义
    ACT = 'ACT'
    GTO = 'GTO'
    ATR = 'ATR'
    ADR = 'ADR'
    FOR = 'FOR'
    SPE = 'SPE'
    POS = 'POS'
    STA = 'STA'
    PRE = 'PRE'
    OBJ = 'OBJ'
    FLT = 'FLT'

    ENCODING = 'UTF-8'

    class GripperStatus(Enum):
        RESET = 0
        ACTIVATING = 1
        ACTIVE = 3

    class ObjectStatus(Enum):
        MOVING = 0
        STOPPED_OUTER_OBJECT = 1
        STOPPED_INNER_OBJECT = 2
        AT_DEST = 3

    def __init__(self):
        self.socket = None
        self.command_lock = threading.Lock()
        self._min_position = 0
        self._max_position = 255
        self._min_speed = 0
        self._max_speed = 255
        self._min_force = 0
        self._max_force = 255

    def connect(self, hostname: str, port: int, socket_timeout: float = 2.0) -> None:
        """连接到夹爪"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((hostname, port))
        self.socket.settimeout(socket_timeout)

    def disconnect(self) -> None:
        """断开与夹爪的连接"""
        if self.socket:
            self.socket.close()
            self.socket = None  # 释放资源后重置为None

    def _set_vars(self, var_dict: Dict[str, Union[int, float]]) -> bool:
        """设置多个变量值"""
        cmd = "SET"
        for variable, value in var_dict.items():
            cmd += f" {variable} {int(value)}"  # 强制转换为整数
        cmd += '\n'
        try:
            with self.command_lock:
                self.socket.sendall(cmd.encode(self.ENCODING))
                data = self.socket.recv(1024)
            return self._is_ack(data)
        except (socket.timeout, ConnectionResetError) as e:
            self.socket = None
            raise RuntimeError(f"通信错误: {e}") from e

    def _set_var(self, variable: str, value: Union[int, float]) -> bool:
        """设置单个变量值"""
        return self._set_vars({variable: value})

    @staticmethod
    def _is_ack(data: bytes) -> bool:
        """检查是否收到确认响应"""
        return data == b'ack'

    def _get_var(self, variable: str) -> int:
        """获取变量值"""
        try:
            with self.command_lock:
                self.socket.sendall(f"GET {variable}\n".encode(self.ENCODING))
                data = self.socket.recv(1024)
            if not data:
                raise RuntimeError("未收到夹爪响应")
            var_name, value_str = data.decode(self.ENCODING).split()
            if var_name != variable:
                raise ValueError(f"响应不匹配: {var_name} != {variable}")
            return int(value_str)
        except (socket.timeout, ConnectionResetError) as e:
            self.socket = None
            raise RuntimeError(f"通信错误: {e}") from e

    def _reset(self) -> None:
        """重置夹爪"""
        self._set_var(self.ACT, 0)
        self._set_var(self.ATR, 0)
        while not (self._get_var(self.ACT) == 0 and self._get_var(self.STA) == 0):
            self._set_var(self.ACT, 0)
            self._set_var(self.ATR, 0)
            time.sleep(0.01)
        time.sleep(0.5)

    def activate(self) -> None:
        """激活夹爪"""
        if not self.is_active():
            self._reset()
            self._set_var(self.ACT, 1)
            time.sleep(1.0)
            while not (self._get_var(self.ACT) == 1 and self._get_var(self.STA) == 3):
                time.sleep(0.01)

    def is_active(self) -> bool:
        """检查夹爪是否已激活"""
        return RobotiqGripper.GripperStatus(self._get_var(self.STA)) == RobotiqGripper.GripperStatus.ACTIVE

    def get_current_position(self) -> int:
        """获取当前位置"""
        return self._get_var(self.POS)

    def move(self, position: int, speed: int, force: int) -> Tuple[bool, int]:
        """发送运动指令"""
        # 参数校验
        if not (0 <= position <= 255 and 0 <= speed <= 255 and 0 <= force <= 255):
            raise ValueError("参数超出范围 (0-255)")

        def clip_val(min_val: int, val: Union[int, float], max_val: int) -> int:
            return max(min_val, min(int(val), max_val))

        clip_pos = clip_val(self._min_position, position, self._max_position)
        clip_spe = clip_val(self._min_speed, speed, self._max_speed)
        clip_for = clip_val(self._min_force, force, self._max_force)

        success = self._set_vars({
            self.POS: clip_pos,
            self.SPE: clip_spe,
            self.FOR: clip_for,
            self.GTO: 1
        })
        return success, clip_pos

    def move_and_wait_for_pos(self, position: int, speed: int, force: int, timeout: float = 10.0) -> Tuple[int, ObjectStatus]:
        """发送运动指令并等待完成"""
        set_ok, cmd_pos = self.move(position, speed, force)
        if not set_ok:
            raise RuntimeError("运动指令发送失败")

        # 等待夹爪确认位置指令
        start_time = time.time()
        while self._get_var(self.PRE) != cmd_pos:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"等待夹爪响应超时 ({timeout}秒)")
            time.sleep(0.001)

        # 等待夹爪完成运动
        start_time = time.time()
        while True:
            obj_status = self._get_var(self.OBJ)
            if obj_status != self.ObjectStatus.MOVING.value:
                break
            if time.time() - start_time > timeout:
                raise TimeoutError(f"夹爪运动超时 ({timeout}秒)")
            time.sleep(0.01)

        return self.get_current_position(), self.ObjectStatus(obj_status)
