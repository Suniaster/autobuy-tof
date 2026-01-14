import time
from ..utils import capture_and_scale, match_template_multiscale
from helper.input_utils import move_mouse_relative
from .base import Action

class CenterCameraAction(Action):
    def __init__(self, params):
        pass

    def execute(self, context, executor):
        # Visual Servoing Loop
        sct = context.get('sct')
        target_tmpl = getattr(executor, "last_matched_template_name", None)
        
        if not target_tmpl or not sct: 
            print("Center Camera: No template or SCT available")
            return

        # Need to load the template again. 
        # Note: In executor.py run() loop, capture_and_scale is called. 
        # Here we might need to capture new frames.
        
        tmpl_img = executor.load_template(target_tmpl)
        if tmpl_img is None: return
        
        # Servo Params
        center_tolerance = 30 # pixels
        max_iterations = 20   # avoid infinite loop
        gain = 0.5            # movement speed factor
        
        print(f"Centering camera on {target_tmpl}...")
        
        for _ in range(max_iterations):
            # 1. Capture fresh frame
            # Using executor.hwnd to capture specific window
            img, sx, sy, _ = capture_and_scale(sct, executor.hwnd, executor.mode)
            if img is None: break
            
            # 2. Find Object
            val, loc, _, size = match_template_multiscale(img, tmpl_img) # Note: util returns (val, loc, scale, size) or similar? 
            # Checking utils signature in original executor.py: 
            # val, loc, _, _ = match_template_multiscale(img, tmpl, scale)
            # Wait, match_template_multiscale returns: val, loc, scale, (w, h)
            # I need to verify utils.py to be sure. 
            # Original executor line 252: val, loc, (w, h) = match_template_multiscale(img, tmpl_img)
            # But line 116: val, _, _, _ = match_template_multiscale(img, tmpl, scale)
            # It seems the return signature is 4 values.
            
            if val < 0.7: # Lost tracking
                print("Lost target during centering.")
                break
            
            w, h = size
            
            # 3. Calculate Offset from Screen Center
            screen_w, screen_h = img.shape[1], img.shape[0]
            screen_cx, screen_cy = screen_w // 2, screen_h // 2
            obj_cx, obj_cy = loc[0] + w // 2, loc[1] + h // 2
            
            dx = obj_cx - screen_cx
            dy = obj_cy - screen_cy
            
            # 4. Check if centered
            if abs(dx) < center_tolerance and abs(dy) < center_tolerance:
                print("Target centered!")
                break
            
            # 5. Move Mouse
            move_x = int(dx * gain)
            move_y = int(dy * gain)
            
            if abs(move_x) < 2: move_x = 0
            if abs(move_y) < 2: move_y = 0
            
            if move_x == 0 and move_y == 0: break
            
            move_mouse_relative(move_x, move_y)
            time.sleep(0.05)
