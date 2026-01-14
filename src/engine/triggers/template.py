from .base import Trigger
from ..utils import match_template_multiscale

class TemplateMatchTrigger(Trigger):
    def __init__(self, params):
        self.template_name = params.get("template")
        self.threshold = params.get("threshold", 0.8)
        self.invert = params.get("invert", False)

    def check(self, context, executor):
        img = context.get('img')
        scale = context.get('scale')
        
        tmpl = executor.load_template(self.template_name)
        if tmpl is None: return False
        
        val, loc, _, _ = match_template_multiscale(img, tmpl, scale)
        
        found = (val >= self.threshold)
        
        if found:
            # Store match info on executor for actions to use
            executor.last_match_loc = loc
            executor.last_match_size = (executor.template_cache[self.template_name].shape[1], 
                                      executor.template_cache[self.template_name].shape[0])
            executor.last_matched_template_name = self.template_name
        
        if self.invert:
            return not found
        else:
            return found
