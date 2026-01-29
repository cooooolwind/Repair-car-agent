from pymodbus.client.sync import ModbusSerialClient

PORT = "/dev/ttyACM0"
STOPBITS = 1
BYTESIZE = 8
TIMEOUT = 1

BAUDS = [9600, 19200, 38400, 57600, 115200]
PARITIES = ["N", "E", "O"]   # 无/偶/奇
SLAVES = range(1, 11)

def try_one(baud, parity, slave):
    c = ModbusSerialClient(method="rtu", port=PORT, baudrate=baud,
                           parity=parity, stopbits=STOPBITS, bytesize=BYTESIZE, timeout=TIMEOUT)
    if not c.connect():
        c.close()
        return False, "connect False"
    r = c.read_holding_registers(0x0000, 1, unit=slave)
    c.close()
    ok = (r is not None) and (not r.isError())
    return ok, str(r)

for baud in BAUDS:
    for parity in PARITIES:
        hit = False
        for slave in SLAVES:
            ok, info = try_one(baud, parity, slave)
            if ok:
                print(f"✅ HIT baud={baud} parity={parity} slave={slave} -> {info}")
                hit = True
                break
        if not hit:
            print(f"❌ NO  baud={baud} parity={parity} (slaves 1-10 all no)")

