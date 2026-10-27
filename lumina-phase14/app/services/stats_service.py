"""Numbers for the admin dashboard."""
from datetime import timedelta

from sqlalchemy import func

from app.extensions import db
from app.models import Order, OrderStatus, Product, User
from app.models.mixins import utcnow


def overview(days: int = 14) -> dict:
    counted = Order.status.notin_((OrderStatus.CANCELLED, OrderStatus.REFUNDED))
    total_sales = db.session.query(func.coalesce(func.sum(Order.total), 0)).filter(counted).scalar() or 0

    start = (utcnow() - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = (db.session.query(func.date(Order.created_at), func.coalesce(func.sum(Order.total), 0), func.count(Order.id))
            .filter(counted, Order.created_at >= start).group_by(func.date(Order.created_at)).all())
    by_day = {str(day): (int(total), int(count)) for day, total, count in rows}
    series = []
    for i in range(days):
        day = (start + timedelta(days=i)).date()
        total, count = by_day.get(day.isoformat(), (0, 0))
        series.append({"date": day.isoformat(), "label": day.strftime("%d %b"), "total": total, "orders": count})

    status_counts = dict(db.session.query(Order.status, func.count(Order.id)).group_by(Order.status).all())
    on_sale = Product.query.filter(Product.deleted_at.is_(None), Product.is_active.is_(True))
    return {
        "total_sales": int(total_sales),
        "orders": Order.query.count(),
        "customers": User.query.filter_by(role="customer").count(),
        "products": on_sale.count(),
        "low_stock": on_sale.filter(Product.stock_quantity <= Product.low_stock_threshold).count(),
        "pending": status_counts.get(OrderStatus.PENDING, 0),
        "status_counts": [(s, status_counts.get(s, 0)) for s in OrderStatus.ALL],
        "series": series,
        "recent_orders": Order.query.order_by(Order.created_at.desc(), Order.id.desc()).limit(8).all(),
        "low_stock_products": (on_sale.filter(Product.stock_quantity <= Product.low_stock_threshold)
                               .order_by(Product.stock_quantity, Product.id).limit(6).all()),
    }
