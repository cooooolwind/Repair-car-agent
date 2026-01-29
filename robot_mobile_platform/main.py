# main.py
import sys
from ax_robot import goto_poi

if __name__ == "__main__":
    name = sys.argv[1]  # 例如 "3" 或 "充电桩"
    res = goto_poi(name)
    print(res)
