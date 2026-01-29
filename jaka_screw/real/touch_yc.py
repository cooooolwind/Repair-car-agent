#!/usr/bin/env python

import matplotlib.pyplot as plt
import numpy as np
import time
import cv2
import sys
sys.path.append('//home/robot/GRCNN')
sys.path.append('//home/robot/GRCNN/real')
from jaka_robot_yc import JAKA_Robot  # 确保文件名正确
from real.realsenseD435 import Camera

# User options (change me)
# --------------- Setup options ---------------
tcp_host_ip = '10.5.5.100' # IP and port to robot arm as TCP client (UR5)
# tcp_port = 30003
# tool_orientation = [-np.pi,0,0]
tool_orientation = [(91.263 * np.pi)/180,(-42.111 * np.pi)/180 , (123.830 * np.pi)/180]

# ---------------------------------------------

# Move robot to home pose
robot = JAKA_Robot(tcp_host_ip)
# robot.move_j([-np.pi, -np.pi/2, np.pi/2, 0, np.pi/2, np.pi])
test_pos = [206.623, 61.893, 143.320, -27.771, -83.912, -44.206]
radians_list = [(angle * np.pi) / 180 for angle in test_pos]
robot.move_j(radians_list)
robot.open_gripper()

# Slow down robot
robot.joint_acc = 1.4
robot.joint_vel = 1.05

# Callback function for clicking on OpenCV window
click_point_pix = ()
camera_color_img, camera_depth_img = robot.get_camera_data()
def mouseclick_callback(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        global camera, robot, click_point_pix
        click_point_pix = (x,y)

        # Get click point in camera coordinates
        click_z = camera_depth_img[y][x] * robot.cam_depth_scale
        click_x = np.multiply(x-robot.cam_intrinsics[0][2],click_z/robot.cam_intrinsics[0][0])
        click_y = np.multiply(y-robot.cam_intrinsics[1][2],click_z/robot.cam_intrinsics[1][1])
        if click_z == 0:
            return
        click_point = np.asarray([click_x,click_y,click_z])
        click_point.shape = (3,1)

        # Convert camera to robot coordinates
        # camera2robot = np.linalg.inv(robot.cam_pose)
        camera2robot = robot.cam_pose
        target_position = np.dot(camera2robot[0:3,0:3],click_point) + camera2robot[0:3,3:]

        target_position = target_position[0:3,0]
        print(target_position)
        print(target_position.shape)
        destination=np.append(target_position,tool_orientation)
        robot.plane_grasp([target_position[0],target_position[1],target_position[2]])


# Show color and depth frames
cv2.namedWindow('color')
cv2.setMouseCallback('color', mouseclick_callback)
cv2.namedWindow('depth')

while True:
    camera_color_img, camera_depth_img = robot.get_camera_data()
    bgr_data = cv2.cvtColor(camera_color_img, cv2.COLOR_RGB2BGR)
    if len(click_point_pix) != 0:
        bgr_data = cv2.circle(bgr_data, click_point_pix, 7, (0,0,255), 2)
    cv2.imshow('color', bgr_data)
    cv2.imshow('depth', camera_depth_img)
    
    if cv2.waitKey(1) == ord('c'):
        break

cv2.destroyAllWindows()
