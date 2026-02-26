import random
import pandas as pd
from data_provider.akshare_pd import AkShareProvider
from strategies.martingale import MartingaleStrategy
from core.engine import BacktestEngine
from utils.plotter import Plotter
import yaml


def run_selection_and_backtest(provider, full_market, sort_by_col, label_name, account_cfg, strategy_cfg):
    print(f"\n{'=' * 20} 基于【{label_name}】筛选 Top 20 {'=' * 20}")

    # 筛选并打印
    top_20 = full_market.nlargest(20, sort_by_col)[['代码', '名称', '最新价', sort_by_col]]
    print(top_20.to_string(index=False))

    # 随机选择一个
    target_stock = random.choice(top_20['代码'].tolist())
    target_name = top_20[top_20['代码'] == target_stock]['名称'].values[0]
    print(f"\n随机选中股票: {target_stock} ({target_name}) 进行回测...")

    # 从配置文件读取策略参数
    config = {
        'first_amount': strategy_cfg['first_amount'],
        'base_drop': strategy_cfg['base_drop'],
        'step_factor': strategy_cfg['step_factor'],
        'growth_factor': strategy_cfg['growth_factor'],
        'max_steps': strategy_cfg['max_steps'],
        'total_capital': account_cfg['initial_capital'],
        'take_profit_pct': strategy_cfg['take_profit_pct'],
        'stop_loss_pct': strategy_cfg['stop_loss_pct']
    }

    # 获取回测数据
    data = provider.get_data(target_stock)

    # 初始化策略（此处可插拔更换策略类）
    strategy = MartingaleStrategy(config)

    # 运行引擎
    engine = BacktestEngine(
        data, 
        strategy, 
        initial_capital=account_cfg['initial_capital'],
        commission=account_cfg['commission_rate']
    )
    results = engine.run()

    # 绘图
    Plotter.plot_results(results, f"{target_stock} {target_name}", f"按{label_name}筛选")


def main():
    # 1. 加载配置
    with open("config/settings.yaml", "r", encoding="utf-8") as f:
        full_cfg = yaml.safe_load(f)
    
    account_cfg = full_cfg['account']
    strategy_cfg = full_cfg['strategy']
    
    provider = AkShareProvider(cache_dir="data")
    full_market = None

    # 1. 尝试获取快照
    try:
        print("正在尝试获取全市场实时快照...")
        full_market = provider.get_market_snapshot()
    except Exception as e:
        print(f"\n[警告] 市场快照拉取失败: {e}")
        print("触发降级机制：手动指定【招商银行】进行策略回测。")

        # 构建一个伪造的 DataFrame，确保后续 run_selection_and_backtest 不报错
        # 这里的列名必须与 akshare 返回的一致（代码、名称、成交额、换手率等）
        fallback_data = {
            '代码': ['600036'],  # 招商银行
            '名称': ['招商银行'],
            '最新价': [0.0],  # 回测时会拉取历史K线，这里只是占位
            '成交额': [99999999999],  # 给个极高值确保它在 Top 20 里
            '换手率': [99.9]
        }
        full_market = pd.DataFrame(fallback_data)

    # 2. 执行基于成交额的筛选与回测
    # 如果是降级模式，top 20 就只有招商银行一只，random.choice 也会选中它
    try:
        run_selection_and_backtest(provider, full_market, '成交额', '成交额', account_cfg, strategy_cfg)
    except Exception as e:
        print(f"成交额回测环节执行失败: {e}")

    # 3. 执行基于换手率的筛选与回测
    try:
        run_selection_and_backtest(provider, full_market, '换手率', '换手率', account_cfg, strategy_cfg)
    except Exception as e:
        print(f"换手率回测环节执行失败: {e}")


if __name__ == "__main__":
    main()
