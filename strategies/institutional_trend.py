"""
终极趋势策略 v6.0 (Ultimate Trend Strategy)

核心逻辑：
1. 初始建仓：趋势初步确立时入场 10%
2. 回调加仓：股价回踩 MA20 支撑位且企稳时追加 10%
3. 动态止盈：25% 大格局移动止盈
4. 自动接力：若被洗出，只要趋势大框架（MA60）未坏，随时准备二次入场
"""
import math
import pandas as pd
import numpy as np
from .base import BaseStrategy


class InstitutionalTrendStrategy(BaseStrategy):
    """终极趋势策略 v6.0"""
    
    def __init__(self, cfg):
        self.cfg = cfg
        # 参数配置
        self.stop_loss_pct = cfg.get('stop_loss_pct', 0.10)          # 硬止损 10%
        self.trailing_stop_pct = cfg.get('trailing_stop_pct', 0.25)  # 移动止盈 25%
        self.unit_size = cfg.get('unit_size', 0.1)                   # 单次建仓比例 10%
        self.max_units = cfg.get('max_units', 2)                     # 最大加仓次数
        self.initial_capital = cfg.get('total_capital', 100000.0)    # 总资金
        
        # 内部状态
        self.units_held = 0       # 当前持有头寸份数
        self.avg_price = 0.0      # 平均持仓成本
        self.peak_price = 0.0     # 入场后的最高价
        self.indicators_df = None
        self.current_idx = 0
        
        # 用于记录交易信息 (在重置状态前保存)
        self._exit_reason = ""    # 退出原因
        self._exit_avg_price = 0.0  # 退出时的成本价 (用于计算收益)
        self._exit_peak_price = 0.0 # 退出时的峰值价

    def prepare(self, data):
        """
        预计算所有技术指标
        """
        df = data.copy()
        
        # === 核心均线系统 ===
        df['MA10'] = df['close'].rolling(10).mean()
        df['MA20'] = df['close'].rolling(20).mean()
        df['MA60'] = df['close'].rolling(60).mean()
        
        # === MACD 指标 ===
        df['DIF'] = df['close'].ewm(span=12, adjust=False).mean() - df['close'].ewm(span=26, adjust=False).mean()
        df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
        df['MACD'] = (df['DIF'] - df['DEA']) * 2
        
        # === 趋势强度判定 (大方向) ===
        # MA20 > MA60 且 MA20 向上
        df['Strong_Trend'] = (
            (df['MA20'] > 1.08*df['MA60']) &
            # (df['MA20'].diff() > 0)
            (df['MA60'].diff(5) >= 0)
        )
        
        # === 入场信号：初次启动 ===
        # MA10 上穿 MA20 (金叉)
        df['MA10_Cross_Up'] = (
            (df['MA10'] > df['MA20']) & 
            (df['MA10'].shift(1) <= df['MA20'].shift(1))
        )
        
        # MACD 多头排列 (DIF > DEA 且 DIF > 0)
        df['MACD_Bullish'] = (df['DIF'] > df['DEA']) & (df['DIF'] > 0)
        
        # 初始入场条件：MA10金叉MA20 或 已处于多头排列
        df['Initial_Entry'] = df['MA10_Cross_Up'].fillna(False)
        
        # === 加仓信号：回踩支撑 ===
        # 最低价靠近 MA20 上方 2% 范围内，且收盘价 > 开盘价 (阳线企稳)
        df['Pullback_Support'] = (
            (df['low'] < df['MA20'] * 1.02) &   # 触及支撑区
            (df['low'] > df['MA20'] * 0.98) &   # 但未有效跌破
            (df['close'] > df['open']) &        # 收阳线
            (df['close'] > df['MA20'])          # 收盘站稳 MA20
        )
        
        # === 离场信号 ===
        # 趋势破坏：价格跌破 MA20 的 2% 缓冲区
        df['Trend_Broken'] = df['close'] < df['MA20'] * 0.98
        
        # 填充 NaN 值 (pandas 2.0+ 语法)
        df = df.ffill().bfill()
        
        # 将布尔列中的 NaN 替换为 False
        bool_cols = ['Strong_Trend', 'MA10_Cross_Up', 'MACD_Bullish', 'Initial_Entry', 
                     'Pullback_Support', 'Trend_Broken']
        for col in bool_cols:
            df[col] = df[col].fillna(False)
        
        self.indicators_df = df
        self.current_idx = 0
        
        print(f"\n{'=' * 50}")
        print(f"终极趋势策略 v6.0 初始化完成")
        print(f"{'=' * 50}")
        print(f"止损: {self.stop_loss_pct*100}% | 移动止盈: {self.trailing_stop_pct*100}%")
        print(f"单次仓位: {self.unit_size*100}% | 最大仓位: {self.unit_size*self.max_units*100}%")
        print(f"{'=' * 50}")
        
        return df
    
    def on_bar(self, bar, account):
        """
        每日调用，返回交易信号
        """
        idx = self.current_idx
        if idx >= len(self.indicators_df):
            self.current_idx += 1
            return None, 0
        
        row = self.indicators_df.iloc[idx]
        price = bar['close']
        high = bar['high']
        
        # 更新持有期间最高价
        if self.units_held > 0:
            self.peak_price = max(self.peak_price, high)
        
        action = None
        shares = 0
        
        # ========== A. 入场与加仓逻辑 ==========
        if row['Strong_Trend']:
            # --- 1. 初次建仓 ---
            if self.units_held == 0:
                # 条件：MA10 > MA20 且 MACD 多头
                if row['Initial_Entry'] or (row['MA10'] > row['MA20'] and row['MACD_Bullish']):
                    action = "BUY"
                    shares = self._calc_shares(price, self.unit_size)
                    if shares > 0:
                        self._update_status("ENTRY", price)
                    else:
                        action = None  # 资金不足，取消买入
            
            # --- 2. 回调加仓 ---
            elif self.units_held < self.max_units:
                if row['Pullback_Support']:
                    action = "BUY"
                    shares = self._calc_shares(price, self.unit_size)
                    if shares > 0:
                        self._update_status("ADD", price)
                    else:
                        action = None
        
        # ========== B. 离场逻辑 ==========
        if self.units_held > 0:
            should_exit = False
            exit_reason = ""
            
            # 1. 移动止盈 (保护利润)
            if self.peak_price > 0 and price < self.peak_price * (1 - self.trailing_stop_pct):
                should_exit = True
                exit_reason = "移动止盈"
            
            # 2. 趋势终结 (跌破 MA20 缓冲区)
            elif row['Trend_Broken']:
                should_exit = True
                exit_reason = "趋势破位"
            
            # 3. 硬止损 (成本价亏损)
            elif self.avg_price > 0 and price < self.avg_price * (1 - self.stop_loss_pct):
                should_exit = True
                exit_reason = "硬止损"
            
            # 执行卖出
            if should_exit:
                action = "SELL"
                shares = account.total_shares
                # 先保存交易信息，再重置状态
                self._exit_reason = exit_reason
                self._exit_avg_price = self.avg_price
                self._exit_peak_price = self.peak_price
                self._update_status("EXIT", price)
        
        self.current_idx += 1
        return action, shares
    
    def _update_status(self, action_type, price):
        """更新持仓状态"""
        if action_type == "ENTRY":
            self.units_held = 1
            self.avg_price = price
            self.peak_price = price
        elif action_type == "ADD":
            # 加权平均成本
            total_shares_before = self.units_held
            self.avg_price = (self.avg_price * total_shares_before + price) / (total_shares_before + 1)
            self.units_held += 1
        elif action_type == "EXIT":
            self.units_held = 0
            self.avg_price = 0.0
            self.peak_price = 0.0
    
    def _calc_shares(self, price, pct):
        """计算买入股数"""
        if price <= 0:
            return 0
        invest = self.initial_capital * pct
        return math.floor(invest / price / 100) * 100
    
    def record_action(self, action_type, price, date):
        """记录交易动作"""
        str_date = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)
        
        if action_type == "BUY":
            if self.units_held == 1:
                print(f"  >>> [初始建仓] {str_date} | 价格: {price:.2f} | 仓位: {self.units_held}/{self.max_units}")
            else:
                print(f"  >>> [回调加仓] {str_date} | 价格: {price:.2f} | 仓位: {self.units_held}/{self.max_units} | 成本: {self.avg_price:.2f}")
        
        elif action_type == "SELL":
            reason = self._exit_reason if self._exit_reason else '未知'
            # 使用保存的成本价计算收益
            avg_price = self._exit_avg_price if self._exit_avg_price > 0 else self.avg_price
            if avg_price > 0:
                pnl_pct = (price / avg_price - 1) * 100
            else:
                pnl_pct = 0.0
            print(f"  <<< [卖出离场] {str_date} | 价格: {price:.2f} | 原因: {reason} | 收益: {pnl_pct:+.2f}%")
