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
        """识别图片文件中的物体和场景（增强版预处理）"""
        try:
            # 检查token
            if not self._check_token():
                return None
            
            # 检查文件是否存在
            if not os.path.exists(image_path):
                print(f"❌ 图片文件不存在: {image_path}")
                return None
            
            print(f"🔍 正在识别图片: {image_path}")
            
            # 🔧 增强：添加图片质量预检查
            if not self._validate_image_quality(image_path):
                print("⚠ 图片质量不佳，但仍尝试识别")
            
            # 🔧 优化：添加图片格式验证和颜色空间处理
            try:
                import cv2
                # 读取图片并验证格式
                img = cv2.imread(image_path)
                if img is None:
                    print(f"❌ 无法读取图片文件: {image_path}")
                    return None
                
                # 🔧 新增：检查图片是否过暗
                if self._is_image_too_dark(img):
                    print("⚠ 检测到较暗的图片，可能影响识别效果")
                
                # 确保图片是BGR格式（OpenCV默认），然后保存为临时文件用于API
                temp_path = image_path + "_temp.jpg"
                
                # 🔧 新增：图片预处理增强（可选）
                processed_img = self._enhance_image_for_recognition(img)
                cv2.imwrite(temp_path, processed_img)
                
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
            
            # 🔧 新增：检查图片数据大小
            if len(image_data) == 0:
                print("❌ 图片文件为空")
                return None
            
            if len(image_data) > 4 * 1024 * 1024:  # 4MB限制
                print("⚠ 图片文件过大，可能影响识别速度")
            
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
            
            # 🔧 新增：增加超时时间以应对复杂图像
            print("🤖 正在调用百度API进行图像识别...")
            
            # 发送请求
            response = requests.post(
                request_url,
                data=params,
                headers=headers,
                timeout=20  # 增加超时时间到20秒
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if 'result' in result:
                    result_num = result.get('result_num', 0)
                    print(f"✅ 图像识别成功，识别到 {result_num} 个物体/场景")
                    
                    if result_num == 0:
                        print("⚠ 未识别到任何明确物体，可能图片质量较差")
                    
                    return self._format_recognition_result(result)
                else:
                    error_msg = result.get('error_msg', '未知错误')
                    error_code = result.get('error_code', 'UNKNOWN')
                    print(f"❌ 图像识别失败: {error_msg} (代码: {error_code})")
                    return None
            else:
                print(f"❌ 图像识别请求失败: HTTP {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"   错误详情: {error_detail}")
                except:
                    pass
                return None
                
        except Exception as e:
            print(f"❌ 图像识别异常: {e}")
            import traceback
            print(f"   详细错误: {traceback.format_exc()}")
            return None
    
    def _validate_image_quality(self, image_path):
        """验证图片基本质量"""
        try:
            import cv2
            img = cv2.imread(image_path)
            if img is None:
                return False
            
            # 检查图片尺寸
            height, width = img.shape[:2]
            if height < 100 or width < 100:
                print(f"⚠ 图片尺寸过小: {width}x{height}")
                return False
            
            # 检查图片是否过暗
            if self._is_image_too_dark(img):
                return False
            
            return True
            
        except Exception as e:
            print(f"⚠ 图片质量检查失败: {e}")
            return True  # 检查失败时假设质量良好
    
    def _is_image_too_dark(self, img, dark_threshold=20):
        """检查图片是否过暗"""
        try:
            # 转换为灰度图
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            mean_brightness = cv2.mean(gray)[0]
            
            if mean_brightness < dark_threshold:
                print(f"⚠ 图片较暗，平均亮度: {mean_brightness:.1f}")
                return True
            
            return False
            
        except Exception as e:
            return False
    
    def _enhance_image_for_recognition(self, img):
        """增强图片用于识别（可选的预处理）"""
        try:
            # 基本的对比度和亮度调整
            # 这里可以根据需要添加更多的图片增强算法
            
            # 检查图片是否过暗，如果过暗则进行亮度调整
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            mean_brightness = cv2.mean(gray)[0]
            
            if mean_brightness < 30:  # 如果图片很暗
                print("🔧 对暗图片进行亮度增强")
                # 简单的亮度提升
                enhanced = cv2.convertScaleAbs(img, alpha=1.2, beta=20)
                return enhanced
            
            return img  # 图片质量良好，不需要增强
            
        except Exception as e:
            print(f"⚠ 图片增强失败: {e}")
            return img  # 增强失败时返回原图

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
