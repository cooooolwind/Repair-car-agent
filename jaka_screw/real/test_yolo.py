#!/usr/bin/env python3
import pyrealsense2 as rs
import numpy as np
import cv2
from ultralytics import YOLO
from scipy.spatial.transform import Rotation as R
import sys                                                                                                                                                                                                                  
import time

# sys.path.append('//home/robot/GRCNN')
# sys.path.append('//home/robot/GRCNN/real')
from jaka_Rotate_yc import JAKA_Robot  # 确保路径正确

# ------------------- 1. 初始化相机 + YOLO -------------------
W, H = 640, 480
pipeline = rs.pipeline()
config = rs.config()
config.enable_stream(rs.stream.depth, W, H, rs.format.z16, 30)
config.enable_stream(rs.stream.color, W, H, rs.format.bgr8, 30)
profile = pipeline.start(config)
print("✅ RealSense started")

device = profile.get_device()
depth_sensor = device.first_depth_sensor()
depth_scale = depth_sensor.get_depth_scale()
print(f"Depth scale: {depth_scale:.6f} m/unit")

align = rs.align(rs.stream.color)
color_stream = profile.get_stream(rs.stream.color)
color_intr = color_stream.as_video_stream_profile().get_intrinsics()
fx, fy, cx, cy = color_intr.fx, color_intr.fy, color_intr.ppx, color_intr.ppy
print(f"Using color intrinsics: fx={fx:.2f}, fy={fy:.2f}, cx={cx:.2f}, cy={cy:.2f}")



# ------------------- 2. 初始化机械臂 -------------------
tcp_host_ip = '10.5.5.100'
robot = JAKA_Robot(tcp_host_ip)

test_pos = [95.982, 187.535, -152.559, 233.931, -267.333, 214.593]
radians_list = [(angle * np.pi) / 180 for angle in test_pos]
robot.move_j(radians_list)


# ------------------- 3. 手眼标定结果 -------------------
rotation_matrix = np.array([
    [-0.72960442,-0.47869273,-0.488396],
    [ 0.68372925,-0.52506026,-0.50678006],
    [-0.0138454,-0.70367961,0.71038251]
])
translation_vector = np.array([0.09459109,0.05475265,-0.02552082])

# ------------------- 4. 坐标转换函数 -------------------
def convert(x, y, z, x1, y1, z1, rx, ry, rz):
    obj_camera_coordinates = np.array([x, y, z])
    end_effector_pose = np.array([x1, y1, z1, rx, ry, rz])

    T_camera_to_end_effector = np.eye(4)
    T_camera_to_end_effector[:3, :3] = rotation_matrix
    T_camera_to_end_effector[:3, 3] = translation_vector

    position = end_effector_pose[:3]
    orientation = R.from_euler('xyz', end_effector_pose[3:], degrees=False).as_matrix()

    T_base_to_end_effector = np.eye(4)
    T_base_to_end_effector[:3, :3] = orientation
    T_base_to_end_effector[:3, 3] = position

    obj_camera_h = np.append(obj_camera_coordinates, [1])
    obj_end_effector_h = T_camera_to_end_effector.dot(obj_camera_h)
    obj_base_h = T_base_to_end_effector.dot(obj_end_effector_h)

    return list(obj_base_h[:3])

# ------------------- 5. 工具函数 -------------------
def is_valid_depth(val, depth_scale):
    if val == 0 or val == 65535:
        return False
    z = val * depth_scale
    return 0.001 <= z <= 3.0  # 限制深度范围3米内

def compute_xyz(u, v, depth_raw, intr, depth_scale):
    Z = depth_raw * depth_scale
    X = (u - intr.ppx) * Z / intr.fx
    Y = (v - intr.ppy) * Z / intr.fy
    return X, Y, Z

# ------------------- 6. 主循环 main arm_work-------------------

print("✅ 系统启动完成，进入自动拧螺丝模式（检测→执行→等待20s→重复）")
model1 = YOLO("best.pt")
model2 = YOLO("hole2.pt")
type = 1    ## 0 down 1 up
print("✅ YOLO 模型加载完成")
try:
    time.sleep(20)
    while True:
        type = (type+1)%2
        frames = pipeline.wait_for_frames()
        aligned = align.process(frames)
        depth_frame = aligned.get_depth_frame()
        color_frame = aligned.get_color_frame()
        if not depth_frame or not color_frame:
            continue

        color_image = np.asanyarray(color_frame.get_data())
        depth_image = np.asanyarray(depth_frame.get_data())

        # YOLO 检测
        if type==0:
            results = model1(color_image)
        
        if type==1:
            results = model2(color_image)
        
        
        annotated = results[0].plot()

        if len(results[0].boxes) > 0:
            # 取置信度最高的目标
            best_box = max(results[0].boxes, key=lambda b: float(b.conf[0]))
            x1, y1, x2, y2 = best_box.xyxy[0].cpu().numpy()
            u = int((x1 + x2) / 2)
            v = int((y1 + y2) / 2)
            conf = float(best_box.conf[0])

            # 标注检测结果
            cv2.circle(annotated, (u, v), 6, (0, 255, 0), -1)
            cv2.putText(annotated, f"Target ({u},{v}) conf={conf:.2f}",
                        (u-60, v-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)
            cv2.putText(annotated, "Screw detected, preparing execution...", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
            cv2.imshow("YOLO Detection", annotated)
            cv2.waitKey(1)

            print(f"\n🟢 检测到螺丝 (conf={conf:.2f})，画面已停留。")
            time.sleep(1)  # 停留让你看清楚目标

            # 获取深度
            depth_raw = int(depth_image[v, u])
            if not is_valid_depth(depth_raw, depth_scale):
                print(f"⚠️ 无效深度 ({u},{v})，跳过。")
                time.sleep(1)
                continue

            # 相机坐标
            X, Y, Z = compute_xyz(u, v, depth_raw, color_intr, depth_scale)
            x1, y1, z1, rx, ry, rz = robot.get_tcp_position()
            RoboX, RoboY, RoboZ = convert(X, Y, Z, x1, y1, z1, rx, ry, rz)

            print(f"像素点 ({u},{v}) -> 相机坐标 ({X:.4f}, {Y:.4f}, {Z:.4f}) m")
            print(f"机械臂基坐标: ({RoboX:.4f}, {RoboY:.4f}, {RoboZ:.4f}) m")

            # 显示“正在执行拧螺丝”提示
            exec_display = annotated.copy()
            cv2.putText(exec_display, "Executing screw operation...", (20, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            cv2.imshow("YOLO Detection", exec_display)
            cv2.waitKey(1)
            # 执行动作
            robot.plane_grasp([RoboX, RoboY, RoboZ],type)
            if type==0:
                print("✅ 拧螺丝完成。")
            
            elif type==1:
                print("✅ up螺丝完成。")
            
            

            # 执行完成，显示等待提示
            wait_display = annotated.copy()
            cv2.putText(wait_display, "Waiting 10s before next detection...", (20, 120),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
            cv2.imshow("YOLO Detection", wait_display)
            cv2.waitKey(1)

            # 等待10秒再恢复检测
            for i in range(10, 0, -1):
                print(f"⏳ 等待 {i} 秒后重新开始检测...", end="\r")
                time.sleep(1)

            print("\n🔁 继续检测中...\n")

        else:
            # 没检测到目标时显示实时画面
            cv2.putText(annotated, "Detecting screws...", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            cv2.imshow("YOLO Detection", annotated)

        # 允许手动退出
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("⏹️ 用户退出程序。")
            break

finally:
    pipeline.stop()
    cv2.destroyAllWindows()
    print("✅ 系统已停止。")
