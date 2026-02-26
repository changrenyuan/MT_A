import matplotlib.pyplot as plt
import numpy as np


class Plotter:
    @staticmethod
    def plot_results(res, symbol, title_suffix=""):
        plt.rcParams['font.sans-serif'] = ['SimHei']
        plt.rcParams['axes.unicode_minus'] = False

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10), sharex=True, gridspec_kw={'height_ratios': [1.5, 1]})

        # --- 上图：价格与交易信号 ---
        ax1.plot(res.index, res['price'], label='股价', color='#bdc3c7', alpha=0.5)
        ax1.plot(res.index, res['avg_price'].replace(0, np.nan), label='持仓均价', color='#f39c12', linestyle='--',
                 linewidth=1.5)

        buys = res[res['buy_signal'].notnull()]
        sells = res[res['sell_signal'].notnull()]
        ax1.scatter(buys.index, buys['buy_signal'], color='#e74c3c', marker='^', s=80, label='买入', zorder=5)
        ax1.scatter(sells.index, sells['sell_signal'], color='#2ecc71', marker='v', s=80, label='卖出', zorder=5)

        ax1.set_title(f"马丁格尔策略回测: {symbol} ({title_suffix})", fontsize=14, pad=20)
        ax1.legend(loc='upper left')
        ax1.grid(True, linestyle=':', alpha=0.6)

        # --- 下图：资金与损益 (核心改进) ---
        # 1. 绘制总资产 (Equity)
        ax2.plot(res.index, res['equity'], label='总资产 (现金+市值)', color='#2980b9', linewidth=2)

        # 2. 绘制持仓市值 (Market Value) - 阴影区域
        ax2.fill_between(res.index, res['market_value'], 0, color='#3498db', alpha=0.2, label='持仓市值')

        # 3. 绘制 PnL (累计净损益) - 独立轴或同轴线
        ax2_pnl = ax2.twinx()  # 创建右侧 Y 轴用于显示盈亏金额
        ax2_pnl.plot(res.index, res['pnl'], label='累计盈亏 (PnL)', color='#e67e22', linewidth=1.5)
        ax2_pnl.axhline(0, color='black', linestyle='-', linewidth=0.5, alpha=0.5)  # 0轴线

        # 标签处理
        ax2.set_ylabel("金额 (元)")
        ax2_pnl.set_ylabel("盈亏额 (元)")

        # 合并图例
        lines, labels = ax2.get_legend_handles_labels()
        lines2, labels2 = ax2_pnl.get_legend_handles_labels()
        ax2.legend(lines + lines2, labels + labels2, loc='upper left')

        ax2.grid(True, linestyle=':', alpha=0.6)

        plt.tight_layout()
        plt.show()