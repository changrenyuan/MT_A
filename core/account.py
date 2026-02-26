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
            self.total_shares = 0
            self.total_cost = 0
            self.avg_price = 0