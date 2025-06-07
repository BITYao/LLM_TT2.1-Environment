"""
扩展的Tello控制器 - 包含LED、点阵屏和视觉感知功能
"""
import time
import re
from djitellopy import TelloSwarm
from config import LED_COLOR_MAP, CHINESE_TO_ENGLISH
from cruise_module import CruiseModule
from vision_module import VisionModule
from linetrack_module import LineTrackModule

class TelloExtendedController:
    def __init__(self, tello_ip="192.168.14.180"):
        self.tello_ip = tello_ip
        self.swarm = None
        self.single_tello = None
        self.connected = False
        self.flying = False
        self.cruise_module = None
        self.vision_module = None
        self.linetrack_module = None
    
    def connect(self):
        """连接到Tello（编队模式）"""
        try:
            print(f"尝试连接到Tello IP: {self.tello_ip}")
            
            # 使用编队模式连接单机
            self.swarm = TelloSwarm.fromIps([self.tello_ip])
            self.swarm.connect()
            
            # 获取单机对象
            self.single_tello = self.swarm.tellos[0]
            
            # 检查电池
            battery = self.single_tello.get_battery()
            print(f"✓ Tello连接成功（编队模式）！电池电量: {battery}%")
            
            if battery < 20:
                print("⚠ 电池电量过低，请充电后再飞行")
                choice = input("是否继续？(y/n): ")
                if choice.lower() != 'y':
                    return False
            
            self.connected = True
            
            # 初始化巡航模块
            self.cruise_module = CruiseModule(self.single_tello)
            print("✓ 巡航模块已初始化")
            
            # 初始化视觉感知模块 - 传入编队模式下的单机实例
            self.vision_module = VisionModule(self.single_tello)
            print("✓ 视觉感知模块已初始化（编队模式兼容）")
            
            # 初始化巡线模块
            self.linetrack_module = LineTrackModule(self)
            print("✓ 巡线模块已初始化")
            
            # 测试视频流连接（可选）
            print("🔍 测试视频流连接...")
            if self.vision_module.start_video_stream():
                print("✓ 视频流测试成功")
                # 立即停止测试流，避免占用资源
                self.vision_module.stop_video_stream()
            else:
                print("⚠ 视频流测试失败，但不影响其他功能")
            
            return True
            
        except Exception as e:
            print(f"✗ Tello连接失败: {e}")
            print("请检查：")
            print("- Tello是否已开启编队模式")
            print("- IP地址是否正确")
            print("- 是否在同一网络下")
            return False
    
    def disconnect(self):
        """断开连接"""
        try:
            # 清理视觉模块
            if self.vision_module:
                print("🔍 清理视觉感知模块...")
                self.vision_module.cleanup()
            
            # 清理巡线模块
            if self.linetrack_module:
                print("🚁 清理巡线模块...")
                self.linetrack_module.cleanup()
            
            if self.flying and self.connected:
                print("🛬 无人机正在降落...")
                self.single_tello.land()
                time.sleep(3)
                self.flying = False
                print("✅ 无人机已安全降落")
            
            if self.swarm:
                print("🔌 断开编队连接...")
                self.swarm.end()
                print("✅ 编队连接已断开")
                
        except Exception as e:
            print(f"⚠ 断开连接时出错: {e}")
    
    def get_battery(self):
        """获取电池电量"""
        if not self.connected:
            return 0
        try:
            return self.single_tello.get_battery()
        except:
            return 0
    
    def get_status(self):
        """获取状态信息（包含巡线状态）"""
        if not self.connected:
            return "未连接"
        
        try:
            battery = self.get_battery()
            
            # 获取巡航状态
            cruise_status = ""
            if self.cruise_module:
                cruise_status = f" | 巡航: {self.cruise_module.get_cruise_status()}"
            
            # 获取视觉状态
            vision_status = ""
            if self.vision_module:
                vision_status = f" | 视觉: {self.vision_module.get_vision_status()}"
            
            # 获取巡线状态
            linetrack_status = ""
            if self.linetrack_module:
                linetrack_status = f" | 巡线: {self.linetrack_module.get_tracking_status()}"
            
            status = f"电池: {battery}% | 飞行状态: {'飞行中' if self.flying else '地面'}{cruise_status}{vision_status}{linetrack_status} | 模式: 复合指令控制"
            return status
        except:
            return "状态获取失败"
    
    def _get_color_rgb(self, color_name):
        """根据颜色名称获取RGB值"""
        color_name = color_name.lower().strip()
        if color_name in LED_COLOR_MAP:
            return LED_COLOR_MAP[color_name]
        else:
            # 尝试模糊匹配
            for key in LED_COLOR_MAP:
                if color_name in key or key in color_name:
                    return LED_COLOR_MAP[key]
            # 默认返回白色
            print(f"⚠ 未识别的颜色: {color_name}，使用白色")
            return (255, 255, 255)

    def _translate_chinese_to_english(self, text):
        """将中文转换为英文用于点阵屏显示"""
        # 先检查是否有直接的翻译
        if text in CHINESE_TO_ENGLISH:
            return CHINESE_TO_ENGLISH[text]
        
        # 检查是否包含中文字符
        if re.search(r'[\u4e00-\u9fff]', text):
            # 包含中文，尝试部分翻译
            result = text
            for chinese, english in CHINESE_TO_ENGLISH.items():
                result = result.replace(chinese, english)
            
            # 如果还有中文字符，提示用户
            if re.search(r'[\u4e00-\u9fff]', result):
                print(f"⚠ 部分中文无法翻译: {text} -> {result}")
                # 移除剩余中文字符，只保留英文和数字
                result = re.sub(r'[\u4e00-\u9fff]', '', result)
            
            return result
        else:
            # 纯英文，直接返回
            return text

    def execute_led_command(self, command):
        """执行LED扩展指令"""
        try:
            command_parts = command.split()
            cmd = command_parts[0].lower()
            
            if cmd == "led_color" and len(command_parts) >= 2:
                # LED颜色设置：led_color red
                color_name = command_parts[1]
                r, g, b = self._get_color_rgb(color_name)
                led_cmd = f"led {r} {g} {b}"
                self.single_tello.send_expansion_command(led_cmd)
                print(f"🔆 LED设置为{color_name}({r},{g},{b})")
                return True
                
            elif cmd == "led_rgb" and len(command_parts) >= 4:
                # LED RGB设置：led_rgb 255 0 0
                try:
                    r = max(0, min(255, int(command_parts[1])))
                    g = max(0, min(255, int(command_parts[2])))
                    b = max(0, min(255, int(command_parts[3])))
                    led_cmd = f"led {r} {g} {b}"
                    self.single_tello.send_expansion_command(led_cmd)
                    print(f"🔆 LED设置为RGB({r},{g},{b})")
                    return True
                except ValueError:
                    print("❌ RGB值必须为数字")
                    return False
                    
            elif cmd == "led_breath" and len(command_parts) >= 3:
                # LED呼吸灯：led_breath green 1.0
                color_name = command_parts[1]
                try:
                    frequency = max(0.1, min(2.5, float(command_parts[2])))
                    r, g, b = self._get_color_rgb(color_name)
                    led_cmd = f"led br {frequency} {r} {g} {b}"
                    self.single_tello.send_expansion_command(led_cmd)
                    print(f"🔆 LED呼吸灯: {color_name}({r},{g},{b}) 频率{frequency}Hz")
                    return True
                except ValueError:
                    print("❌ 频率必须为数字")
                    return False
                    
            elif cmd == "led_blink" and len(command_parts) >= 4:
                # LED交替闪烁：led_blink red blue 1.0
                color1_name = command_parts[1]
                color2_name = command_parts[2]
                try:
                    frequency = max(0.1, min(10.0, float(command_parts[3])))
                    r1, g1, b1 = self._get_color_rgb(color1_name)
                    r2, g2, b2 = self._get_color_rgb(color2_name)
                    led_cmd = f"led bl {frequency} {r1} {g1} {b1} {r2} {g2} {b2}"
                    self.single_tello.send_expansion_command(led_cmd)
                    print(f"🔆 LED交替闪烁: {color1_name}-{color2_name} 频率{frequency}Hz")
                    return True
                except ValueError:
                    print("❌ 频率必须为数字")
                    return False
                    
            elif cmd == "display_text" and len(command_parts) >= 2:
                # 点阵屏显示文本：display_text Hello World
                text = " ".join(command_parts[1:])
                # 限制长度
                if len(text) > 70:
                    text = text[:70]
                    print(f"⚠ 文本过长，已截断为: {text}")
                
                # 中文转英文
                english_text = self._translate_chinese_to_english(text)
                
                # 发送点阵屏滚动显示命令（蓝色，向左滚动，1Hz）
                mled_cmd = f"mled l r 1 {english_text}"
                self.single_tello.send_expansion_command(mled_cmd)
                print(f"📺 点阵屏显示: '{text}' -> '{english_text}'")
                return True
            
            else:
                print(f"❌ 未知LED指令: {command}")
                return False
                
        except Exception as e:
            print(f"❌ LED指令执行失败: {e}")
            return False

    def execute_cruise_command(self, command):
        """执行巡航相关指令"""
        try:
            cmd = command.lower()
            
            if cmd == "start_cruise":
                if self.flying and self.cruise_module:
                    success = self.cruise_module.start_cruise()
                    if success:
                        print("✓ 巡航模式已启动")
                    return success
                else:
                    print("⚠ 无人机未在飞行中或巡航模块未初始化")
                    return False
            
            elif cmd == "stop_cruise":
                if self.cruise_module:
                    self.cruise_module.stop_cruise()
                    print("✓ 巡航模式已停止")
                    return True
                else:
                    print("⚠ 巡航模块未初始化")
                    return False
            
            elif cmd == "cruise_status":
                if self.cruise_module:
                    status = self.cruise_module.get_cruise_status()
                    print(f"📊 巡航状态: {status}")
                    return True
                else:
                    print("⚠ 巡航模块未初始化")
                    return False
            
            elif cmd == "tof_distance":
                if self.cruise_module:
                    distance = self.cruise_module.get_tof_distance()
                    if distance is not None:
                        print(f"📏 激光测距: {distance}mm")
                        return True
                    else:
                        print("❌ 激光测距读取失败")
                        return False
                else:
                    print("⚠ 巡航模块未初始化")
                    return False
            
            else:
                return False
                
        except Exception as e:
            print(f"❌ 巡航指令执行失败: {e}")
            return False

    def execute_linetrack_command(self, command):
        """执行巡线相关指令"""
        try:
            cmd = command.lower()
            
            if cmd == "start_linetrack":
                if self.flying and self.linetrack_module:
                    success = self.linetrack_module.start_line_tracking()
                    if success:
                        print("✓ 巡线模式已启动")
                    return success
                else:
                    print("⚠ 无人机未在飞行中或巡线模块未初始化")
                    return False
            
            elif cmd == "stop_linetrack":
                if self.linetrack_module:
                    self.linetrack_module.stop_line_tracking()
                    print("✓ 巡线模式已停止")
                    return True
                else:
                    print("⚠ 巡线模块未初始化")
                    return False
            
            elif cmd == "linetrack_status":
                if self.linetrack_module:
                    status = self.linetrack_module.get_tracking_status()
                    print(f"📊 巡线状态: {status}")
                    return True
                else:
                    print("⚠ 巡线模块未初始化")
                    return False
            
            else:
                return False
                
        except Exception as e:
            print(f"❌ 巡线指令执行失败: {e}")
            return False

    def execute_vision_command(self, command):
        """执行视觉感知相关指令"""
        try:
            if not self.vision_module:
                print("⚠ 视觉感知模块未初始化")
                return False
            
            command_parts = command.split()
            cmd = command_parts[0].lower()
            
            # 对于需要视频流的指令，先确保视频流已启动
            video_required_commands = ["capture_image", "recognize_view", "show_video"]
            if cmd in video_required_commands and not self.vision_module.video_streaming:
                print("📹 自动启动视频流...")
                if not self.vision_module.start_video_stream():
                    print("❌ 无法启动视频流，视觉指令执行失败")
                    return False
            
            if cmd == "start_video":
                # 启动视频流
                success = self.vision_module.start_video_stream()
                if success:
                    print("📹 视频流已启动")
                return success
            
            elif cmd == "stop_video":
                # 停止视频流
                success = self.vision_module.stop_video_stream()
                if success:
                    print("📹 视频流已停止")
                return success
            
            elif cmd == "capture_image":
                # 捕获图片
                if len(command_parts) > 1:
                    filename = " ".join(command_parts[1:])
                    image_path = self.vision_module.capture_image(filename)
                else:
                    image_path = self.vision_module.capture_image()
                
                if image_path:
                    print(f"📸 图片已保存: {image_path}")
                    return True
                else:
                    print("❌ 图片捕获失败")
                    return False
            
            elif cmd == "recognize_view":
                # 识别当前视野
                baike_num = 0
                if len(command_parts) > 1:
                    try:
                        baike_num = int(command_parts[1])
                    except:
                        pass
                
                result = self.vision_module.recognize_current_view(baike_num=baike_num)
                if result:
                    print("🔍 视野识别完成")
                    return True
                else:
                    print("❌ 视野识别失败")
                    return False
            
            elif cmd == "start_auto_recognition":
                # 启动自动识别（需要视频流）
                if not self.vision_module.video_streaming:
                    print("📹 自动启动视频流...")
                    if not self.vision_module.start_video_stream():
                        print("❌ 无法启动视频流，自动识别启动失败")
                        return False
                
                interval = 5.0
                if len(command_parts) > 1:
                    try:
                        interval = float(command_parts[1])
                    except:
                        pass
                
                self.vision_module.start_auto_recognition(interval)
                print(f"🔍 自动识别已启动，间隔: {interval}秒")
                return True
            
            elif cmd == "stop_auto_recognition":
                # 停止自动识别
                self.vision_module.stop_auto_recognition()
                print("🔍 自动识别已停止")
                return True
            
            elif cmd == "vision_status":
                # 查看视觉状态
                status = self.vision_module.get_vision_status()
                print(f"🔍 视觉状态: {status}")
                return True
            
            elif cmd == "show_video":
                # 显示视频流窗口（调试用）
                print("📺 启动视频显示窗口...")
                self.vision_module.display_video_stream()
                return True
            
            else:
                return False
                
        except Exception as e:
            print(f"❌ 视觉指令执行失败: {e}")
            return False

    def execute_basic_command(self, command):
        """执行基本飞行指令（增加巡线相关指令）"""
        if not self.connected:
            print("Tello未连接")
            return False
        
        try:
            # 检查是否为巡线指令
            if command.startswith(("start_linetrack", "stop_linetrack", "linetrack_status")):
                return self.execute_linetrack_command(command)
            
            # 检查是否为视觉指令
            if command.startswith(("start_video", "stop_video", "capture_image", "recognize_view", 
                                 "start_auto_recognition", "stop_auto_recognition", "vision_status", "show_video")):
                return self.execute_vision_command(command)
            
            # 先检查电池状态
            battery = self.get_battery()
            print(f"当前电池: {battery}%")
            
            command_parts = command.split()
            cmd = command_parts[0].lower()
            
            print(f"🚁 执行指令: {command}")
            
            if cmd == "takeoff":
                if not self.flying:
                    try:
                        self.single_tello.takeoff()
                        print("等待起飞完成...")
                        time.sleep(3)  # 等待起飞完成
                        self.flying = True
                        print("✓ 无人机起飞成功")
                        return True
                    except Exception as e:
                        print(f"❌ 起飞失败: {e}")
                        return False
                else:
                    print("⚠ 无人机已在飞行中")
                    return False
                    
            elif cmd == "land":
                if self.flying:
                    try:
                        # 停止巡航和巡线
                        if self.cruise_module:
                            self.cruise_module.stop_cruise()
                        if self.linetrack_module:
                            self.linetrack_module.stop_line_tracking()
                        
                        self.single_tello.land()
                        time.sleep(3)  # 等待降落完成
                        self.flying = False
                        print("✓ 无人机降落成功")
                        return True
                    except Exception as e:
                        print(f"❌ 降落失败: {e}")
                        # 如果降落失败，尝试紧急停止
                        try:
                            print("尝试紧急停止...")
                            self.single_tello.emergency()
                            time.sleep(2)
                            self.flying = False
                            if self.cruise_module:
                                self.cruise_module.stop_cruise()
                            if self.linetrack_module:
                                self.linetrack_module.stop_line_tracking()
                            print("✓ 紧急停止成功")
                            return True
                        except:
                            print("❌ 紧急停止也失败")
                            return False
                else:
                    print("⚠ 无人机未在飞行中")
                    return False
                    
            elif cmd == "stop":
                try:
                    # 停止所有模式
                    if self.cruise_module:
                        self.cruise_module.stop_cruise()
                    if self.linetrack_module:
                        self.linetrack_module.stop_line_tracking()
                    
                    self.single_tello.emergency()
                    self.flying = False
                    print("✓ 紧急停止执行")
                    return True
                except Exception as e:
                    print(f"❌ 紧急停止失败: {e}")
                    return False
                        
            elif self.flying:  # 只有在飞行中才执行移动命令
                try:
                    result = False
                    if cmd == "up" and len(command_parts) == 2:
                        distance = max(20, min(500, int(command_parts[1])))
                        print(f"🚁 向上移动 {distance}cm")
                        self.single_tello.move_up(distance)
                        result = True
                        
                    elif cmd == "down" and len(command_parts) == 2:
                        distance = max(20, min(500, int(command_parts[1])))
                        print(f"🚁 向下移动 {distance}cm")
                        self.single_tello.move_down(distance)
                        result = True
                        
                    elif cmd == "left" and len(command_parts) == 2:
                        distance = max(20, min(500, int(command_parts[1])))
                        print(f"🚁 向左移动 {distance}cm")
                        self.single_tello.move_left(distance)
                        result = True
                        
                    elif cmd == "right" and len(command_parts) == 2:
                        distance = max(20, min(500, int(command_parts[1])))
                        print(f"🚁 向右移动 {distance}cm")
                        self.single_tello.move_right(distance)
                        result = True
                        
                    elif cmd == "forward" and len(command_parts) == 2:
                        distance = max(20, min(500, int(command_parts[1])))
                        print(f"🚁 向前移动 {distance}cm")
                        self.single_tello.move_forward(distance)
                        result = True
                        
                    elif cmd == "back" and len(command_parts) == 2:
                        distance = max(20, min(500, int(command_parts[1])))
                        print(f"🚁 向后移动 {distance}cm")
                        self.single_tello.move_back(distance)
                        result = True
                        
                    elif cmd == "rotate_cw" and len(command_parts) == 2:
                        angle = max(1, min(360, int(command_parts[1])))
                        print(f"🔄 顺时针旋转 {angle}度")
                        self.single_tello.rotate_clockwise(angle)
                        result = True
                        
                    elif cmd == "rotate_ccw" and len(command_parts) == 2:
                        angle = max(1, min(360, int(command_parts[1])))
                        print(f"🔄 逆时针旋转 {angle}度")
                        self.single_tello.rotate_counter_clockwise(angle)
                        result = True
                        
                    else:
                        print(f"✗ 未知命令: {command}")
                        result = False
                    
                    if result:
                        print(f"✓ 命令执行完成: {command}")
                        time.sleep(1)  # 命令完成后稳定时间
                    
                    return result
                        
                except Exception as e:
                    print(f"❌ 指令执行失败: {e}")
                    return False
            else:
                print("⚠ 无人机未在飞行中，无法执行移动命令")
                return False
                
        except Exception as e:
            print(f"✗ 命令执行错误: {e}")
            return False

    def emergency_stop(self):
        """紧急停止所有操作"""
        try:
            # 停止巡航
            if self.cruise_module:
                self.cruise_module.emergency_stop()
            
            # 停止巡线
            if self.linetrack_module:
                self.linetrack_module.stop_line_tracking()
            
            # 停止所有RC控制
            if self.flying and self.connected:
                self.single_tello.send_rc_control(0, 0, 0, 0)
                time.sleep(0.5)
                
        except Exception as e:
            print(f"⚠ 紧急停止RC控制时出错: {e}")
