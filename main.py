"""
MT_A 主入口 - 支持单股票和多股票回测
"""

import random
import traceback
import pandas as pd
from data_provider.akshare_pd import AkShareProvider
from strategies.martingale import MartingaleStrategy
from strategies.institutional_trend import InstitutionalTrendStrategy
from core.engine import BacktestEngine
from utils.plotter import Plotter
from utils.metrics import MetricsCalculator
from utils.report_generator import ReportGenerator
import yaml


# 策略映射表
STRATEGY_MAP = {
    'martingale': MartingaleStrategy,
    'institutional_trend': InstitutionalTrendStrategy,
}


def build_strategy_config(strategy_name, account_cfg, full_cfg, symbols=None):
    """根据策略名称构建配置参数"""
    strategy_specific = full_cfg.get(strategy_name, {})
    default_cfg = full_cfg.get('strategy', {})
    
    if strategy_name == 'martingale':
        return {
            'first_amount': strategy_specific.get('first_amount', default_cfg.get('first_amount', 10000.0)),
            'base_drop': strategy_specific.get('base_drop', default_cfg.get('base_drop', 0.03)),
            'step_factor': strategy_specific.get('step_factor', default_cfg.get('step_factor', 1.1)),
            'growth_factor': strategy_specific.get('growth_factor', default_cfg.get('growth_factor', 1.5)),
            'max_steps': strategy_specific.get('max_steps', default_cfg.get('max_steps', 5)),
            'total_capital': account_cfg['initial_capital'],
            'take_profit_pct': strategy_specific.get('take_profit_pct', default_cfg.get('take_profit_pct', 0.08)),
            'stop_loss_pct': strategy_specific.get('stop_loss_pct', default_cfg.get('stop_loss_pct', 0.15))
        }
    elif strategy_name == 'institutional_trend':
        return {
            'stop_loss_pct': strategy_specific.get('stop_loss_pct', default_cfg.get('stop_loss_pct', 0.10)),
            'trailing_stop_pct': strategy_specific.get('trailing_stop_pct', default_cfg.get('trailing_stop_pct', 0.20)),
            'unit_size': strategy_specific.get('unit_size', default_cfg.get('unit_size', 0.1)),
            'max_units': strategy_specific.get('max_units', default_cfg.get('max_units', 4)),
            'total_capital': account_cfg['initial_capital'],
            'profit_tier1': strategy_specific.get('profit_tier1', default_cfg.get('profit_tier1', 0.30)),
            'trailing_tier1': strategy_specific.get('trailing_tier1', default_cfg.get('trailing_tier1', 0.15)),
            'profit_tier2': strategy_specific.get('profit_tier2', default_cfg.get('profit_tier2', 0.50)),
            'trailing_tier2': strategy_specific.get('trailing_tier2', default_cfg.get('trailing_tier2', 0.10)),
            'partial_exit_pct': strategy_specific.get('partial_exit_pct', default_cfg.get('partial_exit_pct', 0.5)),
            'enable_partial_exit': strategy_specific.get('enable_partial_exit', default_cfg.get('enable_partial_exit', False)),
        }
    else:
        raise ValueError(f"未知策略: {strategy_name}")


def run_single_backtest(provider, target_stock, target_name, account_cfg, full_cfg, strategy_name='martingale'):
    """执行单个股票的回测"""
    print(f"\n{'=' * 20} 回测: {target_stock} ({target_name}) {'=' * 20}")
    print(f"策略: {strategy_name}")
    
    try:
        config = build_strategy_config(strategy_name, account_cfg, full_cfg)
        data = provider.get_data(target_stock)
        
        if data.empty:
            print(f"[警告] 股票 {target_stock} 数据为空，跳过回测")
            return None

        print(f"数据范围: {data.index[0]} ~ {data.index[-1]}, 共 {len(data)} 个交易日")

        strategy_class = STRATEGY_MAP.get(strategy_name)
        if not strategy_class:
            raise ValueError(f"策略 {strategy_name} 未注册")
        
        strategy = strategy_class(config)

        engine = BacktestEngine(
            data, 
            strategy, 
            initial_capital=account_cfg['initial_capital'],
            commission=account_cfg['commission_rate']
        )
        results = engine.run()

        # 计算并显示绩效指标
        metrics = MetricsCalculator.calculate(results, account_cfg['initial_capital'])
        print_metrics(metrics)
        
        # 生成HTML报告
        report_gen = ReportGenerator(output_dir="reports")
        report_path = report_gen.generate_html_report(
            results, metrics, target_stock, strategy_name, account_cfg['initial_capital']
        )
        print(f"\n📄 HTML报告已生成: {report_path}")

        # 绘图
        Plotter.plot_results(results, f"{target_stock} {target_name}", f"策略: {strategy_name}")
        
        return results
        
    except Exception as e:
        print(f"[回测错误] {e}")
        traceback.print_exc()
        return None


