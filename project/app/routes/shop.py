"""Catalogue: shop listing, category pages, search and product details."""
from dataclasses import replace
from urllib.parse import urljoin

from flask import (Blueprint, current_app, redirect, render_template, request,
                   session, url_for)

from app.services import catalog_service
from app.services.catalog_service import ProductFilters

bp = Blueprint("shop", __name__)

RECENT_KEY = "recently_viewed"
RECENT_MAX = 8


# ---------------------------------------------------------------- listing helpers
def _page_args():
    default = current_app.config["PRODUCTS_PER_PAGE"]
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = catalog_service.parse_per_page(request.args.get("per_page", type=int), default)
    return page, per_page, ({} if per_page == default else {"per_page": per_page})


def _price_label(filters, symbol):
    low, high = filters.min_price_str, filters.max_price_str
    if low and high:
        return f"Price: {symbol}{low} - {symbol}{high}"
    return f"Price: from {symbol}{low}" if low else f"Price: up to {symbol}{high}"


def _listing(endpoint, view_args, *, category=None, default_sort="newest"):
    """Shared logic for /shop, /category/<slug> and /search.

    Returns (redirect_response, None) or (None, template_context).
    """
    filters = ProductFilters.from_args(request.args, default_sort=default_sort)
    selected = category
    if category is not None:
        filters = replace(filters, category=None)  # the URL already fixes the category
    elif filters.category:
        selected = catalog_service.find_category(filters.category)
        if selected is None:  # unknown slug: ignore the filter
            filters = replace(filters, category=None)

    page, per_page, per_args = _page_args()
    products = catalog_service.list_products(filters, category=selected, page=page, per_page=per_page)
    base_args = {**view_args, **per_args}
    if products.pages and page > products.pages:
        return redirect(url_for(endpoint, **base_args, **filters.to_args(), page=products.pages)), None

    def url_for_filters(f):
        return url_for(endpoint, **base_args, **f.to_args())

    symbol = current_app.config["CURRENCY_SYMBOL"]
    chips = []
    if filters.category and selected is not None:
        chips.append((f"Category: {selected.name}", url_for_filters(filters.without("category"))))
    if filters.min_price is not None or filters.max_price is not None:
        chips.append((_price_label(filters, symbol), url_for_filters(filters.without("price"))))
    for brand in filters.brands:
        chips.append((f"Brand: {brand}", url_for_filters(filters.without("brand", brand))))
    if filters.min_rating:
        chips.append((f"{filters.min_rating} stars & up", url_for_filters(filters.without("rating"))))
    if filters.in_stock:
        chips.append(("In stock only", url_for_filters(filters.without("in_stock"))))

    clear_filters = ProductFilters(q=filters.q, sort=filters.sort, default_sort=default_sort)
    return None, {
        "products": products,
        "filters": filters,
        "brands": catalog_service.brand_facets(selected, filters.q),
        "chips": chips,
        "active_count": filters.active_count,
        "clear_url": url_for_filters(clear_filters),
        "filter_action": url_for(endpoint, **view_args),
        "per_page_arg": per_args.get("per_page"),
        "sort_options": catalog_service.sort_options(include_relevance=default_sort == "relevance"),
        "pagination_endpoint": endpoint,
        "pagination_args": {**base_args, **filters.to_args()},
        "show_category_filter": category is None,
    }


@bp.get("/shop")
def index():
    redirect_response, ctx = _listing("shop.index", {})
    return redirect_response or render_template("shop/index.html", **ctx)


@bp.get("/category/<slug>")
def category(slug):
    cat = catalog_service.get_active_category_or_404(slug)
    redirect_response, ctx = _listing("shop.category", {"slug": slug}, category=cat)
    return redirect_response or render_template("shop/category.html", category=cat, **ctx)


@bp.get("/search")
def search():
    q = " ".join((request.args.get("q") or "").split())[:100]
    if not q:
        return render_template("shop/search.html", q="", products=None, best_sellers=[])
    redirect_response, ctx = _listing("shop.search", {}, default_sort="relevance")
    if redirect_response:
        return redirect_response
    best = catalog_service.best_sellers(4) if not ctx["products"].items else []
    return render_template("shop/search.html", q=q, best_sellers=best, **ctx)


# ---------------------------------------------------------------- product page
def _gallery(product):
    items = [{"url": img.url, "alt": img.alt or product.name} for img in product.images]
    if product.main_image and all(i["url"] != product.main_image for i in items):
        items.insert(0, {"url": product.main_image, "alt": product.name})
    return items


def _absolute(url):
    return urljoin(request.host_url, url) if url and not url.startswith("http") else url


def _json_ld(product, summary, page_url, image):
    data = {
        "@context": "https://schema.org", "@type": "Product", "name": product.name,
        "sku": product.sku, "description": product.short_description or product.name,
        "url": page_url,
        "offers": {
            "@type": "Offer", "url": page_url,
            "priceCurrency": current_app.config["CURRENCY_CODE"],
            "price": f"{product.price / 100:.2f}",
            "availability": ("https://schema.org/InStock" if product.stock_quantity > 0
                             else "https://schema.org/OutOfStock"),
        },
    }
    if product.brand:
        data["brand"] = {"@type": "Brand", "name": product.brand}
    if image:
        data["image"] = [image]
    if summary["total"]:
        data["aggregateRating"] = {"@type": "AggregateRating",
                                   "ratingValue": summary["average"], "reviewCount": summary["total"]}
    return data


def _recently_viewed(current_id):
    ids = [i for i in session.get(RECENT_KEY, []) if isinstance(i, int) and i != current_id]
    return catalog_service.products_by_ids(ids[:RECENT_MAX])[:4]


def _remember(product_id):
    ids = [i for i in session.get(RECENT_KEY, []) if isinstance(i, int) and i != product_id]
    session[RECENT_KEY] = [product_id, *ids][:RECENT_MAX]


@bp.get("/product/<slug>")
def product(slug):
    item = catalog_service.get_product_or_404(slug)
    summary = catalog_service.rating_summary(item.id)
    gallery = _gallery(item)
    page_url = url_for("shop.product", slug=item.slug, _external=True)
    image = _absolute(gallery[0]["url"]) if gallery else None
    recent = _recently_viewed(item.id)
    _remember(item.id)
    return render_template(
        "shop/product.html", product=item, gallery=gallery, summary=summary,
        reviews=catalog_service.product_reviews(item.id, limit=10),
        related=catalog_service.related_products(item, limit=4), recently_viewed=recent,
        max_qty=max(min(item.stock_quantity, current_app.config["MAX_QTY_PER_ITEM"]), 0),
        canonical_url=page_url, og_image=image, json_ld=_json_ld(item, summary, page_url, image),
    )
