# Tello编队语音控制系统 v2.4 / Tello Formation Voice Control System v2.4

🚁 基于百度语音识别和LLM的智能无人机控制系统  
🚁 Intelligent drone control system based on Baidu Speech Recognition and LLM

## 📋 项目简介 / Project Overview

### 中文 / Chinese
这是一个功能丰富的Tello无人机语音控制系统，支持复合指令、视觉感知、LED控制和巡航模式。系统使用百度语音识别进行语音输入，通过LLM进行智能指令解析，并提供图形界面和控制台两种操作模式。

### 英文 / English
This is a feature-rich Tello drone voice control system that supports compound commands, visual perception, LED control, and cruise mode. The system uses Baidu Speech Recognition for voice input, intelligent command parsing through LLM, and provides both GUI and console operation modes.

## 🌟 主要功能 / Key Features

### 中文 / Chinese
- **🎤 智能语音控制**: 基于百度语音识别，支持自然语言指令
- **🤖 复合指令支持**: 通过LLM解析复杂的多步骤指令
- **👁️ 视觉感知**: 实时摄像头画面识别和智能描述
- **🎨 LED控制**: 支持颜色设置、呼吸灯、闪烁等效果
- **📺 点阵屏显示**: 支持文本滚动显示（中英文自动转换）
- **🛰️ 智能巡航**: 自动避障的随机巡航模式
- **🖥️ 双模式界面**: 图形界面和控制台模式可选
- **📋 指令队列**: 智能指令排队执行系统
- **💓 心跳机制**: 飞行状态保持和安全监控

### 英文 / English
- **🎤 Intelligent Voice Control**: Based on Baidu Speech Recognition, supports natural language commands
- **🤖 Compound Command Support**: Complex multi-step command parsing through LLM
- **👁️ Visual Perception**: Real-time camera image recognition and intelligent description
- **🎨 LED Control**: Supports color settings, breathing effects, blinking, etc.
- **📺 Matrix Display**: Supports text scrolling display (automatic Chinese-English conversion)
- **🛰️ Smart Cruise**: Random cruise mode with automatic obstacle avoidance
- **🖥️ Dual Interface**: Optional GUI and console modes
- **📋 Command Queue**: Intelligent command queuing execution system
- **💓 Heartbeat Mechanism**: Flight status maintenance and safety monitoring

## 🏗️ 系统架构 / System Architecture

### 中文 / Chinese
```
main.py (主控制器)
├── voice_controller.py (语音控制器)
│   ├── baidu_asr.py (百度语音识别)
│   └── speech_synthesis.py (语音合成)
├── tello_extended_controller.py (扩展Tello控制器)
│   ├── cruise_module.py (巡航模块)
│   └── vision_module.py (视觉感知模块)
├── command_queue_manager.py (指令队列管理器)
├── llm_client.py (LLM客户端)
├── voice_ui.py (图形界面)
└── config.py (配置文件)
```

### 英文 / English
```
main.py (Main Controller)
├── voice_controller.py (Voice Controller)
│   ├── baidu_asr.py (Baidu ASR)
│   └── speech_synthesis.py (Speech Synthesis)
├── tello_extended_controller.py (Extended Tello Controller)
│   ├── cruise_module.py (Cruise Module)
│   └── vision_module.py (Vision Module)
├── command_queue_manager.py (Command Queue Manager)
├── llm_client.py (LLM Client)
├── voice_ui.py (GUI Interface)
└── config.py (Configuration)
```

## 📦 环境依赖 / Dependencies

### 中文 / Chinese
```bash
# 核心依赖
pip install djitellopy        # Tello无人机控制
pip install pyttsx3          # 语音合成
pip install pyaudio          # 音频处理
pip install keyboard         # 键盘监听
pip install requests         # HTTP请求
pip install opencv-python    # 视频处理
pip install tkinter          # 图形界面（通常随Python自带）

# 可选依赖（Windows）
pip install msvcrt           # Windows键盘输入检测
```

