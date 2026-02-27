"""
回测结果可视化模块

支持图表：
1. 股价走势与交易信号
2. 总资产曲线
3. 持仓市值
4. 累计盈亏
5. 回撤曲线
6. 月度/年度收益分布
"""
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from typing import Optional
import os


class Plotter:
    """回测结果绘图器"""
    
    @staticmethod
    def plot_results(res: pd.DataFrame, symbol: str, title_suffix: str = "", 
                     save_dir: str = "reports/charts", show: bool = False):
        """
        绘制完整回测结果 (6个子图)
        
        Args:
            res: 回测结果 DataFrame
            symbol: 股票代码
            title_suffix: 标题后缀
            save_dir: 保存目录
            show: 是否显示图表 (默认 False，只保存)
        """
        try:
            plt.rcParams['font.sans-serif'] = ['SimHei']
            plt.rcParams['axes.unicode_minus'] = False

            # === 创建 6 个子图 ===
            fig, axes = plt.subplots(6, 1, figsize=(16, 24), sharex=True)
            fig.suptitle(f"策略回测: {symbol} ({title_suffix})", fontsize=18, fontweight='bold', y=0.995)

            ax1, ax2, ax3, ax4, ax5, ax6 = axes

            # ========== 子图1: 价格与交易信号 ==========
            Plotter._plot_price_and_signals(ax1, res)

            # ========== 子图2: 总资产 ==========
            Plotter._plot_equity(ax2, res)

            # ========== 子图3: 持仓市值 ==========
            Plotter._plot_market_value(ax3, res)

            # ========== 子图4: 累计盈亏 ==========
            initial_capital = res['equity'].iloc[0] if len(res) > 0 else 100000
            Plotter._plot_pnl(ax4, res, initial_capital)

            # ========== 子图5: 回撤曲线 ==========
            Plotter._plot_drawdown(ax5, res)

            # ========== 子图6: 滚动收益 (月度) ==========
            Plotter._plot_rolling_returns(ax6, res)

            plt.tight_layout(rect=[0, 0, 1, 0.99])
            
            # 保存到文件
            os.makedirs(save_dir, exist_ok=True)
            safe_symbol = symbol.replace("/", "_").replace("\\", "_")
            filepath = os.path.join(save_dir, f"{safe_symbol}_backtest.png")
            fig.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
            print(f"  📈 图表已保存: {filepath}")
            
            if show:
                plt.show()
            else:
                plt.close(fig)
            
            return filepath
            
        except Exception as e:
            print(f"[绘图错误] {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def plot_multi_stock(res: pd.DataFrame, symbols: list, title: str = "多股票组合回测",
                         save_dir: str = "reports/charts", show: bool = False):
        """
        为多股票组合绘制图表 (每只股票单独一张图)
        
        Args:
            res: 回测结果 DataFrame
            symbols: 股票代码列表
            title: 总标题
            save_dir: 保存目录
            show: 是否显示
        """
        saved_files = []
        
        for symbol in symbols:
            # 检查是否有该股票的数据
            shares_col = f"{symbol}_shares"
            if shares_col not in res.columns:
                continue
            
            # 为每只股票创建单独的图
            filepath = Plotter._plot_single_stock_summary(res, symbol, save_dir, show)
            if filepath:
                saved_files.append(filepath)
        
        # 绘制组合总览图
        overview_path = Plotter._plot_portfolio_overview(res, symbols, title, save_dir, show)
        if overview_path:
            saved_files.append(overview_path)
        
        return saved_files
    
    @staticmethod
    def _plot_single_stock_summary(res: pd.DataFrame, symbol: str, 
                                   save_dir: str, show: bool = False):
        """绘制单只股票的简要图表"""
        try:
            plt.rcParams['font.sans-serif'] = ['SimHei']
            plt.rcParams['axes.unicode_minus'] = False
            
            fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=True)
            fig.suptitle(f"股票回测: {symbol}", fontsize=14, fontweight='bold')
            
            ax1, ax2, ax3 = axes
            
            # 子图1: 价格与信号
            Plotter._plot_single_price(ax1, res, symbol)
            
            # 子图2: 持仓股数
            Plotter._plot_single_position(ax2, res, symbol)
            
            # 子图3: 该股票盈亏贡献 (简化版)
            Plotter._plot_single_contribution(ax3, res, symbol)
            
            plt.tight_layout(rect=[0, 0, 1, 0.98])
            
            # 保存
            os.makedirs(save_dir, exist_ok=True)
            safe_symbol = symbol.replace("/", "_").replace("\\", "_")
            filepath = os.path.join(save_dir, f"{safe_symbol}_summary.png")
            fig.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
            print(f"  📈 图表已保存: {filepath}")
            
            if show:
                plt.show()
            else:
                plt.close(fig)
            
            return filepath
            
        except Exception as e:
            print(f"[绘图错误] {symbol}: {e}")
            return None
    
    @staticmethod
    def _plot_single_price(ax, res: pd.DataFrame, symbol: str):
        """绘制单只股票价格"""
        shares_col = f"{symbol}_shares"
        avg_col = f"{symbol}_avg_price"
        
        # 尝试获取价格数据
        price_col = 'price'
        
        ax.plot(res.index, res[price_col], label='参考价格', color='#bdc3c7', alpha=0.6, linewidth=1)
        
        # 持仓均价
        if avg_col in res.columns:
            avg_price_safe = res[avg_col].replace(0, np.nan)
            ax.plot(res.index, avg_price_safe, label='持仓均价', color='#f39c12', linestyle='--', linewidth=1.5)
        
        # 买入/卖出信号
        buys = res[res['buy_signal'].notnull()]
        sells = res[res['sell_signal'].notnull()]
        if len(buys) > 0:
            ax.scatter(buys.index, buys['buy_signal'], color='#e74c3c', marker='^', s=60, label='买入', zorder=5)
        if len(sells) > 0:
            ax.scatter(sells.index, sells['sell_signal'], color='#2ecc71', marker='v', s=60, label='卖出', zorder=5)
        
        ax.set_ylabel("价格")
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(True, linestyle=':', alpha=0.5)
        ax.set_title(f"{symbol} 价格走势与信号", fontsize=10)
    
    @staticmethod
    def _plot_single_position(ax, res: pd.DataFrame, symbol: str):
        """绘制单只股票持仓"""
        shares_col = f"{symbol}_shares"
        cost_col = f"{symbol}_cost"
        
        if shares_col not in res.columns:
            ax.text(0.5, 0.5, '无持仓数据', transform=ax.transAxes, ha='center', va='center')
            return
        
        shares = res[shares_col]
        
        # 柱状图显示持仓股数
        colors = ['#3498db' if s > 0 else '#ecf0f1' for s in shares]
        ax.bar(res.index, shares, color=colors, alpha=0.6, width=1.5)
        ax.set_ylabel("持仓股数")
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(True, linestyle=':', alpha=0.5)
        ax.set_title(f"{symbol} 持仓变化", fontsize=10)
    
    @staticmethod
    def _plot_single_contribution(ax, res: pd.DataFrame, symbol: str):
        """绘制单只股票对组合的贡献"""
        shares_col = f"{symbol}_shares"
        cost_col = f"{symbol}_cost"
        
        if shares_col not in res.columns or cost_col not in res.columns:
            ax.text(0.5, 0.5, '无数据', transform=ax.transAxes, ha='center', va='center')
            return
        
        # 简化：显示持仓成本
        cost = res[cost_col]
        ax.fill_between(res.index, cost, 0, color='#3498db', alpha=0.4, label='持仓成本')
        ax.plot(res.index, cost, color='#2980b9', linewidth=1.5)
        ax.set_ylabel("持仓成本 (元)")
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(True, linestyle=':', alpha=0.5)
        ax.set_title(f"{symbol} 持仓成本", fontsize=10)
    
    @staticmethod
    def _plot_portfolio_overview(res: pd.DataFrame, symbols: list, title: str,
                                 save_dir: str, show: bool = False):
        """绘制组合总览图"""
        try:
            plt.rcParams['font.sans-serif'] = ['SimHei']
            plt.rcParams['axes.unicode_minus'] = False
            
            fig, axes = plt.subplots(3, 1, figsize=(16, 14), sharex=True)
            fig.suptitle(title, fontsize=16, fontweight='bold')
            
            ax1, ax2, ax3 = axes
            
            # 子图1: 总资产曲线
            Plotter._plot_equity(ax1, res)
            
            # 子图2: 各股票持仓堆叠
            Plotter._plot_positions_stacked(ax2, res, symbols)
            
            # 子图3: 累计盈亏
            initial_capital = res['equity'].iloc[0] if len(res) > 0 else 100000
            Plotter._plot_pnl(ax3, res, initial_capital)
            
            plt.tight_layout(rect=[0, 0, 1, 0.98])
            
            # 保存
            os.makedirs(save_dir, exist_ok=True)
            filepath = os.path.join(save_dir, "portfolio_overview.png")
            fig.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
            print(f"  📈 组合总览图已保存: {filepath}")
            
            if show:
                plt.show()
            else:
                plt.close(fig)
            
            return filepath
            
        except Exception as e:
            print(f"[绘图错误] 组合总览: {e}")
            return None
    
    @staticmethod
    def _plot_positions_stacked(ax, res: pd.DataFrame, symbols: list):
        """绘制各股票持仓堆叠图"""
        colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6']
        
        # 收集各股票的市值
        position_values = []
        labels = []
        for i, symbol in enumerate(symbols):
            shares_col = f"{symbol}_shares"
            cost_col = f"{symbol}_cost"
            
            if shares_col not in res.columns:
                continue
            
            # 使用成本作为市值近似
            if cost_col in res.columns:
                position_values.append(res[cost_col])
                labels.append(symbol)
        
        if not position_values:
            ax.text(0.5, 0.5, '无持仓数据', transform=ax.transAxes, ha='center', va='center')
            return
        
        # 堆叠面积图
        ax.stackplot(res.index, position_values, labels=labels, 
                    colors=colors[:len(labels)], alpha=0.7)
        ax.set_ylabel("持仓成本 (元)")
        ax.legend(loc='upper left', fontsize=8, ncol=len(labels))
        ax.grid(True, linestyle=':', alpha=0.5)
        ax.set_title("各股票持仓分布", fontsize=10)
    
    @staticmethod
    def _plot_price_and_signals(ax, res: pd.DataFrame):
        """绘制价格与交易信号"""
        ax.plot(res.index, res['price'], label='股价', color='#bdc3c7', alpha=0.6, linewidth=1)
        
        # 持仓均价
        if 'avg_price' in res.columns:
            avg_price_safe = res['avg_price'].replace(0, np.nan)
            ax.plot(res.index, avg_price_safe, label='持仓均价', color='#f39c12', linestyle='--', linewidth=1.5)

        # 买入/卖出信号点
        if 'buy_signal' in res.columns:
            buys = res[res['buy_signal'].notnull()]
            if len(buys) > 0:
                ax.scatter(buys.index, buys['buy_signal'], color='#e74c3c', marker='^', s=80, label='买入', zorder=5)
        
        if 'sell_signal' in res.columns:
            sells = res[res['sell_signal'].notnull()]
            if len(sells) > 0:
                ax.scatter(sells.index, sells['sell_signal'], color='#2ecc71', marker='v', s=80, label='卖出', zorder=5)

        ax.set_ylabel("价格")
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(True, linestyle=':', alpha=0.5)
        ax.set_title("股价走势与交易信号", fontsize=10)
    
    @staticmethod
    def _plot_equity(ax, res: pd.DataFrame):
        """绘制总资产曲线"""
        ax.plot(res.index, res['equity'], label='总资产', color='#2980b9', linewidth=2)
        ax.axhline(y=res['equity'].iloc[0], color='gray', linestyle='--', linewidth=0.8, label='初始资金', alpha=0.7)
        ax.fill_between(res.index, res['equity'], res['equity'].iloc[0], 
                       where=(res['equity'] >= res['equity'].iloc[0]),
                       color='#2ecc71', alpha=0.2)
        ax.fill_between(res.index, res['equity'], res['equity'].iloc[0], 
                       where=(res['equity'] < res['equity'].iloc[0]),
                       color='#e74c3c', alpha=0.2)
        ax.set_ylabel("金额 (元)")
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(True, linestyle=':', alpha=0.5)
        ax.set_title("总资产曲线", fontsize=10)
    
    @staticmethod
    def _plot_market_value(ax, res: pd.DataFrame):
        """绘制持仓市值"""
        ax.fill_between(res.index, res['market_value'], 0, color='#3498db', alpha=0.4, label='持仓市值')
        ax.plot(res.index, res['market_value'], color='#2980b9', linewidth=1.5)
        ax.set_ylabel("金额 (元)")
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(True, linestyle=':', alpha=0.5)
        ax.set_title("持仓市值", fontsize=10)
    
    @staticmethod
    def _plot_pnl(ax, res: pd.DataFrame, initial_capital: float):
        """绘制累计盈亏"""
        pnl = res['pnl']
        
        # 盈亏金额 - 正负阴影
        ax.fill_between(res.index, pnl, 0, where=(pnl >= 0), 
                       color='#e74c3c', alpha=0.4, label='浮盈')
        ax.fill_between(res.index, pnl, 0, where=(pnl < 0), 
                       color='#3498db', alpha=0.4, label='浮亏')
        ax.plot(res.index, pnl, color='#7f8c8d', linewidth=1.5)
        ax.axhline(0, color='black', linestyle='-', linewidth=0.5)
        
        ax.set_ylabel("盈亏金额 (元)")
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(True, linestyle=':', alpha=0.5)
        ax.set_title("累计盈亏 (红色=盈利, 蓝色=亏损)", fontsize=10)

        # 右侧 Y 轴 - 盈亏比例
        ax_twin = ax.twinx()
        pnl_pct = (pnl / initial_capital) * 100 if initial_capital > 0 else pnl * 0
        ax_twin.plot(res.index, pnl_pct, color='#9b59b6', linewidth=1, linestyle=':', alpha=0.5)
        ax_twin.set_ylabel("盈亏比例 (%)", color='#9b59b6', fontsize=8)
        ax_twin.tick_params(axis='y', labelcolor='#9b59b6', labelsize=7)
        
        # 标注最终盈亏
        final_pnl = pnl.iloc[-1] if len(pnl) > 0 else 0
        final_pnl_pct = (final_pnl / initial_capital) * 100 if initial_capital > 0 else 0
        color = '#e74c3c' if final_pnl >= 0 else '#3498db'
        ax.text(0.02, 0.95, f"最终: {final_pnl:+,.0f}元 ({final_pnl_pct:+.2f}%)", 
                transform=ax.transAxes, fontsize=10, fontweight='bold',
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor=color, alpha=0.3))
    
    @staticmethod
    def _plot_drawdown(ax, res: pd.DataFrame):
        """绘制回撤曲线"""
        equity = res['equity']
        max_equity = equity.cummax()
        max_equity_safe = max_equity.replace(0, np.nan)
        drawdowns = ((equity - max_equity) / max_equity_safe).fillna(0)
        
        ax.fill_between(res.index, drawdowns, 0, color='#e74c3c', alpha=0.3)
        ax.plot(res.index, drawdowns, color='#e74c3c', linewidth=1.5)
        ax.axhline(0, color='black', linestyle='-', linewidth=0.5)
        
        # 标注最大回撤
        max_dd = drawdowns.min()
        ax.axhline(max_dd, color='#c0392b', linestyle='--', linewidth=1, alpha=0.7)
        ax.text(0.98, 0.05, f"最大回撤: {max_dd*100:.2f}%", 
                transform=ax.transAxes, fontsize=10, fontweight='bold',
                horizontalalignment='right', color='#c0392b')
        
        ax.set_ylabel("回撤")
        ax.grid(True, linestyle=':', alpha=0.5)
        ax.set_title("回撤曲线", fontsize=10)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y*100:.1f}%'))
    
    @staticmethod
    def _plot_rolling_returns(ax, res: pd.DataFrame):
        """绘制滚动收益 (月度)"""
        try:
            equity = res['equity']
            
            # 计算月度收益
            monthly = equity.resample('M').last()
            monthly_returns = monthly.pct_change().dropna()
            
            if len(monthly_returns) == 0:
                ax.text(0.5, 0.5, '数据不足，无法计算月度收益', 
                       transform=ax.transAxes, ha='center', va='center', fontsize=12)
                ax.set_title("月度收益率", fontsize=10)
                return
            
            # 绘制柱状图
            colors = ['#e74c3c' if r >= 0 else '#3498db' for r in monthly_returns]
            ax.bar(monthly_returns.index, monthly_returns * 100, color=colors, alpha=0.7, width=20)
            
            ax.axhline(0, color='black', linestyle='-', linewidth=0.5)
            ax.set_ylabel("月度收益率 (%)")
            ax.set_xlabel("日期")
            ax.grid(True, linestyle=':', alpha=0.5)
            ax.set_title("月度收益率分布 (红=盈利, 蓝=亏损)", fontsize=10)
            
            # 设置 x 轴格式
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
            
        except Exception as e:
            ax.text(0.5, 0.5, f'月度收益计算失败: {e}', 
                   transform=ax.transAxes, ha='center', va='center', fontsize=10)
