import os, sys

# 让 Python 能找到 jkrc.so
sys.path.append('/home/robot/jaka')

# 让系统能找到 libjakaAPI.so
os.environ["LD_LIBRARY_PATH"] = "/home/robot/jaka:" + os.environ.get("LD_LIBRARY_PATH", "")

import jkrc
print("✅ import jkrc 成功:", jkrc)

