"""
机构趋势跟踪策略 (Institutional Trend System)

基于技术指标的趋势跟踪策略，包含以下核心逻辑：
1. 信号层：MA均线系统 + MACD + 量能过滤
2. 风控层：硬止损 + 移动止盈 + 趋势破坏判定
"""
import math
import pandas as pd
import numpy as np
from .base import BaseStrategy


class InstitutionalTrendStrategy(BaseStrategy):
    """机构趋势跟踪策略"""
    
    def __init__(self, cfg):
        self.cfg = cfg
        self.stop_loss_pct = cfg.get('stop_loss_pct', 0.08)          # 硬止损 8%
        self.trailing_stop_pct = cfg.get('trailing_stop_pct', 0.15)  # 移动止盈 15%
        self.position_size = cfg.get('position_size', 0.2)           # 单股仓位 20%
        self.initial_capital = cfg.get('total_capital', 100000.0)    # 总资金
        
        # 内部状态
        self.in_position = False
        self.entry_price = 0
        self.peak_price = 0
        self.indicators_df = None
        self.current_idx = 0
        
    def prepare(self, data):
        """
        预计算所有技术指标
        在回测开始前由引擎调用
        """
        df = data.copy()
        
        # MA均线系统
        df['MA5'] = df['close'].rolling(5).mean()
        df['MA10'] = df['close'].rolling(10).mean()
        df['MA20'] = df['close'].rolling(20).mean()
        df['MA60'] = df['close'].rolling(60).mean()
        
        # MACD指标
        df['DIF'] = df['close'].ewm(span=12, adjust=False).mean() - df['close'].ewm(span=26, adjust=False).mean()
        df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
        
        # 量能与风险控制指标
        df['VMA20'] = df['volume'].rolling(20).mean()
        df['ROC_20'] = df['close'].pct_change(20)
        
        # --- 预计算信号 ---
        # MACD 0轴上方死叉
        df['MACD_Dead_Cross'] = (
            (df['DIF'] < df['DEA']) & 
            (df['DIF'].shift(1) >= df['DEA'].shift(1)) & 
            (df['DIF'] > 0)
        )
        
        # 趋势买入信号 (6大金律)
        buy_cond = (
            (df['MA5'] > df['MA10']) & 
            (df['MA10'] > df['MA20']) & 
            (df['MA20'].diff() > 0) & 
            ((df['DIF'] > df['DEA']) & (df['DIF'].shift(1) <= df['DEA'].shift(1))) & 
            (df['volume'] > df['VMA20']) & 
            (df['ROC_20'] < 0.3) & 
            (df['MA20'] > df['MA60'])
        )
        # 信号去重，确保只取第一天
        df['Signal_Entry'] = buy_cond & (~buy_cond.shift(1).fillna(False))
        
        self.indicators_df = df
        self.current_idx = 0
        
        print(f"\n--- 机构趋势策略初始化完成 ---")
        print(f"止损: {self.stop_loss_pct*100}% | 移动止盈: {self.trailing_stop_pct*100}% | 仓位: {self.position_size*100}%")
        print("-" * 40)
        
        return df
    
    def on_bar(self, bar, account):
        """
        每日调用，返回交易信号
        """
        # 获取当前索引对应的指标数据
        idx = self.current_idx
        if idx >= len(self.indicators_df):
            self.current_idx += 1
            return None, 0
            
        row = self.indicators_df.iloc[idx]
        price = bar['close']
        high = bar['high']
        
        # 更新峰值价格 (持仓状态下)
        if self.in_position:
            self.peak_price = max(self.peak_price, high)
        
        action = None
        shares = 0
        
        # --- 买入逻辑 ---
        if not self.in_position and row['Signal_Entry']:
            # 买入信号触发
            action = "BUY"
            shares = self._calc_shares(price)
            self.in_position = True
            self.entry_price = price
            self.peak_price = price
            
        # --- 卖出逻辑 ---
        elif self.in_position:
            # 1. 趋势破坏 (有效跌破MA20，2%缓冲区)
            exit_trend = price < (row['MA20'] * 0.98)
            
            # 2. MACD死叉
            exit_macd = row['MACD_Dead_Cross']
            
            # 3. 硬止损
            exit_stop_loss = price < self.entry_price * (1 - self.stop_loss_pct)
            
            # 4. 移动止盈
            exit_trailing = price < self.peak_price * (1 - self.trailing_stop_pct)
            
            if exit_trend or exit_macd or exit_stop_loss or exit_trailing:
                action = "SELL"
                shares = account.total_shares
                # 记录退出原因
                if exit_trailing:
                    self._exit_reason = "移动止盈"
                elif exit_stop_loss:
                    self._exit_reason = "硬止损"
                elif exit_trend:
                    self._exit_reason = "有效破位"
                else:
                    self._exit_reason = "MACD死叉"
        
        self.current_idx += 1
        return action, shares
    
    def _calc_shares(self, price):
        """计算买入股数 (按仓位比例)"""
        invest = self.initial_capital * self.position_size
        return math.floor(invest / price / 100) * 100
    
    def record_action(self, action_type, price, date):
        """记录交易动作"""
        str_date = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)
        
        if action_type == "BUY":
            print(f"  >>> [买入] {str_date} | 价格: {price:.2f}")
        elif action_type == "SELL":
            reason = getattr(self, '_exit_reason', '未知')
            pnl_pct = (price / self.entry_price - 1) * 100 if self.entry_price > 0 else 0
            print(f"  <<< [卖出] {str_date} | 价格: {price:.2f} | 原因: {reason} | 收益: {pnl_pct:.2f}%")
            # 重置状态
            self.in_position = False
            self.entry_price = 0
            self.peak_price = 0
