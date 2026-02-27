import matplotlib.pyplot as plt
import numpy as np


class Plotter:
    @staticmethod
    def plot_results(res, symbol, title_suffix=""):
        try:
            plt.rcParams['font.sans-serif'] = ['SimHei']
            plt.rcParams['axes.unicode_minus'] = False

            # === 创建 4 个子图 ===
            fig, axes = plt.subplots(4, 1, figsize=(15, 16), sharex=True)
            fig.suptitle(f"策略回测: {symbol} ({title_suffix})", fontsize=16, fontweight='bold', y=0.98)

            ax1, ax2, ax3, ax4 = axes

            # ========== 子图1: 价格与交易信号 ==========
            ax1.plot(res.index, res['price'], label='股价', color='#bdc3c7', alpha=0.5)
            
            # 安全处理 avg_price，将 0 替换为 NaN
            avg_price_safe = res['avg_price'].replace(0, np.nan)
            ax1.plot(res.index, avg_price_safe, label='持仓均价', color='#f39c12', linestyle='--', linewidth=1.5)

            # 买入/卖出信号点
            buys = res[res['buy_signal'].notnull()]
            sells = res[res['sell_signal'].notnull()]
            if len(buys) > 0:
                ax1.scatter(buys.index, buys['buy_signal'], color='#e74c3c', marker='^', s=80, label='买入', zorder=5)
            if len(sells) > 0:
                ax1.scatter(sells.index, sells['sell_signal'], color='#2ecc71', marker='v', s=80, label='卖出', zorder=5)

            ax1.set_ylabel("价格")
            ax1.legend(loc='upper left')
            ax1.grid(True, linestyle=':', alpha=0.6)
            ax1.set_title("股价走势与交易信号")

            # ========== 子图2: 总资产 ==========
            ax2.plot(res.index, res['equity'], label='总资产', color='#2980b9', linewidth=2)
            ax2.axhline(y=res['equity'].iloc[0], color='gray', linestyle='--', linewidth=0.8, label='初始资金')
            ax2.set_ylabel("金额 (元)")
            ax2.legend(loc='upper left')
            ax2.grid(True, linestyle=':', alpha=0.6)
            ax2.set_title("总资产曲线")

            # ========== 子图3: 持仓市值 ==========
            ax3.fill_between(res.index, res['market_value'], 0, color='#3498db', alpha=0.4, label='持仓市值')
            ax3.plot(res.index, res['market_value'], color='#2980b9', linewidth=1.5)
            ax3.set_ylabel("金额 (元)")
            ax3.legend(loc='upper left')
            ax3.grid(True, linestyle=':', alpha=0.6)
            ax3.set_title("持仓市值")

            # ========== 子图4: 累计盈亏 (金额 + 比例) ==========
            # 盈亏金额 - 正负阴影
            pnl = res['pnl']
            ax4.fill_between(res.index, pnl, 0, where=(pnl >= 0), 
                           color='#e74c3c', alpha=0.4, label='浮盈 (金额)')
            ax4.fill_between(res.index, pnl, 0, where=(pnl < 0), 
                           color='#3498db', alpha=0.4, label='浮亏 (金额)')
            ax4.plot(res.index, pnl, color='#7f8c8d', linewidth=1.5)
            ax4.axhline(0, color='black', linestyle='-', linewidth=0.5)
            
            ax4.set_ylabel("盈亏金额 (元)")
            ax4.set_xlabel("日期")
            ax4.legend(loc='upper left')
            ax4.grid(True, linestyle=':', alpha=0.6)
            ax4.set_title("累计盈亏 (红色=盈利, 蓝色=亏损)")

            # 在右侧添加盈亏比例轴
            # 获取初始资金 (从 equity 列第一个值)
            initial_capital = res['equity'].iloc[0] if len(res) > 0 else 100000
            ax4_twin = ax4.twinx()
            
            # 计算盈亏比例
            pnl_pct = (pnl / initial_capital) * 100 if initial_capital > 0 else pnl * 0
            ax4_twin.plot(res.index, pnl_pct, color='#9b59b6', linewidth=1, linestyle=':', alpha=0.7)
            ax4_twin.set_ylabel("盈亏比例 (%)", color='#9b59b6')
            ax4_twin.tick_params(axis='y', labelcolor='#9b59b6')
            
            # 标注最终盈亏
            final_pnl = pnl.iloc[-1] if len(pnl) > 0 else 0
            final_pnl_pct = (final_pnl / initial_capital) * 100 if initial_capital > 0 else 0
            color = '#e74c3c' if final_pnl >= 0 else '#3498db'
            ax4.text(0.02, 0.95, f"最终盈亏: {final_pnl:+,.0f} 元 ({final_pnl_pct:+.2f}%)", 
                    transform=ax4.transAxes, fontsize=12, fontweight='bold',
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor=color, alpha=0.3))

            plt.tight_layout(rect=[0, 0, 1, 0.96])  # 为总标题留出空间
            plt.show()
            
        except Exception as e:
            print(f"[绘图错误] {e}")
            import traceback
            traceback.print_exc()
