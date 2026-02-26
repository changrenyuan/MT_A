import math
import pandas as pd
from .base import BaseStrategy


class MartingaleStrategy(BaseStrategy):
    def __init__(self, cfg):
        self.cfg = cfg
        self.step = 0
        self.last_buy_price = 0
        self.order_plan = []  # 挂单计划表

    def setup_plan(self, entry_price):
        """基于起始价生成马丁加仓计划表"""
        self.order_plan = []
        current_last_price = entry_price
        for i in range(self.cfg['max_steps']):
            drop = self.cfg['base_drop'] * (self.cfg['step_factor'] ** i) if i > 0 else 0
            trigger_price = current_last_price * (1 - drop)
            amount = self.cfg['first_amount'] * (self.cfg['growth_factor'] ** i)
            self.order_plan.append({
                "层级": i + 1,
                "触发价格": round(trigger_price, 2),
                "计划投入": round(amount, 2)
            })
            current_last_price = trigger_price

        print("\n--- 策略挂单计划表 (Martingale Plan) ---")
        print(pd.DataFrame(self.order_plan).to_string(index=False))
        print("-" * 40)

    def on_bar(self, bar, account):
        price = bar['close']
        date = bar.name.strftime('%Y-%m-%d')

        # 初始第一单激活
        if self.step == 0:
            self.setup_plan(price)
            print(f"策略启动日期: {date} | 起始价格: {price:.2f}")
            return "BUY", self._calc_shares(price, 0)

        # 止盈止损逻辑
        if account.total_shares > 0:
            if price >= account.avg_price * (1 + self.cfg['take_profit_pct']):
                return "SELL", account.total_shares
            if price <= account.avg_price * (1 - self.cfg['stop_loss_pct']):
                return "SELL", account.total_shares

        # 马丁补仓逻辑
        if self.step < self.cfg['max_steps']:
            next_plan = self.order_plan[self.step]
            if price <= next_plan['触发价格']:
                return "BUY", self._calc_shares(price, self.step)

        return None, 0

    def _calc_shares(self, price, step_idx):
        invest = self.cfg['first_amount'] * (self.cfg['growth_factor'] ** step_idx)
        return math.floor(invest / price / 100) * 100

    # def record_action(self, action_type, price, date):
    #     if action_type == "BUY":
    #         self.last_buy_price = price
    #         self.step += 1
    #         print(f"  [SIGNAL] {date} 触发买入: 价格 {price:.2f} (层级 {self.step})")
    #     else:
    #         print(f"  [SIGNAL] {date} 触发卖出: 价格 {price:.2f}")
    #         self.step = 0

    def record_action(self, action_type, price, date):
        # 格式化日期
        str_date = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)

        if action_type == "BUY":
            self.last_buy_price = price
            self.step += 1
            print(f"  >>> [买入] {str_date} | 价格: {price:.2f} | 阶梯: {self.step}")
        elif action_type == "SELL":
            print(f"  <<< [卖出] {str_date} | 价格: {price:.2f} | 收益清算完毕")
            self.step = 0
            self.last_buy_price = 0