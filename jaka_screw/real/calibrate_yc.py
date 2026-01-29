#!/usr/bin/env python

import matplotlib.pyplot as plt
import numpy as np
import time
import cv2
import sys
sys.path.append('//home/robot/GRCNN')
sys.path.append('//home/robot/GRCNN/real')
from jaka_robot_yc import JAKA_Robot  # 确保文件名正确
from scipy import optimize
from mpl_toolkits.mplot3d import Axes3D

# 配置参数
tcp_host_ip = '10.5.5.100'
# workspace_limits = np.asarray([[0.2, 0.4], [0.4,0.6], [0.05, 0.1]])
workspace_limits = np.asarray([[0.35,0.4], [0.08,0.13], [0.41,0.46]])
calib_grid_step = 0.05
checkerboard_offset_from_tool = [0, 0.067, 0]  # 工具坐标系到标定板的偏移
test_orientation = [-86.436, -44.422, -59.779]
tool_orientation = [(angle * np.pi) / 180 for angle in test_orientation]  # 固定工具方向

# 创建3D标定网格
gridspace_x = np.linspace(workspace_limits[0][0], workspace_limits[0][1], 
                          int(1 + (workspace_limits[0][1] - workspace_limits[0][0])/calib_grid_step))
gridspace_y = np.linspace(workspace_limits[1][0], workspace_limits[1][1], 
                          int(1 + (workspace_limits[1][1] - workspace_limits[1][0])/calib_grid_step))
gridspace_z = np.linspace(workspace_limits[2][0], workspace_limits[2][1], 
                          int(1 + (workspace_limits[2][1] - workspace_limits[2][0])/calib_grid_step))

calib_grid_x, calib_grid_y, calib_grid_z = np.meshgrid(gridspace_x, gridspace_y, gridspace_z)     ####np.meshgrid() 函数生成一个三维网格坐标系
                                                                                                  ###返回三个3D数组，分别包含所有点的X、Y、Z坐标
num_calib_grid_pts = calib_grid_x.shape[0]*calib_grid_x.shape[1]*calib_grid_x.shape[2]  ##calib_grid_x.size 返回数组中元素的总数 5*4*2=40
calib_grid_x.shape = (num_calib_grid_pts,1)
calib_grid_y.shape = (num_calib_grid_pts,1)
calib_grid_z.shape = (num_calib_grid_pts,1)
calib_grid_pts = np.concatenate((calib_grid_x, calib_grid_y, calib_grid_z), axis=1)

measured_pts = []
observed_pts = []
observed_pix = []

# 连接机器人
print('Connecting to JAKA robot...')
robot = JAKA_Robot(tcp_host_ip)

# 移动到初始位置
print('Moving to home position...')
test_pos = [206.623, 61.893, 143.320, -27.771, -83.912, -44.206]
radians_list = [(angle * np.pi) / 180 for angle in test_pos]
robot.move_j(radians_list)

