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

        # 当日交易信号 (用于快照)
        self._daily_buy_signal = None
        self._daily_sell_signal = None

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

        # 获取所有股票的交易日期并集
        all_dates = set()
        for symbol, df in self.data.items():
            all_dates.update(df.index)
        all_dates = sorted(all_dates)

        for date in all_dates:
            # 重置当日信号
            self._daily_buy_signal = None
            self._daily_sell_signal = None

            # 遍历每只股票
            for symbol, df in self.data.items():
                if date not in df.index:
                    continue

                bar = df.loc[date]

                # 获取策略信号
                signal = self.strategy.on_bar(bar, self.account, symbol)

                # 解析信号并执行
                if signal:
                    action, shares = self._parse_signal(signal, symbol)
                    if action and shares > 0:
                        price = bar['close']
                        self.account.update(symbol, action, shares, price, self.commission)
                        self.strategy.record_action(action, price, date, symbol)
                        # 记录信号 (多股票模式记录第一个信号的价格)
                        if action == "BUY" and self._daily_buy_signal is None:
                            self._daily_buy_signal = price
                        elif action == "SELL" and self._daily_sell_signal is None:
                            self._daily_sell_signal = price

            # 记录每日快照 (取第一只股票的价格作为参考)
            first_symbol = list(self.data.keys())[0]
            if date in self.data[first_symbol].index:
                ref_price = self.data[first_symbol].loc[date, 'close']
            else:
                ref_price = 0

            self._record_snapshot(date, ref_price, list(self.data.keys()))

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

    def _record_snapshot(self, date, price, symbols=None):
        """记录每日快照"""
        # 计算总市值
        market_value = 0
        total_shares = 0
        total_cost = 0

        if isinstance(symbols, list):
            # 多股票模式
            for sym in symbols:
                pos = self.account.get_position(sym)
                if pos and pos.shares > 0:
                    # 获取当前价格
                    if sym in self.data and date in self.data[sym].index:
                        sym_price = self.data[sym].loc[date, 'close']
                        market_value += pos.shares * sym_price
                    else:
                        market_value += pos.cost
                    total_shares += pos.shares
                    total_cost += pos.cost
        else:
            # 单股票模式
            if self.account.has_position(symbols):
                pos = self.account.get_position(symbols)
                market_value = pos.shares * price
                total_shares = pos.shares
                total_cost = pos.cost

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
            # 交易信号 (用于绩效计算)
            "buy_signal": self._daily_buy_signal,
            "sell_signal": self._daily_sell_signal,
        }
        
        # 添加各股票持仓信息 (多股票模式)
        if isinstance(symbols, list):
            for sym in symbols:
                pos = self.account.get_position(sym)
                if pos:
                    snapshot[f"{sym}_shares"] = pos.shares
                    snapshot[f"{sym}_cost"] = pos.cost
                    snapshot[f"{sym}_avg_price"] = pos.avg_price
                else:
                    snapshot[f"{sym}_shares"] = 0
                    snapshot[f"{sym}_cost"] = 0
                    snapshot[f"{sym}_avg_price"] = 0
        
        self.history.append(snapshot)
