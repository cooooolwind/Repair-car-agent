from pymodbus.client.sync import ModbusSerialClient

PORT="/dev/ttyACM0"

client = ModbusSerialClient(
    method="rtu",
    port=PORT,
    baudrate=115200,
    parity="N",
    stopbits=1,
    bytesize=8,
    timeout=1
)

print("open:", client.connect())

# 扫描 1~20 个从站地址
for sid in range(1, 21):
    try:
        r = client.read_holding_registers(0x0000, 1, unit=sid)
        ok = (r is not None) and (not r.isError())
        print(f"sid={sid:02d}: {'OK' if ok else 'NO'} -> {r}")
    except Exception as e:
        print(f"sid={sid:02d}: EXC -> {e}")

client.close()

