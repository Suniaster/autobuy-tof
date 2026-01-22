
import cv2
import numpy as np
from .base import Trigger

class ColorMatchTrigger(Trigger):
    def __init__(self, params):
        self.target_x = int(params.get("x", 0))
        self.target_y = int(params.get("y", 0))
        self.target_rgb = params.get("rgb", [0, 0, 0]) # [r, g, b]
        self.tolerance = int(params.get("tolerance", 10))
        self.params = params

    def check(self, context, executor):
        # We need the screen content
        # If executor is running, context usually contains 'img' (full screenshot or cropped?)
        # context['img'] is typically BGR in current implementation
        
        # We need absolute coordinates on the image
        img = context.get('img')
        monitor = context.get('monitor')
        
        if img is None or monitor is None:
            return False
            
        # Coordinates are relative to Client Area (monitor['left'], monitor['top'])
        # if the user picked them there.
        # But we need to handle Resolution Scaling first.
        
        res_w = self.params.get("resolution_width", 0)
        res_h = self.params.get("resolution_height", 0)
        
        current_w = monitor["width"]
        current_h = monitor["height"]
        
        local_x = self.target_x
        local_y = self.target_y
        
        if res_w > 0 and res_h > 0:
            scale_x = current_w / res_w
            scale_y = current_h / res_h
            local_x = int(local_x * scale_x)
            local_y = int(local_y * scale_y)
            
        # Ensure bounds
        h, w = img.shape[:2]
        if 0 <= local_x < w and 0 <= local_y < h:
            # Image is BGR (OpenCV default)
            pixel = img[local_y, local_x]
            b, g, r = int(pixel[0]), int(pixel[1]), int(pixel[2])
            
            tr, tg, tb = self.target_rgb
            
            # Distance
            dist = ((r - tr)**2 + (g - tg)**2 + (b - tb)**2) ** 0.5
            
            # DEBUG
            # print(f"[ColorMatch] Check ({local_x}, {local_y}) | Target: ({tr},{tg},{tb}) | Found: ({r},{g},{b}) | Dist: {dist:.2f} | Tol: {self.tolerance}")

            if dist <= self.tolerance:
                print(f"[ColorMatch] MATCHED! ({local_x}, {local_y})")
                return True
            else:
                # Optional: print only if reasonably close to avoid spam, or print always for deep debug
                if dist < 50: # Only print if somewhat close, to avoid spamming console
                     print(f"[ColorMatch] Close... Dist: {dist:.2f} (Tol: {self.tolerance}) at ({local_x}, {local_y}) Found: ({r},{g},{b}) Target: ({tr},{tg},{tb})")
                
        else:
            print(f"[ColorMatch] Out of bounds: ({local_x}, {local_y}) in image of size {w}x{h}")
            
        return False