def run_multi_stock_backtest(provider, stock_list, account_cfg, full_cfg, strategy_name='institutional_trend'):
    """
    执行多股票回测
    
    Args:
        provider: 数据提供者
        stock_list: 股票列表 [(code, name), ...]
        account_cfg: 账户配置
        full_cfg: 完整配置
        strategy_name: 策略名称
    """
    print(f"\n{'=' * 60}")
    print(f"🔄 多股票组合回测")
    print(f"{'=' * 60}")
    print(f"策略: {strategy_name}")
    print(f"股票池: {len(stock_list)} 只")
    for code, name in stock_list:
        print(f"  - {code}: {name}")
    print(f"最大持仓数: {account_cfg.get('max_positions', 3)}")
    print(f"初始资金: {account_cfg['initial_capital']:,.0f}")
    
    try:
        # 获取所有股票数据
        data_dict = {}
        for code, name in stock_list:
            df = provider.get_data(code)
            if not df.empty:
                data_dict[code] = df
                print(f"  ✓ {code}: {len(df)} 条记录")
            else:
                print(f"  ✗ {code}: 无数据")
        
        if not data_dict:
            print("[错误] 没有有效数据")
            return None
        
        # 初始化策略 (传入股票代码列表)
        symbols = list(data_dict.keys())
        config = build_strategy_config(strategy_name, account_cfg, full_cfg, symbols)
        
        strategy_class = STRATEGY_MAP.get(strategy_name)
        if not strategy_class:
            raise ValueError(f"策略 {strategy_name} 未注册")
        
        # 多股票策略需要传入 symbols 参数
        if strategy_name == 'institutional_trend':
            strategy = strategy_class(config, symbols=symbols)
        else:
            strategy = strategy_class(config)

        # 运行引擎
        engine = BacktestEngine(
            data_dict,
            strategy,
            initial_capital=account_cfg['initial_capital'],
            commission=account_cfg['commission_rate']
        )
        results = engine.run()

        # 计算并显示绩效指标
        metrics = MetricsCalculator.calculate(results, account_cfg['initial_capital'])
        print_metrics(metrics)
        
        # 显示最终持仓情况
        print(f"\n📊 最终持仓情况")
        for symbol in symbols:
            if f"{symbol}_shares" in results.columns:
                final_shares = results[f"{symbol}_shares"].iloc[-1]
                final_cost = results[f"{symbol}_cost"].iloc[-1]
                if final_shares > 0:
                    print(f"  {symbol}: {int(final_shares)} 股, 成本 {final_cost:,.0f}")
        
        # 生成报告
        symbols_str = "_".join(symbols[:3])
        if len(symbols) > 3:
            symbols_str += f"_+{len(symbols)-3}"
        report_gen = ReportGenerator(output_dir="reports")
        report_path = report_gen.generate_html_report(
            results, metrics, f"MULTI_{symbols_str}", strategy_name, account_cfg['initial_capital']
        )
        print(f"\n📄 HTML报告已生成: {report_path}")
        
        return results
        
    except Exception as e:
        print(f"[多股票回测错误] {e}")
        traceback.print_exc()
        return None


