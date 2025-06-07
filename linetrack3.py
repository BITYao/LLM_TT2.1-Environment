import sys
import io

# 强制设置标准输出编码为UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
import cv2
import time
import numpy as np
import threading
import queue
import os
import sys
from pathlib import Path
from djitellopy import Tello
from datetime import datetime
import traceback
from collections import deque
import atexit
import locale

# 检测系统默认编码
print(f"系统默认编码: {locale.getpreferredencoding()}")
print(f"Python默认编码: {sys.getdefaultencoding()}")

# 配置路径 - 使用Path对象安全处理中文路径
FILE = Path(__file__).resolve()
ROOT = FILE.parent
print(f"当前工作目录: {ROOT}")

if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

# 全局变量
frame_queue = queue.Queue(maxsize=10)
result_queue = queue.Queue(maxsize=10)
control_queue = queue.Queue(maxsize=5)
stop_event = threading.Event()

# ==================== 优化的下视图像坐标系参数 ====================
# 下视图像坐标系定义：
# - 图像左侧 = 无人机前进方向 (Forward)
# - 图像右侧 = 无人机后退方向 (Backward) 
# - 图像上方 = 无人机右侧方向 (Right)
# - 图像下方 = 无人机左侧方向 (Left)

# 图像尺寸和中心点
IMAGE_WIDTH = 320
IMAGE_HEIGHT = 240
IMAGE_CENTER_X = IMAGE_WIDTH // 2   # 160
IMAGE_CENTER_Y = IMAGE_HEIGHT // 2  # 120

# 控制死区和敏感度
LATERAL_DEADZONE = 8        # 左右控制死区（像素）
FORWARD_DEADZONE = 5        # 前后控制死区（像素）
POSITION_SENSITIVITY = 0.4   # 位置控制敏感度
DIRECTION_SENSITIVITY = 0.8  # 方向控制敏感度

# 轨迹跟随参数
TRACK_ALIGNMENT_TOLERANCE = 3.0  # 轨迹对齐容忍度（像素）

# 速度控制参数 - 根据下视图像优化
MIN_FORWARD_SPEED = 6        # 最小前进速度
MAX_FORWARD_SPEED = 18       # 最大前进速度  
MIN_LATERAL_SPEED = 4        # 最小侧向速度
MAX_LATERAL_SPEED = 15       # 最大侧向速度
MAX_YAW_SPEED = 20           # 最大偏航速度

# 方向控制优化参数
DIRECTION_THRESHOLD = 12.0   # 方向偏离阈值（度）- 针对下视图像优化
YAW_RESPONSE_FACTOR = 0.7    # 偏航响应系数

# 轨迹预测参数
PREDICTION_STEPS = 3         # 预测步数
HISTORY_LENGTH = 5           # 历史位置记录长度

# 方向优先级参数
PREFERRED_DIRECTION = 0      # 下视图像中向左为0度（无人机前进方向）
DIRECTION_TOLERANCE = 35     # 方向匹配容忍度
FORWARD_DIRECTION_BIAS = 2.5 # 前向方向评分加权

# 自动飞行控制参数
AUTO_FLIGHT_TIME = 90    # 延长自动飞行时间
AUTO_SAFETY_CHECK_INTERVAL = 1.0  

# 全局实例
tello = None
vignette_corrector = None
position_history = deque(maxlen=HISTORY_LENGTH)
direction_history = deque(maxlen=HISTORY_LENGTH)

# ==================== 下视图像坐标转换类 ====================
class DownwardCoordinateSystem:
    """
    下视图像坐标系转换和控制映射
    处理下视图像与无人机控制指令的坐标转换
    """
    
    def __init__(self, image_width=IMAGE_WIDTH, image_height=IMAGE_HEIGHT):
        self.width = image_width
        self.height = image_height
        self.center_x = image_width // 2
        self.center_y = image_height // 2
        
        print(f"下视坐标系初始化: {self.width}x{self.height}, 中心=({self.center_x}, {self.center_y})")
        print("坐标系映射: 左=前进, 右=后退, 上=右侧, 下=左侧")
    
    def image_to_drone_control(self, image_x, image_y):
        """
        将图像坐标转换为无人机控制指令
        
        Args:
            image_x, image_y: 图像坐标（轨迹中心点）
            
        Returns:
            control_dict: {lr: 左右控制, fb: 前后控制, explanation: 说明}
        """
        # 计算相对于图像中心的偏移
        offset_x = image_x - self.center_x  # 正值=右偏，负值=左偏
        offset_y = image_y - self.center_y  # 正值=下偏，负值=上偏
        
        # 坐标转换逻辑：
        # 图像X轴（左右）-> 无人机前后控制 (FB)
        # 图像Y轴（上下）-> 无人机左右控制 (LR)
        
        # FB控制：图像左偏（负X）= 前进，图像右偏（正X）= 后退
        fb_control = -offset_x * POSITION_SENSITIVITY
        
        # LR控制：图像上偏（负Y）= 右移，图像下偏（正Y）= 左移  
        lr_control = -offset_y * POSITION_SENSITIVITY
        
        # 应用死区
        if abs(fb_control) < FORWARD_DEADZONE:
            fb_control = 0
        if abs(lr_control) < LATERAL_DEADZONE:
            lr_control = 0
        
        # 限制控制范围
        fb_control = np.clip(fb_control, -MAX_FORWARD_SPEED, MAX_FORWARD_SPEED)
        lr_control = np.clip(lr_control, -MAX_LATERAL_SPEED, MAX_LATERAL_SPEED)
        
        explanation = f"图像偏移({offset_x:.1f},{offset_y:.1f}) -> 控制(FB:{fb_control:.1f}, LR:{lr_control:.1f})"
        
        return {
            'lr': int(lr_control),
            'fb': int(fb_control), 
            'offset_x': offset_x,
            'offset_y': offset_y,
            'explanation': explanation
        }
    
    def calculate_direction_control(self, line_angle, target_angle=PREFERRED_DIRECTION):
        """
        计算方向控制，确保无人机沿轨迹方向飞行
        
        Args:
            line_angle: 检测到的轨迹角度（度）
            target_angle: 目标角度（0度=向左=前进方向）
        
        Returns:
            yaw_control: 偏航控制值
        """
        # 角度偏差计算
        angle_error = line_angle - target_angle
        
        # 归一化到[-180, 180]
        while angle_error > 180:
            angle_error -= 360
        while angle_error < -180:
            angle_error += 360
        
        # 计算偏航控制
        yaw_control = angle_error * DIRECTION_SENSITIVITY * YAW_RESPONSE_FACTOR
        yaw_control = np.clip(yaw_control, -MAX_YAW_SPEED, MAX_YAW_SPEED)
        
        return int(yaw_control), angle_error
    
    def is_on_track_center(self, track_width, image_width_ref=None):
        """
        判断无人机是否在轨迹中心线上
        
        Args:
            track_width: 检测到的轨迹宽度
            image_width_ref: 参考图像宽度
        
        Returns:
            bool: 是否在轨迹中心
        """
        if image_width_ref is None:
            image_width_ref = self.width
            
        # 轨迹宽度合理性检查
        reasonable_width = track_width < (image_width_ref * 0.6)
        
        # 可以添加更多判断逻辑
        return reasonable_width

