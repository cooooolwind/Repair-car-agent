#!/usr/bin/env python

import socket
import numpy as np
import cv2
import os
import time
import struct
import pyrealsense2 as rs
import sys
sys.path.append('/home/yc1/robot/GRCNN')
sys.path.append('/home/yc1/robot/GRCNN/real')

import socket
import numpy as np
import cv2
import os
import time
import struct
import pyrealsense2 as rs
 
# class RealsenseD435(object):
 
#     def __init__(self):
#         self.im_height = 720
#         self.im_width = 1280
#         self.intrinsics = None
#         self.get_data()
#         # color_img, depth_img = self.get_data()
#         # print(color_img, depth_img)
 
 
#     def get_data(self):
#         # Return color image and depth image
#         pipeline = rs.pipeline()
#         config = rs.config()
#         config.enable_stream(rs.stream.depth, self.im_width, self.im_height, rs.format.z16, 30)
#         config.enable_stream(rs.stream.color, self.im_width, self.im_height, rs.format.bgr8, 30)
#         profile = pipeline.start(config)
#         frames = pipeline.wait_for_frames()
#         depth = frames.get_depth_frame()
#         color = frames.get_color_frame()
#         depth_img=np.asarray(depth.get_data())
#         color_img=np.asarray(color.get_data())
#         # print(depth_img.dtype,color_img.dtype)
#         # color_profile = color.get_profile()
#         # cvsprofile = rs.video_stream_profile(color_profile)
#         # color_intrin = cvsprofile.get_intrinsics()   # [ 640x480  p[325.14 244.014]  f[607.879 607.348]  Inverse Brown Conrady [0 0 0 0 0] ]
 
#         # Get camera intrinsics
#         self.intrinsics = [607.879,0,325.14,0,607.348,244.014,0,0,1]   # Change me!!!!!!!
 
#         return color_img, depth_img
class Camera(object):

    def __init__(self):
        self.im_height = 720
        self.im_width = 1280
        self.intrinsics = None
        self.pipeline = None
        self.config = None
        self.depth_scale = 1.0  # 初始化深度缩放因子
        self._initialize_camera()
        self.get_data()  # 获取一次数据来设置内参

    def _initialize_camera(self):
        """初始化相机并配置流"""
        if self.pipeline is None:
            self.pipeline = rs.pipeline()
            self.config = rs.config()
            self.config.enable_stream(rs.stream.depth, self.im_width, self.im_height, rs.format.z16, 30)
            self.config.enable_stream(rs.stream.color, self.im_width, self.im_height, rs.format.bgr8, 30)

            # 启动流并获取深度缩放因子
            profile = self.pipeline.start(self.config)
            depth_sensor = profile.get_device().first_depth_sensor()
            self.depth_scale = depth_sensor.get_depth_scale()

            # 获取并设置内参
            frames = self.pipeline.wait_for_frames()
            color = frames.get_color_frame()
            color_profile = color.get_profile()
            cvsprofile = rs.video_stream_profile(color_profile)
            color_intrin = cvsprofile.get_intrinsics()

            self.intrinsics = np.array([
                [color_intrin.fx, 0, color_intrin.ppx],
                [0, color_intrin.fy, color_intrin.ppy],
                [0, 0, 1]
            ])

    def get_data(self):
        """获取相机数据，包括彩色图像、深度图像和内参"""
        if self.pipeline is None:
            self._initialize_camera()

        # 获取一帧数据
        frames = self.pipeline.wait_for_frames()
        color = frames.get_color_frame()
        depth = frames.get_depth_frame()

        # 转换为numpy数组
        depth_img = np.asarray(depth.get_data())
        color_img = np.asarray(color.get_data())

        # 应用深度缩放因子（与标定代码保持一致）
        # 注意：这里不应用缩放因子，因为标定代码会单独处理
        # depth_img = depth_img * self.depth_scale

        return color_img, depth_img

    def close(self):
        """释放相机资源"""
        if self.pipeline is not None:
            self.pipeline.stop()
            self.pipeline = None
            print("相机资源已释放")
