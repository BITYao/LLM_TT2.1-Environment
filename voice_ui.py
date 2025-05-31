"""
语音控制UI界面 - 增强版动效
"""
import tkinter as tk
from tkinter import ttk
import threading
import time
import math
import random
from tkinter import scrolledtext

class VoiceControlUI:
    def __init__(self, voice_controller, tello_controller):
        self.voice_controller = voice_controller
        self.tello_controller = tello_controller
        
        # 界面控制标志 - 必须在最开始初始化
        self.ui_running = True
        self.is_recording = False  # 防止重复录音
        
        # 动效控制变量
        self.animation_running = True
        self.recording_animation_active = False
        self.connection_animation_active = False
        self.battery_pulse_active = False
        
        # 创建主窗口
        self.root = tk.Tk()
        self.root.title("🚁 Tello语音控制系统 v2.4 - 动效增强版")
        self.root.geometry("900x650")
        self.root.resizable(True, True)
        
        # 设置语音控制器为UI模式
        self.voice_controller.set_ui_mode(True)
        
        # 设置窗口图标和样式
        self.setup_styles()
        
        # 界面变量
        self.voice_mode_active = tk.BooleanVar(value=False)
        self.recording_active = tk.BooleanVar(value=False)
        self.connection_status = tk.StringVar(value="未连接")
        self.battery_level = tk.StringVar(value="--")
        self.flight_status = tk.StringVar(value="地面")
        self.queue_count = tk.StringVar(value="0")
        
        # 动效状态变量
        self.recording_color_phase = 0
        self.connection_icon_rotation = 0
        self.battery_pulse_phase = 0
        
        # 创建界面
        self.create_widgets()
        
        # 绑定按键事件
        self.setup_key_bindings()
        
        # 启动动效系统
        self.start_animations()
        
        # 启动状态更新线程
        self.start_status_update()
        
        # 设置窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_styles(self):
        """设置界面样式"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # 配置颜色主题
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'), foreground='#2E86AB')
        style.configure('Status.TLabel', font=('Arial', 10))
        style.configure('Recording.TLabel', font=('Arial', 12, 'bold'), foreground='red')
        style.configure('Active.TButton', font=('Arial', 10, 'bold'))
        style.configure('Emergency.TButton', font=('Arial', 10, 'bold'), foreground='white')
        
        # 设置主题色
        style.configure('Success.TLabel', foreground='#27AE60')
        style.configure('Warning.TLabel', foreground='#F39C12')
        style.configure('Error.TLabel', foreground='#E74C3C')
    
    def create_widgets(self):
        """创建界面组件"""
        # 主容器
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # 动态标题 - 添加动效容器
        title_frame = ttk.Frame(main_frame)
        title_frame.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        self.title_label = ttk.Label(title_frame, text="🚁 Tello语音控制系统", style='Title.TLabel')
        self.title_label.grid(row=0, column=0)
        
        self.status_indicator = ttk.Label(title_frame, text="●", font=('Arial', 20), foreground='gray')
        self.status_indicator.grid(row=0, column=1, padx=(10, 0))
        
        # 左侧控制面板
        self.create_control_panel(main_frame)
        
        # 中间状态面板
        self.create_status_panel(main_frame)
        
        # 右侧日志面板
        self.create_log_panel(main_frame)
        
        # 底部按钮区域
        self.create_button_panel(main_frame)
    
    def create_control_panel(self, parent):
        """创建控制面板"""
        control_frame = ttk.LabelFrame(parent, text="🎤 语音控制", padding="15")
        control_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        
        # 语音模式状态 - 添加动效指示器
        mode_frame = ttk.Frame(control_frame)
        mode_frame.grid(row=0, column=0, pady=5, sticky=(tk.W, tk.E))
        
        self.voice_mode_label = ttk.Label(mode_frame, text="语音模式: 关闭", style='Status.TLabel')
        self.voice_mode_label.grid(row=0, column=0, sticky=tk.W)
        
        self.mode_indicator = ttk.Label(mode_frame, text="⭕", font=('Arial', 14))
        self.mode_indicator.grid(row=0, column=1, padx=(10, 0))
        
        # 语音模式切换按钮
        self.voice_toggle_btn = ttk.Button(
            control_frame, 
            text="🎙️ 激活语音模式 (V)", 
            command=self.toggle_voice_mode,
            style='Active.TButton'
        )
        self.voice_toggle_btn.grid(row=1, column=0, pady=8, sticky=(tk.W, tk.E))
        
        # 录音状态指示 - 增强版
        recording_frame = ttk.Frame(control_frame)
        recording_frame.grid(row=2, column=0, pady=5, sticky=(tk.W, tk.E))
        
        self.recording_label = ttk.Label(
            recording_frame, 
            text="⭕ 未录音", 
            style='Status.TLabel'
        )
        self.recording_label.grid(row=0, column=0, sticky=tk.W)
        
        # 录音波形指示器
        self.wave_indicator = ttk.Label(recording_frame, text="", font=('Arial', 12))
        self.wave_indicator.grid(row=0, column=1, padx=(10, 0))
        
        # 按住说话按钮 - 增强版
        self.talk_btn = ttk.Button(
            control_frame,
            text="🎤 按住说话 (空格)",
            state=tk.DISABLED
        )
        self.talk_btn.grid(row=3, column=0, pady=8, sticky=(tk.W, tk.E))
        
        # 绑定按钮按下和释放事件
        self.talk_btn.bind('<Button-1>', self.start_recording)
        self.talk_btn.bind('<ButtonRelease-1>', self.stop_recording)
        
        # 音量指示器
        self.volume_frame = ttk.Frame(control_frame)
        self.volume_frame.grid(row=4, column=0, pady=5, sticky=(tk.W, tk.E))
        
        ttk.Label(self.volume_frame, text="音量:", style='Status.TLabel').grid(row=0, column=0, sticky=tk.W)
        self.volume_bar = ttk.Progressbar(self.volume_frame, mode='determinate', length=150)
        self.volume_bar.grid(row=0, column=1, padx=(5, 0), sticky=(tk.W, tk.E))
        
        # 说明文字
        help_text = """
