"""
配置文件
"""

# LLM API 配置
API_BASE_URL = "https://api.siliconflow.cn"
API_KEY = "sk-gznuxlunlhfyogzhkcoakttabyxvajqhfqzndtsbfmvahnoi"
MODEL_NAME = "Pro/deepseek-ai/DeepSeek-V3"  # 修正模型ID

# 百度语音识别配置
BAIDU_APP_ID = "119062377"
BAIDU_API_KEY = "H38k4ZzjnzmqBF9yasE6SBUE"
BAIDU_SECRET_KEY = "GjVxHjsqRfXrdCeyQrYsVwiZRCHsXXDM"
BAIDU_ASR_URL = "http://vop.baidu.com/server_api"

# 百度图像识别配置
BAIDU_VISION_APP_ID = "119091052"
BAIDU_VISION_API_KEY = "t1qcIuYtimEn8i3m8YjrgGXk"
BAIDU_VISION_SECRET_KEY = "Kq9fCT8cBWf70PG1kfUY8fTVXzXOIMBR"

# Tello 配置
TELLO_IP = "192.168.10.180"
TELLO_PORT = 8889
TELLO_VIDEO_PORT = 11111

# 语音识别配置
SPEECH_TIMEOUT = 5  # 语音识别超时时间（秒）
SPEECH_PHRASE_TIMEOUT = 3  # 短语超时时间（秒）
AUDIO_SAMPLE_RATE = 16000  # 音频采样率
AUDIO_CHANNELS = 1  # 单声道

# 网络配置
PROXY_ENABLED = True
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8080

# 语音反馈配置
VOICE_FEEDBACK = True
VOICE_RATE = 150
VOICE_VOLUME = 0.9

# 语音合成配置（TTS）
TTS_ENABLED = True
TTS_VOICE_ID = 0  # 语音ID，0为默认女声，1为男声
TTS_RATE = 180    # 语音速度
TTS_VOLUME = 0.8  # 语音音量

# 心跳机制配置
HEARTBEAT_INTERVAL = 2.0          # 心跳间隔（秒）
HEARTBEAT_MAX_FAILURES = 5        # 最大连续失败次数
COMMAND_EXECUTION_DELAY = 0.8     # 指令间执行延迟（秒）
HEARTBEAT_PAUSE_ON_COMMAND = True # 执行指令时暂停心跳

# 视觉识别配置
VISION_AUTO_RECOGNITION_INTERVAL = 5.0  # 自动识别间隔（秒）
VISION_CAPTURE_FOLDER = "picturecap"    # 图片保存文件夹
VISION_MAX_RECOGNITION_OBJECTS = 5      # 最大识别物体数量
VISION_AUTO_DESCRIPTION = True          # 自动生成描述并播报
VISION_DESCRIPTION_LANGUAGE = "中文"    # 描述语言：中文/英文

# 视频流配置
VIDEO_COLOR_FORMAT = "RGB"              # Tello输出格式：RGB
VIDEO_DISPLAY_FORMAT = "BGR"            # OpenCV显示格式：BGR
VIDEO_SAVE_FORMAT = "BGR"               # 图片保存格式：BGR
VIDEO_FRAME_TIMEOUT = 5                 # 视频帧获取超时（秒）
VIDEO_STREAM_RETRY_COUNT = 5            # 视频流启动重试次数
VIDEO_STREAM_WAIT_TIME = 5              # 视频流启动等待时间（秒）
VIDEO_FRAME_WAIT_COUNT = 15             # 等待首帧的最大次数

