"""
回测报告生成模块

支持：
- HTML 格式报告导出
- 完整绩效指标汇总
- 图表嵌入
"""
import os
from datetime import datetime
from typing import Dict, Any
import pandas as pd


class ReportGenerator:
    """回测报告生成器"""
    
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    def generate_html_report(
        self,
        df: pd.DataFrame,
        metrics: Dict[str, Any],
        symbol: str,
        strategy_name: str,
        initial_capital: float
    ) -> str:
        """
        生成HTML格式回测报告
        
        Args:
            df: 回测结果DataFrame
            metrics: 绩效指标字典
            symbol: 股票代码
            strategy_name: 策略名称
            initial_capital: 初始资金
        
        Returns:
            报告文件路径
        """
        raw = metrics.get('_raw', {})
        
        # 计算月度/年度收益
        monthly_returns = self._calc_period_returns(df, 'M')
        yearly_returns = self._calc_period_returns(df, 'Y')
        
        # 计算回撤数据
        drawdown_data = self._calc_drawdown_data(df)
        
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>回测报告 - {symbol}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            background: #f5f5f5;
            color: #333;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 28px;
            margin-bottom: 10px;
        }}
        .header .subtitle {{
            font-size: 16px;
            opacity: 0.9;
        }}
        .card {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .card-title {{
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
            color: #667eea;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }}
        .metric-item {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }}
        .metric-label {{
            font-size: 12px;
            color: #666;
            margin-bottom: 5px;
        }}
        .metric-value {{
            font-size: 20px;
            font-weight: bold;
            color: #333;
        }}
        .metric-value.positive {{
            color: #e74c3c;
        }}
        .metric-value.negative {{
            color: #3498db;
        }}
        .metric-value.neutral {{
            color: #333;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        th, td {{
            padding: 10px;
            text-align: center;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background: #f8f9fa;
            font-weight: bold;
        }}
        .positive-return {{
            color: #e74c3c;
        }}
        .negative-return {{
            color: #3498db;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: #666;
            font-size: 12px;
        }}
        .summary-highlight {{
            font-size: 24px;
            padding: 20px;
            text-align: center;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .profit {{
            color: #e74c3c;
        }}
        .loss {{
            color: #3498db;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 策略回测报告</h1>
            <div class="subtitle">{symbol} | {strategy_name} | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
        </div>
        
        <div class="summary-highlight">
            最终盈亏: <span class="{'profit' if raw.get('total_return', 0) >= 0 else 'loss'}">
                {initial_capital * (1 + raw.get('total_return', 0)):,.0f} 元
            </span>
            <br>
            <small>累计收益率: <span class="{'profit' if raw.get('total_return', 0) >= 0 else 'loss'}">{metrics.get('累计收益率', '0%')}</span></small>
        </div>
        
        <div class="card">
            <div class="card-title">📈 收益率指标</div>
            <div class="metrics-grid">
                <div class="metric-item">
                    <div class="metric-label">累计收益率</div>
                    <div class="metric-value {'positive' if raw.get('total_return', 0) >= 0 else 'negative'}">{metrics.get('累计收益率', '0%')}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">年化收益率</div>
                    <div class="metric-value {'positive' if raw.get('annual_return', 0) >= 0 else 'negative'}">{metrics.get('年化收益率', '0%')}</div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-title">⚠️ 风险指标</div>
            <div class="metrics-grid">
                <div class="metric-item">
                    <div class="metric-label">最大回撤</div>
                    <div class="metric-value negative">{metrics.get('最大回撤', '0%')}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">年化波动率</div>
                    <div class="metric-value">{metrics.get('年化波动率', '0%')}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">下行波动率</div>
                    <div class="metric-value">{metrics.get('下行波动率', '0%')}</div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-title">🎯 风险调整收益</div>
            <div class="metrics-grid">
                <div class="metric-item">
                    <div class="metric-label">夏普比率</div>
                    <div class="metric-value {'positive' if raw.get('sharpe_ratio', 0) >= 1 else 'neutral'}">{metrics.get('夏普比率', '0.00')}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">索提诺比率</div>
                    <div class="metric-value {'positive' if raw.get('sortino_ratio', 0) >= 1 else 'neutral'}">{metrics.get('索提诺比率', '0.00')}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">卡玛比率</div>
                    <div class="metric-value {'positive' if raw.get('calmar_ratio', 0) >= 1 else 'neutral'}">{metrics.get('卡玛比率', '0.00')}</div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-title">📊 交易统计</div>
            <div class="metrics-grid">
                <div class="metric-item">
                    <div class="metric-label">交易天数</div>
                    <div class="metric-value">{metrics.get('交易天数', 0)}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">交易次数</div>
                    <div class="metric-value">{metrics.get('交易次数', 0)}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">盈利次数</div>
                    <div class="metric-value positive">{metrics.get('盈利次数', 0)}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">亏损次数</div>
                    <div class="metric-value negative">{metrics.get('亏损次数', 0)}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">胜率</div>
                    <div class="metric-value {'positive' if raw.get('win_rate', 0) >= 0.5 else 'negative'}">{metrics.get('胜率', '0%')}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">盈亏比</div>
                    <div class="metric-value {'positive' if raw.get('profit_loss_ratio', 0) >= 1 else 'negative'}">{metrics.get('盈亏比', '0.00')}</div>
                </div>
            </div>
        </div>
        
        {self._generate_yearly_table(yearly_returns)}
        
        {self._generate_monthly_table(monthly_returns)}
        
        <div class="footer">
            <p>🤖 由量化回测框架自动生成 | MT_A Backtest Framework</p>
            <p>⚠️ 本报告仅供研究参考，不构成投资建议</p>
        </div>
    </div>
</body>
</html>"""
        
        # 保存文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"report_{symbol}_{timestamp}.html"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return filepath
    
    def _calc_period_returns(self, df: pd.DataFrame, freq: str) -> list:
        """计算周期收益率"""
        if len(df) == 0:
            return []
        
        try:
            equity = df['equity']
            period = equity.resample(freq).last()
            returns = period.pct_change().dropna()
            
            result = []
            for date, ret in returns.items():
                if freq == 'M':
                    label = date.strftime('%Y-%m')
                else:
                    label = date.strftime('%Y')
                result.append({
                    'period': label,
                    'return': ret
                })
            return result
        except:
            return []
    
    def _calc_drawdown_data(self, df: pd.DataFrame) -> list:
        """计算回撤数据"""
        if len(df) == 0:
            return []
        
        try:
            equity = df['equity']
            max_equity = equity.cummax()
            max_equity_safe = max_equity.replace(0, np.nan)
            drawdowns = ((equity - max_equity) / max_equity_safe).fillna(0)
            
            result = []
            for date, dd in drawdowns.items():
                result.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'drawdown': dd
                })
            return result[-100:]  # 只返回最近100条
        except:
            return []
    
    def _generate_yearly_table(self, yearly_returns: list) -> str:
        """生成年度收益表格HTML"""
        if not yearly_returns:
            return ""
        
        rows = ""
        for item in yearly_returns:
            ret = item['return'] * 100
            css_class = 'positive-return' if ret >= 0 else 'negative-return'
            rows += f"<tr><td>{item['period']}</td><td class='{css_class}'>{ret:+.2f}%</td></tr>"
        
        return f"""
        <div class="card">
            <div class="card-title">📅 年度收益分布</div>
            <table>
                <thead>
                    <tr><th>年份</th><th>收益率</th></tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
        """
    
    def _generate_monthly_table(self, monthly_returns: list) -> str:
        """生成月度收益表格HTML"""
        if not monthly_returns:
            return ""
        
        # 只显示最近12个月
        recent = monthly_returns[-12:] if len(monthly_returns) > 12 else monthly_returns
        
        rows = ""
        for item in recent:
            ret = item['return'] * 100
            css_class = 'positive-return' if ret >= 0 else 'negative-return'
            rows += f"<tr><td>{item['period']}</td><td class='{css_class}'>{ret:+.2f}%</td></tr>"
        
        return f"""
        <div class="card">
            <div class="card-title">📅 月度收益分布 (最近12个月)</div>
            <table>
                <thead>
                    <tr><th>月份</th><th>收益率</th></tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
        """


# 添加 numpy 导入
import numpy as np
