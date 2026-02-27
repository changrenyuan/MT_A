"""
绩效指标计算模块

支持计算的指标：
- 收益率指标：累计收益率、年化收益率
- 风险指标：最大回撤、年化波动率、下行波动率
- 风险调整收益：夏普比率、索提诺比率、卡玛比率
- 交易统计：胜率、盈亏比、交易次数、平均持仓天数
"""
import numpy as np
import pandas as pd
from typing import Dict, Any


class MetricsCalculator:
    """绩效指标计算器"""
    
    @staticmethod
    def calculate(df: pd.DataFrame, initial_capital: float) -> Dict[str, Any]:
        """
        计算完整绩效指标
        
        Args:
            df: 回测结果DataFrame，需包含 equity, pnl, buy_signal, sell_signal 等列
            initial_capital: 初始资金
        
        Returns:
            包含所有绩效指标的字典
        """
        if len(df) == 0 or initial_capital <= 0:
            return MetricsCalculator._empty_metrics()
        
        equity = df['equity']
        pnl = df['pnl']
        
        # === 收益率指标 ===
        total_return = MetricsCalculator._calc_total_return(equity, initial_capital)
        annual_return = MetricsCalculator._calc_annual_return(equity, initial_capital)
        
        # === 风险指标 ===
        max_drawdown = MetricsCalculator._calc_max_drawdown(equity)
        annual_volatility = MetricsCalculator._calc_annual_volatility(equity)
        downside_volatility = MetricsCalculator._calc_downside_volatility(equity)
        
        # === 风险调整收益 ===
        sharpe_ratio = MetricsCalculator._calc_sharpe_ratio(equity)
        sortino_ratio = MetricsCalculator._calc_sortino_ratio(equity, downside_volatility)
        calmar_ratio = MetricsCalculator._calc_calmar_ratio(annual_return, max_drawdown)
        
        # === 交易统计 ===
        trade_stats = MetricsCalculator._calc_trade_stats(df)
        
        return {
            # 收益率指标
            "累计收益率": f"{total_return * 100:.2f}%",
            "年化收益率": f"{annual_return * 100:.2f}%",
            
            # 风险指标
            "最大回撤": f"{max_drawdown * 100:.2f}%",
            "年化波动率": f"{annual_volatility * 100:.2f}%",
            "下行波动率": f"{downside_volatility * 100:.2f}%",
            
            # 风险调整收益
            "夏普比率": f"{sharpe_ratio:.2f}",
            "索提诺比率": f"{sortino_ratio:.2f}",
            "卡玛比率": f"{calmar_ratio:.2f}",
            
            # 交易统计
            "交易天数": len(df),
            "交易次数": trade_stats['total_trades'],
            "盈利次数": trade_stats['win_trades'],
            "亏损次数": trade_stats['loss_trades'],
            "胜率": f"{trade_stats['win_rate'] * 100:.1f}%",
            "盈亏比": f"{trade_stats['profit_loss_ratio']:.2f}",
            
            # 原始数值 (用于报告生成)
            "_raw": {
                "total_return": total_return,
                "annual_return": annual_return,
                "max_drawdown": max_drawdown,
                "annual_volatility": annual_volatility,
                "sharpe_ratio": sharpe_ratio,
                "sortino_ratio": sortino_ratio,
                "calmar_ratio": calmar_ratio,
                **trade_stats
            }
        }
    
    @staticmethod
    def _empty_metrics() -> Dict[str, Any]:
        """返回空指标"""
        return {
            "累计收益率": "0.00%",
            "年化收益率": "0.00%",
            "最大回撤": "0.00%",
            "年化波动率": "0.00%",
            "下行波动率": "0.00%",
            "夏普比率": "0.00",
            "索提诺比率": "0.00",
            "卡玛比率": "0.00",
            "交易天数": 0,
            "交易次数": 0,
            "盈利次数": 0,
            "亏损次数": 0,
            "胜率": "0.0%",
            "盈亏比": "0.00",
            "_raw": {}
        }
    
    @staticmethod
    def _calc_total_return(equity: pd.Series, initial_capital: float) -> float:
        """计算累计收益率"""
        if initial_capital <= 0:
            return 0.0
        return (equity.iloc[-1] / initial_capital) - 1
    
    @staticmethod
    def _calc_annual_return(equity: pd.Series, initial_capital: float) -> float:
        """计算年化收益率"""
        days = len(equity)
        if days <= 0:
            return 0.0
        total_return = MetricsCalculator._calc_total_return(equity, initial_capital)
        return (1 + total_return) ** (252 / days) - 1
    
    @staticmethod
    def _calc_max_drawdown(equity: pd.Series) -> float:
        """计算最大回撤"""
        max_equity = equity.cummax()
        # 避免除零
        max_equity_safe = max_equity.replace(0, np.nan)
        drawdowns = (equity - max_equity) / max_equity_safe
        drawdowns = drawdowns.fillna(0)
        return abs(drawdowns.min())
    
    @staticmethod
    def _calc_annual_volatility(equity: pd.Series) -> float:
        """计算年化波动率"""
        returns = equity.pct_change().dropna()
        if len(returns) <= 1:
            return 0.0
        return returns.std() * np.sqrt(252)
    
    @staticmethod
    def _calc_downside_volatility(equity: pd.Series, risk_free_rate: float = 0.03) -> float:
        """计算下行波动率 (只考虑负收益)"""
        returns = equity.pct_change().dropna()
        if len(returns) <= 1:
            return 0.0
        daily_rf = risk_free_rate / 252
        downside_returns = returns[returns < daily_rf] - daily_rf
        if len(downside_returns) == 0:
            return 0.0
        return np.sqrt((downside_returns ** 2).mean()) * np.sqrt(252)
    
    @staticmethod
    def _calc_sharpe_ratio(equity: pd.Series, risk_free_rate: float = 0.03) -> float:
        """计算夏普比率"""
        returns = equity.pct_change().dropna()
        if len(returns) <= 1:
            return 0.0
        std = returns.std()
        if std <= 0 or np.isnan(std):
            return 0.0
        excess_return = returns.mean() * 252 - risk_free_rate
        return excess_return / (std * np.sqrt(252))
    
    @staticmethod
    def _calc_sortino_ratio(equity: pd.Series, downside_vol: float, risk_free_rate: float = 0.03) -> float:
        """计算索提诺比率"""
        if downside_vol <= 0:
            return 0.0
        returns = equity.pct_change().dropna()
        if len(returns) <= 1:
            return 0.0
        excess_return = returns.mean() * 252 - risk_free_rate
        return excess_return / downside_vol
    
    @staticmethod
    def _calc_calmar_ratio(annual_return: float, max_drawdown: float) -> float:
        """计算卡玛比率"""
        if max_drawdown <= 0:
            return 0.0
        return annual_return / max_drawdown
    
    @staticmethod
    def _calc_trade_stats(df: pd.DataFrame) -> Dict[str, Any]:
        """计算交易统计"""
        buys = df[df['buy_signal'].notnull()]
        sells = df[df['sell_signal'].notnull()]
        
        total_trades = len(sells)  # 以卖出次数计
        
        if total_trades == 0:
            return {
                'total_trades': 0,
                'win_trades': 0,
                'loss_trades': 0,
                'win_rate': 0.0,
                'profit_loss_ratio': 0.0,
                'avg_profit': 0.0,
                'avg_loss': 0.0,
            }
        
        # 计算每笔交易的盈亏
        # 需要追踪买入和卖出配对
        profits = []
        buy_prices = []
        
        for i, row in df.iterrows():
            if pd.notna(row['buy_signal']):
                buy_prices.append(row['buy_signal'])
            if pd.notna(row['sell_signal']) and buy_prices:
                buy_price = buy_prices.pop(0) if buy_prices else row['sell_signal']
                profit_pct = (row['sell_signal'] / buy_price - 1)
                profits.append(profit_pct)
        
        if not profits:
            return {
                'total_trades': total_trades,
                'win_trades': 0,
                'loss_trades': 0,
                'win_rate': 0.0,
                'profit_loss_ratio': 0.0,
                'avg_profit': 0.0,
                'avg_loss': 0.0,
            }
        
        wins = [p for p in profits if p > 0]
        losses = [p for p in profits if p < 0]
        
        win_trades = len(wins)
        loss_trades = len(losses)
        win_rate = win_trades / len(profits) if profits else 0
        
        avg_profit = np.mean(wins) if wins else 0
        avg_loss = abs(np.mean(losses)) if losses else 0
        profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0
        
        return {
            'total_trades': total_trades,
            'win_trades': win_trades,
            'loss_trades': loss_trades,
            'win_rate': win_rate,
            'profit_loss_ratio': profit_loss_ratio,
            'avg_profit': avg_profit,
            'avg_loss': avg_loss,
        }
    
    @staticmethod
    def calc_monthly_returns(df: pd.DataFrame) -> pd.DataFrame:
        """计算月度收益率"""
        if len(df) == 0:
            return pd.DataFrame()
        
        equity = df['equity']
        monthly = equity.resample('M').last()
        monthly_returns = monthly.pct_change().dropna()
        
        # 构建月度收益表
        monthly_df = pd.DataFrame({
            '月份': monthly_returns.index.strftime('%Y-%m'),
            '收益率': monthly_returns.values
        })
        
        return monthly_df
    
    @staticmethod
    def calc_yearly_returns(df: pd.DataFrame) -> pd.DataFrame:
        """计算年度收益率"""
        if len(df) == 0:
            return pd.DataFrame()
        
        equity = df['equity']
        yearly = equity.resample('Y').last()
        yearly_returns = yearly.pct_change().dropna()
        
        yearly_df = pd.DataFrame({
            '年份': yearly_returns.index.strftime('%Y'),
            '收益率': yearly_returns.values
        })
        
        return yearly_df
    
    @staticmethod
    def calc_drawdown_series(df: pd.DataFrame) -> pd.Series:
        """计算回撤序列"""
        if len(df) == 0:
            return pd.Series()
        
        equity = df['equity']
        max_equity = equity.cummax()
        max_equity_safe = max_equity.replace(0, np.nan)
        drawdowns = (equity - max_equity) / max_equity_safe
        return drawdowns.fillna(0)
