"""
策略基类模块 - 支持多股票信号
"""

from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    """策略基类"""
    
    def __init__(self):
        self.actions = []  # 记录交易动作
    
    @abstractmethod
    def on_bar(self, bar, account, symbol=None):
        """
        每个K线周期调用一次
        
        Args:
            bar: 当前K线数据 (Series)
            account: Portfolio 账户实例
            symbol: 股票代码 (多股票模式下使用)
        
        Returns:
            None: 不交易
            tuple: (action, shares) 如 ("BUY", 100)
            dict: {"action": "BUY", "shares": 100}
        """
        pass
    
    def prepare(self, data):
        """
        预处理数据 (可选实现)
        
        Args:
            data: 单股票 DataFrame 或多股票 dict
        
        Returns:
            处理后的数据
        """
        return data
    
    def record_action(self, action, price, date, symbol=None):
        """记录交易动作"""
        self.actions.append({
            'date': date,
            'action': action,
            'price': price,
            'symbol': symbol
        })
    
    def get_signals(self, bar):
        """
        生成交易信号 (可选实现)
        
        Returns:
            dict: {"action": "BUY"/"SELL", "shares": 100}
        """
        return None


class MultiStockStrategy(BaseStrategy):
    """多股票策略基类"""
    
    def __init__(self, symbols=None):
        super().__init__()
        self.symbols = symbols or []
        self.state = {}  # 各股票独立状态
        
        # 初始化每只股票的状态
        for symbol in self.symbols:
            self.state[symbol] = {}
    
    def init_symbol_state(self, symbol, **kwargs):
        """初始化单只股票的状态"""
        if symbol not in self.state:
            self.state[symbol] = {}
        self.state[symbol].update(kwargs)
    
    def get_symbol_state(self, symbol, key, default=None):
        """获取单只股票的状态"""
        return self.state.get(symbol, {}).get(key, default)
    
    def set_symbol_state(self, symbol, key, value):
        """设置单只股票的状态"""
        if symbol not in self.state:
            self.state[symbol] = {}
        self.state[symbol][key] = value
