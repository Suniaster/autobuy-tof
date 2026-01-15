from .input import ClickMatchAction, PressKeyAction, WaitAction, ClickPositionAction
from .camera import CenterCameraAction

def execute_action(action_data, context, executor):
    handler = None
    if action_data.type == "click_match":
        handler = ClickMatchAction(action_data.params)
    elif action_data.type == "press_key":
        handler = PressKeyAction(action_data.params)
    elif action_data.type == "wait":
        handler = WaitAction(action_data.params)
    elif action_data.type == "click_position":
        handler = ClickPositionAction(action_data.params)    
    elif action_data.type == "center_camera":
        handler = CenterCameraAction(action_data.params)

    if handler:
        handler.execute(context, executor)
