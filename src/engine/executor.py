import time
import cv2
import mss
import pyautogui
import os
import keyboard
from .model import Graph, Vertex, Edge
from .utils import capture_and_scale, match_template_multiscale
from helper.input_utils import click_direct_input

class GraphExecutor:
    def __init__(self, graph: Graph, hwnd, templates_dir: str, on_state_change=None):
        self.graph = graph
        self.hwnd = hwnd
        self.templates_dir = templates_dir
        self.on_state_change = on_state_change
        self.current_vertex = graph.get_start_vertex()
        self.running = False
        self.paused = False
        self.mode = 1 # 1: Fast, 2: Slow
        self.template_cache = {}
        self.last_transition_time = time.time()

    def load_template(self, filename):
        if filename in self.template_cache:
            return self.template_cache[filename]
        
        path = os.path.join(self.templates_dir, filename)
        if not os.path.exists(path):
            print(f"Warning: Template {path} not found")
            return None
        
        img = cv2.imread(path)
        if img is not None:
            self.template_cache[filename] = img
        return img

    def run(self):
        self.running = True
        print(f"Starting Graph Executor. Start Node: {self.current_vertex.name if self.current_vertex else 'None'}")
        
        if not self.current_vertex:
            print("Error: No start vertex found!")
            return

        if self.on_state_change and self.current_vertex:
            self.on_state_change(self.current_vertex.id)

        with mss.mss() as sct:
            while self.running:
                if self.paused:
                    time.sleep(0.1)
                    continue

                # Capture Screen
                img, sx, sy, monitor = capture_and_scale(sct, self.hwnd, self.mode)
                if img is None:
                    time.sleep(0.1)
                    continue

                avg_scale = (sx + sy) / 2.0
                
                # Check outgoing edges
                edges = self.graph.get_outgoing_edges(self.current_vertex.id)
                # Sort by Priority (Higher First)
                edges.sort(key=lambda e: e.priority, reverse=True)
                
                transition_happened = False

                for edge in edges:
                    if self.check_trigger(edge.trigger, img, avg_scale):
                        print(f"[{self.current_vertex.name}] Triggered Edge to -> {edge.target_id}")
                        
                        # Execute Action
                        if edge.action:
                            self.execute_action(edge.action, monitor, sct)
                        
                        # Transition
                        next_v = self.graph.vertices.get(edge.target_id)
                        if next_v:
                            self.current_vertex = next_v
                            transition_happened = True
                            self.last_transition_time = time.time()
                            
                            if self.on_state_change:
                                self.on_state_change(self.current_vertex.id)
                                
                            time.sleep(0.2) # Debounce
                            break
                
                if not transition_happened:
                    # Stuck Check
                    if time.time() - self.last_transition_time > 5.0:
                        # Attempt Recovery
                        print(f"[{self.current_vertex.name}] Stuck? Scanning for other states...")
                        found_state = self.scan_for_state(img, avg_scale)
                        if found_state:
                             print(f"-> Recovered to state: {found_state.name}")
                             self.current_vertex = found_state
                             self.last_transition_time = time.time()
                             if self.on_state_change:
                                self.on_state_change(self.current_vertex.id)
                    time.sleep(0.1)

    def scan_for_state(self, img, scale):
        for v in self.graph.vertices.values():
            if v.template and v.id != self.current_vertex.id:
                 tmpl = self.load_template(v.template)
                 if tmpl is None: continue
                 
                 val, _, _, _ = match_template_multiscale(img, tmpl, scale)
                 if val >= 0.85: # High confidence for recovery
                     return v
        return None

    def check_trigger(self, trigger, img, scale):
        if trigger.type == "template_match":
            template_name = trigger.params.get("template")
            threshold = trigger.params.get("threshold", 0.8)
            invert = trigger.params.get("invert", False)
            
            tmpl = self.load_template(template_name)
            if tmpl is None: return False
            
            val, loc, _, _ = match_template_multiscale(img, tmpl, scale)
            
            found = (val >= threshold)
            
            if found:
                # Store match info
                self.last_match_loc = loc
                self.last_match_size = (self.template_cache[template_name].shape[1], self.template_cache[template_name].shape[0])
            
            if invert:
                return not found
            else:
                return found
                
        elif trigger.type == "immediate":
            return True
                
        elif trigger.type == "wait":
             # TODO: Implement time-based triggers
             pass
             
        return False

    def execute_action(self, action, monitor, sct=None):
        if action.type == "click_match":
            if hasattr(self, 'last_match_loc') and self.last_match_loc:
                loc = self.last_match_loc
                w, h = self.last_match_size
                
                center_x = loc[0] + w // 2
                center_y = loc[1] + h // 2
                
                final_x = monitor["left"] + center_x
                final_y = monitor["top"] + center_y
                
                # Modifiers
                mods = action.params.get("modifiers", "")
                keys_to_hold = [k.strip() for k in mods.split(",") if k.strip()]
                
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

        elif action.type == "center_camera":
             # Visual Servoing Loop
             target_tmpl = getattr(self, "last_matched_template_name", None)
             if not target_tmpl or not sct: 
                 print("Center Camera: No template or SCT available")
                 return

             tmpl_img = load_template(self.assets_dir, target_tmpl)
             if tmpl_img is None: return
             
             # Servo Params
             center_tolerance = 30 # pixels
             max_iterations = 20   # avoid infinite loop
             gain = 0.5            # movement speed factor
             
             print(f"Centering camera on {target_tmpl}...")
             
             for _ in range(max_iterations):
                 # 1. Capture fresh frame
                 img, sx, sy, _ = capture_and_scale(sct, self.hwnd, self.mode)
                 if img is None: break
                 
                 # 2. Find Object
                 val, loc, (w, h) = match_template_multiscale(img, tmpl_img)
                 if val < 0.7: # Lost tracking
                     print("Lost target during centering.")
                     break
                 
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

        elif action.type == "press_key":
            key = action.params.get("key")
            if key:
                mods = action.params.get("modifiers", "")
                keys_to_hold = [k.strip() for k in mods.split(",") if k.strip()]
                
                # Press Mods
                for k in keys_to_hold:
                    try: keyboard.press(k)
                    except: pass
                
                if keys_to_hold:
                    time.sleep(0.05) 

                # TAP KEY
                duration = float(action.params.get("duration", 0.05))
                if duration < 0.01: duration = 0.01 # Safety
                
                if key.lower() == "left_click":
                     # Special handling for mouse click
                     try:
                        click_direct_input()
                        time.sleep(duration) 
                     except Exception as e:
                        print(f"Error clicking: {e}")
                else:
                    # Standard Keyboard Press
                    try: 
                        keyboard.press(key)
                        time.sleep(duration)
                        keyboard.release(key)
                    except Exception as e:
                        print(f"Error pressing key {key}: {e}")
                    
                time.sleep(0.05)

                # Release Mods
                for k in reversed(keys_to_hold):
                    try: keyboard.release(k)
                    except: pass
                
        elif action.type == "wait":
            duration = action.params.get("duration", 0.5)
            time.sleep(duration)

    def stop(self):
        self.running = False
