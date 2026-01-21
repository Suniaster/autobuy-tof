import tkinter as tk
import customtkinter as ctk
import os

from .model import Graph
from .editor_modules.defs import THEME
from .editor_modules.canvas_mixin import CanvasMixin
from .editor_modules.io_mixin import IOMixin
from .editor_modules.execution_mixin import ExecutionMixin

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class GraphEditor(ctk.CTk, CanvasMixin, IOMixin, ExecutionMixin):
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
        
        self.selected_item = None # (type, id)
        self.drag_data = {"x": 0, "y": 0, "item": None, "pan_start": None, "drag_start_screen": None, "node_start_world": None}
        
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
        self.connecting_node = None
        self.creation_start = None # (type, id/coords)
        self.creating_edge = False
        self.edge_drag = None # (edge_id, "source"|"target")
        self.node_coords = {}
        
        # UI Layout
        self.create_menu()
        self.create_canvas()
        self.create_toolbar()
        
        # Config Persistence
        self.config_file = os.path.join(self.assets_dir, "editor_config.json")
        self.load_config()
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)

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

        # Settings Menu
        settings_menu = tk.Menu(menubar, tearoff=0)
        self.var_bg_mode = tk.BooleanVar(value=self.graph.settings.get("background_mode", False))
        
        def on_bg_mode_toggle():
            self.graph.settings["background_mode"] = self.var_bg_mode.get()
            
        settings_menu.add_checkbutton(label="Run in Background (Experimental)", 
                                      variable=self.var_bg_mode, 
                                      command=on_bg_mode_toggle)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        
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

    def update_status(self, text):
        self.status_lbl.configure(text=text)

    def set_mode(self, mode):
        self.mode = mode
        self.mode_label.configure(text=mode)
        self.selected_item = None
        self.creating_edge = False
        self.refresh_canvas()
        
        cursor_map = {
            "SELECT": "arrow",
            "ADD_NODE": "cross",
            "CONNECT": "tcross",
            "DELETE": "X_cursor"
        }
        self.canvas.config(cursor=cursor_map.get(mode, "arrow"))

    def new_graph(self):
        self.graph = Graph()
        self.node_coords = {}
        self.active_node_id = None
        self.refresh_canvas()
        self.update_status("New Graph Created")

    def on_close(self):
        self.save_config()
        self.destroy()
        self.check_execution_queue()

if __name__ == "__main__":
    app = GraphEditor(".")
    app.mainloop()
