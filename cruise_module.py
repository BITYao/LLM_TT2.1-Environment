"""
巡航模块 - 平滑巡航与激光避障 (RC控制版本)
"""
import threading
import time
import random
import re

class CruiseModule:
    def __init__(self, tello):
        self.tello = tello
        self.is_cruising = False
        self.cruise_thread = None
        
        # 避障参数
        self.safe_distance = 500  # 安全距离 (mm)
        self.warning_distance = 800  # 警告距离 (mm)
        self.max_distance = 8190  # 最大测距范围
        
        # RC控制参数 (速度范围: -100 到 100)
        self.cruise_speed = 35  # 前进巡航速度
        self.turn_speed = 30  # 转向速度
        self.vertical_speed = 25  # 上下移动速度
        self.avoidance_speed = 40  # 避障速度
        
        # 平滑控制参数
        self.control_interval = 0.1  # RC控制发送间隔 (秒)
        self.cruise_duration = 2.0  # 每次巡航动作持续时间 (秒)
        self.avoidance_duration = 1.5  # 避障动作持续时间 (秒)
        self.smooth_steps = 10  # 速度渐变步数
        
        # 状态记录
        self.last_tof_distance = None
        self.current_action = "forward"  # 当前动作
        self.action_start_time = 0  # 当前动作开始时间
        self.last_distance_check = 0  # 上次测距时间
        self.distance_check_interval = 0.5  # 测距检查间隔
        
        # 避免重复的历史记录
        self.action_history = []  # 动作历史
        self.consecutive_avoidance_count = 0  # 连续避障次数
        
        print("✅ 平滑巡航模块已初始化 (RC控制)")
    
    def get_tof_distance(self):
        """获取激光测距仪数据"""
        try:
            # 发送TOF测距指令
            response = self.tello.send_read_command('EXT tof?')
            
            if response:
                # 解析响应格式："tof 123"
                match = re.search(r'tof\s+(\d+)', response)
                if match:
                    distance = int(match.group(1))
                    self.last_tof_distance = distance
                    return distance
                else:
                    print(f"⚠ TOF数据格式异常: {response}")
                    return None
            else:
                print("❌ TOF响应为空")
                return None
                
        except Exception as e:
            print(f"❌ 获取TOF数据失败: {e}")
            return None
    
    def is_obstacle_detected(self):
        """检测是否有障碍物"""
        distance = self.get_tof_distance()
        
        if distance is None:
            print("⚠ 无法获取测距数据，进入避障模式")
            return True  # 安全起见，无法测距时认为有障碍
        
        if distance >= self.max_distance:
            return False
        
        if distance < self.safe_distance:
            print(f"🚨 检测到障碍物！距离: {distance}mm")
            return True
        elif distance < self.warning_distance:
            print(f"⚠ 前方障碍物较近，距离: {distance}mm")
            return False
        else:
            return False
    
    def smooth_rc_control(self, target_lr, target_fb, target_ud, target_yaw, duration):
        """平滑的RC控制，带速度渐变"""
        try:
            # 计算渐变步骤
            steps = max(1, int(duration / self.control_interval))
            
            # 渐变到目标速度
            for i in range(steps):
                progress = (i + 1) / steps
                
                # 使用二次函数实现平滑加速
                smooth_progress = progress * progress
                
                current_lr = int(target_lr * smooth_progress)
                current_fb = int(target_fb * smooth_progress)
                current_ud = int(target_ud * smooth_progress)
                current_yaw = int(target_yaw * smooth_progress)
                
                # 发送RC控制指令
                self.tello.send_rc_control(current_lr, current_fb, current_ud, current_yaw)
                
                # 检查是否需要停止巡航
                if not self.is_cruising:
                    break
                
                time.sleep(self.control_interval)
            
            # 保持目标速度一段时间
            maintain_steps = max(1, int(duration * 0.7 / self.control_interval))
            for _ in range(maintain_steps):
                if not self.is_cruising:
                    break
                
                self.tello.send_rc_control(target_lr, target_fb, target_ud, target_yaw)
                time.sleep(self.control_interval)
            
            # 渐变停止
            stop_steps = max(1, int(duration * 0.3 / self.control_interval))
            for i in range(stop_steps):
                if not self.is_cruising:
                    break
                
                progress = 1.0 - (i + 1) / stop_steps
                
                current_lr = int(target_lr * progress)
                current_fb = int(target_fb * progress)
                current_ud = int(target_ud * progress)
                current_yaw = int(target_yaw * progress)
                
                self.tello.send_rc_control(current_lr, current_fb, current_ud, current_yaw)
                time.sleep(self.control_interval)
            
            # 确保完全停止
            self.tello.send_rc_control(0, 0, 0, 0)
            
        except Exception as e:
            print(f"❌ RC控制执行失败: {e}")
            # 紧急停止
            try:
                self.tello.send_rc_control(0, 0, 0, 0)
            except:
                pass
    
    def execute_avoidance_maneuver(self):
        """执行平滑避障机动"""
        try:
            self.consecutive_avoidance_count += 1
            
            # 根据连续避障次数调整策略
            if self.consecutive_avoidance_count > 3:
                # 连续避障过多，尝试大幅改变方向
                print("🔄 连续避障过多，执行大幅转向")
                # 大幅转向 + 后退
                self.smooth_rc_control(0, -self.avoidance_speed, 0, random.choice([-60, 60]), 2.0)
                time.sleep(0.5)
                # 继续转向
                self.smooth_rc_control(0, 0, 0, random.choice([-40, 40]), 1.5)
                self.consecutive_avoidance_count = 0
                return True
            
            # 选择避障策略
            avoidance_strategies = [
                ("left_turn", -self.avoidance_speed, 0, 0, -self.turn_speed),  # 左转
                ("right_turn", self.avoidance_speed, 0, 0, self.turn_speed),   # 右转
                ("back_left", -self.avoidance_speed//2, -self.avoidance_speed//2, 0, -self.turn_speed//2),  # 后退+左转
                ("back_right", self.avoidance_speed//2, -self.avoidance_speed//2, 0, self.turn_speed//2),   # 后退+右转
                ("up_back", 0, -self.avoidance_speed//2, self.vertical_speed, 0),      # 上升+后退
                ("down_back", 0, -self.avoidance_speed//2, -self.vertical_speed, 0),   # 下降+后退
            ]
            
            # 避免重复最近的动作
            available_strategies = []
            for strategy in avoidance_strategies:
                if strategy[0] not in self.action_history[-2:]:
                    available_strategies.append(strategy)
            
            if not available_strategies:
                available_strategies = avoidance_strategies
            
            # 随机选择避障策略
            strategy_name, lr, fb, ud, yaw = random.choice(available_strategies)
            
            print(f"🔄 执行避障机动: {strategy_name}")
            print(f"   RC控制: lr={lr}, fb={fb}, ud={ud}, yaw={yaw}")
            
            # 执行避障动作
            self.smooth_rc_control(lr, fb, ud, yaw, self.avoidance_duration)
            
            # 记录动作历史
            self.action_history.append(strategy_name)
            if len(self.action_history) > 5:
                self.action_history.pop(0)
            
            print(f"✅ 避障机动完成: {strategy_name}")
            
            # 短暂悬停
            time.sleep(0.5)
            
            return True
            
        except Exception as e:
            print(f"❌ 避障机动失败: {e}")
            # 紧急停止
            try:
                self.tello.send_rc_control(0, 0, 0, 0)
            except:
                pass
            return False
    
    def execute_cruise_action(self):
        """执行巡航动作"""
        try:
            # 重置连续避障计数
            self.consecutive_avoidance_count = 0
            
            # 定义巡航动作模式
            cruise_patterns = [
                ("forward", 0, self.cruise_speed, 0, 0),  # 直线前进
                ("forward_slight_left", -self.cruise_speed//4, self.cruise_speed, 0, 0),  # 前进+微左
                ("forward_slight_right", self.cruise_speed//4, self.cruise_speed, 0, 0),   # 前进+微右
                ("spiral_left", -self.cruise_speed//3, self.cruise_speed, 0, -self.turn_speed//2),  # 螺旋左转
                ("spiral_right", self.cruise_speed//3, self.cruise_speed, 0, self.turn_speed//2),   # 螺旋右转
                ("gentle_turn_left", 0, self.cruise_speed, 0, -self.turn_speed//3),   # 缓慢左转
                ("gentle_turn_right", 0, self.cruise_speed, 0, self.turn_speed//3),    # 缓慢右转
                ("rise_forward", 0, self.cruise_speed, self.vertical_speed//2, 0),      # 上升前进
                ("descend_forward", 0, self.cruise_speed, -self.vertical_speed//2, 0),  # 下降前进
            ]
            
            # 选择巡航模式
            if random.random() < 0.7:  # 70%概率保持直线或微调
                pattern_name, lr, fb, ud, yaw = random.choice(cruise_patterns[:3])
            else:  # 30%概率选择更复杂的动作
                pattern_name, lr, fb, ud, yaw = random.choice(cruise_patterns[3:])
            
            print(f"🎯 巡航动作: {pattern_name}")
            print(f"   RC控制: lr={lr}, fb={fb}, ud={ud}, yaw={yaw}")
            
            # 执行巡航动作
            self.smooth_rc_control(lr, fb, ud, yaw, self.cruise_duration)
            
            self.current_action = pattern_name
            
            # 记录动作历史
            self.action_history.append(pattern_name)
            if len(self.action_history) > 3:
                self.action_history.pop(0)
            
            return True
            
        except Exception as e:
            print(f"❌ 巡航动作失败: {e}")
            # 紧急停止
            try:
                self.tello.send_rc_control(0, 0, 0, 0)
            except:
                pass
            return False
    
    def cruise_worker(self):
        """巡航工作线程"""
        print("🚁 平滑巡航线程已启动")
        
        while self.is_cruising:
            try:
                current_time = time.time()
                
                # 定期检查距离
                if current_time - self.last_distance_check >= self.distance_check_interval:
                    self.last_distance_check = current_time
                    
                    # 检查前方是否有障碍物
                    if self.is_obstacle_detected():
                        print("🚨 检测到障碍物，执行避障")
                        success = self.execute_avoidance_maneuver()
                        if not success:
                            print("⚠ 避障失败，暂停巡航")
                            time.sleep(1)
                        continue
                
                # 执行正常巡航
                success = self.execute_cruise_action()
                
                if not success:
                    print("⚠ 巡航动作失败，暂停片刻")
                    time.sleep(1)
                else:
                    # 巡航动作完成后的短暂间隔
                    time.sleep(0.3)
                
                # 显示当前状态
                if self.last_tof_distance is not None:
                    print(f"📏 前方距离: {self.last_tof_distance}mm | 动作: {self.current_action}")
                
            except Exception as e:
                print(f"❌ 巡航线程错误: {e}")
                # 紧急停止所有控制
                try:
                    self.tello.send_rc_control(0, 0, 0, 0)
                except:
                    pass
                time.sleep(1)
        
        # 巡航结束，确保停止所有控制
        try:
            self.tello.send_rc_control(0, 0, 0, 0)
            print("🛑 已停止所有RC控制")
        except:
            pass
        
        print("🛑 平滑巡航线程已退出")
    
    def start_cruise(self):
        """开始巡航"""
        if self.is_cruising:
            print("⚠ 巡航已在进行中")
            return False
        
        try:
            # 先测试激光测距
            distance = self.get_tof_distance()
            if distance is None:
                print("❌ 无法获取激光测距数据，无法启动巡航")
                return False
            
            print(f"📏 初始前方距离: {distance}mm")
            
            # 检查初始距离是否安全
            if distance < self.safe_distance:
                print(f"❌ 初始距离过近({distance}mm)，无法启动巡航")
                return False
            
            # 启动巡航
            self.is_cruising = True
            self.consecutive_avoidance_count = 0
            self.action_history.clear()
            self.last_distance_check = time.time()
            
            self.cruise_thread = threading.Thread(target=self.cruise_worker, daemon=True)
            self.cruise_thread.start()
            
            print("✅ 平滑巡航已启动")
            print(f"⚙️ 安全距离: {self.safe_distance}mm")
            print(f"⚙️ 警告距离: {self.warning_distance}mm")
            print(f"⚙️ 巡航速度: {self.cruise_speed}")
            print(f"⚙️ 控制间隔: {self.control_interval}秒")
            print(f"⚙️ 动作持续: {self.cruise_duration}秒")
            
            return True
            
        except Exception as e:
            print(f"❌ 启动巡航失败: {e}")
            self.is_cruising = False
            return False
    
    def stop_cruise(self):
        """停止巡航"""
        if not self.is_cruising:
            print("⚠ 巡航未在进行中")
            return
        
        print("🛑 正在停止平滑巡航...")
        self.is_cruising = False
        
        # 立即停止RC控制
        try:
            self.tello.send_rc_control(0, 0, 0, 0)
            print("🛑 已停止RC控制")
        except Exception as e:
            print(f"⚠ 停止RC控制时出错: {e}")
        
        # 等待巡航线程结束
        if self.cruise_thread:
            self.cruise_thread.join(timeout=5)
        
        print("✅ 平滑巡航已停止")
    
    def get_cruise_status(self):
        """获取巡航状态"""
        if self.is_cruising:
            status = f"平滑巡航中 (动作: {self.current_action}"
            if self.last_tof_distance is not None:
                status += f", 前方距离: {self.last_tof_distance}mm"
            if self.consecutive_avoidance_count > 0:
                status += f", 连续避障: {self.consecutive_avoidance_count}次"
            status += ")"
            return status
        else:
            return "未巡航"
    
    def adjust_cruise_parameters(self, safe_distance=None, cruise_speed=None, control_interval=None):
        """调整巡航参数"""
        if safe_distance is not None:
            self.safe_distance = max(200, min(1000, safe_distance))
            self.warning_distance = max(self.safe_distance + 100, self.warning_distance)
            print(f"⚙️ 安全距离调整为: {self.safe_distance}mm")
        
        if cruise_speed is not None:
            self.cruise_speed = max(10, min(80, cruise_speed))
            self.turn_speed = max(10, min(60, int(cruise_speed * 0.8)))
            self.vertical_speed = max(10, min(50, int(cruise_speed * 0.7)))
            self.avoidance_speed = max(20, min(90, int(cruise_speed * 1.2)))
            print(f"⚙️ 巡航速度调整为: {self.cruise_speed}")
        
        if control_interval is not None:
            self.control_interval = max(0.05, min(0.5, control_interval))
            print(f"⚙️ 控制间隔调整为: {self.control_interval}秒")
    
    def emergency_stop(self):
        """紧急停止所有控制"""
        print("🚨 巡航模块紧急停止")
        self.is_cruising = False
        try:
            self.tello.send_rc_control(0, 0, 0, 0)
        except:
            pass
