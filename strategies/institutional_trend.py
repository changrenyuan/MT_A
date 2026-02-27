"""
终极趋势策略 v6.1 (专业优化版)

核心优化点：
1. 分档动态止盈：收益越高，止盈越紧，防止"坐过山车"
2. 乖离率过滤 (Bias Check)：防止在远离均线时盲目追高入场
3. 放量破位确认：避免被缩量假跌破洗出
4. 分批出场逻辑：达到目标位后先套现一部分
"""
import math
import pandas as pd
import numpy as np
from .base import BaseStrategy


class InstitutionalTrendStrategy(BaseStrategy):
    """终极趋势策略 v6.1 (专业优化版)"""
    
    def __init__(self, cfg):
        self.cfg = cfg
        # 参数配置
        self.stop_loss_pct = cfg.get('stop_loss_pct', 0.10)          # 硬止损 10%
        self.trailing_stop_pct = cfg.get('trailing_stop_pct', 0.20)  # 默认移动止盈 20%
        self.unit_size = cfg.get('unit_size', 0.1)                   # 单次建仓比例 10%
        self.max_units = cfg.get('max_units', 4)                     # 最大加仓次数
        self.initial_capital = cfg.get('total_capital', 100000.0)    # 总资金
        
        # 分档止盈参数
        self.profit_tier1 = cfg.get('profit_tier1', 0.30)   # 第一档: 利润 30%
        self.trailing_tier1 = cfg.get('trailing_tier1', 0.15)  # 对应止盈 15%
        self.profit_tier2 = cfg.get('profit_tier2', 0.50)   # 第二档: 利润 50%
        self.trailing_tier2 = cfg.get('trailing_tier2', 0.10)  # 对应止盈 10%
        
        # 分批出场参数
        self.partial_exit_pct = cfg.get('partial_exit_pct', 0.5)  # 分批卖出比例 50%
        self.enable_partial_exit = cfg.get('enable_partial_exit', True)  # 是否启用分批出场
        
        # 内部状态
        self.units_held = 0       # 当前持有头寸份数
        self.avg_price = 0.0      # 平均持仓成本
        self.peak_price = 0.0     # 入场后的最高价
        self.indicators_df = None
        self.current_idx = 0
        
        # 用于记录交易信息
        self._exit_reason = ""
        self._exit_avg_price = 0.0
        self._partial_exited = False  # 是否已部分止盈
        self._initial_shares = 0  # 初始买入股数，用于计算 units_held

    def prepare(self, data):
        """
        预计算所有技术指标
        """
        df = data.copy()
        
        # === 1. 基础均线系统 ===
        df['MA10'] = df['close'].rolling(10).mean()
        df['MA20'] = df['close'].rolling(20).mean()
        df['MA60'] = df['close'].rolling(60).mean()
        
        # === 2. MACD 指标 ===
        df['DIF'] = df['close'].ewm(span=12, adjust=False).mean() - df['close'].ewm(span=26, adjust=False).mean()
        df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
        df['MACD'] = (df['DIF'] - df['DEA']) * 2
        
        # === 3. 成交量均线 ===
        df['MA_Vol'] = df['volume'].rolling(20).mean()
        
        # === 4. 乖离率 (Bias) ===
        # 股价/MA20，用于防止追高
        df['Bias'] = df['close'] / df['MA20']
        
        # === 5. 趋势强度判定 (优化: 降低门槛捕捉更早趋势) ===
        # MA20 > MA60 * 1.02 且 MA60 三日内向上
        df['Strong_Trend'] = (
            (df['MA20'] > df['MA60'] * 1.02) & 
            (df['MA60'].diff(3) >= 0)
        )
        
        # === 6. 入场信号 ===
        # MA10 上穿 MA20
        df['MA10_Cross_Up'] = (
            (df['MA10'] > df['MA20']) & 
            (df['MA10'].shift(1) <= df['MA20'].shift(1))
        )
        
        # MACD 多头
        df['MACD_Bullish'] = (df['DIF'] > df['DEA']) & (df['DIF'] > 0)
        
        # === 7. 加仓信号：回踩支撑 ===
        df['Pullback_Support'] = (
            (df['low'] < df['MA20'] * 1.02) &   # 触及支撑区
            (df['low'] > df['MA20'] * 0.98) &   # 但未有效跌破
            (df['close'] > df['open']) &        # 收阳线
            (df['close'] > df['MA20']) &        # 收盘站稳 MA20
            (df['Bias'] < 1.05)                 # 乖离率不过大
        )
        
        # === 8. 离场信号：放量破位确认 ===
        # 收盘跌破 MA20 的 2% 缓冲区 且 成交量放大
        df['Trend_Broken'] = (
            (df['close'] < df['MA20'] * 0.98) & 
            (df['volume'] > df['MA_Vol'] * 1.2)
        )
        
        # 缩量跌破 (可能是假跌破，不触发离场)
        df['Weak_Break'] = (
            (df['close'] < df['MA20'] * 0.98) & 
            (df['volume'] < df['MA_Vol'] * 0.8)
        )
        
        # 填充 NaN 值
        df = df.ffill().bfill()
        
        # 将布尔列中的 NaN 替换为 False
        bool_cols = ['Strong_Trend', 'MA10_Cross_Up', 'MACD_Bullish', 'Pullback_Support', 
                     'Trend_Broken', 'Weak_Break']
        for col in bool_cols:
            df[col] = df[col].fillna(False)
        
        self.indicators_df = df
        self.current_idx = 0
        
        print(f"\n{'=' * 50}")
        print(f"终极趋势策略 v6.1 (专业优化版) 初始化完成")
        print(f"{'=' * 50}")
        print(f"止损: {self.stop_loss_pct*100}% | 默认止盈: {self.trailing_stop_pct*100}%")
        print(f"单次仓位: {self.unit_size*100}% | 最大仓位: {self.unit_size*self.max_units*100}%")
        print(f"分档止盈: {self.profit_tier1*100}%→{self.trailing_tier1*100}% | {self.profit_tier2*100}%→{self.trailing_tier2*100}%")
        print(f"乖离率过滤: < 8% | 放量破位确认: > 1.2倍均量")
        print(f"分批出场: {'启用' if self.enable_partial_exit else '禁用'} ({self.partial_exit_pct*100:.0f}%)")
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
            # === 1. 初次建仓 ===
            if self.units_held == 0:
                # 乖离率过滤：只有在距离 MA20 不远时才入场
                bias_ok = row['Bias'] < 1.08
                
                # 入场条件：MA10 > MA20 且 MACD 多头 且 不追高
                if (row['MA10_Cross_Up'] or (row['MA10'] > row['MA20'] and row['MACD_Bullish'])) and bias_ok:
                    action = "BUY"
                    shares = self._calc_shares(price, self.unit_size)
                    if shares > 0:
                        self._initial_shares = shares
                        self._update_status("ENTRY", price)
                        self._partial_exited = False
                    else:
                        action = None
            
            # === 2. 回调加仓 ===
            elif self.units_held < self.max_units:
                if row['Pullback_Support']:
                    action = "BUY"
                    shares = self._calc_shares(price, self.unit_size)
                    if shares > 0:
                        self._initial_shares += shares
                        self._update_status("ADD", price)
                    else:
                        action = None
        
        # ========== B. 离场逻辑 (分档动态止盈) ==========
        if self.units_held > 0 and account.total_shares > 0:
            should_exit = False
            exit_reason = ""
            
            # 计算当前浮盈
            current_profit = (price / self.avg_price - 1) if self.avg_price > 0 else 0
            
            # --- 核心优化：分档动态止盈 ---
            # 利润越高，止盈位拉得越近，防止"坐过山车"
            dynamic_trailing = self.trailing_stop_pct  # 默认 20%
            if current_profit > self.profit_tier2:     # 利润 > 50%
                dynamic_trailing = self.trailing_tier2  # 回撤 10% 就跑
            elif current_profit > self.profit_tier1:   # 利润 > 30%
                dynamic_trailing = self.trailing_tier1  # 回撤 15% 就跑
            
            # 1. 动态移动止盈
            if self.peak_price > 0 and price < self.peak_price * (1 - dynamic_trailing):
                # 检查是否启用分批出场
                if self.enable_partial_exit and not self._partial_exited and current_profit > 0.10:
                    # 分批卖出：先卖出指定比例
                    # partial_exit_pct = 0.5 表示卖出 50%
                    partial_shares = math.floor(account.total_shares * self.partial_exit_pct / 100) * 100
                    if partial_shares > 0:
                        action = "SELL"
                        shares = partial_shares
                        self._partial_exited = True
                        exit_reason = f"分批止盈(卖{self.partial_exit_pct*100:.0f}%)"
                        self._exit_reason = exit_reason
                        self._exit_avg_price = self.avg_price
                        # 更新 units_held (按比例减少)
                        self.units_held = max(1, self.units_held - 1)
                        # 重置 peak_price 以继续跟踪剩余仓位
                        self.peak_price = price
                    else:
                        should_exit = True
                        exit_reason = f"分档止盈({dynamic_trailing*100:.0f}%)"
                else:
                    should_exit = True
                    exit_reason = f"分档止盈({dynamic_trailing*100:.0f}%)"
            
            # 2. 放量破位确认 (避免缩量假跌破)
            elif row['Trend_Broken']:
                should_exit = True
                exit_reason = "放量破位"
            
            # 3. 硬止损 (成本价亏损 10%)
            elif self.avg_price > 0 and price < self.avg_price * (1 - self.stop_loss_pct):
                should_exit = True
                exit_reason = "硬止损"
            
            # 执行全部卖出
            if should_exit:
                action = "SELL"
                shares = account.total_shares
                self._exit_reason = exit_reason
                self._exit_avg_price = self.avg_price
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
            total_units = self.units_held
            self.avg_price = (self.avg_price * total_units + price) / (total_units + 1)
            self.units_held += 1
        elif action_type == "EXIT":
            self.units_held = 0
            self.avg_price = 0.0
            self.peak_price = 0.0
            self._partial_exited = False
            self._initial_shares = 0
    
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
            avg_price = self._exit_avg_price if self._exit_avg_price > 0 else self.avg_price
            if avg_price > 0:
                pnl_pct = (price / avg_price - 1) * 100
            else:
                pnl_pct = 0.0
            
            # 判断是否部分卖出
            if self._partial_exited and "分批" in reason:
                print(f"  <-> [分批卖出] {str_date} | 价格: {price:.2f} | 原因: {reason} | 收益: {pnl_pct:+.2f}%")
            else:
                print(f"  <<< [卖出离场] {str_date} | 价格: {price:.2f} | 原因: {reason} | 收益: {pnl_pct:+.2f}%")
