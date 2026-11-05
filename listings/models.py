"""Properties the agency itself is marketing. Published ones appear on alfatah-marketing.com."""

from django.conf import settings
from django.db import models
from django.urls import reverse

from leads.models import Area, City, Lead, normalize_phone

# Ticked in one tap on the add-listing screen. Agents can type their own too.
COMMON_FEATURES = [
    "Corner", "Park facing", "Main road", "Possession ready", "All dues clear", "Gas available",
    "Near mosque", "Near school", "Basement", "Solar system", "Furnished", "Servant quarter",
    "Car porch", "Lawn", "Double storey", "Lift", "Generator backup", "Gated community",
]


class ListingQuerySet(models.QuerySet):
    def public(self):
        """What alfatah-marketing.com shows: approved by an admin, marked for the website, not sold."""
        return self.filter(on_website=True, status__in=Listing.LIVE_STATUSES, approved_at__isnull=False)

    def pending_approval(self):
        return self.filter(on_website=True, status__in=Listing.LIVE_STATUSES, approved_at__isnull=True)


class Listing(models.Model):
    class Purpose(models.TextChoices):
        SALE = "sale", "For sale"
        RENT = "rent", "For rent"

    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        UNDER_OFFER = "under_offer", "Under offer"
        SOLD = "sold", "Sold / rented out"
        WITHDRAWN = "withdrawn", "Withdrawn"

    # Statuses the public website shows. Sold and withdrawn listings drop off it automatically.
    LIVE_STATUSES = (Status.AVAILABLE, Status.UNDER_OFFER)

    PropertyType = Lead.PropertyType
    SizeUnit = Lead.SizeUnit

    purpose = models.CharField(max_length=10, choices=Purpose.choices, default=Purpose.SALE)
    property_type = models.CharField(max_length=20, choices=PropertyType.choices, default=PropertyType.HOUSE)
    title = models.CharField(max_length=150, blank=True, help_text="Leave empty to build one from the size and type.")
    description = models.TextField(blank=True)
    features = models.TextField(blank=True, help_text="One per line.")

    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="listings")
    area = models.ForeignKey(Area, on_delete=models.SET_NULL, null=True, blank=True, related_name="listings")
    location_text = models.CharField(
        "Location", max_length=200, blank=True, help_text="Block, street or an area that isn't in the list yet.",
    )

    price = models.BigIntegerField("Price (PKR)", null=True, blank=True, help_text="Monthly rent for rentals.")
    size = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    size_unit = models.CharField(max_length=10, choices=SizeUnit.choices, default=SizeUnit.MARLA)
    bedrooms = models.PositiveSmallIntegerField(null=True, blank=True)
    bathrooms = models.PositiveSmallIntegerField(null=True, blank=True)

    # Private: never sent to the website.
    owner_name = models.CharField(max_length=150, blank=True)
    owner_phone = models.CharField(max_length=30, blank=True)
    lead = models.ForeignKey(Lead, on_delete=models.SET_NULL, null=True, blank=True, related_name="listings")

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE, db_index=True)
    on_website = models.BooleanField("Show on website", default=True)
    featured = models.BooleanField(default=False, help_text="Highlighted on the website.")
    badge = models.CharField(max_length=30, blank=True, help_text='Short label on the photo, e.g. "Hot deal".')
    # Only admins can approve. A listing reaches the website only once approved.
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="listings"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ListingQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.display_title

    def get_absolute_url(self):
        return reverse("listing_detail", args=[self.pk])

    @property
    def ref(self):
        """Reference shown to customers, e.g. AF-3012. Continues after the website's old sample ids."""
        return f"AF-{3000 + self.pk}" if self.pk else ""

    @property
    def size_label(self):
        if self.size is None:
            return ""
        return f"{self.size.normalize():f} {self.get_size_unit_display()}"

    @property
    def type_label(self):
        return "Apartment" if self.property_type == self.PropertyType.FLAT else self.get_property_type_display()

    @property
    def display_title(self):
        if self.title:
            return self.title
        parts = []
        if self.property_type in (self.PropertyType.FLAT,) and self.bedrooms:
            parts.append(f"{self.bedrooms} Bed")
        elif self.size is not None:
            parts.append(self.size_label)
        parts.append(self.type_label)
        if self.property_type == self.PropertyType.PLOT:
            parts[-1] = "Residential Plot"
        return " ".join(parts) + (" for Rent" if self.purpose == self.Purpose.RENT else "")

    @property
    def location_label(self):
        place = self.area.name if self.area else self.location_text
        if self.area and self.location_text:
            place = f"{self.location_text}, {self.area.name}"
        return f"{place}, {self.city.name}" if place else self.city.name

    @property
    def feature_list(self):
        return [f.strip() for f in self.features.splitlines() if f.strip()]

    @property
    def is_approved(self):
        return self.approved_at is not None

    @property
    def is_public(self):
        """Photos and details may be shown publicly (the website feed uses the same rule)."""
        return self.on_website and self.status in self.LIVE_STATUSES and self.is_approved

    @property
    def is_live(self):
        return self.is_public and self.photos.exists()

    @property
    def awaiting_approval(self):
        return self.on_website and self.status in self.LIVE_STATUSES and not self.is_approved

    @property
    def cover(self):
        return self.photos.first()

    @property
    def owner_whatsapp_url(self):
        number = normalize_phone(self.owner_phone)
        if number.startswith("0"):
            number = "92" + number[1:]
        return f"https://wa.me/{number}" if number else ""


def photo_path(photo, filename):
    return f"listings/{photo.listing_id}/{filename}"


class ListingPhoto(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to=photo_path)
    position = models.PositiveIntegerField(default=0, help_text="The first photo is the cover.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return f"Photo {self.pk} of {self.listing}"

    def get_absolute_url(self):
        return reverse("listing_photo", args=[self.pk])
