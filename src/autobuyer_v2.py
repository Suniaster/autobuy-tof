import argparse
import sys
import os
import time
import keyboard
import threading
from helper.input_utils import is_admin, focus_window
from engine.executor import GraphExecutor
from engine.model import Graph
from engine.editor import GraphEditor

# Configuration
DEFAULT_GRAPH_FILE = "graph.json"
GAME_TITLE_KEYWORD = "Tower of Fantasy"

def get_asset_path(filename=""):
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
        return os.path.join(base_path, "assets", "autobuyer", filename)
    else:
        base_path = os.path.dirname(os.path.realpath(__file__))
        # src/../assets/autobuyer -> assets/autobuyer
        return os.path.join(base_path, "..", "assets", "autobuyer", filename)

def launch_editor(graph_file, assets_dir):
    print("Launching Editor...")
    editor = GraphEditor(assets_dir)
    if os.path.exists(graph_file):
        try:
            editor.graph = Graph.load_from_file(graph_file)
            if os.path.exists(graph_file + ".layout"):
                import json
                with open(graph_file + ".layout", "r") as f:
                    editor.node_coords = json.load(f)
            else:
                editor.auto_layout()
            editor.refresh_canvas()
        except Exception as e:
            print(f"Error loading graph: {e}")
            
    editor.mainloop()

def main():
    parser = argparse.ArgumentParser(description="Autobuyer V2 - Graph Based")
    parser.add_argument("--run", action="store_true", help="Launch the Graph Runner (Autobuyer)")
    parser.add_argument("--graph", type=str, default=DEFAULT_GRAPH_FILE, help="Path to graph JSON file")
    args = parser.parse_args()

    # Resolve graph path relative to script if not absolute
    graph_path = args.graph
    if not os.path.isabs(graph_path):
        graph_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", graph_path)

    templates_dir = get_asset_path()

    if not args.run:
        launch_editor(graph_path, templates_dir)
        return

    # Runner Mode
    if not is_admin():
        print("WARNING: Script expects Admin privileges.")
        time.sleep(2)

    if not os.path.exists(graph_path):
        print(f"Error: Graph file '{graph_path}' not found!")
        print("Run normally (without --run) to create one in the editor.")
        return

    try:
        graph = Graph.load_from_file(graph_path)
    except Exception as e:
        print(f"Failed to load graph: {e}")
        return

    from engine.utils import get_client_rect_screen_coords, find_all_game_windows
    import win32gui

    print("Waiting for game window...")
    print("Waiting for game window...")
    hwnd = None
    
    # Wait until at least one window is found
    while not hwnd:
        windows = find_all_game_windows(GAME_TITLE_KEYWORD)
        if not windows:
             time.sleep(1)
             continue
        
        if len(windows) == 1:
            hwnd = windows[0][0]
        else:
            print(f"\nMultiple windows found for '{GAME_TITLE_KEYWORD}':")
            for i, (h, title, rect) in enumerate(windows):
                print(f"{i+1}: {title} (HWND: {h}) - {rect['width']}x{rect['height']} at ({rect['left']},{rect['top']})")
            
            while True:
                try:
                    val = input("Select Window Index (1-N): ").strip()
                    idx = int(val) - 1
                    if 0 <= idx < len(windows):
                        hwnd = windows[idx][0]
                        break
                    else:
                        print("Invalid index.")
                except ValueError:
                    # If user just hits enter or invalid input, refresh list? 
                    # For now just loop prompt.
                    pass


    print(f"Game found: {hwnd}")
    
    templates_dir = get_asset_path()
    executor = GraphExecutor(graph, hwnd, templates_dir)
    
    # Hotkeys
    def toggle_pause():
        executor.running = not executor.running
        state = "RESUMED" if executor.running else "PAUSED"
        print(f"[{state}]")

    keyboard.add_hotkey('f1', toggle_pause)
    keyboard.add_hotkey('f2', lambda: executor.stop())

    print("Press F1 to Pause/Resume, F2 to Stop.")
    
    try:
        executor.run()
    except KeyboardInterrupt:
        pass
    finally:
        executor.stop()
        keyboard.unhook_all()

if __name__ == "__main__":
    main()
