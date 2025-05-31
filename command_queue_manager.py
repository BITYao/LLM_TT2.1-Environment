"""
指令队列管理器 - 处理指令队列和心跳机制
"""
import threading
import time
import queue

class CommandQueueManager:
    def __init__(self, tello_controller):
        self.tello_controller = tello_controller
        
        # 心跳机制相关属性
        self.heartbeat_thread = None
        self.heartbeat_running = False
        self.heartbeat_lock = threading.Lock()
        self.command_executing = False  # 标记是否正在执行命令
        self.heartbeat_interval = 2.0  # 心跳间隔（秒）
        
        # 指令队列相关属性
        self.command_queue = queue.Queue()
        self.queue_processor_thread = None
        self.queue_processing = False
    
    def start_heartbeat(self):
        """启动心跳机制"""
        if self.heartbeat_running:
            return
            
        self.heartbeat_running = True
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_worker, daemon=True)
        self.heartbeat_thread.start()
        print("✓ 心跳机制已启动（每2秒发送悬停指令）")
    
    def stop_heartbeat(self):
        """停止心跳机制"""
        self.heartbeat_running = False
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=3)
        print("✓ 心跳机制已停止")
    
    def _heartbeat_worker(self):
        """心跳工作线程"""
        while self.heartbeat_running and self.tello_controller.flying and self.tello_controller.connected:
            try:
                with self.heartbeat_lock:
                    # 只有在不执行命令时才发送心跳
                    if not self.command_executing and self.tello_controller.flying:
                        self.tello_controller.single_tello.send_rc_control(0, 0, 0, 0)
                
                time.sleep(self.heartbeat_interval)
                
            except Exception as e:
                print(f"❌ 心跳发送失败: {e}")
                time.sleep(1)  # 出错时短暂等待后继续
        
        print("💓 心跳线程已退出")
    
    def start_command_queue_processor(self):
        """启动指令队列处理器"""
        if self.queue_processing:
            return
            
        self.queue_processing = True
        self.queue_processor_thread = threading.Thread(target=self._process_command_queue, daemon=True)
        self.queue_processor_thread.start()
        print("✓ 指令队列处理器已启动")
    
    def stop_command_queue_processor(self):
        """停止指令队列处理器"""
        self.queue_processing = False
        if self.queue_processor_thread:
            self.queue_processor_thread.join(timeout=3)
        print("✓ 指令队列处理器已停止")
    
    def _process_command_queue(self):
        """处理指令队列的工作线程"""
        while self.queue_processing:
            try:
                # 从队列获取指令（阻塞式，超时1秒）
                command = self.command_queue.get(timeout=1)
                
                if command:
                    print(f"📤 从队列执行指令: {command}")
                    success = self._execute_single_command_with_heartbeat(command)
                    
                    if success:
                        print(f"✅ 指令执行成功: {command}")
                    else:
                        print(f"❌ 指令执行失败: {command}")
                        # 如果是关键指令失败，可以选择清空队列
                        if command in ["takeoff", "land", "stop"]:
                            print("⚠ 关键指令失败，清空剩余队列")
                            self.clear_command_queue()
                    
                    # 指令间延迟，确保无人机稳定
                    time.sleep(0.5)
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ 队列处理错误: {e}")
                time.sleep(1)
        
        print("📥 指令队列处理器已退出")
    
    def _execute_single_command_with_heartbeat(self, command):
        """执行单条指令（带心跳控制）"""
        try:
            # 标记开始执行命令，暂停心跳
            with self.heartbeat_lock:
                self.command_executing = True
            
            # 执行指令
            success = self._route_command(command)
            
            return success
            
        except Exception as e:
            print(f"✗ 命令执行错误: {e}")
            return False
        finally:
            # 恢复心跳（命令执行完毕）
            with self.heartbeat_lock:
                self.command_executing = False
    
    def _route_command(self, command):
        """路由指令到相应的执行器"""
        command_parts = command.split()
        cmd = command_parts[0].lower()
        
        # 检查是否为巡航指令
        if cmd in ["start_cruise", "stop_cruise", "cruise_status", "tof_distance"]:
            return self.tello_controller.execute_cruise_command(command)
        
        # 检查是否为LED扩展指令
        elif cmd in ["led_color", "led_rgb", "led_breath", "led_blink", "display_text"]:
            return self.tello_controller.execute_led_command(command)
        
        # 检查是否为视觉感知指令
        elif cmd in ["start_video", "stop_video", "capture_image", "recognize_view", 
                    "start_auto_recognition", "stop_auto_recognition", "vision_status", "show_video",
                    "test_speech_description"]:  # 添加测试语音描述指令
            return self.tello_controller.execute_vision_command(command)
        
        # 基本飞行指令
        else:
            return self.tello_controller.execute_basic_command(command)
    
    def clear_command_queue(self):
        """清空指令队列"""
        cleared_count = 0
        while not self.command_queue.empty():
            try:
                self.command_queue.get_nowait()
                cleared_count += 1
            except queue.Empty:
                break
        
        if cleared_count > 0:
            print(f"🗑 已清空 {cleared_count} 条待执行指令")
    
    def add_commands_to_queue(self, commands):
        """将指令列表添加到队列"""
        if isinstance(commands, str):
            commands = [commands]
        
        added_count = 0
        for command in commands:
            if command and command != "unknown":
                self.command_queue.put(command)
                added_count += 1
                print(f"📥 指令已加入队列: {command}")
        
        if added_count > 0:
            print(f"📋 共添加 {added_count} 条指令到队列")
            return True
        else:
            print("❌ 没有有效指令添加到队列")
            return False
    
    def get_queue_status(self):
        """获取队列状态"""
        return self.command_queue.qsize()
    
    def execute_command(self, commands):
        """执行语音命令（支持复合指令）"""
        if not self.tello_controller.connected:
            print("Tello未连接")
            return False
        
        # 如果是单个指令，转换为列表
        if isinstance(commands, str):
            commands = [commands]
        
        print(f"🎯 收到指令序列，共 {len(commands)} 条")
        
        # 检查是否包含紧急停止指令
        if "stop" in commands:
            print("🚨 检测到紧急停止指令，立即执行")
            return self._execute_single_command_with_heartbeat("stop")
        
        # 如果只有一条指令且是起飞/降落，立即执行
        if len(commands) == 1 and commands[0] in ["takeoff", "land"]:
            success = self._execute_single_command_with_heartbeat(commands[0])
            if success and commands[0] == "takeoff":
                # 起飞成功后启动心跳机制和队列处理器
                self.start_heartbeat()
                self.start_command_queue_processor()
            elif commands[0] == "land":
                # 降落时停止相关系统
                self.clear_command_queue()
                self.stop_heartbeat()
                self.stop_command_queue_processor()
            return success
        
        # 多条指令添加到队列
        return self.add_commands_to_queue(commands)
    
    def shutdown(self):
        """关闭队列管理器"""
        print("🔄 正在关闭指令队列管理器...")
        
        # 停止指令队列处理器
        try:
            self.stop_command_queue_processor()
        except Exception as e:
            print(f"⚠ 停止指令队列处理器时出错: {e}")
        
        # 清空剩余指令
        try:
            self.clear_command_queue()
        except Exception as e:
            print(f"⚠ 清空指令队列时出错: {e}")
        
        # 停止心跳机制
        try:
            self.stop_heartbeat()
        except Exception as e:
            print(f"⚠ 停止心跳机制时出错: {e}")
        
        # 停止所有RC控制
        try:
            if self.tello_controller.flying and self.tello_controller.connected:
                print("🛑 停止所有移动...")
                self.tello_controller.single_tello.send_rc_control(0, 0, 0, 0)
                time.sleep(0.5)
        except Exception as e:
            print(f"⚠ 停止RC控制时出错: {e}")