# 采集标定数据
print('Collecting calibration data...')
for idx in range(num_calib_grid_pts):
    tool_position = calib_grid_pts[idx, :]
    print(f"Moving to point {idx+1}/{num_calib_grid_pts}: {tool_position}")
    
    # 创建完整的6元素工具位姿 [x, y, z, rx, ry, rz]
    tool_config = np.hstack([tool_position, tool_orientation])
    # print("------------------")
    # print(tool_config.size)
    # print("------------------")
    # 使用安全的速度和加速度
    robot.move_j_p(tool_config,k_acc=0.5, k_vel=0.5)
    time.sleep(1.0)  # 稳定时间
    
    # 检测标定板
    checkerboard_size = (5, 5)
    camera_color_img, camera_depth_img = robot.get_camera_data()
    bgr_color_data = cv2.cvtColor(camera_color_img, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(bgr_color_data, cv2.COLOR_BGR2GRAY)
    
    # 查找棋盘格角点
    found, corners = cv2.findChessboardCorners(gray, checkerboard_size, None, cv2.CALIB_CB_ADAPTIVE_THRESH)

    print(found)
    if found:
        # 精确定位角点alibration complete!

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        corners_refined = cv2.cornerSubPix(gray, corners, (5, 5), (-1, -1), criteria)  ##corners_refined - 精炼后的角点坐标
        
        # 获取中心点
        center_pix = np.round(corners_refined[12,0,:]).astype(int)
        
        z = camera_depth_img[center_pix[1]][center_pix[0]]
        x = np.multiply(center_pix[0]-robot.cam_intrinsics[0][2],z/robot.cam_intrinsics[0][0])
        y = np.multiply(center_pix[1]-robot.cam_intrinsics[1][2],z/robot.cam_intrinsics[1][1])
        
        # 存储数据
        measured_pt = tool_position + checkerboard_offset_from_tool
        measured_pts.append(measured_pt) # 机械臂坐标系下的点
        observed_pts.append([x, y, z])  # 相机坐标系下的点
        observed_pix.append(center_pix)  # 像素坐标点
        
        # 可视化
        vis = cv2.drawChessboardCorners(bgr_color_data, (1,1), corners_refined[12,:,:], found)
        cv2.imshow('Calibration', vis)
        cv2.waitKey(500)
    else:
        print(f"Checkerboard not found at position {idx}")

cv2.destroyAllWindows()

# 转换为numpy数组
measured_pts = np.asarray(measured_pts)
observed_pts = np.asarray(observed_pts)
observed_pix = np.asarray(observed_pix)
world2camera = np.eye(4)

# 标定计算
def get_rigid_transform(A, B):
    assert len(A) == len(B)
    N = A.shape[0] # Total points
    centroid_A = np.mean(A, axis=0)
    centroid_B = np.mean(B, axis=0)
    AA = A - np.tile(centroid_A, (N, 1)) # Centre the points
    BB = B - np.tile(centroid_B, (N, 1))
    H = np.dot(np.transpose(AA), BB) # Dot is matrix multiplication for array
    U, S, Vt = np.linalg.svd(H)
    R = np.dot(Vt.T, U.T)
    if np.linalg.det(R) < 0: # Special reflection case
       Vt[2,:] *= -1
       R = np.dot(Vt.T, U.T)
    t = np.dot(-R, centroid_A.T) + centroid_B.T
    return R, t

# def calibrate_camera():
#     """执行相机标定"""
#     # 计算初始变换
#     R, t = get_rigid_transform(measured_pts, observed_pts)
    
#     # 优化Z轴缩放
#     def error_func(z_scale):
#         scaled_observed = observed_pts.copy()
#         scaled_observed[:, 2] *= z_scale[0]
#         R, t = get_rigid_transform(measured_pts, scaled_observed)
#         transformed = (R @ measured_pts.T).T + t
#         return np.linalg.norm(transformed - scaled_observed, axis=1)
#     res = optimize.least_squares(error_func, [1.0], method='lm')
#     z_scale_opt = res.x[0]
    
#     # 使用优化后的参数计算最终变换
#     scaled_observed = observed_pts.copy()
#     scaled_observed[:, 2] *= z_scale_opt
#     R, t = get_rigid_transform(measured_pts, scaled_observed)
    
#     # 构建变换矩阵
#     camera_pose = np.eye(4)
#     camera_pose[:3, :3] = R
#     camera_pose[:3, 3] = t
    
#     return camera_pose, z_scale_opt

def get_rigid_transform_error(z_scale):
    global measured_pts, observed_pts, observed_pix, world2camera, camera

    # Apply z offset and compute new observed points using camera intrinsics
    observed_z = observed_pts[:,2:] * z_scale
    observed_x = np.multiply(observed_pix[:,[0]]-robot.cam_intrinsics[0][2],observed_z/robot.cam_intrinsics[0][0])
    observed_y = np.multiply(observed_pix[:,[1]]-robot.cam_intrinsics[1][2],observed_z/robot.cam_intrinsics[1][1])
    new_observed_pts = np.concatenate((observed_x, observed_y, observed_z), axis=1)

    # Estimate rigid transform between measured points and new observed points
    R, t = get_rigid_transform(np.asarray(measured_pts), np.asarray(new_observed_pts))
    t.shape = (3,1)
    world2camera = np.concatenate((np.concatenate((R, t), axis=1),np.array([[0, 0, 0, 1]])), axis=0)

    # Compute rigid transform error
    registered_pts = np.dot(R,np.transpose(measured_pts)) + np.tile(t,(1,measured_pts.shape[0]))
    error = np.transpose(registered_pts) - new_observed_pts
    error = np.sum(np.multiply(error,error))
    rmse = np.sqrt(error/measured_pts.shape[0])
    return rmse

# 执行标定
print('Calibrating...')
z_scale_init = 1
optim_result = optimize.minimize(get_rigid_transform_error, np.asarray(z_scale_init), method='Nelder-Mead')
camera_depth_offset = optim_result.x
# print("----------------")
# print(camera_pose)
# print("----------------")

# 保存结果
print("Saving calibration results...")
np.savetxt('/home/robot/GRCNN/real/cam_pose/camera_depth_scale_yc.txt', camera_depth_offset, delimiter=' ')

get_rigid_transform_error(camera_depth_offset)
camera_pose = np.linalg.inv(world2camera)
np.savetxt('/home/robot/GRCNN/real/cam_pose/camera_pose_yc.txt', camera_pose, delimiter=' ')


print(f"Calibration complete!\nCamera pose:\n{camera_pose}\nDepth scale: {camera_depth_offset}")







# DEBUG CODE -----------------------------------------------------------------------------------

# np.savetxt('/home/robot/GRCNN/real/cam_pose/measured_pts.txt', np.asarray(measured_pts), delimiter=' ')
# np.savetxt('/home/robot/GRCNN/real/cam_pose/observed_pts.txt', np.asarray(observed_pts), delimiter=' ')
# np.savetxt('/home/robot/GRCNN/real/cam_pose/observed_pix.txt', np.asarray(observed_pix), delimiter=' ')
# measured_pts = np.loadtxt('/home/robot/GRCNN/real/cam_pose/measured_pts.txt', delimiter=' ')
# observed_pts = np.loadtxt('/home/robot/GRCNN/real/cam_pose/observed_pts.txt', delimiter=' ')
# observed_pix = np.loadtxt('/home/robot/GRCNN/real/cam_pose/observed_pix.txt', delimiter=' ')

# fig = plt.figure()
# ax = fig.add_subplot(111, projection='3d')
# ax.scatter(measured_pts[:,0],measured_pts[:,1],measured_pts[:,2], c='blue')

# print(camera_depth_offset)
# R, t = get_rigid_transform(np.asarray(measured_pts), np.asarray(observed_pts))
# t.shape = (3,1)
# camera_pose = np.concatenate((np.concatenate((R, t), axis=1),np.array([[0, 0, 0, 1]])), axis=0)
# camera2robot = np.linalg.inv(camera_pose)
# t_observed_pts = np.transpose(np.dot(camera2robot[0:3,0:3],np.transpose(observed_pts)) + np.tile(camera2robot[0:3,3:],(1,observed_pts.shape[0])))

# ax.scatter(t_observed_pts[:,0],t_observed_pts[:,1],t_observed_pts[:,2], c='red')

# new_observed_pts = observed_pts.copy()
# new_observed_pts[:,2] = new_observed_pts[:,2] * camera_depth_offset[0]
# R, t = get_rigid_transform(np.asarray(measured_pts), np.asarray(new_observed_pts))
# t.shape = (3,1)
# camera_pose = np.concatenate((np.concatenate((R, t), axis=1),np.array([[0, 0, 0, 1]])), axis=0)
# camera2robot = np.linalg.inv(camera_pose)
# t_new_observed_pts = np.transpose(np.dot(camera2robot[0:3,0:3],np.transpose(new_observed_pts)) + np.tile(camera2robot[0:3,3:],(1,new_observed_pts.shape[0])))

# ax.scatter(t_new_observed_pts[:,0],t_new_observed_pts[:,1],t_new_observed_pts[:,2], c='green')

# plt.show()