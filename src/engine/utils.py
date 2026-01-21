import cv2
import numpy as np
import mss
import time
import win32gui
import win32ui
import win32con
import ctypes

BASE_WIDTH = 1920
BASE_HEIGHT = 1080

def find_all_game_windows(keyword):
    """
    Returns a list of (hwnd, title, rect_dict) for all visible windows matching keyword.
    rect_dict is same format as get_client_rect_screen_coords
    """
    matches = []
    def callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if keyword in title:
                rect = get_client_rect_screen_coords(hwnd)
                if rect:
                    matches.append((hwnd, title, rect))
    win32gui.EnumWindows(callback, None)
    return matches

def get_client_rect_screen_coords(hwnd):
    try:
        left, top, right, bottom = win32gui.GetClientRect(hwnd)
        width = right - left
        height = bottom - top
        pt = win32gui.ClientToScreen(hwnd, (0, 0))
        screen_left = pt[0]
        screen_top = pt[1]
        return {"top": screen_top, "left": screen_left, "width": width, "height": height}
    except:
        return None

def capture_window_background(hwnd):
    try:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width = right - left
        height = bottom - top
        
        if width <= 0 or height <= 0: return None
        
        hwndDC = win32gui.GetWindowDC(hwnd)
        mfcDC  = win32ui.CreateDCFromHandle(hwndDC)
        saveDC = mfcDC.CreateCompatibleDC()
        
        saveBitMap = win32ui.CreateBitmap()
        saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
        saveDC.SelectObject(saveBitMap)

        result = ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 2)
        if result != 1:
            result = ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 0)

        bmpinfo = saveBitMap.GetInfo()
        bmpstr = saveBitMap.GetBitmapBits(True)
        
        img = np.frombuffer(bmpstr, dtype='uint8')
        img.shape = (bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4)
        
        win32gui.DeleteObject(saveBitMap.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwndDC)
        
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR) 
    except Exception:
        return None

def capture_and_scale(sct, hwnd, mode=1):
    capture_method = "screen"
    
    if win32gui.IsIconic(hwnd):
        if mode == 1:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.2)
        else:
            capture_method = "background"

    monitor = get_client_rect_screen_coords(hwnd)
    img_bgr = None
    
    if capture_method == "background":
         img_bgr = capture_window_background(hwnd)
         if img_bgr is None:
             return None, 1.0, 1.0, monitor
    else:
        if not monitor: return None, 1.0, 1.0, None
        screenshot = sct.grab(monitor)
        img_np = np.array(screenshot)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
    
    if img_bgr is None: return None, 1.0, 1.0, monitor

    curr_h, curr_w = img_bgr.shape[:2]
    scale_x = curr_w / BASE_WIDTH
    scale_y = curr_h / BASE_HEIGHT
    
    return img_bgr, scale_x, scale_y, monitor

def match_template_multiscale(img, template, start_scale=1.0):
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    
    scales = np.linspace(start_scale * 0.8, start_scale * 1.2, 20)
    
    best_val = -1
    best_loc = None
    best_scale = 1.0
    best_size = (0, 0)
    
    for scale in scales:
        t_w = int(template_gray.shape[1] * scale)
        t_h = int(template_gray.shape[0] * scale)
        
        if t_w <= 0 or t_h <= 0 or t_w > img_gray.shape[1] or t_h > img_gray.shape[0]:
            continue
            
        resized_template = cv2.resize(template_gray, (t_w, t_h))
        
        res = cv2.matchTemplate(img_gray, resized_template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        
        if max_val > best_val:
            best_val = max_val
            best_loc = max_loc
            best_scale = scale
            best_size = (t_w, t_h)
            
    return best_val, best_loc, best_scale, best_size
