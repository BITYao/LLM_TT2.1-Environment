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
                "stream": False,
                "max_tokens": 200,  # 增加token数量以支持复合指令
                "temperature": 0.1,
                "top_p": 0.7,
                "stop": None,
                "response_format": {"type": "text"}
            }
            
            print(f"发送到LLM: {voice_text}")
            
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=15  # 增加超时时间
            )
            
            print(f"API响应状态: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"完整API响应: {result}")
                
                if 'choices' in result and len(result['choices']) > 0:
                    command_text = result['choices'][0]['message']['content'].strip()
                    print(f"LLM解析结果: {voice_text} -> {command_text}")
                    
                    # 解析复合指令
                    if ';' in command_text:
                        commands = [cmd.strip() for cmd in command_text.split(';') if cmd.strip()]
                        print(f"检测到复合指令，共{len(commands)}条: {commands}")
                        return commands  # 返回命令列表
                    elif ',' in command_text:
                        # 支持逗号分隔的指令
                        commands = [cmd.strip() for cmd in command_text.split(',') if cmd.strip()]
                        print(f"检测到逗号分隔指令，共{len(commands)}条: {commands}")
                        return commands  # 返回命令列表
                    else:
                        return [command_text] if command_text != "unknown" else ["unknown"]
                else:
                    print("API响应格式错误，缺少choices字段")
                    return ["unknown"]
            else:
                print(f"API请求失败: {response.status_code}")
                print(f"错误响应: {response.text}")
                return ["unknown"]
                
        except Exception as e:
            print(f"LLM解析错误: {e}")
            return ["unknown"]
    
    def generate_vision_description(self, recognition_result):
        """
        根据图像识别结果生成自然语言描述
        """
        try:
            if not recognition_result or 'objects' not in recognition_result:
                return "未识别到任何物体"
            
            # 提取前3个置信度最高的物体
            objects = recognition_result['objects'][:3]
            objects_info = []
            
            for obj in objects:
                objects_info.append({
                    "name": obj['name'],
                    "confidence": obj['confidence']
                })
            
            # 构建提示词
            objects_text = str(objects_info)
            
            payload = {
                "model": MODEL_NAME,
                "messages": [
                    {"role": "system", "content": VISION_DESCRIPTION_PROMPT},
                    {"role": "user", "content": f"请描述这个识别结果：{objects_text}"}
                ],
                "stream": False,
                "max_tokens": 100,
                "temperature": 0.3,
                "top_p": 0.8,
                "stop": None,
                "response_format": {"type": "text"}
            }
            
            print(f"🤖 请求LLM生成图像描述...")
            print(f"🔍 识别对象: {objects_info}")
            
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if 'choices' in result and len(result['choices']) > 0:
                    description = result['choices'][0]['message']['content'].strip()
                    print(f"✅ LLM生成描述: {description}")
                    return description
                else:
                    print("❌ LLM响应格式错误")
                    return "识别结果处理失败"
            else:
                print(f"❌ LLM请求失败: {response.status_code}")
                print(f"错误详情: {response.text}")
                return "描述生成失败"
                
        except Exception as e:
            print(f"❌ 生成图像描述异常: {e}")
            import traceback
            print(f"详细错误: {traceback.format_exc()}")
            return "描述生成出错"
    
    def test_connection(self):
        """
        测试API连接
        """
        try:
            print("正在测试LLM API连接...")
            # 使用复合指令测试
            test_result = self.parse_voice_command("先起飞再向前飞50厘米")
            
            # 如果能正确解析复合指令，说明连接正常
            if isinstance(test_result, list) and len(test_result) > 1:
                print("✓ LLM API连接测试成功，支持复合指令")
                return True
            elif test_result != ["unknown"]:
                print("✓ LLM API连接正常")
                return True
            else:
                print("✗ LLM API连接测试失败")
                return False
                
        except Exception as e:
            print(f"LLM API连接测试异常: {e}")
            return False
    
    def test_vision_description(self):
        """
        测试图像描述生成功能
        """
        try:
            print("🧪 测试图像描述生成...")
            
            # 模拟测试数据
            test_recognition = {
                'objects': [
                    {'name': '显示器屏幕', 'confidence': 99.8},
                    {'name': '模糊图片', 'confidence': 62.8},
                    {'name': '文字图片', 'confidence': 39.9}
                ]
            }
            
            description = self.generate_vision_description(test_recognition)
            
            if description and description not in ["描述生成失败", "描述生成出错"]:
                print(f"✅ 图像描述生成测试成功: {description}")
                return True
            else:
                print(f"❌ 图像描述生成测试失败: {description}")
                return False
                
        except Exception as e:
            print(f"❌ 图像描述生成测试异常: {e}")
            return False