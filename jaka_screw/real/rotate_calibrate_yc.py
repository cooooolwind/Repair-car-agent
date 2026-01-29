#!/usr/bin/env python

import matplotlib.pyplot as plt
import numpy as np
import time
import cv2
import sys
sys.path.append('//home/robot/GRCNN')
sys.path.append('//home/robot/GRCNN/real')
from jaka_Rotate_yc import JAKA_Robot  # 确保文件名正确
from scipy import optimize
from mpl_toolkits.mplot3d import Axes3D

# 配置参数
tcp_host_ip = '10.5.5.100'
# workspace_limits = np.asarray([[0.2, 0.4], [0.4,0.6], [0.05, 0.1]])
workspace_limits = np.asarray([[0.38,0.43], [0.05,0.15], [0.15,0.20]])
calib_grid_step = 0.05
# 眼在手上：标定板固定在工作台，不需要工具到标定板的偏移
# checkerboard_offset_from_tool = [0, 0, 0]  # 工具坐标系到标定板的偏移

# 重要：定义标定板在工作台坐标系下的固定位置（眼在手上配置的关键参数）
checkerboard_in_world = [0.55, 0.12, -0.086]  # 标定板在工作台坐标系下的固定坐标 [x, y, z] (单位：米)
test_orientation = [165.166, -15.388, 48.938]
tool_orientation = [(angle * np.pi) / 180 for angle in test_orientation]  # 固定工具方向

# 创建3D标定网格 - 机械臂末端移动的路径点
gridspace_x = np.linspace(workspace_limits[0][0], workspace_limits[0][1], 
                          int(1 + (workspace_limits[0][1] - workspace_limits[0][0])/calib_grid_step))
gridspace_y = np.linspace(workspace_limits[1][0], workspace_limits[1][1], 
                          int(1 + (workspace_limits[1][1] - workspace_limits[1][0])/calib_grid_step))
gridspace_z = np.linspace(workspace_limits[2][0], workspace_limits[2][1], 
                          int(1 + (workspace_limits[2][1] - workspace_limits[2][0])/calib_grid_step))

calib_grid_x, calib_grid_y, calib_grid_z = np.meshgrid(gridspace_x, gridspace_y, gridspace_z)     
num_calib_grid_pts = calib_grid_x.shape[0]*calib_grid_x.shape[1]*calib_grid_x.shape[2]  
calib_grid_x.shape = (num_calib_grid_pts,1)
calib_grid_y.shape = (num_calib_grid_pts,1)
calib_grid_z.shape = (num_calib_grid_pts,1)
calib_grid_pts = np.concatenate((calib_grid_x, calib_grid_y, calib_grid_z), axis=1)

measured_pts = []  # 标定板在机械臂坐标系下的位置
observed_pts = []  # 标定板在相机坐标系下的位置
observed_pix = []  # 标定板中心点的像素坐标

# 连接机器人
print('Connecting to JAKA robot...')
robot = JAKA_Robot(tcp_host_ip)

# 移动到初始位置
print('Moving to home position...')                                 
test_pos = [-0.068, 95.352, -137.317, 153.165, 91.471, 223.285]
radians_list = [(angle * np.pi) / 180 for angle in test_pos]
robot.move_j(radians_list)

