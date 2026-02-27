"""
回测结果可视化模块

支持图表：
1. 股价走势与交易信号
2. 该股票持仓市值
3. 该股票持仓成本
4. 该股票浮动盈亏
5. 回撤曲线（基于该股票）
6. 月度收益分布
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
            symbol: 股票代码/名称
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

            # ========== 子图2: 持仓市值 ==========
            Plotter._plot_market_value(ax2, res)

            # ========== 子图3: 持仓成本 ==========
            Plotter._plot_position_cost(ax3, res)

            # ========== 子图4: 浮动盈亏 ==========
            Plotter._plot_floating_pnl(ax4, res)

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
    def plot_multi_stock(res: pd.DataFrame, symbols: list, symbol_names: dict = None,
                         title: str = "多股票组合回测",
                         save_dir: str = "reports/charts", show: bool = False):
        """
        为多股票组合绘制图表
        
        Args:
            res: 回测结果 DataFrame
            symbols: 股票代码列表
            symbol_names: 股票代码到名称的映射 {code: name}
            title: 总标题
            save_dir: 保存目录
            show: 是否显示
        """
        if symbol_names is None:
            symbol_names = {}
        
        saved_files = []
        
        # 1. 为每只股票生成完整的6子图（使用独立绩效数据）
        for symbol in symbols:
            # 检查是否有该股票的数据
            shares_col = f"{symbol}_shares"
            if shares_col not in res.columns:
                continue
            
            stock_name = symbol_names.get(symbol, "")
            display_name = f"{symbol} {stock_name}".strip()
            
            # 创建该股票的专属数据视图（计算独立绩效）
            stock_res = Plotter._extract_stock_data(res, symbol)
            
            # 生成完整6子图
            filepath = Plotter.plot_results(
                stock_res, 
                display_name, 
                "个股回测详情",
                save_dir=save_dir, 
                show=show
            )
            if filepath:
                saved_files.append(filepath)
        
        # 2. 绘制组合总览图（使用账户级数据）
        overview_path = Plotter._plot_portfolio_overview(res, symbols, symbol_names, title, save_dir, show)
        if overview_path:
            saved_files.append(overview_path)
        
        return saved_files
    
    @staticmethod
    def _extract_stock_data(res: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """
        从多股票结果中提取单只股票的独立绩效数据
        
        使用虚拟账户数据：
        - 虚拟现金余额 = 累计卖出收入 - 累计买入支出
        - 虚拟权益 = 现金余额 + 持仓市值
        
        这样即使卖出股票，权益曲线也能连续（不会归零）
        """
        stock_res = pd.DataFrame(index=res.index)
        
        # 该股票的独立价格
        price_col = f"{symbol}_price"
        if price_col in res.columns:
            stock_res['price'] = res[price_col]
        else:
            stock_res['price'] = res['price']
        
        # 该股票的持仓信息
        shares = res.get(f'{symbol}_shares', 0)
        cost = res.get(f'{symbol}_cost', 0)
        avg_price = res.get(f'{symbol}_avg_price', 0)
        
        stock_res['total_shares'] = shares
        stock_res['total_cost'] = cost
        stock_res['avg_price'] = avg_price
        
        # === 使用虚拟账户数据 ===
        # 持仓市值 = 股数 * 当前价格
        stock_res['market_value'] = shares * stock_res['price']
        
        # 虚拟现金余额（engine 计算）
        stock_res['cash'] = res.get(f'{symbol}_cash', 0)
        
        # 虚拟权益 = 现金 + 持仓市值（engine 计算）
        if f'{symbol}_equity' in res.columns:
            stock_res['equity'] = res[f'{symbol}_equity']
        else:
            stock_res['equity'] = stock_res['cash'] + stock_res['market_value']
        
        # 浮动盈亏 = 持仓市值 - 持仓成本
        stock_res['pnl'] = stock_res['market_value'] - cost
        
        # 该股票独立的交易信号
        buy_col = f"{symbol}_buy_signal"
        sell_col = f"{symbol}_sell_signal"
        if buy_col in res.columns:
            stock_res['buy_signal'] = res[buy_col]
        if sell_col in res.columns:
            stock_res['sell_signal'] = res[sell_col]
        
        return stock_res
    
    @staticmethod
    def _plot_portfolio_overview(res: pd.DataFrame, symbols: list, symbol_names: dict,
                                 title: str, save_dir: str, show: bool = False):
        """绘制组合总览图（使用账户级数据）"""
        try:
            plt.rcParams['font.sans-serif'] = ['SimHei']
            plt.rcParams['axes.unicode_minus'] = False
            
            fig, axes = plt.subplots(3, 1, figsize=(16, 14), sharex=True)
            fig.suptitle(f"{title} - 组合总览", fontsize=16, fontweight='bold')
            
            ax1, ax2, ax3 = axes
            
            # 子图1: 总资产曲线（账户级）
            Plotter._plot_equity(ax1, res)
            
            # 子图2: 各股票持仓堆叠
            Plotter._plot_positions_stacked(ax2, res, symbols, symbol_names)
            
            # 子图3: 累计盈亏（账户级）
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
    def _plot_positions_stacked(ax, res: pd.DataFrame, symbols: list, symbol_names: dict):
        """绘制各股票持仓堆叠图"""
        colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6']
        
        # 收集各股票的持仓市值
        position_values = []
        labels = []
        for i, symbol in enumerate(symbols):
            shares_col = f"{symbol}_shares"
            price_col = f"{symbol}_price"
            
            if shares_col not in res.columns:
                continue
            
            shares = res[shares_col]
            price = res[price_col] if price_col in res.columns else res['price']
            market_value = shares * price
            
            if market_value.sum() > 0:
                position_values.append(market_value)
                stock_name = symbol_names.get(symbol, "")
                labels.append(f"{symbol} {stock_name}".strip() if stock_name else symbol)
        
        if not position_values:
            ax.text(0.5, 0.5, '无持仓数据', transform=ax.transAxes, ha='center', va='center')
            return
        
        # 堆叠面积图
        ax.stackplot(res.index, position_values, labels=labels, 
                    colors=colors[:len(labels)], alpha=0.7)
        ax.set_ylabel("持仓市值 (元)")
        ax.legend(loc='upper left', fontsize=8, ncol=min(len(labels), 3))
        ax.grid(True, linestyle=':', alpha=0.5)
        ax.set_title("各股票持仓市值分布", fontsize=10)
    
    @staticmethod
    def _plot_price_and_signals(ax, res: pd.DataFrame):
        """绘制价格与交易信号"""
        # 价格曲线
        if 'price' in res.columns:
            ax.plot(res.index, res['price'], label='股价', color='#bdc3c7', alpha=0.6, linewidth=1)
        
        # 持仓均价
        if 'avg_price' in res.columns:
            avg_price_safe = res['avg_price'].replace(0, np.nan)
            if avg_price_safe.notna().any():
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
        """绘制总资产曲线（账户级）"""
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
        ax.set_title("账户总资产曲线", fontsize=10)
    
    @staticmethod
    def _plot_market_value(ax, res: pd.DataFrame):
        """绘制持仓市值"""
        market_value = res['market_value']
        ax.fill_between(res.index, market_value, 0, color='#3498db', alpha=0.4, label='持仓市值')
        ax.plot(res.index, market_value, color='#2980b9', linewidth=1.5)
        ax.set_ylabel("金额 (元)")
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(True, linestyle=':', alpha=0.5)
        ax.set_title("持仓市值", fontsize=10)
    
    @staticmethod
    def _plot_position_cost(ax, res: pd.DataFrame):
        """绘制持仓成本"""
        cost = res['total_cost']
        shares = res['total_shares']
        
        ax.fill_between(res.index, cost, 0, color='#e67e22', alpha=0.4, label='持仓成本')
        ax.plot(res.index, cost, color='#d35400', linewidth=1.5)
        
        # 右侧Y轴显示持仓股数
        ax2 = ax.twinx()
        ax2.bar(res.index, shares, color='#9b59b6', alpha=0.3, width=1.5, label='持仓股数')
        ax2.set_ylabel("持仓股数", color='#9b59b6', fontsize=8)
        ax2.tick_params(axis='y', labelcolor='#9b59b6', labelsize=7)
        
        ax.set_ylabel("持仓成本 (元)")
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(True, linestyle=':', alpha=0.5)
        ax.set_title("持仓成本与股数", fontsize=10)
    
    @staticmethod
    def _plot_floating_pnl(ax, res: pd.DataFrame):
        """绘制虚拟账户盈亏曲线"""
        # 使用虚拟账户权益作为盈亏
        equity = res['equity']
        
        # 盈亏金额 - 正负阴影
        ax.fill_between(res.index, equity, 0, where=(equity >= 0), 
                       color='#e74c3c', alpha=0.4, label='盈利')
        ax.fill_between(res.index, equity, 0, where=(equity < 0), 
                       color='#3498db', alpha=0.4, label='亏损')
        ax.plot(res.index, equity, color='#7f8c8d', linewidth=1.5)
        ax.axhline(0, color='black', linestyle='-', linewidth=0.5)
        
        ax.set_ylabel("账户盈亏 (元)")
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(True, linestyle=':', alpha=0.5)
        ax.set_title("虚拟账户累计盈亏 (红=盈利, 蓝=亏损)", fontsize=10)
        
        # 标注最终盈亏
        final_equity = equity.iloc[-1] if len(equity) > 0 else 0
        color = '#e74c3c' if final_equity >= 0 else '#3498db'
        ax.text(0.02, 0.95, f"累计盈亏: {final_equity:+,.0f}元", 
                transform=ax.transAxes, fontsize=10, fontweight='bold',
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor=color, alpha=0.3))
    
    @staticmethod
    def _plot_pnl(ax, res: pd.DataFrame, initial_capital: float):
        """绘制累计盈亏（账户级）"""
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
        ax.set_title("账户累计盈亏 (红色=盈利, 蓝色=亏损)", fontsize=10)

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
        """绘制回撤曲线（基于虚拟账户权益）"""
        equity = res['equity']
        
        # 找到第一个有交易的日期（权益非零）
        first_trade_idx = equity.ne(0).idxmax() if equity.ne(0).any() else None
        
        if first_trade_idx is None or equity.sum() == 0:
            ax.text(0.5, 0.5, '无交易记录', transform=ax.transAxes, ha='center', va='center')
            ax.set_title("虚拟账户回撤曲线", fontsize=10)
            return
        
        # 从第一次交易开始计算
        equity_active = equity.copy()
        
        # 计算从峰值的回撤
        max_equity = equity_active.cummax()
        # 避免除以0：只在max_equity > 0时计算
        max_equity_safe = max_equity.replace(0, np.nan)
        drawdowns = ((equity_active - max_equity) / max_equity_safe.abs()).fillna(0)
        
        # 将交易前的回撤设为0
        if first_trade_idx is not None:
            drawdowns.loc[:first_trade_idx] = 0
        
        ax.fill_between(res.index, drawdowns, 0, color='#e74c3c', alpha=0.3)
        ax.plot(res.index, drawdowns, color='#e74c3c', linewidth=1.5)
        ax.axhline(0, color='black', linestyle='-', linewidth=0.5)
        
        # 标注最大回撤
        max_dd = drawdowns.min()
        if max_dd < 0:
            ax.axhline(max_dd, color='#c0392b', linestyle='--', linewidth=1, alpha=0.7)
            ax.text(0.98, 0.05, f"最大回撤: {max_dd*100:.2f}%", 
                    transform=ax.transAxes, fontsize=10, fontweight='bold',
                    horizontalalignment='right', color='#c0392b')
        
        ax.set_ylabel("回撤")
        ax.grid(True, linestyle=':', alpha=0.5)
        ax.set_title("虚拟账户回撤曲线", fontsize=10)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y*100:.1f}%'))
    
    @staticmethod
    def _plot_rolling_returns(ax, res: pd.DataFrame):
        """绘制滚动收益 (月度，基于虚拟账户)"""
        try:
            equity = res['equity']
            
            # 找到第一个有交易的日期
            first_trade_idx = equity.ne(0).idxmax() if equity.ne(0).any() else None
            
            if first_trade_idx is None:
                ax.text(0.5, 0.5, '无交易记录', transform=ax.transAxes, ha='center', va='center')
                ax.set_title("月度收益率", fontsize=10)
                return
            
            # 从第一次交易开始截取数据
            equity_active = equity.loc[first_trade_idx:]
            
            if len(equity_active) < 30:  # 少于30天
                ax.text(0.5, 0.5, '回测时间较短，无法计算月度收益', 
                       transform=ax.transAxes, ha='center', va='center', fontsize=12)
                ax.set_title("月度收益率", fontsize=10)
                return
            
            # 计算月度权益变化（不用pct_change，因为起始值可能是0或负数）
            monthly = equity_active.resample('M').last()
            
            # 计算月度收益金额（本月末 - 上月末）
            monthly_pnl = monthly.diff()
            monthly_pnl = monthly_pnl.dropna()
            
            # 过滤掉无效值
            monthly_pnl = monthly_pnl[np.isfinite(monthly_pnl)]
            
            if len(monthly_pnl) == 0:
                ax.text(0.5, 0.5, '数据不足，无法计算月度收益', 
                       transform=ax.transAxes, ha='center', va='center', fontsize=12)
                ax.set_title("月度收益率", fontsize=10)
                return
            
            # 绘制柱状图（显示月度盈亏金额）
            colors = ['#e74c3c' if r >= 0 else '#3498db' for r in monthly_pnl]
            ax.bar(monthly_pnl.index, monthly_pnl, color=colors, alpha=0.7, width=20)
            
            ax.axhline(0, color='black', linestyle='-', linewidth=0.5)
            ax.set_ylabel("月度盈亏 (元)")
            ax.set_xlabel("日期")
            ax.grid(True, linestyle=':', alpha=0.5)
            ax.set_title("月度盈亏分布 (红=盈利, 蓝=亏损)", fontsize=10)
            
            # 设置 x 轴格式
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
            
        except Exception as e:
            ax.text(0.5, 0.5, f'月度收益计算失败: {e}', 
                   transform=ax.transAxes, ha='center', va='center', fontsize=10)
