"""
语音合成模块 - 文字转语音播报
"""
import pyttsx3
import threading
import queue
import time
from config import TTS_ENABLED, TTS_VOICE_ID, TTS_RATE, TTS_VOLUME

class SpeechSynthesis:
    def __init__(self):
        self.enabled = TTS_ENABLED
        self.engine = None
        self.speaking_queue = queue.Queue()
        self.speaking_thread = None
        self.speaking_running = False
        
        # 初始化TTS引擎
        self._init_tts_engine()
        
        # 启动语音播报线程
        if self.enabled:
            self.start_speaking_service()
    
    def _init_tts_engine(self):
        """初始化TTS引擎"""
        try:
            if not self.enabled:
                return
            
            print("🔊 初始化语音合成引擎...")
            self.engine = pyttsx3.init()
            
            # 设置语音参数
            voices = self.engine.getProperty('voices')
            if voices and len(voices) > TTS_VOICE_ID:
                self.engine.setProperty('voice', voices[TTS_VOICE_ID].id)
                print(f"✅ 设置语音: {voices[TTS_VOICE_ID].name}")
            
            self.engine.setProperty('rate', TTS_RATE)
            self.engine.setProperty('volume', TTS_VOLUME)
            
            print(f"✅ 语音合成引擎初始化成功")
            print(f"   语音速度: {TTS_RATE}")
            print(f"   音量: {TTS_VOLUME}")
            
        except Exception as e:
            print(f"❌ 语音合成引擎初始化失败: {e}")
            self.enabled = False
    
    def speak(self, text, priority=False):
        """
        添加文本到语音播报队列
        
        Args:
            text: 要播报的文本
            priority: 是否优先播报（插队）
        """
        if not self.enabled or not text:
            return
        
        try:
            if priority:
                # 优先播报，插入队列头部
                temp_queue = queue.Queue()
                temp_queue.put(text)
                
                # 将原队列内容放到临时队列后面
                while not self.speaking_queue.empty():
                    try:
                        item = self.speaking_queue.get_nowait()
                        temp_queue.put(item)
                    except queue.Empty:
                        break
                
                # 替换原队列
                self.speaking_queue = temp_queue
                print(f"🔊 优先语音播报: {text}")
            else:
                self.speaking_queue.put(text)
                print(f"🔊 添加语音播报: {text}")
                
        except Exception as e:
            print(f"❌ 添加语音播报失败: {e}")
    
    def speak_now(self, text):
        """立即播报（阻塞式）"""
        if not self.enabled or not self.engine:
            return
        
        try:
            print(f"🔊 立即播报: {text}")
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as e:
            print(f"❌ 立即播报失败: {e}")
    
    def start_speaking_service(self):
        """启动语音播报服务线程"""
        if self.speaking_running or not self.enabled:
            return
        
        self.speaking_running = True
        self.speaking_thread = threading.Thread(target=self._speaking_worker, daemon=True)
        self.speaking_thread.start()
        print("✅ 语音播报服务已启动")
    
    def stop_speaking_service(self):
        """停止语音播报服务"""
        if not self.speaking_running:
            return
        
        print("🔊 停止语音播报服务...")
        self.speaking_running = False
        
        if self.speaking_thread:
            self.speaking_thread.join(timeout=3)
        
        print("✅ 语音播报服务已停止")
    
    def _speaking_worker(self):
        """语音播报工作线程"""
        while self.speaking_running:
            try:
                # 从队列获取文本（阻塞式，超时1秒）
                text = self.speaking_queue.get(timeout=1)
                
                if text and self.enabled and self.engine:
                    print(f"🔊 正在播报: {text}")
                    self.engine.say(text)
                    self.engine.runAndWait()
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ 语音播报错误: {e}")
                time.sleep(1)
        
        print("🔊 语音播报线程已退出")
    
    def clear_queue(self):
        """清空语音播报队列"""
        cleared_count = 0
        while not self.speaking_queue.empty():
            try:
                self.speaking_queue.get_nowait()
                cleared_count += 1
            except queue.Empty:
                break
        
        if cleared_count > 0:
            print(f"🔊 已清空 {cleared_count} 条语音播报")
    
    def set_voice_params(self, rate=None, volume=None, voice_id=None):
        """动态设置语音参数"""
        if not self.enabled or not self.engine:
            return False
        
        try:
            if rate is not None:
                self.engine.setProperty('rate', rate)
                print(f"🔊 语音速度已设置为: {rate}")
            
            if volume is not None:
                self.engine.setProperty('volume', volume)
                print(f"🔊 音量已设置为: {volume}")
            
            if voice_id is not None:
                voices = self.engine.getProperty('voices')
                if voices and len(voices) > voice_id:
                    self.engine.setProperty('voice', voices[voice_id].id)
                    print(f"🔊 语音已切换为: {voices[voice_id].name}")
            
            return True
            
        except Exception as e:
            print(f"❌ 设置语音参数失败: {e}")
            return False
    
    def get_queue_size(self):
        """获取播报队列大小"""
        return self.speaking_queue.qsize()
    
    def test_speech(self):
        """测试语音合成"""
        try:
            if not self.enabled:
                print("⚠ 语音合成未启用")
                return False
            
            test_text = "语音合成测试成功，我是无人机的声音助手。"
            self.speak_now(test_text)
            return True
            
        except Exception as e:
            print(f"❌ 语音合成测试失败: {e}")
            return False
    
    def shutdown(self):
        """关闭语音合成服务"""
        try:
            print("🔄 正在关闭语音合成服务...")
            
            # 清空队列
            self.clear_queue()
            
            # 停止播报线程
            self.stop_speaking_service()
            
            # 停止引擎
            if self.engine:
                try:
                    self.engine.stop()
                except:
                    pass
            
            print("✅ 语音合成服务已关闭")
            
        except Exception as e:
            print(f"⚠ 关闭语音合成服务时出错: {e}")
