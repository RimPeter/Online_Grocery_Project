from django import template


register = template.Library()


@register.filter
def with_error_attrs(bound_field, error_id):
    """Render a bound field with its visible validation error associated."""
    if not bound_field.errors:
        return bound_field.as_widget()

    described_by = []
    existing_description = bound_field.field.widget.attrs.get("aria-describedby", "")
    described_by.extend(existing_description.split())

    if bound_field.field.help_text and bound_field.auto_id:
        described_by.append(f"{bound_field.auto_id}_helptext")

    described_by.append(error_id)
    described_by = list(dict.fromkeys(described_by))

    return bound_field.as_widget(
        attrs={
            "aria-invalid": "true",
            "aria-describedby": " ".join(described_by),
            "aria-errormessage": error_id,
        }
    )
