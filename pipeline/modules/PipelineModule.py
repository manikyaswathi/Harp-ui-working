import abc

class PipelineModule(abc.ABC):
    def __init__(self):
        self.name = "default"
        self.application = "default"

    @abc.abstractmethod
    def execute(self):
        pass