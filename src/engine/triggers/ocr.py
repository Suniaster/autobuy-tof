import easyocr
import numpy as np
import cv2
import re
from .base import Trigger

class OCRWatchTrigger(Trigger):
    def __init__(self, params):
        self.region = params.get("region") # [x, y, w, h]
        self.condition = params.get("condition", ">")
        self.target_val = float(params.get("value", 0))

    def check(self, context, executor):
        sct = context.get('sct')
        if not self.region or not sct: return False
        
        # Initialize Reader Lazily via executor
        if executor.ocr_reader is None:
            print("Initializing EasyOCR (this may take a moment)...")
            executor.ocr_reader = easyocr.Reader(['en'], gpu=True) 
        
        # Capture Region (Absolute Coords)
        monitor = {"top": self.region[1], "left": self.region[0], "width": self.region[2], "height": self.region[3]}
        sct_img = sct.grab(monitor)
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
