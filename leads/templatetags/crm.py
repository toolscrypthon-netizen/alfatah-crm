from django import template

register = template.Library()


@register.filter
def pkr(value):
    """Formats rupees the way agents say them: 2.5 Crore, 85 Lakh, 45,000."""
    if value in (None, ""):
        return ""
    value = int(value)
    if value >= 10_000_000:
        return f"{value / 10_000_000:.2f}".rstrip("0").rstrip(".") + " Crore"
    if value >= 100_000:
        return f"{value / 100_000:.2f}".rstrip("0").rstrip(".") + " Lakh"
    return f"{value:,}"


@register.filter
def size_display(lead):
    if lead.size is None:
        return ""
    return f"{lead.size.normalize():f} {lead.get_size_unit_display()}"
