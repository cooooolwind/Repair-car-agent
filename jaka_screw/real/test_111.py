import matplotlib.pyplot as plt
import numpy as np
import time
import cv2
# from UR_Robot import UR_Robot
import sys
sys.path.append('/home/robot/jaka/python_env')
import jkrc
from scipy import optimize  
from mpl_toolkits.mplot3d import Axes3D  

import sys
sys.path.append('//home/robot/GRCNN')
sys.path.append('//home/robot/GRCNN/real')
# 导入自定义机械臂控制类（关键修改：从jaka_robot模块导入Jaka_Robot）
# 若jaka_robot.py在其他路径，需添加路径：sys.path.append('/path/to/jaka_robot_directory')
from jaka_robot import Jaka_Robot  # 导入封装好的机械臂类
from real.robotiq_gripper import RobotiqGripper  # 夹爪控制类（若jaka_robot已包含可省略）
from real.realsenseD435 import Camera  # 相机控制类（若jaka_robot已包含可省略）

ip = '10.5.5.100' # IP and port to robot arm as TCP client (UR5)
# tcp_port = 30003
# workspace_limits = np.asarray([[0.3, 0.75], [0.05, 0.4], [-0.2, -0.1]]) # Cols: min max, Rows: x y z (define workspace limits in robot coordinates)
# workspace_limits = np.asarray([[0.35, 0.55], [0, 0.35], [0.15, 0.25]])
workspace_limits = np.asarray([[0.2, 0.4], [0.4, 0.6], [0.05, 0.1]])

robot = Jaka_Robot(ip,workspace_limits=workspace_limits,
        is_use_robotiq85=False,  # 标定无需夹爪，可关闭
        is_use_camera=True)      ####jaka_robot初始化

robot.move_j([-np.pi, -np.pi/2, np.pi/2, 0, np.pi/2, np.pi])

