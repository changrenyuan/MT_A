import math
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import akshare as ak
from dataclasses import dataclass
from typing import List, Dict

# 配置配置
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False


@dataclass
class StrategyConfig:
    """策略参数配置类"""
    symbol: str = "sh600415"
    first_amount: float = 10000.0  # 首笔投入金额
    base_drop: float = 0.02  # 基础跌幅 (2%)
    step_factor: float = 1.1  # 跌幅步进系数
    growth_factor: float = 1.5  # 资金倍增系数
    max_steps: int = 6  # 最大补仓次数
    total_capital: float = 100000.0
    take_profit_pct: float = 0.05  # 止盈 5%
    stop_loss_pct: float = 0.15  # 止损 15%


class MartingaleBacktester:
    def __init__(self, config: StrategyConfig):
        self.cfg = config
        self.df = None
        self.results = None

    def fetch_data(self):
        """获取数据层"""
        try:
            df = ak.stock_zh_a_daily(symbol=self.cfg.symbol)
            df.index = pd.to_datetime(df.index)
            # 仅保留核心列
            self.df = df[['close']].copy()
            return self
        except Exception as e:
            print(f"数据获取失败: {e}")
            return None

    def run(self):
        """核心回测引擎 (优化逻辑)"""
        if self.df is None: return

        # 初始化状态变量
        step = 0
        total_shares = 0
        total_cost = 0
        used_capital = 0
        last_buy_price = 0  # 记录上次买入价以计算下次触发点

        history = []

        for date, row in self.df.iterrows():
            price = row['close']
            buy_shares, sell_shares = 0, 0
            avg_price = total_cost / total_shares if total_shares > 0 else 0

            # --- 1. 卖出逻辑 (优先级通常高于买入) ---
            if total_shares > 0:
                is_tp = price >= avg_price * (1 + self.cfg.take_profit_pct)
                is_sl = price <= avg_price * (1 - self.cfg.stop_loss_pct)

                if is_tp or is_sl:
                    sell_shares = total_shares
                    # 结算
                    total_shares = 0
                    total_cost = 0
                    step = 0  # 重置马丁层级
                    last_buy_price = 0

            # --- 2. 买入逻辑 ---
            # 确定触发价：如果是第一笔，按初始价；否则按上次买入价计算
            if step == 0:
                # 初始买入逻辑：这里可以设定为第一个交易日直接买入，或达到某个观察价
                trigger_price = price + 1  # 示例：立即触发首笔
            else:
                current_drop_target = self.cfg.base_drop * (self.cfg.step_factor ** (step - 1))
                trigger_price = last_buy_price * (1 - current_drop_target)

            if step < self.cfg.max_steps and price <= trigger_price:
                invest_amount = self.cfg.first_amount * (self.cfg.growth_factor ** step)

                if used_capital + invest_amount <= self.cfg.total_capital:
                    shares = math.floor(invest_amount / price / 100) * 100
                    if shares > 0:
                        buy_shares = shares
                        cost = shares * price
                        total_shares += shares
                        total_cost += cost
                        used_capital += cost
                        last_buy_price = price
                        step += 1
                        avg_price = total_cost / total_shares

            # 记录每日快照
            history.append({
                "date": date,
                "price": price,
                "buy_shares": buy_shares,
                "sell_shares": sell_shares,
                "total_shares": total_shares,
                "avg_price": avg_price,
                "total_cost": total_cost,
                "equity": total_shares * price,
                "pnl": (total_shares * price) - total_cost
            })

        self.results = pd.DataFrame(history).set_index('date')
        return self.results

    def plot(self):
        """可视化层"""
        if self.results is None: return

        res = self.results
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True, gridspec_kw={'height_ratios': [2, 1]})

        # Top: Price and Signals
        ax1.plot(res.index, res['price'], label='股价', color='#bdc3c7', alpha=0.8)
        ax1.plot(res.index, res['avg_price'].replace(0, np.nan), label='持仓均价', color='#f39c12', linestyle='--')

        # 标注交易点
        buys = res[res['buy_shares'] > 0]
        sells = res[res['sell_shares'] > 0]
        ax1.scatter(buys.index, buys['price'], color='#e74c3c', marker='^', label='买入', s=60, zorder=5)
        ax1.scatter(sells.index, sells['price'], color='#2ecc71', marker='v', label='卖出', s=60, zorder=5)

        ax1.set_title(f"马丁格尔策略回测: {self.cfg.symbol}", fontsize=14)
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Bottom: PnL
        ax2.fill_between(res.index, res['pnl'], 0, where=(res['pnl'] >= 0), color='#2ecc71', alpha=0.3, label='浮盈')
        ax2.fill_between(res.index, res['pnl'], 0, where=(res['pnl'] < 0), color='#e74c3c', alpha=0.3, label='浮亏')
        ax2.plot(res.index, res['pnl'], color='#7f8c8d', linewidth=1)

        ax2.set_ylabel("净损益 (PnL)")
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.show()


# --- 调用示例 ---
if __name__ == "__main__":
    config = StrategyConfig(
        symbol="sh600415",
        base_drop=0.03,  # 跌3%补一次
        growth_factor=1.2,  # 每次补仓资金增加20%
        take_profit_pct=0.06  # 6%止盈
    )

    engine = MartingaleBacktester(config)
    engine.fetch_data()
    report = engine.run()

    print("回测总结:")
    print(f"最终累计投入: {report['total_cost'].max():.2f}")
    print(f"最大持仓股数: {report['total_shares'].max()}")

    engine.plot()