# ==================== 暗角校正类 ====================
class VignetteCorrector:
    """无人机镜头暗角校正器"""
    
    def __init__(self, image_shape, vignette_strength=0.4):
        self.height, self.width = image_shape[:2]
        self.vignette_strength = vignette_strength
        self.correction_mask = self._create_correction_mask()
        print(f"暗角校正器初始化完成: {self.width}x{self.height}, 强度={vignette_strength}")
    
    def _create_correction_mask(self):
        center_x, center_y = self.width // 2, self.height // 2
        y, x = np.ogrid[:self.height, :self.width]
        distance = np.sqrt((x - center_x)**2 + (y - center_y)**2)
        max_distance = np.sqrt(center_x**2 + center_y**2)
        normalized_distance = distance / max_distance
        correction_mask = 1 + self.vignette_strength * (normalized_distance ** 2)
        correction_mask = np.clip(correction_mask, 1.0, 2.0)
        return correction_mask.astype(np.float32)
    
    def correct_vignette(self, image):
        if image is None:
            return None
            
        current_height, current_width = image.shape[:2]
        if current_height != self.height or current_width != self.width:
            self.height, self.width = current_height, current_width
            self.correction_mask = self._create_correction_mask()
            
        image_float = image.astype(np.float32)
        
        if len(image.shape) == 3:
            corrected = np.zeros_like(image_float)
            for i in range(image.shape[2]):
                corrected[:,:,i] = image_float[:,:,i] * self.correction_mask
        else:
            corrected = image_float * self.correction_mask
        
        corrected = np.clip(corrected, 0, 255)
        return corrected.astype(np.uint8)
    
    def visualize_correction(self, original_image):
        if original_image is None:
            return None
            
        corrected = self.correct_vignette(original_image)
        h, w = original_image.shape[:2]
        comparison = np.zeros((h, w*2, 3), dtype=np.uint8)
        
        if len(original_image.shape) == 3:
            comparison[:, :w] = original_image
            comparison[:, w:] = corrected
        else:
            comparison[:, :w] = cv2.cvtColor(original_image, cv2.COLOR_GRAY2BGR)
            comparison[:, w:] = cv2.cvtColor(corrected, cv2.COLOR_GRAY2BGR)
        
        cv2.line(comparison, (w, 0), (w, h), (0, 255, 0), 2)
        cv2.putText(comparison, "Original", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.putText(comparison, "Corrected", (w+10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        return comparison

# 安全清理函数
def safe_cleanup():
    global tello
    print("正在安全清理资源...")
    if tello is not None:
        try:
            tello.send_rc_control(0, 0, 0, 0)
            time.sleep(0.1)
        except:
            pass
        
        try:
            tello.send_expansion_command("led 0 0 0")
            time.sleep(0.1)
        except:
            pass
        
        try:
            if tello.is_flying:
                print("正在降落...")
                tello.land()
                time.sleep(3)
        except:
            pass
        
        try:
            tello.streamoff()
            time.sleep(0.5)
        except:
            pass
        
        try:
            tello.end()
        except:
            pass
    
    cv2.destroyAllWindows()

atexit.register(safe_cleanup)

# 模糊PID控制器
class FuzzyPIDController:
    def __init__(self, kp=1.0, ki=0.0, kd=0.1, windup_guard=20.0):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.windup_guard = windup_guard
        self.error_sum = 0.0
        self.last_error = 0.0
        self.last_time = time.time()
    
    def compute(self, error, current_time=None):
        if current_time is None:
            current_time = time.time()
        
        time_delta = current_time - self.last_time
        if time_delta <= 0:
            time_delta = 0.01
        
        error_delta = (error - self.last_error) / time_delta
        self.error_sum += error * time_delta
        
        if self.error_sum > self.windup_guard:
            self.error_sum = self.windup_guard
        elif self.error_sum < -self.windup_guard:
            self.error_sum = -self.windup_guard
        
        # 模糊化控制增益
        if abs(error) < 5:
            effective_kp = self.kp * 1.8
            effective_kd = self.kd * 0.6
        elif abs(error) < 15:
            effective_kp = self.kp * 1.4
            effective_kd = self.kd * 1.0
        else:
            effective_kp = self.kp * 0.9
            effective_kd = self.kd * 1.6
        
        p_term = effective_kp * error
        i_term = self.ki * self.error_sum
        d_term = effective_kd * error_delta
        
        output = p_term + i_term + d_term
        
        self.last_error = error
        self.last_time = current_time
        
        return output

# 创建PID控制器 - 针对下视图像优化
lateral_pid = FuzzyPIDController(kp=0.4, ki=0.02, kd=0.15)    # 左右控制
forward_pid = FuzzyPIDController(kp=0.35, ki=0.015, kd=0.12)  # 前后控制  
direction_pid = FuzzyPIDController(kp=0.6, ki=0.03, kd=0.18)  # 方向控制

# ==================== 轨迹预测和历史分析 ====================
class TrajectoryPredictor:
    """轨迹预测器，用于预测性控制"""
    
    def __init__(self, history_length=HISTORY_LENGTH):
        self.position_history = deque(maxlen=history_length)
        self.direction_history = deque(maxlen=history_length)
        self.time_history = deque(maxlen=history_length)
    
    def add_observation(self, center_pos, direction_angle):
        """添加观测数据"""
        current_time = time.time()
        self.position_history.append(center_pos)
        self.direction_history.append(direction_angle)
        self.time_history.append(current_time)
    
    def predict_next_position(self, steps_ahead=PREDICTION_STEPS):
        """预测下一个位置"""
        if len(self.position_history) < 3:
            return None
        
        # 简单的线性预测
        recent_positions = list(self.position_history)[-3:]
        
        # 计算运动向量
        dx = recent_positions[-1][0] - recent_positions[-2][0]
        dy = recent_positions[-1][1] - recent_positions[-2][1]
        
        # 预测位置
        predicted_x = recent_positions[-1][0] + dx * steps_ahead
        predicted_y = recent_positions[-1][1] + dy * steps_ahead
        
        return (int(predicted_x), int(predicted_y))
    
    def get_movement_trend(self):
        """获取运动趋势"""
        if len(self.position_history) < 2:
            return "stable"
        
        recent_positions = list(self.position_history)[-2:]
        dx = recent_positions[-1][0] - recent_positions[-2][0]
        dy = recent_positions[-1][1] - recent_positions[-2][1]
        
        if abs(dx) < 2 and abs(dy) < 2:
            return "stable"
        elif abs(dx) > abs(dy):
            return "horizontal" if dx > 0 else "horizontal_back"
        else:
            return "vertical_down" if dy > 0 else "vertical_up"

# ==================== 优化的轨迹检测函数 ====================
def normalize_angle_to_forward_reference(angle):
    """
    将角度归一化为以前进方向为参考的角度
    前进方向(左侧)为0度
    """
    # 调整角度使左侧(前进方向)为0度
    normalized = angle
    if normalized > 180:
        normalized -= 360
    return normalized

def calculate_direction_score(normalized_angle):
    """
    计算方向评分，前进方向(0度)得分最高
    """
    # 计算与前进方向(0度)的角度差
    angle_diff = abs(normalized_angle)
    if angle_diff > 180:
        angle_diff = 360 - angle_diff
    
    # 前向方向得分最高
    if angle_diff <= DIRECTION_TOLERANCE:
        return FORWARD_DIRECTION_BIAS  # 前向方向加权
    elif angle_diff <= 90:
        return 1.0 - (angle_diff / 90.0)  # 90度内线性降低
    else:
        return 0  # 背向方向不加分
        
def detect_turn_improved(contour, points):
    """
    改进的转弯检测算法
    """
    # 计算轮廓复杂度
    perimeter = cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
    
    # 计算凸包和凸缺陷
    hull = cv2.convexHull(contour)
    hull_area = cv2.contourArea(hull)
    contour_area = cv2.contourArea(contour)
    
    # 计算填充度
    solidity = contour_area / hull_area if hull_area > 0 else 0
    
    # 计算轮廓的主要方向变化
    if len(points) >= 10:
        # 采样点进行方向分析
        step = max(1, len(points) // 10)
        sampled_points = points[::step]
        
        if len(sampled_points) >= 3:
            directions = []
            for i in range(1, len(sampled_points) - 1):
                prev_pt = sampled_points[i-1]
                curr_pt = sampled_points[i]
                next_pt = sampled_points[i+1]
                
                vec1 = curr_pt - prev_pt
                vec2 = next_pt - curr_pt
                
                if np.linalg.norm(vec1) > 0 and np.linalg.norm(vec2) > 0:
                    # 计算两向量夹角
                    cos_angle = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
                    cos_angle = np.clip(cos_angle, -1.0, 1.0)
                    angle = np.degrees(np.arccos(cos_angle))
                    directions.append(angle)
            
            # 如果有显著的方向变化，认为有转弯
            if directions and (np.max(directions) > 45 or np.std(directions) > 15):
                return True
    
    # 基于几何特征的转弯检测
    has_turn = (len(approx) > 5) or (solidity < 0.8)
    
    return has_turn

# 定义裁剪边缘的像素值
CROP_MARGIN = 20  # 每个边缘裁剪20个像素

def detect_track_optimized(frame):
    """
    优化的轨迹检测函数 - 采用黑线检测方法并增加方向优先级选择
    - 暗角校正预处理
    - 使用固定阈值方法
    - 优化形态学处理
    - 改进线条筛选逻辑
    - 新增：多线条时优先选择前向方向
    """
    global vignette_corrector
    
    # 步骤1: 暗角校正
    ENABLE_VIGNETTE_CORRECTION = True  # 添加这个变量定义
    if vignette_corrector is not None and ENABLE_VIGNETTE_CORRECTION:
        corrected_frame = vignette_corrector.correct_vignette(frame)
        cv2.imshow("Vignette Corrected", corrected_frame)
    else:
        corrected_frame = frame
        
    # 步骤2：裁剪边缘，去除暗角或误差区域
    height, width = corrected_frame.shape[:2]
    cropped_frame = corrected_frame[CROP_MARGIN:height-CROP_MARGIN, CROP_MARGIN:width-CROP_MARGIN]
    cv2.imshow("Cropped Frame", cropped_frame)


    # 步骤2: 转换为灰度图
    gray = cv2.cvtColor(cropped_frame, cv2.COLOR_BGR2GRAY)
    
    # 步骤3: 高斯模糊
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # 步骤4: 使用固定阈值方法
    _, binary = cv2.threshold(blurred, 50, 255, cv2.THRESH_BINARY_INV)
    cv2.imshow("Binary Threshold", binary)
    
    # 检查二值化结果
    white_pixels = np.sum(binary == 255)
    total_pixels = binary.shape[0] * binary.shape[1]
    white_ratio = white_pixels / total_pixels
    print(f"二值化后白色像素比例: {white_ratio:.3f}")
    
    if white_ratio < 0.001:  # 如果白色像素太少
        print("警告: 二值化后几乎没有白色区域，可能阈值设置有问题")
        return {"found": False, "reason": "no_white_pixels", "binary_image": binary}
    
    # 步骤5: 优化的形态学处理
    kernel_small = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    kernel_medium = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    
    # 轻微的开运算去除小噪声
    binary_cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_small, iterations=1)
    cv2.imshow("After Open Operation", binary_cleaned)
    
    # 轻微的闭运算连接断裂
    binary_cleaned = cv2.morphologyEx(binary_cleaned, cv2.MORPH_CLOSE, kernel_medium, iterations=1)
    cv2.imshow("Morphology Processed", binary_cleaned)
    
    # 检查形态学处理后的结果
    white_pixels_after = np.sum(binary_cleaned == 255)
    white_ratio_after = white_pixels_after / total_pixels
    print(f"形态学处理后白色像素比例: {white_ratio_after:.3f}")
    
    if white_ratio_after < 0.0005:  # 如果形态学处理导致白色区域消失
        print("警告: 形态学处理导致白色区域消失，使用原始二值化结果")
        binary_cleaned = binary
    
    # 步骤6: 轮廓检测
    contours, _ = cv2.findContours(binary_cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"检测到 {len(contours)} 个轮廓")
    
    if not contours:
        return {"found": False, "reason": "no_contours", "binary_image": binary_cleaned}
    
    # 步骤7: 改进的轨迹候选筛选 - 加入方向优先级
    valid_tracks = []
    
    for i, contour in enumerate(contours):
        area = cv2.contourArea(contour)
        print(f"轮廓 {i}: 面积 = {area}")
        
        # 面积筛选 - 去除过小的噪声
        if area < 30 :
            print(f"  -> 面积过小，跳过")
            continue
        elif area > 2500:
            print(f"  -> 面积过大，跳过")
            continue
        # 检查轮廓是否主要由白色像素组成
        mask = np.zeros(binary_cleaned.shape, dtype=np.uint8)
        cv2.fillPoly(mask, [contour], 255)
        white_in_contour = np.sum((binary_cleaned == 255) & (mask == 255))
        contour_area_pixels = np.sum(mask == 255)
        
        if contour_area_pixels > 0:
            white_ratio_in_contour = white_in_contour / contour_area_pixels
            print(f"  -> 轮廓内白色像素比例: {white_ratio_in_contour:.3f}")
            
            # 主要由白色像素组成的区域
            if white_ratio_in_contour > 0.5:
                # 计算几何特征
                rect = cv2.minAreaRect(contour)
                width, height = rect[1]
                
                if width > 0 and height > 0:
                    aspect_ratio = max(width, height) / min(width, height)
                    
                    # 计算轨迹方向
                    points = contour.reshape(-1, 2)
                    if len(points) >= 5:
                        try:
                            # 使用PCA计算主方向
                            centroid = np.mean(points, axis=0)
                            centered_points = points - centroid
                            cov_matrix = np.cov(centered_points.T)
                            eigenvalues, eigenvectors = np.linalg.eig(cov_matrix)
                            main_direction = eigenvectors[:, np.argmax(eigenvalues)]
                            track_angle = np.degrees(np.arctan2(main_direction[1], main_direction[0]))
                        except:
                            track_angle = rect[2]
                            if rect[1][0] < rect[1][1]:
                                track_angle += 90
                    else:
                        track_angle = rect[2]
                        if rect[1][0] < rect[1][1]:
                            track_angle += 90
                    
                    # 归一化角度到0-360度
                    track_angle = track_angle % 360
                    
                    # 归一化角度为前向参考
                    normalized_angle = normalize_angle_to_forward_reference(track_angle)
                    
                    # 计算方向评分
                    direction_score = calculate_direction_score(normalized_angle)
                    
                    # 计算填充度
                    hull = cv2.convexHull(contour)
                    hull_area = cv2.contourArea(hull)
                    solidity = area / hull_area if hull_area > 0 else 0
                    
                    # 改进的评分系统
                    score = 0
                    
                    # 长宽比评分 - 轨迹通常是细长的
                    if aspect_ratio >= 1.5:
                        score += 2
                        if aspect_ratio >= 3.0:
                            score += 1
                    
                    # 面积评分
                    if 50 <= area <= 5000:
                        score += 2
                    elif area > 5000:
                        score += 1
                    
                    # 填充度评分
                    if solidity > 0.6:
                        score += 1
                    
                    # 方向评分 - 前向方向优先
                    score += direction_score
                    
                    print(f"  -> 长宽比: {aspect_ratio:.2f}, 方向: {track_angle:.1f}°({normalized_angle:.1f}°), 方向评分: {direction_score:.2f}, 总评分: {score:.2f}")
                    
                    if score >= 2:  # 降低评分要求以匹配更多轨迹
                        valid_tracks.append({
                            'contour': contour,
                            'area': area,
                            'aspect_ratio': aspect_ratio,
                            'solidity': solidity,
                            'track_angle': track_angle,
                            'normalized_angle': normalized_angle,
                            'direction_score': direction_score,
                            'score': score,
                            'rect': rect,
                            'width': width,
                            'height': height
                        })
                        print(f"  -> 有效轨迹候选，评分: {score:.2f}")
            else:
                print(f"  -> 白色像素比例过低，跳过")
    
    print(f"找到 {len(valid_tracks)} 个有效轨迹候选")
    
    if not valid_tracks:
        return {"found": False, "reason": "no_valid_tracks", "binary_image": binary_cleaned}
    
    # 步骤8: 选择最佳轨迹 - 优先考虑方向评分
    if len(valid_tracks) == 1:
        best_track = valid_tracks[0]
        print(f"只有一个候选轨迹，直接选择")
    else:
        # 多个候选时，按总评分排序
        valid_tracks.sort(key=lambda x: x['score'], reverse=True)
        
        print(f"多个轨迹候选，按评分排序:")
        for i, track in enumerate(valid_tracks[:3]):  # 显示前3个
            print(f"  候选{i+1}: 评分={track['score']:.2f}, 方向={track['track_angle']:.1f}°, 面积={track['area']}")
        
        best_track = valid_tracks[0]
        
        # 如果最高分的轨迹方向不是前向，但存在前向方向的轨迹，考虑切换
        forward_candidates = [track for track in valid_tracks if track['direction_score'] >= FORWARD_DIRECTION_BIAS]
        if forward_candidates and best_track['direction_score'] < FORWARD_DIRECTION_BIAS:
            # 如果存在前向候选，且当前最佳不是前向，考虑切换
            best_forward = max(forward_candidates, key=lambda x: x['score'])
            
            # 如果前向候选的评分不差太多，优先选择前向
            if best_forward['score'] >= best_track['score'] * 0.8:
                print(f"优先选择前向方向轨迹: 评分={best_forward['score']:.2f} vs {best_track['score']:.2f}")
                best_track = best_forward
    
    contour = best_track['contour']
    print(f"最终选择轨迹: 面积={best_track['area']}, 方向={best_track['track_angle']:.1f}°, 总评分={best_track['score']:.2f}")
    
    # 步骤9: 计算轨迹中心和特征
    M = cv2.moments(contour)
    
    if M["m00"] == 0:
        return {"found": False, "reason": "zero_moment", "binary_image": binary_cleaned}
    
    # 计算轨迹中心点
    cx = int(M["m10"] / M["m00"])
    cy = int(M["m01"] / M["m00"])
    
    # 轨迹方向角度
    track_angle = best_track['track_angle']
    
    # 计算轨迹宽度
    track_width = min(best_track['width'], best_track['height'])
    track_length = max(best_track['width'], best_track['height'])
    
    # 转弯检测
    points = contour.reshape(-1, 2)
    has_turn = detect_turn_improved(contour, points)
    
    print(f"轨迹检测完成: 中心=({cx}, {cy}), 角度={track_angle:.1f}°, 宽度={track_width:.1f}, 转弯={has_turn}")
    
    return {
        "found": True,
        "center": (cx, cy),
        "track_angle": float(track_angle),
        "normalized_angle": float(best_track['normalized_angle']),
        "direction_score": float(best_track['direction_score']),
        "track_width": float(track_width),
        "track_length": float(track_length),
        "has_turn": has_turn,
        "contour": contour,
        "binary_image": binary_cleaned,
        "track_info": best_track,
        "candidates_count": len(valid_tracks),
        "area": best_track['area'],
        "aspect_ratio": best_track['aspect_ratio'],
        "solidity": best_track['solidity']
    }

# ==================== 优化的轨迹跟随控制 ====================
def calculate_track_following_control(track_result, coord_system, predictor):
    """
    计算轨迹跟随控制指令 - 确保无人机与轨迹重合
    
    Args:
        track_result: 轨迹检测结果
        coord_system: 下视坐标转换器
        predictor: 轨迹预测器
    
    Returns:
        control_dict: 控制指令字典
    """
    if not track_result["found"]:
        return {
            "lr": 0, "fb": 0, "yaw": 15, 
            "control_mode": "SEARCHING",
            "status": "no_track",
            "alignment_score": 0
        }
    
    # 获取轨迹信息
    track_center = track_result["center"]
    track_angle = track_result["track_angle"]
    track_width = track_result["track_width"]
    has_turn = track_result["has_turn"]
    
    # 添加到预测器
    predictor.add_observation(track_center, track_angle)
    
    # 基础位置控制 - 确保无人机在轨迹中心
    position_control = coord_system.image_to_drone_control(track_center[0], track_center[1])
    base_lr = position_control['lr']
    base_fb = position_control['fb']
    
    # 方向控制 - 确保无人机沿轨迹方向
    yaw_control, angle_error = coord_system.calculate_direction_control(track_angle, PREFERRED_DIRECTION)
    
    # 计算对齐评分
    position_offset = np.sqrt(position_control['offset_x']**2 + position_control['offset_y']**2)
    alignment_score = max(0, 100 - position_offset * 2 - abs(angle_error))
    
    # 根据对齐情况和轨迹特征决定控制模式
    if position_offset <= TRACK_ALIGNMENT_TOLERANCE and abs(angle_error) <= DIRECTION_THRESHOLD:
        # 完美对齐 - 主要前进
        control_mode = "ALIGNED_FORWARD"
        
        # 预测性控制
        predicted_pos = predictor.predict_next_position()
        if predicted_pos:
            future_control = coord_system.image_to_drone_control(predicted_pos[0], predicted_pos[1])
            # 混合当前控制和预测控制
            final_lr = int(base_lr * 0.7 + future_control['lr'] * 0.3)
            final_fb = max(MIN_FORWARD_SPEED, int(base_fb * 0.5 + MAX_FORWARD_SPEED * 0.8))
        else:
            final_lr = base_lr
            final_fb = max(MIN_FORWARD_SPEED, MAX_FORWARD_SPEED)
        
        final_yaw = int(yaw_control * 0.6)  # 减少偏航调整
        
    elif position_offset <= TRACK_ALIGNMENT_TOLERANCE * 2:
        # 基本对齐 - 位置微调 + 前进
        control_mode = "FINE_TUNING"
        
        final_lr = int(base_lr * 1.2)
        final_fb = int(MAX_FORWARD_SPEED * 0.7)
        final_yaw = int(yaw_control * 0.8)
        
    elif abs(angle_error) > DIRECTION_THRESHOLD * 2:
        # 方向偏差大 - 主要调整方向
        control_mode = "DIRECTION_CORRECTION"
        
        final_lr = int(base_lr * 0.5)
        final_fb = MIN_FORWARD_SPEED if abs(angle_error) < 45 else 0
        final_yaw = yaw_control
        
    else:
        # 位置偏差大 - 主要调整位置
        control_mode = "POSITION_CORRECTION"
        
        final_lr = base_lr
        final_fb = int(MAX_FORWARD_SPEED * 0.5)
        final_yaw = int(yaw_control * 0.7)
    
    # 转弯特殊处理
    if has_turn:
        print("检测到轨迹转弯，调整控制策略...")
        if control_mode == "ALIGNED_FORWARD":
            control_mode = "TURN_FOLLOWING"
            final_fb = int(final_fb * 0.6)  # 转弯时减速
            final_yaw = int(final_yaw * 1.3)  # 增强转向
        elif abs(angle_error) > 30:
            control_mode = "SHARP_TURN"
            final_fb = 0  # 急转弯时停止前进
            final_yaw = yaw_control
      # 限制控制范围
    final_lr = int(np.clip(final_lr, -MAX_LATERAL_SPEED, MAX_LATERAL_SPEED))
    final_fb = int(np.clip(final_fb, -MAX_FORWARD_SPEED, MAX_FORWARD_SPEED))
    final_yaw = int(np.clip(final_yaw, -MAX_YAW_SPEED, MAX_YAW_SPEED))
    
    # 运动趋势分析
    movement_trend = predictor.get_movement_trend()
    
    print(f"轨迹跟随控制: 模式={control_mode}, 偏移={position_offset:.1f}px, 角度误差={angle_error:.1f}°")
    print(f"控制输出: LR={final_lr}, FB={final_fb}, YAW={final_yaw}")
    
    return {
        "lr": final_lr,
        "fb": final_fb, 
        "yaw": final_yaw,
        "control_mode": control_mode,
        "alignment_score": alignment_score,
        "position_offset": position_offset,
        "angle_error": angle_error,
        "movement_trend": movement_trend,
        "has_turn": has_turn,
        "track_width": track_width,
        "status": "tracking"
    }

# ==================== 智能控制执行函数 ====================
def execute_smart_tracking_control(tello, control_result):
    """
    执行智能轨迹跟随控制
    根据不同的控制模式采用不同的执行策略
    """
    # 确保控制参数是Python原生int类型
    lr = int(control_result["lr"])
    fb = int(control_result["fb"])
    yaw = int(control_result["yaw"])
    
    control_mode = control_result["control_mode"]
    if control_mode == "ALIGNED_FORWARD":
        # 完美对齐 - 流畅前进
        tello.send_rc_control(
            lr,
            fb, 
            0,
            yaw
        )

        
    elif control_mode == "FINE_TUNING":
        # 微调模式 - 正常控制
        tello.send_rc_control(
            lr,
            fb,
            0, 
            yaw
        )

        
    elif control_mode == "DIRECTION_CORRECTION":
        # 方向修正 - 可能需要分步
        angle_error = abs(control_result.get("angle_error", 0))
        
        if angle_error > 45:
            # 大角度修正 - 分步执行
            print(f"执行大角度方向修正: {angle_error:.1f}°")
            
            # 第一步：停止前进，专注转向
            tello.send_rc_control(0, 0, 0, yaw)
            time.sleep(0.8)
            # 第二步：缓慢恢复前进
            tello.send_rc_control(
                int(lr * 0.5), 
                int(MIN_FORWARD_SPEED), 
                0, 
                int(yaw * 0.7)
            )
        else:
            # 中等角度修正
            tello.send_rc_control(
                lr,
                fb,
                0,
                yaw
            )
        

        
    elif control_mode == "POSITION_CORRECTION":
        # 位置修正
        tello.send_rc_control(
            lr,
            fb,
            0,
            yaw
        )

        
    elif control_mode in ["TURN_FOLLOWING", "SHARP_TURN"]:
        # 转弯处理
        if control_mode == "SHARP_TURN":
            print("执行急转弯跟随...")            # 急转弯：先转向再前进
            tello.send_rc_control(0, 0, 0, yaw)
            time.sleep(1.0)
            tello.send_rc_control(int(lr), int(MIN_FORWARD_SPEED), 0, 0)
        else:
            # 缓转弯：减速跟随
            tello.send_rc_control(
                lr,
                fb, 
                0,
                yaw
            )
        

        
    else:
        # 搜索模式
        tello.send_rc_control(0, 0, 0, 15)


# ==================== 增强可视化函数 ====================
def visualize_track_following(track_result, frame, control_result, coord_system, predictor):
    """
    可视化轨迹跟随状态 - 增强显示
    """
    height, width, _ = frame.shape
    center_x, center_y = width // 2, height // 2
    annotated_frame = frame.copy()
    
    # 显示二值化图像
    if "binary_image" in track_result:
        cv2.imshow("Track Binary", track_result["binary_image"])
    
    # 显示坐标系信息
    cv2.putText(annotated_frame, "Downward View - Left=Forward", 
               (10, height-80), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
    
    if track_result["found"]:
        # 根据控制模式选择颜色
        control_mode = control_result["control_mode"]
        alignment_score = control_result["alignment_score"]
        
        if control_mode == "ALIGNED_FORWARD":
            contour_color = (0, 255, 0)  # 绿色 - 完美对齐
            mode_text = "ALIGNED & FORWARD"
        elif control_mode == "FINE_TUNING":
            contour_color = (0, 255, 255)  # 黄色 - 微调
            mode_text = "FINE TUNING"
        elif control_mode == "DIRECTION_CORRECTION":
            contour_color = (0, 165, 255)  # 橙色 - 方向修正
            mode_text = "DIRECTION CORRECT"
        elif control_mode == "POSITION_CORRECTION":
            contour_color = (255, 0, 255)  # 紫色 - 位置修正
            mode_text = "POSITION CORRECT"
        elif control_mode in ["TURN_FOLLOWING", "SHARP_TURN"]:
            contour_color = (0, 0, 255)  # 红色 - 转弯
            mode_text = control_mode
        else:
            contour_color = (128, 128, 128)  # 灰色
            mode_text = control_mode
        
        # 绘制轨迹轮廓
        cv2.drawContours(annotated_frame, [track_result["contour"]], -1, contour_color, 3)
        
        # 绘制轨迹中心点
        track_center = track_result["center"]
        cv2.circle(annotated_frame, track_center, 8, (0, 0, 255), -1)
        cv2.circle(annotated_frame, track_center, 12, (255, 255, 255), 2)
        
        # 绘制无人机期望位置（图像中心）
        cv2.circle(annotated_frame, (center_x, center_y), 6, (255, 0, 0), -1)
        cv2.circle(annotated_frame, (center_x, center_y), 10, (255, 255, 255), 2)
        
        # 绘制偏移向量
        cv2.arrowedLine(annotated_frame, (center_x, center_y), track_center, (255, 255, 0), 2, tipLength=0.3)
        
        # 绘制轨迹方向箭头
        track_angle = track_result["track_angle"]
        angle_rad = np.radians(track_angle)
        arrow_length = 60
        
        end_x = int(track_center[0] + arrow_length * np.cos(angle_rad))
        end_y = int(track_center[1] + arrow_length * np.sin(angle_rad))
        cv2.arrowedLine(annotated_frame, track_center, (end_x, end_y), contour_color, 3, tipLength=0.4)
        
        # 绘制预测位置
        predicted_pos = predictor.predict_next_position()
        if predicted_pos and 0 <= predicted_pos[0] < width and 0 <= predicted_pos[1] < height:
            cv2.circle(annotated_frame, predicted_pos, 6, (0, 255, 255), 2)
            cv2.putText(annotated_frame, "PRED", (predicted_pos[0]-15, predicted_pos[1]-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        
        # 绘制对齐评分条
        score_bar_width = 150
        score_bar_height = 15
        score_bar_x = width - score_bar_width - 10
        score_bar_y = 10
        
        # 背景条
        cv2.rectangle(annotated_frame, (score_bar_x, score_bar_y), 
                     (score_bar_x + score_bar_width, score_bar_y + score_bar_height), (50, 50, 50), -1)
        
        # 分数条
        score_width = int((alignment_score / 100.0) * score_bar_width)
        score_color = (0, 255, 0) if alignment_score > 80 else (0, 255, 255) if alignment_score > 60 else (0, 165, 255)
        cv2.rectangle(annotated_frame, (score_bar_x, score_bar_y), 
                     (score_bar_x + score_width, score_bar_y + score_bar_height), score_color, -1)
        
        cv2.putText(annotated_frame, f"Alignment: {alignment_score:.0f}%", 
                   (score_bar_x, score_bar_y + score_bar_height + 15), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        # 显示详细信息
        info_lines = [
            f"Mode: {mode_text}",
            f"Position Offset: {control_result['position_offset']:.1f}px",
            f"Angle Error: {control_result['angle_error']:.1f}°",
            f"Track Size: {track_result['track_width']:.0f}x{track_result['track_length']:.0f}",
            f"Control: LR={control_result['lr']} FB={control_result['fb']} YAW={control_result['yaw']}"
        ]
        
        for i, text in enumerate(info_lines):
            y_pos = 30 + i * 18
            
            if i == 0:  # 模式
                color = contour_color
                thickness = 2
            elif i == 4:  # 控制指令
                color = (255, 0, 0)
                thickness = 2
            else:
                color = (255, 255, 255)
                thickness = 1
            
            cv2.putText(annotated_frame, text, (10, y_pos), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, thickness)
        
        # 显示运动趋势
        movement_trend = control_result.get("movement_trend", "unknown")
        cv2.putText(annotated_frame, f"Trend: {movement_trend}", 
                   (10, height - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
        
        # 转弯指示
        if track_result["has_turn"]:
            cv2.putText(annotated_frame, "TURN DETECTED!", 
                       (width//2-80, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        
        return annotated_frame, control_result
    else:
        # 未检测到轨迹
        reason = track_result.get("reason", "unknown")
        cv2.putText(annotated_frame, f"No track detected: {reason}", 
                   (center_x-120, center_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        # 显示搜索模式
        cv2.putText(annotated_frame, "SEARCHING MODE", 
                   (center_x-80, center_y+30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)
        
        return annotated_frame, {"lr": 0, "fb": 0, "yaw": 15, "control_mode": "SEARCHING"}

# ==================== 优化的主飞行测试函数 ====================
def test_optimized_track_following():
    global tello, vignette_corrector
    
    # 连接无人机
    print("Connecting to Tello...")
    try:
        tello = Tello()
        tello.connect()
        battery = tello.get_battery()
        print(f"Battery: {battery}%")
        if battery < 30:
            print("Battery too low, test cancelled!")
            return
    except Exception as e:
        print(f"Cannot connect to Tello: {e}")
        return
    
    # 初始化视频流
    print("Starting video stream...")
    try:
        tello.streamon()
        frame_read = tello.get_frame_read()
        time.sleep(2)
    except Exception as e:
        print(f"Video stream failed: {e}")
        return
    
    # 创建测试输出目录
    test_dir = ROOT / "optimized_track_test"
    test_dir.mkdir(exist_ok=True)
    
    # 初始化关键组件
    coord_system = DownwardCoordinateSystem(IMAGE_WIDTH, IMAGE_HEIGHT)
    predictor = TrajectoryPredictor(HISTORY_LENGTH)
    
    # 起飞前LED指示
    print("Preparing for takeoff...")

    
    try:
        # 执行起飞
        print("Taking off...")
        tello.takeoff()
        time.sleep(3)
        
        # 调整飞行高度
        FLIGHT_HEIGHT = 80  # 添加飞行高度变量定义
        print(f"Adjusting to flight height {FLIGHT_HEIGHT}cm...")
        current_height = tello.get_height()
        print(f"Current height: {current_height}cm")
        
        if current_height < FLIGHT_HEIGHT:
            height_diff = FLIGHT_HEIGHT - current_height
            tello.move_up(height_diff)
            time.sleep(2)
        
        # 切换到下视摄像头
        print("Switching to downward camera...")
        tello.set_video_direction(1)
        time.sleep(3)
        
        # 初始化暗角校正器
        print("Initializing vignette corrector...")
        VIGNETTE_STRENGTH = 0.8  # 添加暗角校正强度定义
        for i in range(10):
            frame = frame_read.frame
            if frame is not None:
                print(f"下视摄像头帧尺寸: {frame.shape}")
                vignette_corrector = VignetteCorrector(frame.shape, VIGNETTE_STRENGTH)
                print("暗角校正器初始化完成")
                break
            time.sleep(0.1)
        else:
            print("警告: 无法获取下视摄像头稳定帧")
            vignette_corrector = None
        
        # ==================== 优化的主循环 ====================
        start_time = time.time()
        frame_count = 0
        last_track_detected = time.time()
        last_safety_check = time.time()
        battery = tello.get_battery()
        height_cm = FLIGHT_HEIGHT  # 初始化高度变量
        tof_distance = 100  # 初始化距离传感器变量
        
        print("Starting OPTIMIZED Track Following with Trajectory Alignment...")
        print(f"Flight time: {AUTO_FLIGHT_TIME} seconds")
        print(f"Coordinate system: Left=Forward, Right=Backward, Up=Right, Down=Left")
        print(f"Alignment tolerance: {TRACK_ALIGNMENT_TOLERANCE}px")
        print(f"Direction threshold: ±{DIRECTION_THRESHOLD}°")
        print("Press Ctrl+C to emergency stop")
        
        while True:
            current_time = time.time()
            
            # 飞行时间限制
            # if current_time - start_time > AUTO_FLIGHT_TIME:
            #     print(f"Flight time limit reached ({AUTO_FLIGHT_TIME}s)")
            #     break
            
            # 获取当前帧
            frame = frame_read.frame
            if frame is None:
                print("No video frame received")
                time.sleep(0.1)
                continue
            
            frame = frame.copy()
            height, width = frame.shape[:2]
            
            # 更新坐标系统（如果图像尺寸变化）
            if width != coord_system.width or height != coord_system.height:
                coord_system = DownwardCoordinateSystem(width, height)
                print(f"更新坐标系: {width}x{height}")
            
            # 检查暗角校正器
            if vignette_corrector is None:
                vignette_corrector = VignetteCorrector(frame.shape, VIGNETTE_STRENGTH)
            
            # 定期安全检查
            if current_time - last_safety_check > AUTO_SAFETY_CHECK_INTERVAL:
                try:
                    battery = tello.get_battery()
                    tof_distance = tello.get_distance_tof()
                    height_cm = tello.get_height()
                    
                    if battery < 20:
                        print(f"Battery critically low: {battery}%, auto landing")
                        break
                    
                    if height_cm < 10:
                        print(f"Height too low: {height_cm}cm, emergency landing")
                        break
                    
                    if tof_distance < 15:
                        print(f"Obstacle too close: {tof_distance}cm, stopping")
                        tello.send_rc_control(0, 0, 0, 0)
                        time.sleep(1)
                        continue
                    
                    last_safety_check = current_time
                    
                except Exception as e:
                    print(f"Safety check error: {e}")
                    battery = 50
                    tof_distance = 100
                    height_cm = FLIGHT_HEIGHT
            
            # ==================== 核心轨迹跟随逻辑 ====================
            # 检测轨迹
            track_result = detect_track_optimized(frame)
            
            # 计算跟随控制
            control_result = calculate_track_following_control(track_result, coord_system, predictor)
            
            # 可视化
            annotated_frame, final_control = visualize_track_following(
                track_result, frame, control_result, coord_system, predictor
            )
            
            if track_result["found"]:
                last_track_detected = current_time
                
                # 显示轨迹跟随状态
                mode = control_result["control_mode"]
                score = control_result["alignment_score"]
                print(f"[轨迹跟随] 模式: {mode}, 对齐评分: {score:.1f}")
                
                # 执行智能控制
                execute_smart_tracking_control(tello, control_result)
                
            else:
                # 轨迹丢失处理
                if current_time - last_track_detected > 3:
                    print("[轨迹跟随] 长时间丢失轨迹，执行搜索...")
                    tello.send_rc_control(0, 0, 0, 20)

                else:
                    print("[轨迹跟随] 短暂丢失轨迹，悬停等待...")
                    tello.send_rc_control(0, 0, 0, 0)
            
            # 显示飞行信息
            remaining_time =  (current_time - start_time)
            cv2.putText(annotated_frame, f"OPTIMIZED Track Following - Time: {remaining_time:.0f}s", 
                       (width-350, height-60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            cv2.putText(annotated_frame, f"Battery: {battery}% | Height: {height_cm}cm", 
                       (width-250, height-40), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
            
            # 显示坐标系十字线
            cv2.line(annotated_frame, (width//2-15, height//2), (width//2+15, height//2), (255, 0, 0), 2)
            cv2.line(annotated_frame, (width//2, height//2-15), (width//2, height//2+15), (255, 0, 0), 2)
            
            # 显示主窗口
            cv2.imshow("Optimized Trajectory Following", annotated_frame)
            
            # 显示暗角校正对比
            if vignette_corrector is not None:
                comparison = vignette_corrector.visualize_correction(frame)
                if comparison is not None:
                    cv2.imshow("Vignette Correction", comparison)
            
            # 保存关键帧
            if frame_count % 90 == 0:  # 每3秒保存一帧
                frame_filename = test_dir / f"optimized_track_{frame_count}.jpg"
                cv2.imwrite(str(frame_filename), annotated_frame)
            
            # 检查退出
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC键
                print("Emergency stop requested")
                break
            
            frame_count += 1
            time.sleep(0.025)  # 稍微提高帧率
            
    except KeyboardInterrupt:
        print("Program interrupted by Ctrl+C")
    except Exception as e:
        print(f"Error during optimized track following: {e}")
        traceback.print_exc()
    finally:
        print("Stopping optimized track following, preparing to land...")
        
        try:
            tello.send_rc_control(0, 0, 0, 0)
            time.sleep(1)
            

            
            if tello.is_flying:
                print("Auto landing...")
                tello.land()
                time.sleep(3)
        except Exception as e:
            print(f"Landing error: {e}")
        
        print("Cleaning up...")
        safe_cleanup()

if __name__ == "__main__":
    test_optimized_track_following()
            # -*- coding: utf-8 -*-
