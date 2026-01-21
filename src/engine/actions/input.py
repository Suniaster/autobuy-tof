import time
import keyboard
import pyautogui
from helper.input_utils import click_direct_input, mouse_down_direct, mouse_up_direct
from .base import Action

class ClickMatchAction(Action):
    def __init__(self, params):
        self.modifiers = params.get("modifiers", "")

    def execute(self, context, executor):
        monitor = context.get('monitor')
        if hasattr(executor, 'last_match_loc') and executor.last_match_loc:
            loc = executor.last_match_loc
            w, h = executor.last_match_size
            
            center_x = loc[0] + w // 2
            center_y = loc[1] + h // 2
            
            final_x = monitor["left"] + center_x
            final_y = monitor["top"] + center_y
            
            # Modifiers
            keys_to_hold = [k.strip() for k in self.modifiers.split(",") if k.strip()]
            
            for k in keys_to_hold:
                try: keyboard.press(k)
                except: pass
            
            if keys_to_hold:
                time.sleep(0.05) # Safety delay for OS to register mods
                
            try:
                pyautogui.moveTo(final_x, final_y)
                click_direct_input()
            finally:
                # Release in reverse
                for k in reversed(keys_to_hold):
                    try: keyboard.release(k)
                    except: pass

class PressKeyAction(Action):
    def __init__(self, params):
        self.key = params.get("key")
        self.modifiers = params.get("modifiers", "")
        self.duration = float(params.get("duration", 0.05))

    def execute(self, context, executor):
        if not self.key: return

        keys_to_hold = [k.strip() for k in self.modifiers.split(",") if k.strip()]
        
        # Press Mods
        for k in keys_to_hold:
            try: keyboard.press(k)
            except: pass
        
        if keys_to_hold:
            time.sleep(0.05) 

        # TAP KEY
        duration = self.duration
        if duration < 0.01: duration = 0.01 # Safety
        
        if self.key.lower() == "left_click":
                # Special handling for mouse click
                try:
                    if duration > 0.1:
                        # Hold logic
                        mouse_down_direct()
                        time.sleep(duration)
                        mouse_up_direct()
                    else:
                        click_direct_input()
                        time.sleep(duration) 
                except Exception as e:
                    print(f"Error clicking: {e}")
        else:
            # Standard Keyboard Press
            try: 
                keyboard.press(self.key)
                time.sleep(duration)
                keyboard.release(self.key)
            except Exception as e:
                print(f"Error pressing key {self.key}: {e}")
            
        time.sleep(0.05)

        # Release Mods
        for k in reversed(keys_to_hold):
            try: keyboard.release(k)
            except: pass

class ClickPositionAction(Action):
    def __init__(self, params):
        self.x = int(params.get("x", 0))
        self.y = int(params.get("y", 0))
        self.modifiers = params.get("modifiers", "")

    def execute(self, context, executor):
        monitor = context.get('monitor')
        if not monitor: return

        # Calculate absolute position
        # Assuming params x,y are coordinates within the window captured (client rect)
        # or relative to monitor top-left.
        # Based on OCR logic, we work with screen coordinates.
        # If the user provides x,y, are they relative to the game window or screen?
        # Usually relative to game window is preferred if the window moves.
        # But 'monitor' here describes the client rect of the window in screen coords.
        
        final_x = monitor["left"] + self.x
        final_y = monitor["top"] + self.y
        
        keys_to_hold = [k.strip() for k in self.modifiers.split(",") if k.strip()]
        
        for k in keys_to_hold:
            try: keyboard.press(k)
            except: pass
        
        if keys_to_hold:
            time.sleep(0.05)
            
        try:
            pyautogui.moveTo(final_x, final_y)
            click_direct_input()
        finally:
            for k in reversed(keys_to_hold):
                try: keyboard.release(k)
                except: pass

class WaitAction(Action):
    def __init__(self, params):
        self.duration = params.get("duration", 0.5)

    def execute(self, context, executor):
        time.sleep(self.duration)
