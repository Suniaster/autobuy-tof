import cv2
import numpy as np
import pyautogui
import mss
import time
import os
import keyboard
from input_utils import click_direct_input, is_admin

# Configuration
REFRESH_TEMPLATE_PATH = "button_template.png"
CONFIRM_TEMPLATE_PATH = "confirm_template.png"
OK_TEMPLATE_PATH = "ok_template.png"
REFRESH_ICON_PATH = "refresh_icon_template.png"

CONFIDENCE_THRESHOLD = 0.8
REFRESH_INTERVAL = 0.3  # Seconds

# Globals
running = True

class State:
    REFRESHING = "REFRESHING"
    BUYING = "BUYING"
    CONFIRMING = "CONFIRMING"

current_state = State.REFRESHING

def stop_script():
    global running
    print("\nF1 pressed. Stopping script...")
    running = False

def load_templates():
    paths = [REFRESH_TEMPLATE_PATH, CONFIRM_TEMPLATE_PATH, OK_TEMPLATE_PATH, REFRESH_ICON_PATH]
    descriptors = ["Item Button", "Confirm Button", "OK Button", "Refresh Icon"]
    templates = []
    
    for p, desc in zip(paths, descriptors):
        if not os.path.exists(p):
            print(f"Error: Template '{p}' ({desc}) not found!")
            return None
        img = cv2.imread(p)
        if img is None:
             print(f"Error: Could not read '{p}'!")
             return None
        templates.append(img)
        
    return templates

def find_and_click(img_bgr, template, monitor, state_name, click=True):
    """
    Generic function to find a template. 
    If click=True, clicks it.
    Returns True if found (and clicked), False otherwise.
    """
    template_h, template_w = template.shape[:2]
    
    res = cv2.matchTemplate(img_bgr, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    
    if max_val >= CONFIDENCE_THRESHOLD:
        if click:
            top_left = max_loc
            center_x = top_left[0] + template_w // 2
            center_y = top_left[1] + template_h // 2
            
            print(f"[{state_name}] Match ({max_val:.2f}) at ({center_x}, {center_y}). Clicking...")
            
            final_x = monitor["left"] + center_x
            final_y = monitor["top"] + center_y
            
            pyautogui.moveTo(final_x, final_y)
            click_direct_input()
        return True
    return False

# Variable to track last refresh time across function calls (or pass it in)
last_refresh_time = 0

def run_state_refreshing(sct, monitor, item_template, refresh_icon_template):
    global last_refresh_time
    
    # 1. Capture Screen
    screenshot = sct.grab(monitor)
    img_np = np.array(screenshot)
    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
    
    # 2. Priority: Check if Item "Comprar" is there
    if find_and_click(img_bgr, item_template, monitor, "ITEM_FOUND"):
        print("-> Found item! Switching to BUYING state...")
        time.sleep(0.3) 
        return State.BUYING

    # 3. Background Task: Click Refresh every 1s
    if time.time() - last_refresh_time >= REFRESH_INTERVAL:
        # Check if refresh button is visible
        if find_and_click(img_bgr, refresh_icon_template, monitor, "AUTO_REFRESH"):
            # Update timer only if we actually clicked or found it? 
            # Usually update if we attempted.
            last_refresh_time = time.time()
            # print("Refreshed list.")
    
    return State.REFRESHING

def run_state_buying(sct, monitor, confirm_template):
    screenshot = sct.grab(monitor)
    img_np = np.array(screenshot)
    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
    
    if find_and_click(img_bgr, confirm_template, monitor, "BUYING"):
        print("-> Confirmed purchase! Switching to CONFIRMING state...")
        time.sleep(0.3)
        return State.CONFIRMING
    
    return State.BUYING

def run_state_confirming(sct, monitor, ok_template):
    screenshot = sct.grab(monitor)
    img_np = np.array(screenshot)
    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
    
    if find_and_click(img_bgr, ok_template, monitor, "CONFIRMING"):
        print("-> OK clicked! Transaction complete. Switching back to REFRESHING...")
        time.sleep(0.5) 
        return State.REFRESHING
    
    return State.CONFIRMING

def main():
    global current_state
    
    if not is_admin():
        print("WARNING: Script is NOT running as Administrator.")
        time.sleep(2)

    print("Auto-buyer started (High Speed + Auto Refresh).")
    print("Press 'F1' to stop.")
    
    keyboard.add_hotkey('f1', stop_script)
    keyboard.add_hotkey('esc', stop_script)
    
    templates = load_templates()
    if templates is None:
        print("Failed to load templates. Exiting.")
        return
        
    item_tmpl, confirm_tmpl, ok_tmpl, refresh_tmpl = templates

    with mss.mss() as sct:
        if len(sct.monitors) < 3:
             print("Error: Monitor 2 not found!")
             return
             
        monitor = sct.monitors[2]
        print(f"Monitoring screen area: {monitor}")
        print(f"Initial State: {current_state}")
        
        state_start_time = time.time()
        
        try:
            while running:
                new_state = current_state
                
                # Check Timeouts for non-refreshing loops
                if current_state in [State.BUYING, State.CONFIRMING]:
                     if time.time() - state_start_time > 2.0:
                         print(f"[Timeout] Resetting to REFRESHING.")
                         new_state = State.REFRESHING
                
                # Logic
                if new_state == current_state:
                    if current_state == State.REFRESHING:
                        # Pass both templates
                        new_state = run_state_refreshing(sct, monitor, item_tmpl, refresh_tmpl)
                    elif current_state == State.BUYING:
                        new_state = run_state_buying(sct, monitor, confirm_tmpl)
                    elif current_state == State.CONFIRMING:
                        new_state = run_state_confirming(sct, monitor, ok_tmpl)
                
                # Transition
                if new_state != current_state:
                    current_state = new_state
                    state_start_time = time.time()
                
                time.sleep(0.01)

        except Exception as e:
            print(f"An error occurred: {e}")
        except KeyboardInterrupt:
            print("\nStopped.")
        finally:
            keyboard.unhook_all()

if __name__ == "__main__":
    main()
