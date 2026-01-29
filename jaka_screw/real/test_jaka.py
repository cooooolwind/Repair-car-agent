import time  
import sys
sys.path.append('/home/robot/jaka/python_env')     
import jkrc
PI = 3.141592653589793
#运动模式
ABS = 0
INCR= 1
joint_pos=[PI,PI/2,0,PI//4,0,0]
robot = jkrc.RC("10.5.5.100")#返回机器人对象
robot.login()#登录
robot.power_on() #上电
# ip = robot.get_controller_ip ()
# print(ip)
robot.enable_robot()
# print("move1")
# robot.joint_move(joint_pos,ABS,True,0.1)
# time.sleep(3)
robot.logout()  
