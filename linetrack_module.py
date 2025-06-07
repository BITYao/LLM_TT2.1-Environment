"""
精简巡线模块 - 用于无人机轨迹跟随
基于下视摄像头的轨迹检测和跟随控制
采用 linetrack3.py 的优化检测流程
"""
import cv2
import time
import numpy as np
import threading
import queue
from collections import deque
import traceback

# ==================== 暗角校正类 ====================
class VignetteCorrector:
    """无人机镜头暗角校正器"""
    
    def __init__(self, image_shape, vignette_strength=0.4):
        self.height, self.width = image_shape[:2]
        self.vignette_strength = vignette_strength
        self.correction_mask = self._create_correction_mask()
        print(f"暗角校正器初始化: {self.width}x{self.height}, 强度={vignette_strength}")
    
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

# ==================== 轨迹预测器 ====================
class TrajectoryPredictor:
    """轨迹预测器，用于预测性控制"""
    
    def __init__(self, history_length=5):
        self.position_history = deque(maxlen=history_length)
        self.direction_history = deque(maxlen=history_length)
        self.time_history = deque(maxlen=history_length)
    
    def add_observation(self, center_pos, direction_angle):
        """添加观测数据"""
        current_time = time.time()
        self.position_history.append(center_pos)
        self.direction_history.append(direction_angle)
        self.time_history.append(current_time)
    
    def predict_next_position(self, steps_ahead=3):
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

class DownwardCoordinateSystem:
    """下视图像坐标系转换和控制映射 - 与linetrack3.py一致"""
    
    def __init__(self, image_width=320, image_height=240):
        self.width = image_width
        self.height = image_height
        self.center_x = image_width // 2
        self.center_y = image_height // 2
        
        # 控制参数 - 与linetrack3.py保持一致
        self.lateral_deadzone = 8        # 左右控制死区
        self.forward_deadzone = 5        # 前后控制死区
        self.position_sensitivity = 0.4   # 位置控制敏感度
        self.direction_sensitivity = 0.8  # 方向控制敏感度
        self.max_forward_speed = 18      # 最大前进速度
        self.max_lateral_speed = 15      # 最大侧向速度
        self.max_yaw_speed = 20          # 最大偏航速度
        self.yaw_response_factor = 0.7   # 偏航响应系数
        
        print(f"下视坐标系初始化: {self.width}x{self.height}, 中心=({self.center_x}, {self.center_y})")
        print("坐标系映射: 左=前进, 右=后退, 上=右侧, 下=左侧")
    
    def image_to_drone_control(self, image_x, image_y):
        """将图像坐标转换为无人机控制指令 - 与linetrack3.py一致"""
        # 计算相对于图像中心的偏移
        offset_x = image_x - self.center_x  # 正值=右偏，负值=左偏
        offset_y = image_y - self.center_y  # 正值=下偏，负值=上偏
        
        # 坐标转换逻辑：
        # 图像X轴（左右）-> 无人机前后控制 (FB)
        # 图像Y轴（上下）-> 无人机左右控制 (LR)
        
        # FB控制：图像左偏（负X）= 前进，图像右偏（正X）= 后退
        fb_control = -offset_x * self.position_sensitivity
        
        # LR控制：图像上偏（负Y）= 右移，图像下偏（正Y）= 左移  
        lr_control = -offset_y * self.position_sensitivity
        
        # 应用死区
        if abs(fb_control) < self.forward_deadzone:
            fb_control = 0
        if abs(lr_control) < self.lateral_deadzone:
            lr_control = 0
        
        # 限制控制范围
        fb_control = np.clip(fb_control, -self.max_forward_speed, self.max_forward_speed)
        lr_control = np.clip(lr_control, -self.max_lateral_speed, self.max_lateral_speed)
        
        explanation = f"图像偏移({offset_x:.1f},{offset_y:.1f}) -> 控制(FB:{fb_control:.1f}, LR:{lr_control:.1f})"
        
        return {
            'lr': int(lr_control),
            'fb': int(fb_control),
            'offset_x': offset_x,
            'offset_y': offset_y,
            'explanation': explanation
        }
    
    def calculate_direction_control(self, line_angle, target_angle=0):
        """计算方向控制 - 与linetrack3.py一致"""
        # 角度偏差计算
        angle_error = line_angle - target_angle
        
        # 归一化到[-180, 180]
        while angle_error > 180:
            angle_error -= 360
        while angle_error < -180:
            angle_error += 360
        
        # 计算偏航控制
        yaw_control = angle_error * self.direction_sensitivity * self.yaw_response_factor
        yaw_control = np.clip(yaw_control, -self.max_yaw_speed, self.max_yaw_speed)
        
        return int(yaw_control), angle_error

