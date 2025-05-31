"""
百度语音识别客户端
"""
import requests
import json
import base64
import pyaudio
import wave
import tempfile
import time
from config import BAIDU_API_KEY, BAIDU_SECRET_KEY, BAIDU_ASR_URL, AUDIO_SAMPLE_RATE, AUDIO_CHANNELS

class BaiduASR:
    def __init__(self):
        self.api_key = BAIDU_API_KEY
        self.secret_key = BAIDU_SECRET_KEY
        self.asr_url = BAIDU_ASR_URL
        self.access_token = None
        self.token_expires = 0
        
        # 获取access_token
        self._get_access_token()
    
    def _get_access_token(self):
        """获取百度API access_token"""
        try:
            # 百度token获取URL
            token_url = "https://aip.baidubce.com/oauth/2.0/token"
            
            params = {
                'grant_type': 'client_credentials',
                'client_id': self.api_key,
                'client_secret': self.secret_key
            }
            
            response = requests.post(token_url, params=params, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if 'access_token' in result:
                    self.access_token = result['access_token']
                    self.token_expires = time.time() + result.get('expires_in', 3600) - 300  # 提前5分钟过期
                    print("✓ 百度语音识别token获取成功")
                    return True
                else:
                    print(f"❌ token获取失败: {result}")
                    return False
            else:
                print(f"❌ token请求失败: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 获取百度token异常: {e}")
            return False
    
    def _check_token(self):
        """检查token是否过期，过期则重新获取"""
        if not self.access_token or time.time() > self.token_expires:
            print("🔄 token已过期，重新获取...")
            return self._get_access_token()
        return True
    
    def record_audio(self, duration=5):
        """录制音频"""
        try:
            print(f"🔴 开始录音（{duration}秒）...")
            
            # 初始化PyAudio
            audio = pyaudio.PyAudio()
            
            # 录音参数
            format = pyaudio.paInt16
            channels = AUDIO_CHANNELS
            rate = AUDIO_SAMPLE_RATE
            chunk = 1024
            
            # 开始录音
            stream = audio.open(
                format=format,
                channels=channels,
                rate=rate,
                input=True,
                frames_per_buffer=chunk
            )
            
            frames = []
            for i in range(0, int(rate / chunk * duration)):
                data = stream.read(chunk)
                frames.append(data)
            
            # 停止录音
            stream.stop_stream()
            stream.close()
            audio.terminate()
            
            print("🔴 录音完成")
            
            # 保存为临时WAV文件
            temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            with wave.open(temp_file.name, 'wb') as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(audio.get_sample_size(format))
                wf.setframerate(rate)
                wf.writeframes(b''.join(frames))
            
            return temp_file.name
            
        except Exception as e:
            print(f"❌ 录音失败: {e}")
            return None
    
    def recognize_audio_file(self, audio_file_path):
        """识别音频文件"""
        try:
            # 检查token
            if not self._check_token():
                return None
            
            print("🔄 正在识别语音...")
            
            # 读取音频文件
            with open(audio_file_path, 'rb') as f:
                audio_data = f.read()
            
            # Base64编码
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            # 构建请求参数
            params = {
                'format': 'wav',
                'rate': AUDIO_SAMPLE_RATE,
                'channel': AUDIO_CHANNELS,
                'cuid': 'TT_VoiceControl',
                'token': self.access_token,
                'dev_pid': 1537,  # 普通话识别
                'speech': audio_base64,
                'len': len(audio_data)
            }
            
            # 发送请求
            headers = {
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                self.asr_url,
                headers=headers,
                json=params,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('err_no') == 0:
                    # 识别成功
                    if 'result' in result and len(result['result']) > 0:
                        recognized_text = result['result'][0]
                        print(f"✅ 百度语音识别结果: '{recognized_text}'")
                        return recognized_text
                    else:
                        print("❌ 识别结果为空")
                        return None
                else:
                    print(f"❌ 识别失败: {result.get('err_msg')}")
                    return None
            else:
                print(f"❌ 请求失败: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ 语音识别异常: {e}")
            return None
        finally:
            # 清理临时文件
            try:
                import os
                if audio_file_path and os.path.exists(audio_file_path):
                    os.unlink(audio_file_path)
            except:
                pass
    
    def test_recognition(self):
        """测试语音识别"""
        try:
            print("🧪 测试百度语音识别...")
            
            # 录制测试音频
            audio_file = self.record_audio(3)
            if not audio_file:
                return False
            
            # 识别测试音频
            result = self.recognize_audio_file(audio_file)
            
            if result:
                print(f"✅ 百度语音识别测试成功: {result}")
                return True
            else:
                print("❌ 百度语音识别测试失败")
                return False
                
        except Exception as e:
            print(f"❌ 测试异常: {e}")
            return False
