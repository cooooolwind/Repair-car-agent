# ax_robot.py
import sys
import subprocess
import json
from typing import Dict

def goto_poi(name: str) -> Dict:
    """
    Python 函数：让 AMR 去指定 POI
    """
    proc = subprocess.run(
        ["node", "/home/nvidia/robot/Repair-car-agent/robot_mobile_platform/move_to_poi.js", name],
        capture_output=True,
        text=True,
        #cwd=".",   # robot_mobile_platform 目录
        timeout=60
    )

    if proc.returncode != 0:
        return {"ok": False, "stderr": proc.stderr}

    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        return {"ok": False, "raw": proc.stdout}



