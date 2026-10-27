"""Catalogue queries: browsing, filters, sorting, search and product-detail data."""
import operator
from dataclasses import dataclass, replace
from functools import reduce

from sqlalchemy import case, func, or_
from sqlalchemy.orm import contains_eager, joinedload, selectinload

from app.extensions import db
from app.models import Category, Product, Review, ReviewStatus
from app.utils.money import to_cents

ALLOWED_PER_PAGE = (12, 24, 48)
RATING_CHOICES = (4, 3, 2, 1)
MAX_PRICE_CENTS = 10**9
MAX_SEARCH_TERMS = 6

SORTS = {
    "newest": (Product.created_at.desc(), Product.id.desc()),
    "price_asc": (Product.price.asc(), Product.id.asc()),
    "price_desc": (Product.price.desc(), Product.id.asc()),
    "rating": (Product.avg_rating.desc(), Product.review_count.desc(), Product.id.asc()),
    "popularity": (Product.sales_count.desc(), Product.id.asc()),
}
SORT_LABELS = {
    "relevance": "Best match",
    "newest": "Newest",
    "price_asc": "Price: low to high",
    "price_desc": "Price: high to low",
    "rating": "Top rated",
    "popularity": "Most popular",
}


def sort_options(include_relevance: bool = False):
    keys = (["relevance"] if include_relevance else []) + list(SORTS)
    return [(key, SORT_LABELS[key]) for key in keys]


def parse_per_page(value, default: int) -> int:
    return value if value in ALLOWED_PER_PAGE else default


# ---------------------------------------------------------------- filters
def _parse_price(raw) -> int | None:
    """User text -> cents, or None if empty/invalid/out of range."""
    if not raw or not str(raw).strip():
        return None
    try:
        cents = to_cents(raw)
    except ValueError:
        return None
    return cents if 0 <= cents <= MAX_PRICE_CENTS else None


def _fmt_price(cents: int) -> str:
    return f"{cents / 100:.2f}".rstrip("0").rstrip(".")


@dataclass(frozen=True)
class ProductFilters:
    """Everything a visitor can narrow a listing by. Invalid input is ignored."""

    q: str = ""
    category: str | None = None  # slug
    min_price: int | None = None  # cents
    max_price: int | None = None
    brands: tuple = ()
    min_rating: int | None = None
    in_stock: bool = False
    sort: str = "newest"
    default_sort: str = "newest"

    @classmethod
    def from_args(cls, args, default_sort: str = "newest") -> "ProductFilters":
        q = " ".join((args.get("q") or "").split())[:100]
        category = (args.get("category") or "").strip()[:120] or None
        low, high = _parse_price(args.get("min_price")), _parse_price(args.get("max_price"))
        if low is not None and high is not None and low > high:
            low, high = high, low
        brands = tuple(dict.fromkeys(
            b.strip()[:80] for b in args.getlist("brand") if b and b.strip()))[:20]
        rating = args.get("rating", type=int)
        valid_sorts = set(SORTS) | ({"relevance"} if default_sort == "relevance" else set())
        sort = args.get("sort")
        return cls(
            q=q, category=category, min_price=low, max_price=high, brands=brands,
            min_rating=rating if rating in RATING_CHOICES else None,
            in_stock=(args.get("in_stock") or "").lower() in {"1", "true", "on", "yes"},
            sort=sort if sort in valid_sorts else default_sort, default_sort=default_sort,
        )

    # --- helpers for templates / URL building ---
    @property
    def min_price_str(self) -> str:
        return _fmt_price(self.min_price) if self.min_price is not None else ""

    @property
    def max_price_str(self) -> str:
        return _fmt_price(self.max_price) if self.max_price is not None else ""

    @property
    def active_count(self) -> int:
        """Number of narrowing filters (search text and sort don't count)."""
        return (bool(self.category) + (self.min_price is not None or self.max_price is not None)
                + len(self.brands) + bool(self.min_rating) + self.in_stock)

    def to_args(self) -> dict:
        args = {}
        if self.q:
            args["q"] = self.q
        if self.category:
            args["category"] = self.category
        if self.min_price is not None:
            args["min_price"] = self.min_price_str
        if self.max_price is not None:
            args["max_price"] = self.max_price_str
        if self.brands:
            args["brand"] = list(self.brands)
        if self.min_rating:
            args["rating"] = self.min_rating
        if self.in_stock:
            args["in_stock"] = 1
        if self.sort != self.default_sort:
            args["sort"] = self.sort
        return args

    def without(self, key: str, value=None) -> "ProductFilters":
        if key == "brand":
            return replace(self, brands=tuple(b for b in self.brands if b != value))
        if key == "price":
            return replace(self, min_price=None, max_price=None)
        if key == "rating":
            return replace(self, min_rating=None)
        if key == "in_stock":
            return replace(self, in_stock=False)
        if key == "category":
            return replace(self, category=None)
        raise ValueError(key)


