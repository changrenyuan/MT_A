"""
终极趋势策略 v6.2 (多股票支持版)

核心优化点：
1. 分档动态止盈：收益越高，止盈越紧，防止"坐过山车"
2. 乖离率过滤 (Bias Check)：防止在远离均线时盲目追高入场
3. 放量破位确认：避免被缩量假跌破洗出
4. 分批出场逻辑：达到目标位后先套现一部分
5. 多股票支持：可同时持有最多3只股票
"""
import math
import pandas as pd
import numpy as np
from .base import MultiStockStrategy


class InstitutionalTrendStrategy(MultiStockStrategy):
    """终极趋势策略 v6.2 (多股票支持版)"""
    
    def __init__(self, cfg, symbols=None):
        super().__init__(symbols=symbols)
        self.cfg = cfg
        
        # 参数配置
        self.stop_loss_pct = cfg.get('stop_loss_pct', 0.10)
        self.trailing_stop_pct = cfg.get('trailing_stop_pct', 0.20)
        self.unit_size = cfg.get('unit_size', 0.1)
        self.max_units = cfg.get('max_units', 4)
        self.initial_capital = cfg.get('total_capital', 100000.0)
        
        # 分档止盈参数
        self.profit_tier1 = cfg.get('profit_tier1', 0.30)
        self.trailing_tier1 = cfg.get('trailing_tier1', 0.15)
        self.profit_tier2 = cfg.get('profit_tier2', 0.50)
        self.trailing_tier2 = cfg.get('trailing_tier2', 0.10)
        
        # 分批出场参数
        self.partial_exit_pct = cfg.get('partial_exit_pct', 0.5)
        self.enable_partial_exit = cfg.get('enable_partial_exit', True)
        
        # 多股票指标数据
        self.indicators = {}  # symbol -> DataFrame
        self.current_idx = {}  # symbol -> int
    
    def prepare(self, data):
        """预处理数据（支持单股票和多股票）"""
        if isinstance(data, dict):
            # 多股票模式
            for symbol, df in data.items():
                self.indicators[symbol] = self._calculate_indicators(df, symbol)
                self.current_idx[symbol] = 0
                self._init_symbol_state(symbol)
        else:
            # 单股票模式
            symbol = "STOCK"
            self.indicators[symbol] = self._calculate_indicators(data, symbol)
            self.current_idx[symbol] = 0
            self._init_symbol_state(symbol)
        
        return data
    
    def _init_symbol_state(self, symbol):
        """初始化单只股票的状态"""
        self.init_symbol_state(
            symbol,
            units_held=0,           # 当前头寸份数
            avg_price=0.0,          # 平均成本
            peak_price=0.0,         # 入场后最高价
            partial_exited=False,   # 是否已部分止盈
            initial_shares=0        # 初始买入股数
        )
    
    def _calculate_indicators(self, df, symbol):
        """计算技术指标"""
        df = df.copy()
        
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
        df['Bias'] = df['close'] / df['MA20']
        
        # === 5. 趋势强度判定 ===
        df['Strong_Trend'] = (
            (df['MA20'] > df['MA60'] * 1.02) & 
            (df['MA60'].diff(3) >= 0)
        )
        
        # === 6. 入场信号 ===
        df['MA10_Cross_Up'] = (
            (df['MA10'] > df['MA20']) & 
            (df['MA10'].shift(1) <= df['MA20'].shift(1))
        )
        df['MACD_Bullish'] = (df['DIF'] > df['DEA']) & (df['DIF'] > 0)
        
        # === 7. 加仓信号 ===
        df['Pullback_Support'] = (
            (df['low'] < df['MA20'] * 1.02) &
            (df['low'] > df['MA20'] * 0.98) &
            (df['close'] > df['open']) &
            (df['close'] > df['MA20']) &
            (df['Bias'] < 1.05)
        )
        
        # === 8. 离场信号 ===
        df['Trend_Broken'] = (
            (df['close'] < df['MA20'] * 0.98) & 
            (df['volume'] > df['MA_Vol'] * 1.2)
        )
        
        # 填充 NaN
        df = df.ffill().bfill()
        
        bool_cols = ['Strong_Trend', 'MA10_Cross_Up', 'MACD_Bullish', 'Pullback_Support', 'Trend_Broken']
        for col in bool_cols:
            df[col] = df[col].fillna(False)
        
        return df
    
    def on_bar(self, bar, account, symbol=None):
        """每日调用，返回交易信号"""
        if symbol is None:
            symbol = "STOCK"
        
        # 检查是否已预处理
        if symbol not in self.indicators:
            return None, 0
        
        # 获取当前索引
        idx = self.current_idx.get(symbol, 0)
        if idx >= len(self.indicators[symbol]):
            self.current_idx[symbol] = idx + 1
            return None, 0
        
        row = self.indicators[symbol].iloc[idx]
        price = bar['close']
        high = bar['high']
        
        # 获取该股票的状态
        state = self.state.get(symbol, {})
        units_held = state.get('units_held', 0)
        avg_price = state.get('avg_price', 0.0)
        peak_price = state.get('peak_price', 0.0)
        partial_exited = state.get('partial_exited', False)
        
        # 更新持有期间最高价
        if units_held > 0:
            peak_price = max(peak_price, high)
            self.set_symbol_state(symbol, 'peak_price', peak_price)
        
        action = None
        shares = 0
        
        # ========== A. 入场与加仓逻辑 ==========
        if row['Strong_Trend']:
            # === 1. 初次建仓 ===
            if units_held == 0:
                bias_ok = row['Bias'] < 1.08
                if (row['MA10_Cross_Up'] or (row['MA10'] > row['MA20'] and row['MACD_Bullish'])) and bias_ok:
                    action = "BUY"
                    shares = self._calc_shares(account, price)
                    if shares > 0:
                        self._update_status(symbol, "ENTRY", price, shares)
                    else:
                        action = None
            
            # === 2. 回调加仓 ===
            elif units_held < self.max_units:
                if row['Pullback_Support']:
                    action = "BUY"
                    shares = self._calc_shares(account, price)
                    if shares > 0:
                        self._update_status(symbol, "ADD", price, shares)
                    else:
                        action = None
        
        # ========== B. 离场逻辑 ==========
        current_shares = account.get_shares(symbol)
        if units_held > 0 and current_shares > 0:
            should_exit = False
            exit_reason = ""
            current_profit = (price / avg_price - 1) if avg_price > 0 else 0
            
            # 分档动态止盈
            dynamic_trailing = self.trailing_stop_pct
            if current_profit > self.profit_tier2:
                dynamic_trailing = self.trailing_tier2
            elif current_profit > self.profit_tier1:
                dynamic_trailing = self.trailing_tier1
            
            # 1. 动态移动止盈
            if peak_price > 0 and price < peak_price * (1 - dynamic_trailing):
                if self.enable_partial_exit and not partial_exited and current_profit > 0.10:
                    partial_shares = math.floor(current_shares * self.partial_exit_pct / 100) * 100
                    if partial_shares > 0:
                        action = "SELL"
                        shares = partial_shares
                        self.set_symbol_state(symbol, 'partial_exited', True)
                        # 更新 units_held
                        self.set_symbol_state(symbol, 'units_held', max(1, units_held - 1))
                        self.set_symbol_state(symbol, 'peak_price', price)
                        exit_reason = f"分批止盈(卖{self.partial_exit_pct*100:.0f}%)"
                        self._record_exit(symbol, exit_reason, avg_price)
                    else:
                        should_exit = True
                        exit_reason = f"分档止盈({dynamic_trailing*100:.0f}%)"
                else:
                    should_exit = True
                    exit_reason = f"分档止盈({dynamic_trailing*100:.0f}%)"
            
            # 2. 放量破位
            elif row['Trend_Broken']:
                should_exit = True
                exit_reason = "放量破位"
            
            # 3. 硬止损
            elif avg_price > 0 and price < avg_price * (1 - self.stop_loss_pct):
                should_exit = True
                exit_reason = "硬止损"
            
            # 执行全部卖出
            if should_exit:
                action = "SELL"
                shares = current_shares
                self._record_exit(symbol, exit_reason, avg_price)
                self._clear_status(symbol)
        
        # 更新索引
        self.current_idx[symbol] = idx + 1
        
        return action, shares
    
    def _calc_shares(self, account, price):
        """计算买入股数（使用账户的仓位计算器）"""
        if price <= 0:
            return 0
        
        available_slots = account.get_available_slots()
        if available_slots <= 0:
            return 0
        
        return account.position_sizer.calculate_shares(account.cash, price, available_slots)
    
    def _update_status(self, symbol, action_type, price, shares):
        """更新持仓状态"""
        if action_type == "ENTRY":
            self.set_symbol_state(symbol, 'units_held', 1)
            self.set_symbol_state(symbol, 'avg_price', price)
            self.set_symbol_state(symbol, 'peak_price', price)
            self.set_symbol_state(symbol, 'partial_exited', False)
            self.set_symbol_state(symbol, 'initial_shares', shares)
        elif action_type == "ADD":
            state = self.state.get(symbol, {})
            old_units = state.get('units_held', 0)
            old_avg = state.get('avg_price', 0.0)
            new_avg = (old_avg * old_units + price) / (old_units + 1)
            self.set_symbol_state(symbol, 'avg_price', new_avg)
            self.set_symbol_state(symbol, 'units_held', old_units + 1)
    
    def _clear_status(self, symbol):
        """清空持仓状态"""
        self.set_symbol_state(symbol, 'units_held', 0)
        self.set_symbol_state(symbol, 'avg_price', 0.0)
        self.set_symbol_state(symbol, 'peak_price', 0.0)
        self.set_symbol_state(symbol, 'partial_exited', False)
        self.set_symbol_state(symbol, 'initial_shares', 0)
    
    def _record_exit(self, symbol, reason, avg_price):
        """记录退出信息"""
        self.set_symbol_state(symbol, '_exit_reason', reason)
        self.set_symbol_state(symbol, '_exit_avg_price', avg_price)
    
    def record_action(self, action_type, price, date, symbol=None):
        """记录交易动作"""
        if symbol is None:
            symbol = "STOCK"
        
        str_date = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)
        state = self.state.get(symbol, {})
        units_held = state.get('units_held', 0)
        avg_price = state.get('avg_price', 0.0)
        partial_exited = state.get('partial_exited', False)
        
        if action_type == "BUY":
            if units_held == 1:
                print(f"  >>> [{symbol}] 初始建仓 {str_date} | 价格: {price:.2f}")
            else:
                print(f"  >>> [{symbol}] 回调加仓 {str_date} | 价格: {price:.2f} | 成本: {avg_price:.2f}")
        
        elif action_type == "SELL":
            reason = state.get('_exit_reason', '未知')
            exit_avg = state.get('_exit_avg_price', avg_price)
            if exit_avg > 0:
                pnl_pct = (price / exit_avg - 1) * 100
            else:
                pnl_pct = 0.0
            
            if partial_exited and "分批" in reason:
                print(f"  <-> [{symbol}] 分批卖出 {str_date} | 价格: {price:.2f} | 原因: {reason} | 收益: {pnl_pct:+.2f}%")
            else:
                print(f"  <<< [{symbol}] 卖出离场 {str_date} | 价格: {price:.2f} | 原因: {reason} | 收益: {pnl_pct:+.2f}%")
