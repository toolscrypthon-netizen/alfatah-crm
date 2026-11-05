from django import forms

from leads.models import Area, City

from .models import Listing


class ListingForm(forms.ModelForm):
    """Backs the step-by-step add-listing screen. Area is typed or picked by name and matched to the city's areas."""

    area_name = forms.CharField(required=False, max_length=150)

    class Meta:
        model = Listing
        fields = [
            "purpose", "property_type", "title", "description", "city", "location_text",
            "price", "size", "size_unit", "bedrooms", "bathrooms",
            "owner_name", "owner_phone", "on_website", "featured", "badge",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["city"].queryset = City.objects.filter(is_active=True)
        if self.instance.pk and self.instance.area:
            self.initial.setdefault("area_name", self.instance.area.name)
        self.features = list(self.instance.feature_list) if self.instance.pk else []

    def clean_price(self):
        price = self.cleaned_data.get("price")
        if price is not None and price < 0:
            raise forms.ValidationError("Price can't be negative.")
        return price

    def clean(self):
        cleaned = super().clean()
        name, city = (cleaned.get("area_name") or "").strip(), cleaned.get("city")
        cleaned["area"] = None
        if name and city:
            area = Area.objects.filter(city=city, name__iexact=name).first()
            if area:
                cleaned["area"] = area
            elif not cleaned.get("location_text"):
                # Not a known area: keep what they typed so nothing is lost.
                cleaned["location_text"] = name
            else:
                cleaned["location_text"] = f"{cleaned['location_text']}, {name}"
        return cleaned

    def save(self, commit=True, features=None):
        listing = super().save(commit=False)
        listing.area = self.cleaned_data.get("area")
        if features is not None:
            seen, clean = set(), []
            for item in features:
                item = item.strip()[:60]
                if item and item.lower() not in seen:
                    seen.add(item.lower())
                    clean.append(item)
            listing.features = "\n".join(clean)
        if commit:
            listing.save()
        return listing
