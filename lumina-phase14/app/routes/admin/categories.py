"""Admin: categories."""
from flask import flash, redirect, render_template, url_for
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.forms.admin import CategoryForm
from app.models import Category
from app.routes.admin import bp
from app.services import storage
from app.utils.slugs import unique_slug


@bp.get("/categories")
def categories():
    return render_template("admin/categories.html", categories=Category.query.order_by(Category.name).all())


def _save(form: CategoryForm, category: Category) -> bool:
    is_new = category.id is None
    if Category.query.filter(Category.name == form.name.data, Category.id != (category.id or 0)).first():
        form.name.errors = [*form.name.errors, "A category with this name already exists."]
        return False
    store, old_image, new_url = storage.get_storage(), category.image, None
    upload = form.image.data if getattr(form.image.data, "filename", "") else None
    if upload is not None:
        try:
            new_url = store.save(upload, subfolder="categories")
        except storage.ImageError as exc:
            form.image.errors = [*form.image.errors, str(exc)]
            return False
    try:
        category.name = form.name.data
        category.description = form.description.data or None
        category.is_active = form.is_active.data
        if new_url:
            category.image = new_url
        elif form.image_url.data:
            category.image = form.image_url.data
        if is_new:
            category.slug = unique_slug(Category, form.name.data)
            db.session.add(category)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        store.delete(new_url)
        flash("Couldn't save the category. Please try again.", "error")
        return False
    if old_image and old_image != category.image:
        store.delete(old_image)
    return True


@bp.route("/categories/new", methods=["GET", "POST"])
def category_new():
    form = CategoryForm()
    if form.validate_on_submit() and _save(form, Category()):
        flash("Category created.", "success")
        return redirect(url_for("admin.categories"))
    return render_template("admin/category_form.html", form=form, category=None)


@bp.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
def category_edit(category_id):
    category = db.get_or_404(Category, category_id)
    form = CategoryForm(obj=category)
    if form.validate_on_submit() and _save(form, category):
        flash("Category saved.", "success")
        return redirect(url_for("admin.categories"))
    return render_template("admin/category_form.html", form=form, category=category)


@bp.post("/categories/<int:category_id>/delete")
def category_delete(category_id):
    category = db.get_or_404(Category, category_id)
    count = len(category.products)
    if count:
        flash(f"“{category.name}” still has {count} product{'s' if count != 1 else ''}. Move or delete them first.", "error")
    else:
        image = category.image
        db.session.delete(category)
        db.session.commit()
        storage.get_storage().delete(image)
        flash("Category deleted.", "info")
    return redirect(url_for("admin.categories"))
