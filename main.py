import os
import cv2
import math
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QFileDialog, QTextEdit, QGroupBox)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

# 字体选择，遇到不可以显示字体按照注释提示修改
# plt.rcParams['font.sans-serif'] = ['Noto Sans CJK JP']  # ubuntu测试的字体
plt.rcParams['font.sans-serif'] = ['SimHei']  # 在window上测试的字体
plt.rcParams['axes.unicode_minus'] = False

# 相机参数  自行修改/
K = np.array([
    [3.7633959e+04, 0, -6.1120942e+03],
    [0, 4.0733195e+04, 2.5577082e+03],
    [0, 0, 1]
], dtype=np.float32)

dist_coeffs = np.array([
    -3.928334421140308,  # k1
    37.967698969959080,  # k2
    -0.0641,  # p1
    0.4768,  # p2
    -394.8186223982327  # k3
], dtype=np.float32)

Z = 1000  # 目标到相机的距离（单位：毫米），自行修改


# *********************************************************************************
class MeasurementSystem(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("基于机器视觉的零件尺寸测量系统")
        self.setGeometry(100, 100, 1200, 800)

        # 初始化变量
        self.original_images = []
        self.gray_images = []
        self.denoised_images = []
        self.binary_imgs = []
        self.measurements = []
        self.cap = None
        self.camera_mode = False

        # 创建主窗口部件
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)

        # 主布局
        self.main_layout = QHBoxLayout()
        self.main_widget.setLayout(self.main_layout)

        # 左侧控制面板
        self.control_panel = QGroupBox("控制面板")
        self.control_layout = QVBoxLayout()

        # 按钮
        self.btn_open_image = QPushButton("打开图像")
        self.btn_open_camera = QPushButton("打开相机")
        self.btn_process = QPushButton("处理图像")
        self.btn_save_results = QPushButton("保存结果")

        # 将按钮添加到控制面板
        self.control_layout.addWidget(self.btn_open_image)
        self.control_layout.addWidget(self.btn_open_camera)
        self.control_layout.addWidget(self.btn_process)
        self.control_layout.addWidget(self.btn_save_results)
        self.control_layout.addStretch()

        self.control_panel.setLayout(self.control_layout)
        self.control_panel.setFixedWidth(200)

        # 右侧显示区域
        self.display_area = QWidget()
        self.display_layout = QVBoxLayout()

        # 图像显示区域
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: black;")

        # 日志和结果显示区域
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)

        # 添加Matplotlib图形显示
        self.figure = plt.figure()
        self.canvas = FigureCanvas(self.figure)

        # 将部件添加到显示区域
        self.display_layout.addWidget(self.image_label, 70)
        self.display_layout.addWidget(self.canvas, 30)
        self.display_layout.addWidget(self.log_text)

        self.display_area.setLayout(self.display_layout)

        # 将控制面板和显示区域添加到主布局
        self.main_layout.addWidget(self.control_panel)
        self.main_layout.addWidget(self.display_area)

        # 连接信号和槽
        self.btn_open_image.clicked.connect(self.open_image)
        self.btn_open_camera.clicked.connect(self.toggle_camera)
        self.btn_process.clicked.connect(self.process_images)
        self.btn_save_results.clicked.connect(self.save_results)

        # 相机定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_camera_frame)

        # 初始化日志
        self.log("系统初始化完成，请选择图像或打开相机")

    def log(self, message):
        """向日志区域添加消息"""
        self.log_text.append(message)

    def open_image(self):
        """打开图像文件"""
        if self.camera_mode:
            self.toggle_camera()  # 如果相机正在运行，先关闭

        options = QFileDialog.Options()
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择图像文件", "",
            "图像文件 (*.bmp *.jpg *.jpeg *.png);;所有文件 (*)",
            options=options
        )

        if not file_paths:
            return

        self.original_images = []
        for file_path in file_paths:
            img = cv2.imread(file_path)
            if img is not None:
                self.original_images.append(img)

        if self.original_images:
            self.display_image(self.original_images[0])
            self.log(f"已加载 {len(self.original_images)} 张图像")
        else:
            self.log("未能加载任何图像")

    def toggle_camera(self):
        """切换相机状态"""
        if self.camera_mode:
            self.timer.stop()
            if self.cap is not None:
                self.cap.release()
                self.cap = None
            self.btn_open_camera.setText("打开相机")
            self.camera_mode = False
            self.log("相机已关闭")
        else:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                self.log("无法打开相机")
                return

            self.camera_mode = True
            self.btn_open_camera.setText("关闭相机")
            self.timer.start(30)  # 30ms更新一次
            self.log("相机已开启")

    def update_camera_frame(self):
        """更新相机帧"""
        if self.cap is not None and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                self.display_image(frame)

    def display_image(self, img):
        """在QLabel中显示图像"""
        if len(img.shape) == 3:  # 彩色图像
            h, w, ch = img.shape
            bytes_per_line = ch * w
            q_img = QImage(img.data, w, h, bytes_per_line, QImage.Format_BGR888)
        else:  # 灰度图像
            h, w = img.shape
            q_img = QImage(img.data, w, h, w, QImage.Format_Grayscale8)

        pixmap = QPixmap.fromImage(q_img)
        scaled_pixmap = pixmap.scaled(
            self.image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.image_label.setPixmap(scaled_pixmap)

    def process_images(self):
        """处理图像并测量尺寸"""
        if not self.original_images and not self.camera_mode:
            self.log("没有可处理的图像")
            return

        if self.camera_mode and self.cap is not None:
            # 从相机捕获当前帧进行处理
            ret, frame = self.cap.read()
            if ret:
                self.original_images = [frame]

        if not self.original_images:
            self.log("没有可处理的图像")
            return

        # 清空之前的处理结果
        self.gray_images = []
        self.denoised_images = []
        self.binary_imgs = []
        self.measurements = []

        # 处理每张图像
        for img in self.original_images:
            # 转换为灰度图
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            self.gray_images.append(gray)

            # 降噪处理
            median_filtered = cv2.medianBlur(gray, 5)
            denoised = cv2.GaussianBlur(median_filtered, (5, 5), 0)
            self.denoised_images.append(denoised)

            # 二值化处理
            _, binary_img = cv2.threshold(denoised, 30, 255, cv2.THRESH_BINARY)
            self.binary_imgs.append(binary_img)

        # 检测形状并测量尺寸
        self.detect_shapes_with_measurement()

        # 显示处理结果
        self.display_measurement_results()

        self.log("图像处理完成")

    def detect_shapes_with_measurement(self):
        """检测形状并测量尺寸"""
        contour_imgs = []
        dimension_records = []
        global_counter = 1

        for img_idx, (gray, binary_img) in enumerate(zip(self.denoised_images, self.binary_imgs)):
            # 轮廓检测
            contours, hierarchy = cv2.findContours(binary_img, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            contour_img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            local_counter = 1

            for i, cnt in enumerate(contours):
                if hierarchy is not None and len(hierarchy) > 0 and hierarchy[0][i][3] != -1:
                    area = cv2.contourArea(cnt)
                    if area < 100:
                        continue

                    # 形状特征计算
                    rect = cv2.minAreaRect(cnt)
                    box = cv2.boxPoints(rect)
                    box = np.int0(box)
                    box_area = cv2.contourArea(box)

                    (x, y), radius = cv2.minEnclosingCircle(cnt)
                    circle_area = np.pi * (radius ** 2)

                    rectangularity = area / box_area if box_area > 0 else 0
                    circularity = area / circle_area if circle_area > 0 else 0
                    aspect_ratio = max(rect[1][0], rect[1][1]) / min(rect[1][0], rect[1][1]) if min(rect[1][0], rect[1][
                        1]) > 0 else 0
                    peri = cv2.arcLength(cnt, True)
                    approx = cv2.approxPolyDP(cnt, 0.03 * peri, True)
                    vertices = len(approx)

                    # 形状判定
                    is_rectangle = (rectangularity > 0.85) and (aspect_ratio < 3) and (4 <= vertices <= 6)
                    is_circle = circularity > 0.85

                    # 尺寸测量
                    if is_rectangle:
                        box_pts = box.astype(np.float32).reshape(-1, 1, 2)
                        corrected_pts = cv2.undistortPoints(box_pts, K, dist_coeffs, P=K)

                        normalized_pts = np.array([
                            [
                                (p[0][0] - K[0, 2]) / K[0, 0],
                                (p[0][1] - K[1, 2]) / K[1, 1]
                            ] for p in corrected_pts
                        ])

                        def sort_rect_pts(pts):
                            pts = pts.reshape(4, 2)
                            centroid = np.mean(pts, axis=0)
                            return sorted(pts, key=lambda p: np.arctan2(p[1] - centroid[1], p[0] - centroid[0]))

                        sorted_pts = sort_rect_pts(normalized_pts)
                        actual_pts = np.array(sorted_pts) * Z

                        width = np.linalg.norm(actual_pts[0] - actual_pts[1])
                        height = np.linalg.norm(actual_pts[1] - actual_pts[2])

                        dimension_records.append({
                            "global_id": global_counter,
                            "local_id": local_counter,
                            "image_id": img_idx + 1,
                            "type": "Rectangle",
                            "width": width,
                            "height": height
                        })

                        cv2.drawContours(contour_img, [box], 0, (0, 255, 0), 2)

                    elif is_circle:
                        center = np.array([[[x, y]]], dtype=np.float32)
                        corrected_center = cv2.undistortPoints(center, K, dist_coeffs, P=K)[0][0]

                        sample_pts = cnt[::10].astype(np.float32).reshape(-1, 1, 2)
                        corrected_edges = cv2.undistortPoints(sample_pts, K, dist_coeffs, P=K)

                        radii = [np.linalg.norm(p[0] - corrected_center) for p in corrected_edges]
                        radius_mm = np.mean(radii) * Z / K[0, 0]

                        dimension_records.append({
                            "global_id": global_counter,
                            "local_id": local_counter,
                            "image_id": img_idx + 1,
                            "type": "Circle",
                            "radius": radius_mm
                        })

                        cv2.drawContours(contour_img, [cnt], -1, (0, 0, 255), 2)
                    else:
                        continue

                    # 标注顺序
                    M = cv2.moments(cnt)
                    if M["m00"] != 0:
                        cX = int(M["m10"] / M["m00"])
                        cY = int(M["m01"] / M["m00"])
                    else:
                        cX, cY = cnt[0][0]

                    cv2.putText(contour_img, f"G{global_counter}", (cX - 40, cY - 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
                    cv2.putText(contour_img, f"L{local_counter}", (cX - 40, cY + 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

                    global_counter += 1
                    local_counter += 1

            contour_imgs.append(contour_img)

        self.measurements = dimension_records
        if contour_imgs:
            self.display_image(contour_imgs[0])

    def display_measurement_results(self):
        """显示测量结果"""
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        if not self.measurements:
            ax.text(0.5, 0.5, "没有检测到可测量的形状",
                    ha='center', va='center', fontsize=12)
            self.canvas.draw()
            return

        # 准备数据
        types = []
        dimensions = []
        for item in self.measurements:
            types.append(item["type"])
            if item["type"] == "Rectangle":
                dimensions.append(f"宽: {item['width']:.2f}mm\n高: {item['height']:.2f}mm")
            else:
                dimensions.append(f"半径: {item['radius']:.2f}mm")

        # 创建表格
        table_data = []
        for i, (t, d) in enumerate(zip(types, dimensions)):
            table_data.append([f"零件 {i + 1}", t, d])

        # 绘制表格
        ax.axis('off')
        table = ax.table(
            cellText=table_data,
            colLabels=["编号", "类型", "尺寸"],
            loc='center',
            cellLoc='center'
        )
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 1.5)

        self.canvas.draw()

        # 在日志中显示结果
        self.log("\n=== 测量结果 ===")
        self.log("编号 | 类型      | 尺寸")
        self.log("-" * 40)
        for item in self.measurements:
            if item["type"] == "Rectangle":
                dim_info = f"宽={item['width']:.2f}mm, 高={item['height']:.2f}mm"
            else:
                dim_info = f"半径={item['radius']:.2f}mm"

            self.log(f"{item['global_id']:3} | {item['type']:9} | {dim_info}")

    def save_results(self):
        """保存结果"""
        if not self.measurements:
            self.log("没有可保存的结果")
            return

        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存结果", "",
            "文本文件 (*.txt);;所有文件 (*)",
            options=options
        )

        if not file_path:
            return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("=== 零件尺寸测量结果 ===\n")
                f.write("编号 | 类型      | 尺寸\n")
                f.write("-" * 40 + "\n")
                for item in self.measurements:
                    if item["type"] == "Rectangle":
                        dim_info = f"宽={item['width']:.2f}mm, 高={item['height']:.2f}mm"
                    else:
                        dim_info = f"半径={item['radius']:.2f}mm"

                    f.write(f"{item['global_id']:3} | {item['type']:9} | {dim_info}\n")

            self.log(f"结果已保存到: {file_path}")
        except Exception as e:
            self.log(f"保存失败: {str(e)}")

    def closeEvent(self, event):
        """关闭窗口时释放资源"""
        if self.cap is not None:
            self.cap.release()
        if self.timer.isActive():
            self.timer.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication([])
    window = MeasurementSystem()
    window.show()
    app.exec_()