✨ 使用说明：
1. 点击"激活语音模式"或按V键
2. 按住"说话"按钮或空格键
3. 松开按钮完成录音识别
4. 支持复合指令，如：
   "先起飞，再向前飞50厘米"
        """
        help_label = ttk.Label(control_frame, text=help_text, style='Status.TLabel', justify=tk.LEFT)
        help_label.grid(row=5, column=0, pady=15, sticky=tk.W)
    
    def create_status_panel(self, parent):
        """创建状态面板"""
        status_frame = ttk.LabelFrame(parent, text="📊 系统状态", padding="15")
        status_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        status_frame.columnconfigure(1, weight=1)
        
        # 连接状态 - 添加动效
        connection_frame = ttk.Frame(status_frame)
        connection_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=3)
        
        ttk.Label(connection_frame, text="连接状态:", style='Status.TLabel').grid(row=0, column=0, sticky=tk.W)
        self.connection_label = ttk.Label(connection_frame, textvariable=self.connection_status, style='Status.TLabel')
        self.connection_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
        self.connection_icon = ttk.Label(connection_frame, text="📡", font=('Arial', 16))
        self.connection_icon.grid(row=0, column=2, padx=(10, 0))
        
        # 电池电量 - 增强版
        battery_frame = ttk.Frame(status_frame)
        battery_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=3)
        
        ttk.Label(battery_frame, text="电池电量:", style='Status.TLabel').grid(row=0, column=0, sticky=tk.W)
        self.battery_label = ttk.Label(battery_frame, textvariable=self.battery_level, style='Status.TLabel')
        self.battery_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
        self.battery_icon = ttk.Label(battery_frame, text="🔋", font=('Arial', 16))
        self.battery_icon.grid(row=0, column=2, padx=(10, 0))
        
        # 飞行状态
        flight_frame = ttk.Frame(status_frame)
        flight_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=3)
        
        ttk.Label(flight_frame, text="飞行状态:", style='Status.TLabel').grid(row=0, column=0, sticky=tk.W)
        self.flight_label = ttk.Label(flight_frame, textvariable=self.flight_status, style='Status.TLabel')
        self.flight_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
        self.flight_icon = ttk.Label(flight_frame, text="🚁", font=('Arial', 16))
        self.flight_icon.grid(row=0, column=2, padx=(10, 0))
        
        # 队列状态
        queue_frame = ttk.Frame(status_frame)
        queue_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=3)
        
        ttk.Label(queue_frame, text="指令队列:", style='Status.TLabel').grid(row=0, column=0, sticky=tk.W)
        self.queue_label = ttk.Label(queue_frame, textvariable=self.queue_count, style='Status.TLabel')
        self.queue_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
        self.queue_icon = ttk.Label(queue_frame, text="📋", font=('Arial', 16))
        self.queue_icon.grid(row=0, column=2, padx=(10, 0))
        
        # 进度条（电池电量）- 增强版
        progress_frame = ttk.Frame(status_frame)
        progress_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=8)
        
        ttk.Label(progress_frame, text="电量进度:", style='Status.TLabel').grid(row=0, column=0, sticky=tk.W)
        self.battery_progress = ttk.Progressbar(progress_frame, mode='determinate', length=250)
        self.battery_progress.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        
        # LED状态指示
        self.led_status = ttk.Label(status_frame, text="💡 LED: 未设置", style='Status.TLabel')
        self.led_status.grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=8)
        
        # 系统运行时间
        self.runtime_label = ttk.Label(status_frame, text="⏱️ 运行时间: 00:00:00", style='Status.TLabel')
        self.runtime_label.grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=3)
        
        # 记录启动时间
        self.start_time = time.time()
        
        # 视觉感知状态
        vision_frame = ttk.Frame(status_frame)
        vision_frame.grid(row=7, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=3)
        
        ttk.Label(vision_frame, text="视觉感知:", style='Status.TLabel').grid(row=0, column=0, sticky=tk.W)
        self.vision_status = ttk.Label(vision_frame, text="未启动", style='Status.TLabel')
        self.vision_status.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
        self.vision_icon = ttk.Label(vision_frame, text="👁️", font=('Arial', 16))
        self.vision_icon.grid(row=0, column=2, padx=(10, 0))
        
        # 最新识别结果
        recognition_frame = ttk.Frame(status_frame)
        recognition_frame.grid(row=8, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=3)
        
        ttk.Label(recognition_frame, text="识别结果:", style='Status.TLabel').grid(row=0, column=0, sticky=tk.W)
        self.recognition_result = ttk.Label(recognition_frame, text="无", style='Status.TLabel')
        self.recognition_result.grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
    
    def create_log_panel(self, parent):
        """创建日志面板"""
        log_frame = ttk.LabelFrame(parent, text="📝 系统日志", padding="10")
        log_frame.grid(row=1, column=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(10, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        # 日志文本框
        self.log_text = scrolledtext.ScrolledText(
            log_frame, 
            height=20, 
            width=40, 
            wrap=tk.WORD,
            font=('Consolas', 9)
        )
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 清空日志按钮
        clear_btn = ttk.Button(log_frame, text="清空日志", command=self.clear_log)
        clear_btn.grid(row=1, column=0, pady=5, sticky=tk.E)
    
    def create_button_panel(self, parent):
        """创建底部按钮面板"""
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=2, column=0, columnspan=3, pady=20, sticky=(tk.W, tk.E))
        
        # 第一行按钮
        row1_frame = ttk.Frame(button_frame)
        row1_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # 紧急控制按钮
        emergency_btn = ttk.Button(
            row1_frame, 
            text="🚨 紧急停止", 
            command=self.emergency_stop,
            style='Active.TButton'
        )
        emergency_btn.grid(row=0, column=0, padx=5)
        
        # 起飞按钮
        takeoff_btn = ttk.Button(row1_frame, text="🛫 起飞", command=self.takeoff)
        takeoff_btn.grid(row=0, column=1, padx=5)
        
        # 降落按钮
        land_btn = ttk.Button(row1_frame, text="🛬 降落", command=self.land)
        land_btn.grid(row=0, column=2, padx=5)
        
        # 刷新状态按钮
        refresh_btn = ttk.Button(row1_frame, text="🔄 刷新状态", command=self.refresh_status)
        refresh_btn.grid(row=0, column=3, padx=5)
        
        # 退出按钮
        exit_btn = ttk.Button(row1_frame, text="❌ 退出系统", command=self.on_closing)
        exit_btn.grid(row=0, column=4, padx=5)
        
        # 第二行按钮 - 视觉控制
        row2_frame = ttk.Frame(button_frame)
        row2_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # 视觉控制按钮
        vision_btn = ttk.Button(row2_frame, text="📹 启动视频", command=self.toggle_video)
        vision_btn.grid(row=0, column=0, padx=5)
        
        capture_btn = ttk.Button(row2_frame, text="📸 拍照", command=self.capture_image)
        capture_btn.grid(row=0, column=1, padx=5)
        
        recognize_btn = ttk.Button(row2_frame, text="🔍 识别", command=self.recognize_view)
        recognize_btn.grid(row=0, column=2, padx=5)
        
        # 新增：语音描述控制按钮
        speech_toggle_btn = ttk.Button(row2_frame, text="📢 切换描述", command=self.toggle_speech_description)
        speech_toggle_btn.grid(row=0, column=3, padx=5)
        
        speak_result_btn = ttk.Button(row2_frame, text="🔊 播报结果", command=self.speak_latest_result)
        speak_result_btn.grid(row=0, column=4, padx=5)
        
        test_speech_btn = ttk.Button(row2_frame, text="🎵 测试语音", command=self.test_speech)
        test_speech_btn.grid(row=0, column=5, padx=5)
    
    def setup_key_bindings(self):
        """设置键盘绑定"""
        # 绑定按键事件到窗口
        self.root.bind('<KeyPress-v>', self.on_v_key_press)
        self.root.bind('<KeyPress-V>', self.on_v_key_press)
        
        # 绑定空格键按下和释放 - 仅在窗口获得焦点时
        self.root.bind('<KeyPress-space>', self.on_space_press)
        self.root.bind('<KeyRelease-space>', self.on_space_release)
        
        # 让窗口可以接收焦点
        self.root.focus_set()
        
        # 绑定窗口焦点事件
        self.root.bind('<FocusIn>', self.on_focus_in)
        self.root.bind('<FocusOut>', self.on_focus_out)
    
    def on_focus_in(self, event):
        """窗口获得焦点"""
        self.log_message("💡 窗口获得焦点，按键控制已激活")
    
    def on_focus_out(self, event):
        """窗口失去焦点"""
        # 如果正在录音，停止录音
        if self.is_recording:
            self.stop_recording(event)
        self.log_message("⚠ 窗口失去焦点，按键控制已停用")
    
    def on_v_key_press(self, event):
        """V键按下事件 - 防止重复触发"""
        try:
            # 延迟处理，避免重复触发
            self.root.after(100, self.toggle_voice_mode)
        except Exception as e:
            self.log_message(f"❌ V键处理错误: {e}")
    
    def on_space_press(self, event):
        """空格键按下事件"""
        if self.voice_mode_active.get() and not self.is_recording:
            self.start_recording(event)
    
    def on_space_release(self, event):
        """空格键释放事件"""
        if self.voice_mode_active.get() and self.is_recording:
            self.stop_recording(event)
    
    def toggle_voice_mode(self):
        """切换语音模式 - 增强版"""
        try:
            # 防止重复调用
            if hasattr(self, '_toggling') and self._toggling:
                return
            
            self._toggling = True
            
            self.voice_controller.toggle_voice_mode()
            active = self.voice_controller.voice_mode_active
            self.voice_mode_active.set(active)
            
            if active:
                self.voice_mode_label.config(text="语音模式: 🟢 激活", foreground='green')
                self.voice_toggle_btn.config(text="🔇 关闭语音模式 (V)")
                self.talk_btn.config(state=tk.NORMAL)
                self.mode_indicator.config(text="🟢", foreground='green')
                self.status_indicator.config(foreground='green')
                self.log_message("✅ 语音模式已激活")
                
                # 激活连接动效
                self.connection_animation_active = True
                
            else:
                self.voice_mode_label.config(text="语音模式: 🔴 关闭", foreground='red')
                self.voice_toggle_btn.config(text="🎙️ 激活语音模式 (V)")
                self.talk_btn.config(state=tk.DISABLED)
                self.mode_indicator.config(text="🔴", foreground='red')
                self.status_indicator.config(foreground='gray')
                self.recording_label.config(text="⭕ 未录音")
                self.wave_indicator.config(text="")
                self.log_message("❌ 语音模式已关闭")
                
                # 停止动效
                self.recording_animation_active = False
                self.connection_animation_active = False
                
                # 如果正在录音，停止录音
                if self.is_recording:
                    self.is_recording = False
                    self.recording_active.set(False)
            
            # 延迟重置标志
            self.root.after(500, lambda: setattr(self, '_toggling', False))
                
        except Exception as e:
            self.log_message(f"❌ 切换语音模式失败: {e}")
            self._toggling = False
    
    def start_recording(self, event):
        """开始录音 - 增强版"""
        if not self.voice_mode_active.get() or self.is_recording:
            return
            
        try:
            self.voice_controller.handle_talk_key_press()
            self.is_recording = True
            self.recording_active.set(True)
            self.recording_label.config(text="🔴 正在录音...", foreground='red')
            self.talk_btn.config(text="🎤 录音中... (松开结束)")
            self.log_message("🎤 开始录音...")
            
            # 启动录音动效
            self.recording_animation_active = True
            
        except Exception as e:
            self.log_message(f"❌ 开始录音失败: {e}")
            self.is_recording = False
    
    def stop_recording(self, event):
        """停止录音 - 增强版"""
        if not self.is_recording:
            return
            
        try:
            self.voice_controller.handle_talk_key_release()
            self.is_recording = False
            self.recording_active.set(False)
            self.recording_label.config(text="🔄 处理中...", foreground='orange')
            self.talk_btn.config(text="🎤 按住说话 (空格)")
            self.wave_indicator.config(text="⏳")
            self.log_message("🔄 录音结束，正在处理...")
            
            # 停止录音动效
            self.recording_animation_active = False
            
            # 延迟重置状态
            self.root.after(2000, self.reset_recording_status)
        except Exception as e:
            self.log_message(f"❌ 停止录音失败: {e}")
            self.is_recording = False
    
    def reset_recording_status(self):
        """重置录音状态 - 增强版"""
        if self.voice_mode_active.get() and not self.is_recording:
            self.recording_label.config(text="⭕ 等待录音", foreground='black')
            self.wave_indicator.config(text="")
    
    def emergency_stop(self):
        """紧急停止"""
        try:
            # 直接调用无人机紧急停止
            self.tello_controller._execute_single_command("stop")
            self.log_message("🚨 紧急停止已执行")
        except Exception as e:
            self.log_message(f"❌ 紧急停止失败: {e}")
    
    def takeoff(self):
        """起飞"""
        try:
            self.tello_controller._execute_single_command("takeoff")
            self.log_message("🛫 起飞指令已发送")
        except Exception as e:
            self.log_message(f"❌ 起飞失败: {e}")
    
    def land(self):
        """降落"""
        try:
            self.tello_controller._execute_single_command("land")
            self.log_message("🛬 降落指令已发送")
        except Exception as e:
            self.log_message(f"❌ 降落失败: {e}")
    
    def refresh_status(self):
        """刷新状态"""
        self.update_status()
        self.log_message("🔄 状态已刷新")
    
    def clear_log(self):
        """清空日志"""
        self.log_text.delete(1.0, tk.END)
    
    def log_message(self, message):
        """添加日志消息"""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
        
        # 限制日志行数
        lines = self.log_text.get(1.0, tk.END).split('\n')
        if len(lines) > 1000:
            # 删除前面的行
            self.log_text.delete(1.0, f"{len(lines) - 800}.0")
    
    def start_animations(self):
        """启动动效系统"""
        def animation_loop():
            while self.animation_running:
                try:
                    # 录音动效
                    if self.recording_animation_active:
                        self.update_recording_animation()
                    
                    # 连接状态动效
                    if self.connection_animation_active:
                        self.update_connection_animation()
                    
                    # 电池脉冲动效
                    if self.battery_pulse_active:
                        self.update_battery_pulse()
                    
                    # 更新运行时间
                    self.update_runtime()
                    
                    # 音量指示器动效
                    self.update_volume_animation()
                    
                    time.sleep(0.1)  # 100ms刷新率
                except Exception as e:
                    pass
        
        animation_thread = threading.Thread(target=animation_loop, daemon=True)
        animation_thread.start()
    
    def update_recording_animation(self):
        """更新录音动效"""
        try:
            # 波形动画
            wave_chars = ["", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
            self.recording_color_phase += 0.3
            
            # 生成波形
            wave_pattern = ""
            for i in range(8):
                height_index = int((math.sin(self.recording_color_phase + i * 0.5) + 1) * 4)
                wave_pattern += wave_chars[min(height_index, len(wave_chars) - 1)]
            
            self.root.after(0, lambda: self.wave_indicator.config(text=wave_pattern, foreground='red'))
            
            # 录音标签颜色脉冲
            color_intensity = int((math.sin(self.recording_color_phase) + 1) * 127 + 128)
            color = f"#{color_intensity:02x}0000"
            self.root.after(0, lambda: self.recording_label.config(foreground=color))
            
        except Exception as e:
            pass
    
    def update_connection_animation(self):
        """更新连接动效"""
        try:
            # 旋转连接图标
            self.connection_icon_rotation += 15
            if self.connection_icon_rotation >= 360:
                self.connection_icon_rotation = 0
            
            # 根据旋转角度改变图标
            icons = ["📡", "📶", "📳", "📶"]
            icon_index = (self.connection_icon_rotation // 90) % len(icons)
            self.root.after(0, lambda: self.connection_icon.config(text=icons[icon_index]))
            
        except Exception as e:
            pass
    
    def update_battery_pulse(self):
        """更新电池脉冲动效"""
        try:
            self.battery_pulse_phase += 0.2
            
            # 电池图标脉冲
            scale = 1 + 0.1 * math.sin(self.battery_pulse_phase)
            size = int(16 * scale)
            
            # 低电量时红色脉冲
            if hasattr(self, 'current_battery') and self.current_battery < 20:
                color_intensity = int((math.sin(self.battery_pulse_phase * 2) + 1) * 127 + 128)
                color = f"#{color_intensity:02x}0000"
                self.root.after(0, lambda: self.battery_label.config(foreground=color))
            
        except Exception as e:
            pass
    
    def update_runtime(self):
        """更新运行时间"""
        try:
            runtime = int(time.time() - self.start_time)
            hours = runtime // 3600
            minutes = (runtime % 3600) // 60
            seconds = runtime % 60
            time_str = f"⏱️ 运行时间: {hours:02d}:{minutes:02d}:{seconds:02d}"
            self.root.after(0, lambda: self.runtime_label.config(text=time_str))
        except Exception as e:
            pass
    
    def update_volume_animation(self):
        """更新音量指示器动效"""
        try:
            # 模拟音量变化
            if self.is_recording:
                volume = random.randint(30, 100)
            else:
                volume = random.randint(0, 20)
            
            self.root.after(0, lambda: setattr(self.volume_bar, 'value', volume))
        except Exception as e:
            pass
    
    def start_status_update(self):
        """启动状态更新线程"""
        def update_loop():
            while self.ui_running:
                try:
                    self.update_status()
                    time.sleep(2)  # 每2秒更新一次
                except Exception as e:
                    print(f"状态更新错误: {e}")
                    time.sleep(1)
        
        update_thread = threading.Thread(target=update_loop, daemon=True)
        update_thread.start()
    
    def update_status(self):
        """更新状态显示 - 增强版（包含视觉状态）"""
        try:
            # 更新连接状态
            if self.tello_controller.connected:
                self.connection_status.set("🟢 已连接")
                self.connection_label.config(foreground='green')
                
                # 更新电池电量
                try:
                    battery = self.tello_controller.single_tello.get_battery()
                    self.current_battery = battery
                    self.battery_level.set(f"{battery}%")
                    self.battery_progress['value'] = battery
                    
                    # 根据电量设置颜色和动效
                    if battery < 20:
                        self.battery_label.config(foreground='red')
                        self.battery_pulse_active = True
                        self.battery_icon.config(text="🪫")
                    elif battery < 50:
                        self.battery_label.config(foreground='orange')
                        self.battery_pulse_active = False
                        self.battery_icon.config(text="🔋")
                    else:
                        self.battery_label.config(foreground='green')
                        self.battery_pulse_active = False
                        self.battery_icon.config(text="🔋")
                        
                except:
                    self.battery_level.set("获取失败")
                    self.battery_progress['value'] = 0
                
                # 更新飞行状态
                if self.tello_controller.flying:
                    self.flight_status.set("🟢 飞行中")
                    self.flight_label.config(foreground='green')
                    self.flight_icon.config(text="🚁")
                else:
                    self.flight_status.set("🔴 地面")
                    self.flight_label.config(foreground='black')
                    self.flight_icon.config(text="🛬")
                    
            else:
                self.connection_status.set("🔴 未连接")
                self.connection_label.config(foreground='red')
                self.battery_level.set("--")
                self.flight_status.set("未知")
                self.battery_progress['value'] = 0
                self.connection_icon.config(text="📵")
            
            # 更新队列状态
            queue_size = self.tello_controller.get_queue_status()
            self.queue_count.set(f"{queue_size} 条指令")
            
            # 队列动态图标
            if queue_size > 0:
                self.queue_icon.config(text="📝")
            else:
                self.queue_icon.config(text="📋")
            
            # 检查语音命令队列
            commands = self.voice_controller.get_command()
            if commands:
                self.log_message(f"🎯 收到语音指令: {commands}")
                success = self.tello_controller.execute_command(commands)
                if success:
                    self.log_message("✅ 指令执行成功")
                else:
                    self.log_message("❌ 指令执行失败")
            
            # 更新视觉感知状态
            if hasattr(self.tello_controller, 'vision_module') and self.tello_controller.vision_module:
                vision_module = self.tello_controller.vision_module
                
                if vision_module.video_streaming:
                    self.vision_status.config(text="🟢 视频流开启", foreground='green')
                    self.vision_icon.config(text="📹")
                else:
                    self.vision_status.config(text="🔴 视频流关闭", foreground='red')
                    self.vision_icon.config(text="👁️")
                
                # 更新识别结果
                self.update_recognition_result()
                
                # 更新语音状态指示
                if hasattr(vision_module, 'auto_description_enabled'):
                    if vision_module.auto_description_enabled:
                        queue_size = vision_module.speech_synthesis.get_queue_size()
                        if queue_size > 0:
                            self.log_message(f"🔊 语音队列: {queue_size}条待播报")
            else:
                self.vision_status.config(text="未初始化", foreground='gray')
                self.vision_icon.config(text="❌")
                    
        except Exception as e:
            pass  # 静默处理更新错误
    
    def toggle_video(self):
        """切换视频流"""
        try:
            if hasattr(self.tello_controller, 'vision_module') and self.tello_controller.vision_module:
                if self.tello_controller.vision_module.video_streaming:
                    success = self.tello_controller.execute_vision_command("stop_video")
                    if success:
                        self.log_message("📹 视频流已停止")
                else:
                    success = self.tello_controller.execute_vision_command("start_video")
                    if success:
                        self.log_message("📹 视频流已启动")
            else:
                self.log_message("❌ 视觉模块未初始化")
        except Exception as e:
            self.log_message(f"❌ 视频控制失败: {e}")
    
    def capture_image(self):
        """捕获图片"""
        try:
            success = self.tello_controller.execute_vision_command("capture_image")
            if success:
                self.log_message("📸 图片捕获成功")
            else:
                self.log_message("❌ 图片捕获失败")
        except Exception as e:
            self.log_message(f"❌ 图片捕获错误: {e}")
    
    def recognize_view(self):
        """识别当前视野"""
        try:
            success = self.tello_controller.execute_vision_command("recognize_view")
            if success:
                self.log_message("🔍 视野识别完成")
                # 更新识别结果显示
                self.update_recognition_result()
            else:
                self.log_message("❌ 视野识别失败")
        except Exception as e:
            self.log_message(f"❌ 视野识别错误: {e}")
    
    def toggle_speech_description(self):
        """切换语音描述功能"""
        try:
            if hasattr(self.tello_controller, 'vision_module') and self.tello_controller.vision_module:
                enabled = self.tello_controller.vision_module.toggle_auto_description()
                status = "开启" if enabled else "关闭"
                self.log_message(f"📢 智能描述播报已{status}")
            else:
                self.log_message("❌ 视觉模块未初始化")
        except Exception as e:
            self.log_message(f"❌ 切换语音描述失败: {e}")
    
    def speak_latest_result(self):
        """播报最新识别结果"""
        try:
            if hasattr(self.tello_controller, 'vision_module') and self.tello_controller.vision_module:
                self.tello_controller.vision_module.speak_recognition_result()
                self.log_message("🔊 正在播报最新识别结果")
            else:
                self.log_message("❌ 视觉模块未初始化")
        except Exception as e:
            self.log_message(f"❌ 播报识别结果失败: {e}")
    
    def test_speech(self):
        """测试语音合成"""
        try:
            if hasattr(self.tello_controller, 'vision_module') and self.tello_controller.vision_module:
                success = self.tello_controller.vision_module.test_speech_synthesis()
                if success:
                    self.log_message("✅ 语音合成测试成功")
                else:
                    self.log_message("❌ 语音合成测试失败")
            else:
                self.log_message("❌ 视觉模块未初始化")
        except Exception as e:
            self.log_message(f"❌ 语音合成测试异常: {e}")
    
    def update_recognition_result(self):
        """更新识别结果显示"""
        try:
            if hasattr(self.tello_controller, 'vision_module') and self.tello_controller.vision_module:
                result = self.tello_controller.vision_module.get_latest_recognition()
                if result:
                    summary = self.tello_controller.vision_module.baidu_vision.format_recognition_summary(result)
                    self.recognition_result.config(text=summary[:50] + "..." if len(summary) > 50 else summary)
                else:
                    self.recognition_result.config(text="无")
        except Exception as e:
            pass
    
    def on_closing(self):
        """窗口关闭事件 - 增强版"""
        self.log_message("🔄 正在关闭UI...")
        self.ui_running = False
        self.animation_running = False
        
        # 停止所有动效
        self.recording_animation_active = False
        self.connection_animation_active = False
        self.battery_pulse_active = False
        
        # 停止录音
        if self.is_recording:
            self.is_recording = False
            try:
                self.voice_controller.handle_talk_key_release()
            except:
                pass
        
        # 停止语音控制
        try:
            self.voice_controller.stop_listening()
        except Exception as e:
            print(f"停止语音控制错误: {e}")
        
        # 关闭主控制器
        try:
            self.tello_controller.running = False
        except:
            pass
        
        self.root.quit()
        self.root.destroy()
    
    def run(self):
        """运行UI - 增强版"""
        self.log_message("🚀 语音控制UI已启动 - 动效增强版")
        self.log_message("✨ 界面动效已激活")
        self.log_message("💡 按V键或点击按钮激活语音模式")
        self.log_message("💡 按住空格键或按钮进行语音录制")
        self.log_message("💡 确保窗口获得焦点以使用按键控制")
        
        try:
            self.root.mainloop()
        except Exception as e:
            print(f"UI运行错误: {e}")
        finally:
            self.ui_running = False
