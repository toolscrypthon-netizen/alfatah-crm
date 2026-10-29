"""Endpoint the lead collectors (OLX first, Facebook later) use to push leads into the CRM."""

import hmac
import json
import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Activity, Area, City, Lead

log = logging.getLogger(__name__)

TEXT_FIELDS = ("title", "description", "area_text", "contact_name", "phone", "source_url", "external_id")
CHOICE_FIELDS = {
    "intent": Lead.Intent, "property_type": Lead.PropertyType, "source": Lead.Source, "size_unit": Lead.SizeUnit,
}
MAX_BATCH = 200


def _authorized(request):
    token = settings.INGEST_API_TOKEN
    supplied = request.headers.get("X-Api-Token", "")
    return bool(token) and hmac.compare_digest(token, supplied)


def _build_lead(item):
    """Turn one JSON item into an unsaved Lead, or raise ValueError with the reason."""
    city = City.objects.filter(slug=item.get("city", "")).first()
    if city is None:
        raise ValueError(f"unknown city {item.get('city')!r}")
    lead = Lead(city=city)
    for field in TEXT_FIELDS:
        value = item.get(field)
        if value is not None:
            max_length = Lead._meta.get_field(field).max_length
            setattr(lead, field, str(value).strip()[:max_length] if max_length else str(value).strip())
    for field, choices in CHOICE_FIELDS.items():
        value = item.get(field)
        if value is not None:
            if value not in choices.values:
                raise ValueError(f"{field} must be one of {', '.join(choices.values)}")
            setattr(lead, field, value)
    if not lead.title:
        raise ValueError("title is required")
    if "intent" not in item:
        raise ValueError("intent is required")
    for field in ("price", "bedrooms"):
        if item.get(field) not in (None, ""):
            setattr(lead, field, int(item[field]))
    if item.get("size") not in (None, ""):
        lead.size = round(float(item["size"]), 2)
    if item.get("posted_at"):
        lead.posted_at = parse_datetime(item["posted_at"])
    if lead.area_text:
        # Match the posted location against known areas, e.g. "DHA Phase 6, Lahore" -> DHA Phase 6.
        text = lead.area_text.lower()
        for area in sorted(Area.objects.filter(city=city), key=lambda a: -len(a.name)):
            if area.name.lower() in text:
                lead.area = area
                break
    return lead


@csrf_exempt
@require_POST
def ingest(request):
    """Accepts {"leads": [...]} and returns how many were created, skipped as duplicates, or rejected."""
    if not _authorized(request):
        return JsonResponse({"error": "invalid or missing X-Api-Token"}, status=401)
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "body must be JSON"}, status=400)
    items = payload.get("leads") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return JsonResponse({"error": 'expected {"leads": [...]}'}, status=400)
    if len(items) > MAX_BATCH:
        return JsonResponse({"error": f"at most {MAX_BATCH} leads per request"}, status=400)

    created, duplicates, errors = [], 0, []
    for index, item in enumerate(items):
        try:
            lead = _build_lead(item)
        except (ValueError, TypeError) as exc:
            errors.append({"index": index, "error": str(exc)})
            continue
        if lead.external_id and Lead.objects.filter(source=lead.source, external_id=lead.external_id).exists():
            duplicates += 1
            continue
        try:
            with transaction.atomic():
                lead.save()
        except IntegrityError:
            duplicates += 1
            continue
        Activity.objects.create(
            lead=lead, kind=Activity.Kind.SYSTEM, body=f"Collected automatically from {lead.get_source_display()}"
        )
        created.append(lead.pk)
    log.info("ingest: %d created, %d duplicates, %d errors", len(created), duplicates, len(errors))
    return JsonResponse({"created": len(created), "duplicates": duplicates, "errors": errors, "ids": created})
