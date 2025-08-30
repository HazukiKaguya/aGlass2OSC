# -*- coding: utf-8 -*-
"""
Name: aGlass To VRChat OSC Sender
Desc: 连接aGlassRuntime (Ver1.1.0.0)，调用API获取来自aGlass DK I/II Eye Tracker的原始眼动数据，并将其转换为VRChat支持的格式的眼动数据，然后使用OSC发送到VRChat。注意，此版本模型的眼球运动无法按照预期进行，需要调整算法。
Author: HazukiKaguya
Thanks: Google Gemini
"""

import ctypes
import time
import sys
import os
import socket
from datetime import datetime
from pythonosc import udp_client

# -----------------------------------------------------------------------------
# 配置
# -----------------------------------------------------------------------------
# 眼动数据记录功能，支持设置 True / False 来开启/关闭，支持设置日志文件名
ENABLE_LOGGING = False
LOG_FILENAME = "vrc_osc_log.csv"
# VRChat OSC 的 IP/端口 相关设置
OSC_IP = "127.0.0.1"
OSC_PORT = 9000 
# aGlass Runtime 相关设置
DLL_PATH = "C:/Program Files/aGlass/aGlass_vr_api.dll"
RUNTIME_IP = "127.0.0.1"
RUNTIME_SEND_PORT = 2000
RUNTIME_RECV_PORT = 2001
# 最大旋转角度相关设置
MAX_YAW_ANGLE = 30.0
MAX_PITCH_ANGLE = 25.0

# -----------------------------------------------------------------------------
# 全局初始化
# -----------------------------------------------------------------------------
AGLASS_ERROR_CODES = {
    0:  "AGLASS_OK: 成功",
    -1: "AGLASS_FAILED: 失败",
    -2: "AGLASS_NO_RESPONSE: 无响应",
    -3: "AGLASS_PARAM_ERROR: 参数错误",
}
class AGLASS_CALIB_COE(ctypes.Structure): _fields_ = [("coe", ctypes.c_ubyte * 1024)]
class AGLASS_INIT_PARAM(ctypes.Structure): _fields_ = [("calibCoe", AGLASS_CALIB_COE), ("pathSize", ctypes.c_int), ("path", ctypes.c_wchar_p)]
class AGLASS_POINT(ctypes.Structure): _fields_ = [("x", ctypes.c_float), ("y", ctypes.c_float)]
class AGLASS_GAZE_DATA(ctypes.Structure): _fields_ = [("timestamp", ctypes.c_longlong), ("valid", ctypes.c_int), ("gazePoint", AGLASS_POINT), ("pupilRadius", ctypes.c_float), ("pupilCenter", AGLASS_POINT), ("exData", ctypes.c_float * 16),]
AGLASS_GAZE_CALLBACK = ctypes.WINFUNCTYPE(None, ctypes.POINTER(AGLASS_GAZE_DATA))

try:
    osc_client = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)
    print(f"OSC 客户端已初始化，将数据发送到 VRChat ({OSC_IP}:{OSC_PORT})")
except Exception as e:
    print(f"错误：初始化 OSC 客户端失败: {e}")
    osc_client = None

aglass_lib = None
latest_left_gaze = {'valid': False, 'pitch': 0.0, 'yaw': 0.0}
latest_right_gaze = {'valid': False, 'pitch': 0.0, 'yaw': 0.0}
log_file_handler = None

# -----------------------------------------------------------------------------
# 回调
# -----------------------------------------------------------------------------
def left_eye_callback(gaze_data_ptr):
    global latest_left_gaze
    if gaze_data_ptr:
        gaze_data = gaze_data_ptr.contents
        is_valid = (gaze_data.valid == 1)
        latest_left_gaze['valid'] = is_valid
        if is_valid:
            latest_left_gaze['yaw'] = (gaze_data.gazePoint.x - 0.5) * 2.0 * MAX_YAW_ANGLE
            latest_left_gaze['pitch'] = (gaze_data.gazePoint.y - 0.5) * 2.0 * MAX_PITCH_ANGLE

def right_eye_callback(gaze_data_ptr):
    global latest_right_gaze
    if gaze_data_ptr:
        gaze_data = gaze_data_ptr.contents
        is_valid = (gaze_data.valid == 1)
        latest_right_gaze['valid'] = is_valid
        if is_valid:
            latest_right_gaze['yaw'] = (gaze_data.gazePoint.x - 0.5) * 2.0 * MAX_YAW_ANGLE
            latest_right_gaze['pitch'] = (gaze_data.gazePoint.y - 0.5) * 2.0 * MAX_PITCH_ANGLE

# -----------------------------------------------------------------------------
# 主程序
# -----------------------------------------------------------------------------
def send_udp_message(sock, message_bytes):
    buffer = bytearray(1024); buffer[:len(message_bytes)] = message_bytes
    sock.sendto(buffer, (RUNTIME_IP, RUNTIME_SEND_PORT))

