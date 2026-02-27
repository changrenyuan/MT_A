import numpy as np
import pandas as pd


class MetricsCalculator:
    @staticmethod
    def calculate(df, initial_capital):
        """计算回测绩效指标，处理边界情况"""
        
        # 安全处理初始资金
        if initial_capital <= 0:
            initial_capital = 1.0
        
        # 1. 收益率
        final_equity = df['equity'].iloc[-1] if len(df) > 0 else initial_capital
        total_return = (final_equity / initial_capital) - 1
        
        # 2. 最大回撤 (MDD)
        equity = df['equity']
        max_equity = equity.cummax()
        # 避免除零：当 max_equity 为 0 时，回撤设为 0
        max_equity_safe = max_equity.replace(0, np.nan)
        drawdowns = (equity - max_equity) / max_equity_safe
        drawdowns = drawdowns.fillna(0)
        max_mdd = drawdowns.min()
        
        # 3. 年化收益 (假设252个交易日)
        days = len(df)
        if days > 0:
            annual_return = (1 + total_return) ** (252 / days) - 1
        else:
            annual_return = 0.0
        
        # 4. 夏普比率 (无风险利率设为3%)
        returns = equity.pct_change().dropna()
        if len(returns) > 1:
            std_returns = returns.std()
            if std_returns > 0 and not np.isnan(std_returns):
                sharpe = (returns.mean() * 252 - 0.03) / (std_returns * np.sqrt(252))
            else:
                sharpe = 0.0
        else:
            sharpe = 0.0

        return {
            "累计收益率": f"{total_return * 100:.2f}%",
            "年化收益率": f"{annual_return * 100:.2f}%",
            "最大回撤": f"{max_mdd * 100:.2f}%",
            "夏普比率": f"{sharpe:.2f}",
            "交易天数": days
        }