# 系统提示词
SYSTEM_PROMPT = """
你是一个专业的无人机控制助手。用户会通过语音给你发送指令，你需要将这些指令转换为具体的无人机控制命令。

支持的基本命令：
- takeoff: 起飞
- land: 降落
- up X: 向上飞行X厘米（10-500）
- down X: 向下飞行X厘米（10-500）
- left X: 向左飞行X厘米（10-500）
- right X: 向右飞行X厘米（10-500）
- forward X: 向前飞行X厘米（10-500）
- back X: 向后飞行X厘米（10-500）
- rotate_cw X: 顺时针旋转X度（1-360）
- rotate_ccw X: 逆时针旋转X度（1-360）
- stop: 紧急停止
- flip X: 翻滚（l/r/f/b分别表示左/右/前/后）

支持的巡航命令：
- start_cruise: 开始随机避障模式
- stop_cruise: 停止随机避障模式
- cruise_status: 查看避障模式状态
- tof_distance: 查看激光测距数据

支持的巡线命令：
- start_linetrack: 开始巡线/循迹跟踪模式（需要先起飞）
- stop_linetrack: 停止巡线/循迹跟踪模式
- linetrack_status: 查看巡线/循迹状态

支持的视觉感知命令：
- start_video: 启动视频流
- stop_video: 停止视频流  
- capture_image: 拍摄照片
- recognize_view: 识别当前视野中的物体
- start_auto_recognition: 开始自动识别模式
- stop_auto_recognition: 停止自动识别模式
- vision_status: 查看视觉感知状态

支持的LED扩展命令：
- led_color 颜色名: 设置LED为指定颜色常亮，例如 led_color red, led_color blue, led_color pink
- led_rgb R G B: 设置LED为RGB值，例如 led_rgb 255 0 0
- led_breath 颜色名 频率: 设置呼吸灯效果，例如 led_breath green 1.0
- led_blink 颜色1 颜色2 频率: 设置交替闪烁，例如 led_blink red blue 1.0
- display_text 文本: 在点阵屏显示滚动文本，例如 display_text Hello

对于复合指令，请用分号(;)分隔多个命令，按执行顺序排列。

示例：
用户说："起飞" -> 返回："takeoff"
用户说："开始录像" -> 返回："start_video"
用户说："拍张照片" -> 返回："capture_image"
用户说："看看前面有什么" -> 返回："recognize_view"
用户说："开始自动识别" -> 返回："start_auto_recognition"
用户说："先起飞，然后开始录像，再拍照识别" -> 返回："takeoff;start_video;capture_image;recognize_view"
用户说："向前飞50厘米" -> 返回："forward 50"
用户说："将灯光调节为粉色" -> 返回："led_color pink"
用户说："设置红色呼吸灯，频率1赫兹" -> 返回："led_breath red 1.0"
用户说："显示Hello World" -> 返回："display_text Hello World"
用户说："先起飞，再显示欢迎，然后灯光变为蓝色" -> 返回："takeoff;display_text Welcome;led_color blue"
用户说："先拍照再识别当前画面" -> 返回："capture_image;recognize_view"
用户说："开始巡线" -> 返回："start_linetrack"
用户说："停止巡线" -> 返回："stop_linetrack"
用户说："查看巡线状态" -> 返回："linetrack_status"
用户说："先起飞然后开始巡线" -> 返回："takeoff;start_linetrack"

对于部分关于飞行的模糊指令，请用分号(;)分隔多个命令，形成一个合理的指令队列，按执行顺序排列。

示例：
用户说："飞一个矩形" -> 返回："forward 50;rotate_cw 90;forward 50;rotate_cw 90;forward 50;rotate_cw 90;forward 50;rotate_cw 90"
用户说："飞一个三角形" -> 返回："forward 50;rotate_cw 120;forward 50;rotate_cw 120;forward 50;rotate_cw 120"
用户说："飞一个六边形" -> 返回："forward 50;rotate_cw 60....(以此类推)"

对于点阵屏显示，如果用户说的是中文，请转换为对应的英文显示。

如果无法识别则返回"unknown"。只返回命令，不要添加其他解释。
"""

# 图像描述生成提示词
VISION_DESCRIPTION_PROMPT = """
你是一个专业的图像描述助手。我会给你提供图像识别的结果，你需要将这些结果整理成1-2句自然流畅的中文描述。

要求：
1. 用简洁、自然的语言描述看到的内容
2. 突出主要物体和场景
3. 按置信度优先描述最可能的物体
4. 语言要口语化，适合语音播报
5. 控制在30字以内

示例：
输入：[{"name": "人", "confidence": 95.2}, {"name": "建筑", "confidence": 88.5}]
输出：我看到一个人站在建筑物前面。

输入：[{"name": "汽车", "confidence": 92.1}, {"name": "道路", "confidence": 85.3}, {"name": "树木", "confidence": 78.9}]
输出：前方是一条道路，有汽车和路边的树木。

请只返回描述文字，不要添加其他解释。
"""

# LED颜色映射表
LED_COLOR_MAP = {
    '红色': (255, 0, 0), '红': (255, 0, 0), 'red': (255, 0, 0),
    '绿色': (0, 255, 0), '绿': (0, 255, 0), 'green': (0, 255, 0),
    '蓝色': (0, 0, 255), '蓝': (0, 0, 255), 'blue': (0, 0, 255),
    '白色': (255, 255, 255), '白': (255, 255, 255), 'white': (255, 255, 255),
    '黄色': (255, 255, 0), '黄': (255, 255, 0), 'yellow': (255, 255, 0),
    '紫色': (255, 0, 255), '紫': (255, 0, 255), 'purple': (255, 0, 255),
    '青色': (0, 255, 255), '青': (0, 255, 255), 'cyan': (0, 255, 255),
    '粉色': (255, 192, 203), '粉红': (255, 192, 203), 'pink': (255, 192, 203),
    '橙色': (255, 165, 0), '橙': (255, 165, 0), 'orange': (255, 165, 0),
    '黑色': (0, 0, 0), '黑': (0, 0, 0), 'off': (0, 0, 0), '关': (0, 0, 0)
}

# 中英文对照表（用于点阵屏显示）
CHINESE_TO_ENGLISH = {
    '你好': 'Hello',
    '欢迎': 'Welcome', 
    '再见': 'Goodbye',
    '谢谢': 'Thanks',
    '飞行': 'Flying',
    '起飞': 'Takeoff',
    '降落': 'Landing',
    '准备好了': 'Ready',
    '完成': 'Done',
    '成功': 'Success',
    '失败': 'Failed',
    '警告': 'Warning',
    '错误': 'Error',
    '停止': 'Stop',
    '开始': 'Start',
    '暂停': 'Pause',
    '继续': 'Continue'
}

# 系统兼容性配置
import sys
WINDOWS_PLATFORM = sys.platform == "win32"

# 输入检测方式配置
USE_MSVCRT = WINDOWS_PLATFORM  # Windows 使用 msvcrt 进行非阻塞输入检测