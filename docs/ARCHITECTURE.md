# MT_A 架构重构方案

## 问题诊断

### 当前职责混乱

| 模块 | 当前职责 | 问题 |
|------|----------|------|
| **Engine** | 遍历数据、执行交易、**记录快照**、**计算财务指标**、**管理虚拟账户** | ❌ 职责越界，做了会计的工作 |
| **Account** | 管理资金和持仓 | ❌ 权限不足，缺少快照记录和虚拟账户追踪 |
| **Strategy** | 生成信号、**读取账户** | ✅ 正确（只读） |
| **Plotter** | 绘图、**计算财务指标** | ❌ 不应该计算指标，应从账户获取 |

### 具体问题

1. **Engine 中直接管理 `_stock_cash`** - 这是账户数据
2. **Engine 中直接管理 `_daily_signals`** - 这是交易记录
3. **Engine 中直接管理 `history`** - 这是快照记录
4. **Engine 中计算 `equity`, `pnl`** - 应由账户模块提供
5. **Plotter 中计算回撤、月度收益** - 应由账户模块提供

---

## 新架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                    Account 模块（会计部门）                       │
│                         【唯一写入权限】                          │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐  │
│  │  Portfolio   │  Position    │  Ledger      │  Snapshot    │  │
│  │  (资金池)     │  (持仓簿)     │  (流水账)     │  (快照表)     │  │
│  └──────────────┴──────────────┴──────────────┴──────────────┘  │
│                                                                 │
│  只读接口：                                                      │
│  - get_cash() / get_equity(prices) / get_pnl(prices)           │
│  - get_position(symbol) / get_all_positions()                  │
│  - get_stock_equity(symbol, price)  # 虚拟账户权益              │
│  - get_history() -> DataFrame  # 每日快照                       │
│  - get_trade_records() -> DataFrame  # 交易流水                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ 只读访问
                              ▼
┌─────────────────┬─────────────────────┬─────────────────────┐
│     Engine      │      Strategy       │    Plotter/Metrics  │
│   (交易执行)     │      (策略分析)      │      (报告生成)      │
├─────────────────┼─────────────────────┼─────────────────────┤
│ - 遍历数据       │ - 接收行情数据       │ - 从账户获取数据     │
│ - 调用策略       │ - 读取账户状态(只读) │ - 生成图表报告       │
│ - 提交交易请求   │ - 返回交易信号       │ - 不计算财务指标     │
│ - 不记录快照     │ - 不修改账户         │                     │
└─────────────────┴─────────────────────┴─────────────────────┘
```

---

## 模块职责规范

### 1. Account 模块（会计部门）- 唯一写入权限

```python
# core/account.py

class Portfolio:
    """账户总管 - 资金与持仓的统一管理者"""
    
    # === 写入接口（仅内部调用）===
    def execute_trade(self, symbol, action, shares, price, commission):
        """执行交易（原子操作）"""
        pass
    
    def record_daily_snapshot(self, date, prices: dict):
        """记录每日快照"""
        pass
    
    # === 只读接口（外部访问）===
    def get_cash(self) -> float:
        """获取可用现金"""
        pass
    
    def get_equity(self, prices: dict) -> float:
        """获取总资产"""
        pass
    
    def get_pnl(self, prices: dict) -> float:
        """获取盈亏"""
        pass
    
    def get_position(self, symbol) -> 'Position':
        """获取持仓"""
        pass
    
    def get_stock_virtual_equity(self, symbol, price) -> float:
        """获取单只股票的虚拟权益（用于独立绩效追踪）"""
        pass
    
    def get_history(self) -> pd.DataFrame:
        """获取快照历史"""
        pass
    
    def get_trade_records(self) -> pd.DataFrame:
        """获取交易流水"""
        pass
```

### 2. Engine 模块（交易执行）- 无账户写入权限

```python
# core/engine.py

class BacktestEngine:
    """回测引擎 - 只负责调度，不管理账户数据"""
    
    def run(self):
        """运行回测"""
        for date, bar in self.data.iterrows():
            # 1. 获取策略信号（传入账户只读引用）
            signal = self.strategy.on_bar(bar, self.account, symbol)
            
            # 2. 提交交易请求（账户自己执行）
            if signal:
                self.account.execute_trade(symbol, action, shares, price, commission)
            
            # 3. 通知账户记录快照
            self.account.record_daily_snapshot(date, prices)
        
        # 4. 返回账户历史数据
        return self.account.get_history()
```

### 3. Strategy 模块（策略分析）- 只读访问

```python
# strategies/base.py

class BaseStrategy:
    def on_bar(self, bar, account, symbol):
        """
        Args:
            bar: 行情数据
            account: 账户只读引用（只能调用 get_* 方法）
            symbol: 股票代码
        
        Returns:
            (action, shares) 或 None
        """
        pass
```

### 4. Plotter 模块（报告生成）- 只读访问

```python
# utils/plotter.py

class Plotter:
    @staticmethod
    def plot_results(account: Portfolio, symbol: str):
        """绘图 - 从账户获取数据"""
        history = account.get_history()
        # 直接使用 history 中的数据绘图
        # 不计算任何财务指标
```

---

## 数据流图

```
┌──────────┐    行情数据     ┌──────────┐
│  Data    │ ──────────────▶│ Engine   │
│ Provider │                │          │
└──────────┘                └────┬─────┘
                                 │
                    ┌────────────┼────────────┐
                    │ 信号       │ 提交交易    │ 通知快照
                    ▼            ▼            ▼
              ┌──────────┐ ┌──────────┐ ┌──────────┐
              │ Strategy │ │ Account  │ │ Account  │
              │ (只读)    │ │ (执行)   │ │ (记录)   │
              └──────────┘ └──────────┘ └──────────┘
                                 │
                                 │ 历史数据
                                 ▼
                           ┌──────────┐
                           │ Plotter  │
                           │ (只读)   │
                           └──────────┘
```

---

## 重构步骤

### Phase 1: 增强 Account 模块
1. 添加 `Ledger` 类记录交易流水
2. 添加 `Snapshot` 记录每日快照
3. 添加虚拟账户追踪（每只股票独立权益）
4. 提供完整的只读接口

### Phase 2: 精简 Engine 模块
1. 移除 `_stock_cash`、`_daily_signals`、`history`
2. 移除财务指标计算逻辑
3. 改为调用 Account 接口

### Phase 3: 修正 Plotter 模块
1. 从 Account 获取数据
2. 移除财务指标计算逻辑

### Phase 4: 验证
1. 单股票回测
2. 多股票回测
3. 图表生成

---

## 命名规范

### 账户方法前缀

| 前缀 | 含义 | 示例 |
|------|------|------|
| `get_` | 只读查询 | `get_cash()`, `get_equity()` |
| `execute_` | 执行交易 | `execute_trade()` |
| `record_` | 记录数据 | `record_snapshot()` |

### 禁止的操作

1. **Engine 直接修改账户数据**
   ```python
   # ❌ 错误
   self.account.cash -= cost
   
   # ✅ 正确
   self.account.execute_trade(symbol, "BUY", shares, price)
   ```

2. **外部模块直接访问账户内部属性**
   ```python
   # ❌ 错误
   cash = self.account.cash
   
   # ✅ 正确
   cash = self.account.get_cash()
   ```

3. **外部模块计算财务指标**
   ```python
   # ❌ 错误
   equity = account.cash + market_value
   
   # ✅ 正确
   equity = account.get_equity(prices)
   ```