# ==================== 方向优化函数 ====================
def normalize_angle_to_forward_reference(angle):
    """将角度归一化为以前进方向为参考的角度"""
    normalized = angle
    if normalized > 180:
        normalized -= 360
    return normalized

def calculate_direction_score(normalized_angle):
    """计算方向评分，前进方向(0度)得分最高"""
    angle_diff = abs(normalized_angle)
    if angle_diff > 180:
        angle_diff = 360 - angle_diff
    
    # 前向方向得分最高
    direction_tolerance = 35
    forward_direction_bias = 2.5
    
    if angle_diff <= direction_tolerance:
        return forward_direction_bias
    elif angle_diff <= 90:
        return 1.0 - (angle_diff / 90.0)
    else:
        return 0

def detect_turn_improved(contour, points):
    """改进的转弯检测算法"""
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

class LineTrackModule:
    """精简巡线模块 - 采用linetrack3.py优化流程"""
    
    def __init__(self, tello_controller):
        self.tello_controller = tello_controller
        self.single_tello = tello_controller.single_tello
        
        # 线程控制
        self.tracking_thread = None
        self.is_tracking = False
        self.track_lock = threading.Lock()
        
        # 视频流相关
        self.frame_read = None
        self.current_frame = None
        self.frame_queue = queue.Queue(maxsize=5)
        
        # 图像尺寸配置
        self.expected_width = 320
        self.expected_height = 240
        
        # 控制系统 - 使用增强版本
        self.coord_system = DownwardCoordinateSystem(self.expected_width, self.expected_height)
        self.predictor = TrajectoryPredictor(history_length=5)
        
        # 暗角校正器
        self.vignette_corrector = None
        self.enable_vignette_correction = True
        
        # 裁剪边缘参数
        self.crop_margin = 20
        
        # 控制参数
        self.track_alignment_tolerance = 3.0
        self.direction_threshold = 12.0
        self.min_forward_speed = 6
        
        # 巡线状态
        self.track_detected = False
        self.last_track_time = 0
        self.control_mode = "SEARCHING"
        self.alignment_score = 0
        
        print("✓ 巡线模块初始化完成（采用linetrack3优化流程）")
    
    def validate_and_crop_frame(self, frame):
        """验证并裁切图像到标准尺寸"""
        if frame is None:
            return None
        
        try:
            current_height, current_width = frame.shape[:2]
            
            # 检查图像尺寸是否异常
            if current_width != self.expected_width or current_height != self.expected_height:
                print(f"⚠ 检测到异常图像尺寸: {current_width}x{current_height}，正在裁切为 {self.expected_width}x{self.expected_height}")
                
                # 如果宽度不匹配，从中心裁切
                if current_width != self.expected_width:
                    if current_width > self.expected_width:
                        # 从中心裁切宽度
                        start_x = (current_width - self.expected_width) // 2
                        frame = frame[:, start_x:start_x + self.expected_width]
                    else:
                        # 宽度不足，填充黑色边缘
                        pad_x = (self.expected_width - current_width) // 2
                        frame = cv2.copyMakeBorder(frame, 0, 0, pad_x, self.expected_width - current_width - pad_x, 
                                                 cv2.BORDER_CONSTANT, value=(0, 0, 0))
                
                # 更新当前尺寸
                current_height, current_width = frame.shape[:2]
                
                # 如果高度异常（特别是下方多出绿色像素的情况），从顶部裁切
                if current_height != self.expected_height:
                    if current_height > self.expected_height:
                        # 从顶部裁切到标准高度（避免底部绿色像素干扰）
                        frame = frame[:self.expected_height, :]
                        print(f"✓ 已从顶部裁切图像，移除底部 {current_height - self.expected_height} 行异常像素")
                    else:
                        # 高度不足，填充黑色边缘
                        pad_y = (self.expected_height - current_height) // 2
                        frame = cv2.copyMakeBorder(frame, pad_y, self.expected_height - current_height - pad_y, 0, 0,
                                                 cv2.BORDER_CONSTANT, value=(0, 0, 0))
                
                # 最终确保尺寸正确
                final_height, final_width = frame.shape[:2]
                if final_width != self.expected_width or final_height != self.expected_height:
                    frame = cv2.resize(frame, (self.expected_width, self.expected_height))
                    print(f"✓ 强制调整图像尺寸为 {self.expected_width}x{self.expected_height}")
            
            return frame
            
        except Exception as e:
            print(f"❌ 图像裁切处理失败: {e}")
            return None
    
    def detect_track_optimized(self, frame):
        """
        优化的轨迹检测函数 - 采用linetrack3.py的检测流程
        """
        if frame is None:
            return {"found": False, "reason": "no_frame"}
        
        # 首先验证和裁切图像
        validated_frame = self.validate_and_crop_frame(frame)
        if validated_frame is None:
            return {"found": False, "reason": "frame_validation_failed"}
        
        try:
            # 步骤1: 暗角校正
            if self.vignette_corrector is not None and self.enable_vignette_correction:
                corrected_frame = self.vignette_corrector.correct_vignette(validated_frame)
            else:
                corrected_frame = validated_frame
            
            # 步骤2：裁剪边缘，去除暗角或误差区域
            height, width = corrected_frame.shape[:2]
            if height > self.crop_margin * 2 and width > self.crop_margin * 2:
                cropped_frame = corrected_frame[self.crop_margin:height-self.crop_margin, 
                                              self.crop_margin:width-self.crop_margin]
            else:
                cropped_frame = corrected_frame
            
            # 步骤3: 转换为灰度图
            gray = cv2.cvtColor(cropped_frame, cv2.COLOR_BGR2GRAY)
            
            # 步骤4: 高斯模糊
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # 步骤5: 使用固定阈值方法
            _, binary = cv2.threshold(blurred, 50, 255, cv2.THRESH_BINARY_INV)
            
            # 检查二值化结果
            white_pixels = np.sum(binary == 255)
            total_pixels = binary.shape[0] * binary.shape[1]
            white_ratio = white_pixels / total_pixels
            
            if white_ratio < 0.001:
                return {"found": False, "reason": "no_white_pixels", "binary": binary, "validated_frame": validated_frame}
            
            # 步骤6: 优化的形态学处理
            kernel_small = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            kernel_medium = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            
            # 轻微的开运算去除小噪声
            binary_cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_small, iterations=1)
            # 轻微的闭运算连接断裂
            binary_cleaned = cv2.morphologyEx(binary_cleaned, cv2.MORPH_CLOSE, kernel_medium, iterations=1)
            
            # 检查形态学处理后的结果
            white_pixels_after = np.sum(binary_cleaned == 255)
            white_ratio_after = white_pixels_after / total_pixels
            
            if white_ratio_after < 0.0005:
                binary_cleaned = binary
            
            # 步骤7: 轮廓检测
            contours, _ = cv2.findContours(binary_cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                return {"found": False, "reason": "no_contours", "binary": binary_cleaned, "validated_frame": validated_frame}
            
            # 步骤8: 改进的轨迹候选筛选 - 加入方向优先级
            valid_tracks = []
            
            for i, contour in enumerate(contours):
                area = cv2.contourArea(contour)
                
                # 面积筛选
                if area < 30 or area > 2500:
                    continue
                
                # 检查轮廓是否主要由白色像素组成
                mask = np.zeros(binary_cleaned.shape, dtype=np.uint8)
                cv2.fillPoly(mask, [contour], 255)
                white_in_contour = np.sum((binary_cleaned == 255) & (mask == 255))
                contour_area_pixels = np.sum(mask == 255)
                
                if contour_area_pixels > 0:
                    white_ratio_in_contour = white_in_contour / contour_area_pixels
                    
                    # 主要由白色像素组成的区域
                    if white_ratio_in_contour > 0.5:
                        # 计算几何特征
                        rect = cv2.minAreaRect(contour)
                        width_rect, height_rect = rect[1]
                        
                        if width_rect > 0 and height_rect > 0:
                            aspect_ratio = max(width_rect, height_rect) / min(width_rect, height_rect)
                            
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
                            
                            # 归一化角度
                            track_angle = track_angle % 360
                            normalized_angle = normalize_angle_to_forward_reference(track_angle)
                            direction_score = calculate_direction_score(normalized_angle)
                            
                            # 计算填充度
                            hull = cv2.convexHull(contour)
                            hull_area = cv2.contourArea(hull)
                            solidity = area / hull_area if hull_area > 0 else 0
                            
                            # 改进的评分系统
                            score = 0
                            
                            # 长宽比评分
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
                            
                            # 方向评分
                            score += direction_score
                            
                            if score >= 2:
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
                                    'width': width_rect,
                                    'height': height_rect
                                })
            
            if not valid_tracks:
                return {"found": False, "reason": "no_valid_tracks", "binary": binary_cleaned, "validated_frame": validated_frame}
            
            # 步骤9: 选择最佳轨迹
            if len(valid_tracks) == 1:
                best_track = valid_tracks[0]
            else:
                # 多个候选时，按总评分排序
                valid_tracks.sort(key=lambda x: x['score'], reverse=True)
                best_track = valid_tracks[0]
                
                # 如果存在前向方向的轨迹，优先选择
                forward_candidates = [track for track in valid_tracks if track['direction_score'] >= 2.5]
                if forward_candidates and best_track['direction_score'] < 2.5:
                    best_forward = max(forward_candidates, key=lambda x: x['score'])
                    if best_forward['score'] >= best_track['score'] * 0.8:
                        best_track = best_forward
            
            contour = best_track['contour']
            
            # 步骤10: 计算轨迹中心和特征
            M = cv2.moments(contour)
            
            if M["m00"] == 0:
                return {"found": False, "reason": "zero_moment", "binary": binary_cleaned, "validated_frame": validated_frame}
            
            # 计算轨迹中心点（需要加上裁剪偏移）
            cx = int(M["m10"] / M["m00"]) + self.crop_margin
            cy = int(M["m01"] / M["m00"]) + self.crop_margin
            
            # 轨迹方向角度
            track_angle = best_track['track_angle']
            
            # 计算轨迹宽度
            track_width = min(best_track['width'], best_track['height'])
            track_length = max(best_track['width'], best_track['height'])
            
            # 转弯检测
            points = contour.reshape(-1, 2)
            has_turn = detect_turn_improved(contour, points)
            
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
                "binary": binary_cleaned,
                "validated_frame": validated_frame,
                "track_info": best_track,
                "candidates_count": len(valid_tracks),
                "area": best_track['area'],
                "aspect_ratio": best_track['aspect_ratio'],
                "solidity": best_track['solidity']
            }
            
        except Exception as e:
            print(f"优化轨迹检测错误: {e}")
            return {"found": False, "reason": f"error: {e}", "validated_frame": validated_frame}
    
    def detect_track(self, frame):
        """轨迹检测 - 使用优化版本"""
        return self.detect_track_optimized(frame)
    
    def calculate_track_following_control(self, track_result):
        """
        计算轨迹跟随控制指令 - 采用linetrack3.py的控制逻辑
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
        has_turn = track_result.get("has_turn", False)
        
        # 添加到预测器
        self.predictor.add_observation(track_center, track_angle)
        
        # 基础位置控制
        position_control = self.coord_system.image_to_drone_control(track_center[0], track_center[1])
        base_lr = position_control['lr']
        base_fb = position_control['fb']
        
        # 方向控制
        yaw_control, angle_error = self.coord_system.calculate_direction_control(track_angle, 0)
        
        # 计算对齐评分
        position_offset = np.sqrt(position_control['offset_x']**2 + position_control['offset_y']**2)
        alignment_score = max(0, 100 - position_offset * 2 - abs(angle_error))
        
        # 根据对齐情况决定控制模式
        if position_offset <= self.track_alignment_tolerance and abs(angle_error) <= self.direction_threshold:
            # 完美对齐
            control_mode = "ALIGNED_FORWARD"
            
            # 预测性控制
            predicted_pos = self.predictor.predict_next_position()
            if predicted_pos:
                future_control = self.coord_system.image_to_drone_control(predicted_pos[0], predicted_pos[1])
                final_lr = int(base_lr * 0.7 + future_control['lr'] * 0.3)
                final_fb = max(self.min_forward_speed, int(base_fb * 0.5 + self.coord_system.max_forward_speed * 0.8))
            else:
                final_lr = base_lr
                final_fb = max(self.min_forward_speed, self.coord_system.max_forward_speed)
            
            final_yaw = int(yaw_control * 0.6)
            
        elif position_offset <= self.track_alignment_tolerance * 2:
            # 基本对齐
            control_mode = "FINE_TUNING"
            
            final_lr = int(base_lr * 1.2)
            final_fb = int(self.coord_system.max_forward_speed * 0.7)
            final_yaw = int(yaw_control * 0.8)
            
        elif abs(angle_error) > self.direction_threshold * 2:
            # 方向偏差大
            control_mode = "DIRECTION_CORRECTION"
            
            final_lr = int(base_lr * 0.5)
            final_fb = self.min_forward_speed if abs(angle_error) < 45 else 0
            final_yaw = yaw_control
            
        else:
            # 位置偏差大
            control_mode = "POSITION_CORRECTION"
            
            final_lr = base_lr
            final_fb = int(self.coord_system.max_forward_speed * 0.5)
            final_yaw = int(yaw_control * 0.7)
        
        # 转弯特殊处理
        if has_turn:
            if control_mode == "ALIGNED_FORWARD":
                control_mode = "TURN_FOLLOWING"
                final_fb = int(final_fb * 0.6)
                final_yaw = int(final_yaw * 1.3)
            elif abs(angle_error) > 30:
                control_mode = "SHARP_TURN"
                final_fb = 0
                final_yaw = yaw_control
        
        # 限制控制范围
        final_lr = int(np.clip(final_lr, -self.coord_system.max_lateral_speed, self.coord_system.max_lateral_speed))
        final_fb = int(np.clip(final_fb, -self.coord_system.max_forward_speed, self.coord_system.max_forward_speed))
        final_yaw = int(np.clip(final_yaw, -self.coord_system.max_yaw_speed, self.coord_system.max_yaw_speed))
        
        # 运动趋势分析
        movement_trend = self.predictor.get_movement_trend()
        
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
    
    def calculate_control(self, track_result):
        """计算巡线控制指令 - 使用增强版本"""
        return self.calculate_track_following_control(track_result)
    
    def execute_smart_tracking_control(self, control_result):
        """执行智能轨迹跟随控制"""
        lr = int(control_result["lr"])
        fb = int(control_result["fb"])
        yaw = int(control_result["yaw"])
        
        control_mode = control_result["control_mode"]
        
        if control_mode == "DIRECTION_CORRECTION":
            angle_error = abs(control_result.get("angle_error", 0))
            
            if angle_error > 45:
                # 大角度修正 - 分步执行
                self.single_tello.send_rc_control(0, 0, 0, yaw)
                time.sleep(0.8)
                self.single_tello.send_rc_control(
                    int(lr * 0.5),
                    int(self.min_forward_speed),
                    0,
                    int(yaw * 0.7)
                )
            else:
                self.single_tello.send_rc_control(lr, fb, 0, yaw)
        elif control_mode == "SHARP_TURN":
            # 急转弯：先转向再前进
            self.single_tello.send_rc_control(0, 0, 0, yaw)
            time.sleep(1.0)
            self.single_tello.send_rc_control(int(lr), int(self.min_forward_speed), 0, 0)
        else:
            # 正常控制
            self.single_tello.send_rc_control(lr, fb, 0, yaw)
    
    def visualize_tracking(self, frame, track_result, control_result):
        """可视化巡线状态 - 增强版本"""
        # 优先使用验证后的帧
        if "validated_frame" in track_result and track_result["validated_frame"] is not None:
            working_frame = track_result["validated_frame"]
        elif frame is not None:
            working_frame = self.validate_and_crop_frame(frame)
        else:
            return None
        
        if working_frame is None:
            return None
        
        annotated_frame = working_frame.copy()
        height, width = annotated_frame.shape[:2]
        center_x, center_y = width // 2, height // 2
        
        # 显示坐标系十字线
        cv2.line(annotated_frame, (center_x-15, center_y), (center_x+15, center_y), (255, 0, 0), 2)
        cv2.line(annotated_frame, (center_x, center_y-15), (center_x, center_y+15), (255, 0, 0), 2)
        cv2.circle(annotated_frame, (center_x, center_y), 6, (255, 0, 0), -1)
        
        # 显示坐标系信息
        cv2.putText(annotated_frame, "Downward View - Left=Forward", 
                   (10, height-80), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        cv2.putText(annotated_frame, f"Size: {width}x{height}", 
                   (width-100, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        
        if track_result["found"]:
            # 根据控制模式选择颜色
            control_mode = control_result["control_mode"]
            alignment_score = control_result["alignment_score"]
            
            if control_mode == "ALIGNED_FORWARD":
                contour_color = (0, 255, 0)  # 绿色
                mode_text = "ALIGNED & FORWARD"
            elif control_mode == "FINE_TUNING":
                contour_color = (0, 255, 255)  # 黄色
                mode_text = "FINE TUNING"
            elif control_mode == "DIRECTION_CORRECTION":
                contour_color = (0, 165, 255)  # 橙色
                mode_text = "DIRECTION CORRECT"
            elif control_mode == "POSITION_CORRECTION":
                contour_color = (255, 0, 255)  # 紫色
                mode_text = "POSITION CORRECT"
            elif control_mode in ["TURN_FOLLOWING", "SHARP_TURN"]:
                contour_color = (0, 0, 255)  # 红色
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
            predicted_pos = self.predictor.predict_next_position()
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
            if track_result.get("has_turn", False):
                cv2.putText(annotated_frame, "TURN DETECTED!", 
                           (width//2-80, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            
        else:
            # 未检测到轨迹
            reason = track_result.get("reason", "unknown")
            cv2.putText(annotated_frame, f"No track detected: {reason}", 
                       (center_x-120, center_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            
            # 显示搜索模式
            cv2.putText(annotated_frame, "SEARCHING MODE", 
                       (center_x-80, center_y+30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)
        
        # 显示标题
        cv2.putText(annotated_frame, "Optimized Line Tracking (linetrack3.py algorithm)", 
                   (10, height-20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
        
        return annotated_frame
    
    def tracking_worker(self):
        """巡线工作线程 - 增强版本"""
        print("🚁 巡线线程启动（采用linetrack3优化算法）")
        
        try:
            while self.is_tracking and self.tello_controller.connected:
                # 获取当前帧
                frame = None
                if self.frame_read:
                    frame = self.frame_read.frame
                
                if frame is not None:
                    # 初始化暗角校正器
                    if self.vignette_corrector is None:
                        self.vignette_corrector = VignetteCorrector(frame.shape, 0.4)
                        print("✓ 暗角校正器已初始化")
                    
                    # 验证图像尺寸
                    original_shape = frame.shape
                    validated_frame = self.validate_and_crop_frame(frame)
                    
                    if validated_frame is not None:
                        self.current_frame = validated_frame.copy()
                        
                        # 如果图像被修正，记录日志
                        if validated_frame.shape != original_shape:
                            print(f"📐 图像已修正: {original_shape} -> {validated_frame.shape}")
                        
                        # 使用优化的轨迹检测
                        track_result = self.detect_track_optimized(validated_frame)
                        
                        # 使用增强的控制计算
                        control_result = self.calculate_track_following_control(track_result)
                        
                        # 增强的可视化
                        annotated_frame = self.visualize_tracking(validated_frame, track_result, control_result)
                        
                        # 显示结果
                        if annotated_frame is not None:
                            cv2.imshow("Line Tracking", annotated_frame)
                            
                            # 显示二值化图像
                            if "binary" in track_result:
                                cv2.imshow("Track Binary", track_result["binary"])
                            
                            cv2.waitKey(1)
                        
                        # 更新状态
                        with self.track_lock:
                            self.track_detected = track_result["found"]
                            self.control_mode = control_result["control_mode"]
                            self.alignment_score = control_result["alignment_score"]
                            
                            if track_result["found"]:
                                self.last_track_time = time.time()
                        
                        # 执行智能控制（仅在飞行时）
                        if self.tello_controller.flying:
                            try:
                                self.execute_smart_tracking_control(control_result)
                            except Exception as e:
                                print(f"智能巡线控制发送失败: {e}")
                    else:
                        print("⚠ 图像验证失败，跳过本帧")
                
                time.sleep(0.033)  # 约30fps
                
        except Exception as e:
            print(f"巡线线程错误: {e}")
            traceback.print_exc()
        finally:
            print("🚁 巡线线程退出")
            cv2.destroyAllWindows()
    
    def start_line_tracking(self):
        """启动巡线模式 - 增强版本"""
        if self.is_tracking:
            print("⚠ 巡线模式已在运行")
            return False
        
        if not self.tello_controller.connected:
            print("❌ Tello未连接，无法启动巡线")
            return False
        
        try:
            print("🎥 切换到下视摄像头...")
            self.single_tello.set_video_direction(1)  # 下视摄像头
            time.sleep(2)
            
            # 启动视频流
            print("📹 启动视频流...")
            self.single_tello.streamon()
            time.sleep(1)
            
            self.frame_read = self.single_tello.get_frame_read()
            time.sleep(1)
            
            # 等待视频流稳定并验证图像质量
            print("🔍 验证下视摄像头图像质量...")
            stable_frames = 0
            for i in range(15):
                frame = self.frame_read.frame
                if frame is not None:
                    validated_frame = self.validate_and_crop_frame(frame)
                    if validated_frame is not None and validated_frame.shape[:2] == (self.expected_height, self.expected_width):
                        stable_frames += 1
                        if stable_frames >= 3:
                            print(f"✓ 下视摄像头就绪，稳定分辨率: {validated_frame.shape}")
                            # 初始化暗角校正器
                            self.vignette_corrector = VignetteCorrector(validated_frame.shape, 0.4)
                            print("✓ 暗角校正器已初始化")
                            break
                    else:
                        stable_frames = 0
                        print(f"⚠ 图像异常，重试... ({i+1}/15)")
                time.sleep(0.5)
            else:
                print("❌ 下视摄像头图像质量不稳定，但继续尝试启动")
            
            # 启动巡线线程
            self.is_tracking = True
            self.tracking_thread = threading.Thread(target=self.tracking_worker, daemon=True)
            self.tracking_thread.start()
            
            print("✅ 巡线模式启动成功（采用linetrack3.py优化算法）")
            return True
            
        except Exception as e:
            print(f"❌ 启动巡线模式失败: {e}")
            self.is_tracking = False
            return False
    
    def stop_line_tracking(self):
        """停止巡线模式"""
        if not self.is_tracking:
            print("⚠ 巡线模式未运行")
            return
        
        print("🛑 停止巡线模式...")
        self.is_tracking = False
        
        # 停止移动
        try:
            if self.tello_controller.flying:
                self.single_tello.send_rc_control(0, 0, 0, 0)
        except:
            pass
        
        # 等待线程结束
        if self.tracking_thread:
            self.tracking_thread.join(timeout=3)
        
        # 关闭窗口
        cv2.destroyAllWindows()
        
        # 切换回前视摄像头
        try:
            print("🎥 切换回前视摄像头...")
            self.single_tello.set_video_direction(0)
            time.sleep(1)
        except Exception as e:
            print(f"切换摄像头失败: {e}")
        
        print("✅ 巡线模式已停止")
    
    def get_tracking_status(self):
        """获取巡线状态 - 增强版本"""
        with self.track_lock:
            if not self.is_tracking:
                return "未启动"
            elif self.track_detected:
                return f"跟踪中 | 模式: {self.control_mode} | 评分: {self.alignment_score:.0f}%"
            else:
                lost_time = time.time() - self.last_track_time
                return f"搜索中 | 丢失: {lost_time:.1f}s"
    
    def cleanup(self):
        """清理资源"""
        self.stop_line_tracking()
        print("✓ 巡线模块已清理")