### 英文 / English
```bash
# Core Dependencies
pip install djitellopy        # Tello drone control
pip install pyttsx3          # Text-to-speech
pip install pyaudio          # Audio processing
pip install keyboard         # Keyboard monitoring
pip install requests         # HTTP requests
pip install opencv-python    # Video processing
pip install tkinter          # GUI framework (usually built-in)

# Optional Dependencies (Windows)
pip install msvcrt           # Windows keyboard input detection
```

## ⚙️ 配置说明 / Configuration

### 中文 / Chinese
在 [`config.py`](config.py) 中配置以下参数：

1. **LLM API 配置**:
   ```python
   API_BASE_URL = "https://api.siliconflow.cn"
   API_KEY = "your-api-key"
   MODEL_NAME = "Pro/deepseek-ai/DeepSeek-V3"
   ```

2. **百度语音识别配置**:
   ```python
   BAIDU_APP_ID = "your-app-id"
   BAIDU_API_KEY = "your-api-key"
   BAIDU_SECRET_KEY = "your-secret-key"
   ```

3. **百度图像识别配置**:
   ```python
   BAIDU_VISION_APP_ID = "your-vision-app-id"
   BAIDU_VISION_API_KEY = "your-vision-api-key"
   BAIDU_VISION_SECRET_KEY = "your-vision-secret-key"
   ```

4. **Tello配置**:
   ```python
   TELLO_IP = "192.168.37.180"  # Tello的IP地址
   ```

### 英文 / English
Configure the following parameters in [`config.py`](config.py):

1. **LLM API Configuration**:
   ```python
   API_BASE_URL = "https://api.siliconflow.cn"
   API_KEY = "your-api-key"
   MODEL_NAME = "Pro/deepseek-ai/DeepSeek-V3"
   ```

2. **Baidu ASR Configuration**:
   ```python
   BAIDU_APP_ID = "your-app-id"
   BAIDU_API_KEY = "your-api-key"
   BAIDU_SECRET_KEY = "your-secret-key"
   ```

3. **Baidu Vision Configuration**:
   ```python
   BAIDU_VISION_APP_ID = "your-vision-app-id"
   BAIDU_VISION_API_KEY = "your-vision-api-key"
   BAIDU_VISION_SECRET_KEY = "your-vision-secret-key"
   ```

4. **Tello Configuration**:
   ```python
   TELLO_IP = "192.168.37.180"  # Tello's IP address
   ```

## 🚀 快速开始 / Quick Start

### 中文 / Chinese

1. **准备工作**:
   - 启动Tello无人机
   - 连接到Tello的WiFi网络
   - 确保计算机联网（用于语音识别和LLM API）

2. **运行系统**:
   ```bash
   python main.py
   ```

3. **选择运行模式**:
   - 输入 `1` 选择图形界面模式（推荐）
   - 输入 `2` 选择控制台模式

4. **开始语音控制**:
   - 按 `V` 键激活语音模式
   - 按住 `空格` 键说话
   - 松开按键完成录音和识别

### 英文 / English

1. **Preparation**:
   - Power on Tello drone
   - Connect to Tello's WiFi network
   - Ensure computer has internet connection (for ASR and LLM API)

2. **Run System**:
   ```bash
   python main.py
   ```

3. **Choose Operation Mode**:
   - Input `1` for GUI mode (recommended)
   - Input `2` for console mode

4. **Start Voice Control**:
   - Press `V` key to activate voice mode
   - Hold `Space` key to speak
   - Release key to complete recording and recognition

## 🎯 支持的指令 / Supported Commands

### 基本飞行指令 / Basic Flight Commands

