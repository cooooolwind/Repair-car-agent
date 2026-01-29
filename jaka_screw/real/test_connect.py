from pymodbus.client.sync import ModbusSerialClient
import time

def test_modbus():
    client = ModbusSerialClient(
        method='rtu',
        port='/dev/ttyACM0',
        baudrate=115200,
        parity='N',  # 'N' for None, 'E' for Even, 'O' for Odd
        stopbits=1,
        bytesize=8,
        timeout=1
    )
    
    if client.connect():
        print("✅ Modbus 连接成功")
        
        # 写寄存器 0x6107 = 1 (地址 2)
        client.write_register(0x6107, 1, unit=2)
        print("发送夹爪夹紧命令")
        time.sleep(0.5)
        
        # 读取确认
        result = client.read_holding_registers(0x6107, 1, unit=2)
        if result:
            print(f"读取寄存器值: {result.registers[0]}")
        
        client.close()
    else:
        print("❌ Modbus 连接失败")

if __name__ == "__main__":
    test_modbus()
