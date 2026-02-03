import time
import mss
import os
import easyocr

from .model import Graph
from .utils import capture_and_scale
from .triggers import check_trigger
from .actions import execute_action

class GraphExecutor:
    def __init__(self, graph: Graph, hwnd, templates_dir: str, on_state_change=None, ocr_reader=None):
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
        self.ocr_reader = ocr_reader # Persistent reader if provided
        
        # Runtime state for edges: { edge_id: {"match_count": 0, "current_triggers": 0} }
        self.edge_states = {} 
            
        # Action context state
        self.last_match_loc = None
        self.last_match_size = None
        self.last_matched_template_name = None

    def load_template(self, filename):
        if not filename: return None
        if filename in self.template_cache:
            return self.template_cache[filename]
        
        path = os.path.join(self.templates_dir, filename)
        if not os.path.exists(path):
            print(f"Warning: Template {path} not found")
            return None
        
        # Load using cv2 from utils (or import cv2 here if needed, but we don't import cv2 at top to keep clean)
        # Actually load_template needs cv2. Let's import cv2.
        import cv2
        img = cv2.imread(path)
        if img is not None:
            self.template_cache[filename] = img
        return img

    def run(self):
        self.running = True
        print(f"Starting Graph Executor. Start Node: {self.current_vertex.name if self.current_vertex else 'None'}")
        print("DEBUG: Executor loaded with Modulo Activation Logic (v2).")
        
        if not self.current_vertex:
            print("Error: No start vertex found!")
            return

        if self.on_state_change and self.current_vertex:
            self.on_state_change(self.current_vertex.id)

        with mss.mss() as sct:
            while self.running:
                # Check background mode setting from graph
                bg_mode = self.graph.settings.get("background_mode", False)
                
                if self.paused:
                    time.sleep(0.1)
                    continue

                # Capture Screen
                img, sx, sy, monitor = capture_and_scale(sct, self.hwnd, self.mode, background_mode=bg_mode)
                if img is None:
                    time.sleep(0.1)
                    continue

                avg_scale = (sx + sy) / 2.0
                
                # Context for triggers/actions
                context = {
                    'img': img,
                    'scale': avg_scale,
                    'sct': sct,
                    'monitor': monitor
                }

                # Check outgoing edges
                edges = self.graph.get_outgoing_edges(self.current_vertex.id)
                # Sort by Priority (Higher First)
                edges.sort(key=lambda e: e.priority, reverse=True)
                
                transition_happened = False

                for edge in edges:
                    # Initialize state for this edge if not present
                    if edge.id not in self.edge_states:
                        self.edge_states[edge.id] = {"match_count": 0, "current_triggers": 0}
                    
                    e_state = self.edge_states[edge.id]

                    # Check max triggers (Execution Limit)
                    if edge.max_triggers != -1 and e_state["current_triggers"] >= edge.max_triggers:
                        continue
                        
                    if check_trigger(edge.trigger, context, self):
                        e_state["match_count"] += 1
                        # Debug Print for increments
                        # print(f"   -> Edge {edge.id[:4]}.. Match! Count: {e_state['match_count']} (Req: {max(edge.activation_threshold, 1)})")
                        
                        # Check Activation Threshold (Modulo Logic)
                        threshold = max(edge.activation_threshold, 1) # Default 1 if <= 0
                        if (e_state["match_count"] % threshold) != 0:
                            continue
                            
                        # Threshold Met (Modulo 0)
                        e_state["current_triggers"] += 1
                        # print(f"[{self.current_vertex.name}] Triggered Edge to -> {edge.target_id} (Matches: {e_state['match_count']}, Executions: {e_state['current_triggers']})")
                        
                        # Execute Action
                        if edge.action:
                             # Wait Before
                             wb = edge.action.params.get("wait_before", 0)
                             if wb > 0:
                                 time.sleep(wb)

                             execute_action(edge.action, context, self)

                             # Wait After
                             wa = edge.action.params.get("wait_after", 0)
                             if wa > 0:
                                 time.sleep(wa)
                        
                        # Transition (only if target exists)
                        if not edge.target_id:
                            continue

                        next_v = self.graph.vertices.get(edge.target_id)
                        if next_v:
                            self.current_vertex = next_v
                            transition_happened = True
                            self.last_transition_time = time.time()
                            
                            if self.on_state_change:
                                self.on_state_change(self.current_vertex.id)
                            break
                
                if not transition_happened:
                    # Stuck Check
                    if time.time() - self.last_transition_time > 5.0:
                        found_state = self.scan_for_state(img, avg_scale)
                        if found_state:
                             print(f"-> Recovered to state: {found_state.name}")
                             self.current_vertex = found_state
                             self.last_transition_time = time.time()
                             if self.on_state_change:
                                self.on_state_change(self.current_vertex.id)
                    
                    # Idle sleep (reduced from 0.5 for responsiveness)
                    time.sleep(0.01)

    def scan_for_state(self, img, scale):
        # Imports needed for scan
        from .utils import match_template_multiscale
        
        for v in self.graph.vertices.values():
            if v.template and v.id != self.current_vertex.id:
                 tmpl = self.load_template(v.template)
                 if tmpl is None: continue
                 
                 val, _, _, _ = match_template_multiscale(img, tmpl, scale)
                 if val >= 0.85: # High confidence for recovery
                     return v
        return None

    def stop(self):
        self.running = False
