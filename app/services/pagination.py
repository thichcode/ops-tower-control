from math import ceil
from typing import Any

from sqlalchemy.orm import Query


def paginate(
    query: Query,
    page: int = 1,
    per_page: int = 50,
) -> dict[str, Any]:
    total = query.count()
    pages = max(0, ceil(total / per_page)) if per_page > 0 else 0
    page = max(1, min(page, pages)) if pages > 0 else 1
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
        "has_prev": page > 1,
        "has_next": page < pages,
    }
