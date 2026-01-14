from abc import ABC, abstractmethod

class Action(ABC):
    @abstractmethod
    def execute(self, context, executor):
        """
        Execute the action.
        :param context: Dict containing 'monitor', 'sct'
        :param executor: The GraphExecutor instance
        """
        pass
