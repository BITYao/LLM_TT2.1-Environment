"""
语音控制器 - 使用百度语音识别（按住键说话模式）
"""
import pyttsx3
import threading
import queue
import time
import keyboard
import pyaudio
import wave
import tempfile
from baidu_asr import BaiduASR
from config import VOICE_FEEDBACK, VOICE_RATE, VOICE_VOLUME, AUDIO_SAMPLE_RATE, AUDIO_CHANNELS

class VoiceController:
    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.baidu_asr = BaiduASR()
        
        # 初始化语音合成
        self.tts_engine = pyttsx3.init() if VOICE_FEEDBACK else None
        if self.tts_engine:
            self.tts_engine.setProperty('rate', VOICE_RATE)
            self.tts_engine.setProperty('volume', VOICE_VOLUME)
        
        # 语音命令队列
        self.command_queue = queue.Queue()
        self.listening = False
        self.voice_mode_active = False  # 语音模式是否激活
        self.recording = False  # 是否正在录音
        self.audio_frames = []  # 录音数据
        self.audio_stream = None
        self.audio = None
        
        # 按键配置
        self.activation_key = 'v'  # 激活/关闭语音模式的按键
        self.talk_key = 'space'    # 按住说话的按键
        
        # UI模式标志
        self._ui_mode = False
    
    def speak(self, text):
        """语音反馈"""
        if self.tts_engine and VOICE_FEEDBACK:
            try:
                print(f"语音反馈: {text}")
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
            except:
                print(f"语音反馈失败: {text}")
        else:
            print(f"系统: {text}")
    
    def start_recording(self):
        """开始录音"""
        if self.recording:
            return
            
        try:
            print("🔴 开始录音...")
            self.recording = True
            self.audio_frames = []
            
            # 初始化PyAudio
            if not self.audio:
                self.audio = pyaudio.PyAudio()
            
            # 录音参数
            format = pyaudio.paInt16
            channels = AUDIO_CHANNELS
            rate = AUDIO_SAMPLE_RATE
            chunk = 1024
            
            # 开始录音流
            self.audio_stream = self.audio.open(
                format=format,
                channels=channels,
                rate=rate,
                input=True,
                frames_per_buffer=chunk
            )
            
            # 录音线程
            def record_audio():
                while self.recording and self.audio_stream:
                    try:
                        data = self.audio_stream.read(chunk, exception_on_overflow=False)
                        self.audio_frames.append(data)
                    except Exception as e:
                        print(f"录音错误: {e}")
                        break
            
            self.record_thread = threading.Thread(target=record_audio, daemon=True)
            self.record_thread.start()
            
        except Exception as e:
            print(f"❌ 开始录音失败: {e}")
            self.recording = False
    
    def stop_recording(self):
        """停止录音并返回音频文件路径"""
        if not self.recording:
            return None
            
        try:
            print("🔴 停止录音...")
            self.recording = False
            
            # 等待录音线程结束
            if hasattr(self, 'record_thread'):
                self.record_thread.join(timeout=1)
            
            # 停止音频流
            if self.audio_stream:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
                self.audio_stream = None
            
            # 检查是否有录音数据
            if not self.audio_frames:
                print("❌ 没有录音数据")
                return None
            
            # 保存为临时WAV文件
            temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            with wave.open(temp_file.name, 'wb') as wf:
                wf.setnchannels(AUDIO_CHANNELS)
                wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
                wf.setframerate(AUDIO_SAMPLE_RATE)
                wf.writeframes(b''.join(self.audio_frames))
            
            print(f"✅ 录音完成，文件: {temp_file.name}")
            return temp_file.name
            
        except Exception as e:
            print(f"❌ 停止录音失败: {e}")
            return None
    
    def cleanup_audio(self):
        """清理音频资源"""
        try:
            if self.audio_stream:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
                self.audio_stream = None
            
            if self.audio:
                self.audio.terminate()
                self.audio = None
        except:
            pass
    
    def toggle_voice_mode(self):
        """切换语音模式"""
        self.voice_mode_active = not self.voice_mode_active
        
        if self.voice_mode_active:
            print("🎤 语音模式已激活")
            print(f"💡 按住 [{self.talk_key.upper()}] 键说话")
            print(f"💡 按 [{self.activation_key.upper()}] 键关闭语音模式")
            self.speak("语音模式已激活，按住空格键说话")
        else:
            print("🔇 语音模式已关闭")
            print(f"💡 按 [{self.activation_key.upper()}] 键重新激活语音模式")
            self.speak("语音模式已关闭")
            
            # 如果正在录音，停止录音
            if self.recording:
                self.stop_recording()
    
    def handle_talk_key_press(self):
        """处理按住说话键按下"""
        if not self.voice_mode_active:
            return
            
        if not self.recording:
            self.start_recording()
    
    def handle_talk_key_release(self):
        """处理按住说话键释放"""
        if not self.voice_mode_active:
            return
            
        if self.recording:
            # 停止录音并处理语音
            audio_file = self.stop_recording()
            if audio_file:
                # 在新线程中处理语音识别，避免阻塞
                processing_thread = threading.Thread(
                    target=self.process_recorded_audio,
                    args=(audio_file,),
                    daemon=True
                )
                processing_thread.start()
    
    def process_recorded_audio(self, audio_file):
        """处理录制的音频"""
        try:
            print("🔄 正在处理语音...")
            
            # 识别语音
            voice_text = self.baidu_asr.recognize_audio_file(audio_file)
            
            if voice_text:
                print(f"✅ 识别到语音: '{voice_text}'")
                
                # 使用LLM解析命令
                print(f"🤖 发送到LLM解析: {voice_text}")
                commands = self.llm_client.parse_voice_command(voice_text)
                
                if isinstance(commands, list):
                    if len(commands) > 1:
                        print(f"🎯 LLM解析出复合指令: {voice_text} -> {commands}")
                        valid_commands = [cmd for cmd in commands if cmd != "unknown"]
                        if valid_commands:
                            if len(valid_commands) > 1:
                                self.speak(f"收到复合指令，共{len(valid_commands)}条")
                            else:
                                self.speak(f"收到指令: {valid_commands[0]}")
                            self.command_queue.put(valid_commands)
                            print(f"📥 复合指令已加入队列: {valid_commands}")
                        else:
                            print("❌ 所有指令都无法解析")
                            self.speak("抱歉，无法识别该指令")
                    else:
                        command = commands[0] if commands else "unknown"
                        print(f"🎯 LLM解析结果: {voice_text} -> {command}")
                        if command and command != "unknown":
                            self.speak(f"收到指令: {command}")
                            self.command_queue.put([command])
                            print(f"📥 指令已加入队列: {command}")
                        else:
                            print("❌ 无法解析的指令")
                            self.speak("抱歉，无法识别该指令")
                else:
                    # 兼容旧格式
                    if commands and commands != "unknown":
                        self.speak(f"收到指令: {commands}")
                        self.command_queue.put([commands])
                        print(f"📥 指令已加入队列: {commands}")
                    else:
                        print("❌ 无法解析的指令")
                        self.speak("抱歉，无法识别该指令")
            else:
                print("🔇 未识别到清晰语音")
                self.speak("未识别到清晰语音")
                
        except Exception as e:
            print(f"❌ 语音处理错误: {e}")
            self.speak("语音处理错误")
    
    def setup_keyboard_hooks(self):
        """设置键盘钩子"""
        try:
            # 只在控制台模式下设置全局键盘钩子
            if self._ui_mode:
                print("🖥️ UI模式：不设置全局键盘钩子，使用窗口按键事件")
                return
            
            # 语音模式切换键
            keyboard.on_press_key(self.activation_key, lambda _: self.toggle_voice_mode())
            
            # 按住说话键
            keyboard.on_press_key(self.talk_key, lambda _: self.handle_talk_key_press())
            keyboard.on_release_key(self.talk_key, lambda _: self.handle_talk_key_release())
            
            print(f"✅ 键盘监听已设置:")
            print(f"   [{self.activation_key.upper()}] 键: 激活/关闭语音模式")
            print(f"   [{self.talk_key.upper()}] 键: 按住说话")
            
        except Exception as e:
            print(f"❌ 设置键盘监听失败: {e}")
    
    def set_ui_mode(self, ui_mode=True):
        """设置UI模式标志"""
        self._ui_mode = ui_mode
        if ui_mode:
            print("🖥️ 已切换到UI模式")
        else:
            print("💻 已切换到控制台模式")

    def start_keyboard_listener(self):
        """启动键盘监听"""
        # 在UI模式下不启动键盘监听线程
        if self._ui_mode:
            print("🖥️ UI模式：跳过键盘监听线程启动")
            self.listening = True
            return
        
        self.listening = True
        
        try:
            self.setup_keyboard_hooks()
            
            print("⌨️ 键盘监听已启动")
            print(f"💡 按 [{self.activation_key.upper()}] 键激活语音模式")
            print("💡 主程序继续运行，可输入命令...")
            
            # 这里不再阻塞等待输入，让主程序控制输入逻辑
            while self.listening:
                time.sleep(0.5)  # 定期检查状态
                
        except KeyboardInterrupt:
            print("\n🛑 键盘监听收到退出信号")
            self.listening = False
        except Exception as e:
            print(f"❌ 键盘监听错误: {e}")
            self.listening = False
    
    def start_listening(self):
        """启动语音监听"""
        if self.listening:
            print("⚠ 语音监听已在运行中")
            return None
        
        # 在UI模式下不启动独立的监听线程
        if self._ui_mode:
            self.listening = True
            print("🖥️ UI模式：语音监听已启用")
            return None
            
        listen_thread = threading.Thread(target=self.start_keyboard_listener, daemon=True)
        listen_thread.start()
        
        # 等待一小段时间确保线程启动
        time.sleep(0.5)
        
        return listen_thread
    
    def stop_listening(self):
        """停止语音监听"""
        print("🔇 正在停止语音监听...")
        
        self.listening = False
        self.voice_mode_active = False
        
        # 停止当前录音
        if self.recording:
            try:
                self.stop_recording()
            except Exception as e:
                print(f"⚠ 停止录音时出错: {e}")
        
        # 清理音频资源
        try:
            self.cleanup_audio()
        except Exception as e:
            print(f"⚠ 清理音频资源时出错: {e}")
        
        # 移除键盘钩子（仅在非UI模式下）
        if not self._ui_mode:
            try:
                keyboard.unhook_all()
                print("✅ 键盘钩子已移除")
            except Exception as e:
                print(f"⚠ 移除键盘钩子时出错: {e}")
        
        # 语音反馈
        try:
            if self.tts_engine and VOICE_FEEDBACK:
                self.tts_engine.say("语音控制已停止")
                self.tts_engine.runAndWait()
        except Exception as e:
            print(f"⚠ 语音反馈时出错: {e}")
        
        print("✅ 语音监听已停止")
    
    def record_and_process_voice(self):
        """兼容旧接口：录制并处理语音"""
        if not self.voice_mode_active:
            print("⚠️ 语音模式未激活，请先按 'v' 键激活")
            return None
        
        print(f"🎤 请按住 [{self.talk_key.upper()}] 键说话...")
        return None  # 现在通过按键触发
    
    def get_command(self):
        """获取命令队列中的命令"""
        try:
            command = self.command_queue.get_nowait()
            print(f"📤 从队列取出命令: {command}")
            return command
        except queue.Empty:
            return None
    
    def test_voice_recognition(self):
        """测试百度语音识别"""
        try:
            print("🧪 测试百度语音识别（使用5秒录音）...")
            return self.baidu_asr.test_recognition()
        except Exception as e:
            print(f"❌ 语音识别测试失败: {e}")
            return False