| 中文指令 / Chinese | 英文指令 / English | 功能 / Function |
|---|---|---|
| 起飞 | takeoff | 无人机起飞 / Drone takeoff |
| 降落 | land | 无人机降落 / Drone landing |
| 向前飞50厘米 | forward 50 | 向前飞行指定距离 / Fly forward specified distance |
| 向后飞30厘米 | back 30 | 向后飞行指定距离 / Fly backward specified distance |
| 向左飞40厘米 | left 40 | 向左飞行指定距离 / Fly left specified distance |
| 向右飞40厘米 | right 40 | 向右飞行指定距离 / Fly right specified distance |
| 向上飞20厘米 | up 20 | 向上飞行指定距离 / Fly up specified distance |
| 向下飞20厘米 | down 20 | 向下飞行指定距离 / Fly down specified distance |
| 顺时针旋转45度 | rotate_cw 45 | 顺时针旋转指定角度 / Rotate clockwise specified degrees |
| 逆时针旋转90度 | rotate_ccw 90 | 逆时针旋转指定角度 / Rotate counterclockwise specified degrees |
| 紧急停止 | stop | 立即停止所有运动 / Stop all movements immediately |

### 视觉感知指令 / Vision Commands

| 中文指令 / Chinese | 英文指令 / English | 功能 / Function |
|---|---|---|
| 开始录像 | start_video | 启动视频流 / Start video stream |
| 停止录像 | stop_video | 停止视频流 / Stop video stream |
| 拍照 | capture_image | 捕获当前画面 / Capture current frame |
| 识别当前画面 | recognize_view | 识别视野中的物体 / Recognize objects in view |
| 开始自动识别 | start_auto_recognition | 启动自动识别模式 / Start auto recognition mode |
| 停止自动识别 | stop_auto_recognition | 停止自动识别模式 / Stop auto recognition mode |

### LED控制指令 / LED Control Commands

| 中文指令 / Chinese | 英文指令 / English | 功能 / Function |
|---|---|---|
| 设置红色灯光 | led_color red | 设置LED为红色 / Set LED to red |
| 设置蓝色呼吸灯 | led_breath blue 1.0 | 设置蓝色呼吸灯效果 / Set blue breathing effect |
| 红蓝交替闪烁 | led_blink red blue 1.0 | 红蓝交替闪烁 / Red-blue alternating blink |
| 显示Hello World | display_text Hello World | 点阵屏显示文本 / Display text on matrix |

### 巡航指令 / Cruise Commands

| 中文指令 / Chinese | 英文指令 / English | 功能 / Function |
|---|---|---|
| 开始巡航 | start_cruise | 启动智能巡航模式 / Start intelligent cruise mode |
| 停止巡航 | stop_cruise | 停止巡航模式 / Stop cruise mode |
| 查看巡航状态 | cruise_status | 查看当前巡航状态 / Check cruise status |
| 查看测距 | tof_distance | 查看激光测距数据 / Check ToF distance data |

### 复合指令示例 / Compound Command Examples

| 中文指令 / Chinese | 解析结果 / Parsed Result |
|---|---|
| 先起飞再向前飞50厘米 | takeoff;forward 50 |
| 起飞后开始录像然后拍照识别 | takeoff;start_video;capture_image;recognize_view |
| 向前飞30厘米再设置红色灯光 | forward 30;led_color red |
| 先显示欢迎再开始巡航 | display_text Welcome;start_cruise |

## 💡 使用技巧 / Usage Tips

### 中文 / Chinese

1. **语音识别优化**:
   - 在安静环境中使用
   - 说话清晰，语速适中
   - 等待"开始录音"提示后再说话

2. **指令使用建议**:
   - 复合指令中各步骤会按顺序执行
   - 紧急情况下说"停止"可立即停止所有动作
   - 起飞前检查电池电量和周围环境

3. **视觉感知**:
   - 确保光线充足以获得更好的识别效果
   - 自动识别模式会消耗较多网络流量
   - 可通过语音关闭自动描述以减少播报

4. **安全提醒**:
   - 始终在开阔、安全的环境中飞行
   - 保持无人机在视线范围内
   - 注意电池电量，及时降落充电

### 英文 / English

1. **Voice Recognition Optimization**:
   - Use in quiet environment
   - Speak clearly at moderate speed
   - Wait for "recording started" prompt before speaking

2. **Command Usage Tips**:
   - Compound commands execute in sequence
   - Say "stop" in emergency to halt all movements immediately
   - Check battery level and surroundings before takeoff

