try:
    import winsound
except ImportError:
    winsound = None

from .base import Action

class BuzzerAction(Action):
    def __init__(self, params):
        self.frequency = int(params.get("frequency", 600))
        self.duration_sec = float(params.get("duration", 0.5))
        
    def execute(self, context, executor):
        if winsound:
            # winsound.Beep takes milliseconds
            winsound.Beep(self.frequency, int(self.duration_sec * 1000))
        else:
            print("BuzzerAction: winsound not available (not on Windows?)")
