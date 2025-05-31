"""
Tello无人机控制器
"""
from djitellopy import Tello
import cv2
import threading
import time
from config import TELLO_IP

class TelloController:
    def __init__(self):
        self.tello = None
        self.connected = False
        self.flying = False
        self.video_stream = None
        self.emergency_stop = False
        
    def connect(self):
        """连接到Tello无人机"""
        try:
            self.tello = Tello()
            self.tello.connect()
            
            # 获取无人机信息
            battery = self.tello.get_battery()
            print(f"Tello连接成功！电池电量: {battery}%")
            
            self.connected = True
            return True
            
        except Exception as e:
            print(f"Tello连接失败: {e}")
            self.connected = False
            return False
    
    def execute_command(self, command):
        """执行无人机命令"""
        if not self.connected:
            print("无人机未连接")
            return False
        
        if self.emergency_stop:
            print("紧急停止模式，忽略命令")
            return False
        
        try:
            command_parts = command.split()
            cmd = command_parts[0].lower()
            
            if cmd == "takeoff":
                if not self.flying:
                    self.tello.takeoff()
                    self.flying = True
                    print("无人机起飞")
                else:
                    print("无人机已在飞行中")
                    
            elif cmd == "land":
                if self.flying:
                    self.tello.land()
                    self.flying = False
                    print("无人机降落")
                else:
                    print("无人机未在飞行中")
                    
            elif cmd == "stop":
                self.emergency_stop = True
                if self.flying:
                    self.tello.emergency()
                    self.flying = False
                print("紧急停止！")
                
            elif self.flying:  # 只有在飞行中才执行移动命令
                if cmd == "up" and len(command_parts) == 2:
                    distance = int(command_parts[1])
                    distance = max(20, min(500, distance))  # 限制范围
                    self.tello.move_up(distance)
                    print(f"向上飞行 {distance}cm")
                    
                elif cmd == "down" and len(command_parts) == 2:
                    distance = int(command_parts[1])
                    distance = max(20, min(500, distance))
                    self.tello.move_down(distance)
                    print(f"向下飞行 {distance}cm")
                    
                elif cmd == "left" and len(command_parts) == 2:
                    distance = int(command_parts[1])
                    distance = max(20, min(500, distance))
                    self.tello.move_left(distance)
                    print(f"向左飞行 {distance}cm")
                    
                elif cmd == "right" and len(command_parts) == 2:
                    distance = int(command_parts[1])
                    distance = max(20, min(500, distance))
                    self.tello.move_right(distance)
                    print(f"向右飞行 {distance}cm")
                    
                elif cmd == "forward" and len(command_parts) == 2:
                    distance = int(command_parts[1])
                    distance = max(20, min(500, distance))
                    self.tello.move_forward(distance)
                    print(f"向前飞行 {distance}cm")
                    
                elif cmd == "back" and len(command_parts) == 2:
                    distance = int(command_parts[1])
                    distance = max(20, min(500, distance))
                    self.tello.move_back(distance)
                    print(f"向后飞行 {distance}cm")
                    
                elif cmd == "rotate_cw" and len(command_parts) == 2:
                    angle = int(command_parts[1])
                    angle = max(1, min(360, angle))
                    self.tello.rotate_clockwise(angle)
                    print(f"顺时针旋转 {angle}度")
                    
                elif cmd == "rotate_ccw" and len(command_parts) == 2:
                    angle = int(command_parts[1])
                    angle = max(1, min(360, angle))
                    self.tello.rotate_counter_clockwise(angle)
                    print(f"逆时针旋转 {angle}度")
                    
                elif cmd == "flip" and len(command_parts) == 2:
                    direction = command_parts[1].lower()
                    if direction in ['l', 'r', 'f', 'b']:
                        self.tello.flip(direction)
                        print(f"翻滚: {direction}")
                    else:
                        print("翻滚方向错误")
                        
                else:
                    print(f"未知命令: {command}")
                    return False
            else:
                print("无人机未在飞行中，无法执行移动命令")
                return False
                
            return True
            
        except Exception as e:
            print(f"命令执行错误: {e}")
            return False
    
    def get_status(self):
        """获取无人机状态"""
        if not self.connected:
            return "未连接"
        
        try:
            battery = self.tello.get_battery()
            height = self.tello.get_height()
            temp = self.tello.get_temperature()
            
            status = f"电池: {battery}% | 高度: {height}cm | 温度: {temp}°C | 飞行状态: {'飞行中' if self.flying else '地面'}"
            return status
        except:
            return "状态获取失败"
    
    def start_video_stream(self):
        """启动视频流"""
        if not self.connected:
            return False
            
        try:
            self.tello.streamon()
            self.video_stream = self.tello.get_frame_read()
            print("视频流已启动")
            return True
        except Exception as e:
            print(f"视频流启动失败: {e}")
            return False
    
    def get_frame(self):
        """获取视频帧"""
        if self.video_stream:
            return self.video_stream.frame
        return None
    
    def diagnose_video_stream(self):
        """诊断视频流状态"""
        try:
            print("🔍 开始视频流诊断...")
            
            if not hasattr(self, 'vision_module') or not self.vision_module:
                print("❌ 视觉模块未初始化")
                return False
            
            # 获取详细状态
            status = self.vision_module.get_stream_status()
            
            print(f"📊 视频流状态:")
            print(f"   流状态: {'开启' if status['streaming'] else '关闭'}")
            print(f"   帧读取器: {'存在' if status['frame_reader_exists'] else '不存在'}")
            print(f"   当前帧: {'有效' if status['current_frame_valid'] else '无效'}")
            print(f"   帧尺寸: {status['frame_shape']}")
            
            # 如果视频流有问题，尝试重启
            if status['streaming'] and not status['current_frame_valid']:
                print("⚠ 检测到视频流异常，尝试重启...")
                return self.vision_module.restart_video_stream()
            
            return status['streaming'] and status['current_frame_valid']
            
        except Exception as e:
            print(f"❌ 视频流诊断失败: {e}")
            return False
    
    def disconnect(self):
        """断开连接"""
        try:
            if self.flying:
                self.tello.land()
            if self.video_stream:
                self.tello.streamoff()
            self.connected = False
            print("Tello连接已断开")
        except:
            pass