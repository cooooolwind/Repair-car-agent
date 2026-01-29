import time
import copy
import numpy as np
import sys
sys.path.append('/home/nvidia/robot/jaka')
import jkrc
sys.path.append('/home/nvidia/robot/jaka_screw')
from real.realsenseD435 import Camera
import glob
# from real.dh_modbus_gripper import dh_modbus_gripper
from time import sleep
import serial
import struct
import threading
import math


class JAKA_Robot:
    def __init__(self, ip="10.5.5.100", workspace_limits=None,is_use_dh_gripper=True, is_use_camera=True):
        if workspace_limits is None:
            workspace_limits = [[-0.650, -0.189], [-0.574, 0.456], [0.44, 0.704]]
        self.workspace_limits = workspace_limits
        self.ip = ip
        self.is_use_dh_gripper = is_use_dh_gripper  # 修改参数名
        self.is_use_camera = is_use_camera
        
        # JAKA机器人连接        self.socket.connect((hostname, port))
        self.robot = jkrc.RC(ip)
        ret = self.robot.login()
        if ret[0] != 0:
            raise ConnectionError(f"Failed to login to JAKA robot at {ip}")
        
        # 机器人初始化
        self.robot.power_on()
        self.robot.enable_robot()

        # #  大寰夹爪配置
        # if self.is_use_dh_gripper:
        #     self.gripper = dh_modbus_gripper()
        #     print("连接夹爪...")
        #     self.port='/dev/ttyUSB2'   ###连接的串口
        #     self.baudrate=115200
        #     self.gripper.open(self.port, self.baudrate)
        #     self.gripper.Initialization()
        #     print("夹爪初始化中...")
        #     init_state = 0
        #     while init_state != 1:
        #         init_state = self.gripper.GetInitState()
        #         time.sleep(0.2)
            # print("夹爪初始化完成!")
        
        # 相机初始化
        # if(self.is_use_camera):
        #     self.camera = Camera()
        #     self.cam_intrinsics = self.camera.intrinsics  # 3x3相机内参矩阵
        
        # 运动参数
        self.joint_acc = 1.4    # rad/s²
        self.joint_vel = 1.05   # rad/s
        self.tool_acc = 0.5     # m/s²
        self.tool_vel = 0.2     # m/s
        
        # # 从文件加载相机位姿和深度比例
        # self.cam_pose = np.loadtxt('/home/yc1/robot/GRCNN/real/cam_pose/camera_pose_yc.txt', delimiter=' ')
        # self.cam_depth_scale = np.loadtxt('/home/yc1/robot/GRCNN/real/cam_pose/camera_depth_scale_yc.txt', delimiter=' ')
        
        # 默认关节配置
        self.home_joint_config = [0.0, -np.pi/2, 0, -np.pi/2, 0, 0]

    def move_j(self, joint_configuration, k_acc=10, k_vel=10):
        """关节空间运动"""
        self.robot.joint_move_extend(
            joint_configuration, 
            0,  # 绝对运动
            True,  # 阻塞模式
            k_vel * self.joint_vel,
            k_acc * self.joint_acc,
            0.01  # 容差
        )
        time.sleep(0.5)

    def move_j_p(self, tool_configuration, k_acc=10, k_vel=10):
        """笛卡尔空间运动"""
        # 将米转换为毫米
        # pos_mm = [x * 1000 for x in tool_configuration[:3]]
        # rot_rad = tool_configuration[3:6]
        # # print("--------")
        # # print(pos_mm + rot_rad)
        # # print(rot_rad)
        # # print("--------")
        
        # full_pose = pos_mm + rot_rad
        # full_pose = [
        # float(tool_configuration[0]) * 1000,  # x mm
        # float(tool_configuration[1]) * 1000,  # y mm
        # float(tool_configuration[2]) * 1000,  # z mm
        # float(tool_configuration[3]),         # rx rad
        # float(tool_configuration[4]),         # ry rad
        # float(tool_configuration[5])          # rz rad
        # ]
        full_pose = [
        float(tool_configuration[0])*1000,  # x mm
        float(tool_configuration[1])*1000,  # y mm
        float(tool_configuration[2])*1000,  # z mm
        float(tool_configuration[3]),         # rx rad
        float(tool_configuration[4]),         # ry rad
        float(tool_configuration[5])          # rz rad
        ]

        self.robot.linear_move_extend(
            full_pose,
            0,  # 绝对运动
            True,  # 阻塞模式
            k_vel * self.tool_vel * 1000,  # 转为mm/s
            k_acc * self.tool_acc * 1000,   # 转为mm/s²
            0.1  # 容差(mm)
        )
        time.sleep(0.5)

    def move_c(self, pose_via, tool_configuration, k_acc=5, k_vel=5, mode=0):
        """执行圆弧运动"""
        # 将米转换为毫米（位置部分）
        via_pos_mm = [x * 1000 for x in pose_via[:3]]
        via_rot_rad = pose_via[3:]
        tool_pos_mm = [x * 1000 for x in tool_configuration[:3]]
        tool_rot_rad = tool_configuration[3:]
        
        via_pose = via_pos_mm + via_rot_rad
        end_pose = tool_pos_mm + tool_rot_rad
        
        # 计算实际加速度和速度（转换为mm/s²和mm/s）
        acc = k_acc * self.tool_acc * 1000
        vel = k_vel * self.tool_vel * 1000
        
        # 调用JAKA SDK的圆弧运动接口
        self.robot.circular_move_extend(
            end_pose,        # 终点位姿
            via_pose,        # 中间点位姿
            mode,            # 运动模式：0-绝对运动，1-增量运动，2-连续运动
            True,            # 阻塞模式
            vel,             # 速度 (mm/s)
            acc,             # 加速度 (mm/s²)
            0.1,             # 容差 (mm)
            None,            # 优化条件（可选）
            5                # 圆弧圈数（默认5）
        )
        time.sleep(0.5)

    def get_camera_data(self):
        """获取相机数据"""
        return self.camera.get_data()

    def go_home(self):
        """返回初始位置"""
        self.move_j(self.home_joint_config)

    def get_joint_position(self):
        """获取当前关节角度"""
        return self.robot.get_joint_position()[1]

    def get_tcp_position(self):
        """获取当前TCP位姿"""
        pos = self.robot.get_tcp_position()[1]
        return [x / 1000 for x in pos[:3]] + pos[3:]  # 毫米转米
    
    def get_pose(self):
        tcp_pos = self.robot.get_tcp_position()[1]
        """
        将TCP位姿转换为齐次变换矩阵 T_base^gripper
        tcp_pos: (x, y, z, rx, ry, rz) 单位：毫米，弧度
        """
        x, y, z, rx, ry, rz = tcp_pos
        
        # 将毫米转换为米
        x, y, z = x/1000, y/1000, z/1000
        
            
         # 构建旋转矩阵（使用X-Y-Z欧拉角顺序，也称为ZYX外旋）
        # R = Rz(rz) * Ry(ry) * Rx(rx)
        rpy = self.robot.rpy_to_rot_matrix([rx,ry,rz])
        R = rpy[1]
        
        # 齐次变换矩阵T_base^gripper
        T_base_gripper = np.eye(4)
        T_base_gripper[:3, :3] = R
        T_base_gripper[:3, 3] = [x, y, z]
        
        return T_base_gripper


    # 新增：大寰夹爪控制方法
    def close_gripper(self, force=100):
        """关闭夹爪，默认力度100"""
        self.gripper.SetTargetForce(force)
        self.gripper.SetTargetPosition(0)  # 0表示完全闭合
        grip_state = 0
        while grip_state == 0:
            grip_state = self.gripper.GetGripState()
            time.sleep(0.2)
        print("夹爪已闭合!")

    def open_gripper(self):
        """打开夹爪"""
        self.gripper.SetTargetPosition(1000)  # 1000表示完全打开
        grip_state = 0
        while grip_state == 0:
            grip_state = self.gripper.GetGripState()
            time.sleep(0.2)
        print("夹爪已打开!")

    def get_current_gripper_pos(self):
        """获取夹爪当前位置 (0-1000)"""
        return self.gripper.GetCurrentPosition()

    def check_grasp(self):
        """检查是否成功抓取物体 (位置>900表示已闭合)"""
        return self.get_current_gripper_pos() <= 10
    
    # ---------- CRC16校验函数（Modbus RTU标准） ----------
    def crc16(self,data: bytes):
        crc = 0xFFFF
        for pos in data:
            crc ^= pos
            for _ in range(8):
                if (crc & 0x0001) != 0:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return struct.pack('<H', crc)  # little-endian返回两字节

    # ---------- 发送指令函数 ----------
    def send_command(self,ser, cmd_hex: str):
        """
        cmd_hex: 形如 '02 06 61 07 00 01' 的字符串
        """
        cmd_bytes = bytes.fromhex(cmd_hex)
        crc = self.crc16(cmd_bytes)
        full_cmd = cmd_bytes + crc
        ser.write(full_cmd)
        print(f"发送: {full_cmd.hex(' ')}")
        time.sleep(0.2)
        # 可选读取返回
        if ser.in_waiting:
            resp = ser.read_all()
            print(f"响应: {resp.hex(' ')}")
        time.sleep(0.5)


    # 修改后的抓取方法
    def plane_grasp(self, position,type,yaw=0, open_size=0.65, k_acc=1, k_vel=1, force=100):
        if type==0:
            """执行平面抓取操作"""
            print("Testing JAKA robot...")

            ser = serial.Serial(port='/dev/ttyACM0', baudrate=115200, timeout=1)
            print("已连接") 

            print("init 夹爪")
            print("旋转 回0绝对位置点")
            self.send_command(ser, "01 06 61 07 00 01")
            # ④ 松开
            print("夹爪松开")
            self.send_command(ser, "02 06 61 07 00 00")

            rpy = [(2.964 * np.pi)/180,(-3.257 * np.pi)/180 , (-135.648 * np.pi)/180]

            
            # 预抓取位置
            # pre_position = copy.deepcopy(position)
            # pre_position[2] -= 0.1
            
            # position[0] -= 0.0045 
            position[1] += 0.012
            position[2] += 0.003

            print(f'执行抓取: 位置({position[0]}, {position[1]}, {position[2]})')
            self.move_j_p(position + rpy, k_acc, k_vel)

            # ② 夹爪夹紧
            print("夹爪夹紧")
            self.send_command(ser, "02 06 61 07 00 01")
            print("旋转 到2000000绝对位置点")
            self.send_command(ser, "01 06 61 07 00 00")

            self.move_down_slowly()
            test_pos = self.get_tcp_position()  ###end pose
            test_pos[2] -= 0.15
            self.move_j_p(test_pos,3,3)
            print("下降和旋转完成")

            # ###three steps to throw nail
            give_pos = [164.417, 173.173 ,-129.832, 222.850, -267.791, 257.801]  # down pose
            radians_list = [(angle * np.pi) / 180 for angle in give_pos]
            self.move_j(radians_list)

            give_pos = [176.663, 177.916 ,-131.248, 194.823, -83.335, 224.238]  # down pose
            radians_list = [(angle * np.pi) / 180 for angle in give_pos]
            self.move_j(radians_list)

            give_pos = [140.653, 182.302 ,-107.482, 191.509, -86.590, 191.100]  # down pose
            radians_list = [(angle * np.pi) / 180 for angle in give_pos]
            self.move_j(radians_list)

            give_pos = [139.827, 192.172 ,-107.496, 188.386, -86.467, 191.106]  # down pose
            radians_list = [(angle * np.pi) / 180 for angle in give_pos]
            self.move_j(radians_list)

            # ④ 松开
            print("夹爪松开")
            self.send_command(ser, "02 06 61 07 00 00")
            time.sleep(5)

            ####get up nail
            give_pos = [140.281, 200.922, -114.081, 185.757, -86.467, 191.058]
            radians_list = [(angle * np.pi) / 180 for angle in give_pos]
            self.move_j(radians_list)

            print("夹爪夹紧")
            self.send_command(ser, "02 06 61 07 00 01")

            give_pos = [139.827, 192.172 ,-107.496, 188.386, -86.467, 191.106]  # down pose
            radians_list = [(angle * np.pi) / 180 for angle in give_pos]
            self.move_j(radians_list)

            give_pos = [140.653, 182.302 ,-107.482, 191.509, -86.590, 191.100]  # down pose
            radians_list = [(angle * np.pi) / 180 for angle in give_pos]
            self.move_j(radians_list)

            give_pos = [176.663, 177.916 ,-131.248, 194.823, -83.335, 224.238]  # down pose
            radians_list = [(angle * np.pi) / 180 for angle in give_pos]
            self.move_j(radians_list)

            give_pos = [164.417, 173.173 ,-129.832, 222.850, -267.791, 257.801]  # down pose
            radians_list = [(angle * np.pi) / 180 for angle in give_pos]
            self.move_j(radians_list)

            give_pos = [95.982, 187.535, -152.559, 233.931, -267.333, 214.593]
            radians_list = [(angle * np.pi) / 180 for angle in give_pos]
            self.move_j(radians_list)

            print("操作完成！")
            ser.close()
            return True
        

        elif type==1:
            """执行平面抓取操作"""
            print("Testing JAKA robot...")

            ser = serial.Serial(port='/dev/ttyACM0', baudrate=115200, timeout=1)
            print("已连接") 

            print("init 夹爪")
        
            rpy = [(2.964 * np.pi)/180,(-3.257 * np.pi)/180 , (-135.648 * np.pi)/180]
        
            pos = self.get_tcp_position()
            pos[2] += 0.03
            self.move_j_p(pos, k_acc, k_vel)
            
            position[2] -= 0.09
            self.move_j_p(position + rpy, k_acc, k_vel)

            position[0] += 0.008
            position[1] -= 0.003
            

            self.move_j_p(position + rpy, k_acc, k_vel)

            pos = self.get_tcp_position()
            pos[2] += 0.06
            self.move_j_p(pos, 0.05, 0.05)
            print("旋转 回0绝对位置点")
            self.send_command(ser, "01 06 61 07 00 01")
            self.move_up_slowly()

            print("夹爪松开")
            self.send_command(ser, "02 06 61 07 00 00")
            
            time.sleep(5)

            test_pos = self.get_tcp_position()  ###end pose
            test_pos[2] -= 0.15
            self.move_j_p(test_pos,3,3)
            print("下降和旋转完成")

            give_pos = [95.982, 187.535, -152.559, 233.931, -267.333, 214.593]
            radians_list = [(angle * np.pi) / 180 for angle in give_pos]
            self.move_j(radians_list)
            
            print("操作完成！")
            ser.close()
            return True
        
        
    def move_up_slowly(self):
        # 移动到结束位置
        pos = self.get_tcp_position()  # end pose
        pos[2] += 0.01
        self.move_j_p(pos,0.05,0.05)
    
    def move_down_slowly(self):
        # 移动到结束位置
        pos = self.get_tcp_position()  # end pose
        pos[2] -= 0.03
        self.move_j_p(pos,0.05,0.05)

    def simple_unscrew_test(self, position):
        """
        简化版拧回螺丝测试：只夹紧夹爪并移动到孔洞上方
        """
        print("🔄 简化版拧回螺丝测试...")

        ser = serial.Serial(port='/dev/ttyACM0', baudrate=115200, timeout=1)

        try:
            # 1. 夹爪夹紧
            print("🦾 夹爪夹紧...")
            self.send_command(ser, "02 06 61 07 00 01")
            time.sleep(1)

            # 2. 定义拧螺丝姿态
            rpy = [(2.964 * np.pi) / 180,
                   (-3.257 * np.pi) / 180,
                   (-135.648 * np.pi) / 180]

            # 3. 位置补偿
            target_pos = position.copy()
            target_pos[0] += 0.006
            target_pos[1] += 0.006  # Y补偿
            target_pos[2] += 0.006  # Z补偿（测试数据）

            # 4. 移动到孔洞上方（带安全高度）
            safe_pos = target_pos.copy()
            safe_pos[2] += 0.05  # 安全高度

            print(f"📍 移动到孔洞安全位置: {safe_pos}")
            self.move_j_p(safe_pos + rpy, k_acc=1, k_vel=0.5)
            print("✅ 已到达孔洞上方安全位置")

            print("🔄 测试完成，夹爪保持夹紧状态")
            return True

        finally:
            ser.close()  

    # 其他原有方法保持不变...
    # (move_j, move_j_p, move_l, go_home, etc.)
    

    # def test_robot(self):
    #     """机器人测试"""
    #     print("Testing JAKA robot...")
    #     # self.go_home()
    
      
    #     # test_pos = [206.623, 61.893, 143.320, -27.771, -83.912, -44.206]
    #     # radians_list = [(angle * np.pi) / 180 for angle in test_pos]
    #     # self.move_j(radians_list)

    #     # test_pos = [30.027, 175.884, -87.559, 181.076, 89.438, 226.457]  ###    start pose
    #     # radians_list = [(angle * np.pi) / 180 for angle in test_pos]
    #     # self.move_j(radians_list)
    #     test_pos = [35.072, 163.961, -87.428, 192.921, 89.388, 221.412]  ###    start pose
    #     radians_list = [(angle * np.pi) / 180 for angle in test_pos]
    #     self.move_j(radians_list,5,5)
        

    #     test_pos = [35.072, 147.312, -63.277, 185.419, 89.388, 221.412]  ###    look pose
    #     radians_list = [(angle * np.pi) / 180 for angle in test_pos]
    #     self.move_j(radians_list,5,5)
    #     time.sleep(2)

    #     # align pose
    #     # one step
    #     test_pos = [31.380, 147.499, -53.203, 175.117, 89.426, 225.304]  
    #     radians_list = [(angle * np.pi) / 180 for angle in test_pos]
    #     self.move_j(radians_list,3,3)

    #     # two step
    #     test_pos = [30.337, 136.826, -32.759, 165.337, 89.435, 226.147]    
    #     radians_list = [(angle * np.pi) / 180 for angle in test_pos]
    #     self.move_j(radians_list,1,1)



    #     # self.go_home()
    #     # self.move_j_p([0.39, 0.09, 0.5, (90.708 * np.pi)/180, (-46.134 * np.pi)/180, (125.173 * np.pi)/180])
    #     # 打开串口

    #     ser = serial.Serial(port='/dev/ttyACM0', baudrate=115200, timeout=1)
    #     print("已连接")

    #     # ② 夹爪夹紧
    #     print("夹爪夹紧")
    #     self.send_command(ser, "02 06 61 07 00 01")
    #     print("旋转 到2000000绝对位置点")
    #     self.send_command(ser, "01 06 61 07 00 00")

    #     self.move_down_slowly()
    #     print("下降和旋转完成")

    #     test_pos = robot.get_tcp_position()  ###end pose
    #     test_pos[2] -= 0.1
    #     self.move_j_p(test_pos,5,5)

    #     #time.sleep(8)

    #     # # # ⑤ 旋转 回0绝对位置点
    #     # print("旋转 回0绝对位置点")
    #     # self.send_command(ser, "01 06 61 07 00 01")

    #     # print("操作完成！")
    #     # ser.close()
    #         # self.close_gripper()
    #         # self.plane_grasp([0.393,0.207,0.242])
    #         # print("----------------------------")
    #         # print(self.get_tcp_position)
    #         # print("----------------------------")

    #         # print("----------------------------")
    #         # print(self.cam_intrinsics)
    #         # print("----------------------------")
    #     print("Test completed")

    def test(self):
        ser = serial.Serial(port='/dev/ttyACM0', baudrate=115200, timeout=1)
             # # ⑤ 旋转 回0绝对位置点
        # print("旋转 回0绝对位置点")
        # self.send_command(ser, "01 06 61 07 00 01")
        #  # ④ 松开
        # print("夹爪松开")
        # self.send_command(ser, "02 06 61 07 00 00")
        # print("操作完成！")
        # ser.close()

        print("夹爪夹紧")
        self.send_command(ser, "02 06 61 07 00 01")
        print("旋转 到2000000绝对位置点")
        self.send_command(ser, "01 06 61 07 00 00")
        ser.close()


        # print(self.get_tcp_position())
        
        # rpy = [(-0.718 * np.pi)/180,(2.833 * np.pi)/180 , (166.427 * np.pi)/180]
        # pose = [-0.2094, 0.0330, 0.6919]
        # self.move_j_p(pose + rpy, 1, 1)


        


    # def test_robot(self):
    #     """机器人测试"""
    #     print("Testing JAKA robot...")
        
    #     # 移动到对齐位置
    #     test_pos = [30.027, 137.203, -32.406, 164.605, 89.438, 226.457]  # align pose
    #     radians_list = [(angle * np.pi) / 180 for angle in test_pos]
    #     self.move_j(radians_list)

    #     # 打开串口
    #     ser = serial.Serial(port='/dev/ttyACM0', baudrate=115200, timeout=1)
    #     print("已连接")
        
    #     # ② 夹爪夹紧
    #     print("夹爪夹紧")
    #     self.send_command(ser, "02 06 61 07 00 01")

    #     # 创建同步事件，确保两个操作同时开始
    #     start_event = threading.Event()

    #     # 创建两个线程：一个负责机械臂下降，一个负责夹爪旋转
    #     def rotate_gripper():
    #         start_event.wait()  # 等待开始信号
    #         """控制夹爪旋转的函数"""
    #         print("旋转 到1000000绝对位置点")
    #         self.send_command(ser, "01 06 61 07 00 01")
    #         # 如果需要持续旋转一段时间，可以在这里添加延时
    #         time.sleep(8)  # 根据需要调整旋转持续时间

    #     def move_down_with_sync():
    #         """带同步的下降函数"""
    #         start_event.wait()  # 等待开始信号
    #         self.move_down_slowly()
            
    #     # 启动机械臂下降线程
    #     down_thread = threading.Thread(target=move_down_with_sync)
    #     rotate_thread = threading.Thread(target=rotate_gripper)

    #     down_thread.start()
    #     rotate_thread.start()

    #     # 短暂延迟后发出开始信号（确保线程都已准备好）
    #     time.sleep(0.1)
    #     start_event.set()  # 关键：发出开始信号！

    #     # 等待下降完成
    #     down_thread.join()
    #     rotate_thread.join()
    #     print("下降和旋转完成")


    #     print("夹爪松开")
    #     self.send_command(ser, "02 06 61 07 00 00")
    #     #   ⑤ 旋转 回0绝对位置点
    #     print("旋转 回0绝对位置点")
    #     self.send_command(ser, "01 06 61 07 00 00")

    #     ser.close()
        
    # def test_robot(self):
    #     print(self.get_tcp_position())
    #     print(self.get_pose())
    #     print("test complete!")

    def test_yc(self):
         print("Testing JAKA robot...")


if __name__ == "__main__":
    robot = JAKA_Robot("10.5.5.100")
    robot.test()

    # joint_positions = robot.get_joint_position()
    # print(f"当前关节角度: {joint_positions}")
    # robot.go_home()
    # robot.get_camera_data()
    # robot.open_gripper()
    # robot.test_yc()
    # robot = JAKA_Robot()
