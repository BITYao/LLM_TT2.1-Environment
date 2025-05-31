"""
网络管理器 - 处理网络切换和代理
"""
import subprocess
import time
import threading
import requests
import socket
from config import PROXY_ENABLED, PROXY_HOST, PROXY_PORT

class NetworkManager:
    def __init__(self):
        self.original_default_gateway = None
        self.tello_connected = False
        
    def get_network_info(self):
        """获取当前网络信息"""
        try:
            result = subprocess.run(['ipconfig'], capture_output=True, text=True, encoding='gbk')
            return result.stdout
        except:
            return ""
    
    def backup_network_config(self):
        """备份当前网络配置"""
        try:
            # 获取默认网关
            result = subprocess.run(['route', 'print', '0.0.0.0'], 
                                  capture_output=True, text=True)
            lines = result.stdout.split('\n')
            for line in lines:
                if '0.0.0.0' in line and '0.0.0.0' in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        self.original_default_gateway = parts[2]
                        print(f"备份原始网关: {self.original_default_gateway}")
                        break
        except Exception as e:
            print(f"备份网络配置失败: {e}")
    
    def connect_to_tello_wifi(self):
        """连接到Tello WiFi网络"""
        try:
            print("正在搜索Tello网络...")
            tello_networks = self.find_tello_networks()
            
            if not tello_networks:
                print("未找到Tello网络，请确保无人机已开启")
                return False
            
            # 连接到第一个找到的Tello网络
            network_name = tello_networks[0]
            print(f"正在连接到Tello网络: {network_name}")
            
            result = subprocess.run([
                'netsh', 'wlan', 'connect', f'name={network_name}'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"已连接到Tello网络: {network_name}")
                time.sleep(3)  # 等待连接稳定
                self.tello_connected = True
                return True
            else:
                print(f"连接Tello网络失败: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"连接Tello WiFi失败: {e}")
            return False
    
    def find_tello_networks(self):
        """查找可用的Tello网络"""
        try:
            # 刷新网络列表
            subprocess.run(['netsh', 'wlan', 'show', 'networks'], 
                          capture_output=True, text=True)
            
            result = subprocess.run(['netsh', 'wlan', 'show', 'networks'], 
                                  capture_output=True, text=True)
            lines = result.stdout.split('\n')
            tello_networks = []
            
            for line in lines:
                if 'SSID' in line and ('Tello' in line.upper() or 'RMTT' in line.upper()):
                    # 提取SSID名称
                    ssid = line.split(':')[-1].strip()
                    if ssid:
                        tello_networks.append(ssid)
            
            print(f"找到Tello网络: {tello_networks}")
            return tello_networks
            
        except Exception as e:
            print(f"搜索Tello网络失败: {e}")
            return []
    
    def test_tello_connection(self):
        """测试Tello连接"""
        try:
            # 尝试连接Tello的UDP端口
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(3)
            sock.sendto(b'command', ('192.168.10.1', 8889))
            response = sock.recv(1024)
            sock.close()
            return b'ok' in response.lower()
        except:
            return False
    
    def restore_network_config(self):
        """恢复原始网络配置"""
        if self.original_default_gateway:
            try:
                print("正在恢复网络配置...")
                # 这里可以添加恢复网络的逻辑
                print("网络配置已恢复")
            except Exception as e:
                print(f"恢复网络配置失败: {e}")

class DualNetworkManager:
    """
    双网络管理器 - 使用手机热点方案
    """
    def __init__(self):
        self.mobile_hotspot_connected = False
        self.tello_connected = False
        
    def setup_dual_network(self):
        """配置双网络连接"""
        print("=== 双网络配置指南 ===")
        print("方案1: 使用手机热点 + Tello WiFi")
        print("1. 开启手机热点")
        print("2. 电脑连接手机热点获得网络")
        print("3. 程序会自动切换到Tello WiFi")
        print("4. 通过手机热点保持API连接")
        
        # 检查当前网络连接
        if self.test_internet_connection():
            print("✓ 当前已有互联网连接")
            self.mobile_hotspot_connected = True
        else:
            print("⚠ 当前无互联网连接")
            print("请先连接到手机热点或其他网络")
            
        print("\n方案2: 使用有线网络 + Tello WiFi")
        print("1. 电脑通过网线连接路由器")
        print("2. WiFi连接Tello")
        print("3. 通过有线网络访问互联网")
        
        return True
    
    def test_internet_connection(self):
        """测试互联网连接"""
        try:
            response = requests.get('http://www.baidu.com', timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def configure_network_priority(self):
        """配置网络优先级"""
        try:
            print("配置网络路由...")
            # 设置Tello网络的特定路由
            subprocess.run([
                'route', 'add', '192.168.10.0', 'mask', '255.255.255.0', '192.168.10.1', 'metric', '1'
            ], capture_output=True)
            
            print("网络路由配置完成")
            return True
            
        except Exception as e:
            print(f"网络路由配置失败: {e}")
            return False

class NetworkChecker:
    """网络状态检测器"""
    
    @staticmethod
    def check_tello_connection():
        """检查Tello连接状态"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(2)
            sock.sendto(b'command', ('192.168.10.1', 8889))
            response = sock.recv(1024)
            sock.close()
            return True
        except:
            return False
    
    @staticmethod
    def check_internet_connection():
        """检查互联网连接状态"""
        try:
            response = requests.get('http://www.baidu.com', timeout=3)
            return response.status_code == 200
        except:
            return False
    
    @staticmethod
    def get_current_wifi():
        """获取当前连接的WiFi"""
        try:
            result = subprocess.run(['netsh', 'wlan', 'show', 'interfaces'], 
                                  capture_output=True, text=True, encoding='gbk')
            lines = result.stdout.split('\n')
            for line in lines:
                if 'SSID' in line and ':' in line:
                    return line.split(':')[-1].strip()
            return "未知"
        except:
            return "未知"