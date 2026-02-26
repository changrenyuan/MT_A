from abc import ABC, abstractmethod

class BaseStrategy(ABC):
    @abstractmethod
    def on_bar(self, bar, account):
        """每个K线周期调用一次"""
        pass