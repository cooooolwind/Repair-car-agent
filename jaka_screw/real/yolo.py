import pyrealsense2 as rs
import numpy as np
import cv2
from ultralytics import YOLO

# 1. 初始化 RealSense 管线
pipeline = rs.pipeline()
config = rs.config()
config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
pipeline.start(config)

# 2. 加载 YOLOv11 模型
model = YOLO("hole2.pt")  # 路径

print("✅ 相机与模型加载成功，开始检测... 按 'q' 退出")

try:
    while True:
        # 3. 获取相机帧
        frames = pipeline.wait_for_frames()
        color_frame = frames.get_color_frame()
        if not color_frame:
            continue
        color_image = np.asanyarray(color_frame.get_data())

        # 4. YOLO 检测
        results = model(color_image)
        
         # 提取中心点
        for box in results[0].boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            u = int((x1 + x2) / 2)
            v = int((y1 + y2) / 2)
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])

            print(f"类别 {cls_id}, 置信度 {conf:.2f}, 中心点: ({u}, {v})")
            cv2.circle(color_image, (u, v), 5, (0, 255, 0), -1)

        # 5. 绘制检测结果
        annotated = results[0].plot()

        # 6. 显示画面
        cv2.imshow('YOLO Screw Detection', annotated)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

finally:
    pipeline.stop()
    cv2.destroyAllWindows()
