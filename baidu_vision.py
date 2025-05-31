"""
百度图像识别客户端 - 通用物体和场景识别
"""
import requests
import json
import base64
import time
import os
from config import BAIDU_VISION_API_KEY, BAIDU_VISION_SECRET_KEY

class BaiduVision:
    def __init__(self):
        self.api_key = BAIDU_VISION_API_KEY
        self.secret_key = BAIDU_VISION_SECRET_KEY
        self.vision_url = "https://aip.baidubce.com/rest/2.0/image-classify/v2/advanced_general"
        self.access_token = None
        self.token_expires = 0
        
        # 获取access_token
        self._get_access_token()
    
    def _get_access_token(self):
        """获取百度图像识别API access_token"""
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
                    print("✓ 百度图像识别token获取成功")
                    return True
                else:
                    print(f"❌ 图像识别token获取失败: {result}")
                    return False
            else:
                print(f"❌ 图像识别token请求失败: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 获取百度图像识别token异常: {e}")
            return False
    
    def _check_token(self):
        """检查token是否过期，过期则重新获取"""
        if not self.access_token or time.time() > self.token_expires:
            print("🔄 图像识别token已过期，重新获取...")
            return self._get_access_token()
        return True
    
    def recognize_image_file(self, image_path, baike_num=0):
        """识别图片文件中的物体和场景"""
        try:
            # 检查token
            if not self._check_token():
                return None
            
            # 检查文件是否存在
            if not os.path.exists(image_path):
                print(f"❌ 图片文件不存在: {image_path}")
                return None
            
            print(f"🔍 正在识别图片: {image_path}")
            
            # 🔧 优化：添加图片格式验证和颜色空间处理
            try:
                import cv2
                # 读取图片并验证格式
                img = cv2.imread(image_path)
                if img is None:
                    print(f"❌ 无法读取图片文件: {image_path}")
                    return None
                
                # 确保图片是BGR格式（OpenCV默认），然后保存为临时文件用于API
                temp_path = image_path + "_temp.jpg"
                cv2.imwrite(temp_path, img)
                
                # 读取处理后的图片数据
                with open(temp_path, 'rb') as f:
                    image_data = f.read()
                
                # 清理临时文件
                try:
                    os.remove(temp_path)
                except:
                    pass
                    
            except ImportError:
                # 如果没有cv2，直接读取原文件
                with open(image_path, 'rb') as f:
                    image_data = f.read()
            except Exception as e:
                print(f"⚠ 图片格式处理出错，使用原始文件: {e}")
                with open(image_path, 'rb') as f:
                    image_data = f.read()
            
            # Base64编码
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # 构建请求参数
            params = {
                'image': image_base64
            }
            
            if baike_num > 0:
                params['baike_num'] = min(baike_num, 5)  # 最多返回5个百科结果
            
            # 构建请求URL
            request_url = f"{self.vision_url}?access_token={self.access_token}"
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            # 发送请求
            response = requests.post(
                request_url,
                data=params,
                headers=headers,
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if 'result' in result:
                    print(f"✅ 图像识别成功，识别到 {result.get('result_num', 0)} 个物体/场景")
                    return self._format_recognition_result(result)
                else:
                    error_msg = result.get('error_msg', '未知错误')
                    print(f"❌ 图像识别失败: {error_msg}")
                    return None
            else:
                print(f"❌ 图像识别请求失败: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ 图像识别异常: {e}")
            return None
    
    def _format_recognition_result(self, raw_result):
        """格式化识别结果"""
        try:
            formatted_result = {
                'log_id': raw_result.get('log_id'),
                'result_num': raw_result.get('result_num', 0),
                'objects': []
            }
            
            for item in raw_result.get('result', []):
                obj_info = {
                    'name': item.get('keyword', '未知'),
                    'confidence': round(item.get('score', 0) * 100, 2),  # 转换为百分比
                    'category': item.get('root', '未分类'),
                    'baike_info': None
                }
                
                # 处理百科信息
                if 'baike_info' in item:
                    baike = item['baike_info']
                    obj_info['baike_info'] = {
                        'url': baike.get('baike_url', ''),
                        'image_url': baike.get('image_url', ''),
                        'description': baike.get('description', '')[:200] + '...' if len(baike.get('description', '')) > 200 else baike.get('description', '')
                    }
                
                formatted_result['objects'].append(obj_info)
            
            return formatted_result
            
        except Exception as e:
            print(f"❌ 格式化识别结果失败: {e}")
            return None
    
    def get_top_objects(self, recognition_result, top_n=3):
        """获取置信度最高的前N个识别结果"""
        if not recognition_result or 'objects' not in recognition_result:
            return []
        
        objects = recognition_result['objects']
        # 按置信度排序
        sorted_objects = sorted(objects, key=lambda x: x['confidence'], reverse=True)
        
        return sorted_objects[:top_n]
    
    def format_recognition_summary(self, recognition_result):
        """格式化识别结果摘要"""
        if not recognition_result:
            return "未识别到任何物体"
        
        top_objects = self.get_top_objects(recognition_result, 3)
        
        if not top_objects:
            return "未识别到任何物体"
        
        summary_parts = []
        for obj in top_objects:
            summary_parts.append(f"{obj['name']}({obj['confidence']:.1f}%)")
        
        return f"识别到: {', '.join(summary_parts)}"
    
    def test_recognition(self, test_image_path=None):
        """测试图像识别功能"""
        try:
            print("🧪 测试百度图像识别...")
            
            if test_image_path and os.path.exists(test_image_path):
                result = self.recognize_image_file(test_image_path)
                if result:
                    summary = self.format_recognition_summary(result)
                    print(f"✅ 百度图像识别测试成功: {summary}")
                    return True
                else:
                    print("❌ 百度图像识别测试失败")
                    return False
            else:
                print("⚠ 需要提供测试图片路径")
                return False
                
        except Exception as e:
            print(f"❌ 图像识别测试异常: {e}")
            return False