# 采集标定数据
print('Collecting calibration data...')
for idx in range(num_calib_grid_pts):
    tool_position = calib_grid_pts[idx, :]  # 机械臂末端在工作台坐标系下的目标位置
    print(f"Moving to point {idx+1}/{num_calib_grid_pts}: {tool_position}")
    
    # 创建完整的6元素工具位姿 [x, y, z, rx, ry, rz]
    tool_config = np.hstack([tool_position, tool_orientation])
    
    # 使用安全的速度和加速度移动机械臂
    robot.move_j_p(tool_config, k_acc=0.5, k_vel=0.5)
    time.sleep(1.0)  # 稳定时间，确保机械臂停止并图像稳定
    
    # 检测标定板
    checkerboard_size = (5, 5)
    camera_color_img, camera_depth_img = robot.get_camera_data()
    bgr_color_data = cv2.cvtColor(camera_color_img, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(bgr_color_data, cv2.COLOR_BGR2GRAY)
    
    # 查找棋盘格角点
    found, corners = cv2.findChessboardCorners(gray, checkerboard_size, None, cv2.CALIB_CB_ADAPTIVE_THRESH)

    print(f"Checkerboard found: {found}")
    if found:
        # 精确定位角点
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        corners_refined = cv2.cornerSubPix(gray, corners, (5, 5), (-1, -1), criteria)  # 精炼后的角点坐标
        
        # 获取棋盘格中心点（5x5棋盘格的中心是第12个角点，索引为12）
        center_pix = np.round(corners_refined[12,0,:]).astype(int)
        
        # 从深度图获取标定板中心点的深度值
        z = camera_depth_img[center_pix[1]][center_pix[0]]
        # 通过相机内参将像素坐标转换为相机坐标系下的3D坐标
        x = np.multiply(center_pix[0]-robot.cam_intrinsics[0][2], z/robot.cam_intrinsics[0][0])
        y = np.multiply(center_pix[1]-robot.cam_intrinsics[1][2], z/robot.cam_intrinsics[1][1])
        
        # 计算标定板在机械臂坐标系下的位置
        # 眼在手上配置：标定板位置 = 标定板在工作台坐标系下的固定位置 - 机械臂末端在工作台坐标系下的位置
        # measured_pt = np.array(checkerboard_in_world) - tool_position

        gripper_pose = robot.get_pose()  # 获取机械臂位姿 T_base^gripper
        base_to_gripper = np.linalg.inv(gripper_pose)  # T_gripper^base
        world_point = np.array([checkerboard_in_world[0], checkerboard_in_world[1], checkerboard_in_world[2], 1])
        gripper_point = np.dot(base_to_gripper, world_point)
        measured_pt = gripper_point[:3]  # 标定板在机械臂坐标系下的坐标

        # measured_pt = np.array(checkerboard_in_world)
        measured_pts.append(measured_pt)  # 机械臂坐标系下的标定板位置
        observed_pts.append([x, y, z])    # 相机坐标系下的标定板位置
        observed_pix.append(center_pix)   # 标定板中心点的像素坐标
        
        # 可视化检测结果
        vis = cv2.drawChessboardCorners(bgr_color_data, (5,5), corners_refined, found)
        cv2.imshow('Calibration', vis)
        cv2.waitKey(500)
    else:
        print(f"Checkerboard not found at position {idx}, skipping...")

cv2.destroyAllWindows()

# 转换为numpy数组
measured_pts = np.asarray(measured_pts)
observed_pts = np.asarray(observed_pts)
observed_pix = np.asarray(observed_pix)
world2camera = np.eye(4)

# 标定计算 - 计算两个点集之间的刚性变换
def get_rigid_transform(A, B):
    """
    计算点集A到点集B的刚性变换（旋转R和平移t）
    A: 机械臂坐标系下的点（标定板位置）
    B: 相机坐标系下的点（标定板位置）
    返回: R(旋转矩阵), t(平移向量)
    """
    assert len(A) == len(B)
    N = A.shape[0] # 点的数量
    centroid_A = np.mean(A, axis=0)  # A的质心
    centroid_B = np.mean(B, axis=0)  # B的质心
    AA = A - np.tile(centroid_A, (N, 1)) # 将A的质心移到原点
    BB = B - np.tile(centroid_B, (N, 1)) # 将B的质心移到原点
    H = np.dot(np.transpose(AA), BB) # 协方差矩阵
    U, S, Vt = np.linalg.svd(H)      # SVD分解
    R = np.dot(Vt.T, U.T)            # 计算旋转矩阵
    if np.linalg.det(R) < 0:         # 处理反射情况
       Vt[2,:] *= -1
       R = np.dot(Vt.T, U.T)
    t = np.dot(-R, centroid_A.T) + centroid_B.T  # 计算平移向量
    return R, t

def get_rigid_transform_error(z_scale):
    """
    计算刚性变换误差，用于优化深度缩放因子
    z_scale: 深度缩放因子
    """
    global measured_pts, observed_pts, observed_pix, world2camera

    # 应用深度缩放并使用相机内参计算新的观测点
    observed_z = observed_pts[:,2:] * z_scale
    observed_x = np.multiply(observed_pix[:,[0]]-robot.cam_intrinsics[0][2], observed_z/robot.cam_intrinsics[0][0])
    observed_y = np.multiply(observed_pix[:,[1]]-robot.cam_intrinsics[1][2], observed_z/robot.cam_intrinsics[1][1])
    new_observed_pts = np.concatenate((observed_x, observed_y, observed_z), axis=1)

    # 计算机械臂坐标系下的点到相机坐标系下点的刚性变换
    R, t = get_rigid_transform(np.asarray(measured_pts), np.asarray(new_observed_pts))
    t.shape = (3,1)
    # 构建4x4变换矩阵（从机械臂坐标系到相机坐标系）
    world2camera = np.concatenate((np.concatenate((R, t), axis=1), np.array([[0, 0, 0, 1]])), axis=0)

    # 计算变换误差（RMSE）
    registered_pts = np.dot(R, np.transpose(measured_pts)) + np.tile(t, (1, measured_pts.shape[0]))
    error = np.transpose(registered_pts) - new_observed_pts
    error = np.sum(np.multiply(error, error))
    rmse = np.sqrt(error/measured_pts.shape[0])
    return rmse

# 执行标定 - 优化深度缩放因子
print('Calibrating...')
z_scale_init = 1
optim_result = optimize.minimize(get_rigid_transform_error, np.asarray(z_scale_init), method='Nelder-Mead')
camera_depth_offset = optim_result.x

# 保存标定结果
print("Saving calibration results...")
np.savetxt('/home/yc1/robot/GRCNN/real/cam_pose/camera_depth_scale_yc.txt', camera_depth_offset, delimiter=' ')

# 用优化后的深度缩放因子重新计算变换矩阵
get_rigid_transform_error(camera_depth_offset)

# 眼在手上配置：world2camera就是相机相对于机械臂末端的变换矩阵（T_gripper^cam）
# 不需要取逆，因为我们要找的是相机在机械臂坐标系下的位姿
camera_pose = world2camera # T_gripper^cam（相机相对于机械臂末端的位姿）

np.savetxt('/home/yc1/robot/GRCNN/real/cam_pose/camera_pose_yc.txt', camera_pose, delimiter=' ')

print(f"Calibration complete!\nCamera pose:\n{camera_pose}\nDepth scale: {camera_depth_offset}")

# # DEBUG CODE -----------------------------------------------------------------------------------
# # 保存调试数据
# np.savetxt('/home/yc1/robot/GRCNN/real/cam_pose/measured_pts.txt', np.asarray(measured_pts), delimiter=' ')
# np.savetxt('/home/yc1/robot/GRCNN/real/cam_pose/observed_pts.txt', np.asarray(observed_pts), delimiter=' ')
# np.savetxt('/home/yc1/robot/GRCNN/real/cam_pose/observed_pix.txt', np.asarray(observed_pix), delimiter=' ')

# # 加载调试数据（用于验证）
# measured_pts = np.loadtxt('/home/yc1/robot/GRCNN/real/cam_pose/measured_pts.txt', delimiter=' ')
# observed_pts = np.loadtxt('/home/yc1/robot/GRCNN/real/cam_pose/observed_pts.txt', delimiter=' ')
# observed_pix = np.loadtxt('/home/yc1/robot/GRCNN/real/cam_pose/observed_pix.txt', delimiter=' ')

# # 3D可视化验证结果
# fig = plt.figure(figsize=(12, 9))
# ax = fig.add_subplot(111, projection='3d')

# # 绘制标定板在机械臂坐标系下的位置（蓝色）
# ax.scatter(measured_pts[:,0], measured_pts[:,1], measured_pts[:,2], c='blue', label='Calibration board in gripper frame', s=50)

# # 使用未优化的深度缩放转换相机坐标系下的点到机械臂坐标系（红色）
# R, t = get_rigid_transform(np.asarray(measured_pts), np.asarray(observed_pts))
# t.shape = (3,1)
# camera_pose_temp = np.concatenate((np.concatenate((R, t), axis=1), np.array([[0, 0, 0, 1]])), axis=0)
# camera2gripper = np.linalg.inv(camera_pose_temp)  # 从相机到机械臂的变换
# t_observed_pts = np.transpose(np.dot(camera2gripper[0:3,0:3], np.transpose(observed_pts)) + np.tile(camera2gripper[0:3,3:], (1, observed_pts.shape[0])))

# ax.scatter(t_observed_pts[:,0], t_observed_pts[:,1], t_observed_pts[:,2], c='red', label='Observed points (no depth scale)', s=30)

# # 使用优化后的深度缩放转换（绿色）
# new_observed_pts = observed_pts.copy()
# new_observed_pts[:,2] = new_observed_pts[:,2] * camera_depth_offset[0]
# R, t = get_rigid_transform(np.asarray(measured_pts), np.asarray(new_observed_pts))
# t.shape = (3,1)
# camera_pose_temp = np.concatenate((np.concatenate((R, t), axis=1), np.array([[0, 0, 0, 1]])), axis=0)
# camera2gripper = np.linalg.inv(camera_pose_temp)
# t_new_observed_pts = np.transpose(np.dot(camera2gripper[0:3,0:3], np.transpose(new_observed_pts)) + np.tile(camera2gripper[0:3,3:], (1, new_observed_pts.shape[0])))

# ax.scatter(t_new_observed_pts[:,0], t_new_observed_pts[:,1], t_new_observed_pts[:,2], c='green', label='Observed points (with depth scale)', s=30)

# ax.set_xlabel('X (m)')
# ax.set_ylabel('Y (m)')
# ax.set_zlabel('Z (m)')
# ax.set_title('Hand-Eye Calibration Results (Eye-in-Hand)')
# ax.legend()
# plt.show()



