import cv2
import numpy as np
import pyautogui
import mss
import time
import os
import keyboard
import win32gui
import win32ui
import win32con
import sys
from input_utils import click_direct_input, is_admin, focus_window

# Configuration
REFRESH_TEMPLATE_PATH = "button_template.png"
CONFIRM_TEMPLATE_PATH = "confirm_template.png"
OK_TEMPLATE_PATH = "ok_template.png"
REFRESH_ICON_PATH = "refresh_icon_template.png"

CONFIDENCE_THRESHOLD = 0.8
REFRESH_INTERVAL = 1.0 

# Base Resolution (What the templates were created on)
BASE_WIDTH = 1920
BASE_HEIGHT = 1080

GAME_TITLE_KEYWORD = "Tower of Fantasy"

# Globals
running = True
MODE = 1 # 1: Fast (Active), 2: Slow (Background/Passive)

class State:
    REFRESHING = "REFRESHING"
    BUYING = "BUYING"
    CONFIRMING = "CONFIRMING"

current_state = State.REFRESHING

def stop_script():
    global running
    print("\nF1 pressed. Stopping script...")
    running = False

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.realpath(__file__))

def load_templates():
    paths = [REFRESH_TEMPLATE_PATH, CONFIRM_TEMPLATE_PATH, OK_TEMPLATE_PATH, REFRESH_ICON_PATH]
    templates = []
    base_path = get_base_path()
    
    for p in paths:
        full_path = os.path.join(base_path, p)
        if not os.path.exists(full_path):
            print(f"Error: Template '{full_path}' not found!")
            return None
        img = cv2.imread(full_path)
        if img is None: return None
        templates.append(img)
        
    return templates

def get_window_handle(keyword):
    hwnd_found = None
    def callback(hwnd, extra):
        nonlocal hwnd_found
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if keyword in title:
                hwnd_found = hwnd
    win32gui.EnumWindows(callback, None)
    return hwnd_found

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
    """
    Captures a specific window even if it is minimized/background using PrintWindow.
    Returns: (img_bgr, width, height) or None
    """
    try:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width = right - left
        height = bottom - top
        
        if width <= 0 or height <= 0: return None
        
        # Create DC
        hwndDC = win32gui.GetWindowDC(hwnd)
        mfcDC  = win32ui.CreateDCFromHandle(hwndDC)
        saveDC = mfcDC.CreateCompatibleDC()
        
        saveBitMap = win32ui.CreateBitmap()
        saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
        saveDC.SelectObject(saveBitMap)

        result = ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 2)
        
        if result != 1:
            # Fallback
            result = ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 0)

        bmpinfo = saveBitMap.GetInfo()
        bmpstr = saveBitMap.GetBitmapBits(True)
        
        img = np.frombuffer(bmpstr, dtype='uint8')
        img.shape = (bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4)
        
        # Free resources
        win32gui.DeleteObject(saveBitMap.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwndDC)
        
        # Convert RGBA to BGR
        # Note: Bitmaps are usually BGRA or BGRX
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR) 
        
    except Exception as e:
        # print(f"Background capture failed: {e}")
        return None

def capture_and_scale(sct, hwnd):
    # Determine if we should restore or capture background
    capture_method = "screen" # default
    
    if win32gui.IsIconic(hwnd):
        if MODE == 1:
            # Fast mode: Restore immediately
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.2)
        else:
            # Slow mode: Try background capture
            capture_method = "background"

    monitor = get_client_rect_screen_coords(hwnd)
    
    img_bgr = None
    
    if capture_method == "background":
         img_bgr = capture_window_background(hwnd)
         if img_bgr is None:
             # Failed background capture, fallback to restore?
             # Or just skip this frame?
             return None, 1.0, 1.0, monitor
    else:
        # Screen capture (mss)
        if not monitor: return None, 1.0, 1.0, None # Fail safe
        screenshot = sct.grab(monitor)
        img_np = np.array(screenshot)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
    
    if img_bgr is None: return None, 1.0, 1.0, monitor

    curr_h, curr_w = img_bgr.shape[:2]
    
    if curr_w != BASE_WIDTH or curr_h != BASE_HEIGHT:
        img_resized = cv2.resize(img_bgr, (BASE_WIDTH, BASE_HEIGHT))
        scale_x = curr_w / BASE_WIDTH
        scale_y = curr_h / BASE_HEIGHT
        return img_resized, scale_x, scale_y, monitor
    else:
        return img_bgr, 1.0, 1.0, monitor