# ---------------------------------------------------------------- query building
def _cards():
    """Visible products with images eager-loaded (avoids N+1 in product cards)."""
    return Product.visible_query().options(selectinload(Product.images))


def _like(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _terms(q: str) -> list:
    return [t[:40] for t in (q or "").split()][:MAX_SEARCH_TERMS]


def _term_clauses(term: str):
    """(match condition, relevance score) for one search word."""
    pattern = _like(term)

    def like(column):
        return column.ilike(pattern, escape="\\")

    weighted = [(like(Product.sku), 5), (like(Product.name), 4), (like(Product.brand), 3),
                (like(Category.name), 2), (like(Product.short_description), 1),
                (like(Product.description), 1)]
    condition = or_(*(cond for cond, _ in weighted))
    score = reduce(operator.add, (case((cond, weight), else_=0) for cond, weight in weighted))
    return condition, score


def _filtered_query(filters: ProductFilters, category: Category | None = None):
    """Returns (query, relevance_score_or_None). Every search word must match somewhere."""
    query = (Product.visible_query().join(Product.category)
             .options(contains_eager(Product.category), selectinload(Product.images)))
    if category is not None:
        query = query.filter(Product.category_id == category.id)
    score = None
    for term in _terms(filters.q):
        condition, term_score = _term_clauses(term)
        query = query.filter(condition)
        score = term_score if score is None else score + term_score
    if filters.min_price is not None:
        query = query.filter(Product.price >= filters.min_price)
    if filters.max_price is not None:
        query = query.filter(Product.price <= filters.max_price)
    if filters.brands:
        query = query.filter(Product.brand.in_(filters.brands))
    if filters.min_rating:
        query = query.filter(Product.avg_rating >= filters.min_rating)
    if filters.in_stock:
        query = query.filter(Product.stock_quantity > 0)
    return query, score


def list_products(filters: ProductFilters | None = None, *, category: Category | None = None,
                  page: int = 1, per_page: int = 12):
    filters = filters or ProductFilters()
    query, score = _filtered_query(filters, category)
    if filters.sort == "relevance" and score is not None:
        order = (score.desc(), Product.sales_count.desc(), Product.id.asc())
    else:
        order = SORTS.get(filters.sort, SORTS["newest"])
    return query.order_by(*order).paginate(page=max(page, 1), per_page=per_page, error_out=False)


def brand_facets(category: Category | None = None, q: str = ""):
    """[(brand, count)] available within the current category / search scope."""
    query = (db.session.query(Product.brand, func.count(Product.id)).join(Product.category)
             .filter(Product.is_active.is_(True), Product.deleted_at.is_(None),
                     Product.brand.is_not(None)))
    if category is not None:
        query = query.filter(Product.category_id == category.id)
    for term in _terms(q):
        query = query.filter(_term_clauses(term)[0])
    return [(brand, count) for brand, count in
            query.group_by(Product.brand).order_by(Product.brand).all()]


def find_category(slug: str):
    return Category.query.filter_by(slug=slug, is_active=True).first()


def suggest(q: str, limit: int = 6):
    """Live-search suggestions: (products, categories)."""
    if not _terms(q):
        return [], []
    query, score = _filtered_query(ProductFilters(q=q, sort="relevance", default_sort="relevance"))
    products = (query.order_by(score.desc(), Product.sales_count.desc(), Product.id.asc())
                .limit(limit).all())
    categories = (Category.query
                  .filter(Category.is_active.is_(True),
                          Category.name.ilike(_like(" ".join(q.split())), escape="\\"))
                  .order_by(Category.name).limit(3).all())
    return products, categories


# ---------------------------------------------------------------- home page sections
def featured(limit: int = 8):
    return (_cards().filter(Product.is_featured.is_(True))
            .order_by(*SORTS["newest"]).limit(limit).all())


def new_arrivals(limit: int = 8):
    return (_cards().filter(Product.is_new.is_(True))
            .order_by(*SORTS["newest"]).limit(limit).all())


def best_sellers(limit: int = 8):
    return (_cards().filter(Product.is_best_seller.is_(True))
            .order_by(Product.sales_count.desc(), Product.id).limit(limit).all())


def categories_with_counts():
    """[(Category, visible_product_count), ...] for active categories."""
    rows = (
        db.session.query(Category, func.count(Product.id))
        .outerjoin(Product, (Product.category_id == Category.id)
                   & Product.is_active.is_(True) & Product.deleted_at.is_(None))
        .filter(Category.is_active.is_(True))
        .group_by(Category.id)
        .order_by(Category.name)
        .all()
    )
    return [(category, count) for category, count in rows]


def home_sections() -> dict:
    categories = categories_with_counts()
    return {
        "featured": featured(8),
        "new_arrivals": new_arrivals(4),
        "best_sellers": best_sellers(4),
        "categories": categories,
        "product_total": Product.visible_query().count(),
        "category_total": len(categories),
    }


def get_active_category_or_404(slug: str) -> Category:
    return Category.query.filter_by(slug=slug, is_active=True).first_or_404()


# ---------------------------------------------------------------- product detail
def get_product_or_404(slug: str) -> Product:
    return (Product.visible_query()
            .options(selectinload(Product.images), joinedload(Product.category))
            .filter(Product.slug == slug).first_or_404())


def rating_summary(product_id: int) -> dict:
    """Average, count and 5..1 star distribution from approved reviews."""
    rows = (db.session.query(Review.rating, func.count(Review.id))
            .filter(Review.product_id == product_id, Review.status == ReviewStatus.APPROVED)
            .group_by(Review.rating).all())
    counts = dict(rows)
    total = sum(counts.values())
    average = sum(r * c for r, c in counts.items()) / total if total else 0.0
    return {
        "average": round(average, 1),
        "total": total,
        "distribution": [
            {"stars": s, "count": counts.get(s, 0),
             "percent": round(counts.get(s, 0) * 100 / total) if total else 0}
            for s in (5, 4, 3, 2, 1)
        ],
    }


def product_reviews(product_id: int, limit: int = 10):
    return (Review.query.filter_by(product_id=product_id, status=ReviewStatus.APPROVED)
            .options(joinedload(Review.user))
            .order_by(Review.created_at.desc(), Review.id.desc()).limit(limit).all())


def related_products(product: Product, limit: int = 4):
    return (_cards().filter(Product.category_id == product.category_id, Product.id != product.id)
            .order_by(Product.sales_count.desc(), Product.id).limit(limit).all())


def products_by_ids(ids):
    """Visible products for `ids`, keeping the order of `ids`."""
    if not ids:
        return []
    found = {p.id: p for p in _cards().filter(Product.id.in_(ids)).all()}
    return [found[i] for i in ids if i in found]
