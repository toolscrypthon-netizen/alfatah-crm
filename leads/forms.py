from django import forms
from django.contrib.auth import get_user_model

from .models import Activity, Area, City, Lead

User = get_user_model()

DATETIME_WIDGET = forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M")


class BootstrapMixin:
    """Adds Bootstrap classes to every widget so templates can render fields as they are."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                css = "form-check-input"
            elif isinstance(widget, forms.Select):
                css = "form-select"
            else:
                css = "form-control"
            widget.attrs["class"] = (widget.attrs.get("class", "") + " " + css).strip()


def active_users():
    return User.objects.filter(is_active=True).order_by("first_name", "username")


class LeadForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Lead
        fields = [
            "intent", "property_type", "title", "description",
            "city", "area", "area_text", "price", "size", "size_unit", "bedrooms",
            "contact_name", "phone", "alt_phone",
            "source", "source_url", "priority", "assigned_to",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["city"].queryset = City.objects.filter(is_active=True)
        self.fields["area"].queryset = Area.objects.select_related("city")
        self.fields["assigned_to"].queryset = active_users()
        if user is not None and not user.can_manage:
            # Agents can't hand leads to other people; new leads they add are theirs.
            del self.fields["assigned_to"]

    def clean(self):
        cleaned = super().clean()
        area, city = cleaned.get("area"), cleaned.get("city")
        if area and city and area.city_id != city.id:
            self.add_error("area", f"{area.name} is not in {city.name}.")
        return cleaned


class ActivityForm(BootstrapMixin, forms.Form):
    """Log a call, message, visit or comment, and optionally move the lead forward in one go."""

    kind = forms.ChoiceField(
        choices=[(k, Activity.Kind(k).label) for k in (
            Activity.Kind.CALL, Activity.Kind.WHATSAPP, Activity.Kind.MEETING, Activity.Kind.COMMENT
        )],
        initial=Activity.Kind.CALL,
    )
    outcome = forms.ChoiceField(choices=[("", "-")] + list(Activity.CallOutcome.choices), required=False)
    body = forms.CharField(
        label="Notes", required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "What did they say? Budget, timeline, objections..."}),
    )
    new_status = forms.ChoiceField(
        label="Change status to", choices=[("", "Keep current status")] + list(Lead.Status.choices), required=False
    )
    follow_up_at = forms.DateTimeField(label="Schedule follow-up", widget=DATETIME_WIDGET, required=False)
    follow_up_note = forms.CharField(label="Follow-up note", max_length=255, required=False)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("kind") == Activity.Kind.COMMENT and not cleaned.get("body"):
            self.add_error("body", "Write a comment.")
        return cleaned


class PipelineForm(BootstrapMixin, forms.Form):
    status = forms.ChoiceField(choices=Lead.Status.choices)
    priority = forms.TypedChoiceField(choices=Lead.Priority.choices, coerce=int)
    assigned_to = forms.ModelChoiceField(queryset=User.objects.none(), required=False, empty_label="Unassigned")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = active_users()


class FollowUpForm(BootstrapMixin, forms.Form):
    due_at = forms.DateTimeField(label="When", widget=DATETIME_WIDGET)
    note = forms.CharField(
        max_length=255, required=False, widget=forms.TextInput(attrs={"placeholder": "What to do, e.g. send photos"})
    )
    assigned_to = forms.ModelChoiceField(queryset=User.objects.none(), required=False, empty_label="Me")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = active_users()


class BulkAssignForm(BootstrapMixin, forms.Form):
    lead_ids = forms.CharField()
    assigned_to = forms.ModelChoiceField(queryset=User.objects.none(), required=False, empty_label="Unassigned")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = active_users()

    def clean_lead_ids(self):
        try:
            return [int(x) for x in self.cleaned_data["lead_ids"].split(",") if x.strip()]
        except ValueError:
            raise forms.ValidationError("Invalid selection.")
