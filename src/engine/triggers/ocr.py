import easyocr
import numpy as np
import cv2
import re
from .base import Trigger

class OCRWatchTrigger(Trigger):
    def __init__(self, params):
        self.region = params.get("region") # [x, y, w, h]
        self.params = params
        self.condition = params.get("condition", ">")
        self.target_val = float(params.get("value", 0))

    def check(self, context, executor):
        sct = context.get('sct')
        if not self.region or not sct: return False
        
        # Initialize Reader Lazily via executor
        if executor.ocr_reader is None:
            print("Initializing EasyOCR (this may take a moment)...")
            executor.ocr_reader = easyocr.Reader(['en'], gpu=True) 
        
        # Capture Region (Absolute Coords or Relative)
        monitor = context.get('monitor')
        if not monitor: return False

        res_w = self.params.get("resolution_width", 0)
        res_h = self.params.get("resolution_height", 0)

        region_x, region_y, region_w, region_h = self.region

        final_monitor = {}

        if res_w > 0 and res_h > 0:
             # New Relative Logic with Scaling
             current_w = monitor["width"]
             current_h = monitor["height"]
             
             scale_x = current_w / res_w
             scale_y = current_h / res_h
             
             t_x = int(region_x * scale_x)
             t_y = int(region_y * scale_y)
             t_w = int(region_w * scale_x)
             t_h = int(region_h * scale_y)
             
             final_monitor = {
                 "top": monitor["top"] + t_y,
                 "left": monitor["left"] + t_x,
                 "width": t_w,
                 "height": t_h
             }
        else:
             # Legacy Absolute Logic
             final_monitor = {
                 "top": region_y,
                 "left": region_x,
                 "width": region_w,
                 "height": region_h
             }
        
        # Clip to screen if needed, but MSS handles basic clipping usually.
        # Ensure width/height > 0
        if final_monitor["width"] <= 0 or final_monitor["height"] <= 0: return False

        # If we have a captured image in context (Background Mode or Fast Mode), use it to crop
        img_np = None
        
        if "img" in context and context["img"] is not None:
            # Calculate offset
            parent_monitor = context.get('monitor')
            if parent_monitor:
                offset_x = final_monitor["left"] - parent_monitor["left"]
                offset_y = final_monitor["top"] - parent_monitor["top"]
                
                # Check bounds
                h, w = context["img"].shape[:2]
                
                x1 = int(offset_x)
                y1 = int(offset_y)
                x2 = int(x1 + final_monitor["width"])
                y2 = int(y1 + final_monitor["height"])
                
                # Clamp
                x1 = max(0, x1); y1 = max(0, y1)
                x2 = min(w, x2); y2 = min(h, y2)
                
                if x2 > x1 and y2 > y1:
                    img_np = context["img"][y1:y2, x1:x2]
                    img_np = cv2.cvtColor(img_np, cv2.COLOR_BGR2BGRA)

        if img_np is None:
             # Fallback to MSS
             sct_img = sct.grab(final_monitor)
             img_np = np.array(sct_img)

        img_gray = cv2.cvtColor(img_np, cv2.COLOR_BGRA2GRAY)
        
        try:
            # Enhanced Preprocessing
            # 1. Upscale (Linear or Cubic) to help with small text
            scale_factor = 3
            width = int(img_gray.shape[1] * scale_factor)
            height = int(img_gray.shape[0] * scale_factor)
            img_large = cv2.resize(img_gray, (width, height), interpolation=cv2.INTER_CUBIC)
            
            # 2. Thresholding (Otsu's binarization)
            _, img_thresh = cv2.threshold(img_large, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
            # allowlist for numbers
            results = executor.ocr_reader.readtext(img_thresh, allowlist='0123456789.-', detail=0)
            
            # Results is a list of strings found. Join them or check first valid number
            text = " ".join(results)
            print(f"[OCR CHECK] Raw: '{text}' | Region: {self.region}")
            
            # Extract numbers
            nums = re.findall(r"[-+]?\d*\.\d+|\d+", text)
            if nums:
                val = float(nums[0])
                print(f"[OCR CHECK] Value: {val} (Target: {self.target_val}, Condition: {self.condition})")
                
                if self.condition == ">": return val > self.target_val
                elif self.condition == "<": return val < self.target_val
                elif self.condition == "=": return abs(val - self.target_val) < 0.001
                elif self.condition == ">=": return val >= self.target_val
                elif self.condition == "<=": return val <= self.target_val
                elif self.condition == "!=": return abs(val - self.target_val) > 0.001

        except Exception as e:
            print(f"OCR Process Error: {e}")
            
        return False
