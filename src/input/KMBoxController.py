'''
KMBoxController
KMBox Net 硬件 HID 输入适配器
通过 USB 硬件模拟键盘输入，绕过游戏反作弊检测
'''
import threading
import time
import random
import logging

from src.utils.logger import logger

# KMBox 全局实例（单例模式）
_kmbox_client = None
_kmbox_lock = threading.Lock()
_kmbox_initialized = False


def init_kmbox(ip, port, uuid, encrypted=True):
    """初始化 KMBox 连接"""
    global _kmbox_client, _kmbox_initialized
    
    with _kmbox_lock:
        if _kmbox_initialized:
            return _kmbox_client
            
        try:
            from kmbox_universal import KMBoxClient
            _kmbox_client = KMBoxClient(ip, port, uuid, timeout=3.0)
            _kmbox_initialized = True
            logger.info(f"[KMBox] 已连接: {ip}:{port} UUID={uuid} 加密={encrypted}")
            return _kmbox_client
        except ImportError:
            logger.error("[KMBox] kmbox-universal 未安装，请运行: pip install kmbox-universal")
            raise
        except Exception as e:
            logger.error(f"[KMBox] 连接失败: {e}")
            raise


def get_kmbox():
    """获取 KMBox 客户端实例"""
    global _kmbox_client
    if _kmbox_client is None:
        raise RuntimeError("[KMBox] 未初始化，请先调用 init_kmbox()")
    return _kmbox_client


# HID 键码映射表
# 将 pyautogui 风格的键名映射到 kmbox_universal.HidKey
_HID_KEY_MAP = None


def _get_hid_key_map():
    """延迟初始化 HID 键码映射"""
    global _HID_KEY_MAP
    if _HID_KEY_MAP is not None:
        return _HID_KEY_MAP
    
    from kmbox_universal import HidKey
    _HID_KEY_MAP = {
        # 字母键
        "A": HidKey.A, "B": HidKey.B, "C": HidKey.C, "D": HidKey.D,
        "E": HidKey.E, "F": HidKey.F, "G": HidKey.G, "H": HidKey.H,
        "I": HidKey.I, "J": HidKey.J, "K": HidKey.K, "L": HidKey.L,
        "M": HidKey.M, "N": HidKey.N, "O": HidKey.O, "P": HidKey.P,
        "Q": HidKey.Q, "R": HidKey.R, "S": HidKey.S, "T": HidKey.T,
        "U": HidKey.U, "V": HidKey.V, "W": HidKey.W, "X": HidKey.X,
        "Y": HidKey.Y, "Z": HidKey.Z,
        # 数字键
        "0": HidKey.NUM_0, "1": HidKey.NUM_1, "2": HidKey.NUM_2,
        "3": HidKey.NUM_3, "4": HidKey.NUM_4, "5": HidKey.NUM_5,
        "6": HidKey.NUM_6, "7": HidKey.NUM_7, "8": HidKey.NUM_8,
        "9": HidKey.NUM_9,
        # 功能键
        "F1": HidKey.F1, "F2": HidKey.F2, "F3": HidKey.F3,
        "F4": HidKey.F4, "F5": HidKey.F5, "F6": HidKey.F6,
        "F7": HidKey.F7, "F8": HidKey.F8, "F9": HidKey.F9,
        "F10": HidKey.F10, "F11": HidKey.F11, "F12": HidKey.F12,
        # 方向键
        "LEFT": HidKey.LEFT, "RIGHT": HidKey.RIGHT,
        "UP": HidKey.UP, "DOWN": HidKey.DOWN,
        # 特殊键
        "SPACE": HidKey.SPACE, "ENTER": HidKey.ENTER,
        "TAB": HidKey.TAB, "ESCAPE": HidKey.ESCAPE, "ESC": HidKey.ESCAPE,
        "DELETE": HidKey.DELETE, "END": HidKey.END,
        "HOME": HidKey.HOME, "INSERT": HidKey.INSERT,
        "PAGEUP": HidKey.PAGE_UP, "PAGEDOWN": HidKey.PAGE_DOWN,
        # 修饰键
        "CTRL": HidKey.LEFT_CTRL, "CTRLLEFT": HidKey.LEFT_CTRL,
        "CTRLRIGHT": HidKey.RIGHT_CTRL,
        "ALT": HidKey.LEFT_ALT, "ALTLEFT": HidKey.LEFT_ALT,
        "ALTRIGHT": HidKey.RIGHT_ALT,
        "SHIFT": HidKey.LEFT_SHIFT, "SHIFTLEFT": HidKey.LEFT_SHIFT,
        "SHIFTRIGHT": HidKey.RIGHT_SHIFT,
    }
    return _HID_KEY_MAP


def _to_hid_key(key_name):
    """将键名转换为 HidKey"""
    key_map = _get_hid_key_map()
    key_upper = key_name.upper()
    if key_upper in key_map:
        return key_map[key_upper]
    raise ValueError(f"未知按键: {key_name}")


# ========== 全局按键函数（兼容原有接口）==========

# 按键保持时长范围（毫秒）- 模拟人类行为
KEY_HOLD_MIN = 40
KEY_HOLD_MAX = 90


def key_down(key):
    """按下按键不释放"""
    try:
        client = get_kmbox()
        hid_key = _to_hid_key(key)
        client.key_down(hid_key)
    except Exception as e:
        logger.debug(f"[KMBox key_down] 失败: {key} - {e}")


def key_up(key):
    """释放按键"""
    try:
        client = get_kmbox()
        hid_key = _to_hid_key(key)
        client.key_up(hid_key)
    except Exception as e:
        logger.debug(f"[KMBox key_up] 失败: {key} - {e}")


def press_key(key, duration=None):
    """
    模拟按键按下并释放
    duration: 保持时长（秒），None 则随机
    """
    if not key:
        return
    
    if duration is None:
        # 随机保持时长，模拟人类行为
        hold_ms = random.randint(KEY_HOLD_MIN, KEY_HOLD_MAX)
        duration = hold_ms / 1000.0
    
    try:
        client = get_kmbox()
        hid_key = _to_hid_key(key)
        hold_ms = int(duration * 1000)
        client.key_press(hid_key, hold_ms)
    except Exception as e:
        logger.debug(f"[KMBox press_key] 失败: {key} - {e}")


def close_kmbox():
    """关闭 KMBox 连接"""
    global _kmbox_client, _kmbox_initialized
    with _kmbox_lock:
        if _kmbox_client is not None:
            try:
                _kmbox_client.close()
                logger.info("[KMBox] 已断开连接")
            except Exception as e:
                logger.warning(f"[KMBox] 断开连接失败: {e}")
            _kmbox_client = None
            _kmbox_initialized = False
