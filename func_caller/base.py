from abc import ABC, abstractmethod

class FuncCaller(ABC):
    @abstractmethod
    def get_point(self) -> str:
        pass

    @abstractmethod
    def arm_move(self, type: str) -> str:
        pass

    @abstractmethod
    def goto_poi(self, name: str) -> str:
        pass