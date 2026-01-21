import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
import win32gui
import uuid
import os

from ..selectors import RegionSelector, PointSelector
from .defs import THEME
from ..model import Trigger, Action, Edge, Vertex

class WindowSelectionDialog(ctk.CTkToplevel):
    def __init__(self, parent, matches):
        super().__init__(parent)
        self.parent = parent
        self.matches = matches
        self.selected_hwnd = None
        
        self.title("Select Game Window")
        self.geometry("500x400")
        self.transient(parent)
        self.grab_set()
        
        self._init_ui()
        
    def _init_ui(self):
        ctk.CTkLabel(self, text="Multiple game windows found. Please select one:", font=("Segoe UI", 14, "bold")).pack(pady=10)
        
        scroll = ctk.CTkScrollableFrame(self, width=450, height=250)
        scroll.pack(pady=10, padx=10)
        
        for i, (hwnd, title, rect) in enumerate(self.matches):
            btn_text = f"Window {i+1}: {title}\nres: {rect['width']}x{rect['height']} pos: ({rect['left']},{rect['top']})"
            ctk.CTkButton(scroll, text=btn_text, command=lambda h=hwnd: self.on_select(h), 
                          anchor="w", fg_color=THEME["node_bg"], hover_color=THEME["node_border"]).pack(fill="x", pady=2)
            
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        
    def on_select(self, hwnd):
        self.selected_hwnd = hwnd
        self.destroy()
        
    def on_cancel(self):
        self.selected_hwnd = None
        self.destroy()

class NodeEditorDialog(ctk.CTkToplevel):
    def __init__(self, parent, node_id):
        super().__init__(parent)
        self.parent = parent
        self.node_id = node_id
        self.vertex = parent.graph.vertices[node_id]
        
        self.title("Edit Node")
        self.geometry("400x320")
        self.transient(parent)
        self.grab_set()
        
        self.name_var = tk.StringVar(value=self.vertex.name)
        self.tmpl_var = tk.StringVar(value=self.vertex.template if self.vertex.template else "")
        self.preview_lbl = None
        
        self._init_ui()
        self.tmpl_var.trace("w", self.update_node_preview)
        self.update_node_preview()
        
    def _init_ui(self):
        ctk.CTkLabel(self, text="Name:").pack(pady=(10, 5))
        ctk.CTkEntry(self, textvariable=self.name_var, width=250).pack(pady=5)
        
        ctk.CTkLabel(self, text="Identity Template (Optional):").pack(pady=(15, 5))
        frame_tmpl = ctk.CTkFrame(self, fg_color="transparent")
        frame_tmpl.pack(pady=5)
        
        ctk.CTkEntry(frame_tmpl, textvariable=self.tmpl_var, width=200).pack(side=tk.LEFT, padx=(0, 10))
        ctk.CTkButton(frame_tmpl, text="Paste", command=self.paste_image, width=60).pack(side=tk.LEFT)
        self.bind("<Control-v>", lambda e: self.paste_image())
        
        self.preview_lbl = ctk.CTkLabel(self, text="")
        self.preview_lbl.pack(pady=10)
        
        ctk.CTkButton(self, text="Save", command=self.save, fg_color="#4CAF50", hover_color="#45a049").pack(pady=20)
        
    def update_node_preview(self, *args):
        fname = self.tmpl_var.get()
        # Ensure we call a method on parent that returns a CTkImage or PhotoImage
        if hasattr(self.parent, 'load_preview_image'):
             photo = self.parent.load_preview_image(fname)
             if photo:
                 self.preview_lbl.configure(image=photo, text="")
                 self.preview_lbl.image = photo
             else:
                 self.preview_lbl.configure(image=None, text="")

    def paste_image(self):
        if hasattr(self.parent, 'save_clipboard_image'):
            filename = self.parent.save_clipboard_image()
            if filename: 
                self.tmpl_var.set(filename)
            
    def save(self):
        self.vertex.name = self.name_var.get()
        t = self.tmpl_var.get()
        self.vertex.template = t if t else None
        self.destroy()
        self.parent.refresh_canvas()

