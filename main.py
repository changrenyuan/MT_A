import random
import traceback
import pandas as pd
from data_provider.akshare_pd import AkShareProvider
from strategies.martingale import MartingaleStrategy
from strategies.institutional_trend import InstitutionalTrendStrategy
from core.engine import BacktestEngine
from utils.plotter import Plotter
import yaml


# 策略映射表 - 支持动态选择策略
STRATEGY_MAP = {
    'martingale': MartingaleStrategy,
    'institutional_trend': InstitutionalTrendStrategy,
}


def build_strategy_config(strategy_name, account_cfg, full_cfg):
    """根据策略名称构建配置参数"""
    # 获取策略专属配置
    strategy_specific = full_cfg.get(strategy_name, {})
    # 获取默认策略配置 (向后兼容)
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
            'trailing_stop_pct': strategy_specific.get('trailing_stop_pct', default_cfg.get('trailing_stop_pct', 0.25)),
            'unit_size': strategy_specific.get('unit_size', default_cfg.get('unit_size', 0.1)),
            'max_units': strategy_specific.get('max_units', default_cfg.get('max_units', 2)),
            'total_capital': account_cfg['initial_capital'],
        }
    else:
        raise ValueError(f"未知策略: {strategy_name}")


def run_backtest(provider, target_stock, target_name, account_cfg, full_cfg, strategy_name='martingale'):
    """执行单个股票的回测"""
    print(f"\n{'=' * 20} 回测: {target_stock} ({target_name}) {'=' * 20}")
    print(f"策略: {strategy_name}")
    
    try:
        # 构建策略配置
        config = build_strategy_config(strategy_name, account_cfg, full_cfg)
        
        # 获取回测数据
        data = provider.get_data(target_stock)
        
        if data.empty:
            print(f"[警告] 股票 {target_stock} 数据为空，跳过回测")
            return None

        print(f"数据范围: {data.index[0]} ~ {data.index[-1]}, 共 {len(data)} 个交易日")

        # 初始化策略
        strategy_class = STRATEGY_MAP.get(strategy_name)
        if not strategy_class:
            raise ValueError(f"策略 {strategy_name} 未注册")
        
        strategy = strategy_class(config)

        # 运行引擎
        engine = BacktestEngine(
            data, 
            strategy, 
            initial_capital=account_cfg['initial_capital'],
            commission=account_cfg['commission_rate']
        )
        results = engine.run()

        # 绘图
        Plotter.plot_results(results, f"{target_stock} {target_name}", f"策略: {strategy_name}")
        
        return results
        
    except Exception as e:
        print(f"[回测错误] {e}")
        traceback.print_exc()
        return None


def run_selection_and_backtest(provider, full_market, sort_by_col, label_name, account_cfg, full_cfg, strategy_name='martingale'):
    """筛选股票并执行回测"""
    print(f"\n{'=' * 20} 基于【{label_name}】筛选 Top 20 {'=' * 20}")
    print(full_market.nlargest(10, sort_by_col)[['代码', '名称', '最新价', sort_by_col]])
    # 筛选并打印
    top_20 = full_market.nlargest(1, sort_by_col)[['代码', '名称', '最新价', sort_by_col]]
    print(top_20.to_string(index=False))

    # 随机选择一个
    target_stock = random.choice(top_20['代码'].tolist())
    target_name = top_20[top_20['代码'] == target_stock]['名称'].values[0]
    
    # 执行回测
    return run_backtest(provider, target_stock, target_name, account_cfg, full_cfg, strategy_name)


def main():
    # 1. 加载配置
    with open("config/settings.yaml", "r", encoding="utf-8") as f:
        full_cfg = yaml.safe_load(f)
    
    account_cfg = full_cfg['account']
    
    # 从配置读取策略名称，默认使用 martingale
    strategy_name = full_cfg.get('strategy_name', 'martingale')
    
    provider = AkShareProvider(cache_dir="data")
    full_market = None

    # 2. 尝试获取快照
    try:
        print("正在尝试获取全市场实时快照...")
        full_market = provider.get_market_snapshot()
    except Exception as e:
        print(f"\n[警告] 市场快照拉取失败: {e}")
        print("触发降级机制：手动指定【招商银行】进行策略回测。")

        # 构建一个伪造的 DataFrame，确保后续 run_selection_and_backtest 不报错
        fallback_data = {
            '代码': ['600036'],  # 招商银行
            '名称': ['招商银行'],
            '最新价': [0.0],
            '成交额': [99999999999],
            '换手率': [99.9]
        }
        full_market = pd.DataFrame(fallback_data)

    # 3. 执行基于成交额的筛选与回测
    try:
        run_selection_and_backtest(
            provider, full_market, '成交额', '成交额', 
            account_cfg, full_cfg, strategy_name
        )
    except Exception as e:
        print(f"成交额回测环节执行失败: {e}")
        traceback.print_exc()

    # 4. 执行基于换手率的筛选与回测
    try:
        run_selection_and_backtest(
            provider, full_market, '换手率', '换手率', 
            account_cfg, full_cfg, strategy_name
        )
    except Exception as e:
        print(f"换手率回测环节执行失败: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
