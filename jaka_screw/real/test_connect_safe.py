#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
工程级 Modbus RTU 串口测试脚本（安全版）
✅ 特点：
- 明确打印：串口是否打开、读写是否成功、失败原因是什么
- 读失败不会崩溃（不会再出现 result.registers 属性错误）
- 默认不执行夹爪夹紧（避免误动作）
- 可选：执行一次“夹紧”写寄存器 + 再读回确认

使用：
  python3 test_connect_safe.py

如果你确认夹爪前方空、想测试“夹紧”，把 DO_WRITE_CLOSE 改成 True。
"""

import time
import traceback

# -----------------------------
# 0) 配置区（你只需要改这里）
# -----------------------------
PORT = "/dev/ttyACM0"
BAUDRATE = 115200
PARITY = "N"
STOPBITS = 1
BYTESIZE = 8
TIMEOUT = 1.0

SLAVE_ID = 2            # 从站地址（原来 unit=2）
REG_ADDR = 0x6107       # 你项目里的寄存器地址
WRITE_VALUE = 1         # 夹紧命令值（你项目里是 1）
POST_WRITE_SLEEP = 0.5  # 写完等待设备处理时间（秒）

DO_WRITE_CLOSE = False  # ✅默认False：只连接/只读，不写（更安全）


def _import_modbus_client():
    """
    兼容不同 pymodbus 版本的导入方式：
    - 2.x: pymodbus.client.sync
    - 3.x: pymodbus.client
    """
    try:
        from pymodbus.client.sync import ModbusSerialClient  # pymodbus 2.x
        return ModbusSerialClient, "2.x(sync)"
    except Exception:
        from pymodbus.client import ModbusSerialClient       # pymodbus 3.x
        return ModbusSerialClient, "3.x"


def _is_error_response(resp) -> bool:
    """pymodbus 响应对象在错误时一般有 isError()，异常时可能直接抛异常或返回异常类型"""
    if resp is None:
        return True
    try:
        return bool(resp.isError())
    except Exception:
        # 有些异常对象没有 isError
        return True


def _print_resp(prefix: str, resp):
    """统一打印响应对象，避免因为属性不存在导致崩溃"""
    if resp is None:
        print(f"{prefix}: None（没有返回，可能超时/断线）")
        return

    # pymodbus 正常读返回一般带 registers
    if hasattr(resp, "registers"):
        print(f"{prefix}: OK registers={resp.registers}")
        return

    # 错误响应一般可以 str() 出错误信息
    try:
        print(f"{prefix}: ERROR resp={resp!r}, str={str(resp)}")
    except Exception:
        print(f"{prefix}: ERROR resp（无法格式化输出）")


def main():
    ModbusSerialClient, api_ver = _import_modbus_client()
    print(f"🔧 pymodbus 客户端导入方式：{api_ver}")
    print(f"🔌 串口：{PORT}  波特率：{BAUDRATE}  从站：{SLAVE_ID}  超时：{TIMEOUT}s")

    # pymodbus 2.x 支持 method='rtu'；3.x 通常不需要 method 参数
    # 为了兼容，这里做一层 try：
    try:
        client = ModbusSerialClient(
            method="rtu",             # 2.x 需要
            port=PORT,
            baudrate=BAUDRATE,
            parity=PARITY,
            stopbits=STOPBITS,
            bytesize=BYTESIZE,
            timeout=TIMEOUT,
        )
    except TypeError:
        # 3.x 不接受 method 参数
        client = ModbusSerialClient(
            port=PORT,
            baudrate=BAUDRATE,
            parity=PARITY,
            stopbits=STOPBITS,
            bytesize=BYTESIZE,
            timeout=TIMEOUT,
        )

    # 1) 连接
    try:
        ok = client.connect()
    except Exception as e:
        print("❌ connect() 发生异常：", repr(e))
        print(traceback.format_exc())
        return

    if not ok:
        print("❌ Modbus 连接失败（connect() 返回 False）")
        return

    print("✅ Modbus 连接成功")

    # 2) 可选：写夹紧命令（默认关闭）
    if DO_WRITE_CLOSE:
        print("⚠️ 将发送夹爪夹紧命令（请确认夹爪周围安全）")
        try:
            # 兼容参数名：2.x 用 unit，3.x 用 slave
            try:
                wresp = client.write_register(REG_ADDR, WRITE_VALUE, unit=SLAVE_ID)
            except TypeError:
                wresp = client.write_register(REG_ADDR, WRITE_VALUE, slave=SLAVE_ID)

            if _is_error_response(wresp):
                _print_resp("🟥 写寄存器返回", wresp)
            else:
                _print_resp("🟩 写寄存器返回", wresp)

        except Exception as e:
            print("❌ 写寄存器发生异常：", repr(e))
            print(traceback.format_exc())

        time.sleep(POST_WRITE_SLEEP)
    else:
        print("🟦 安全模式：不写寄存器（仅连接/读取）")

    # 3) 读取寄存器（读失败也不会崩）
    try:
        try:
            rresp = client.read_holding_registers(REG_ADDR, 1, unit=SLAVE_ID)
        except TypeError:
            rresp = client.read_holding_registers(REG_ADDR, 1, slave=SLAVE_ID)

        if _is_error_response(rresp):
            _print_resp("🟥 读寄存器返回", rresp)
            print("👉 读失败常见原因：从站地址不对/寄存器不可读/超时/校验或波特率不匹配/设备未响应")
        else:
            _print_resp("🟩 读寄存器返回", rresp)
            # 如果确实有 registers，就打印第一个值
            val = rresp.registers[0] if hasattr(rresp, "registers") and rresp.registers else None
            print(f"📌 读取到的寄存器[0] = {val}")

    except Exception as e:
        print("❌ 读寄存器发生异常：", repr(e))
        print(traceback.format_exc())

    # 4) 关闭
    try:
        client.close()
    except Exception:
        pass
    print("🔒 已关闭串口连接")


if __name__ == "__main__":
    main()

