import sys
import time
import numpy as np
import os
from scipy.spatial.transform import Rotation as R

# 获取当前文件所在目录 (jaka_screw/real)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# ----------------- 1. 尝试导入硬件库 -----------------
try:
    import pyrealsense2 as rs
    from ultralytics import YOLO
    try:
        from .jaka_Rotate_yc import JAKA_Robot
    except ImportError:
        sys.path.append(os.path.abspath(os.path.join(CURRENT_DIR, "../../")))
        from jaka_screw.real.jaka_Rotate_yc import JAKA_Robot

    LIBS_IMPORTED = True
except ImportError as e:
    print(f"⚠️ 依赖库导入失败，将强制使用模拟模式: {e}")
    LIBS_IMPORTED = False

# ----------------- 2. 机器人控制器类 -----------------
class ScrewRobotController:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ScrewRobotController, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if self.initialized: return
        
        self.use_simulation = False 

        if LIBS_IMPORTED:
            try:
                print("🔵 正在尝试连接硬件...")
                self._init_camera()
                self._init_robot()
                self._init_models()
                print("🟢 硬件初始化及归位成功！")
            except Exception as e:
                print(f"⚠️ 硬件连接失败: {e}")
                print("⚠️ 系统已自动切换至【模拟/调试模式】。")
                self.use_simulation = True
        else:
            self.use_simulation = True

        self.initialized = True

    def _init_camera(self):
        print("   -> 初始化相机...")
        self.W, self.H = 640, 480
        self.pipeline = rs.pipeline()
        self.config = rs.config()
        self.config.enable_stream(rs.stream.depth, self.W, self.H, rs.format.z16, 30)
        self.config.enable_stream(rs.stream.color, self.W, self.H, rs.format.bgr8, 30)
        self.profile = self.pipeline.start(self.config)
        
        self.align = rs.align(rs.stream.color)
        profile = self.profile.get_stream(rs.stream.color)
        self.intr = profile.as_video_stream_profile().get_intrinsics()
        self.depth_scale = self.profile.get_device().first_depth_sensor().get_depth_scale()
        print("   -> 相机就绪")

    def _init_robot(self):
        print("   -> 初始化机械臂...")
        self.robot = JAKA_Robot('10.5.5.100')
        
        # ✅ 复刻 test_yolo.py: 初始化时先移动到观测位置
        # 这一步非常重要，确保机械臂在相机的视野范围内，且姿态适合抓取
        print("   -> 正在移动至观测初始位 (move_j)...")
        test_pos = [95.982, 187.535, -152.559, 233.931, -267.333, 214.593]
        radians_list = [(angle * np.pi) / 180 for angle in test_pos]
        self.robot.move_j(radians_list)
        time.sleep(1) # 等待到位

        # ✅ 复刻 test_yolo.py: 手眼标定矩阵
        self.R_matrix = np.array([
            [-0.72960442,-0.47869273,-0.488396],
            [ 0.68372925,-0.52506026,-0.50678006],
            [-0.0138454,-0.70367961,0.71038251]
        ])
        self.T_vector = np.array([0.09459109,0.05475265,-0.02552082])
        print("   -> 机械臂就绪")

    def _init_models(self):
        print("   -> 加载YOLO模型...")
        # ✅ 复刻 test_yolo.py: 加载两个模型
        path_down = os.path.join(CURRENT_DIR, "best.pt") # 对应 model1 (0: down/拧紧)
        path_up = os.path.join(CURRENT_DIR, "hole2.pt")  # 对应 model2 (1: up/拧松)
        
        self.model_down = None
        self.model_up = None

        if os.path.exists(path_down):
            self.model_down = YOLO(path_down)
        else:
            print(f"      (警告: 找不到 {path_down})")
            
        if os.path.exists(path_up):
            self.model_up = YOLO(path_up)
        else:
             print(f"      (警告: 找不到 {path_up})")

    def _convert_coords(self, x, y, z, x1, y1, z1, rx, ry, rz):
        # ✅ 复刻 test_yolo.py: 坐标转换逻辑
        obj_camera = np.array([x, y, z])
        end_pose = np.array([x1, y1, z1, rx, ry, rz])
        T_cam_end = np.eye(4)
        T_cam_end[:3, :3] = self.R_matrix
        T_cam_end[:3, 3] = self.T_vector

        position = end_pose[:3]
        # 注意: test_yolo.py 用的是 'xyz' 欧拉角转换
        orientation = R.from_euler('xyz', end_pose[3:], degrees=False).as_matrix()
        
        T_base_end = np.eye(4)
        T_base_end[:3, :3] = orientation
        T_base_end[:3, 3] = position

        obj_cam_h = np.append(obj_camera, [1])
        obj_end_h = T_cam_end.dot(obj_cam_h)
        obj_base_h = T_base_end.dot(obj_end_h)
        return list(obj_base_h[:3])

    def _compute_xyz(self, u, v, depth_raw):
        Z = depth_raw * self.depth_scale
        X = (u - self.intr.ppx) * Z / self.intr.fx
        Y = (v - self.intr.ppy) * Z / self.intr.fy
        return X, Y, Z

    def execute_task(self, mode: str) -> str:
        if self.use_simulation:
            action = "拧松(Up)" if mode == '1' else "拧紧(Down)"
            time.sleep(2)
            return f"【模拟模式】执行完毕：{action} (未连接硬件)"

        target_mode = int(mode) # 0: down, 1: up
        # ✅ 复刻 test_yolo.py: 根据模式选择模型
        model = self.model_up if target_mode == 1 else self.model_down
        
        if model is None:
            return "错误：请求的模型文件未找到，无法执行。"

        print(f"🔍 开始寻找目标 (Mode: {target_mode})...")
        
        # 尝试20次（约2-3秒），模拟 test_yolo.py 的循环检测
        for i in range(20):
            try:
                frames = self.pipeline.wait_for_frames()
                aligned = self.align.process(frames)
                depth_frame = aligned.get_depth_frame()
                color_frame = aligned.get_color_frame()
                if not depth_frame or not color_frame: continue
                
                color_img = np.asanyarray(color_frame.get_data())
                depth_img = np.asanyarray(depth_frame.get_data())
                
                results = model(color_img, verbose=False)
                
                if len(results[0].boxes) > 0:
                    best_box = max(results[0].boxes, key=lambda b: float(b.conf[0]))
                    conf = float(best_box.conf[0])
                    
                    # 这里的阈值可以根据实际情况调整，test_yolo中没显式写阈值，但默认通常较高
                    if conf < 0.4: continue 

                    x1, y1, x2, y2 = best_box.xyxy[0].cpu().numpy()
                    u, v = int((x1 + x2) / 2), int((y1 + y2) / 2)
                    
                    depth_raw = int(depth_img[v, u])
                    
                    # ✅ 复刻 test_yolo.py: 深度校验
                    z_metric = depth_raw * self.depth_scale
                    if z_metric < 0.001 or z_metric > 3.0: 
                        continue 

                    # 1. 计算相机坐标
                    X, Y, Z = self._compute_xyz(u, v, depth_raw)
                    
                    # 2. 获取当前机械臂位姿
                    tcp_pos = self.robot.get_tcp_position()
                    rx_c, ry_c, rz_c = tcp_pos[0], tcp_pos[1], tcp_pos[2]
                    rx, ry, rz = tcp_pos[3], tcp_pos[4], tcp_pos[5]
                    
                    # 3. 转换到基坐标
                    RoboX, RoboY, RoboZ = self._convert_coords(X, Y, Z, rx_c, ry_c, rz_c, rx, ry, rz)
                    
                    print(f"📍 目标锁定: 像素({u},{v}) -> 机械臂坐标 ({RoboX:.4f}, {RoboY:.4f}, {RoboZ:.4f})")
                    
                    # ✅ 复刻 test_yolo.py: 直接调用 plane_grasp
                    # 注意：如果之前只动爪子，可能是因为初始位置不对。
                    # 现在我们在 _init_robot 里加了 move_j，应该能解决这个问题。
                    print("🚀 执行 plane_grasp ...")
                    self.robot.plane_grasp([RoboX, RoboY, RoboZ], target_mode)
                    
                    action_name = "拧松(Up)" if target_mode == 1 else "拧紧(Down)"
                    return f"成功检测到螺丝(conf={conf:.2f})，并在坐标({RoboX:.3f}, {RoboY:.3f}, {RoboZ:.3f})完成了{action_name}动作。"
            except Exception as e:
                print(f"执行循环中出错: {e}")
                continue
            
            time.sleep(0.1)

        return "未检测到有效螺丝目标，请检查视野。"

robot_ctrl = ScrewRobotController()

def Arm_move(type: str = "0") -> str:
    try:
        return robot_ctrl.execute_task(type)
    except Exception as e:
        return f"执行出错: {str(e)}"