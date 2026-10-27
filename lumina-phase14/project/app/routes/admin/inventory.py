"""Admin: stock levels."""
from flask import flash, render_template, request
from sqlalchemy import or_

from app.extensions import db
from app.models import Product
from app.routes.admin import bp
from app.routes.admin._helpers import back, like, paginate, pagination_args


@bp.get("/inventory")
def inventory():
    q = " ".join((request.args.get("q") or "").split())[:100]
    level = request.args.get("level", "")
    query = Product.query.filter(Product.deleted_at.is_(None))
    if level == "out":
        query = query.filter(Product.stock_quantity <= 0)
    elif level == "low":
        query = query.filter(Product.stock_quantity > 0, Product.stock_quantity <= Product.low_stock_threshold)
    if q:
        pattern = like(q)
        query = query.filter(or_(Product.name.ilike(pattern, escape="\\"), Product.sku.ilike(pattern, escape="\\")))
    base = Product.query.filter(Product.deleted_at.is_(None))
    counts = {
        "all": base.count(),
        "low": base.filter(Product.stock_quantity > 0, Product.stock_quantity <= Product.low_stock_threshold).count(),
        "out": base.filter(Product.stock_quantity <= 0).count(),
    }
    pagination = paginate(query.order_by(Product.stock_quantity, Product.id), per_page=25)
    return render_template("admin/inventory.html", products=pagination, q=q, level=level, counts=counts,
                           args=pagination_args())


@bp.post("/inventory/<int:product_id>")
def inventory_update(product_id):
    product = db.get_or_404(Product, product_id)
    try:
        stock = int(request.form.get("stock_quantity", ""))
        threshold = int(request.form.get("low_stock_threshold", ""))
    except ValueError:
        flash("Stock and alert level must be whole numbers.", "error")
        return back("admin.inventory")
    if not (0 <= stock <= 1_000_000 and 0 <= threshold <= 100_000):
        flash("Stock and alert level must be between 0 and the allowed maximum.", "error")
    else:
        product.stock_quantity, product.low_stock_threshold = stock, threshold
        db.session.commit()
        flash(f"Stock for “{product.name}” updated.", "success")
    return back("admin.inventory")
