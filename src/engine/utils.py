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
    hwndDC = None
    mfcDC = None
    saveDC = None
    saveBitMap = None
    
    try:
        # 1. Capture Full Window (More reliable for games than ClientOnly)
        # We need the full window dimensions to create the compatible bitmap
        w_left, w_top, w_right, w_bottom = win32gui.GetWindowRect(hwnd)
        w_width = w_right - w_left
        w_height = w_bottom - w_top
        
        if w_width <= 0 or w_height <= 0: return None

        hwndDC = win32gui.GetWindowDC(hwnd)
        mfcDC  = win32ui.CreateDCFromHandle(hwndDC)
        saveDC = mfcDC.CreateCompatibleDC()
        
        saveBitMap = win32ui.CreateBitmap()
        saveBitMap.CreateCompatibleBitmap(mfcDC, w_width, w_height)
        saveDC.SelectObject(saveBitMap)
        
        # Use PW_RENDERFULLCONTENT (2) which includes the window frame/titlebar
        # This is often necessary for hardware accelerated windows that return black otherwise
        PW_RENDERFULLCONTENT = 2
        result = ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), PW_RENDERFULLCONTENT)
        
        img_final = None
        
        if result == 1:
             bmpinfo = saveBitMap.GetInfo()
             bmpstr = saveBitMap.GetBitmapBits(True)
             img = np.frombuffer(bmpstr, dtype='uint8')
             img.shape = (bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4)
             img_full = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
             
             # 2. Crop to Client Area
             # We captured the whole window, but we only want the game content (Client Area).
             # We need to calculate the offset of the Client Area relative to the Window.
             
             point = win32gui.ClientToScreen(hwnd, (0,0))
             client_screen_x, client_screen_y = point
             
             # WindowRect is also in Screen Coords
             offset_x = client_screen_x - w_left
             offset_y = client_screen_y - w_top
             
             # Get confirmed Client Size
             _, _, c_right, c_bottom = win32gui.GetClientRect(hwnd)
             c_width = c_right
             c_height = c_bottom
             
             # Sanity check and crop
             if c_width > 0 and c_height > 0 and offset_x >= 0 and offset_y >= 0:
                 end_x = min(img_full.shape[1], offset_x + c_width)
                 end_y = min(img_full.shape[0], offset_y + c_height)
                 
                 # Ensure we don't slice with invalid coords
                 if end_x > offset_x and end_y > offset_y:
                    img_final = img_full[offset_y:end_y, offset_x:end_x]
                 else:
                    img_final = img_full # Fallback
             else:
                 img_final = img_full

        return img_final

    except Exception as e:
        print(f"Background Capture Error: {e}")
        return None
        
    finally:
        # cleanup
        if saveBitMap: win32gui.DeleteObject(saveBitMap.GetHandle())
        if saveDC: saveDC.DeleteDC()
        if mfcDC: mfcDC.DeleteDC()
        if hwndDC: win32gui.ReleaseDC(hwnd, hwndDC)

def capture_and_scale(sct, hwnd, mode=1, background_mode=False):
    capture_method = "screen"
    
    if background_mode:
        capture_method = "background"
    elif win32gui.IsIconic(hwnd):
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
