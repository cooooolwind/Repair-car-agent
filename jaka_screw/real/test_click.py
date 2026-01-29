#!/usr/bin/env python3
import pyrealsense2 as rs
import numpy as np
import cv2
import sys
from scipy.spatial.transform import Rotation as R
import json
import logging,os
import socket
import time
import sys

import matplotlib.pyplot as plt
sys.path.append('//home/robot/GRCNN')
sys.path.append('//home/robot/GRCNN/real')
from jaka_Rotate_yc import JAKA_Robot  # 确保文件名正确
from real.realsenseD435 import Camera


from libs.log_setting import CommonLog
from libs.auxiliary import create_folder_with_date, get_ip, popup_message

logger_ = logging.getLogger(__name__)
logger_ = CommonLog(logger_)

tcp_host_ip = '10.5.5.100' 
robot = JAKA_Robot(tcp_host_ip)

test_pos = [95.982, 187.535, -152.559, 233.931, -267.333, 214.593]
radians_list = [(angle * np.pi) / 180 for angle in test_pos]
robot.move_j(radians_list)


rotation_matrix = np.array([
    [-0.72960442,-0.47869273,-0.488396],
    [ 0.68372925,-0.52506026,-0.50678006],
    [-0.0138454,-0.70367961,0.71038251]
])
translation_vector = np.array([0.09459109,0.05475265,-0.02552082])

def convert(x ,y ,z ,x1 ,y1 ,z1 ,rx ,ry ,rz):
    """
    我们需要将手眼标定得到旋转向量和平移向量转换为齐次变换矩阵，然后使用深度相机识别到的物体坐标（x, y, z）和
    机械臂末端的位姿（x1,y1,z1,rx,ry,rz）来计算物体相对于机械臂基座的位姿（x, y, z）

    """
    # 深度相机识别物体返回的坐标
    obj_camera_coordinates = np.array([x, y, z])

    # 机械臂末端的位姿，单位为弧度
    end_effector_pose = np.array([x1, y1, z1,
                                  rx, ry, rz])

    # 将旋转矩阵和平移向量转换为齐次变换矩阵
    T_camera_to_end_effector = np.eye(4)
    T_camera_to_end_effector[:3, :3] = rotation_matrix
    T_camera_to_end_effector[:3, 3] = translation_vector

    # 机械臂末端的位姿转换为齐次变换矩阵
    position = end_effector_pose[:3]
    orientation = R.from_euler('xyz', end_effector_pose[3:], degrees=False).as_matrix()

    T_base_to_end_effector = np.eye(4)
    T_base_to_end_effector[:3, :3] = orientation
    T_base_to_end_effector[:3, 3] = position

    # 计算物体相对于机械臂基座的位姿
    obj_camera_coordinates_homo = np.append(obj_camera_coordinates, [1])  # 将物体坐标转换为齐次坐标

    obj_end_effector_coordinates_homo = T_camera_to_end_effector.dot(obj_camera_coordinates_homo)

    obj_base_coordinates_homo = T_base_to_end_effector.dot(obj_end_effector_coordinates_homo)

    obj_base_coordinates = list(obj_base_coordinates_homo[:3])  # 从齐次坐标中提取物体的x, y, z坐标

    return obj_base_coordinates


# ---------- 配置 ----------
W, H = 640, 480
MAX_VALID_M = 10.0     # 合理深度上限（可按场景调小，例如 3.0）
SEARCH_RADIUS = 8      # 邻域搜索半径（像素）
MIN_SAMPLES_MEDIAN = 3 # 邻域最少样本数用于取中值

# ---------- 初始化 RealSense ----------
pipeline = rs.pipeline()
config = rs.config()
config.enable_stream(rs.stream.depth, W, H, rs.format.z16, 30)
config.enable_stream(rs.stream.color, W, H, rs.format.bgr8, 30)

print("Starting RealSense pipeline...")
profile = pipeline.start(config)

device = profile.get_device()
depth_sensor = device.first_depth_sensor()
depth_scale = depth_sensor.get_depth_scale()
print(f"Depth scale: {depth_scale:.6f} m/unit")

# 打开红外投射器（如果设备支持）
if depth_sensor.supports(rs.option.emitter_enabled):
    depth_sensor.set_option(rs.option.emitter_enabled, 1)

# 对齐 depth -> color
align = rs.align(rs.stream.color)
color_stream = profile.get_stream(rs.stream.color)
color_intr = color_stream.as_video_stream_profile().get_intrinsics()
fx, fy, cx, cy = color_intr.fx, color_intr.fy, color_intr.ppx, color_intr.ppy
print(f"Using color intrinsics: fx={fx:.2f}, fy={fy:.2f}, cx={cx:.2f}, cy={cy:.2f}")

# ---------- 全局变量与回调 ----------
click_coords = None  # 当用户点击时，这里记录 (u (col), v (row))

def on_mouse(event, x, y, flags, param):
    global click_coords
    if event == cv2.EVENT_LBUTTONDOWN:
        # x 是列(u)，y 是行(v)
        click_coords = (int(x), int(y))
        print(f"\nMouse clicked at pixel: ({click_coords[0]}, {click_coords[1]})")

