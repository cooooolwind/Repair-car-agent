#!/usr/bin/env python
import math
import matplotlib.pyplot as plt
import numpy as np
import time
import cv2
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

# --------------- 标定参数配置 ---------------
ROBOT_IP = '10.5.5.100'  # 机器人IP
WORKSPACE_LIMITS = np.asarray([[0.2, 0.4], [0.4, 0.6], [0.05, 0.1]])  # 标定空间
CALIB_GRID_STEP = 0.05  # 网格步长（米）
CHECKERBOARD_OFFSET = [0.0, 0.087, 0.0]  # 棋盘格相对工具的偏移（浮点数）
TOOL_ORIENTATION = [-np.pi/2, 0.0, 0.0]  # 工具姿态（RPY弧度）
CHECKERBOARD_SIZE = (11, 8)  # 棋盘格内角点数量
# -------------------------------------------


def collect_calibration_data(robot):
    # # 初始化存储标定数据的列表
    measured_pts = []    # 机械臂坐标系下的点
    observed_pts = []    # 相机坐标系下的点
    observed_pix = []    # 像素坐标点

    # 生成3D标定网格
    grid_x = np.linspace(WORKSPACE_LIMITS[0,0], WORKSPACE_LIMITS[0,1],
                         int(1 + (WORKSPACE_LIMITS[0,1]-WORKSPACE_LIMITS[0,0])/CALIB_GRID_STEP))
    grid_y = np.linspace(WORKSPACE_LIMITS[1,0], WORKSPACE_LIMITS[1,1],
                         int(1 + (WORKSPACE_LIMITS[1,1]-WORKSPACE_LIMITS[1,0])/CALIB_GRID_STEP))
    grid_z = np.linspace(WORKSPACE_LIMITS[2,0], WORKSPACE_LIMITS[2,1],
                         int(1 + (WORKSPACE_LIMITS[2,1]-WORKSPACE_LIMITS[2,0])/CALIB_GRID_STEP))
    calib_grid_x, calib_grid_y, calib_grid_z = np.meshgrid(grid_x, grid_y, grid_z)
    calib_pts = np.vstack([calib_grid_x.ravel(), calib_grid_y.ravel(), calib_grid_z.ravel()]).T
    print(f"生成标定网格: {calib_pts.shape[0]} 个点")
    # num_calib_grid_pts = calib_grid_x.shape[0]*calib_grid_x.shape[1]*calib_grid_x.shape[2]

    # calib_grid_x.shape = (num_calib_grid_pts,1)
    # calib_grid_y.shape = (num_calib_grid_pts,1)
    # calib_grid_z.shape = (num_calib_grid_pts,1)
    # calib_grid_pts = np.concatenate((calib_grid_x, calib_grid_y, calib_grid_z), axis=1)

    # measured_pts = []
    # observed_pts = []
    # observed_pix = []

    # 修正：确保关节角度是原生 Python 浮点数列表
    home_joints_rad = [
        -math.pi,  # 关节1
        -math.pi / 2,  # 关节2
        math.pi / 2,  # 关节3
        0,  # 关节4
        math.pi / 2,  # 关节5
        math.pi  # 关节6
    ]
    home_joints_deg = [math.degrees(rad) for rad in home_joints_rad]  # 原生float列表
    # print("---------")
    # print(home_joints_deg)
    # print("---------")
    # 移动到初始姿态
    if not robot.move_j(home_joints_deg):
        print("初始姿态移动失败，退出采集")
        return None, None, None
    time.sleep(2)

    # 遍历网格点采集数据
    for i, tool_pos in enumerate(calib_pts):
        tool_config = list(tool_pos) + TOOL_ORIENTATION  # 位姿：[x,y,z,rx,ry,rz]
        print(f"\n处理点 {i+1}/{len(calib_pts)}: {tool_config[:3]}")

        # 移动到目标位姿（使用robot的move_l方法）
        if not robot.move_l(tool_config):
            print("跳过该点")
            continue
        time.sleep(2)  # 等待稳定

        # 获取相机数据（使用robot的get_camera_data方法）
        color_img, depth_img = robot.get_camera_data()
        if color_img is None or depth_img is None:
            print("相机数据获取失败，跳过")
            continue

        # 检测棋盘格角点
        gray_img = cv2.cvtColor(color_img, cv2.COLOR_RGB2GRAY)
        found, corners = cv2.findChessboardCorners(
            gray_img, CHECKERBOARD_SIZE, cv2.CALIB_CB_ADAPTIVE_THRESH
        )
        if not found:
            print("未检测到棋盘格，跳过")
            continue

        # 亚像素优化
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        corners_refined = cv2.cornerSubPix(gray_img, corners, (5,5), (-1,-1), criteria)

        # 动态计算中心角点（修复原固定索引问题）
        center_pix = np.mean(corners_refined.squeeze(), axis=0)
        distances = np.linalg.norm(corners_refined.squeeze() - center_pix, axis=1)
        center_idx = np.argmin(distances)
        corner_pix = np.round(corners_refined[center_idx, 0, :]).astype(int)

        # 优化深度值获取（取周围区域平均值）
        y, x = corner_pix[1], corner_pix[0]
        window = depth_img[max(0, y-2):min(y+3, depth_img.shape[0]),
                           max(0, x-2):min(x+3, depth_img.shape[1])]
        valid_depth = window[window > 0]
        if len(valid_depth) == 0:
            print("无有效深度值，跳过")
            continue
        z = np.mean(valid_depth)  # 平均深度

        # 计算相机坐标系3D坐标
        cam_intr = robot.cam_intrinsics
        x_cam = (corner_pix[0] - cam_intr[0,2]) * z / cam_intr[0,0]
        y_cam = (corner_pix[1] - cam_intr[1,2]) * z / cam_intr[1,1]

        # 保存数据
        observed_pts.append([float(x_cam), float(y_cam), float(z)])
        measured_pts.append(tool_pos + np.array(CHECKERBOARD_OFFSET))  # 机械臂点+偏移
        observed_pix.append(corner_pix)

        # 可视化
        vis_img = cv2.drawChessboardCorners(
            color_img, (1,1), corners_refined[center_idx:center_idx+1], found
        )
        cv2.imwrite(f"calib_{i:04d}.png", cv2.cvtColor(vis_img, cv2.COLOR_RGB2BGR))
        cv2.imshow("Calibration", cv2.cvtColor(vis_img, cv2.COLOR_RGB2BGR))
        cv2.waitKey(300)

    cv2.destroyAllWindows()
    return np.array(measured_pts), np.array(observed_pts), np.array(observed_pix)


