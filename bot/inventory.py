"""Per-bot inventory + sales stats for the "📊 Sales & Stock" tool
(bot/handlers/tools/shop.py) — a bot owner's own small-business view of
THEIR shop: revenue, order counts, top products, and a low/out-of-stock
list. Mirrors bot/admin_panel.py's platform-wide stats (same PAID_STATUSES,
same query shapes) but scoped to a single bot_id — that module stays the
platform ADMIN's cross-bot view; this one is what an ordinary bot owner
sees about their own store. No Telegram-handler code here.

This is a lightweight owner-facing estimate, not real accounting: revenue
sums Order.price as stored regardless of payment method/currency (same
simplification bot/admin_panel.py already makes), and profit is computed
against each product's CURRENT cost_price (not a per-order snapshot), so
editing a cost price after the fact reshapes past profit too.
"""

import uuid

from sqlalchemy import func, select

from bot.admin_panel import PAID_STATUSES
from bot.db.base import async_session_maker
from bot.db.models import Order, Product

# A product at or below this stock level is flagged in get_shop_stats's
# low_stock list (0 itself means fully out of stock).
LOW_STOCK_THRESHOLD = 5


async def get_shop_stats(bot_id: uuid.UUID) -> dict:
    async with async_session_maker() as session:
        product_count = (
            await session.execute(select(func.count(Product.id)).where(Product.bot_id == bot_id))
        ).scalar_one()

        order_count = (
            await session.execute(select(func.count(Order.id)).where(Order.bot_id == bot_id))
        ).scalar_one()

        paid_count, revenue = (
            await session.execute(
                select(func.count(Order.id), func.coalesce(func.sum(Order.price), 0)).where(
                    Order.bot_id == bot_id, Order.status.in_(PAID_STATUSES)
                )
            )
        ).one()

        profit_rows = (
            await session.execute(
                select(Order.price, Product.cost_price)
                .join(Product, Product.id == Order.product_id)
                .where(
                    Order.bot_id == bot_id,
                    Order.status.in_(PAID_STATUSES),
                    Product.cost_price.isnot(None),
                )
            )
        ).all()
        profit_known = len(profit_rows) > 0
        profit = sum(price - cost for price, cost in profit_rows) if profit_known else None

        top_rows = (
            await session.execute(
                select(
                    Product.name,
                    func.count(Order.id),
                    func.coalesce(func.sum(Order.price), 0),
                )
                .join(Order, Order.product_id == Product.id)
                .where(Product.bot_id == bot_id, Order.status.in_(PAID_STATUSES))
                .group_by(Product.id, Product.name)
                .order_by(func.count(Order.id).desc())
                .limit(5)
            )
        ).all()
        top_products = [{"name": name, "orders": cnt, "revenue": int(rev)} for name, cnt, rev in top_rows]

        low_stock_rows = (
            await session.execute(
                select(Product.name, Product.stock_quantity)
                .where(
                    Product.bot_id == bot_id,
                    Product.stock_quantity.isnot(None),
                    Product.stock_quantity <= LOW_STOCK_THRESHOLD,
                )
                .order_by(Product.stock_quantity)
            )
        ).all()
        low_stock = [{"name": name, "stock": qty} for name, qty in low_stock_rows]

    return {
        "product_count": product_count,
        "order_count": order_count,
        "paid_order_count": paid_count,
        "revenue": int(revenue),
        "profit": int(profit) if profit is not None else None,
        "top_products": top_products,
        "low_stock": low_stock,
    }
