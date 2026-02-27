"""
回测引擎模块 - 支持多股票回测
"""

import pandas as pd
from .account import Portfolio


class BacktestEngine:
    """回测引擎 - 支持单股票和多股票模式"""
    
    def __init__(self, data, strategy, initial_capital, commission=0.0003):
        """
        Args:
            data: 单股票 DataFrame 或多股票 dict {symbol: DataFrame}
            strategy: 策略实例
            initial_capital: 初始资金
            commission: 手续费率
        """
        self.data = data
        self.strategy = strategy
        self.account = Portfolio(initial_capital)
        self.commission = commission
        self.initial_capital = initial_capital
        self.history = []
        
        # 检测是否为多股票模式
        self.is_multi_stock = isinstance(data, dict)
        
        # 当日交易信号 (用于快照) - 兼容单股票模式
        self._daily_buy_signal = None
        self._daily_sell_signal = None
        
        # 多股票模式：每只股票独立的信号
        self._daily_signals = {}  # {symbol: {'buy': price, 'sell': price}}
        
        # 多股票模式：每只股票的虚拟账户（追踪现金余额）
        # 用于计算单只股票的独立权益曲线
        self._stock_cash = {}  # {symbol: cash_balance}
    
    def run(self):
        """运行回测"""
        if self.is_multi_stock:
            return self._run_multi_stock()
        else:
            return self._run_single_stock()
    
    def _run_single_stock(self):
        """单股票回测"""
        # 如果策略有 prepare 方法，先预处理数据
        if hasattr(self.strategy, 'prepare'):
            self.data = self.strategy.prepare(self.data)
        
        symbol = "STOCK"  # 默认股票标识
        
        for date, bar in self.data.iterrows():
            # 重置当日信号
            self._daily_buy_signal = None
            self._daily_sell_signal = None
            
            # 获取策略信号
            signal = self.strategy.on_bar(bar, self.account, symbol)
            
            # 解析信号
            if signal:
                action, shares = self._parse_signal(signal, symbol)
                if action and shares > 0:
                    price = bar['close']
                    self.account.update(symbol, action, shares, price, self.commission)
                    self.strategy.record_action(action, price, date, symbol)
                    # 记录信号
                    if action == "BUY":
                        self._daily_buy_signal = price
                    elif action == "SELL":
                        self._daily_sell_signal = price
            
            # 记录每日快照
            self._record_snapshot(date, bar['close'], symbol)
        
        return pd.DataFrame(self.history).set_index("date")
    
    def _run_multi_stock(self):
        """多股票回测"""
        # 预处理所有股票数据
        if hasattr(self.strategy, 'prepare'):
            self.data = self.strategy.prepare(self.data)
        
        # 初始化每只股票的虚拟账户
        for symbol in self.data.keys():
            self._stock_cash[symbol] = 0.0
        
        # 获取所有股票的交易日期并集
        all_dates = set()
        for symbol, df in self.data.items():
            all_dates.update(df.index)
        all_dates = sorted(all_dates)
        
        for date in all_dates:
            # 重置当日所有股票的信号
            self._daily_signals = {}
            self._daily_buy_signal = None
            self._daily_sell_signal = None
            
            # 记录当日各股票价格
            daily_prices = {}  # {symbol: price}
            
            # 遍历每只股票
            for symbol, df in self.data.items():
                if date not in df.index:
                    continue
                
                bar = df.loc[date]
                price = bar['close']
                daily_prices[symbol] = price
                
                # 初始化该股票的信号记录
                self._daily_signals[symbol] = {'buy': None, 'sell': None}
                
                # 获取策略信号
                signal = self.strategy.on_bar(bar, self.account, symbol)
                
                # 解析信号并执行
                if signal:
                    action, shares = self._parse_signal(signal, symbol)
                    if action and shares > 0:
                        # 记录交易前的持仓（用于计算虚拟账户现金流）
                        pos_before = self.account.get_position(symbol)
                        shares_before = pos_before.shares if pos_before else 0
                        
                        # 执行交易
                        self.account.update(symbol, action, shares, price, self.commission)
                        self.strategy.record_action(action, price, date, symbol)
                        
                        # 更新该股票的虚拟账户现金流
                        if action == "BUY":
                            # 买入：现金流出 = 股数 * 价格 * (1 + 手续费)
                            cost = shares * price * (1 + self.commission)
                            self._stock_cash[symbol] -= cost
                        elif action == "SELL":
                            # 卖出：现金流入 = 股数 * 价格 * (1 - 手续费)
                            revenue = shares * price * (1 - self.commission)
                            self._stock_cash[symbol] += revenue
                        
                        # 记录该股票的信号
                        if action == "BUY":
                            self._daily_signals[symbol]['buy'] = price
                            if self._daily_buy_signal is None:
                                self._daily_buy_signal = price
                        elif action == "SELL":
                            self._daily_signals[symbol]['sell'] = price
                            if self._daily_sell_signal is None:
                                self._daily_sell_signal = price
            
            # 记录每日快照
            first_symbol = list(self.data.keys())[0]
            ref_price = daily_prices.get(first_symbol, 0)
            self._record_snapshot_multi(date, ref_price, list(self.data.keys()), daily_prices)
        
        return pd.DataFrame(self.history).set_index("date")
    
    def _parse_signal(self, signal, symbol):
        """解析策略信号"""
        if isinstance(signal, tuple):
            action, shares = signal
            return action, shares
        elif isinstance(signal, str):
            # 只返回动作，需要计算股数
            return signal, 0
        elif isinstance(signal, dict):
            action = signal.get('action')
            shares = signal.get('shares', 0)
            return action, shares
        return None, 0
    
    def _record_snapshot(self, date, price, symbol):
        """记录每日快照 (单股票模式)"""
        pos = self.account.get_position(symbol)
        market_value = pos.shares * price if pos else 0
        total_cost = pos.cost if pos else 0
        total_shares = pos.shares if pos else 0
        
        equity = self.account.cash + market_value
        pnl = equity - self.initial_capital
        
        snapshot = {
            "date": date,
            "price": price,
            "cash": self.account.cash,
            "total_shares": total_shares,
            "market_value": market_value,
            "total_cost": total_cost,
            "equity": equity,
            "pnl": pnl,
            "buy_signal": self._daily_buy_signal,
            "sell_signal": self._daily_sell_signal,
        }
        
        self.history.append(snapshot)
    
    def _record_snapshot_multi(self, date, ref_price, symbols, daily_prices):
        """记录每日快照 (多股票模式)"""
        # 计算总市值
        market_value = 0
        total_shares = 0
        total_cost = 0
        
        for sym in symbols:
            pos = self.account.get_position(sym)
            if pos and pos.shares > 0:
                sym_price = daily_prices.get(sym, 0)
                if sym_price > 0:
                    market_value += pos.shares * sym_price
                else:
                    market_value += pos.cost
                total_shares += pos.shares
                total_cost += pos.cost
        
        equity = self.account.cash + market_value
        pnl = equity - self.initial_capital
        
        snapshot = {
            "date": date,
            "price": ref_price,  # 参考价格
            "cash": self.account.cash,
            "total_shares": total_shares,
            "market_value": market_value,
            "total_cost": total_cost,
            "equity": equity,
            "pnl": pnl,
            # 兼容字段 (用于绩效计算)
            "buy_signal": self._daily_buy_signal,
            "sell_signal": self._daily_sell_signal,
        }
        
        # 添加各股票独立数据
        for sym in symbols:
            pos = self.account.get_position(sym)
            sym_price = daily_prices.get(sym, 0)
            
            # 持仓信息
            if pos:
                snapshot[f"{sym}_shares"] = pos.shares
                snapshot[f"{sym}_cost"] = pos.cost
                snapshot[f"{sym}_avg_price"] = pos.avg_price
            else:
                snapshot[f"{sym}_shares"] = 0
                snapshot[f"{sym}_cost"] = 0
                snapshot[f"{sym}_avg_price"] = 0
            
            # 价格
            snapshot[f"{sym}_price"] = sym_price
            
            # 交易信号
            signals = self._daily_signals.get(sym, {})
            snapshot[f"{sym}_buy_signal"] = signals.get('buy')
            snapshot[f"{sym}_sell_signal"] = signals.get('sell')
            
            # === 新增：该股票的虚拟账户数据 ===
            # 虚拟现金余额（累计卖出收入 - 累计买入支出）
            stock_cash = self._stock_cash.get(sym, 0)
            snapshot[f"{sym}_cash"] = stock_cash
            
            # 虚拟权益 = 现金余额 + 持仓市值
            stock_market_value = (pos.shares * sym_price) if pos and sym_price > 0 else 0
            snapshot[f"{sym}_equity"] = stock_cash + stock_market_value
        
        self.history.append(snapshot)
