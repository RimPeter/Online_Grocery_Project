import re
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


ALLERGENS = [
    # UK major allergens and common variants
    "milk", "wheat", "gluten", "egg", "eggs", "soy", "soya",
    "sesame", "peanut", "peanuts", "tree nuts", "almond", "hazelnut",
    "walnut", "cashew", "pistachio", "pecan", "brazil", "macadamia",
    "celery", "mustard", "fish", "crustaceans", "shellfish", "molluscs",
    "sulphites", "sulphur dioxide", "lupin", "barley", "rye", "oats",
]

ALLERGEN_REGEX = re.compile(r"\b(" + "|".join(map(re.escape, ALLERGENS)) + r")\b", re.IGNORECASE)


@register.filter(name="highlight_allergens")
def highlight_allergens(value: str):
    """
    Emphasize common allergen words by wrapping them in <strong class="allergen">.
    Escapes the input first to prevent HTML injection, then applies highlighting.
    Returns a SafeString suitable for further filters like linebreaksbr.
    """
    if not value:
        return ""
    safe = escape(value)

    def repl(m):
        word = m.group(0)
        return f"<strong class=\"allergen\">{word}</strong>"

    highlighted = ALLERGEN_REGEX.sub(repl, safe)
    return mark_safe(highlighted)


@register.filter(name="render_ingredients_nutrition")
def render_ingredients_nutrition(value: str) -> str:
    """
    Render a combined Ingredients/Nutrition text blob as structured HTML.
    - Ingredients shown as a block with allergens highlighted
    - Nutritional information shown as a table when detected

    Fallback: returns highlighted text with <br> line breaks if we cannot detect a table structure.
    """
    if not value:
        return ""

    # Normalize lines
    text = value.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if not lines:
        return ""

    # Find the start of the nutrition section
    nut_idx = None
    for i, ln in enumerate(lines):
        if "nutritional" in ln.lower():
            nut_idx = i
            break

    ing_lines = lines
    nut_lines = []
    if nut_idx is not None:
        ing_lines = lines[:nut_idx]
        nut_lines = lines[nut_idx + 1 :]

    # Build ingredients HTML
    ing_html = ""
    if ing_lines:
        ing_text = "\n".join(ing_lines)
        ing_html = f'<div class="pd-ingr">{highlight_allergens(ing_text)}</div>'

    # Attempt to parse nutrition table
    rows = []
    headers = []
    if nut_lines:
        tmp = list(nut_lines)
        # Collect up to 3 header descriptor lines (e.g., '100g contains', 'Each slice...', '% RI* per slice')
        while tmp and any(k in tmp[0].lower() for k in ["100g", "contains", "each", "slice", "serving", "ri"]):
            headers.append(tmp.pop(0))
            if len(headers) >= 3:
                break

        # Parse rows: name, per100g, perServing, optional RI%
        i = 0
        def is_value(s: str) -> bool:
            return any(ch.isdigit() for ch in s)
        while i < len(tmp):
            name = tmp[i]; i += 1
            if i >= len(tmp):
                break
            per100 = tmp[i] if is_value(tmp[i]) else ""
            if per100:
                i += 1
            per_serv = ""
            if i < len(tmp) and is_value(tmp[i]):
                per_serv = tmp[i]; i += 1
            ri = ""
            if i < len(tmp) and tmp[i].strip().endswith('%'):
                ri = tmp[i]; i += 1
            rows.append((name, per100, per_serv, ri))

    if rows:
        th1 = "Nutrient"
        th2 = headers[0] if len(headers) >= 1 else "Per 100g"
        th3 = headers[1] if len(headers) >= 2 else "Per serving"
        th4 = headers[2] if len(headers) >= 3 else "% RI per serving"
        # Build table HTML with escaped cell values
        parts = [
            '<table class="pd-nutrition-table">',
            "<thead><tr>",
            f"<th>{escape(th1)}</th>",
            f"<th>{escape(th2)}</th>",
            f"<th>{escape(th3)}</th>",
            f"<th>{escape(th4)}</th>",
            "</tr></thead>",
            "<tbody>",
        ]
        for name, v100, vserv, vri in rows:
            parts.append("<tr>")
            parts.append(f"<td>{escape(name)}</td>")
            parts.append(f"<td class=\"num\">{escape(v100)}</td>")
            parts.append(f"<td class=\"num\">{escape(vserv)}</td>")
            parts.append(f"<td class=\"num\">{escape(vri)}</td>")
            parts.append("</tr>")
        parts.append("</tbody></table>")
        table_html = "".join(parts)
        return mark_safe(ing_html + table_html)

    # Fallback: basic highlighted + line breaks
    fallback = highlight_allergens(text)
    # Replace newlines with <br>
    return mark_safe(str(fallback).replace("\n", "<br>"))