3. **Visual Perception**:
   - Ensure sufficient lighting for better recognition
   - Auto recognition mode consumes more network traffic
   - Voice-disable auto description to reduce announcements

4. **Safety Reminders**:
   - Always fly in open, safe environments
   - Keep drone within line of sight
   - Monitor battery level and land for charging when needed

## 🔧 故障排除 / Troubleshooting

### 中文 / Chinese

**常见问题**:

1. **无人机连接失败**:
   - 检查是否连接到Tello的WiFi
   - 确认IP地址设置正确
   - 重启无人机和程序

2. **语音识别失败**:
   - 检查网络连接
   - 确认百度API配置正确
   - 检查麦克风权限

3. **视频流启动失败**:
   - 重启视频流: `restart_video_stream()`
   - 检查无人机是否连接
   - 确认其他程序未占用摄像头

4. **LLM解析错误**:
   - 检查API密钥配置
   - 确认网络连接正常
   - 尝试更换模型

### 英文 / English

**Common Issues**:

1. **Drone Connection Failed**:
   - Check if connected to Tello's WiFi
   - Confirm IP address settings are correct
   - Restart drone and program

2. **Voice Recognition Failed**:
   - Check network connection
   - Confirm Baidu API configuration is correct
   - Check microphone permissions

3. **Video Stream Startup Failed**:
   - Restart video stream: `restart_video_stream()`
   - Check if drone is connected
   - Ensure no other programs are using camera

4. **LLM Parsing Error**:
   - Check API key configuration
   - Confirm network connection is normal
   - Try switching models

## 📝 开发说明 / Development Notes

### 中文 / Chinese

**核心模块**:

- [`main.py`](main.py): 主控制器，负责系统初始化和模式选择
- [`voice_controller.py`](voice_controller.py): 语音控制器，处理语音识别和按键监听
- [`tello_extended_controller.py`](tello_extended_controller.py): 扩展Tello控制器，集成各功能模块
- [`command_queue_manager.py`](command_queue_manager.py): 指令队列管理器，处理指令排队和心跳
- [`llm_client.py`](llm_client.py): LLM客户端，负责智能指令解析和图像描述
- [`vision_module.py`](vision_module.py): 视觉感知模块，处理摄像头和图像识别
- [`voice_ui.py`](voice_ui.py): 图形界面，提供可视化控制界面

**扩展建议**:
- 可添加更多LED效果模式
- 支持更多语言的语音识别
- 增加飞行路径规划功能
- 集成更多视觉AI功能

### 英文 / English

**Core Modules**:

- [`main.py`](main.py): Main controller for system initialization and mode selection
- [`voice_controller.py`](voice_controller.py): Voice controller for speech recognition and key monitoring
- [`tello_extended_controller.py`](tello_extended_controller.py): Extended Tello controller integrating functional modules
- [`command_queue_manager.py`](command_queue_manager.py): Command queue manager for instruction queuing and heartbeat
- [`llm_client.py`](llm_client.py): LLM client for intelligent command parsing and image description
- [`vision_module.py`](vision_module.py): Vision module for camera and image recognition
- [`voice_ui.py`](voice_ui.py): GUI interface providing visual control interface

**Extension Suggestions**:
- Add more LED effect modes
- Support more languages for speech recognition
- Add flight path planning functionality
- Integrate more visual AI features

## 👥 作者信息 / Authors

**开发团队 / Development Team**: 杨垚，乔明梁

## 📄 许可证 / License

本项目仅供学习和研究使用 / This project is for educational and research purposes only.

## 🔗 相关链接 / Related Links

- [DJI Tello SDK](https://github.com/dji-sdk/Tello-Python)
- [百度语音识别 API](https://ai.baidu.com/tech/speech)
- [百度图像识别 API](https://ai.baidu.com/tech/vision)

---

⚡ **快速体验**: 下载代码 → 配置API → 连接Tello → 运行 [`main.py`](main.py) → 开始语音控制！  
⚡ **Quick Experience**: Download code → Configure API → Connect Tello → Run [`main.py`](main.py) → Start voice control!
