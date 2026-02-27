"""
账户管理模块 - 支持多股票持仓

架构：
- PositionSizer: 仓位计算器
- RiskManager: 风险管理器  
- Portfolio: 多股票组合账户
"""


class PositionSizer:
    """仓位计算器"""
    
    def __init__(self, max_positions=3, position_pct=0.33):
        """
        Args:
            max_positions: 最大持仓数量
            position_pct: 单只股票仓位比例 (默认1/3)
        """
        self.max_positions = max_positions
        self.position_pct = position_pct
    
    def calculate_shares(self, cash, price, available_slots=None):
        """
        计算可买入股数
        
        Args:
            cash: 可用现金
            price: 当前价格
            available_slots: 可用仓位槽位 (None则自动计算)
        
        Returns:
            股数 (100股整数倍)
        """
        if price <= 0:
            return 0
        
        # 根据剩余槽位计算可用资金比例
        if available_slots is None:
            allocation = cash * self.position_pct
        else:
            if available_slots <= 0:
                return 0
            allocation = cash / available_slots
        
        # 计算股数，取整到100股
        shares = int(allocation // price // 100) * 100
        return max(shares, 0)
    
    def calculate_partial_shares(self, total_shares, exit_pct):
        """计算部分卖出股数"""
        partial = int(total_shares * exit_pct // 100) * 100
        return max(partial, 0)


class RiskManager:
    """风险管理器"""
    
    def __init__(self, max_positions=3, max_single_position_pct=0.4):
        """
        Args:
            max_positions: 最大持仓数量
            max_single_position_pct: 单只股票最大仓位比例
        """
        self.max_positions = max_positions
        self.max_single_position_pct = max_single_position_pct
    
    def allow_new_position(self, portfolio, symbol=None):
        """
        判断是否允许开新仓位
        
        Args:
            portfolio: Portfolio 实例
            symbol: 股票代码 (可选，用于判断是否加仓)
        
        Returns:
            bool: 是否允许
        """
        # 如果该股票已持仓，允许加仓
        if symbol and symbol in portfolio.positions:
            return True
        
        # 检查是否达到最大持仓数
        return len(portfolio.positions) < self.max_positions
    
    def check_position_limit(self, portfolio, symbol, cost):
        """
        检查单只股票仓位是否超限
        
        Args:
            portfolio: Portfolio 实例
            symbol: 股票代码
            cost: 本次投入金额
        
        Returns:
            bool: 是否在限制内
        """
        total_equity = portfolio.get_equity()
        if total_equity <= 0:
            return False
        
        # 计算加仓后的仓位比例
        current_value = portfolio.get_position_value(symbol)
        new_ratio = (current_value + cost) / total_equity
        
        return new_ratio <= self.max_single_position_pct


class Position:
    """单个股票持仓"""
    
    def __init__(self, symbol, shares=0, cost=0):
        self.symbol = symbol
        self.shares = shares      # 持仓股数
        self.cost = cost          # 累计投入成本
    
    @property
    def avg_price(self):
        """持仓均价"""
        return self.cost / self.shares if self.shares > 0 else 0
    
    def add(self, shares, price):
        """加仓"""
        self.shares += shares
        self.cost += shares * price
    
    def reduce(self, shares):
        """减仓"""
        if shares >= self.shares:
            # 全部卖出
            cost_reduced = self.cost
            self.shares = 0
            self.cost = 0
            return cost_reduced
        else:
            # 部分卖出
            ratio = shares / self.shares
            cost_reduced = self.cost * ratio
            self.shares -= shares
            self.cost -= cost_reduced
            return cost_reduced
    
    def clear(self):
        """清仓"""
        cost_reduced = self.cost
        self.shares = 0
        self.cost = 0
        return cost_reduced


class Portfolio:
    """多股票组合账户"""
    
    def __init__(self, initial_cash, max_positions=3):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions = {}  # symbol -> Position
        
        # 集成仓位计算器和风险管理器
        self.position_sizer = PositionSizer(max_positions=max_positions)
        self.risk_manager = RiskManager(max_positions=max_positions)
        
        # 用于记录交易手续费
        self.total_commission = 0
    
    # ==================== 查询接口 ====================
    
    def has_position(self, symbol):
        """是否持有某股票"""
        return symbol in self.positions and self.positions[symbol].shares > 0
    
    def get_position(self, symbol):
        """获取持仓信息"""
        return self.positions.get(symbol)
    
    def get_shares(self, symbol):
        """获取持仓股数"""
        pos = self.positions.get(symbol)
        return pos.shares if pos else 0
    
    def get_avg_price(self, symbol):
        """获取持仓均价"""
        pos = self.positions.get(symbol)
        return pos.avg_price if pos else 0
    
    def get_position_value(self, symbol, price=None):
        """
        获取持仓市值
        
        Args:
            symbol: 股票代码
            price: 当前价格 (可选，不传则返回成本)
        """
        pos = self.positions.get(symbol)
        if not pos or pos.shares <= 0:
            return 0
        if price:
            return pos.shares * price
        return pos.cost
    
    def get_total_position_cost(self):
        """获取总持仓成本"""
        return sum(pos.cost for pos in self.positions.values())
    
    def get_equity(self, prices=None):
        """
        获取总资产
        
        Args:
            prices: dict {symbol: price} 当前价格字典
        """
        position_value = 0
        if prices:
            for symbol, pos in self.positions.items():
                if pos.shares > 0 and symbol in prices:
                    position_value += pos.shares * prices[symbol]
                else:
                    position_value += pos.cost  # 没有价格则用成本估算
        else:
            position_value = self.get_total_position_cost()
        
        return self.cash + position_value
    
    def get_available_slots(self):
        """获取可用仓位槽位"""
        active_positions = sum(1 for pos in self.positions.values() if pos.shares > 0)
        return max(0, self.risk_manager.max_positions - active_positions)
    
    def get_position_count(self):
        """获取当前持仓数量"""
        return sum(1 for pos in self.positions.values() if pos.shares > 0)
    
    # ==================== 交易接口 ====================
    
    def update(self, symbol, action, shares, price, commission_rate=0):
        """
        更新持仓
        
        Args:
            symbol: 股票代码
            action: "BUY" 或 "SELL"
            shares: 股数
            price: 价格
            commission_rate: 手续费率
        
        Returns:
            dict: 交易结果
        """
        result = {
            'success': False,
            'action': action,
            'symbol': symbol,
            'shares': 0,
            'price': price,
            'cost': 0,
            'commission': 0,
            'message': ''
        }
        
        if action == "BUY":
            return self._execute_buy(symbol, shares, price, commission_rate, result)
        elif action == "SELL":
            return self._execute_sell(symbol, shares, price, commission_rate, result)
        else:
            result['message'] = f"未知操作: {action}"
            return result
    
    def _execute_buy(self, symbol, shares, price, commission_rate, result):
        """执行买入"""
        # 检查是否允许开仓
        if not self.risk_manager.allow_new_position(self, symbol):
            result['message'] = f"已达到最大持仓数 {self.risk_manager.max_positions}"
            return result
        
        # 检查资金是否充足
        cost = shares * price
        commission = cost * commission_rate
        total_need = cost + commission
        
        if total_need > self.cash:
            result['message'] = f"资金不足: 需要 {total_need:.2f}, 可用 {self.cash:.2f}"
            return result
        
        # 执行买入
        self.cash -= total_need
        self.total_commission += commission
        
        # 更新持仓
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol)
        
        self.positions[symbol].add(shares, price)
        
        result['success'] = True
        result['shares'] = shares
        result['cost'] = cost
        result['commission'] = commission
        result['message'] = f"买入成功: {symbol} {shares}股 @ {price:.2f}"
        
        return result
    
    def _execute_sell(self, symbol, shares, price, commission_rate, result):
        """执行卖出"""
        if symbol not in self.positions:
            result['message'] = f"未持有 {symbol}"
            return result
        
        pos = self.positions[symbol]
        
        # 如果 shares <= 0 或 >= 持仓数，则全部卖出
        if shares <= 0 or shares >= pos.shares:
            shares = pos.shares
        
        if shares <= 0:
            result['message'] = f"持仓为空: {symbol}"
            return result
        
        # 计算收入
        revenue = shares * price
        commission = revenue * commission_rate
        net_revenue = revenue - commission
        
        # 执行卖出
        self.cash += net_revenue
        self.total_commission += commission
        
        # 更新持仓
        pos.reduce(shares)
        
        # 如果清仓，移除持仓记录
        if pos.shares <= 0:
            del self.positions[symbol]
        
        result['success'] = True
        result['shares'] = shares
        result['cost'] = revenue
        result['commission'] = commission
        result['message'] = f"卖出成功: {symbol} {shares}股 @ {price:.2f}"
        
        return result
    
    # ==================== 兼容旧接口 ====================
    
    @property
    def total_shares(self):
        """兼容旧接口: 返回第一只股票的股数"""
        for pos in self.positions.values():
            if pos.shares > 0:
                return pos.shares
        return 0
    
    @property
    def total_cost(self):
        """兼容旧接口: 返回第一只股票的成本"""
        for pos in self.positions.values():
            if pos.shares > 0:
                return pos.cost
        return 0
    
    @property  
    def avg_price(self):
        """兼容旧接口: 返回第一只股票的均价"""
        for pos in self.positions.values():
            if pos.shares > 0:
                return pos.avg_price
        return 0
