import json
import uuid
from typing import List, Dict, Optional, Any

class Trigger:
    """
    Defines what causes a transition to happen.
    """
    def __init__(self, type: str, params: Dict[str, Any] = None):
        self.type = type
        self.params = params or {}

    def to_dict(self):
        return {"type": self.type, "params": self.params}

    @staticmethod
    def from_dict(data):
        return Trigger(data["type"], data.get("params"))

class Action:
    """
    Defines what happens when a transition occurs.
    """
    def __init__(self, type: str, params: Dict[str, Any] = None):
        self.type = type
        self.params = params or {}

    def to_dict(self):
        return {"type": self.type, "params": self.params}

    @staticmethod
    def from_dict(data):
        return Action(data["type"], data.get("params"))

class Edge:
    """
    A transition between two vertices (states).
    """
    def __init__(self, source_id: str, target_id: str, trigger: Trigger, action: Optional[Action] = None, id: str = None):
        self.id = id or str(uuid.uuid4())
        self.source_id = source_id
        self.target_id = target_id
        self.trigger = trigger
        self.action = action

    def to_dict(self):
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "trigger": self.trigger.to_dict(),
            "action": self.action.to_dict() if self.action else None
        }

    @staticmethod
    def from_dict(data):
        trigger = Trigger.from_dict(data["trigger"])
        action = Action.from_dict(data["action"]) if data.get("action") else None
        return Edge(
            source_id=data["source_id"],
            target_id=data["target_id"],
            trigger=trigger,
            action=action,
            id=data.get("id")
        )

class Vertex:
    """
    A state in the machine.
    """
    def __init__(self, name: str, description: str = "", template: str = None, id: str = None, is_start: bool = False):
        self.id = id or str(uuid.uuid4())
        self.name = name
        self.description = description
        self.template = template
        self.is_start = is_start

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "template": self.template,
            "is_start": self.is_start
        }

    @staticmethod
    def from_dict(data):
        return Vertex(
            name=data["name"],
            description=data.get("description", ""),
            template=data.get("template"),
            id=data.get("id"),
            is_start=data.get("is_start", False)
        )

class Graph:
    """
    The State Machine Graph containing Vertices and Edges.
    """
    def __init__(self):
        self.vertices: Dict[str, Vertex] = {}
        self.edges: List[Edge] = []

    def add_vertex(self, vertex: Vertex):
        self.vertices[vertex.id] = vertex

    def add_edge(self, edge: Edge):
        self.edges.append(edge)

    def get_start_vertex(self) -> Optional[Vertex]:
        for v in self.vertices.values():
            if v.is_start:
                return v
        return None

    def get_outgoing_edges(self, vertex_id: str) -> List[Edge]:
        return [e for e in self.edges if e.source_id == vertex_id]

    def to_json(self):
        return json.dumps({
            "vertices": [v.to_dict() for v in self.vertices.values()],
            "edges": [e.to_dict() for e in self.edges]
        }, indent=2)

    def save_to_file(self, filename: str):
        with open(filename, 'w') as f:
            f.write(self.to_json())

    @staticmethod
    def load_from_file(filename: str) -> 'Graph':
        with open(filename, 'r') as f:
            data = json.load(f)
        
        graph = Graph()
        for v_data in data.get("vertices", []):
            graph.add_vertex(Vertex.from_dict(v_data))
            
        for e_data in data.get("edges", []):
            graph.add_edge(Edge.from_dict(e_data))
            
        return graph