def perform_udp_handshake():
    print("开始与 aGlass Runtime 执行 UDP 握手..."); receiver_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); receiver_socket.bind((RUNTIME_IP, RUNTIME_RECV_PORT)); receiver_socket.settimeout(5.0); sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        print(f"  -> 向 {RUNTIME_IP}:{RUNTIME_SEND_PORT} 发送 'path' 请求 (1024 bytes)..."); send_udp_message(sender_socket, b'path')
        path_data, _ = receiver_socket.recvfrom(1024); received_path = path_data.decode('utf-16-le').rstrip('\x00'); print(f"  <- 从 Runtime 收到路径: {received_path}")
        print(f"  -> 向 {RUNTIME_IP}:{RUNTIME_SEND_PORT} 发送 'request' 请求 (1024 bytes)..."); send_udp_message(sender_socket, b'request')
        calib_data, _ = receiver_socket.recvfrom(1024); print(f"  <- 从 Runtime 收到校准数据 ({len(calib_data)} bytes)")
        init_param = AGLASS_INIT_PARAM(); ctypes.memmove(ctypes.byref(init_param.calibCoe.coe), calib_data, len(calib_data)); init_param.path = received_path; init_param.pathSize = 512; print("UDP 握手成功，初始化参数已准备就绪。")
        return init_param
    except socket.timeout: print("\n错误：UDP 握手超时！请确保 aGlass Runtime 正在运行并且防火墙允许通信。"); return None
    finally: receiver_socket.close(); sender_socket.close()

def main():
    global aglass_lib, log_file_handler
    if not osc_client: return

    try:
        if ENABLE_LOGGING:
            log_file_handler = open(LOG_FILENAME, 'w', encoding='utf-8', newline='')
            log_file_handler.write("timestamp,eyes_closed,left_pitch,left_yaw,right_pitch,right_yaw\n")
            print(f"日志记录功能已开启，数据将保存到 '{LOG_FILENAME}'")

        init_param = perform_udp_handshake()
        if not init_param: return

        try:
            aglass_lib = ctypes.WinDLL(DLL_PATH)
            print("DLL加载成功。")
        except Exception as e: print(f"错误：DLL加载失败: {e}"); return

        aglass_lib.aGlass_init.argtypes = [ctypes.POINTER(AGLASS_INIT_PARAM)]; aglass_lib.aGlass_init.restype = ctypes.c_int
        aglass_lib.aGlass_release.restype = ctypes.c_int; aglass_lib.aGlass_start.restype = ctypes.c_int; aglass_lib.aGlass_stop.restype = ctypes.c_int
        aglass_lib.aGlass_start_tracking.argtypes = [AGLASS_GAZE_CALLBACK, AGLASS_GAZE_CALLBACK]; aglass_lib.aGlass_start_tracking.restype = ctypes.c_int
        aglass_lib.aGlass_stop_tracking.restype = ctypes.c_int
        
        left_callback_ptr = AGLASS_GAZE_CALLBACK(left_eye_callback)
        right_callback_ptr = AGLASS_GAZE_CALLBACK(right_eye_callback)

        print("正在初始化 aGlass..."); status_code = aglass_lib.aGlass_init(ctypes.byref(init_param))
        if status_code != 0: raise RuntimeError(f"aGlass_init 失败! API 返回值: {status_code}, 错误: {AGLASS_ERROR_CODES.get(status_code, '未知错误')}")
        print("初始化成功。")

        print("正在启动眼动模组..."); status_code = aglass_lib.aGlass_start()
        if status_code != 0: raise RuntimeError(f"aGlass_start 失败! API 返回值: {status_code}, 错误: {AGLASS_ERROR_CODES.get(status_code, '未知错误')}")
        print("模组启动成功。")
        
        print("正在开始眼动追踪..."); status_code = aglass_lib.aGlass_start_tracking(left_callback_ptr, right_callback_ptr)
        if status_code != 0: raise RuntimeError(f"aGlass_start_tracking 失败! API 返回值: {status_code}, 错误: {AGLASS_ERROR_CODES.get(status_code, '未知错误')}")
        print("眼动追踪已开始。按 Ctrl+C 退出。")

        while True:
            is_blinking = not latest_left_gaze['valid'] and not latest_right_gaze['valid']
            eyes_closed_amount = 1.0 if is_blinking else 0.0
            
            if ENABLE_LOGGING and log_file_handler:
                timestamp_str = datetime.now().isoformat()
                lp = latest_left_gaze['pitch'] if not is_blinking else ''
                ly = latest_left_gaze['yaw'] if not is_blinking else ''
                rp = latest_right_gaze['pitch'] if not is_blinking else ''
                ry = latest_right_gaze['yaw'] if not is_blinking else ''
                log_line = f"{timestamp_str},{eyes_closed_amount},{lp},{ly},{rp},{ry}\n"
                log_file_handler.write(log_line)

            osc_client.send_message("/tracking/eye/EyesClosedAmount", eyes_closed_amount)
            
            if not is_blinking:
                pitch_yaw_values = [
                    latest_left_gaze['pitch'], latest_left_gaze['yaw'], 
                    latest_right_gaze['pitch'], latest_right_gaze['yaw']
                ]
                osc_client.send_message("/tracking/eye/LeftRightPitchYaw", pitch_yaw_values)

            print(f"VRChat OSC -> Left(P/Y): {latest_left_gaze['pitch']:.1f}/{latest_left_gaze['yaw']:.1f} | Right(P/Y): {latest_right_gaze['pitch']:.1f}/{latest_right_gaze['yaw']:.1f} | Closed: {eyes_closed_amount:.2f}  ", end='\r')
            time.sleep(0.02)

    except KeyboardInterrupt: print("\n检测到用户中断。")
    except Exception as e: print(f"\n程序运行出错: {e}")
    finally:
        if aglass_lib:
            print("\n正在停止并释放 aGlass 资源...")
            aglass_lib.aGlass_stop_tracking(); aglass_lib.aGlass_stop(); aglass_lib.aGlass_release()
            print("SDK 资源已释放。程序退出。")
            
        if log_file_handler:
            log_file_handler.close()
            print(f"日志文件 '{LOG_FILENAME}' 已保存。")

if __name__ == "__main__":

    main()
