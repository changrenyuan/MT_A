class Portfolio:
    """负责资金和仓位记录"""

    def __init__(self, initial_cash):
        self.cash = initial_cash
        self.total_shares = 0
        self.total_cost = 0
        self.avg_price = 0

    def update(self, action, shares, price, commission_rate=0):
        cost = shares * price
        comm = cost * commission_rate

        if action == "BUY":
            self.cash -= (cost + comm)
            self.total_shares += shares
            self.total_cost += cost
            self.avg_price = self.total_cost / self.total_shares
        elif action == "SELL":
            self.cash += (cost - comm)
            
            # 支持部分卖出
            self.total_shares -= shares
            
            if self.total_shares <= 0:
                # 全部卖出，清零成本
                self.total_shares = 0
                self.total_cost = 0
                self.avg_price = 0
            else:
                # 部分卖出，按比例减少成本
                sell_ratio = shares / (shares + self.total_shares)
                self.total_cost = self.total_cost * (1 - sell_ratio)
                # avg_price 保持不变，因为平均成本不变
