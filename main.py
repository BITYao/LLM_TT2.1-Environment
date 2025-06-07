import time
from voice_controller import VoiceController
from llm_client import LLMClient
from network_manager import NetworkChecker
from tello_extended_controller import TelloExtendedController
from command_queue_manager import CommandQueueManager

class TelloVoiceControl:
    def __init__(self):
        self.llm_client = LLMClient()
        self.voice_controller = VoiceController(self.llm_client)
        self.network_checker = NetworkChecker()
        
        # 使用新的控制器和队列管理器
        self.tello_controller = TelloExtendedController()
        self.queue_manager = None
        
        self.running = False
    
    def initialize(self):
        """初始化编队语音控制系统"""
        print("=== Tello编队语音控制系统初始化 ===")
        print("注意：使用编队模式，保持互联网连接")
        
        # 1. 确认网络连接（保持互联网连接用于API调用）
        print("1. 检查网络连接...")
        if self.network_checker.check_internet_connection():
            print("✓ 互联网连接正常，可以使用API服务")
        else:
            print("✗ 互联网连接异常，将影响语音识别和LLM功能")
            choice = input("是否继续？(y/n): ")
            if choice.lower() != 'y':
                return False
        
        current_wifi = self.network_checker.get_current_wifi()
        print(f"当前WiFi: {current_wifi}")
        
        # 2. 测试LLM连接
        print("2. 测试LLM API连接...")
        if self.llm_client.test_connection():
            print("✓ LLM API连接正常")
        else:
            print("✗ LLM API连接失败，将使用离线模式")
        
        # 3. 测试语音识别
        print("3. 测试百度语音识别...")
        if self.voice_controller.test_voice_recognition():
            print("✓ 百度语音识别正常")
        else:
            print("✗ 百度语音识别失败，请检查麦克风和网络")
        
        # 4. 连接Tello
        print("4. 连接Tello（编队模式）...")
        if not self.tello_controller.connect():
            return False
        
        # 5. 初始化队列管理器
        self.queue_manager = CommandQueueManager(self.tello_controller)
        print("✓ 指令队列管理器已初始化")
        
        print("=== 编队语音控制系统初始化完成 ===\n")
        return True
    
    def execute_command(self, commands):
        """执行语音命令（委托给队列管理器）"""
        if self.queue_manager:
            return self.queue_manager.execute_command(commands)
        else:
            print("❌ 队列管理器未初始化")
            return False
    
    def _execute_single_command(self, command):
        """执行单条指令（UI兼容接口）"""
        return self.execute_command([command])
    
    def get_queue_status(self):
        """获取队列状态"""
        if self.queue_manager:
            return self.queue_manager.get_queue_status()
        return 0
    
    def get_status(self):
        """获取无人机状态"""
        status = self.tello_controller.get_status()
        queue_size = self.get_queue_status()
        if queue_size > 0:
            status += f" | 队列: {queue_size}条指令"
        return status
    
    # 属性兼容（用于UI访问）
    @property
    def connected(self):
        return self.tello_controller.connected
    
    @property
    def flying(self):
        return self.tello_controller.flying
    
    @property
    def single_tello(self):
        return self.tello_controller.single_tello
    
    def run(self):
        """运行编队语音控制程序"""
        try:
            if not self.initialize():
                print("系统初始化失败，退出程序")
                return
            
            self.running = True
            
            print("=== 编队语音控制模式运行中 ===")
            print("正在启动图形界面...")
            
            # 询问用户选择运行模式
            choice = input("选择运行模式：\n1. 图形界面模式 (推荐)\n2. 控制台模式\n请输入 (1/2): ").strip()
            
            if choice == "1":
                self.run_with_ui()
            else:
                self.run_console_mode()
                
        except Exception as e:
            print(f"❌ 运行时错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.shutdown()
    
    def run_with_ui(self):
        """使用图形界面运行"""
        try:
            from voice_ui import VoiceControlUI
            
            print("🚀 启动图形界面...")
            
            # 启动语音监听（不使用键盘钩子）
            self.voice_controller.listening = True
            
            # 创建并运行UI
            ui = VoiceControlUI(self.voice_controller, self)
            ui.run()
            
        except ImportError:
            print("❌ 无法导入UI模块，请检查是否安装了tkinter")
            print("回退到控制台模式...")
            self.run_console_mode()
        except Exception as e:
            print(f"❌ UI启动失败: {e}")
            print("回退到控制台模式...")
            self.run_console_mode()
    
    def run_console_mode(self):
        """控制台模式运行"""
        print("语音控制已启动（百度语音识别 + 按键说话模式）")
        print("保持互联网连接，支持API调用")
        print("支持复合指令：如'先向前飞50厘米，再顺时针旋转45度'")
        print("支持LED控制：如'将灯光调节为粉色'，'设置红色呼吸灯'")
        print("支持点阵屏：如'显示Hello World'，'显示欢迎'")
        print("支持巡航模式：如'开始巡航'，'停止巡航'，'查看测距'")
        print("支持巡线模式：如'开始巡线'，'停止巡线'，'巡线状态'")
        print("💡 按键语音控制模式:")
        print("   - 按 [V] 键激活/关闭语音模式")
        print("   - 按住 [空格] 键说话")
        print("   - 输入 's' 查看状态, 输入 'c' 开始巡航, 输入 'l' 开始巡线")
        print("   - 输入 'x' 停止所有模式, 输入 'q' 退出系统")
        print("-" * 40)
        
        # 启动语音监听（在后台线程中运行）
        voice_thread = self.voice_controller.start_listening()
        
        # 主控制循环 - 简化为轮询模式
        try:
            last_check_time = time.time()
            
            while self.running:
                # 检查语音命令队列
                commands = self.voice_controller.get_command()
                if commands:
                    print(f"🎯 收到语音指令: {commands}")
                    success = self.execute_command(commands)
                    if not success:
                        self.voice_controller.speak("指令执行失败")
                
                # 每秒检查一次用户输入（非阻塞方式）
                current_time = time.time()
                if current_time - last_check_time >= 1.0:
                    last_check_time = current_time
                    
                    # 提示用户可以输入命令
                    try:
                        import msvcrt
                        if msvcrt.kbhit():
                            user_input = input("\n请输入命令 (s=状态, c=巡航, l=巡线, x=停止所有模式, q=退出): ").strip().lower()
                            if user_input == 's':
                                status = self.get_status()
                                print(f"📊 当前状态: {status}")
                                queue_size = self.get_queue_status()
                                if queue_size > 0:
                                    print(f"📋 队列中还有 {queue_size} 条指令等待执行")
                            
                            elif user_input == 'c':
                                # 开始巡航
                                if self.tello_controller.flying:
                                    success = self.execute_command("start_cruise")
                                    if not success:
                                        print("❌ 启动巡航失败")
                                else:
                                    print("⚠ 无人机未在飞行中，无法开始巡航")
                            
                            elif user_input == 'l':
                                # 开始巡线
                                if self.tello_controller.flying:
                                    success = self.execute_command("start_linetrack")
                                    if not success:
                                        print("❌ 启动巡线失败")
                                else:
                                    print("⚠ 无人机未在飞行中，无法开始巡线")
                            
                            elif user_input == 'x':
                                # 停止所有模式
                                success1 = self.execute_command("stop_cruise")
                                success2 = self.execute_command("stop_linetrack")
                                if success1 or success2:
                                    print("✓ 已停止所有自动模式")
                                else:
                                    print("❌ 停止模式失败")
                            
                            elif user_input == 'q':
                                print("🛑 退出系统")
                                self.running = False
                                break
                            
                            elif user_input == 'v':
                                # 手动切换语音模式
                                self.voice_controller.toggle_voice_mode()
                            
                            elif user_input != '':
                                print("❌ 无效输入，请输入 's', 'c', 'l', 'x', 'v' 或 'q'")
                    except:
                        # 如果 msvcrt 不可用，使用简单轮询
                        pass
                
                time.sleep(0.1)  # 避免CPU占用过高
                    
        except KeyboardInterrupt:
            print("\n🛑 收到Ctrl+C信号，正在退出...")
            self.running = False
    
    def shutdown(self):
        """安全关闭编队语音控制系统"""
        print("\n🔄 正在关闭编队语音控制系统...")
        
        self.running = False
        
        # 停止语音监听（优先停止）
        try:
            print("🔇 停止语音监听...")
            self.voice_controller.stop_listening()
        except Exception as e:
            print(f"⚠ 停止语音监听时出错: {e}")
        
        # 停止队列管理器
        try:
            if self.queue_manager:
                self.queue_manager.shutdown()
        except Exception as e:
            print(f"⚠ 关闭队列管理器时出错: {e}")
        
        # 断开Tello连接
        try:
            print("🔌 断开Tello连接...")
            self.tello_controller.disconnect()
        except Exception as e:
            print(f"⚠ 断开Tello连接时出错: {e}")
        
        print("✅ 编队语音控制系统已安全关闭")


def main():
    """主函数"""
    print("Tello编队语音控制系统 v2.4 - 重构版")
    print("作者: 杨垚，乔明梁") 
    print("模式: 编队单机控制 + 百度语音识别 + 复合指令支持 + 巡线功能")
    print("架构: 模块化重构 - 控制器分离")
    print("-" * 40)
    
    # 创建并运行编队控制系统
    control_system = TelloVoiceControl()
    control_system.run()

if __name__ == "__main__":
    main()