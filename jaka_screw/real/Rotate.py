import serial
import time
import struct
import minimalmodbus

# ---------- CRC16校验函数（Modbus RTU标准） ----------
def crc16(data: bytes):
    crc = 0xFFFF
    for pos in data:
        crc ^= pos
        for _ in range(8):
            if (crc & 0x0001) != 0:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return struct.pack('<H', crc)  # little-endian返回两字节

# ---------- 发送指令函数 ----------
def send_command(ser, cmd_hex: str):
    """
    cmd_hex: 形如 '02 06 61 07 00 01' 的字符串
    """
    cmd_bytes = bytes.fromhex(cmd_hex)
    crc = crc16(cmd_bytes)
    full_cmd = cmd_bytes + crc
    ser.write(full_cmd)
    print(f"发送: {full_cmd.hex(' ')}")
    time.sleep(0.2)
    # 可选读取返回
    if ser.in_waiting:
        resp = ser.read_all()
        print(f"响应: {resp.hex(' ')}")
    time.sleep(0.5)


# ---------- 主流程 ----------
def main():
    # 打开串口
    ser = serial.Serial(port='/dev/ttyACM0', baudrate=115200, timeout=1)
    print("已连接 COM7")


    # ② 夹爪夹紧
    print("夹爪夹紧")
    # send_command(ser, "02 06 61 07 00 01")

    # print("旋转 到1000000绝对位置点")
    # send_command(ser, "01 06 61 07 00 01")

    time.sleep(8)

    # ④ 松开
    # print("夹爪松开")
    send_command(ser, "02 06 61 07 00 00")


    # ⑤ 旋转 回0绝对位置点
    # print("旋转 回0绝对位置点")
    send_command(ser, "01 06 61 07 00 00")

    print("操作完成！")
    ser.close()



if __name__ == "__main__":
    main()