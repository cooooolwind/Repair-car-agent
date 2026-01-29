import matplotlib.pyplot as plt
import numpy as np
import time
import cv2
import sys
sys.path.append('//home/robot/GRCNN')
sys.path.append('//home/robot/GRCNN/real')
# from jaka_robot_yc import JAKA_Robot  # 确保文件名正确
from scipy import optimize
from mpl_toolkits.mplot3d import Axes3D

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

# np.savetxt('/home/robot/GRCNN/real/cam_pose/measured_pts.txt', np.asarray(measured_pts), delimiter=' ')
# np.savetxt('/home/robot/GRCNN/real/cam_pose/observed_pts.txt', np.asarray(observed_pts), delimiter=' ')
# np.savetxt('/home/robot/GRCNN/real/cam_pose/observed_pix.txt', np.asarray(observed_pix), delimiter=' ')
measured_pts = np.loadtxt('/home/robot/GRCNN/real/cam_pose/measured_pts.txt', delimiter=' ')
observed_pts = np.loadtxt('/home/robot/GRCNN/real/cam_pose/observed_pts.txt', delimiter=' ')
observed_pix = np.loadtxt('/home/robot/GRCNN/real/cam_pose/observed_pix.txt', delimiter=' ')

fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')
ax.scatter(measured_pts[:,0],measured_pts[:,1],measured_pts[:,2], c='blue')

camera_depth_offset = [0.00087891]
print(camera_depth_offset)
R, t = get_rigid_transform(np.asarray(measured_pts), np.asarray(observed_pts))
t.shape = (3,1)
camera_pose = np.concatenate((np.concatenate((R, t), axis=1),np.array([[0, 0, 0, 1]])), axis=0)
camera2robot = np.linalg.inv(camera_pose)
t_observed_pts = np.transpose(np.dot(camera2robot[0:3,0:3],np.transpose(observed_pts)) + np.tile(camera2robot[0:3,3:],(1,observed_pts.shape[0])))

ax.scatter(t_observed_pts[:,0],t_observed_pts[:,1],t_observed_pts[:,2], c='red')

new_observed_pts = observed_pts.copy()
new_observed_pts[:,2] = new_observed_pts[:,2] * camera_depth_offset[0]
R, t = get_rigid_transform(np.asarray(measured_pts), np.asarray(new_observed_pts))
t.shape = (3,1)
camera_pose = np.concatenate((np.concatenate((R, t), axis=1),np.array([[0, 0, 0, 1]])), axis=0)
camera2robot = np.linalg.inv(camera_pose)
t_new_observed_pts = np.transpose(np.dot(camera2robot[0:3,0:3],np.transpose(new_observed_pts)) + np.tile(camera2robot[0:3,3:],(1,new_observed_pts.shape[0])))

ax.scatter(t_new_observed_pts[:,0],t_new_observed_pts[:,1],t_new_observed_pts[:,2], c='green')

plt.show()