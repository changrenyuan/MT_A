import numpy as np
import pandas as pd


class MetricsCalculator:
    @staticmethod
    def calculate(df, initial_capital):
        # 1. 收益率
        total_return = (df['equity'].iloc[-1] / initial_capital) - 1
        # 2. 最大回撤 (MDD)
        equity = df['equity']
        max_equity = equity.cummax()
        drawdowns = (equity - max_equity) / max_equity
        max_mdd = drawdowns.min()
        # 3. 年化收益 (假设252个交易日)
        days = len(df)
        annual_return = (1 + total_return) ** (252 / days) - 1
        # 4. 夏普比率 (无风险利率设为3%)
        returns = equity.pct_change().dropna()
        sharpe = (returns.mean() * 252 - 0.03) / (returns.std() * np.sqrt(252))

        return {
            "累计收益率": f"{total_return * 100:.2f}%",
            "年化收益率": f"{annual_return * 100:.2f}%",
            "最大回撤": f"{max_mdd * 100:.2f}%",
            "夏普比率": f"{sharpe:.2f}",
            "交易天数": days
        }