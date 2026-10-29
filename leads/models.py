import re

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class City(models.Model):
    """A city the CRM collects leads for. New cities are added here as the business expands."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True, help_text="Collectors only gather leads for active cities.")

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "cities"

    def __str__(self):
        return self.name


class Area(models.Model):
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name="areas")
    name = models.CharField(max_length=150)

    class Meta:
        ordering = ["city__name", "name"]
        unique_together = [("city", "name")]

    def __str__(self):
        return f"{self.name}, {self.city}"


def normalize_phone(value):
    """Reduce a Pakistani phone number to 03XXXXXXXXX so duplicates can be matched."""
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("0092"):
        digits = digits[4:]
    elif digits.startswith("92"):
        digits = digits[2:]
    if len(digits) == 10 and digits.startswith("3"):
        digits = "0" + digits
    return digits


class Lead(models.Model):
    class Intent(models.TextChoices):
        SELLING = "selling", "Selling"
        BUYING = "buying", "Looking to buy"
        RENT_OUT = "rent_out", "Renting out"
        RENT_WANTED = "rent_wanted", "Looking to rent"

    class PropertyType(models.TextChoices):
        HOUSE = "house", "House"
        FLAT = "flat", "Flat / Apartment"
        PLOT = "plot", "Plot"
        COMMERCIAL = "commercial", "Commercial"
        FARMHOUSE = "farmhouse", "Farmhouse"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        INTERESTED = "interested", "Interested"
        FOLLOW_UP = "follow_up", "Follow-up"
        NEGOTIATING = "negotiating", "Negotiating"
        WON = "won", "Closed - won"
        LOST = "lost", "Closed - lost"
        NOT_INTERESTED = "not_interested", "Not interested"
        INVALID = "invalid", "Invalid / spam"

    CLOSED_STATUSES = (Status.WON, Status.LOST, Status.NOT_INTERESTED, Status.INVALID)

    class Source(models.TextChoices):
        OLX = "olx", "OLX"
        FACEBOOK = "facebook", "Facebook"
        ZAMEEN = "zameen", "Zameen"
        WHATSAPP = "whatsapp", "WhatsApp"
        REFERRAL = "referral", "Referral"
        WALK_IN = "walk_in", "Walk-in / call"
        MANUAL = "manual", "Other"

    class Priority(models.IntegerChoices):
        LOW = 1, "Low"
        NORMAL = 2, "Normal"
        HIGH = 3, "High"

    class SizeUnit(models.TextChoices):
        MARLA = "marla", "Marla"
        KANAL = "kanal", "Kanal"
        SQFT = "sqft", "Sq. ft"

    # What the lead wants
    intent = models.CharField(max_length=20, choices=Intent.choices)
    property_type = models.CharField(max_length=20, choices=PropertyType.choices, default=PropertyType.HOUSE)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="leads")
    area = models.ForeignKey(Area, on_delete=models.SET_NULL, null=True, blank=True, related_name="leads")
    area_text = models.CharField(
        "Location (as posted)", max_length=255, blank=True,
        help_text="Free-text location from the original post, kept when it doesn't match a known area.",
    )
    price = models.BigIntegerField("Price (PKR)", null=True, blank=True, help_text="Asking price, or budget for buyers.")
    size = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    size_unit = models.CharField(max_length=10, choices=SizeUnit.choices, default=SizeUnit.MARLA)
    bedrooms = models.PositiveSmallIntegerField(null=True, blank=True)

    # Who posted it
    contact_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    phone_normalized = models.CharField(max_length=20, blank=True, db_index=True, editable=False)
    alt_phone = models.CharField(max_length=30, blank=True)

    # Where it came from
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    source_url = models.URLField(max_length=500, blank=True)
    external_id = models.CharField(
        max_length=100, blank=True,
        help_text="The listing or post id on the source site, used to skip duplicates.",
    )
    posted_at = models.DateTimeField(null=True, blank=True, help_text="When it was posted on the source site.")

    # Pipeline
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW, db_index=True)
    priority = models.IntegerField(choices=Priority.choices, default=Priority.NORMAL)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_leads"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_leads"
    )
    next_follow_up = models.DateTimeField(null=True, blank=True, db_index=True, editable=False)
    last_contacted_at = models.DateTimeField(null=True, blank=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "external_id"],
                condition=~models.Q(external_id=""),
                name="unique_external_listing",
            )
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.phone_normalized = normalize_phone(self.phone)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("lead_detail", args=[self.pk])

    @property
    def is_closed(self):
        return self.status in self.CLOSED_STATUSES

    @property
    def whatsapp_url(self):
        number = self.phone_normalized
        if number.startswith("0"):
            number = "92" + number[1:]
        return f"https://wa.me/{number}" if number else ""

    @property
    def follow_up_overdue(self):
        return bool(self.next_follow_up and self.next_follow_up < timezone.now())

    def duplicates(self):
        """Other leads with the same phone number, which usually means the same person."""
        if not self.phone_normalized:
            return Lead.objects.none()
        return Lead.objects.filter(phone_normalized=self.phone_normalized).exclude(pk=self.pk)

    def refresh_follow_up(self):
        upcoming = self.follow_ups.filter(completed_at__isnull=True).order_by("due_at").first()
        self.next_follow_up = upcoming.due_at if upcoming else None
        Lead.objects.filter(pk=self.pk).update(next_follow_up=self.next_follow_up)


class Activity(models.Model):
    """One entry on a lead's timeline: a call, a comment, or a change someone made."""

    class Kind(models.TextChoices):
        CALL = "call", "Call"
        WHATSAPP = "whatsapp", "WhatsApp"
        MEETING = "meeting", "Meeting / visit"
        COMMENT = "comment", "Comment"
        STATUS = "status", "Status change"
        ASSIGNMENT = "assignment", "Assignment"
        FOLLOW_UP = "follow_up", "Follow-up"
        SYSTEM = "system", "System"

    CONTACT_KINDS = (Kind.CALL, Kind.WHATSAPP, Kind.MEETING)

    class CallOutcome(models.TextChoices):
        ANSWERED = "answered", "Answered"
        NO_ANSWER = "no_answer", "No answer"
        BUSY = "busy", "Busy"
        SWITCHED_OFF = "switched_off", "Switched off"
        WRONG_NUMBER = "wrong_number", "Wrong number"
        CALL_BACK = "call_back", "Asked to call back"

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="activities")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    outcome = models.CharField(max_length=20, choices=CallOutcome.choices, blank=True)
    body = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "activities"

    def __str__(self):
        return f"{self.get_kind_display()} on {self.lead}"


class FollowUp(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="follow_ups")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="follow_ups"
    )
    due_at = models.DateTimeField()
    note = models.CharField(max_length=255, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_at"]

    def __str__(self):
        return f"Follow up {self.lead} at {self.due_at:%Y-%m-%d %H:%M}"

    @property
    def is_overdue(self):
        return self.completed_at is None and self.due_at < timezone.now()
