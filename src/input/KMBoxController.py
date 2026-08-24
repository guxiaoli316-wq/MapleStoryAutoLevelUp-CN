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
        "a": HidKey.A, "b": HidKey.B, "c": HidKey.C, "d": HidKey.D,
        "e": HidKey.E, "f": HidKey.F, "g": HidKey.G, "h": HidKey.H,
        "i": HidKey.I, "j": HidKey.J, "k": HidKey.K, "l": HidKey.L,
        "m": HidKey.M, "n": HidKey.N, "o": HidKey.O, "p": HidKey.P,
        "q": HidKey.Q, "r": HidKey.R, "s": HidKey.S, "t": HidKey.T,
        "u": HidKey.U, "v": HidKey.V, "w": HidKey.W, "x": HidKey.X,
        "y": HidKey.Y, "z": HidKey.Z,
        # 数字键
        "0": HidKey.NUM_0, "1": HidKey.NUM_1, "2": HidKey.NUM_2,
        "3": HidKey.NUM_3, "4": HidKey.NUM_4, "5": HidKey.NUM_5,
        "6": HidKey.NUM_6, "7": HidKey.NUM_7, "8": HidKey.NUM_8,
        "9": HidKey.NUM_9,
        # 功能键
        "f1": HidKey.F1, "f2": HidKey.F2, "f3": HidKey.F3,
        "f4": HidKey.F4, "f5": HidKey.F5, "f6": HidKey.F6,
        "f7": HidKey.F7, "f8": HidKey.F8, "f9": HidKey.F9,
        "f10": HidKey.F10, "f11": HidKey.F11, "f12": HidKey.F12,
        # 方向键
        "left": HidKey.LEFT, "right": HidKey.RIGHT,
        "up": HidKey.UP, "down": HidKey.DOWN,
        # 特殊键
        "space": HidKey.SPACE, "enter": HidKey.ENTER,
        "tab": HidKey.TAB, "escape": HidKey.ESCAPE, "esc": HidKey.ESCAPE,
        "delete": HidKey.DELETE, "end": HidKey.END,
        "home": HidKey.HOME, "insert": HidKey.INSERT,
        "pageup": HidKey.PAGE_UP, "pagedown": HidKey.PAGE_DOWN,
        # 修饰键
        "ctrl": HidKey.LEFT_CTRL, "ctrlleft": HidKey.LEFT_CTRL,
        "ctrlright": HidKey.RIGHT_CTRL,
        "alt": HidKey.LEFT_ALT, "altleft": HidKey.LEFT_ALT,
        "altright": HidKey.RIGHT_ALT,
        "shift": HidKey.LEFT_SHIFT, "shiftleft": HidKey.LEFT_SHIFT,
        "shiftright": HidKey.RIGHT_SHIFT,
    }
    return _HID_KEY_MAP


def _to_hid_key(key_name):
    """将键名转换为 HidKey"""
    key_map = _get_hid_key_map()
    key_lower = key_name.lower()
    if key_lower in key_map:
        return key_map[key_lower]
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
        logger.warning(f"[KMBox key_down] 失败: {key} - {e}")


def key_up(key):
    """释放按键"""
    try:
        client = get_kmbox()
        hid_key = _to_hid_key(key)
        client.key_up(hid_key)
    except Exception as e:
        logger.warning(f"[KMBox key_up] 失败: {key} - {e}")


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
        logger.warning(f"[KMBox press_key] 失败: {key} - {e}")


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