def print_metrics(metrics):
    """打印绩效指标"""
    print(f"\n{'=' * 60}")
    print(f"📊 回测绩效报告")
    print(f"{'=' * 60}")
    
    print(f"\n📈 收益率指标")
    print(f"  累计收益率: {metrics['累计收益率']}")
    print(f"  年化收益率: {metrics['年化收益率']}")
    
    print(f"\n⚠️ 风险指标")
    print(f"  最大回撤: {metrics['最大回撤']}")
    print(f"  年化波动率: {metrics['年化波动率']}")
    print(f"  下行波动率: {metrics['下行波动率']}")
    
    print(f"\n🎯 风险调整收益")
    print(f"  夏普比率: {metrics['夏普比率']}")
    print(f"  索提诺比率: {metrics['索提诺比率']}")
    print(f"  卡玛比率: {metrics['卡玛比率']}")
    
    print(f"\n📊 交易统计")
    print(f"  交易天数: {metrics['交易天数']}")
    print(f"  交易次数: {metrics['交易次数']}")
    print(f"  盈利次数: {metrics['盈利次数']} | 亏损次数: {metrics['亏损次数']}")
    print(f"  胜率: {metrics['胜率']}")
    print(f"  盈亏比: {metrics['盈亏比']}")
    
    print(f"{'=' * 60}")


def run_selection_and_backtest(provider, full_market, sort_by_col, label_name, account_cfg, full_cfg, strategy_name='martingale'):
    """筛选股票并执行回测"""
    print(f"\n{'=' * 20} 基于【{label_name}】筛选 Top 20 {'=' * 20}")
    print(full_market.nlargest(10, sort_by_col)[['代码', '名称', '最新价', sort_by_col]])
    
    top_20 = full_market.nlargest(1, sort_by_col)[['代码', '名称', '最新价', sort_by_col]]
    print(top_20.to_string(index=False))

    target_stock = random.choice(top_20['代码'].tolist())
    target_name = top_20[top_20['代码'] == target_stock]['名称'].values[0]
    
    return run_single_backtest(provider, target_stock, target_name, account_cfg, full_cfg, strategy_name)


def main():
    # 1. 加载配置
    with open("config/settings.yaml", "r", encoding="utf-8") as f:
        full_cfg = yaml.safe_load(f)
    
    account_cfg = full_cfg['account']
    strategy_name = full_cfg.get('strategy_name', 'martingale')
    
    # 检查是否启用多股票模式
    multi_stock_cfg = full_cfg.get('multi_stock', {})
    enable_multi = multi_stock_cfg.get('enable', False)
    
    provider = AkShareProvider(cache_dir="data")

    # 2. 多股票模式
    if enable_multi:
        stock_config = multi_stock_cfg.get('stocks', [])
        
        if not stock_config:
            # 未配置股票列表，从市场快照中自动选择成交额前3
            print("未配置股票列表，正在获取市场快照自动选股...")
            try:
                full_market = provider.get_market_snapshot()
                top_3 = full_market.nlargest(3, '成交额')[['代码', '名称']].head(3)
                stock_list = [(row['代码'], row['名称']) for _, row in top_3.iterrows()]
                print(f"自动选择成交额前3名:")
                for code, name in stock_list:
                    print(f"  - {code}: {name}")
            except Exception as e:
                print(f"[警告] 市场快照获取失败: {e}，使用默认股票")
                stock_list = [
                    ('600036', '招商银行'),
                    ('000001', '平安银行'),
                    ('601318', '中国平安')
                ]
        else:
            # 解析配置格式
            stock_list = []
            for item in stock_config:
                if isinstance(item, dict):
                    stock_list.append((item.get('code', ''), item.get('name', '')))
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    stock_list.append((item[0], item[1]))
        
        run_multi_stock_backtest(provider, stock_list, account_cfg, full_cfg, strategy_name)
        return

    # 3. 单股票模式
    full_market = None
    try:
        print("正在尝试获取全市场实时快照...")
        full_market = provider.get_market_snapshot()
    except Exception as e:
        print(f"\n[警告] 市场快照拉取失败: {e}")
        print("触发降级机制：手动指定【招商银行】进行策略回测。")
        
        fallback_data = {
            '代码': ['600036'],
            '名称': ['招商银行'],
            '最新价': [0.0],
            '成交额': [99999999999],
            '换手率': [99.9]
        }
        full_market = pd.DataFrame(fallback_data)

    try:
        run_selection_and_backtest(
            provider, full_market, '成交额', '成交额', 
            account_cfg, full_cfg, strategy_name
        )
    except Exception as e:
        print(f"成交额回测环节执行失败: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
