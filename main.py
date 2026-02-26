import math
import matplotlib.pyplot as plt
import akshare as ak
import matplotlib

# 中文显示
matplotlib.rcParams['font.sans-serif'] = ['SimHei']
matplotlib.rcParams['axes.unicode_minus'] = False

# =============================
# 回测函数
# =============================
def martingale_backtest_full(
        symbol,
        entry_price,
        first_amount,
        base_drop,
        step_factor,
        growth_factor,
        max_steps,
        total_capital,
        take_profit_pct=0.03,   # 止盈百分比
        stop_loss_pct=0.1       # 止损百分比
):
    stock_df = ak.stock_zh_a_daily(symbol=symbol)
    dates = stock_df.index.tolist()
    prices = stock_df['close'].tolist()

    step = 0
    cumulative_drop = 0
    used_capital = 0
    total_shares = 0
    total_cost = 0

    history = []

    for date, price in zip(dates, prices):

        trigger_buy = False
        buy_shares = 0
        buy_cost = 0
        trigger_sell = False
        sell_amount = 0

        avg_price = total_cost / total_shares if total_shares > 0 else 0
        equity = total_shares * price
        floating_profit = equity - total_cost if total_shares > 0 else 0

        # ---- 卖出逻辑（止盈/止损） ----
        if total_shares > 0:
            if price >= avg_price * (1 + take_profit_pct):
                trigger_sell = True
                sell_amount = total_shares
                total_shares = 0
                total_cost = 0
            elif price <= avg_price * (1 - stop_loss_pct):
                trigger_sell = True
                sell_amount = total_shares
                total_shares = 0
                total_cost = 0

        # ---- 买入逻辑 ----
        if step < max_steps:
            incremental_drop = base_drop * (step_factor ** step)
            cumulative_drop += incremental_drop
            trigger_price = entry_price * (1 - cumulative_drop)

            if price <= trigger_price and used_capital < total_capital:
                amount = first_amount * (growth_factor ** step)
                if used_capital + amount > total_capital:
                    amount = total_capital - used_capital
                if amount > 0:
                    buy_shares = math.floor(amount / price / 100) * 100
                    if buy_shares > 0:
                        buy_cost = buy_shares * price
                        used_capital += buy_cost
                        total_shares += buy_shares
                        total_cost += buy_cost
                        trigger_buy = True
                        step += 1
                        avg_price = total_cost / total_shares

        equity = total_shares * price
        floating_profit = equity - total_cost

        history.append({
            "日期": date,
            "收盘价": price,
            "触发买入": trigger_buy,
            "买入股数": buy_shares,
            "本次投入": buy_cost,
            "触发卖出": trigger_sell,
            "卖出股数": sell_amount,
            "累计投入": total_cost,
            "持仓股数": total_shares,
            "持仓均价": avg_price,
            "持仓市值": equity,
            "浮盈": floating_profit
        })

    return history

# =============================
# 参数
# =============================
symbol = "sh600415"
entry_price = 25
first_amount = 10000
base_drop = 0.01
step_factor = 1.1
growth_factor = 1.5
max_steps = 6
total_capital = 100000

history = martingale_backtest_full(symbol, entry_price, first_amount,
                                   base_drop, step_factor, growth_factor,
                                   max_steps, total_capital)

# =============================
# 打印完整每日状态
# =============================
print("===== 每日交易明细 =====")
for h in history:
    status = []
    if h['触发买入']:
        status.append(f"买入 {h['买入股数']}股 / {h['本次投入']:.2f}元")
    if h['触发卖出']:
        status.append(f"卖出 {h['卖出股数']}股")
    if not status:
        status.append("-")
    print(f"{h['日期']} | 收盘价: {h['收盘价']:.2f} | {', '.join(status)} | "
          f"持仓股数: {h['持仓股数']} | 持仓均价: {h['持仓均价']:.2f} | "
          f"累计投入: {h['累计投入']:.2f} | 浮盈: {h['浮盈']:.2f}")

# =============================
# 绘图：上下两图
# =============================
dates = [h["日期"] for h in history]
prices = [h["收盘价"] for h in history]
avg_price_curve = [h["持仓均价"] for h in history]
equity_curve = [h["持仓市值"] for h in history]
cumulative_cost_curve = [h["累计投入"] for h in history]
floating_profit_curve = [h["浮盈"] for h in history]

fig, (ax1, ax2) = plt.subplots(2,1, figsize=(16,10), sharex=True)

# ---- 上图：股价 + 持仓均价 + 买入/卖出点 ----
ax1.plot(dates, prices, label="股价", color='blue')
ax1.plot(dates, avg_price_curve, label="持仓均价", color='orange', linestyle='--')

for i, h in enumerate(history):
    if h['触发买入']:
        ax1.scatter(h['日期'], h['收盘价'], color='red', marker='^', s=120)
    if h['触发卖出']:
        ax1.scatter(h['日期'], h['收盘价'], color='green', marker='v', s=120)

ax1.set_ylabel("价格")
ax1.set_title(f"{symbol} 回测 - 马丁策略每日状态")
ax1.legend()
ax1.grid(True)

# ---- 下图：累计投入 + 持仓市值 + 浮盈 ----
ax2.plot(dates, cumulative_cost_curve, label="累计投入", color='purple', linestyle='--')
ax2.plot(dates, equity_curve, label="持仓市值", color='green')
ax2.plot(dates, floating_profit_curve, label="浮盈", color='red')
ax2.set_xlabel("日期")
ax2.set_ylabel("资金 / 市值 / 浮盈")
ax2.legend()
ax2.grid(True)

plt.show()