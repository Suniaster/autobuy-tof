import tkinter as tk
import customtkinter as ctk

from tkinter import filedialog, messagebox, simpledialog
import math
import json
import os
import uuid
import win32clipboard
import threading
import time
import win32gui
import keyboard
from io import BytesIO
import cv2
import numpy as np
from PIL import Image
from .model import Graph, Vertex, Edge, Trigger, Action
from .executor import GraphExecutor
from .selectors import RegionSelector, PointSelector
import mss
import zipfile


# Configuration
GAME_TITLE_KEYWORD = "Tower of Fantasy"

# --- 2025 Design System ---
THEME = {
    "bg_main": "#0f1117",       # Deepest Void
    "bg_canvas": "#0a0c12",     # Canvas BG
    "node_bg": "#17191f",       # Node Surface
    "node_border": "#2a2f38",   # Subtle Border
    "accent_cyan": "#06b6d4",   # Active / Focus
    "accent_purple": "#a78bfa", # Special
    "accent_emerald": "#34d399",# Success / Start
    "accent_rose": "#fb7185",   # Error / Delete
    "text_main": "#f3f4f6",     # Primary Text
    "text_sub": "#9ca3af",      # Secondary Text
    "grid": "#1e2128"           # Grid Lines
}

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class GraphEditor(ctk.CTk):
    def __init__(self, assets_dir):
        super().__init__()
        self.title("Autobuyer Studio 2026")
        self.geometry("1400x900")
        
        # Configure Main Window
        self.configure(fg_color=THEME["bg_main"])
        
        self.assets_dir = assets_dir
        if not os.path.exists(self.assets_dir):
            os.makedirs(self.assets_dir)

        self.graph = Graph()
        self.node_width = 180
        self.node_height = 80
        # self.node_radius (deprecated for rounded rect width/height)
        
        self.selected_item = None # (type, id)
        self.drag_data = {"x": 0, "y": 0, "item": None, "pan_start": None}
        
        # Canvas Transform
        self.offset_x = 0
        self.offset_y = 0
        self.scale = 1.0
        
        self.mode = "SELECT" 
        
        # Execution State
        self.executor = None
        self.executor_thread = None
        self.active_node_id = None
        self.is_running = False
        self.cached_ocr_reader = None
        self.game_hwnd = None # Explicitly selected window

        # Interaction State
        self.connecting_point = None 
        self.connecting_node = None # Legacy? Keep for now to be safe, but we might repurpose
        self.creation_start = None # (type, id/coords)
        self.creating_edge = False
        self.edge_drag = None # (edge_id, "source"|"target")
        
        # UI Layout
        self.create_menu()
        self.create_canvas()

    def create_menu(self):
        menubar = tk.Menu(self)
        
        # File Menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New", command=self.new_graph)
        file_menu.add_command(label="Open", command=self.load_graph)
        file_menu.add_command(label="Save", command=self.save_graph)
        file_menu.add_command(label="Export", command=self.export_to_zip)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Target Menu
        target_menu = tk.Menu(menubar, tearoff=0)
        target_menu.add_command(label="Select Game Window...", command=self.select_target_window)
        menubar.add_cascade(label="Target", menu=target_menu)
        
        self.config(menu=menubar)

    def create_toolbar(self):
        # Floating Toolbar (Top Center)
        toolbar = ctk.CTkFrame(self, fg_color=THEME["node_bg"], corner_radius=20, border_width=1, border_color=THEME["node_border"])
        toolbar.place(relx=0.5, rely=0.03, anchor="n")
        
        # Helper to create icon buttons
        def add_btn(text, cmd, color=THEME["node_bg"], hover=THEME["node_border"], text_col=THEME["text_main"]):
             ctk.CTkButton(toolbar, text=text, command=cmd, width=40, height=40, 
                           fg_color=color, hover_color=hover, text_color=text_col,
                           corner_radius=10, font=("Arial", 16)).pack(side=tk.LEFT, padx=5, pady=5)

        self.btn_run = ctk.CTkButton(toolbar, text="▶", command=self.toggle_run, width=40, height=40, 
                                     fg_color=THEME["accent_emerald"], hover_color=THEME["node_border"], 
                                     corner_radius=10, font=("Arial", 16))
        self.btn_run.pack(side=tk.LEFT, padx=(10, 5), pady=5)

        add_btn("↖", lambda: self.set_mode("SELECT"))
        add_btn("+", lambda: self.set_mode("ADD_NODE"))
        add_btn("→", lambda: self.set_mode("CONNECT"))
        add_btn("🗑", lambda: self.set_mode("DELETE"), text_col=THEME["accent_rose"])
        
        self.mode_label = ctk.CTkLabel(toolbar, text="SELECT", text_color=THEME["accent_cyan"], font=("Segoe UI", 12, "bold"))
        self.mode_label.pack(side=tk.LEFT, padx=(10, 15), pady=5)
        
        # Status Bar (Bottom)
        self.status_bar = ctk.CTkFrame(self, height=30, fg_color=THEME["bg_main"])
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_lbl = ctk.CTkLabel(self.status_bar, text="Ready", text_color=THEME["text_sub"], font=("Segoe UI", 11))
        self.status_lbl.pack(side=tk.RIGHT, padx=20)
        
        # Version/Info
        ctk.CTkLabel(self.status_bar, text="Autobuyer Engine v2.0", text_color=THEME["node_border"], font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=20)

    # --- UI Updates ---
    def update_status(self, text):
        self.status_lbl.configure(text=text)

    # Updated to resolve_game_window to handle multiple instances
    def resolve_game_window(self, force_ask=False):
        from .utils import find_all_game_windows
        
        matches = find_all_game_windows(GAME_TITLE_KEYWORD)
        
        if not matches:
             return None
        
        # If user explicitly asks, show dialog even if only 1 match
        if len(matches) == 1 and not force_ask:
            return matches[0][0] # Return HWND
        
        # Multiple windows found OR forced ask
        return self.ask_window_selection_dialog(matches)

    def select_target_window(self):
        hwnd = self.resolve_game_window(force_ask=True)
        if hwnd:
            self.game_hwnd = hwnd
            match_found = False
            # Try to get title for confirmation
            try:
                title = win32gui.GetWindowText(hwnd)
                messagebox.showinfo("Target Selected", f"Target set to:\n{title}\n(HWND: {hwnd})")
            except:
                messagebox.showinfo("Target Selected", f"Target set to HWND: {hwnd}")
        else:
            # If nothing returned (e.g. cancel or no windows), clear? or keep old?
            # If no windows found loops back out, but cancel returns None
            pass

    def ask_window_selection_dialog(self, matches):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Select Game Window")
        dialog.geometry("500x400")
        dialog.transient(self)
        dialog.grab_set() # Modal
        
        selected_hwnd = tk.StringVar(value="")
        
        ctk.CTkLabel(dialog, text="Multiple game windows found. Please select one:", font=("Segoe UI", 14, "bold")).pack(pady=10)
        
        scroll = ctk.CTkScrollableFrame(dialog, width=450, height=250)
        scroll.pack(pady=10, padx=10)
        
        def on_select(hwnd):
            selected_hwnd.set(str(hwnd))
            dialog.destroy()
            
        for i, (hwnd, title, rect) in enumerate(matches):
            btn_text = f"Window {i+1}: {title}\nres: {rect['width']}x{rect['height']} pos: ({rect['left']},{rect['top']})"
            ctk.CTkButton(scroll, text=btn_text, command=lambda h=hwnd: on_select(h), 
                          anchor="w", fg_color=THEME["node_bg"], hover_color=THEME["node_border"]).pack(fill="x", pady=2)
            
        # Cancel handler
        def on_cancel():
            dialog.destroy()
        
        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        
        self.wait_window(dialog)
        
        res = selected_hwnd.get()
        if res:
            return int(res)
        return None

    def toggle_run(self):
        if self.is_running:
            # STOP
            if self.executor:
                self.executor.stop()
            self.is_running = False
            self.btn_run.configure(text="▶", fg_color=THEME["accent_emerald"])
            self.update_status("Stopped")
            self.active_node_id = None
            if self.executor:
                self.cached_ocr_reader = self.executor.ocr_reader
            self.refresh_canvas()
            
            # Unhook F1
            try:
                keyboard.remove_hotkey('f1')
            except: pass
            
        else:
            # START
            hwnd = None
            if self.game_hwnd and win32gui.IsWindow(self.game_hwnd):
                # Verify it's still visible/valid?
                hwnd = self.game_hwnd
            else:
                hwnd = self.resolve_game_window()
                
            if not hwnd:
                messagebox.showerror("Error", f"Game window '{GAME_TITLE_KEYWORD}' not found!")
                return
                
            self.game_hwnd = hwnd # Remember for session

            self.is_running = True
            self.btn_run.configure(text="⏹", fg_color=THEME["accent_rose"])
            self.update_status("Starting Engine...")
            
            self.update_status("Starting Engine...")
            
            self.executor = GraphExecutor(self.graph, hwnd, self.assets_dir, 
                                          on_state_change=self.on_executor_state_change,
                                          ocr_reader=self.cached_ocr_reader)
            
            # Hook F1
            keyboard.add_hotkey('f1', self.toggle_pause)
            
            # Start Thread
            self.executor_thread = threading.Thread(target=self.run_executor_thread, daemon=True)
            self.executor_thread.start()

    def toggle_pause(self):
        if self.executor:
            self.executor.paused = not self.executor.paused
            state = "PAUSED" if self.executor.paused else "RUNNING"
            # Update UI from thread safe way?
            # We can update button text or Title
            print(f"[{state}]")
            # We can't safely touch Tkinter directly from hotkey thread sometimes, 
            # but usually it's fine for simple config updates or we use after.
            # Let's change window title or something visual.
            self.after(0, lambda: self.update_pause_ui(self.executor.paused))

    def update_pause_ui(self, is_paused):
        if is_paused:
            self.btn_run.configure(text="⏸", fg_color=THEME["accent_cyan"])
            self.update_status("Paused")
        else:
            self.btn_run.configure(text="⏹", fg_color=THEME["accent_rose"])
            self.update_status("Running...")


    def run_executor_thread(self):
        try:
            self.executor.run()
        except Exception as e:
            print(f"Executor Error: {e}")
            self.is_running = False
            self.after(0, lambda: messagebox.showerror("Error", f"Runtime Error: {e}"))
            self.after(0, lambda: messagebox.showerror("Error", f"Runtime Error: {e}"))
            self.after(0, lambda: self.btn_run.configure(text="▶", fg_color=THEME["accent_emerald"]))
        finally:
             if self.executor:
                 self.cached_ocr_reader = self.executor.ocr_reader

    # ... [Rest of Canvas/Drawing Logic, slightly modified to highlight active] ...

    def set_mode(self, mode):
        self.mode = mode
        self.mode_label.configure(text=mode)
        self.connecting_node = None
        self.canvas.delete("temp_line")
        self.canvas.config(cursor="arrow")
        if mode == "ADD_NODE": self.canvas.config(cursor="cross")
        elif mode == "CONNECT": self.canvas.config(cursor="hand2")
        elif mode == "DELETE": self.canvas.config(cursor="X_cursor")

    def create_canvas(self):
        self.canvas = tk.Canvas(self, bg=THEME["bg_canvas"], highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Interactions
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        
        # Right Click (Context) 
        self.canvas.bind("<Button-3>", self.on_right_click)
        
        # Middle Click (Pan) or Space+Drag logic
        self.canvas.bind("<ButtonPress-2>", self.start_pan)
        self.canvas.bind("<B2-Motion>", self.continue_pan)
        self.canvas.bind("<ButtonRelease-2>", self.end_pan)
        # Windows often treats wheel click as Button-2? Check.
        
        # Zoom
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        
        # Cancellation
        self.bind("<Escape>", self.on_cancel)
        self.bind("<Delete>", self.on_cancel)

    def on_cancel(self, event):
        # Abort Drag/Creation
        self.creating_edge = False
        self.creation_start = None
        self.edge_drag = None
        self.drag_data["item"] = None
        self.connecting_node = None
        self.connecting_point = None
        
        self.canvas.delete("temp_line")
        self.refresh_canvas()
        self.set_mode("SELECT")

    # --- Transform Helpers ---
    def world_to_screen(self, wx, wy):
        sx = (wx * self.scale) + self.offset_x
        sy = (wy * self.scale) + self.offset_y
        return sx, sy

    def screen_to_world(self, sx, sy):
        wx = (sx - self.offset_x) / self.scale
        wy = (sy - self.offset_y) / self.scale
        return wx, wy

    # --- Pan & Zoom ---
    def start_pan(self, event):
        self.canvas.config(cursor="fleur")
        self.drag_data["pan_start"] = (event.x, event.y)

    def continue_pan(self, event):
        if self.drag_data["pan_start"]:
            dx = event.x - self.drag_data["pan_start"][0]
            dy = event.y - self.drag_data["pan_start"][1]
            self.offset_x += dx
            self.offset_y += dy
            self.drag_data["pan_start"] = (event.x, event.y)
            self.refresh_canvas()

    def end_pan(self, event):
        self.canvas.config(cursor="arrow")
        self.drag_data["pan_start"] = None

    def on_zoom(self, event):
        # Zoom centered on mouse
        old_scale = self.scale
        if event.delta > 0:
            self.scale *= 1.1
        else:
            self.scale *= 0.9
        
        # Clamp scale
        self.scale = max(0.2, min(self.scale, 5.0))
        
        # Adjust offset to keep mouse pointed at same world coord
        # screen_x = world_x * scale + offset_x
        # offset_x = screen_x - world_x * scale
        
        wx = (event.x - self.offset_x) / old_scale
        wy = (event.y - self.offset_y) / old_scale
        
        self.offset_x = event.x - wx * self.scale
        self.offset_y = event.y - wy * self.scale
        
        self.refresh_canvas()

    def draw_grid(self):
        # Efficient Grid Drawing
        # We draw lines based on world coords visible in screen
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        
        grid_size = 50 * self.scale
        if grid_size < 10: return # Too dense
        
        # Dots logic for modern feel
        # Calculate start points
        start_x = self.offset_x % grid_size
        start_y = self.offset_y % grid_size
        
        # Draw Dots (or thin crosses)
        for i in range(int(w / grid_size) + 1):
            for j in range(int(h / grid_size) + 1):
                px = start_x + i * grid_size
                py = start_y + j * grid_size
                self.canvas.create_oval(px-1, py-1, px+1, py+1, fill=THEME["grid"], outline="")

    def new_graph(self):
        self.graph = Graph()
        self.node_coords = {}
        self.refresh_canvas()

    def save_graph(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
        if filepath:
            self.graph.save_to_file(filepath)
            with open(filepath + ".layout", "w") as f:
                json.dump(self.node_coords, f)
            messagebox.showinfo("Saved", "Graph saved!")

    def export_to_zip(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".zip", filetypes=[("ZIP Files", "*.zip")])
        if filepath:
            try:
                # 1. Collect Used Assets
                used_assets = set()
                
                # Check Vertices
                for v in self.graph.vertices.values():
                    if v.template:
                        used_assets.add(v.template)
                        
                # Check Edges
                for e in self.graph.edges:
                    if e.trigger and e.trigger.type == "template_match":
                         tmpl = e.trigger.params.get("template")
                         if tmpl:
                             used_assets.add(tmpl)

                # 2. Create Zip File
                with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    # Add Graph JSON
                    graph_json = self.graph.to_json()
                    zipf.writestr("graph.json", graph_json)
                    
                    # Add Layout JSON
                    layout_json = json.dumps(self.node_coords)
                    zipf.writestr("graph.json.layout", layout_json)
                    
                    # Add Used Assets
                    if os.path.exists(self.assets_dir):                        
                        for asset_name in used_assets:
                             abs_path = os.path.join(self.assets_dir, asset_name)
                             if os.path.exists(abs_path) and os.path.isfile(abs_path):
                                 zip_path = os.path.join("assets", "autobuyer", asset_name)
                                 zipf.write(abs_path, arcname=zip_path)
                                 
                messagebox.showinfo("Exported", f"Successfully exported to {filepath}")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))

    def load_graph(self):
        filepath = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if filepath:
            try:
                self.graph = Graph.load_from_file(filepath)
                if os.path.exists(filepath + ".layout"):
                    with open(filepath + ".layout", "r") as f:
                        self.node_coords = json.load(f)
                else:
                    self.auto_layout()
                self.refresh_canvas()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def auto_layout(self):
        i = 0
        for v_id in self.graph.vertices:
            self.node_coords[v_id] = (150 + (i % 4) * 200, 100 + (i // 4) * 200)
            i += 1

    def refresh_canvas(self):
        self.canvas.delete("all")
        self.draw_grid() # Draw grid first
        
        for edge in self.graph.edges:
            p1 = self.node_coords.get(edge.source_id) if edge.source_id else None
            p2 = self.node_coords.get(edge.target_id) if edge.target_id else None
            self.draw_edge(p1, p2, edge)
        for v_id, vertex in self.graph.vertices.items():
            x, y = self.node_coords.get(v_id, (100, 100))
            self.draw_node(x, y, vertex)
        for v_id, vertex in self.graph.vertices.items():
            x, y = self.node_coords.get(v_id, (100, 100))
            self.draw_node(x, y, vertex)

    def draw_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        points = [x1+radius, y1,
                  x1+radius, y1,
                  x2-radius, y1,
                  x2-radius, y1,
                  x2, y1,
                  x2, y1+radius,
                  x2, y1+radius,
                  x2, y2-radius,
                  x2, y2-radius,
                  x2, y2,
                  x2-radius, y2,
                  x2-radius, y2,
                  x1+radius, y2,
                  x1+radius, y2,
                  x1, y2,
                  x1, y2-radius,
                  x1, y2-radius,
                  x1, y1+radius,
                  x1, y1+radius,
                  x1, y1]
        return self.canvas.create_polygon(points, smooth=True, **kwargs)

    def draw_node(self, wx, wy, vertex):
        # Convert to screen coords
        sx, sy = self.world_to_screen(wx, wy)
        
        # Scale dimensions
        w = self.node_width * self.scale
        h = self.node_height * self.scale
        
        # Bounding box
        x1 = sx - w/2
        y1 = sy - h/2
        x2 = sx + w/2
        y2 = sy + h/2
        
        # Styles
        bg_color = THEME["node_bg"]
        outline_color = THEME["node_border"]
        text_color = THEME["text_main"]
        border_w = 1 * max(1, self.scale)
        
        # State Colors
        accent = THEME["accent_cyan"] # Default accent
        status_text = "Idle"
        
        if vertex.is_start:
            accent = THEME["accent_emerald"]
            status_text = "Start"
            # bg_color = "#13231b" # Slight tinge?
            
        # Highlight Logic
        if vertex.id == self.active_node_id:
            outline_color = THEME["accent_purple"] # Active glow color
            border_w = 2 * max(1, self.scale)
            # Add Glow (Simulated with larger semi-transparent rect behind? Expensive in Tk)
            # We can use a shadow offset
            self.draw_rounded_rect(x1-2, y1-2, x2+2, y2+2, 10*self.scale, fill=THEME["accent_purple"], outline="")
            status_text = "Running..."
        elif self.selected_item == ("node", vertex.id):
             outline_color = THEME["accent_cyan"]
             border_w = 2 * max(1, self.scale)

        tag = f"node:{vertex.id}"
        
        # Main Shape
        # We assume 10px radius at scale 1
        r = 10 * self.scale
        
        # Draw background shape
        rect_id = self.draw_rounded_rect(x1, y1, x2, y2, r, fill=bg_color, outline=outline_color, width=border_w, tags=tag)
        
        # Accent Bar (Left side)
        # Clip or draw small rect
        bar_w = 4 * self.scale
        self.canvas.create_rectangle(x1, y1+r/2, x1+bar_w, y2-r/2, fill=accent, outline="", tags=tag)
        
        # Icon (Simulated with Circle/Text)
        icon_r = 8 * self.scale
        icon_x = x1 + 20 * self.scale
        icon_y = sy
        self.canvas.create_oval(icon_x-icon_r, icon_y-icon_r, icon_x+icon_r, icon_y+icon_r, fill=THEME["bg_canvas"], outline=accent, width=1, tags=tag)
        
        # Title
        title_font_size = int(10 * self.scale)
        self.canvas.create_text(icon_x + 15*self.scale, sy - 5*self.scale, text=vertex.name, anchor="w", fill=text_color, font=("Segoe UI", title_font_size, "bold"), tags=tag)
        
        # Status Subtitle
        sub_font_size = int(8 * self.scale)
        self.canvas.create_text(icon_x + 15*self.scale, sy + 8*self.scale, text=status_text, anchor="w", fill=THEME["text_sub"], font=("Segoe UI", sub_font_size), tags=tag)

    def draw_edge(self, p1, p2, edge):
        # Convert World to Screen
        sx1, sy1 = 0, 0
        if p1:
            sx1, sy1 = self.world_to_screen(p1[0], p1[1])
        elif edge.points and len(edge.points) >= 2:
            sx1, sy1 = self.world_to_screen(edge.points[0], edge.points[1])
        else:
            return # No start point

        sx2, sy2 = 0, 0
        if p2:
            sx2, sy2 = self.world_to_screen(p2[0], p2[1])
        elif edge.points and len(edge.points) >= 4:
            sx2, sy2 = self.world_to_screen(edge.points[2], edge.points[3])
        else:
            return # No end point

        tag = f"edge:{edge.id}"
        color = THEME["text_sub"] # Default edge color (#9ca3af)
        width = 2 * self.scale
        arrow_shape = (10*self.scale, 12*self.scale, 4*self.scale)
        
        if self.selected_item == ("edge", edge.id):
             color = THEME["accent_cyan"]
             width = 3 * self.scale
        
        # Self Loop Logic (Simplified Transform)
        if edge.source_id and edge.source_id == edge.target_id:
            # Loop above node
            # Node half-height is 40. Start loop at edge.
            node_half_h = (self.node_height / 2) * self.scale
            margin = 2 * self.scale
            
            top_y = sy1 - node_half_h
            
            points = [
                sx1 - 10*self.scale, top_y,
                sx1 - 40*self.scale, top_y - 40*self.scale, # Control 1
                sx1 + 40*self.scale, top_y - 40*self.scale, # Control 2
                sx1 + 10*self.scale, top_y              # End
            ]
            self.canvas.create_line(points, arrow=tk.LAST, arrowshape=arrow_shape, width=width, fill=color, tags=tag, smooth=True)
            mid_x = sx1
            mid_y = sy1 - 65*self.scale
        else:
            # Calculate intersection with node circumference/box to show arrow clearly
            # Vector P1 -> P2
            dx = sx2 - sx1
            dy = sy2 - sy1
            dist = math.hypot(dx, dy)
            
            if dist == 0: return 

            # Normalize
            ux = dx / dist
            uy = dy / dist
            
            # Node dimensions (scaled)
            w = self.node_width * self.scale
            h = self.node_height * self.scale
            
            # Adjust Start/End to be at the edge of the node (approximate rect/box intersection)
            # Simple ray-box intersection logic or just offset by half-width/height logic if strictly horizontal/vertical
            # But for arbitrary angles, we need to find where the line hits the box.
            
            # Simple approximation: Clamp the vector to the box
            # For a box of size w,h, the edge is at x= +/- w/2 or y= +/- h/2
            
            def get_box_intersect(ux, uy, w, h):
                t_x = (w / 2) / abs(ux) if ux != 0 else float('inf')
                t_y = (h / 2) / abs(uy) if uy != 0 else float('inf')
                
                t = min(t_x, t_y)
                return t
            
            start_offset = 0
            end_offset = 0
            
            if p1: # Source is node
                start_offset = get_box_intersect(ux, uy, w, h) + 5 * self.scale
            if p2: # Target is node
                end_offset = get_box_intersect(-ux, -uy, w, h) + 5 * self.scale

            x1 = sx1 + ux * start_offset
            y1 = sy1 + uy * start_offset
            x2 = sx2 - ux * end_offset
            y2 = sy2 - uy * end_offset

            self.canvas.create_line(x1, y1, x2, y2, arrow=tk.LAST, arrowshape=arrow_shape, width=width, fill=color, tags=tag)
            
            mid_x = (sx1 + sx2) / 2
            mid_y = (sy1 + sy2) / 2

            mid_x = (sx1 + sx2) / 2
            mid_y = (sy1 + sy2) / 2

        # Draw Drag Handles (if selected or arguably always to hint interaction)
        # We'll draw them small and transparent-ish or accent color
        handle_r = 4 * self.scale
        
        # Source Handle
        self.canvas.create_oval(sx1-handle_r, sy1-handle_r, sx1+handle_r, sy1+handle_r, 
                                fill=THEME["accent_cyan"], outline="", tags=(f"handle:{edge.id}:source", tag))
                                
        # Target Handle
        self.canvas.create_oval(sx2-handle_r, sy2-handle_r, sx2+handle_r, sy2+handle_r, 
                                fill=THEME["accent_emerald"], outline="", tags=(f"handle:{edge.id}:target", tag))

        # Smart Label (Transformed)
        label = ""
        ttype = edge.trigger.type
        if ttype == "template_match":
            tmpl = edge.trigger.params.get("template", "")
            label = ""
            if edge.trigger.params.get("invert"):
                label = "(!)"
        elif ttype == "ocr_watch":
            cond = edge.trigger.params.get("condition", ">")
            val = edge.trigger.params.get("value", 0)
            label = f"OCR {cond} {val}"
        elif ttype == "immediate":
            label = ">>>"
        elif ttype == "wait":
             label = "Wait"
        else:
            label = ttype
        
        # Action hint
        if edge.action:
            atype = edge.action.type
            if atype == "press_key":
                k = edge.action.params.get("key", "")
                label += f"\n[{k}]"
            elif atype == "click_position":
                 x = edge.action.params.get("x", 0)
                 y = edge.action.params.get("y", 0)
                 label += f"\n[{x},{y}]"
            elif atype == "buzzer":
                label += f"\n[Buzzer]"
                 
        # Label offset
        if edge.source_id != edge.target_id:
             mid_y -= 10 * self.scale
        
        if label:
            # Draw label background for readability
            # Tkinter text doesn't support bg directly efficiently with padding, but we can try simple text
            self.canvas.create_text(mid_x, mid_y, text=label, fill=THEME["accent_cyan"], font=("Segoe UI", int(9*self.scale), "bold"), tags=tag)

    # ... [Interaction Handlers - Identical to previous version] ...
    
    def on_click(self, event):
        item = self.canvas.find_closest(event.x, event.y)
        tags = self.canvas.gettags(item)
        clicked_type = None
        clicked_id = None
        
        # Check for handles first
        for tag in tags:
            if tag.startswith("handle:"):
                # handle:edge_id:source/target
                # robust split to handle IDs with colons
                prefix_len = len("handle:")
                content = tag[prefix_len:]
                # We expect {id}:{type}, so split from right once
                edge_id, end_type = content.rsplit(":", 1)
                
                self.edge_drag = (edge_id, end_type)
                self.set_mode("REWIRE") # Temporary mode for dragging edge end
                return
            elif tag.startswith("node:"):
                clicked_type = "node"
                clicked_id = tag.split(":", 1)[1]
            elif tag.startswith("edge:"):
                clicked_type = "edge"
                clicked_id = tag.split(":", 1)[1]

        wx, wy = self.screen_to_world(event.x, event.y)

        if self.mode == "CONNECT":
            # 1. Start Creation?
            if not self.creating_edge:
                self.creating_edge = True
                if clicked_type == "node":
                    self.creation_start = ("node", clicked_id)
                else:
                    self.creation_start = ("point", (wx, wy))
                
                # Visual Feedback?
                # Maybe sound or slight highlight?
                return
            else:
                # 2. End Creation
                source_id = None
                target_id = None
                points = None
                
                # Determine Source
                stype, sval = self.creation_start
                if stype == "node": source_id = sval
                else: points = [sval[0], sval[1]]
                
                # Determine Target & Points
                if clicked_type == "node":
                    target_id = clicked_id
                    if points: points.extend([wx, wy]) # Point->Node, end points matter less but we can store them? 
                    # Actually if target is node, we don't strictly need end point in points list for model, 
                    # but for disconnect implementation its good to have
                    if points: points = [*points, wx, wy]
                else:
                    # Target is Point
                    if not points: # Node->Point
                         # We need start node coords
                         if source_id in self.node_coords:
                             nx, ny = self.node_coords[source_id]
                             points = [nx+self.node_width/2, ny+self.node_height/2, wx, wy]
                         else: points = [0,0, wx, wy] # Should not happen
                    else: # Point->Point
                         points.extend([wx, wy])

                # Create Edge Immediately
                new_edge = Edge(source_id, target_id, Trigger("template_match"), Action("None"), points=points)
                self.graph.add_edge(new_edge)
                
                # Reset
                self.creating_edge = False
                self.creation_start = None
                self.canvas.delete("temp_line")
                self.refresh_canvas()
                return

        elif self.mode == "DELETE":
            if clicked_type == "node": self.delete_node(clicked_id)
            elif clicked_type == "edge": self.delete_edge(clicked_id)
            return

        elif self.mode == "ADD_NODE":
             self.add_node(wx, wy)
             self.set_mode("SELECT")
             return
            
        self.selected_item = (clicked_type, clicked_id)
        self.refresh_canvas()
        if clicked_type == "node":
            self.drag_data["item"] = clicked_id
            self.drag_data["drag_start_screen"] = (event.x, event.y)
            self.drag_data["node_start_world"] = self.node_coords[clicked_id]

    def on_drag(self, event):
        wx, wy = self.screen_to_world(event.x, event.y)
        
        if self.mode == "REWIRE" and self.edge_drag:
             edge_id, end_type = self.edge_drag
             edge = next((e for e in self.graph.edges if e.id == edge_id), None)
             if edge:
                 # Update edge points interactively
                 if not edge.points:
                     # Initialize points if missing (from Node centers)
                     p1 = self.node_coords.get(edge.source_id) if edge.source_id else (0,0)
                     p2 = self.node_coords.get(edge.target_id) if edge.target_id else (0,0)
                     # Add size offset if nodes
                     if edge.source_id: p1 = (p1[0]+self.node_width/2, p1[1]+self.node_height/2)
                     if edge.target_id: p2 = (p2[0]+self.node_width/2, p2[1]+self.node_height/2)
                     edge.points = [p1[0], p1[1], p2[0], p2[1]]
                 
                 # Update the specific end
                 if end_type == "source":
                     edge.points[0] = wx
                     edge.points[1] = wy
                     # Detach from node logically while dragging? Or wait for release?
                     # Wait for release to commit logic, but visually show disconnect
                 elif end_type == "target":
                     # Ensure 4 points logic
                     if len(edge.points) < 4: edge.points.extend([wx, wy])
                     edge.points[2] = wx
                     edge.points[3] = wy
                     
                 self.refresh_canvas()
             return

        if self.mode == "CONNECT":
             sx1, sy1 = 0, 0
             if self.creating_edge and self.creation_start:
                 # Draw from start
                 stype, sval = self.creation_start
                 if stype == "node":
                     if sval in self.node_coords:
                         p1_world = self.node_coords[sval]
                         sx1, sy1 = self.world_to_screen(p1_world[0] + self.node_width/2, p1_world[1] + self.node_height/2)
                 else:
                     sx1, sy1 = self.world_to_screen(sval[0], sval[1])

                 self.canvas.delete("temp_line")
                 self.canvas.create_line(sx1, sy1, event.x, event.y, dash=(2,2), fill=THEME["accent_cyan"], tags="temp_line")
             return
             
        if self.mode == "SELECT" and self.drag_data["item"]:
            dx_screen = event.x - self.drag_data["drag_start_screen"][0]
            dy_screen = event.y - self.drag_data["drag_start_screen"][1]
            
            dx_world = dx_screen / self.scale
            dy_world = dy_screen / self.scale
            
            
            start_wx, start_wy = self.drag_data["node_start_world"]
            self.node_coords[self.drag_data["item"]] = (start_wx + dx_world, start_wy + dy_world)
            
            self.refresh_canvas()



    def on_release(self, event):
        if self.mode == "REWIRE" and self.edge_drag:
            # Commit the drag
            wx, wy = self.screen_to_world(event.x, event.y)
            edge_id, end_type = self.edge_drag
            edge = next((e for e in self.graph.edges if e.id == edge_id), None)
            
            if edge:
                # Check for drop on Node
                # Find closest item again? Or calculate distance to all nodes?
                # Calculating distance is safer than screen-based find_closest overlap
                found_v = None
                for v_id, coords in self.node_coords.items():
                    # Simple box check
                    nx, ny = coords
                    if nx <= wx <= nx + self.node_width and ny <= wy <= ny + self.node_height:
                         found_v = v_id
                         break
                
                if found_v:
                     # Snap to Node
                     if end_type == "source": 
                         edge.source_id = found_v
                     else: 
                         edge.target_id = found_v
                         
                     # Do we clear points? Or keep them as hints?
                     # If we snap both ends, we should probably clear and rely on auto-draw
                     if edge.source_id and edge.target_id:
                         edge.points = None # Reset to auto
                else:
                     # Drop in space -> Disconnect
                     if end_type == "source": edge.source_id = None
                     else: edge.target_id = None
                     # Points are already updated in on_drag
            
            self.edge_drag = None
            self.set_mode("SELECT")
            self.refresh_canvas()
            return
            
        self.drag_data["item"] = None

    def on_right_click(self, event):
        self.on_click(event)
        if self.selected_item:
            typ, oid = self.selected_item
            menu = tk.Menu(self, tearoff=0)
            if typ == "node":
                menu.add_command(label="Edit Node", command=lambda: self.edit_node(oid))
                menu.add_command(label="Set as Start", command=lambda: self.set_start_node(oid))
                menu.add_command(label="Delete", command=lambda: self.delete_node(oid))
            elif typ == "edge":
                menu.add_command(label="Edit Edge", command=lambda: self.edit_edge(oid))
                menu.add_command(label="Delete", command=lambda: self.delete_edge(oid))
            menu.post(event.x_root, event.y_root)

    def on_double_click(self, event):
        self.on_click(event)
        if self.selected_item:
            typ, oid = self.selected_item
            if typ == "node": self.edit_node(oid)
            elif typ == "edge": self.edit_edge(oid)

    def add_node(self, x, y):
        dialog = ctk.CTkInputDialog(text="Node Name:", title="Input")
        name = dialog.get_input()
        if name:
            v = Vertex(name)
            self.graph.add_vertex(v)
            self.node_coords[v.id] = (x, y)
            self.refresh_canvas()

    def edit_node(self, node_id):
        v = self.graph.vertices[node_id]
        
        win = ctk.CTkToplevel(self)
        win.title("Edit Node")
        win.geometry("400x320")
        
        # Make modal-like
        win.transient(self)
        win.grab_set()
        
        # Name
        ctk.CTkLabel(win, text="Name:").pack(pady=(10, 5))
        name_var = tk.StringVar(value=v.name)
        ctk.CTkEntry(win, textvariable=name_var, width=250).pack(pady=5)
        
        # Template
        ctk.CTkLabel(win, text="Identity Template (Optional):").pack(pady=(15, 5))
        frame_tmpl = ctk.CTkFrame(win, fg_color="transparent")
        frame_tmpl.pack(pady=5)
        
        tmpl_var = tk.StringVar(value=v.template if v.template else "")
        ctk.CTkEntry(frame_tmpl, textvariable=tmpl_var, width=200).pack(side=tk.LEFT, padx=(0, 10))
        
        preview_lbl = tk.Label(win, bg="#333333") # Keep tk.Label for image? or use CTkLabel
        # CTkLabel can display images but needs CTkImage. 
        # For simplicity in this migration step, let's keep tk.Label for the image preview 
        # BUT we need to make sure the background matches the theme.
        # Actually CTkLabel is better.
        preview_lbl = ctk.CTkLabel(win, text="")
        preview_lbl.pack(pady=10)

        def update_node_preview(*args):
             fname = tmpl_var.get()
             # We might need to wrap the photo in CTkImage if we want high DPI support, 
             # but standard PhotoImage works with CTkLabel too (usually).
             photo = self.load_preview_image(fname)
             if photo:
                 preview_lbl.configure(image=photo, text="")
                 preview_lbl.image = photo
             else:
                 preview_lbl.configure(image=None, text="") # CTk uses configure, and None for no image

        tmpl_var.trace("w", update_node_preview)
        update_node_preview()
        
        def paste_image():
            filename = self.save_clipboard_image()
            if filename: tmpl_var.set(filename)
            
        ctk.CTkButton(frame_tmpl, text="Paste", command=paste_image, width=60).pack(side=tk.LEFT)
        win.bind("<Control-v>", lambda e: paste_image())

        def save():
            v.name = name_var.get()
            v.template = tmpl_var.get()
            if not v.template: v.template = None
            win.destroy()
            self.refresh_canvas()
            
        ctk.CTkButton(win, text="Save", command=save, fg_color="#4CAF50", hover_color="#45a049").pack(pady=20)

    def delete_node(self, node_id):
        self.graph.edges = [e for e in self.graph.edges if e.source_id != node_id and e.target_id != node_id]
        del self.graph.vertices[node_id]
        if node_id in self.node_coords: del self.node_coords[node_id]
        self.selected_item = None
        self.refresh_canvas()
    
    def delete_edge(self, edge_id):
        self.graph.edges = [e for e in self.graph.edges if e.id != edge_id]
        self.selected_item = None
        self.refresh_canvas()
        
    def delete_selection(self):
        if self.selected_item:
            typ, oid = self.selected_item
            if typ == "node": self.delete_node(oid)
            elif typ == "edge": self.delete_edge(oid)

    def set_start_node(self, node_id):
        for v in self.graph.vertices.values():
            v.is_start = (v.id == node_id)
        self.refresh_canvas()

    def create_edge_dialog(self, source_id, target_id, points=None):
        self.open_edge_window(source_id=source_id, target_id=target_id, points=points)
        
    def edit_edge(self, edge_id):
        edge = next((e for e in self.graph.edges if e.id == edge_id), None)
        if edge: self.open_edge_window(edge=edge)

    def open_edge_window(self, source_id=None, target_id=None, edge=None, points=None):
        win = ctk.CTkToplevel(self)
        win.title("Edge Properties")
        win.geometry("500x800") 
        win.resizable(False, False)
        
        # Make modal-like
        win.transient(self)
        win.grab_set()

        PAD_X = 10
        PAD_Y = 5
        
        # Helper for Labeled Frame equivalent
        # Helper for Collapsible Section
        def create_collapsible_section(parent, title, collapsed=False):
            wrapper = ctk.CTkFrame(parent, fg_color="transparent")
            
            # State holder attached to wrapper to persist
            wrapper.is_collapsed = collapsed
            
            def toggle():
                wrapper.is_collapsed = not wrapper.is_collapsed
                if wrapper.is_collapsed:
                    content.pack_forget()
                    btn.configure(text=f"▶ {title}")
                else:
                    content.pack(fill=tk.X, padx=0, pady=(0, 5))
                    btn.configure(text=f"▼ {title}")

            btn_text = f"▶ {title}" if collapsed else f"▼ {title}"
            btn = ctk.CTkButton(wrapper, text=btn_text, command=toggle, 
                                fg_color="transparent", hover_color=THEME["node_border"],
                                anchor="w", font=("Segoe UI", 12, "bold"), 
                                width=10, height=24)
            btn.pack(fill=tk.X)
            
            content = ctk.CTkFrame(wrapper, fg_color=THEME["node_bg"]) 
            if not collapsed:
                content.pack(fill=tk.X, padx=0, pady=(0, 5))
            
            # Inner padded frame for actual controls
            inner = ctk.CTkFrame(content, fg_color="transparent")
            inner.pack(fill=tk.X, padx=10, pady=10)
                
            return wrapper, inner
        
        # --- Trigger Configuration ---
        trigger_outer, trigger_frame = create_collapsible_section(win, "Trigger Configuration", collapsed=False)
        trigger_outer.pack(fill=tk.X, padx=10, pady=5)
        
        ctk.CTkLabel(trigger_frame, text="Type:").pack(anchor=tk.W)
        trig_type_var = ctk.StringVar(value="template_match")
        if edge: trig_type_var.set(edge.trigger.type)
        ctk.CTkOptionMenu(trigger_frame, variable=trig_type_var, values=["template_match", "ocr_watch", "immediate"]).pack(fill=tk.X, pady=2)

        # Container for Dynamic Trigger Options
        trig_opts = ctk.CTkFrame(trigger_frame, fg_color="transparent")
        trig_opts.pack(fill=tk.X, pady=5)
        
        # --- Template Match UI ---
        tmpl_frame = ctk.CTkFrame(trig_opts, fg_color="transparent")
        
        ctk.CTkLabel(tmpl_frame, text="Template Image:").pack(anchor=tk.W)
        inner_tmpl = ctk.CTkFrame(tmpl_frame, fg_color="transparent")
        inner_tmpl.pack(fill=tk.X)
        
        tmpl_var = tk.StringVar()
        if edge: tmpl_var.set(edge.trigger.params.get("template", ""))
        ctk.CTkEntry(inner_tmpl, textvariable=tmpl_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        def paste_image():
            filename = self.save_clipboard_image()
            if filename: tmpl_var.set(filename)
        ctk.CTkButton(inner_tmpl, text="Paste", command=paste_image, width=60).pack(side=tk.LEFT, padx=5)

        preview_label = ctk.CTkLabel(tmpl_frame, text="")
        preview_label.pack(pady=5)
        
        def update_preview(*args):
            fname = tmpl_var.get()
            photo = self.load_preview_image(fname)
            if photo:
                preview_label.configure(image=photo, text="")
                preview_label.image = photo 
            else:
                preview_label.configure(image=None, text="(No Image)" if fname else "")
        tmpl_var.trace("w", update_preview)
        update_preview()
        
        inv_frame = ctk.CTkFrame(tmpl_frame, fg_color="transparent")
        inv_frame.pack(fill=tk.X, pady=2)
        invert_var = tk.BooleanVar() # CTkCheckBox uses standard BooleanVar
        if edge: invert_var.set(edge.trigger.params.get("invert", False))
        ctk.CTkCheckBox(inv_frame, text="Invert Condition (Trigger if NOT found)", variable=invert_var).pack(anchor=tk.W)

        # --- OCR Watch UI ---
        ocr_frame = ctk.CTkFrame(trig_opts, fg_color="transparent")
        
        ctk.CTkLabel(ocr_frame, text="Region (x, y, w, h):").pack(anchor=tk.W)
        ocr_row1 = ctk.CTkFrame(ocr_frame, fg_color="transparent")
        ocr_row1.pack(fill=tk.X)
        
        region_var = tk.StringVar(value="0,0,100,50")
        if edge and edge.trigger.type == "ocr_watch":
            r = edge.trigger.params.get("region", [0,0,100,50])
            region_var.set(f"{r[0]},{r[1]},{r[2]},{r[3]}")
        ctk.CTkEntry(ocr_row1, textvariable=region_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        def select_region():
             self.attributes('-alpha', 0.0)
             def on_select(rect):
                 self.attributes('-alpha', 1.0)
                 region_var.set(f"{rect[0]},{rect[1]},{rect[2]},{rect[3]}")
                 win.deiconify()
             RegionSelector(self, on_select)
             
        ctk.CTkButton(ocr_row1, text="Select", command=select_region, width=60).pack(side=tk.LEFT, padx=5)
        
        ocr_row2 = ctk.CTkFrame(ocr_frame, fg_color="transparent")
        ocr_row2.pack(fill=tk.X, pady=5)
        
        ctk.CTkLabel(ocr_row2, text="Condition:").pack(side=tk.LEFT)
        cond_var = ctk.StringVar(value=">")
        if edge and edge.trigger.type == "ocr_watch":
            cond_var.set(edge.trigger.params.get("condition", ">"))
        ctk.CTkOptionMenu(ocr_row2, variable=cond_var, values=[">", "<", "=", ">=", "<=", "!="], width=70).pack(side=tk.LEFT, padx=5)
        
        ctk.CTkLabel(ocr_row2, text="Value:").pack(side=tk.LEFT, padx=(10,0))
        val_var = tk.StringVar(value="0")
        if edge and edge.trigger.type == "ocr_watch":
            val_var.set(edge.trigger.params.get("value", "0"))
        ctk.CTkEntry(ocr_row2, textvariable=val_var, width=60).pack(side=tk.LEFT, padx=5)
        
        ctk.CTkLabel(ocr_frame, text="Parse Interval (s):").pack(anchor=tk.W)
        ocr_interval_var = tk.StringVar(value="1.0")
        if edge and edge.trigger.type == "ocr_watch":
            ocr_interval_var.set(str(edge.trigger.params.get("interval", 1.0)))
        ctk.CTkEntry(ocr_frame, textvariable=ocr_interval_var).pack(fill=tk.X)

        def update_trig_ui(*args):
            tmpl_frame.pack_forget()
            ocr_frame.pack_forget()
            t = trig_type_var.get()
            if t == "template_match": tmpl_frame.pack(fill=tk.X)
            elif t == "ocr_watch": ocr_frame.pack(fill=tk.X)
        
        trig_type_var.trace("w", update_trig_ui)
        update_trig_ui()


        # --- Action Configuration ---
        action_outer, action_frame = create_collapsible_section(win, "Action Configuration", collapsed=False)
        action_outer.pack(fill=tk.X, padx=10, pady=5)
        
        ctk.CTkLabel(action_frame, text="Type:").pack(anchor=tk.W)
        action_var = ctk.StringVar(value="None")
        if edge and edge.action: action_var.set(edge.action.type)
        elif edge is None: action_var.set("click_match") 
        
        ctk.CTkOptionMenu(action_frame, variable=action_var, values=["None", "click_match", "press_key", "wait", "center_camera", "click_position", "buzzer"]).pack(fill=tk.X, pady=2)

        options_container = ctk.CTkFrame(action_frame, fg_color="transparent")
        options_container.pack(fill=tk.X, pady=5)

        # Dynamic Frames
        key_frame = ctk.CTkFrame(options_container, fg_color="transparent")
        mods_frame_container = ctk.CTkFrame(options_container, fg_color="transparent")
        pos_frame = ctk.CTkFrame(options_container, fg_color="transparent")
        wait_frame = ctk.CTkFrame(options_container, fg_color="transparent")
        buzzer_frame = ctk.CTkFrame(options_container, fg_color="transparent")
        
        # -> Key + Duration
        ctk.CTkLabel(key_frame, text="Key:").pack(anchor=tk.W)
        key_var = tk.StringVar()
        if edge and edge.action: key_var.set(edge.action.params.get("key", ""))
        ctk.CTkEntry(key_frame, textvariable=key_var).pack(fill=tk.X)
        
        ctk.CTkLabel(key_frame, text="Duration (s):").pack(anchor=tk.W)
        dur_var = tk.StringVar(value="0.05")
        if edge and edge.action: dur_var.set(str(edge.action.params.get("duration", 0.05)))
        ctk.CTkEntry(key_frame, textvariable=dur_var).pack(fill=tk.X)

        # -> Wait Action Fields
        ctk.CTkLabel(wait_frame, text="Duration (s):").pack(anchor=tk.W)
        wait_dur_var = tk.StringVar(value="0.5")
        if edge and edge.action and edge.action.type == "wait":
             wait_dur_var.set(str(edge.action.params.get("duration", 0.5)))
        ctk.CTkEntry(wait_frame, textvariable=wait_dur_var).pack(fill=tk.X)

        # -> Buzzer Action Fields
        ctk.CTkLabel(buzzer_frame, text="Frequency (Hz):").pack(anchor=tk.W)
        buzzer_freq_var = tk.StringVar(value="600")
        if edge and edge.action and edge.action.type == "buzzer":
             buzzer_freq_var.set(str(edge.action.params.get("frequency", 600)))
        ctk.CTkEntry(buzzer_frame, textvariable=buzzer_freq_var).pack(fill=tk.X)
        
        ctk.CTkLabel(buzzer_frame, text="Duration (s):").pack(anchor=tk.W)
        buzzer_dur_var = tk.StringVar(value="0.5")
        if edge and edge.action and edge.action.type == "buzzer":
             buzzer_dur_var.set(str(edge.action.params.get("duration", 0.5)))
        ctk.CTkEntry(buzzer_frame, textvariable=buzzer_dur_var).pack(fill=tk.X)

        # -> Position Fields
        ctk.CTkLabel(pos_frame, text="Position (x, y):").pack(anchor=tk.W)
        pos_inner = ctk.CTkFrame(pos_frame, fg_color="transparent")
        pos_inner.pack(fill=tk.X)
        
        x_var = tk.StringVar(value="0")
        y_var = tk.StringVar(value="0")
        if edge and edge.action and edge.action.type == "click_position":
            x_var.set(str(edge.action.params.get("x", 0)))
            y_var.set(str(edge.action.params.get("y", 0)))
            
        ctk.CTkEntry(pos_inner, textvariable=x_var, width=80).pack(side=tk.LEFT)
        ctk.CTkLabel(pos_inner, text=",").pack(side=tk.LEFT, padx=5)
        ctk.CTkEntry(pos_inner, textvariable=y_var, width=80).pack(side=tk.LEFT)
        
        def select_point():
             self.attributes('-alpha', 0.0)
             def on_point(pt):
                 self.attributes('-alpha', 1.0)
                 x_var.set(pt[0])
                 y_var.set(pt[1])
                 win.deiconify()
             PointSelector(self, on_point)
        ctk.CTkButton(pos_inner, text="Select Cursor", command=select_point).pack(side=tk.LEFT, padx=10)

        # -> Modifiers
        ctk.CTkLabel(mods_frame_container, text="Modifiers:").pack(anchor=tk.W)
        mods_frame = ctk.CTkFrame(mods_frame_container, fg_color="transparent")
        mods_frame.pack(fill=tk.X)
        
        current_mods = []
        if edge and edge.action:
             raw_mods = edge.action.params.get("modifiers", "")
             current_mods = [m.strip().lower() for m in raw_mods.split(",") if m.strip()]

        mod_vars = {}
        for mod_key in ["alt", "ctrl", "shift"]:
            var = tk.BooleanVar(value=(mod_key in current_mods))
            mod_vars[mod_key] = var
            ctk.CTkCheckBox(mods_frame, text=mod_key.capitalize(), variable=var).pack(side=tk.LEFT, padx=5)

        def update_act_ui(*args):
            key_frame.pack_forget()
            mods_frame_container.pack_forget()
            pos_frame.pack_forget()
            wait_frame.pack_forget()
            buzzer_frame.pack_forget()
            val = action_var.get()
            if val == "press_key":
                key_frame.pack(fill=tk.X, pady=2)
                mods_frame_container.pack(fill=tk.X, pady=2)
            elif val == "click_match":
                mods_frame_container.pack(fill=tk.X, pady=2)
            elif val == "click_position":
                pos_frame.pack(fill=tk.X, pady=2)
                mods_frame_container.pack(fill=tk.X, pady=2)
            elif val == "wait":
                wait_frame.pack(fill=tk.X, pady=2)
            elif val == "buzzer":
                buzzer_frame.pack(fill=tk.X, pady=2)
        
        action_var.trace("w", update_act_ui)
        update_act_ui() 

        # --- Settings ---
        settings_outer, settings_frame = create_collapsible_section(win, "Advanced Settings", collapsed=True)
        settings_outer.pack(fill=tk.X, padx=10, pady=5)
        
        s_row1 = ctk.CTkFrame(settings_frame, fg_color="transparent")
        s_row1.pack(fill=tk.X)
        
        ctk.CTkLabel(s_row1, text="Confidence:").pack(side=tk.LEFT)
        conf_var = tk.StringVar(value="0.8")
        if edge: conf_var.set(str(edge.trigger.params.get("threshold", 0.8)))
        ctk.CTkEntry(s_row1, textvariable=conf_var, width=60).pack(side=tk.LEFT, padx=5)
        
        ctk.CTkLabel(s_row1, text="Priority:").pack(side=tk.LEFT, padx=(20, 0))
        prio_var = tk.StringVar(value="0")
        if edge: prio_var.set(str(edge.priority))
        ctk.CTkEntry(s_row1, textvariable=prio_var, width=60).pack(side=tk.LEFT, padx=5)

        def save():
            trig_type = trig_type_var.get()
            tmpl = tmpl_var.get()
            act_type = action_var.get()
            try:
                conf = float(conf_var.get())
            except:
                conf = 0.8
            target_key = key_var.get()
            is_inverted = invert_var.get()
            try:
                duration = float(dur_var.get())
            except:
                duration = 0.05

            try:
                wait_duration = float(wait_dur_var.get())
            except:
                 wait_duration = 0.5
            try:
                priority = int(prio_var.get())
            except:
                priority = 0

            try:
                buzzer_freq = int(buzzer_freq_var.get())
            except:
                buzzer_freq = 600
            
            try:
                buzzer_duration = float(buzzer_dur_var.get())
            except:
                buzzer_duration = 0.5
            
            selected_mods = [k for k, v in mod_vars.items() if v.get()]
            mods_str = ", ".join(selected_mods)
            
            trigger_params = {}
            if trig_type == "template_match":
                trigger_params = {"template": tmpl, "threshold": conf, "invert": is_inverted}
            elif trig_type == "ocr_watch":
                try:
                     r = [int(x) for x in region_var.get().split(",")]
                     trigger_params = {
                         "region": r,
                         "condition": cond_var.get(),
                         "value": float(val_var.get()),
                         "interval": float(ocr_interval_var.get())
                     }
                except ValueError:
                    messagebox.showerror("Error", "Invalid OCR Parameters")
                    return
            
            trigger = Trigger(trig_type, trigger_params)
            
            action = None
            if act_type != "None":
                action_params = {}
                if mods_str: action_params["modifiers"] = mods_str
                if target_key: action_params["key"] = target_key
                if act_type == "press_key": action_params["duration"] = duration
                if act_type == "click_position":
                    try: x = int(x_var.get())
                    except: x = 0
                    try: y = int(y_var.get())
                    except: y = 0
                    action_params["x"] = x
                    action_params["y"] = y
                
                if act_type == "wait":
                    action_params["duration"] = wait_duration
                
                if act_type == "buzzer":
                    action_params["frequency"] = buzzer_freq
                    action_params["duration"] = buzzer_duration
                
                action = Action(act_type, action_params)

            if edge:
                edge.trigger = trigger
                edge.action = action
                edge.priority = priority
                edge.points = points # Update points if editing? Or stick to original? Usually points are static for disconnected.
            else:
                new_edge = Edge(source_id, target_id, trigger, action, priority=priority, points=points)
                self.graph.add_edge(new_edge)
            win.destroy()
            self.refresh_canvas()

        ctk.CTkButton(win, text="Save Changes", command=save, fg_color="#4CAF50", hover_color="#45a049", font=("Arial", 14, "bold")).pack(pady=20, fill=tk.X, padx=20, ipady=5)
        win.bind("<Control-v>", lambda e: paste_image())

    def on_paste_hotkey(self, event):
        messagebox.showinfo("Paste", "Open an Edge dialog to paste a template.")

    def save_clipboard_image(self):
        try:
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_DIB):
                data = win32clipboard.GetClipboardData(win32clipboard.CF_DIB)
                win32clipboard.CloseClipboard()
            else:
                win32clipboard.CloseClipboard()
                messagebox.showerror("Error", "No image in clipboard!")
                return None
            fname = f"captured_{uuid.uuid4().hex[:8]}.bmp"
            fpath = os.path.join(self.assets_dir, fname)
            with open(fpath, "wb") as f:
                dib_header_size = int.from_bytes(data[0:4], byteorder='little')
                filesize = 14 + len(data)
                offset = 14 + dib_header_size 
                import struct
                bmp_header = struct.pack('<2sIHHI', b'BM', filesize, 0, 0, offset)
                f.write(bmp_header)
                f.write(data)
            return fname
        except Exception as e:
            messagebox.showerror("Error", f"Failed to paste: {e}")
            try: win32clipboard.CloseClipboard()
            except: pass
            return None

    def load_preview_image(self, filename, max_size=(200, 100)):
        if not filename: return None
        path = os.path.join(self.assets_dir, filename)
        if not os.path.exists(path): return None
        
        try:
            img = cv2.imread(path)
            if img is None: return None
            
            # Convert BGR to RGB
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img)
            
            # Calculate Scale
            h, w = img.shape[:2]
            scale = min(max_size[0]/w, max_size[1]/h)
            
            # Set display size
            display_size = (int(w * scale), int(h * scale))
            
            # CTkImage handles scaling
            return ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=display_size)

        except Exception as e:
            print(f"Error loading preview: {e}")
            return None

if __name__ == "__main__":
    app = GraphEditor(".")
    app.mainloop()
