import tkinter as tk
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
from .model import Graph, Vertex, Edge, Trigger, Action
from .executor import GraphExecutor
import mss

class RegionSelector(tk.Toplevel):
    def __init__(self, master, on_select):
        super().__init__(master)
        self.on_select = on_select
        self.attributes('-fullscreen', True)
        self.attributes('-alpha', 0.3)
        self.config(bg='black')
        self.bind('<Escape>', self.close)
        
        self.canvas = tk.Canvas(self, cursor="cross", bg="grey11")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        
        # Transparent window fix for some OS (Windows usually needs more work for true click-through but we want to intercept clicks)
        # We want to show a screenshot ideally? Or just Draw a rectangle on a transparent overlay.
        # 'attributes -alpha' makes the WHOLE window transparent. 
        # To make a "snipping tool" with Tkinter is tricky for perfect visuals, but a simple semi-transparent overlay works.
        # We will use a canvas with a rectangle.
        self.start_x = None
        self.start_y = None
        self.rect = None

        # Capture screen for context (Optional, but helps visibility)
        # For simplicity, we just use a grey overlay.

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, event.x, event.y, outline='red', width=2)

    def on_drag(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        x1, y1 = self.start_x, self.start_y
        x2, y2 = event.x, event.y
        
        x = min(x1, x2)
        y = min(y1, y2)
        w = abs(x2 - x1)
        h = abs(y2 - y1)
        
        if w > 5 and h > 5:
            self.on_select((x, y, w, h))
        
        self.close()

    def close(self, event=None):
        self.destroy()


# Configuration
GAME_TITLE_KEYWORD = "Tower of Fantasy"

class GraphEditor(tk.Tk):
    def __init__(self, assets_dir):
        super().__init__()
        self.title("Autobuyer State Machine Editor")
        self.geometry("1100x800")
        
        self.assets_dir = assets_dir
        if not os.path.exists(self.assets_dir):
            os.makedirs(self.assets_dir)

        self.graph = Graph()
        self.node_radius = 25
        self.selected_item = None # (type, id)
        self.drag_data = {"x": 0, "y": 0, "item": None}
        
        self.mode = "SELECT" 
        
        # Execution State
        self.executor = None
        self.executor_thread = None
        self.active_node_id = None
        self.is_running = False
        
        # UI Layout
        self.create_menu()
        self.create_toolbar()
        self.create_canvas()
        
        self.node_coords = {}
        self.temp_line = None
        self.connecting_node = None
        
        # Hotkeys
        self.bind("<Control-v>", self.on_paste_hotkey)
        self.bind("<Delete>", lambda e: self.delete_selection())

        # Polling for UI updates from thread
        self.check_execution_queue()

    def check_execution_queue(self):
        # In a real app we'd use a Queue, here we can simplistic polling if updating a var
        # But actually, tkinter is not thread safe. 
        # The callback from executor runs in thread. We must not touch UI there.
        # We will update self.active_node_id and call refresh_canvas via after() ??
        # No, refresh_canvas is UI.
        # Better: use after loop to check if active_node_id changed? 
        # Or have the callback scheduling an event.
        pass

    def on_executor_state_change(self, node_id):
        self.active_node_id = node_id
        # Schedule update on main thread
        self.after(0, self.refresh_canvas)

    def create_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New", command=self.new_graph)
        file_menu.add_command(label="Open", command=self.load_graph)
        file_menu.add_command(label="Save", command=self.save_graph)
        menubar.add_cascade(label="File", menu=file_menu)
        self.config(menu=menubar)

    def create_toolbar(self):
        toolbar = tk.Frame(self, width=120, bg="#f0f0f0", relief=tk.RAISED, bd=2)
        toolbar.pack(side=tk.LEFT, fill=tk.Y)
        
        tk.Label(toolbar, text="Tools", font=("Arial", 10, "bold"), bg="#f0f0f0").pack(pady=10)
        
        self.btn_run = tk.Button(toolbar, text="▶ Run", command=self.toggle_run, width=10, bg="lightgreen")
        self.btn_run.pack(pady=20)

        # Standard Tools
        tk.Button(toolbar, text="↖ Select", command=lambda: self.set_mode("SELECT"), width=10).pack(pady=2)
        tk.Button(toolbar, text="+ Node", command=lambda: self.set_mode("ADD_NODE"), width=10).pack(pady=2)
        tk.Button(toolbar, text="→ Connect", command=lambda: self.set_mode("CONNECT"), width=10).pack(pady=2)
        tk.Button(toolbar, text="🗑 Delete", command=lambda: self.set_mode("DELETE"), width=10).pack(pady=2)
        
        self.mode_label = tk.Label(toolbar, text="Mode: SELECT", fg="blue", bg="#f0f0f0")
        self.mode_label.pack(side=tk.BOTTOM, pady=20)

    def find_game_window(self):
        hwnd_found = None
        def callback(h, extra):
            nonlocal hwnd_found
            if win32gui.IsWindowVisible(h):
                if GAME_TITLE_KEYWORD in win32gui.GetWindowText(h):
                    hwnd_found = h
        win32gui.EnumWindows(callback, None)
        return hwnd_found

    def toggle_run(self):
        if self.is_running:
            # STOP
            if self.executor:
                self.executor.stop()
            self.is_running = False
            self.btn_run.config(text="▶ Run", bg="lightgreen")
            self.active_node_id = None
            self.refresh_canvas()
            
            # Unhook F1
            try:
                keyboard.remove_hotkey('f1')
            except: pass
            
        else:
            # START
            hwnd = self.find_game_window()
            if not hwnd:
                messagebox.showerror("Error", f"Game window '{GAME_TITLE_KEYWORD}' not found!")
                return

            self.is_running = True
            self.btn_run.config(text="⏹ Stop", bg="#ffcccc")
            
            self.executor = GraphExecutor(self.graph, hwnd, self.assets_dir, on_state_change=self.on_executor_state_change)
            
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
            self.btn_run.config(text="⏸ Paused", bg="yellow")
        else:
            self.btn_run.config(text="⏹ Stop", bg="#ffcccc")


    def run_executor_thread(self):
        try:
            self.executor.run()
        except Exception as e:
            print(f"Executor Error: {e}")
            self.is_running = False
            self.after(0, lambda: messagebox.showerror("Error", f"Runtime Error: {e}"))
            self.after(0, lambda: self.btn_run.config(text="▶ Run", bg="lightgreen"))

    # ... [Rest of Canvas/Drawing Logic, slightly modified to highlight active] ...

    def set_mode(self, mode):
        self.mode = mode
        self.mode_label.config(text=f"Mode: {mode}")
        self.connecting_node = None
        self.canvas.delete("temp_line")
        self.canvas.config(cursor="arrow")
        if mode == "ADD_NODE": self.canvas.config(cursor="cross")
        elif mode == "CONNECT": self.canvas.config(cursor="hand2")
        elif mode == "DELETE": self.canvas.config(cursor="X_cursor")

    def create_canvas(self):
        self.canvas = tk.Canvas(self, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)

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
        for edge in self.graph.edges:
            p1 = self.node_coords.get(edge.source_id)
            p2 = self.node_coords.get(edge.target_id)
            if p1 and p2:
                self.draw_edge(p1, p2, edge)
        for v_id, vertex in self.graph.vertices.items():
            x, y = self.node_coords.get(v_id, (100, 100))
            self.draw_node(x, y, vertex)

    def draw_node(self, x, y, vertex):
        color = "lightgreen" if vertex.is_start else "lightblue"
        outline = "black"
        width = 1
        
        # Highlight Logic
        if vertex.id == self.active_node_id:
            color = "#ffeb3b" # Yellow/Gold for active
            outline = "#ff9800"
            width = 4
        elif self.selected_item == ("node", vertex.id):
             outline = "red"
             width = 3

        tag = f"node:{vertex.id}"
        self.canvas.create_oval(x-self.node_radius, y-self.node_radius, x+self.node_radius, y+self.node_radius, fill=color, outline=outline, width=width, tags=tag)
        self.canvas.create_text(x, y, text=vertex.name, tags=tag, font=("Arial", 9, "bold" if vertex.id == self.active_node_id else "normal"))

    def draw_edge(self, p1, p2, edge):
        tag = f"edge:{edge.id}"
        color = "black"
        width = 2
        arrow_shape = (16, 20, 6)
        if self.selected_item == ("edge", edge.id):
             color = "red"
             width = 3
        
    def draw_edge(self, p1, p2, edge):
        tag = f"edge:{edge.id}"
        color = "black"
        width = 2
        arrow_shape = (16, 20, 6)
        if self.selected_item == ("edge", edge.id):
             color = "red"
             width = 3
        
        # Check for Self-Loop
        if edge.source_id == edge.target_id:
            # Draw a loop above the node
            x, y = p1
            r = self.node_radius
            
            # Control points for a loop
            # Start at top of node
            x1, y1 = x, y - r
            # Loop out to top-right, top, top-left
            # We use create_line with smooth=True for bezier-like curve
            
            # Points: Start(Top), Control1(TopRight), Control2(TopLeft), End(Top)
            # Actually strictly starting at Top might overlap label or just look odd. 
            # Let's do a loop from Top-Left to Top-Right.
            
            # Bezier approach:
            # p_start = (x - r/2, y-r)
            # p_mid_1 = (x - r*2, y - r*3)
            # p_mid_2 = (x + r*2, y - r*3)
            # p_end   = (x + r/2, y-r)
            
            # Actually drawing to circumference:
            # Angle -45 deg (Top Left) to +45 deg (Top Right) ??
            # Let's try explicit points.
            
            offset = 40
            points = [
                x - 10, y - r,            # Start
                x - offset, y - r - offset, # Control 1
                x + offset, y - r - offset, # Control 2
                x + 10, y - r             # End
            ]
            
            self.canvas.create_line(points, arrow=tk.LAST, arrowshape=arrow_shape, width=width, fill=color, tags=tag, smooth=True)
            
            # Label pos
            mid_x = x
            mid_y = y - r - offset
            
        else:
            # Calculate intersection with node circumference to show arrow clearly
            # Vector P1 -> P2
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            dist = math.hypot(dx, dy)
            
            if dist == 0: return 

            # Normalize
            ux = dx / dist
            uy = dy / dist
            
            # Radius offset
            start_offset = self.node_radius
            end_offset = self.node_radius

            # Adjusted Points
            x1 = p1[0] + ux * start_offset
            y1 = p1[1] + uy * start_offset
            x2 = p2[0] - ux * end_offset
            y2 = p2[1] - uy * end_offset

            self.canvas.create_line(x1, y1, x2, y2, arrow=tk.LAST, arrowshape=arrow_shape, width=width, fill=color, tags=tag)
            
            mid_x = (p1[0] + p2[0]) / 2
            mid_y = (p1[1] + p2[1]) / 2

        # Label
        label = edge.trigger.params.get("template", "")
        if not label: label = "Wait" if edge.trigger.type == "wait" else "?"
        else: label = os.path.basename(label)
        
        # Offset label slightly if standard line
        if edge.source_id != edge.target_id:
             mid_y -= 15
        else:
             mid_y -= 10 # Loop label
             
        self.canvas.create_text(mid_x, mid_y, text=label, fill="blue", font=("Arial", 8), tags=tag)

    # ... [Interaction Handlers - Identical to previous version] ...
    
    def on_click(self, event):
        item = self.canvas.find_closest(event.x, event.y)
        tags = self.canvas.gettags(item)
        clicked_type = None
        clicked_id = None
        for tag in tags:
            if tag.startswith("node:"):
                clicked_type = "node"
                clicked_id = tag.split(":")[1]
            elif tag.startswith("edge:"):
                clicked_type = "edge"
                clicked_id = tag.split(":")[1]

        if self.mode == "ADD_NODE":
            self.add_node(event.x, event.y)
            self.set_mode("SELECT")
            return
        elif self.mode == "DELETE":
            if clicked_type == "node": self.delete_node(clicked_id)
            elif clicked_type == "edge": self.delete_edge(clicked_id)
            return
        elif self.mode == "CONNECT":
            if clicked_type == "node":
                if not self.connecting_node:
                    self.connecting_node = clicked_id
                    messagebox.showinfo("Connect", f"Selected source: {self.graph.vertices[clicked_id].name}. Click target.")
                else:
                    # Allow self-connection
                    self.create_edge_dialog(self.connecting_node, clicked_id)
                    self.connecting_node = None
                    self.canvas.delete("temp_line")
                    self.set_mode("SELECT")
            return
            
        self.selected_item = (clicked_type, clicked_id)
        self.refresh_canvas()
        if clicked_type == "node":
            self.drag_data["item"] = clicked_id
            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y

    def on_drag(self, event):
        if self.mode == "CONNECT" and self.connecting_node:
             p1 = self.node_coords[self.connecting_node]
             self.canvas.delete("temp_line")
             self.canvas.create_line(p1[0], p1[1], event.x, event.y, dash=(2,2), tags="temp_line")
             return
        if self.mode == "SELECT" and self.drag_data["item"]:
            dx = event.x - self.drag_data["x"]
            dy = event.y - self.drag_data["y"]
            v_id = self.drag_data["item"]
            cur_x, cur_y = self.node_coords[v_id]
            self.node_coords[v_id] = (cur_x + dx, cur_y + dy)
            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y
            self.refresh_canvas()

    def on_release(self, event):
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
        name = simpledialog.askstring("Input", "Node Name:")
        if name:
            v = Vertex(name)
            self.graph.add_vertex(v)
            self.node_coords[v.id] = (x, y)
            self.refresh_canvas()

    def edit_node(self, node_id):
        v = self.graph.vertices[node_id]
        
        win = tk.Toplevel(self)
        win.title("Edit Node")
        win.geometry("400x250")
        
        # Name
        tk.Label(win, text="Name:").pack(pady=5)
        name_var = tk.StringVar(value=v.name)
        tk.Entry(win, textvariable=name_var).pack()
        
        # Template
        tk.Label(win, text="Identity Template (Optional):").pack(pady=5)
        frame_tmpl = tk.Frame(win)
        frame_tmpl.pack()
        
        tmpl_var = tk.StringVar(value=v.template if v.template else "")
        tk.Entry(frame_tmpl, textvariable=tmpl_var, width=30).pack(side=tk.LEFT)
        
        preview_lbl = tk.Label(win)
        preview_lbl.pack(pady=2)

        def update_node_preview(*args):
             fname = tmpl_var.get()
             photo = self.load_preview_image(fname)
             if photo:
                 preview_lbl.config(image=photo, text="")
                 preview_lbl.image = photo
             else:
                 preview_lbl.config(image="", text="")

        tmpl_var.trace("w", update_node_preview)
        update_node_preview()
        
        def paste_image():
            filename = self.save_clipboard_image()
            if filename: tmpl_var.set(filename)
            
        tk.Button(frame_tmpl, text="Paste", command=paste_image).pack(side=tk.LEFT, padx=5)
        win.bind("<Control-v>", lambda e: paste_image())

        def save():
            v.name = name_var.get()
            v.template = tmpl_var.get()
            if not v.template: v.template = None
            win.destroy()
            self.refresh_canvas()
            
        tk.Button(win, text="Save", command=save, bg="lightgreen").pack(pady=20)

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

    def create_edge_dialog(self, source_id, target_id):
        self.open_edge_window(source_id=source_id, target_id=target_id)
        
    def edit_edge(self, edge_id):
        edge = next((e for e in self.graph.edges if e.id == edge_id), None)
        if edge: self.open_edge_window(edge=edge)

    def open_edge_window(self, source_id=None, target_id=None, edge=None):
        win = tk.Toplevel(self)
        win.title("Edge Properties")
        win.geometry("400x480")

        # Trigger Type
        tk.Label(win, text="Trigger:").pack(pady=5)
        trig_type_var = tk.StringVar(value="template_match")
        if edge: trig_type_var.set(edge.trigger.type)
        tk.OptionMenu(win, trig_type_var, "template_match", "ocr_watch", "immediate").pack()

        # Trigger Options Container
        trig_opts = tk.Frame(win)
        trig_opts.pack(pady=5, fill=tk.X)
        
        # --- Template Match UI ---
        tmpl_frame = tk.Frame(trig_opts)
        
        tk.Label(tmpl_frame, text="Template Image:").pack(pady=2)
        inner_tmpl = tk.Frame(tmpl_frame)
        inner_tmpl.pack()
        
        tmpl_var = tk.StringVar()
        if edge: tmpl_var.set(edge.trigger.params.get("template", ""))
        tmpl_entry = tk.Entry(inner_tmpl, textvariable=tmpl_var, width=30)
        tmpl_entry.pack(side=tk.LEFT)
        
        def paste_image():
            filename = self.save_clipboard_image()
            if filename: tmpl_var.set(filename)
        tk.Button(inner_tmpl, text="Paste (Ctrl+V)", command=paste_image).pack(side=tk.LEFT, padx=5)

        preview_label = tk.Label(tmpl_frame)
        preview_label.pack(pady=5)
        
        def update_preview(*args):
            fname = tmpl_var.get()
            photo = self.load_preview_image(fname)
            if photo:
                preview_label.config(image=photo, text="")
                preview_label.image = photo 
            else:
                preview_label.config(image="", text="(No Image)" if fname else "")
        tmpl_var.trace("w", update_preview)
        update_preview() # init
        
        # Invert Checkbox
        inv_frame = tk.Frame(tmpl_frame)
        inv_frame.pack(pady=2)
        invert_var = tk.BooleanVar()
        if edge: invert_var.set(edge.trigger.params.get("invert", False))
        tk.Checkbutton(inv_frame, text="Invert (Trigger if NOT found)", variable=invert_var).pack()

        # --- OCR Watch UI ---
        ocr_frame = tk.Frame(trig_opts)
        
        # Region
        tk.Label(ocr_frame, text="Region (x,y,w,h):").pack(pady=2)
        region_var = tk.StringVar(value="0,0,100,50")
        if edge and edge.trigger.type == "ocr_watch":
            r = edge.trigger.params.get("region", [0,0,100,50])
            region_var.set(f"{r[0]},{r[1]},{r[2]},{r[3]}")
        
        region_entry = tk.Entry(ocr_frame, textvariable=region_var)
        region_entry.pack()
        
        def select_region():
            self.attributes('-alpha', 0.0) # Hide main window
            def on_select(rect):
                self.attributes('-alpha', 1.0)
                region_var.set(f"{rect[0]},{rect[1]},{rect[2]},{rect[3]}")
                # Bring editor back to front
                win.deiconify()
            
            # Minimize editor window temporarily
            # win.withdraw() 
            # Actually better to just launch selector
            RegionSelector(self, on_select)
            
        tk.Button(ocr_frame, text="Select Region", command=select_region).pack(pady=2)
        
        # Condition
        tk.Label(ocr_frame, text="Condition:").pack(pady=2)
        cond_frame = tk.Frame(ocr_frame)
        cond_frame.pack()
        
        cond_var = tk.StringVar(value=">")
        if edge and edge.trigger.type == "ocr_watch":
            cond_var.set(edge.trigger.params.get("condition", ">"))
            
        tk.OptionMenu(cond_frame, cond_var, ">", "<", "=", ">=", "<=", "!=").pack(side=tk.LEFT)
        
        # Value
        val_var = tk.StringVar(value="0")
        if edge and edge.trigger.type == "ocr_watch":
            val_var.set(edge.trigger.params.get("value", "0"))
        tk.Entry(cond_frame, textvariable=val_var, width=10).pack(side=tk.LEFT)
        
        # Interval
        tk.Label(ocr_frame, text="Parse Interval (s):").pack(pady=2)
        ocr_interval_var = tk.DoubleVar(value=1.0)
        if edge and edge.trigger.type == "ocr_watch":
            ocr_interval_var.set(edge.trigger.params.get("interval", 1.0))
        tk.Entry(ocr_frame, textvariable=ocr_interval_var).pack()

        # Dynamic Trigger UI Support
        def update_trig_ui(*args):
            tmpl_frame.pack_forget()
            ocr_frame.pack_forget()
            
            t = trig_type_var.get()
            if t == "template_match":
                tmpl_frame.pack(fill=tk.X)
            elif t == "ocr_watch":
                ocr_frame.pack(fill=tk.X)
        
        trig_type_var.trace("w", update_trig_ui)
        update_trig_ui()



        # Action
        tk.Label(win, text="Action:").pack(pady=5)
        action_var = tk.StringVar(value="None")
        if edge and edge.action: action_var.set(edge.action.type)
        elif edge is None: action_var.set("click_match") 
        
        opt = tk.OptionMenu(win, action_var, "None", "click_match", "press_key", "wait", "center_camera")
        opt.pack()

        # Container for Dynamic Options
        options_container = tk.Frame(win)
        options_container.pack(pady=5, fill=tk.X)

        # Dynamic Frames
        key_frame = tk.Frame(options_container)
        mods_frame_container = tk.Frame(options_container)
        
        # --- Key Field + Duration ---
        tk.Label(key_frame, text="Key (for Press Key):").pack(pady=2)
        key_var = tk.StringVar()
        if edge and edge.action: key_var.set(edge.action.params.get("key", ""))
        tk.Entry(key_frame, textvariable=key_var).pack()
        
        tk.Label(key_frame, text="Duration (s):").pack(pady=2)
        dur_var = tk.DoubleVar(value=0.05)
        if edge and edge.action: dur_var.set(edge.action.params.get("duration", 0.05))
        tk.Entry(key_frame, textvariable=dur_var).pack()

        # --- Modifiers Field ---
        tk.Label(mods_frame_container, text="Modifiers:").pack(pady=5)
        mods_frame = tk.Frame(mods_frame_container)
        mods_frame.pack()
        
        current_mods = []
        if edge and edge.action:
             raw_mods = edge.action.params.get("modifiers", "")
             current_mods = [m.strip().lower() for m in raw_mods.split(",") if m.strip()]

        mod_vars = {}
        for mod_key in ["alt", "ctrl", "shift"]:
            var = tk.BooleanVar(value=(mod_key in current_mods))
            mod_vars[mod_key] = var
            tk.Checkbutton(mods_frame, text=mod_key.capitalize(), variable=var).pack(side=tk.LEFT, padx=5)

        # Update Function
        def update_ui(*args):
            key_frame.pack_forget()
            mods_frame_container.pack_forget()
            
            val = action_var.get()
            if val == "press_key":
                key_frame.pack(pady=2)
                mods_frame_container.pack(pady=2)
            elif val == "click_match":
                mods_frame_container.pack(pady=2)
            # wait/None -> hide all
            
        action_var.trace("w", update_ui)
        update_ui() # Set initial state

        tk.Label(win, text="Confidence:").pack(pady=5) # This will be packed after the dynamic frames
        conf_var = tk.DoubleVar(value=0.8)
        if edge: conf_var.set(edge.trigger.params.get("threshold", 0.8))
        tk.Entry(win, textvariable=conf_var).pack()
        
        # Priority
        tk.Label(win, text="Priority (Higher = First):").pack(pady=5)
        prio_var = tk.IntVar(value=0)
        if edge: prio_var.set(edge.priority)
        tk.Entry(win, textvariable=prio_var).pack()

        def save():
            trig_type = trig_type_var.get()
            tmpl = tmpl_var.get()
            act_type = action_var.get()
            conf = conf_var.get()
            target_key = key_var.get()
            is_inverted = invert_var.get()
            duration = dur_var.get()
            priority = prio_var.get()
            
            # Reconstruct modifiers string
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
                         "interval": ocr_interval_var.get()
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
                action = Action(act_type, action_params)

            if edge:
                edge.trigger = trigger
                edge.action = action
                edge.priority = priority
            else:
                new_edge = Edge(source_id, target_id, trigger, action, priority=priority)
                self.graph.add_edge(new_edge)
            win.destroy()
            self.refresh_canvas()
        tk.Button(win, text="Save", command=save, bg="lightgreen").pack(pady=20)
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
            
            # Resize while keeping aspect ratio
            h, w = img.shape[:2]
            scale = min(max_size[0]/w, max_size[1]/h)
            if scale < 1:
                new_w = int(w * scale)
                new_h = int(h * scale)
                img = cv2.resize(img, (new_w, new_h))
            
            # Convert to PNG for Tkinter
            _, buffer = cv2.imencode(".png", img)
            data = buffer.tobytes()
            return tk.PhotoImage(data=data)
        except Exception as e:
            print(f"Error loading preview: {e}")
            return None

if __name__ == "__main__":
    app = GraphEditor(".")
    app.mainloop()
