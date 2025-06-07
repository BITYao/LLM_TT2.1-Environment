"""
视觉感知模块 - Tello摄像头 + 百度图像识别
"""
import cv2
import os
import time
import threading
from datetime import datetime
from baidu_vision import BaiduVision
from llm_client import LLMClient
from speech_synthesis import SpeechSynthesis
from config import VISION_AUTO_DESCRIPTION

class VisionModule:
    def __init__(self, tello):
        self.tello = tello
        self.baidu_vision = BaiduVision()
        self.llm_client = LLMClient()
        self.speech_synthesis = SpeechSynthesis()
        
        # 摄像头相关
        self.frame_read = None
        self.video_streaming = False
        self.capture_folder = "picturecap"
        
        # 识别相关
        self.auto_recognition = False
        self.recognition_interval = 5.0  # 自动识别间隔（秒）
        self.last_recognition_time = 0
        self.latest_recognition_result = None
        
        # 线程控制
        self.recognition_thread = None
        self.recognition_running = False
        
        # 智能描述相关
        self.auto_description_enabled = VISION_AUTO_DESCRIPTION
        
        # 创建图片保存文件夹
        self._ensure_capture_folder()
        
        print("✅ 视觉感知模块已初始化")
        print(f"   自动描述播报: {'开启' if self.auto_description_enabled else '关闭'}")
    
    def _ensure_capture_folder(self):
        """确保图片保存文件夹存在"""
        if not os.path.exists(self.capture_folder):
            os.makedirs(self.capture_folder)
            print(f"📁 创建图片保存文件夹: {self.capture_folder}")
    
    def start_video_stream(self):
        """启动视频流（适配编队模式）- 增强版重试机制"""
        try:
            if self.video_streaming:
                print("⚠ 视频流已在运行中")
                return True
            
            print("📹 启动Tello视频流（编队模式）...")
            
            # 🔧 新增：设置摄像头方向（强制要求）
            print("📷 设置摄像头方向...")
            try:
                self.tello.set_video_direction(0)
                print("✅ 摄像头方向设置成功")
                time.sleep(1)  # 等待设置生效
            except Exception as direction_error:
                print(f"⚠ 摄像头方向设置失败: {direction_error}")
                # 继续执行，不中断流程
            
            # 第一步：发送streamon命令
            self.tello.streamon()
            print("✅ streamon命令已发送")
            
            # 第二步：等待视频流稳定
            print("⏳ 等待视频流稳定...")
            time.sleep(5)  # 增加等待时间到5秒
            
            # 第三步：尝试获取视频帧读取器（多次重试）
            max_retries = 5
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    print(f"🔄 尝试获取视频帧读取器 ({retry_count + 1}/{max_retries})...")
                    
                    # 获取视频帧读取器
                    self.frame_read = self.tello.get_frame_read()
                    
                    if self.frame_read is None:
                        print("❌ 帧读取器创建失败")
                        retry_count += 1
                        time.sleep(2)
                        continue
                    
                    # 第四步：等待第一帧准备就绪
                    frame_wait_count = 0
                    max_frame_waits = 15  # 最多等待15秒
                    
                    print("⏳ 等待第一帧准备就绪...")
                    while frame_wait_count < max_frame_waits:
                        try:
                            frame = self.frame_read.frame
                            if frame is not None and frame.size > 0:
                                # 验证帧的基本属性
                                height, width = frame.shape[:2]
                                if height > 0 and width > 0:
                                    print(f"✅ 获得有效视频帧，分辨率: {width}x{height}")
                                    self.video_streaming = True
                                    return True
                                    
                        except Exception as frame_error:
                            print(f"⚠ 帧检查出错: {frame_error}")
                        
                        frame_wait_count += 1
                        time.sleep(1)
                        print(f"⏳ 等待视频帧... ({frame_wait_count}/{max_frame_waits})")
                    
                    print("❌ 等待视频帧超时")
                    retry_count += 1
                    
                    # 清理失败的帧读取器
                    self.frame_read = None
                    time.sleep(2)
                    
                except Exception as retry_error:
                    print(f"❌ 第{retry_count + 1}次重试失败: {retry_error}")
                    retry_count += 1
                    self.frame_read = None
                    time.sleep(2)
            
            # 所有重试都失败
            print("❌ 视频流启动失败：无法获取有效视频帧")
            
            # 尝试重置视频流
            try:
                print("🔄 尝试重置视频流...")
                self.tello.streamoff()
                time.sleep(2)
                return False
            except:
                pass
            
            return False
            
        except Exception as e:
            print(f"❌ 启动视频流异常: {e}")
            self.video_streaming = False
            self.frame_read = None
            return False
    
    def stop_video_stream(self):
        """停止视频流 - 增强版清理"""
        try:
            if not self.video_streaming:
                return True
            
            print("📹 停止Tello视频流...")
            
            # 标记为停止状态
            self.video_streaming = False
            
            # 清理帧读取器
            if self.frame_read:
                try:
                    # 尝试停止帧读取器（如果有stop方法）
                    if hasattr(self.frame_read, 'stop'):
                        self.frame_read.stop()
                except:
                    pass
                finally:
                    self.frame_read = None
            
            # 发送streamoff命令
            self.tello.streamoff()
            
            # 给一点时间让视频流完全停止
            time.sleep(2)
            
            print("✅ Tello视频流已停止")
            return True
            
        except Exception as e:
            print(f"❌ 停止视频流失败: {e}")
            # 强制清理状态
            self.video_streaming = False
            self.frame_read = None
            return False
    
    def _get_valid_frame(self, max_attempts=10, skip_dark_frames=True):
        """获取有效的视频帧（带重试机制和黑帧检测）"""
        if not self.video_streaming or not self.frame_read:
            return None
        
        for attempt in range(max_attempts):
            try:
                frame = self.frame_read.frame
                
                if frame is not None and frame.size > 0:
                    # 验证帧的基本属性
                    if len(frame.shape) >= 2 and frame.shape[0] > 0 and frame.shape[1] > 0:
                        
                        # 🔧 新增：检测并跳过纯黑帧或过暗帧
                        if skip_dark_frames and self._is_frame_too_dark(frame):
                            print(f"⚫ 跳过过暗帧 ({attempt + 1}/{max_attempts})...")
                            time.sleep(0.3)  # 稍等片刻再获取下一帧
                            continue
                        
                        # 🔧 新增：基本图像质量检查
                        if self._is_frame_quality_good(frame):
                            return frame
                        else:
                            print(f"📷 帧质量不佳，重试 ({attempt + 1}/{max_attempts})...")
                
                print(f"⏳ 尝试获取有效帧 ({attempt + 1}/{max_attempts})...")
                time.sleep(0.5)
                
            except Exception as e:
                print(f"❌ 获取帧时出错: {e}")
                time.sleep(0.5)
        
        print("❌ 无法获取有效视频帧")
        return None
    
    def _is_frame_too_dark(self, frame, dark_threshold=15):
        """检测帧是否过暗（纯黑或接近黑色）"""
        try:
            # 转换为灰度图计算平均亮度
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            else:
                gray = frame
            
            mean_brightness = cv2.mean(gray)[0]
            
            # 如果平均亮度低于阈值，认为是暗帧
            if mean_brightness < dark_threshold:
                print(f"🔍 检测到暗帧，平均亮度: {mean_brightness:.1f}")
                return True
            
            return False
            
        except Exception as e:
            print(f"⚠ 暗帧检测出错: {e}")
            return False
    
    def _is_frame_quality_good(self, frame, variance_threshold=40):
        """检测帧的基本质量"""
        try:
            # 转换为灰度图
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            else:
                gray = frame
            
            # 计算图像方差（判断是否有足够的细节）
            variance = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            if variance < variance_threshold:
                print(f"📷 帧细节不足，方差: {variance:.1f}")
                return False
            
            return True
            
        except Exception as e:
            print(f"⚠ 帧质量检测出错: {e}")
            return True  # 出错时假设质量良好

    def capture_image(self, filename=None):
        """捕获当前视频帧并保存为图片（增强版错误处理）"""
        try:
            if not self.video_streaming or not self.frame_read:
                print("❌ 视频流未启动，无法捕获图片")
                return None
            
            print("📸 正在捕获图片...")
            
            # 使用增强的帧获取方法
            frame = self._get_valid_frame()
            
            if frame is None:
                print("❌ 无法获取有效视频帧")
                return None
            
            # 🔧 修复：将RGB转换为BGR格式（Tello默认输出RGB格式）
            try:
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                print("✅ 视频帧颜色格式转换成功")
            except Exception as color_error:
                print(f"⚠ 颜色格式转换失败，使用原始帧: {color_error}")
                frame_bgr = frame
            
            # 生成文件名
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"tello_capture_{timestamp}.jpg"
            
            # 确保文件名有正确的扩展名
            if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                filename += '.jpg'
            
            # 完整文件路径
            filepath = os.path.join(self.capture_folder, filename)
            
            # 保存图片（使用BGR格式）
            success = cv2.imwrite(filepath, frame_bgr)
            
            if success:
                # 验证文件确实被保存
                if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                    print(f"📸 图片已保存: {filepath}")
                    return filepath
                else:
                    print("❌ 图片保存验证失败")
                    return None
            else:
                print("❌ 保存图片失败")
                return None
                
        except Exception as e:
            print(f"❌ 捕获图片异常: {e}")
            return None
    
    def capture_temp_image(self, max_frame_attempts=15):
        """捕获临时图片（用于识别后删除）- 增强版避免黑帧"""
        try:
            if not self.video_streaming or not self.frame_read:
                print("❌ 视频流未启动，无法捕获临时图片")
                return None
            
            print("📸 正在获取高质量视频帧用于识别...")
            
            # 使用增强的帧获取方法（更多重试次数，严格质量检查）
            frame = self._get_valid_frame(max_attempts=max_frame_attempts, skip_dark_frames=True)
            
            if frame is None:
                print("❌ 无法获取有效视频帧")
                return None
            
            # 输出帧的基本信息用于调试
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
                mean_brightness = cv2.mean(gray)[0]
                print(f"✅ 获得高质量帧，亮度: {mean_brightness:.1f}")
            
            # 🔧 修复：将RGB转换为BGR格式
            try:
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            except Exception as color_error:
                print(f"⚠ 颜色格式转换失败，使用原始帧: {color_error}")
                frame_bgr = frame
            
            # 临时文件路径
            temp_filename = f"temp_recognition_{int(time.time())}.jpg"
            temp_filepath = os.path.join(self.capture_folder, temp_filename)
            
            # 使用BGR格式保存
            success = cv2.imwrite(temp_filepath, frame_bgr)
            
            if success and os.path.exists(temp_filepath):
                print(f"📸 临时图片已保存: {temp_filepath}")
                return temp_filepath
            else:
                print("❌ 临时图片保存失败")
                return None
                
        except Exception as e:
            print(f"❌ 捕获临时图片异常: {e}")
            return None

    def restart_video_stream(self):
        """重启视频流"""
        try:
            print("🔄 重启视频流...")
            
            # 先停止现有视频流
            self.stop_video_stream()
            
            # 等待一段时间
            time.sleep(3)
            
            # 🔧 新增：重启时也设置摄像头方向
            print("📷 重新设置摄像头方向...")
            try:
                self.tello.set_video_direction(0)
                print("✅ 摄像头方向重新设置成功")
                time.sleep(0.5)
            except Exception as direction_error:
                print(f"⚠ 摄像头方向重新设置失败: {direction_error}")
            
            # 重新启动
            success = self.start_video_stream()
            
            if success:
                print("✅ 视频流重启成功")
            else:
                print("❌ 视频流重启失败")
            
            return success
            
        except Exception as e:
            print(f"❌ 视频流重启异常: {e}")
            return False

    def get_stream_status(self):
        """获取视频流详细状态"""
        status = {
            'streaming': self.video_streaming,
            'frame_reader_exists': self.frame_read is not None,
            'current_frame_valid': False,
            'frame_shape': None
        }
        
        if self.frame_read:
            try:
                frame = self.frame_read.frame
                if frame is not None and frame.size > 0:
                    status['current_frame_valid'] = True
                    status['frame_shape'] = frame.shape
            except:
                pass
        
        return status

    def recognize_current_view(self, save_image=True, baike_num=0, auto_describe=None):
        """识别当前视野中的物体（带心跳保持）"""
        heartbeat_thread = None
        heartbeat_running = False
        
        try:
            # 🔧 新增：启动识别期间的心跳保持
            if hasattr(self, 'tello') and self.tello and hasattr(self.tello, 'send_rc_control'):
                print("💓 启动识别期间心跳保持...")
                heartbeat_running = True
                heartbeat_thread = threading.Thread(
                    target=self._maintain_heartbeat_during_recognition, 
                    args=(lambda: heartbeat_running,), 
                    daemon=True
                )
                heartbeat_thread.start()
            
            # 捕获当前图片
            print("🔍 开始图像识别流程...")
            
            if save_image:
                image_path = self.capture_image()
            else:
                # 使用增强的临时图片捕获（避免黑帧）
                image_path = self.capture_temp_image(max_frame_attempts=15)
            
            if not image_path:
                print("❌ 图片捕获失败")
                return None
            
            print("🤖 正在调用百度图像识别API...")
            
            # 识别图片 - 这个过程可能耗时较长
            result = self.baidu_vision.recognize_image_file(image_path, baike_num)
            
            if result:
                self.latest_recognition_result = result
                summary = self.baidu_vision.format_recognition_summary(result)
                print(f"🔍 当前视野识别结果: {summary}")
                
                # 详细结果
                top_objects = self.baidu_vision.get_top_objects(result, 5)
                for i, obj in enumerate(top_objects, 1):
                    category_info = f" ({obj['category']})" if obj['category'] != '未分类' else ""
                    print(f"   {i}. {obj['name']}: {obj['confidence']:.1f}%{category_info}")
                
                # 生成智能描述并播报
                should_describe = auto_describe if auto_describe is not None else self.auto_description_enabled
                if should_describe:
                    print("🗣 开始生成智能描述...")
                    self._generate_and_speak_description(result)
                
                # 清理临时文件
                if not save_image and image_path and os.path.exists(image_path):
                    try:
                        os.remove(image_path)
                        print("🗑️ 临时识别文件已清理")
                    except:
                        pass
                
                return result
            else:
                print("❌ 图像识别失败")
                if self.auto_description_enabled:
                    self.speech_synthesis.speak("识别失败，请稍后重试")
                return None
                
        except Exception as e:
            print(f"❌ 识别当前视野异常: {e}")
            return None
        finally:
            # 🔧 停止心跳保持
            if heartbeat_thread and heartbeat_running:
                print("💓 停止识别期间心跳保持")
                heartbeat_running = False
                try:
                    heartbeat_thread.join(timeout=2)
                except:
                    pass
    
    def _maintain_heartbeat_during_recognition(self, should_continue):
        """在识别过程中维持心跳（独立线程）"""
        try:
            while should_continue():
                try:
                    # 发送悬停指令保持连接
                    if hasattr(self, 'tello') and self.tello:
                        self.tello.send_rc_control(0, 0, 0, 0)
                    
                    time.sleep(1.5)  # 每1.5秒发送一次心跳
                    
                except Exception as e:
                    print(f"⚠ 识别心跳发送失败: {e}")
                    time.sleep(1)
        
        except Exception as e:
            print(f"❌ 识别心跳线程异常: {e}")

    def _generate_and_speak_description(self, recognition_result):
        """生成智能描述并语音播报"""
        try:
            if not recognition_result or 'objects' not in recognition_result:
                return
            
            print("🤖 正在生成智能描述...")
            
            # 检查LLM客户端是否有描述生成方法
            if not hasattr(self.llm_client, 'generate_vision_description'):
                print("⚠ LLM客户端缺少图像描述功能，使用简单描述")
                fallback_description = self._generate_simple_description(recognition_result)
                print(f"📢 简单描述: {fallback_description}")
                self.speech_synthesis.speak(fallback_description)
                return
            
            # 使用LLM生成自然语言描述
            description = self.llm_client.generate_vision_description(recognition_result)
            
            if description and description not in ["描述生成失败", "描述生成出错", "识别结果处理失败"]:
                print(f"📢 智能描述: {description}")
                # 语音播报描述
                self.speech_synthesis.speak(description, priority=True)
            else:
                # 如果LLM描述失败，使用简单格式
                print("⚠ LLM描述生成失败，使用备用方案")
                fallback_description = self._generate_simple_description(recognition_result)
                print(f"📢 简单描述: {fallback_description}")
                self.speech_synthesis.speak(fallback_description)
                
        except Exception as e:
            print(f"❌ 生成描述异常: {e}")
            import traceback
            print(f"详细错误: {traceback.format_exc()}")
            
            # 使用简单描述作为最后的备用方案
            try:
                fallback_description = self._generate_simple_description(recognition_result)
                print(f"📢 备用描述: {fallback_description}")
                self.speech_synthesis.speak(fallback_description)
            except Exception as fallback_error:
                print(f"❌ 备用描述也失败: {fallback_error}")
                self.speech_synthesis.speak("识别完成，但描述生成失败")
    
    def _generate_simple_description(self, recognition_result):
        """生成简单描述（备用方案）"""
        try:
            top_objects = self.baidu_vision.get_top_objects(recognition_result, 2)
            
            if not top_objects:
                return "未识别到明确物体"
            
            if len(top_objects) == 1:
                obj = top_objects[0]
                return f"我看到{obj['name']}"
            else:
                obj1, obj2 = top_objects[0], top_objects[1]
                return f"我看到{obj1['name']}和{obj2['name']}"
                
        except Exception as e:
            return "识别结果处理中"
    
    def start_auto_recognition(self, interval=5.0):
        """启动自动识别模式"""
        if self.recognition_running:
            print("⚠ 自动识别已在运行中")
            return
        
        self.auto_recognition = True
        self.recognition_interval = max(3.0, interval)  # 最小间隔3秒
        self.recognition_running = True
        
        self.recognition_thread = threading.Thread(target=self._auto_recognition_worker, daemon=True)
        self.recognition_thread.start()
        
        print(f"🔍 自动识别已启动，间隔: {self.recognition_interval}秒")
    
    def stop_auto_recognition(self):
        """停止自动识别模式"""
        if not self.recognition_running:
            return
        
        print("🔍 停止自动识别...")
        self.auto_recognition = False
        self.recognition_running = False
        
        if self.recognition_thread:
            self.recognition_thread.join(timeout=3)
        
        print("✅ 自动识别已停止")
    
    def _auto_recognition_worker(self):
        """自动识别工作线程（优化版）"""
        consecutive_failures = 0
        max_failures = 3  # 连续失败3次后暂停
        
        while self.recognition_running and self.auto_recognition:
            try:
                current_time = time.time()
                
                # 检查是否到了识别时间
                if current_time - self.last_recognition_time >= self.recognition_interval:
                    self.last_recognition_time = current_time
                    
                    print("🔍 自动识别开始...")
                    
                    # 执行识别（不保存图片，启用描述，带心跳保持）
                    result = self.recognize_current_view(save_image=False, auto_describe=True)
                    
                    if result:
                        consecutive_failures = 0  # 重置失败计数
                        print("✅ 自动识别成功")
                    else:
                        consecutive_failures += 1
                        print(f"❌ 自动识别失败 ({consecutive_failures}/{max_failures})")
                        
                        # 连续失败过多，暂停自动识别
                        if consecutive_failures >= max_failures:
                            print("⚠ 连续识别失败过多，暂停自动识别")
                            self.auto_recognition = False
                            self.speech_synthesis.speak("视觉识别出现问题，已暂停自动识别")
                            break
                
                time.sleep(1)  # 每秒检查一次
                
            except Exception as e:
                print(f"❌ 自动识别线程错误: {e}")
                consecutive_failures += 1
                time.sleep(2)
                
                if consecutive_failures >= max_failures:
                    print("⚠ 自动识别线程错误过多，停止自动识别")
                    self.auto_recognition = False
                    break
    
    def toggle_auto_description(self):
        """切换自动描述功能"""
        self.auto_description_enabled = not self.auto_description_enabled
        status = "开启" if self.auto_description_enabled else "关闭"
        print(f"📢 自动描述播报已{status}")
        self.speech_synthesis.speak(f"自动描述播报已{status}")
        return self.auto_description_enabled
    
    def speak_recognition_result(self):
        """播报最新识别结果"""
        if self.latest_recognition_result:
            self._generate_and_speak_description(self.latest_recognition_result)
        else:
            self.speech_synthesis.speak("暂无识别结果")
    
    def test_speech_synthesis(self):
        """测试语音合成"""
        return self.speech_synthesis.test_speech()
    
    def get_latest_recognition(self):
        """获取最新的识别结果"""
        return self.latest_recognition_result
    
    def display_video_stream(self, window_name="Tello Camera"):
        """显示视频流（用于调试，适配编队模式）"""
        try:
            if not self.video_streaming or not self.frame_read:
                print("❌ 视频流未启动")
                return
            
            print(f"📺 显示视频流窗口: {window_name}")
            print("💡 按 'q' 键退出显示，按 'c' 键捕获图片，按 'r' 键识别当前画面")
            
            # 设置窗口
            cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
            
            # 记录帧率
            frame_count = 0
            start_time = time.time()
            
            while True:
                frame = self.frame_read.frame
                
                if frame is not None and frame.size > 0:
                    # 🔧 修复：将RGB转换为BGR格式用于显示
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    
                    # 添加识别结果叠加显示
                    display_frame = self._add_recognition_overlay(frame_bgr)
                    
                    # 添加帧率信息
                    frame_count += 1
                    current_time = time.time()
                    if current_time - start_time >= 5.0:  # 每5秒计算一次帧率
                        fps = frame_count / (current_time - start_time)
                        frame_count = 0
                        start_time = current_time
                        
                        # 在图像上显示帧率
                        cv2.putText(display_frame, f"FPS: {fps:.1f}", (10, display_frame.shape[0] - 10), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    
                    # 添加颜色格式标识
                    cv2.putText(display_frame, "BGR Format", (10, 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    
                    cv2.imshow(window_name, display_frame)
                else:
                    print("⚠ 获取到无效视频帧")
                
                key = cv2.waitKey(1) & 0xFF
                
                if key == ord('q') or key == 27:  # 'q' 或 ESC 键
                    break
                elif key == ord('c'):
                    self.capture_image()
                elif key == ord('r'):
                    self.recognize_current_view()
            
            cv2.destroyWindow(window_name)
            print("📺 视频显示窗口已关闭")
            
        except Exception as e:
            print(f"❌ 显示视频流异常: {e}")
            try:
                cv2.destroyAllWindows()
            except:
                pass
    
    def _add_recognition_overlay(self, frame):
        """在视频帧上叠加识别结果"""
        try:
            if self.latest_recognition_result:
                overlay_frame = frame.copy()
                
                # 获取前3个识别结果
                top_objects = self.baidu_vision.get_top_objects(self.latest_recognition_result, 3)
                
                # 在左上角显示识别结果
                y_offset = 30
                for obj in top_objects:
                    text = f"{obj['name']}: {obj['confidence']:.1f}%"
                    cv2.putText(overlay_frame, text, (10, y_offset), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    y_offset += 30
                
                return overlay_frame
            else:
                return frame
                
        except Exception as e:
            return frame
    
    def get_vision_status(self):
        """获取视觉模块状态"""
        status_parts = []
        
        if self.video_streaming:
            status_parts.append("视频流: 开启")
        else:
            status_parts.append("视频流: 关闭")
        
        if self.auto_recognition:
            status_parts.append(f"自动识别: 开启({self.recognition_interval}s)")
        else:
            status_parts.append("自动识别: 关闭")
        
        # 添加语音描述状态
        if self.auto_description_enabled:
            status_parts.append("智能描述: 开启")
        else:
            status_parts.append("智能描述: 关闭")
        
        # 添加语音队列状态
        queue_size = self.speech_synthesis.get_queue_size()
        if queue_size > 0:
            status_parts.append(f"语音队列: {queue_size}条")
        
        if self.latest_recognition_result:
            summary = self.baidu_vision.format_recognition_summary(self.latest_recognition_result)
            status_parts.append(f"最新识别: {summary}")
        
        return " | ".join(status_parts)
    
    def cleanup(self):
        """清理资源"""
        try:
            # 停止自动识别
            self.stop_auto_recognition()
            
            # 停止视频流
            self.stop_video_stream()
            
            # 关闭语音合成
            self.speech_synthesis.shutdown()
            
            # 清理临时文件
            self._cleanup_temp_files()
            
            print("✅ 视觉模块已清理")
            
        except Exception as e:
            print(f"⚠ 视觉模块清理时出错: {e}")
    
    def _cleanup_temp_files(self):
        """清理临时文件"""
        try:
            temp_files = [f for f in os.listdir(self.capture_folder) 
                         if f.startswith('temp_recognition_')]
            
            for temp_file in temp_files:
                temp_path = os.path.join(self.capture_folder, temp_file)
                try:
                    os.remove(temp_path)
                except:
                    pass
                    
        except Exception as e:
            pass
