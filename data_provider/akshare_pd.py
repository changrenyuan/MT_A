import akshare as ak
import pandas as pd
import os
from datetime import datetime
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
        """获取全 A 股当日实时快照，并实现本地一日一存"""
        today_str = datetime.now().strftime('%Y%m%d')
        cache_file = os.path.join(self.cache_dir, f"market_snapshot_{today_str}.csv")

        # 1. 检查缓存
        if os.path.exists(cache_file):
            print(f"检测到本地缓存，加载今日 ({today_str}) 快照数据...")
            df = pd.read_csv(cache_file, dtype={'代码': str})  # 保证代码列不丢失 0
            return df

        # 2. 缓存不存在，拉取数据
        print(f"未检测到本地缓存，正在从 AkShare 拉取最新市场快照...")
        try:
            df = ak.stock_zh_a_spot()
            # 3. 立即存入本地
            df.to_csv(cache_file, index=False, encoding='utf-8-sig')
            print(f"数据拉取成功并已保存至: {cache_file}")
            return df
        except Exception as e:
            print(f"拉取失败: {e}")
            # 如果拉取不到今天的，尝试加载最近一次的缓存（可选逻辑）
            raise ConnectionError("无法连接到行情服务器且无本地缓存可用。")

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