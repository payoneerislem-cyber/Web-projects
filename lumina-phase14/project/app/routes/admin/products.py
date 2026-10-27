"""Admin: products (create / edit / soft-delete / flags / images)."""
from flask import flash, redirect, render_template, request, url_for
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.forms.admin import ProductForm
from app.models import Category, Product, ProductImage
from app.models.mixins import utcnow
from app.routes.admin import bp
from app.routes.admin._helpers import back, like, paginate, pagination_args
from app.services import storage
from app.utils.slugs import unique_slug

MAX_IMAGES = 8
FLAGS = {"active": "is_active", "featured": "is_featured", "new": "is_new", "best_seller": "is_best_seller"}


def _cents_str(cents):
    return f"{cents / 100:.2f}" if cents is not None else ""


@bp.get("/products")
def products():
    q = " ".join((request.args.get("q") or "").split())[:100]
    status = request.args.get("status", "")
    category_id = request.args.get("category", type=int)
    query = Product.query.options(joinedload(Product.category))
    if q:
        pattern = like(q)
        query = query.filter(or_(Product.name.ilike(pattern, escape="\\"), Product.sku.ilike(pattern, escape="\\"),
                                 Product.brand.ilike(pattern, escape="\\")))
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if status == "deleted":
        query = query.filter(Product.deleted_at.is_not(None))
    else:
        query = query.filter(Product.deleted_at.is_(None))
        if status == "inactive":
            query = query.filter(Product.is_active.is_(False))
        elif status == "active":
            query = query.filter(Product.is_active.is_(True))
        elif status == "low":
            query = query.filter(Product.stock_quantity <= Product.low_stock_threshold)
    pagination = paginate(query.order_by(Product.created_at.desc(), Product.id.desc()))
    return render_template("admin/products.html", products=pagination, q=q, status=status, category_id=category_id,
                           categories=Category.query.order_by(Category.name).all(), args=pagination_args())


def _form(product=None) -> ProductForm:
    form = ProductForm(obj=product)
    form.category_id.choices = [(c.id, c.name) for c in Category.query.order_by(Category.name).all()]
    if product is not None and request.method == "GET":
        form.price.data = _cents_str(product.price)
        form.compare_at_price.data = _cents_str(product.compare_at_price)
        form.cost_price.data = _cents_str(product.cost_price) if product.cost_price else ""
        form.specs.data = "\n".join(f"{k}: {v}" for k, v in product.specs.items()) if isinstance(product.specs, dict) else ""
    return form


def _save(form: ProductForm, product: Product) -> bool:
    is_new = product.id is None
    if Product.query.filter(Product.sku == form.sku.data, Product.id != (product.id or 0)).first():
        form.sku.errors = [*form.sku.errors, "This SKU is already used by another product."]
        return False
    delete_ids = {int(i) for i in request.form.getlist("delete_image") if i.isdecimal()}
    uploads = [f for f in (form.images.data or []) if getattr(f, "filename", "")]
    keep = [] if is_new else [img for img in product.images if img.id not in delete_ids]
    if len(keep) + len(uploads) + (1 if form.image_url.data else 0) > MAX_IMAGES:
        form.images.errors = [*form.images.errors, f"A product can have at most {MAX_IMAGES} images."]
        return False

    store, saved_urls = storage.get_storage(), []
    try:
        for upload in uploads:
            saved_urls.append(store.save(upload))
    except storage.ImageError as exc:
        for url in saved_urls:
            store.delete(url)
        form.images.errors = [*form.images.errors, str(exc)]
        return False

    removed_urls = []
    try:
        product.name, product.sku, product.category_id = form.name.data, form.sku.data, form.category_id.data
        product.brand = form.brand.data or None
        product.price = form.cents["price"]
        product.compare_at_price = form.cents["compare_at_price"]
        product.cost_price = form.cents["cost_price"] or 0
        product.stock_quantity, product.low_stock_threshold = form.stock_quantity.data, form.low_stock_threshold.data
        product.short_description = form.short_description.data or None
        product.description = form.description.data or None
        product.specs = form.specs_dict or None
        product.is_active, product.is_featured = form.is_active.data, form.is_featured.data
        product.is_new, product.is_best_seller = form.is_new.data, form.is_best_seller.data
        if is_new:
            product.slug = unique_slug(Product, form.name.data)
            db.session.add(product)
        for img in list(product.images):
            if img.id in delete_ids:
                removed_urls.append(img.url)
                product.images.remove(img)
        for url in [*saved_urls, *([form.image_url.data] if form.image_url.data else [])]:
            product.images.append(ProductImage(url=url, alt=product.name))
        for position, img in enumerate(product.images):
            img.position = position
        product.main_image = product.images[0].url if product.images else None
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        for url in saved_urls:
            store.delete(url)
        flash("Couldn't save the product. Please try again.", "error")
        return False
    for url in removed_urls:
        store.delete(url)
    return True


@bp.route("/products/new", methods=["GET", "POST"])
def product_new():
    form = _form()
    if form.validate_on_submit() and _save(form, Product()):
        flash("Product created.", "success")
        return redirect(url_for("admin.products"))
    return render_template("admin/product_form.html", form=form, product=None)


@bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
def product_edit(product_id):
    product = db.get_or_404(Product, product_id)
    form = _form(product)
    if form.validate_on_submit() and _save(form, product):
        flash("Product saved.", "success")
        return redirect(url_for("admin.products"))
    return render_template("admin/product_form.html", form=form, product=product)


@bp.post("/products/<int:product_id>/toggle")
def product_toggle(product_id):
    product = db.get_or_404(Product, product_id)
    attr = FLAGS.get(request.form.get("field", ""))
    if attr is None:
        flash("Unknown option.", "error")
    else:
        setattr(product, attr, not getattr(product, attr))
        db.session.commit()
        flash(f"{product.name}: {attr[3:].replace('_', ' ')} is now {'on' if getattr(product, attr) else 'off'}.", "success")
    return back("admin.products")


@bp.post("/products/<int:product_id>/delete")
def product_delete(product_id):
    """Soft delete: past orders keep their snapshots and the product can be restored."""
    product = db.get_or_404(Product, product_id)
    product.deleted_at, product.is_active = utcnow(), False
    db.session.commit()
    flash(f"“{product.name}” was removed from the store. You can restore it from the Deleted filter.", "info")
    return back("admin.products")


@bp.post("/products/<int:product_id>/restore")
def product_restore(product_id):
    product = db.get_or_404(Product, product_id)
    product.deleted_at = None
    db.session.commit()
    flash(f"“{product.name}” was restored (it is inactive until you switch it on).", "success")
    return back("admin.products", status="deleted")