def find_and_click(img_bgr, template, monitor, scale_x, scale_y, state_name):
    template_h, template_w = template.shape[:2]
    
    res = cv2.matchTemplate(img_bgr, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    
    if max_val >= CONFIDENCE_THRESHOLD:
        # Detected in BASE resolution
        base_x = max_loc[0] + template_w // 2
        base_y = max_loc[1] + template_h // 2
        
        # Scale to REAL resolution
        real_x = int(base_x * scale_x)
        real_y = int(base_y * scale_y)
        
        # Add Monitor Offset
        final_x = monitor["left"] + real_x
        final_y = monitor["top"] + real_y
        
        print(f"[{state_name}] Match ({max_val:.2f}). Clicking at ({final_x}, {final_y})")
        
        pyautogui.moveTo(final_x, final_y)
        click_direct_input()
        return True
    return False

last_refresh_time = 0

def run_state(current, sct, hwnd, templates):
    global last_refresh_time
    item_tmpl, confirm_tmpl, ok_tmpl, refresh_tmpl = templates
    
    # 1. Capture
    img, sx, sy, monitor = capture_and_scale(sct, hwnd)
    if img is None: return current # Failed to grab
    
    next_state = current
    
    if current == State.REFRESHING:
        if find_and_click(img, item_tmpl, monitor, sx, sy, "ITEM_FOUND"):
            print("-> Found item! BUYING...")
            
            # If in Slow Mode and minimized, we need to Restore NOW
            if MODE == 2:
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    time.sleep(0.5) # Wait for animation
                    
                # Ensure focus
                try:
                    win32gui.SetForegroundWindow(hwnd)
                    time.sleep(0.1)
                except: pass
                pass

            time.sleep(0.3)
            return State.BUYING
            
        # Only check refresh in Fast Mode (1)
        if MODE == 1:
            if time.time() - last_refresh_time >= REFRESH_INTERVAL:
                if find_and_click(img, refresh_tmpl, monitor, sx, sy, "AUTO_REFRESH"):
                    last_refresh_time = time.time()
                
    elif current == State.BUYING:
        if find_and_click(img, confirm_tmpl, monitor, sx, sy, "BUYING"):
            print("-> Confirmed! CONFIRMING...")
            time.sleep(0.3)
            return State.CONFIRMING
            
    elif current == State.CONFIRMING:
        if find_and_click(img, ok_tmpl, monitor, sx, sy, "CONFIRMING"):
            print("-> Done! REFRESHING...")
            time.sleep(0.5)
            return State.REFRESHING
            
    return next_state

def ask_user_mode():
    global MODE
    print("\nSelect Mode:")
    print("1: Fast Mode (Always Active, Auto-Refresh)")
    print("2: Slow Mode (Background Monitor, Auto-Maximize on Buy)")
    
    while True:
        try:
            val = input("Choice (1/2): ").strip()
            if val == "1": 
                MODE = 1
                break
            elif val == "2":
                MODE = 2
                break
        except: pass
    print(f"Mode {MODE} selected.\n")

def main():
    global current_state, MODE
    
    ask_user_mode()
    
    if not is_admin():
        print("WARNING: Script expects Admin privileges.")
        time.sleep(2)

    print("Auto-buyer: Window-Independent Mode.")
    print(f"Targeting window: '{GAME_TITLE_KEYWORD}'")
    print("Press 'F1' to stop.")
    
    keyboard.add_hotkey('f1', stop_script)
    keyboard.add_hotkey('esc', stop_script)
    
    templates = load_templates()
    if templates is None: return

    with mss.mss() as sct:
        # Wait for window
        hwnd = get_window_handle(GAME_TITLE_KEYWORD)
        if not hwnd:
            print(f"Waiting for '{GAME_TITLE_KEYWORD}'...")
            while not hwnd and running:
                hwnd = get_window_handle(GAME_TITLE_KEYWORD)
                time.sleep(1)
        
        if not running: return
        print(f"Window found! Handle: {hwnd}")
        
        try:
            focus_window(GAME_TITLE_KEYWORD)
        except: pass

        state_start_time = time.time()
        
        try:
            while running:
                # Check Timeouts
                if current_state in [State.BUYING, State.CONFIRMING]:
                     if time.time() - state_start_time > 2.0:
                         print("[Timeout] Resetting to REFRESHING.")
                         current_state = State.REFRESHING
                         state_start_time = time.time()

                new_state = run_state(current_state, sct, hwnd, templates)
                
                if new_state != current_state:
                    current_state = new_state
                    state_start_time = time.time()
                
                # Small delay
                time.sleep(0.01)

        except Exception as e:
            print(f"Error: {e}")
        finally:
            keyboard.unhook_all()

if __name__ == "__main__":
    main()
