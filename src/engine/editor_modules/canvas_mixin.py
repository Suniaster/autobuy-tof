import tkinter as tk
import customtkinter as ctk
import math
from .defs import THEME
from ..model import Trigger, Action, Edge, Vertex
from .dialogs import NodeEditorDialog, EdgeEditorDialog

class CanvasMixin:
    def create_canvas(self):
        self.canvas = tk.Canvas(self, bg=THEME["bg_canvas"], highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Interactions
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_right_click)
        
        # Pan
        self.canvas.bind("<ButtonPress-2>", self.start_pan)
        self.canvas.bind("<B2-Motion>", self.continue_pan)
        self.canvas.bind("<ButtonRelease-2>", self.end_pan)
        
        # Zoom
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        
        # Cancellation
        self.bind("<Escape>", self.on_cancel)
        self.bind("<Delete>", lambda e: self.on_cancel(e))

    def refresh_canvas(self):
        self.canvas.delete("all")
        self.draw_grid()
        
        for edge in self.graph.edges:
            p1 = self.node_coords.get(edge.source_id) if edge.source_id else None
            p2 = self.node_coords.get(edge.target_id) if edge.target_id else None
            self.draw_edge(p1, p2, edge)
            
        for v_id, vertex in self.graph.vertices.items():
            x, y = self.node_coords.get(v_id, (100, 100))
            self.draw_node(x, y, vertex)

    def draw_grid(self):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        
        grid_size = 50 * self.scale
        if grid_size < 10: return
        
        start_x = self.offset_x % grid_size
        start_y = self.offset_y % grid_size
        
        for i in range(int(w / grid_size) + 1):
            for j in range(int(h / grid_size) + 1):
                px = start_x + (i * grid_size)
                py = start_y + (j * grid_size)
                self.canvas.create_oval(px-1, py-1, px+1, py+1, fill=THEME["grid"], outline="")

    def draw_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        points = [x1+radius, y1, x1+radius, y1, x2-radius, y1, x2-radius, y1, x2, y1,
                  x2, y1+radius, x2, y1+radius, x2, y2-radius, x2, y2-radius, x2, y2,
                  x2-radius, y2, x2-radius, y2, x1+radius, y2, x1+radius, y2, x1, y2,
                  x1, y2-radius, x1, y2-radius, x1, y1+radius, x1, y1+radius, x1, y1]
        return self.canvas.create_polygon(points, smooth=True, **kwargs)

    def draw_node(self, wx, wy, vertex):
        sx, sy = self.world_to_screen(wx, wy)
        w = self.node_width * self.scale
        h = self.node_height * self.scale
        
        x1, y1, x2, y2 = sx - w/2, sy - h/2, sx + w/2, sy + h/2
        
        bg_color = THEME["node_bg"]
        outline_color = THEME["node_border"]
        text_color = THEME["text_main"]
        border_w = 1 * max(1, self.scale)
        accent = THEME["accent_cyan"]
        status_text = "Idle"
        
        if vertex.is_start:
            accent = THEME["accent_emerald"]
            status_text = "Start"
            
        if vertex.id == self.active_node_id:
            outline_color = THEME["accent_purple"]
            border_w = 2 * max(1, self.scale)
            self.draw_rounded_rect(x1-2, y1-2, x2+2, y2+2, 10*self.scale, fill=THEME["accent_purple"], outline="")
            status_text = "Running..."
        elif self.selected_item == ("node", vertex.id):
             outline_color = THEME["accent_cyan"]
             border_w = 2 * max(1, self.scale)

        tag = f"node:{vertex.id}"
        r = 10 * self.scale
        self.draw_rounded_rect(x1, y1, x2, y2, r, fill=bg_color, outline=outline_color, width=border_w, tags=tag)
        
        bar_w = 4 * self.scale
        self.canvas.create_rectangle(x1, y1+r/2, x1+bar_w, y2-r/2, fill=accent, outline="", tags=tag)
        
        icon_r = 8 * self.scale
        icon_x = x1 + 20 * self.scale
        self.canvas.create_oval(icon_x-icon_r, sy-icon_r, icon_x+icon_r, sy+icon_r, fill=THEME["bg_canvas"], outline=accent, width=1, tags=tag)
        
        title_font_size = int(10 * self.scale)
        self.canvas.create_text(icon_x + 15*self.scale, sy - 5*self.scale, text=vertex.name, anchor="w", fill=text_color, font=("Segoe UI", title_font_size, "bold"), tags=tag)
        
        sub_font_size = int(8 * self.scale)
        self.canvas.create_text(icon_x + 15*self.scale, sy + 8*self.scale, text=status_text, anchor="w", fill=THEME["text_sub"], font=("Segoe UI", sub_font_size), tags=tag)

    def draw_edge(self, p1, p2, edge):
        sx1, sy1 = (0,0)
        if p1: sx1, sy1 = self.world_to_screen(p1[0], p1[1])
        elif edge.points and len(edge.points) >= 2: sx1, sy1 = self.world_to_screen(edge.points[0], edge.points[1])
        else: return

        sx2, sy2 = (0,0)
        if p2: sx2, sy2 = self.world_to_screen(p2[0], p2[1])
        elif edge.points and len(edge.points) >= 4: sx2, sy2 = self.world_to_screen(edge.points[2], edge.points[3])
        else: return

        tag = f"edge:{edge.id}"
        color = THEME["text_sub"]
        width = 2 * self.scale
        arrow_shape = (10*self.scale, 12*self.scale, 4*self.scale)
        
        if self.selected_item == ("edge", edge.id):
             color = THEME["accent_cyan"]
             width = 3 * self.scale
        
        mid_x, mid_y = (sx1+sx2)/2, (sy1+sy2)/2

        if edge.source_id and edge.source_id == edge.target_id:
            node_half_h = (self.node_height / 2) * self.scale
            top_y = sy1 - node_half_h
            points = [sx1 - 10*self.scale, top_y, sx1 - 40*self.scale, top_y - 40*self.scale,
                      sx1 + 40*self.scale, top_y - 40*self.scale, sx1 + 10*self.scale, top_y]
            self.canvas.create_line(points, arrow=tk.LAST, arrowshape=arrow_shape, width=width, fill=color, tags=tag, smooth=True)
            mid_y = sy1 - 65*self.scale
        else:
             # Intersection logic simplified
             dx, dy = sx2-sx1, sy2-sy1
             dist = math.hypot(dx, dy)
             if dist == 0: return
             ux, uy = dx/dist, dy/dist
             w, h = self.node_width * self.scale, self.node_height * self.scale
             
             def get_box_intersect(ux, uy):
                 t = min((w/2)/abs(ux) if ux!=0 else float('inf'), (h/2)/abs(uy) if uy!=0 else float('inf'))
                 return t

             start_offset = (get_box_intersect(ux, uy) + 5*self.scale) if p1 else 0
             end_offset = (get_box_intersect(-ux, -uy) + 5*self.scale) if p2 else 0
             
             self.canvas.create_line(sx1 + ux*start_offset, sy1 + uy*start_offset, sx2 - ux*end_offset, sy2 - uy*end_offset,
                                     arrow=tk.LAST, arrowshape=arrow_shape, width=width, fill=color, tags=tag)

        handle_r = 4 * self.scale
        self.canvas.create_oval(sx1-handle_r, sy1-handle_r, sx1+handle_r, sy1+handle_r, fill=THEME["accent_cyan"], outline="", tags=(f"handle:{edge.id}:source", tag))
        self.canvas.create_oval(sx2-handle_r, sy2-handle_r, sx2+handle_r, sy2+handle_r, fill=THEME["accent_emerald"], outline="", tags=(f"handle:{edge.id}:target", tag))

        label = edge.trigger.type
        if edge.trigger.type == "template_match":
            label = "(!)" if edge.trigger.params.get("invert") else ""
        elif edge.trigger.type == "ocr_watch":
            label = f"OCR {edge.trigger.params.get('condition','>')} {edge.trigger.params.get('value',0)}"
        elif edge.trigger.type == "immediate": label = ">>>"
        elif edge.trigger.type == "wait": label = "Wait"
        
        if edge.action:
             if edge.action.type == "press_key": label += f"\n[{edge.action.params.get('key','')}]"
             elif edge.action.type == "click_position": label += f"\n[{edge.action.params.get('x',0)},{edge.action.params.get('y',0)}]"
             elif edge.action.type == "buzzer": label += "\n[Buzzer]"

        if edge.source_id != edge.target_id: mid_y -= 10 * self.scale
        
        if label:
            self.canvas.create_text(mid_x, mid_y, text=label, fill=THEME["accent_cyan"], font=("Segoe UI", int(9*self.scale), "bold"), tags=tag)

    # --- Interaction Logic ---
    def on_click(self, event):
        item = self.canvas.find_closest(event.x, event.y)
        tags = self.canvas.gettags(item)
        clicked_type, clicked_id = None, None
        
        for tag in tags:
            if tag.startswith("handle:"):
                # "handle:edge_id:source"
                _, eid, end = tag.split(":", 2) 
                self.edge_drag = (eid, end)
                self.set_mode("REWIRE")
                return
            elif tag.startswith("node:"): clicked_type, clicked_id = "node", tag.split(":")[1]
            elif tag.startswith("edge:"): clicked_type, clicked_id = "edge", tag.split(":")[1]

        wx, wy = self.screen_to_world(event.x, event.y)
        
        if self.mode == "CONNECT":
            if not self.creating_edge:
                self.creating_edge = True
                self.creation_start = ("node", clicked_id) if clicked_type == "node" else ("point", (wx, wy))
            else:
                s_type, s_val = self.creation_start
                source_id = s_val if s_type == "node" else None
                points = [s_val[0], s_val[1]] if s_type == "point" else None
                
                target_id = clicked_id if clicked_type == "node" else None
                
                # Logic for points...
                if clicked_type == "node" and points: points.extend([wx, wy])
                elif not clicked_type: # Target Point
                     if not points: # Node->Point
                         nx, ny = self.node_coords[source_id]
                         points = [nx+self.node_width/2, ny+self.node_height/2, wx, wy]
                     else: points.extend([wx, wy])

                new_edge = Edge(source_id, target_id, Trigger("immediate"), Action("None"), points=points)
                self.graph.add_edge(new_edge)
                
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
            
        self.selected_item = (clicked_type, clicked_id) if clicked_type else None
        self.refresh_canvas()
        if clicked_type == "node":
            self.drag_data["item"] = clicked_id
            self.drag_data["drag_start_screen"] = (event.x, event.y)
            self.drag_data["node_start_world"] = self.node_coords[clicked_id]

    def on_drag(self, event):
        wx, wy = self.screen_to_world(event.x, event.y)
        
        if self.mode == "REWIRE" and self.edge_drag:
             eid, end = self.edge_drag
             edge = next((e for e in self.graph.edges if e.id == eid), None)
             if edge:
                 if not edge.points: 
                     p1 = self.node_coords.get(edge.source_id, (0,0))
                     p2 = self.node_coords.get(edge.target_id, (0,0))
                     edge.points = [p1[0], p1[1], p2[0], p2[1]]
                 
                 idx = 0 if end == "source" else 2
                 if len(edge.points) < 4: edge.points.extend([0,0])
                 edge.points[idx] = wx
                 edge.points[idx+1] = wy
                 self.refresh_canvas()
             return

        if self.mode == "CONNECT" and self.creating_edge and self.creation_start:
             s_type, s_val = self.creation_start
             sx, sy = 0, 0
             if s_type == "node":
                 world = self.node_coords.get(s_val, (0,0))
                 sx, sy = self.world_to_screen(world[0]+self.node_width/2, world[1]+self.node_height/2)
             else:
                 sx, sy = self.world_to_screen(s_val[0], s_val[1])
                 
             self.canvas.delete("temp_line")
             self.canvas.create_line(sx, sy, event.x, event.y, dash=(2,2), fill=THEME["accent_cyan"], tags="temp_line")
             return

        if self.mode == "SELECT" and self.drag_data["item"]:
             dx = (event.x - self.drag_data["drag_start_screen"][0]) / self.scale
             dy = (event.y - self.drag_data["drag_start_screen"][1]) / self.scale
             start_wx, start_wy = self.drag_data["node_start_world"]
             self.node_coords[self.drag_data["item"]] = (start_wx + dx, start_wy + dy)
             self.refresh_canvas()

    def on_release(self, event):
        if self.mode == "REWIRE" and self.edge_drag:
            # Snap logic can be added here
            self.edge_drag = None
            self.set_mode("SELECT")
            self.refresh_canvas()
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

    def on_cancel(self, event):
        self.creating_edge = False
        self.creation_start = None
        self.edge_drag = None
        self.drag_data["item"] = None
        self.canvas.delete("temp_line")
        self.refresh_canvas()
        self.set_mode("SELECT")

    def world_to_screen(self, wx, wy):
        return (wx * self.scale) + self.offset_x, (wy * self.scale) + self.offset_y

    def screen_to_world(self, sx, sy):
        return (sx - self.offset_x) / self.scale, (sy - self.offset_y) / self.scale

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
        old_scale = self.scale
        self.scale *= 1.1 if event.delta > 0 else 0.9
        self.scale = max(0.2, min(self.scale, 5.0))
        
        wx = (event.x - self.offset_x) / old_scale
        wy = (event.y - self.offset_y) / old_scale
        self.offset_x = event.x - wx * self.scale
        self.offset_y = event.y - wy * self.scale
        self.refresh_canvas()

    def auto_layout(self):
        i = 0
        for v_id in self.graph.vertices:
            self.node_coords[v_id] = (150 + (i % 4) * 200, 100 + (i // 4) * 200)
            i += 1

    # --- Wrapper Actions ---
    def edit_node(self, node_id):
        NodeEditorDialog(self, node_id)
        
    def edit_edge(self, edge_id):
        edge = next((e for e in self.graph.edges if e.id == edge_id), None)
        if edge: EdgeEditorDialog(self, edge=edge)

    def delete_node(self, node_id):
        self.graph.edges = [e for e in self.graph.edges if e.source_id != node_id and e.target_id != node_id]
        if node_id in self.graph.vertices: del self.graph.vertices[node_id]
        if node_id in self.node_coords: del self.node_coords[node_id]
        self.selected_item = None
        self.refresh_canvas()

    def delete_edge(self, edge_id):
        self.graph.edges = [e for e in self.graph.edges if e.id != edge_id]
        self.selected_item = None
        self.refresh_canvas()
        
    def set_start_node(self, node_id):
        for v in self.graph.vertices.values():
            v.is_start = (v.id == node_id)
        self.refresh_canvas()

    def add_node(self, wx, wy):
        dialog = ctk.CTkInputDialog(text="Node Name:", title="Input")
        name = dialog.get_input()
        if name:
            v = Vertex(name)
            self.graph.add_vertex(v)
            self.node_coords[v.id] = (wx, wy)
            self.refresh_canvas()