cv2.namedWindow("Color + Depth", cv2.WINDOW_NORMAL)
cv2.setMouseCallback("Color + Depth", on_mouse)

# ---------- 工具函数 ----------
def is_valid_raw(val, depth_scale, max_valid_m=MAX_VALID_M):
    if val == 0 or val == 65535:
        return False
    z = val * depth_scale
    if not (0.001 <= z <= max_valid_m):
        return False
    return True

def find_valid_samples(depth_img, u, v, depth_scale, max_radius=SEARCH_RADIUS):
    H_img, W_img = depth_img.shape
    samples = []
    for r in range(1, max_radius + 1):
        # search square ring of radius r
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                uu, vv = u + dx, v + dy
                if 0 <= uu < W_img and 0 <= vv < H_img:
                    val = int(depth_img[vv, uu])
                    if is_valid_raw(val, depth_scale):
                        samples.append((uu, vv, val))
        if len(samples) >= MIN_SAMPLES_MEDIAN:
            break
    return samples

def compute_xyz_from_raw(u, v, depth_raw, intr, depth_scale):
    Z = depth_raw * depth_scale
    X = (u - intr.ppx) * Z / intr.fx
    Y = (v - intr.ppy) * Z / intr.fy
    return X, Y, Z


# ---------- 主循环 ----------
try:
    while True:
        frames = pipeline.wait_for_frames(timeout_ms=2000)
        aligned = align.process(frames)
        depth_frame = aligned.get_depth_frame()
        color_frame = aligned.get_color_frame()
        if not depth_frame or not color_frame:
            continue

        color_image = np.asanyarray(color_frame.get_data())
        depth_image = np.asanyarray(depth_frame.get_data())

        # 非零深度比例（简单信息）
        non_zero_ratio = np.count_nonzero(depth_image) / depth_image.size

        # 可视化图像（实时显示）
        depth_colormap = cv2.applyColorMap(cv2.convertScaleAbs(depth_image, alpha=0.03), cv2.COLORMAP_JET)
        vis = np.hstack((color_image, depth_colormap))

        # 若用户点击了某点，处理并打印 XYZ
        if click_coords is not None:
            u, v = click_coords
            # socket_command = '{"cmdName": "get_tcp_pos"}'
            # state,pose = send_cmd(client,socket_command)
            pose = robot.get_tcp_position()
            x1, y1, z1, rx, ry, rz = pose
            # bounds check
            if not (0 <= u < W and 0 <= v < H):
                print("Clicked pixel out of bounds.")
            else:
                depth_raw = int(depth_image[v, u])
                if is_valid_raw(depth_raw, depth_scale):
                    X, Y, Z = compute_xyz_from_raw(u, v, depth_raw, color_intr, depth_scale)
                    RoboX,RoboY,RoboZ = convert(X, Y, Z,x1, y1, z1, rx, ry, rz)
                    print(f"✅ Pixel ({u},{v}) valid: raw={depth_raw} -> Camera_XYZ=({X:.4f}, {Y:.4f}, {Z:.4f}) m")
                    print(f"✅ Camera_XYZ valid -> Robo_XYZ=({RoboX:.4f}, {RoboY:.4f}, {RoboZ:.4f}) m")

                    robot.plane_grasp([RoboX,RoboY,RoboZ])
                    # RoboX = RoboX + 0.016
                    # RoboY = RoboY + 0.0155
                    # RoboZ = RoboZ - 0.007
                    

                else:
                    # 在邻域收集样本并用中值回退
                    samples = find_valid_samples(depth_image, u, v, depth_scale)
                    if len(samples) == 0:
                        print(f"⚠️ Pixel ({u},{v}) invalid and no valid neighbor found within radius {SEARCH_RADIUS}.")
                    else:
                        # 以 depth_raw 中值作为回退点
                        vals = np.array([s[2] for s in samples])
                        median_idx = np.argsort(vals)[len(vals)//2]
                        uu, vv, depth_raw_med = samples[median_idx]
                        X, Y, Z = compute_xyz_from_raw(uu, vv, depth_raw_med, color_intr, depth_scale)
                        RoboX,RoboY,RoboZ = convert(X, Y, Z,x1, y1, z1, rx, ry, rz)
                        print(f"✅ Pixel ({u},{v}) valid: raw={depth_raw} -> Camera_XYZ=({X:.4f}, {Y:.4f}, {Z:.4f}) m")
                        print(f"✅ Camera_XYZ valid -> Robo_XYZ=({RoboX:.4f}, {RoboY:.4f}, {RoboZ:.4f}) m")

                        robot.plane_grasp([RoboX,RoboY,RoboZ])
                        # RoboX = RoboX + 0.016
                        # RoboY = RoboY + 0.0155
                        # RoboZ = RoboZ - 0.007
                       
            # reset click
            click_coords = None

        # show visualization
        cv2.imshow("Color + Depth", vis)
        # press 'q' to quit
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break

        # optional: print some status every few frames (not necessary)
        # print(f"Non-zero ratio: {non_zero_ratio:.3f}", end='\r')

finally:
    pipeline.stop()
    cv2.destroyAllWindows()
    print("\nStopped.")
