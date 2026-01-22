from .template import TemplateMatchTrigger
from .ocr import OCRWatchTrigger
from .color import ColorMatchTrigger

def check_trigger(trigger_data, context, executor):
    handler = None
    if trigger_data.type == "template_match":
        handler = TemplateMatchTrigger(trigger_data.params)
    elif trigger_data.type == "ocr_watch":
        handler = OCRWatchTrigger(trigger_data.params)
    elif trigger_data.type == "color_match":
        handler = ColorMatchTrigger(trigger_data.params)
    elif trigger_data.type == "immediate":
        return True
    elif trigger_data.type == "wait":
        # Wait triggers are usually handled as actions or logic, 
        # but if used as a transition trigger it might mean "after X time in state"
        # The original code passed on "wait", so we return False or handle it if logic existed.
        # Original: "pass" -> return False implicitly.
        return False

    if handler:
        return handler.check(context, executor)
    return False
