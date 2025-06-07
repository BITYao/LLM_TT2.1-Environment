"""
LLM API客户端
"""
import requests
import json
from config import API_BASE_URL, API_KEY, MODEL_NAME, SYSTEM_PROMPT, VISION_DESCRIPTION_PROMPT

class LLMClient:
    def __init__(self):
        self.api_url = f"{API_BASE_URL}/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
    
    def parse_voice_command(self, voice_text):
        """
        使用LLM解析语音命令，支持复合指令
        """
        try:
            payload = {
                "model": MODEL_NAME,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": voice_text}
                ],
                "temperature": 0.1,
                "max_tokens": 200
            }
            
            response = requests.post(
                self.api_url, 
                headers=self.headers, 
                json=payload, 
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content'].strip()
                
                # 解析复合指令（以分号分隔）
                commands = [cmd.strip() for cmd in content.split(';') if cmd.strip()]
                print(f"🤖 LLM解析结果: {commands}")
                return commands
            else:
                print(f"❌ LLM API错误: {response.status_code}")
                return ["unknown"]
                
        except Exception as e:
            print(f"❌ LLM解析错误: {e}")
            return ["unknown"]
    
    def generate_vision_description(self, recognition_result):
        """
        根据图像识别结果生成自然语言描述
        """
        try:
            # 将识别结果格式化为输入文本
            input_text = str(recognition_result)
            
            payload = {
                "model": MODEL_NAME,
                "messages": [
                    {"role": "system", "content": VISION_DESCRIPTION_PROMPT},
                    {"role": "user", "content": input_text}
                ],
                "temperature": 0.3,
                "max_tokens": 100
            }
            
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=8
            )
            
            if response.status_code == 200:
                result = response.json()
                description = result['choices'][0]['message']['content'].strip()
                print(f"🤖 生成描述: {description}")
                return description
            else:
                print(f"❌ 描述生成API错误: {response.status_code}")
                return "图像识别完成，但描述生成失败"
                
        except Exception as e:
            print(f"❌ 描述生成错误: {e}")
            return "看到了一些物体，但无法生成详细描述"
    
    def test_connection(self):
        """
        测试API连接
        """
        try:
            test_payload = {
                "model": MODEL_NAME,
                "messages": [
                    {"role": "user", "content": "Hello"}
                ],
                "max_tokens": 10
            }
            
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=test_payload,
                timeout=5
            )
            
            return response.status_code == 200
            
        except Exception as e:
            print(f"API连接测试失败: {e}")
            return False
    
    def test_vision_description(self):
        """
        测试图像描述生成功能
        """
        try:
            test_data = [{"name": "person", "confidence": 95.2}, {"name": "building", "confidence": 88.5}]
            description = self.generate_vision_description(test_data)
            return description is not None and len(description) > 0
            
        except Exception as e:
            print(f"视觉描述测试失败: {e}")
            return False