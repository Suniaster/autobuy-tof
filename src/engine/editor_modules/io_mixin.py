import tkinter as tk
from tkinter import filedialog, messagebox
import json
import os
import uuid
import zipfile
import win32clipboard
import struct
import cv2
import numpy as np
from PIL import Image
import customtkinter as ctk

from ..model import Graph

class IOMixin:
    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r") as f:
                    cfg = json.load(f)
                    geom = cfg.get("geometry", "1400x900")
                    self.geometry(geom)
        except Exception as e:
            print(f"Failed to load config: {e}")

    def save_config(self):
        try:
            cfg = {"geometry": self.geometry()}
            with open(self.config_file, "w") as f:
                json.dump(cfg, f, indent=4)
        except Exception as e:
            print(f"Failed to save config: {e}")

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
                
                # Update UI vars from settings
                if hasattr(self, 'var_bg_mode'):
                    self.var_bg_mode.set(self.graph.settings.get("background_mode", False))
                
                self.refresh_canvas()
            except Exception as e:
                messagebox.showerror("Error", str(e))

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
