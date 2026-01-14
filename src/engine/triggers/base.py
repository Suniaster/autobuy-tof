from abc import ABC, abstractmethod

class Trigger(ABC):
    @abstractmethod
    def check(self, context, executor):
        """
        Check if the trigger condition is met.
        :param context: Dict containing current frame 'img', 'scale', 'sct'
        :param executor: The GraphExecutor instance
        :return: Boolean
        """
        pass
