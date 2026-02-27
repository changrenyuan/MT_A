import akshare as ak
import pandas as pd
import os
from datetime import datetime, time
import glob
from .base import BaseDataProvider


class AkShareProvider(BaseDataProvider):
    def __init__(self, cache_dir="data"):
        self.cache_dir = cache_dir
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

        # 💡 核心修复：强制禁用当前进程的系统代理
        # 防止 VPN 导致的 ProxyError
        # os.environ['HTTP_PROXY'] = ''
        # os.environ['HTTPS_PROXY'] = ''
        # os.environ['http_proxy'] = ''
        # os.environ['https_proxy'] = ''

    def get_market_snapshot(self) -> pd.DataFrame:
        """获取全 A 股当日实时快照
        规则：
        1. 11:30 之后：尝试加载/创建今日缓存。
        2. 11:30 之前：不缓存今日数据，直接寻找最近的历史缓存。
        """
        now = datetime.now()
        today_str = now.strftime('%Y%m%d')
        threshold_time = time(11, 30)

        # 路径定义
        cache_file_today = os.path.join(self.cache_dir, f"market_snapshot_{today_str}.csv")

        # --- 逻辑 A: 11:30 之前的情况 ---
        if now.time() < threshold_time:
            print(f"当前时间 ({now.strftime('%H:%M')}) 早于 11:30，正在检索最近的历史缓存...")

            # 搜索所有快照缓存文件
            cache_pattern = os.path.join(self.cache_dir, "market_snapshot_*.csv")
            all_caches = glob.glob(cache_pattern)

            # 过滤掉今天的缓存（如果有的话），并按文件名（日期）降序排列
            history_caches = sorted([f for f in all_caches if today_str not in f], reverse=True)

            if history_caches:
                latest_history = history_caches[0]
                print(f"检测到历史缓存，加载最近日期数据: {os.path.basename(latest_history)}")
                return pd.read_csv(latest_history, dtype={'代码': str})
            else:
                # 如果连历史缓存都没有，则不得不拉取实时数据（但不保存）
                print("警告：未找到任何历史缓存，正在拉取实时数据（不执行本地缓存）...")
                return ak.stock_zh_a_spot()

        # --- 逻辑 B: 11:30 之后的情况 (原逻辑) ---
        if os.path.exists(cache_file_today):
            print(f"检测到今日 ({today_str}) 缓存，正在加载...")
            return pd.read_csv(cache_file_today, dtype={'代码': str})

        print(f"11:30 后首次运行，正在从 AkShare 拉取并缓存今日最新快照...")
        try:
            df = ak.stock_zh_a_spot()
            # 立即存入本地
            df.to_csv(cache_file_today, index=False, encoding='utf-8-sig')
            print(f"今日数据已成功缓存至: {cache_file_today}")
            return df
        except Exception as e:
            print(f"拉取失败: {e}")
            raise ConnectionError("无法获取实时行情且无可用缓存。")

    def get_data_dc(self, symbol: str) -> pd.DataFrame:
        """获取指定股票的历史日线数据 (也可以做缓存，此处保持简洁)"""
        try:
            # 这里的 symbol 处理：akshare 需要 sh600415 格式或 600415
            # 如果是东财快照里的纯数字，可能需要补齐
            formatted_symbol = symbol if symbol.startswith(('sh', 'sz', 'bj')) else self._fix_symbol(symbol)
            df = ak.stock_zh_a_daily(symbol=formatted_symbol)
            df.index = pd.to_datetime(df.index)
            print(df)
            return df[['open', 'high', 'low', 'close', 'volume']]
        except Exception as e:
            print(f"获取股票 {symbol} 历史数据失败: {e}")
            return pd.DataFrame()

    def get_data(self, symbol: str) -> pd.DataFrame:
        """获取最近两年的历史数据，使用更稳定的 hist 接口"""
        try:
            # 去掉 sh/sz 前缀只留数字
            # raw_code = "".join(filter(str.isdigit, symbol))
            # 💡 使用 stock_zh_a_hist 代替 daily 接口
            # df = ak.stock_zh_a_hist(symbol=raw_code, period="daily", adjust="qfq")
            df = ak.stock_zh_a_daily(symbol=symbol, adjust="qfq")
            if df.empty: return pd.DataFrame()

            # 重命名列以适配回测引擎
            df = df.rename(columns={
                '日期': 'date', '开盘': 'open', '收盘': 'close',
                '最高': 'high', '最低': 'low', '成交量': 'volume'
            })
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            # 只取最近 500 个交易日，避免 1970 问题
            return df.sort_index().tail(500)
        except Exception as e:
            print(f"数据拉取失败 {symbol}: {e}")
            return pd.DataFrame()
    def _fix_symbol(self, symbol: str) -> str:
        """简单补齐代码前缀"""
        if symbol.startswith('6'): return f"sh{symbol}"
        if symbol.startswith(('0', '3')): return f"sz{symbol}"
        return symbol