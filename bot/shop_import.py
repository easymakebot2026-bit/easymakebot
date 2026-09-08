"""Spreadsheet import for the "Shop" tool (bot/handlers/tools/shop.py):
lets a bot owner upload their OWN product catalogue (name/price/stock/etc.)
and have it upserted directly into Product rows — no manual "Add Product"
wizard needed per item. Sibling to bot/content_import.py (same parsing
approach — forgiving header matching, .xlsx/.csv, Code-based upsert/delete —
reused via the shared, already-generic helpers there), but a separate module
because the two import SELLABLE PRODUCTS with different fields (price, stock,
cost) rather than generic content (body/link/category/nesting).

Nothing here needs a network call or any external service.
"""

from io import BytesIO

from openpyxl import Workbook

from bot.content_import import _load_rows, _normalize  # generic, pure — safe to reuse

# Column header synonyms — English + Persian only (this platform's two
# primary languages everywhere else, e.g. bot/help_text.py); unlike the
# Content List importer this doesn't try to cover all 10 languages, to keep
# scope manageable. A bot owner's own English/Persian catalogue still works
# out of the box, same forgiving matching (loose contains-match, any header
# row in the first 15 rows).
_COLUMN_SYNONYMS = {
    "name": {
        "title", "name", "product", "product name", "item", "item name",
        "عنوان", "نام", "نام محصول", "کالا", "محصول",
    },
    "description": {
        "description", "desc", "details", "body", "text", "info",
        "توضیحات", "توضیح", "شرح", "جزئیات", "متن",
    },
    "price": {
        "price", "cost", "sale price", "unit price", "amount",
        "قیمت", "قیمت فروش", "مبلغ",
    },
    "cost_price": {
        "cost price", "purchase price", "wholesale price", "buy price",
        "قیمت خرید", "بهای تمام‌شده", "قیمت عمده",
    },
    "stock": {
        "stock", "quantity", "qty", "inventory", "stock quantity", "count", "units",
        "موجودی", "تعداد", "انبار", "موجودی انبار",
    },
    "image_url": {
        "image", "image url", "imageurl", "img", "photo", "picture",
        "لینک تصویر", "عکس", "تصویر", "عکس محصول",
    },
    "code": {
        "code", "sku", "id", "ref", "reference",
        "کد", "شناسه", "کد کالا",
    },
    "action": {
        "action", "op", "operation", "command",
        "عملیات", "اقدام", "دستور",
    },
}

_DELETE_ACTION_VALUES = {
    "delete", "remove", "del", "drop",
    "حذف", "پاک", "پاک کردن", "حذف کردن",
}

_NORMALIZED_SYNONYMS = {
    field: {_normalize(name) for name in names} for field, names in _COLUMN_SYNONYMS.items()
}

_HEADER_SCAN_ROWS = 15

SAMPLE_HEADERS_EN = ["Name", "Description", "Price", "Cost Price", "Stock", "Image URL", "Code", "Action"]
SAMPLE_HEADERS_FA = ["نام", "توضیحات", "قیمت", "قیمت خرید", "موجودی", "لینک تصویر", "کد", "عملیات"]


def _match_field(header: object) -> str | None:
    if header is None:
        return None
    norm = _normalize(header)
    if not norm:
        return None
    for field, names in _NORMALIZED_SYNONYMS.items():
        if norm in names:
            return field
    if len(norm) >= 3:
        for field, names in _NORMALIZED_SYNONYMS.items():
            for name in names:
                if len(name) >= 3 and (name in norm or norm in name):
                    return field
    return None


def _pick_header_row(rows: list[tuple]) -> tuple[int, list[str | None]]:
    best_index = -1
    best_fields: list[str | None] = []
    best_score = 0
    for index, row in enumerate(rows[:_HEADER_SCAN_ROWS]):
        fields = [_match_field(cell) for cell in row]
        score = sum(1 for f in fields if f)
        if score > best_score:
            best_index, best_fields, best_score = index, fields, score

    if best_score == 0:
        raise ValueError(
            "None of the column headers were recognized. Use the sample "
            "template's headers (Name, Description, Price, Stock, Image URL, Code, Action) "
            "or matching names, in either a .xlsx or .csv file."
        )
    return best_index, best_fields


def _to_int(value: str | None) -> int | None:
    if not value:
        return None
    cleaned = value.replace(",", "").strip()
    try:
        return int(float(cleaned))
    except ValueError:
        return None


def parse_products_workbook(data: bytes, filename: str | None = None) -> list[dict]:
    """Returns a list of {"name", "description", "price", "cost_price",
    "stock_quantity", "image_url", "code", "action"} dicts, one per data row.
    "action" is "delete" or None. A row needs a Name AND a valid Price to be
    kept (except a delete row, which only needs a Code). Price/cost/stock
    cells are parsed loosely (commas, decimals tolerated); an unparseable
    Price drops the row (reported by the caller as skipped).

    Accepts .xlsx or .csv; the header row need not be the first row. Raises
    ValueError if the file can't be read or has no recognizable header row.
    """
    rows = _load_rows(data, filename)
    header_index, column_fields = _pick_header_row(rows)
    data_rows = rows[header_index + 1 :]

    items = []
    for row in data_rows:
        item: dict[str, str | None] = {
            "name": None, "description": None, "price": None, "cost_price": None,
            "stock": None, "image_url": None, "code": None, "action": None,
        }
        for field, value in zip(column_fields, row):
            if field is None or value is None:
                continue
            text = str(value).strip()
            if text:
                item[field] = text

        item["action"] = (
            "delete" if (item["action"] or "").strip().lower() in _DELETE_ACTION_VALUES else None
        )

        if item["action"] == "delete":
            if not item["code"]:
                continue  # a delete row needs a Code to know what to delete
            items.append({"name": None, "description": None, "price": None, "cost_price": None,
                          "stock_quantity": None, "image_url": None, "code": item["code"], "action": "delete"})
            continue

        price = _to_int(item["price"])
        if not item["name"] or price is None:
            continue  # a sellable row needs at least a name and a numeric price

        items.append({
            "name": item["name"],
            "description": item["description"] or "",
            "price": price,
            "cost_price": _to_int(item["cost_price"]),
            "stock_quantity": _to_int(item["stock"]),
            "image_url": item["image_url"] or None,
            "code": item["code"] or None,
            "action": None,
        })

    return items


def generate_sample_products_excel(lang: str = "en") -> bytes:
    """A ready-to-fill .xlsx for the product importer, headers in "en" or "fa"."""
    headers = SAMPLE_HEADERS_FA if lang == "fa" else SAMPLE_HEADERS_EN
    example = (
        ["نمونه محصول", "توضیح کوتاه محصول", "150000", "90000", "20", "", "SKU-1", ""]
        if lang == "fa"
        else ["Example product", "Short product description", "150000", "90000", "20", "", "SKU-1", ""]
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Products"
    ws.sheet_view.rightToLeft = lang == "fa"
    ws.append(headers)
    ws.append(example)

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