def calibrate_hand_eye(measured_pts, observed_pts, observed_pix, robot):
    """计算相机与机械臂的坐标变换（逻辑不变）"""
    if len(measured_pts) < 3:
        raise ValueError("有效标定点数不足（至少3个）")
    depth_scale = robot.cam_depth_scale if hasattr(robot, 'cam_depth_scale') else 1.0
    print(f"使用相机深度缩放因子: {depth_scale}")

    # 刚性变换求解（SVD方法）
    def get_rigid_transform(A, B):
        N = A.shape[0]
        centroid_A = np.mean(A, axis=0)
        centroid_B = np.mean(B, axis=0)
        AA = A - centroid_A
        BB = B - centroid_B
        H = AA.T @ BB
        U, S, Vt = np.linalg.svd(H)
        R = Vt.T @ U.T
        if np.linalg.det(R) < 0:
            Vt[2,:] *= -1
            R = Vt.T @ U.T
        t = centroid_B - R @ centroid_A
        return R, t

    # 优化深度缩放因子
    world2camera = np.eye(4)
    def depth_scale_error(z_scale):
        z = observed_pts[:,2:] * float(z_scale)
        x = (observed_pix[:,[0]] - robot.cam_intrinsics[0,2]) * z / robot.cam_intrinsics[0,0]
        y = (observed_pix[:,[1]] - robot.cam_intrinsics[1,2]) * z / robot.cam_intrinsics[1,1]
        new_obs = np.hstack([x, y, z])
        R, t = get_rigid_transform(measured_pts, new_obs)
        world2camera[:3,:3] = R
        world2camera[:3,3] = t
        pred_obs = (R @ measured_pts.T).T + t
        return np.sqrt(np.mean(np.sum((pred_obs - new_obs)**2, axis=1)))

    # 求解最优深度缩放因子
    result = optimize.minimize(depth_scale_error, [1.0], method="Nelder-Mead")
    depth_scale = result.x[0]
    print(f"最优深度缩放因子: {depth_scale:.4f}")

    # 计算最终相机位姿
    depth_scale_error(depth_scale)
    camera_pose = np.linalg.inv(world2camera)  # 相机在机械臂坐标系下的位姿
    return camera_pose, depth_scale


def main():
    # 从jaka_robot导入Jaka_Robot类并初始化（关键修改）
    robot = Jaka_Robot(
        ip=ROBOT_IP,
        workspace_limits=WORKSPACE_LIMITS,
        is_use_robotiq85=False,  # 标定无需夹爪，可关闭
        is_use_camera=True
    )
    if not robot.connected:
        print("机器人连接失败，退出")
        return

    # 采集标定数据（复用封装的robot对象）
    measured_pts, observed_pts, observed_pix = collect_calibration_data(robot)
    if measured_pts is None:
        robot.disconnect()
        return

    # 执行标定
    try:
        camera_pose, depth_scale = calibrate_hand_eye(
            measured_pts, observed_pts, observed_pix, robot
        )
    except Exception as e:
        print(f"标定失败: {e}")
        robot.disconnect()
        return

    # 保存结果（统一路径到real/cam_pose，与jaka_robot中加载路径一致）
    np.savetxt('real/cam_pose/camera_pose.txt', camera_pose, delimiter=' ')
    np.savetxt('real/cam_pose/camera_depth_scale.txt', [depth_scale], delimiter=' ')
    print("\n标定结果已保存:")
    print("- 相机位姿: real/cam_pose/camera_pose.txt")
    print("- 深度缩放因子: real/cam_pose/camera_depth_scale.txt")

    # 可视化标定结果
    fig = plt.figure()
    ax = fig.add_subplot(111, projection="3d")
    ax.scatter(measured_pts[:,0], measured_pts[:,1], measured_pts[:,2], c="b", label="机械臂坐标")
    # 转换相机点到机械臂坐标系
    R, t = camera_pose[:3,:3], camera_pose[:3,3]
    obs_scaled = observed_pts.copy()
    obs_scaled[:,2] *= depth_scale
    obs_robot = (R @ obs_scaled.T).T + t
    ax.scatter(obs_robot[:,0], obs_robot[:,1], obs_robot[:,2], c="r", label="相机坐标(转换后)")
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_zlabel("Z (m)")
    ax.legend()
    plt.show()

    # 关闭资源
    robot.disconnect()


if __name__ == "__main__":
    main()
