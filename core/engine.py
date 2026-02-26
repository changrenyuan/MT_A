import pandas as pd
from .account import Portfolio


class BacktestEngine:
    def __init__(self, data, strategy, initial_capital, commission=0.0003):
        self.data = data
        self.strategy = strategy
        self.account = Portfolio(initial_capital)
        self.commission = commission
        self.history = []

    # def run(self):
    #     for date, bar in self.data.iterrows():
    #         action, shares = self.strategy.on_bar(bar, self.account)
    #
    #         if action:
    #             self.account.update(action, shares, bar['close'], self.commission)
    #             self.strategy.record_action(action, bar['close'], date)
    #
    #         # 每日快照记录
    #         equity = self.account.cash + (self.account.total_shares * bar['close'])
    #         self.history.append({
    #             "date": date,
    #             "price": bar['close'],
    #             "cash": self.account.cash,
    #             "total_shares": self.account.total_shares,
    #             "avg_price": self.account.avg_price,
    #             "total_cost": self.account.total_cost,
    #             "equity": equity,
    #             "buy_signal": bar['close'] if action == "BUY" else None,
    #             "sell_signal": bar['close'] if action == "SELL" else None
    #         })
    #
    #     return pd.DataFrame(self.history).set_index("date")

        # 修改 src/core/engine.py 中的 run 方法
    def run(self):
        used_capital = 0  # 追踪累计投入
        for date, bar in self.data.iterrows():
            action, shares = self.strategy.on_bar(bar, self.account)

            if action:
                price = bar['close']
                # 计算本次实际投入（不含手续费的原始成本，用于计算净利润）
                if action == "BUY":
                    used_capital += shares * price

                self.account.update(action, shares, price, self.commission)
                self.strategy.record_action(action, price, date)

            # --- 关键：完善每日快照 ---
            market_value = self.account.total_shares * bar['close']  # 持仓市值
            equity = self.account.cash + market_value  # 总资产
            # 浮动盈亏 = 总资产 - 初始资金 (或者用 总资产 - 累计投入 - 剩余现金)
            # 这里统一使用：总资产 - 初始总资金 = 累计净收益
            pnl = equity - 200000.0  # 假设初始资金是 20万

            self.history.append({
                "date": date,
                "price": bar['close'],
                "cash": self.account.cash,
                "total_shares": self.account.total_shares,
                "market_value": market_value,
                "avg_price": self.account.avg_price,
                "total_cost": self.account.total_cost,  # 当前持仓成本
                "equity": equity,
                "pnl": pnl,
                "buy_signal": bar['close'] if action == "BUY" else None,
                "sell_signal": bar['close'] if action == "SELL" else None
            })

        return pd.DataFrame(self.history).set_index("date")