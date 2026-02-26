from abc import ABC, abstractmethod
import pandas as pd

class BaseDataProvider(ABC):
    @abstractmethod
    def get_data(self, symbol: str) -> pd.DataFrame:
        pass