class EdgeEditorDialog(ctk.CTkToplevel):
    def __init__(self, parent, source_id=None, target_id=None, edge=None, points=None):
        super().__init__(parent)
        self.parent = parent
        self.edge = edge
        self.source_id = source_id
        self.target_id = target_id
        self.points = points
        
        self.title("Edge Properties")
        self.geometry("500x800")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        # Vars
        self.trig_type_var = tk.StringVar(value="immediate")
        self.tmpl_var = tk.StringVar()
        self.invert_var = tk.BooleanVar()
        self.region_var = tk.StringVar(value="0,0,100,50")
        self.cond_var = tk.StringVar(value=">")
        self.val_var = tk.StringVar(value="0")
        self.ocr_interval_var = tk.StringVar(value="1.0")
        
        self.action_var = tk.StringVar(value="None")
        self.key_var = tk.StringVar()
        self.dur_var = tk.StringVar(value="0.05")
        self.wait_dur_var = tk.StringVar(value="0.5")
        self.buzzer_freq_var = tk.StringVar(value="600")
        self.buzzer_dur_var = tk.StringVar(value="0.5")
        self.x_var = tk.StringVar(value="0")
        self.y_var = tk.StringVar(value="0")
        self.mod_vars = {}
        
        self.conf_var = tk.StringVar(value="0.8")
        self.prio_var = tk.StringVar(value="0")

        self._init_vars_from_edge()
        self._init_ui()
        self.update_trig_ui()
        self.update_act_ui()
        
    def _init_vars_from_edge(self):
        if self.edge:
            self.trig_type_var.set(self.edge.trigger.type)
            p = self.edge.trigger.params
            if self.edge.trigger.type == "template_match":
                self.tmpl_var.set(p.get("template", ""))
                self.invert_var.set(p.get("invert", False))
                self.conf_var.set(str(p.get("threshold", 0.8)))

            elif self.edge.trigger.type == "ocr_watch":
                r = p.get("region", [0,0,100,50])
                self.region_var.set(f"{r[0]},{r[1]},{r[2]},{r[3]}")
                self.cond_var.set(p.get("condition", ">"))
                self.val_var.set(p.get("value", "0"))
                self.ocr_interval_var.set(str(p.get("interval", 1.0)))
                
            self.prio_var.set(str(self.edge.priority))
            
            if self.edge.action:
                self.action_var.set(self.edge.action.type)
                ap = self.edge.action.params
                self.key_var.set(ap.get("key", ""))
                self.dur_var.set(str(ap.get("duration", 0.05)))
                
                if self.edge.action.type == "wait":
                    self.wait_dur_var.set(str(ap.get("duration", 0.5)))
                if self.edge.action.type == "buzzer":
                    self.buzzer_freq_var.set(str(ap.get("frequency", 600)))
                    self.buzzer_dur_var.set(str(ap.get("duration", 0.5)))
                if self.edge.action.type == "click_position":
                    self.x_var.set(str(ap.get("x", 0)))
                    self.y_var.set(str(ap.get("y", 0)))
        else:
            self.action_var.set("None")

    def create_collapsible_section(self, parent, title, collapsed=False):
        wrapper = ctk.CTkFrame(parent, fg_color="transparent")
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
        
        inner = ctk.CTkFrame(content, fg_color="transparent")
        inner.pack(fill=tk.X, padx=10, pady=10)
            
        return wrapper, inner

    def _init_ui(self):
        # Trigger
        to, tf = self.create_collapsible_section(self, "Trigger Configuration", collapsed=False)
        to.pack(fill=tk.X, padx=10, pady=5)
        
        ctk.CTkLabel(tf, text="Type:").pack(anchor=tk.W)
        ctk.CTkOptionMenu(tf, variable=self.trig_type_var, values=["template_match", "ocr_watch", "immediate"]).pack(fill=tk.X, pady=2)
        
        self.trig_opts = ctk.CTkFrame(tf, fg_color="transparent")
        self.trig_opts.pack(fill=tk.X, pady=5)
        
        # Template Match UI
        self.tmpl_frame = ctk.CTkFrame(self.trig_opts, fg_color="transparent")
        ctk.CTkLabel(self.tmpl_frame, text="Template Image:").pack(anchor=tk.W)
        inner_tmpl = ctk.CTkFrame(self.tmpl_frame, fg_color="transparent")
        inner_tmpl.pack(fill=tk.X)
        ctk.CTkEntry(inner_tmpl, textvariable=self.tmpl_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ctk.CTkButton(inner_tmpl, text="Paste", command=self.paste_image, width=60).pack(side=tk.LEFT, padx=5)
        
        self.preview_label = ctk.CTkLabel(self.tmpl_frame, text="")
        self.preview_label.pack(pady=5)
        self.tmpl_var.trace("w", self.update_preview)
        
        ctk.CTkCheckBox(self.tmpl_frame, text="Invert Condition", variable=self.invert_var).pack(anchor=tk.W)
        
        # OCR Watch UI
        self.ocr_frame = ctk.CTkFrame(self.trig_opts, fg_color="transparent")
        ctk.CTkLabel(self.ocr_frame, text="Region (x, y, w, h):").pack(anchor=tk.W)
        
        ocr_row1 = ctk.CTkFrame(self.ocr_frame, fg_color="transparent")
        ocr_row1.pack(fill=tk.X)
        ctk.CTkEntry(ocr_row1, textvariable=self.region_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ctk.CTkButton(ocr_row1, text="Select", command=self.select_region, width=60).pack(side=tk.LEFT, padx=5)
        
        ocr_row2 = ctk.CTkFrame(self.ocr_frame, fg_color="transparent")
        ocr_row2.pack(fill=tk.X, pady=5)
        ctk.CTkOptionMenu(ocr_row2, variable=self.cond_var, values=[">", "<", "=", ">=", "<=", "!="], width=70).pack(side=tk.LEFT, padx=5)
        ctk.CTkEntry(ocr_row2, textvariable=self.val_var, width=60).pack(side=tk.LEFT, padx=5)
        
        ctk.CTkLabel(self.ocr_frame, text="Parse Interval (s):").pack(anchor=tk.W)
        ctk.CTkEntry(self.ocr_frame, textvariable=self.ocr_interval_var).pack(fill=tk.X)
        
        self.trig_type_var.trace("w", self.update_trig_ui)
        
        # Action
        ao, af = self.create_collapsible_section(self, "Action Configuration", collapsed=False)
        ao.pack(fill=tk.X, padx=10, pady=5)
        
        ctk.CTkLabel(af, text="Type:").pack(anchor=tk.W)
        ctk.CTkOptionMenu(af, variable=self.action_var, values=["None", "click_match", "press_key", "wait", "center_camera", "click_position", "buzzer"]).pack(fill=tk.X, pady=2)
        
        self.act_opts = ctk.CTkFrame(af, fg_color="transparent")
        self.act_opts.pack(fill=tk.X, pady=5)
        
        # Sub-frames for action
        self.key_frame = ctk.CTkFrame(self.act_opts, fg_color="transparent")
        ctk.CTkLabel(self.key_frame, text="Key:").pack(anchor=tk.W)
        ctk.CTkEntry(self.key_frame, textvariable=self.key_var).pack(fill=tk.X)
        ctk.CTkLabel(self.key_frame, text="Duration (s):").pack(anchor=tk.W)
        ctk.CTkEntry(self.key_frame, textvariable=self.dur_var).pack(fill=tk.X)
        
        self.wait_frame = ctk.CTkFrame(self.act_opts, fg_color="transparent")
        ctk.CTkLabel(self.wait_frame, text="Duration (s):").pack(anchor=tk.W)
        ctk.CTkEntry(self.wait_frame, textvariable=self.wait_dur_var).pack(fill=tk.X)
        
        self.buzzer_frame = ctk.CTkFrame(self.act_opts, fg_color="transparent")
        ctk.CTkLabel(self.buzzer_frame, text="Freq (Hz):").pack(anchor=tk.W)
        ctk.CTkEntry(self.buzzer_frame, textvariable=self.buzzer_freq_var).pack(fill=tk.X)
        ctk.CTkLabel(self.buzzer_frame, text="Duration (s):").pack(anchor=tk.W)
        ctk.CTkEntry(self.buzzer_frame, textvariable=self.buzzer_dur_var).pack(fill=tk.X)
        
        self.pos_frame = ctk.CTkFrame(self.act_opts, fg_color="transparent")
        ctk.CTkLabel(self.pos_frame, text="Position (x,y):").pack(anchor=tk.W)
        pos_inner = ctk.CTkFrame(self.pos_frame, fg_color="transparent")
        pos_inner.pack(fill=tk.X)
        ctk.CTkEntry(pos_inner, textvariable=self.x_var, width=80).pack(side=tk.LEFT)
        ctk.CTkButton(pos_inner, text="Select", command=self.select_point, width=60).pack(side=tk.LEFT, padx=5)
        # Note: Added y_var implicitly via next entry but I'll make it explicit
        ctk.CTkLabel(pos_inner, text=",").pack(side=tk.LEFT)
        ctk.CTkEntry(pos_inner, textvariable=self.y_var, width=80).pack(side=tk.LEFT)

        self.mods_frame_container = ctk.CTkFrame(self.act_opts, fg_color="transparent")
        ctk.CTkLabel(self.mods_frame_container, text="Modifiers:").pack(anchor=tk.W)
        mf = ctk.CTkFrame(self.mods_frame_container, fg_color="transparent")
        mf.pack(fill=tk.X)
        
        current_mods = []
        if self.edge and self.edge.action:
             raw = self.edge.action.params.get("modifiers", "")
             current_mods = [m.strip().lower() for m in raw.split(",") if m.strip()]
             
        for mk in ["alt", "ctrl", "shift"]:
            v = tk.BooleanVar(value=(mk in current_mods))
            self.mod_vars[mk] = v
            ctk.CTkCheckBox(mf, text=mk.capitalize(), variable=v).pack(side=tk.LEFT, padx=5)

        self.action_var.trace("w", self.update_act_ui)
        
        # Settings
        so, sf = self.create_collapsible_section(self, "Advanced Settings", collapsed=True)
        so.pack(fill=tk.X, padx=10, pady=5)
        
        r1 = ctk.CTkFrame(sf, fg_color="transparent")
        r1.pack(fill=tk.X)
        ctk.CTkLabel(r1, text="Confidence:").pack(side=tk.LEFT)
        ctk.CTkEntry(r1, textvariable=self.conf_var, width=60).pack(side=tk.LEFT, padx=5)
        ctk.CTkLabel(r1, text="Priority:").pack(side=tk.LEFT, padx=(20,0))
        ctk.CTkEntry(r1, textvariable=self.prio_var, width=60).pack(side=tk.LEFT, padx=5)
        
        ctk.CTkButton(self, text="Save Changes", command=self.save, fg_color="#4CAF50", hover_color="#45a049", font=("Arial", 14, "bold")).pack(pady=20, fill=tk.X, padx=20, ipady=5)
        self.bind("<Control-v>", lambda e: self.paste_image())

    def update_trig_ui(self, *args):
        self.tmpl_frame.pack_forget()
        self.ocr_frame.pack_forget()
        t = self.trig_type_var.get()
        if t == "template_match": self.tmpl_frame.pack(fill=tk.X)
        elif t == "ocr_watch": self.ocr_frame.pack(fill=tk.X)

    def update_act_ui(self, *args):
        self.key_frame.pack_forget()
        self.mods_frame_container.pack_forget()
        self.pos_frame.pack_forget()
        self.wait_frame.pack_forget()
        self.buzzer_frame.pack_forget()
        
        val = self.action_var.get()
        if val == "press_key":
            self.key_frame.pack(fill=tk.X, pady=2)
            self.mods_frame_container.pack(fill=tk.X, pady=2)
        elif val == "click_match":
            self.mods_frame_container.pack(fill=tk.X, pady=2)
        elif val == "click_position":
            self.pos_frame.pack(fill=tk.X, pady=2)
            self.mods_frame_container.pack(fill=tk.X, pady=2)
        elif val == "wait":
            self.wait_frame.pack(fill=tk.X, pady=2)
        elif val == "buzzer":
            self.buzzer_frame.pack(fill=tk.X, pady=2)
            
    def update_preview(self, *args):
        fname = self.tmpl_var.get()
        if hasattr(self.parent, 'load_preview_image'):
             photo = self.parent.load_preview_image(fname)
             if photo:
                 self.preview_label.configure(image=photo, text="")
                 self.preview_label.image = photo 
             else:
                 self.preview_label.configure(image=None, text="(No Image)" if fname else "")

    def paste_image(self):
        if hasattr(self.parent, 'save_clipboard_image'):
            filename = self.parent.save_clipboard_image()
            if filename: self.tmpl_var.set(filename)

    def select_region(self):
        hwnd = self.parent.resolve_game_window()
        self.parent.game_hwnd = hwnd # Sync back
        
        self.attributes('-alpha', 0.0)
        def on_select(rect):
            self.attributes('-alpha', 1.0)
            final_rect = list(rect)
            if hwnd and win32gui.IsWindow(hwnd):
                try:
                    from ..utils import get_client_rect_screen_coords
                    win_rect = get_client_rect_screen_coords(hwnd)
                    if win_rect:
                        final_rect[0] = rect[0] - win_rect['left']
                        final_rect[1] = rect[1] - win_rect['top']
                except: pass
            self.region_var.set(f"{final_rect[0]},{final_rect[1]},{final_rect[2]},{final_rect[3]}")
            self.deiconify()
        RegionSelector(self.parent, on_select) # Use parent as master for Selector usually, or self? Selector usually is fullscreen.

    def select_point(self):
        hwnd = self.parent.resolve_game_window()
        self.parent.game_hwnd = hwnd
        self.attributes('-alpha', 0.0)
        def on_point(pt):
            self.attributes('-alpha', 1.0)
            final_pt = list(pt)
            if hwnd and win32gui.IsWindow(hwnd):
                try:
                    from ..utils import get_client_rect_screen_coords
                    win_rect = get_client_rect_screen_coords(hwnd)
                    if win_rect:
                        final_pt[0] = pt[0] - win_rect['left']
                        final_pt[1] = pt[1] - win_rect['top']
                except: pass
            self.x_var.set(str(final_pt[0]))
            self.y_var.set(str(final_pt[1]))
            self.deiconify()
        PointSelector(self.parent, on_point)

    def save(self):
        # Validation and Save
        try:
             # Capture Window Resolution
             res_w, res_h = 1920, 1080
             target_hwnd = self.parent.game_hwnd
             if target_hwnd and win32gui.IsWindow(target_hwnd):
                 rect = win32gui.GetClientRect(target_hwnd)
                 res_w = rect[2] - rect[0]
                 res_h = rect[3] - rect[1]
             
             trig_type = self.trig_type_var.get()
             t_params = {}
             if trig_type == "template_match":
                 t_params = {
                     "template": self.tmpl_var.get(),
                     "threshold": float(self.conf_var.get()),
                     "invert": self.invert_var.get()
                 }
             elif trig_type == "ocr_watch":
                 r = [int(x) for x in self.region_var.get().split(",")]
                 t_params = {
                     "region": r,
                     "condition": self.cond_var.get(),
                     "value": float(self.val_var.get()),
                     "interval": float(self.ocr_interval_var.get()),
                     "resolution_width": res_w,
                     "resolution_height": res_h
                 }
                 
             trigger = Trigger(trig_type, t_params)
             
             act_type = self.action_var.get()
             action = None
             if act_type != "None":
                 a_params = {}
                 mods = [k for k, v in self.mod_vars.items() if v.get()]
                 if mods: a_params["modifiers"] = ", ".join(mods)
                 
                 if act_type == "press_key":
                     a_params["key"] = self.key_var.get()
                     a_params["duration"] = float(self.dur_var.get())
                 elif act_type == "click_position":
                     a_params["x"] = int(self.x_var.get())
                     a_params["y"] = int(self.y_var.get())
                     a_params["resolution_width"] = res_w
                     a_params["resolution_height"] = res_h
                 elif act_type == "wait":
                     a_params["duration"] = float(self.wait_dur_var.get())
                 elif act_type == "buzzer":
                     a_params["frequency"] = int(self.buzzer_freq_var.get())
                     a_params["duration"] = float(self.buzzer_dur_var.get())
                     
                 action = Action(act_type, a_params)
             
             prio = int(self.prio_var.get())
             
             if self.edge:
                 self.edge.trigger = trigger
                 self.edge.action = action
                 self.edge.priority = prio
             else:
                 new_edge = Edge(self.source_id, self.target_id, trigger, action, priority=prio, points=self.points)
                 self.parent.graph.add_edge(new_edge)
                 
             self.destroy()
             self.parent.refresh_canvas()
             
        except Exception as e:
            messagebox.showerror("Error", f"Invalid parameters: {e}")

