
import tkinter as tk
import customtkinter as ctk

class RegionSelector(ctk.CTkToplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback
        self.attributes('-fullscreen', True)
        self.attributes('-topmost', True)
        self.attributes('-alpha', 0.3)
        self.configure(bg="black")
        
        self.canvas = tk.Canvas(self, cursor="cross", bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.start_x = None
        self.start_y = None
        self.rect = None
        
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Escape>", lambda e: self.destroy())
        
        # Force focus and grab
        self.wait_visibility(self)
        self.attributes('-alpha', 0.3)
        self.focus_force()
        self.grab_set()

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="red", width=2)
        
    def on_drag(self, event):
        if self.start_x:
            self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)
            
    def on_release(self, event):
        if self.start_x:
            x1 = min(self.start_x, event.x)
            y1 = min(self.start_y, event.y)
            x2 = max(self.start_x, event.x)
            y2 = max(self.start_y, event.y)
            w = x2 - x1
            h = y2 - y1
            
            if w > 5 and h > 5:
                # Callback with [x, y, w, h]
                # Note: These are screen coordinates relative to this fullscreen window
                self.callback([x1, y1, w, h])
                self.destroy()
            else:
                self.canvas.delete(self.rect)
                self.start_x = None

class PointSelector(ctk.CTkToplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback
        self.attributes('-fullscreen', True)
        self.attributes('-topmost', True)
        self.attributes('-alpha', 0.3)
        self.configure(bg="black")
        
        self.canvas = tk.Canvas(self, cursor="target", bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.canvas.bind("<Button-1>", self.on_click)
        self.bind("<Escape>", lambda e: self.destroy())

        # Force focus and grab
        self.wait_visibility(self)
        self.attributes('-alpha', 0.3)
        self.focus_force()
        self.grab_set()
        
    def on_click(self, event):
        self.callback([event.x, event.y])
        self.destroy()
