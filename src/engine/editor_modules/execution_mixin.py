import threading
import time
import keyboard
import win32gui
import tkinter as tk
from tkinter import messagebox
from .defs import THEME, GAME_TITLE_KEYWORD
from ..executor import GraphExecutor
from .dialogs import WindowSelectionDialog

class ExecutionMixin:
    def toggle_run(self):
        if self.is_running:
            # STOP
            if self.executor:
                self.executor.stop()
            self.is_running = False
            if hasattr(self, 'btn_run'):
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
                hwnd = self.game_hwnd
            else:
                hwnd = self.resolve_game_window()
                
            if not hwnd:
                messagebox.showerror("Error", f"Game window '{GAME_TITLE_KEYWORD}' not found!")
                return
                
            self.game_hwnd = hwnd

            self.is_running = True
            if hasattr(self, 'btn_run'):
                self.btn_run.configure(text="⏹", fg_color=THEME["accent_rose"])
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
            self.after(0, lambda: self.update_pause_ui(self.executor.paused))

    def update_pause_ui(self, is_paused):
        if is_paused:
            if hasattr(self, 'btn_run'):
                self.btn_run.configure(text="⏸", fg_color=THEME["accent_cyan"])
            self.update_status("Paused")
        else:
            if hasattr(self, 'btn_run'):
                self.btn_run.configure(text="⏹", fg_color=THEME["accent_rose"])
            self.update_status("Running...")

    def run_executor_thread(self):
        try:
            self.executor.run()
        except Exception as e:
            print(f"Executor Error: {e}")
            self.is_running = False
            self.after(0, lambda: messagebox.showerror("Error", f"Runtime Error: {e}"))
            if hasattr(self, 'btn_run'):
                self.after(0, lambda: self.btn_run.configure(text="▶", fg_color=THEME["accent_emerald"]))
        finally:
             if self.executor:
                 self.cached_ocr_reader = self.executor.ocr_reader
    
    def on_executor_state_change(self, node_id):
        self.active_node_id = node_id
        self.after(0, self.refresh_canvas)

    def check_execution_queue(self):
        pass

    def resolve_game_window(self, force_ask=False):
        from ..utils import find_all_game_windows
        
        matches = find_all_game_windows(GAME_TITLE_KEYWORD)
        
        if not matches:
             return None
        
        if len(matches) == 1 and not force_ask:
            return matches[0][0]
        
        # Open Dialog
        dialog = WindowSelectionDialog(self, matches)
        self.wait_window(dialog)
        return dialog.selected_hwnd

    def select_target_window(self):
        hwnd = self.resolve_game_window(force_ask=True)
        if hwnd:
            self.game_hwnd = hwnd
            try:
                title = win32gui.GetWindowText(hwnd)
                messagebox.showinfo("Target Selected", f"Target set to:\n{title}\n(HWND: {hwnd})")
            except:
                messagebox.showinfo("Target Selected", f"Target set to HWND: {hwnd}")
