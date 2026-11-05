import json
import mimetypes

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET, require_POST

from leads.models import Area, City, Lead, normalize_phone
from leads.services import visible_leads
from leads.templatetags.crm import pkr

from . import services
from .forms import ListingForm
from .models import COMMON_FEATURES, Listing, ListingPhoto


def _wants_json(request):
    return request.headers.get("X-Requested-With") == "fetch"


def _redirect_next(request, fallback):
    target = request.POST.get("next", "")
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return redirect(target)
    return redirect(fallback)


def _get_listing(request, pk, edit=False):
    listing = get_object_or_404(services.visible_listings(), pk=pk)
    if edit and not services.can_edit(request.user, listing):
        raise PermissionDenied
    return listing


@login_required
def listing_list(request):
    qs = services.visible_listings()
    f = {k: request.GET.get(k, "").strip() for k in ("q", "status", "purpose", "type", "mine")}
    if f["q"]:
        qs = qs.filter(
            Q(title__icontains=f["q"]) | Q(location_text__icontains=f["q"]) | Q(area__name__icontains=f["q"])
            | Q(description__icontains=f["q"]) | Q(owner_name__icontains=f["q"]) | Q(owner_phone__icontains=f["q"])
        )
    if f["status"] == "live":
        qs = qs.filter(status__in=Listing.LIVE_STATUSES)
    elif f["status"] == "pending":
        qs = qs.pending_approval()
    elif f["status"]:
        qs = qs.filter(status=f["status"])
    if f["purpose"]:
        qs = qs.filter(purpose=f["purpose"])
    if f["type"]:
        qs = qs.filter(property_type=f["type"])
    if f["mine"]:
        qs = qs.filter(created_by=request.user)
    return render(request, "listings/listing_list.html", {
        "listings": qs[:200], "filters": f, "Listing": Listing,
        "pending_count": Listing.objects.pending_approval().count() if request.user.is_admin else 0,
    })


def _wizard_context(form, listing=None):
    city_areas = {
        str(c.pk): list(Area.objects.filter(city=c).order_by("name").values_list("name", flat=True))
        for c in City.objects.filter(is_active=True)
    }
    chosen = form.features if hasattr(form, "features") else []
    extra = [f for f in chosen if f not in COMMON_FEATURES]
    return {
        "form": form,
        "listing": listing,
        "cities": City.objects.filter(is_active=True),
        "city_areas": city_areas,
        "common_features": COMMON_FEATURES,
        "chosen_features": chosen,
        "extra_features": extra,
        "max_photos": services.MAX_PHOTOS,
        "Listing": Listing,
    }


def _save_from_request(request, form, is_new):
    listing = form.save(commit=False, features=request.POST.getlist("feature"))
    if is_new:
        listing.created_by = request.user
        lead_id = request.POST.get("lead", "")
        if lead_id.isdigit():
            listing.lead = visible_leads(request.user).filter(pk=lead_id).first()
    if listing.lead is None and listing.owner_phone:
        # Same owner as a seller/landlord lead we already have: link them so both pages show it.
        listing.lead = (
            Lead.objects.filter(phone_normalized=normalize_phone(listing.owner_phone),
                                intent__in=[Lead.Intent.SELLING, Lead.Intent.RENT_OUT])
            .order_by("-created_at").first()
        )
    was_approved = listing.is_approved
    if request.user.is_admin:
        if is_new:
            services.approve(listing, request.user, save=False)
    elif not is_new and form.has_changed():
        services.unapprove(listing, save=False)
    listing.save()
    added, errors = services.add_photos(listing, request.FILES.getlist("photos"))
    if added and not is_new and not request.user.is_admin:
        services.unapprove(listing)
    for error in errors:
        messages.warning(request, error)
    if is_new:
        if listing.is_live:
            messages.success(request, f"Listing {listing.ref} saved and it's now on the website.")
        elif listing.on_website and not listing.photos.exists():
            messages.warning(request, f"Listing {listing.ref} saved. Add a photo to put it on the website.")
        elif listing.awaiting_approval:
            messages.success(request, f"Listing {listing.ref} saved. It goes on the website once an admin approves it.")
        else:
            messages.success(request, f"Listing {listing.ref} saved.")
    else:
        note = " It will go back on the website once an admin approves the changes." if (
            was_approved and not listing.is_approved and listing.on_website) else ""
        messages.success(request, "Listing updated." + (f" {added} photo(s) added." if added else "") + note)
    return listing


def _form_response(request, form, template_context, status=200):
    if _wants_json(request):
        return JsonResponse({"ok": False, "errors": form.errors.get_json_data()}, status=400)
    return render(request, "listings/listing_form.html", template_context, status=status)


@login_required
def listing_create(request):
    if request.method == "POST":
        form = ListingForm(request.POST)
        if form.is_valid():
            listing = _save_from_request(request, form, is_new=True)
            if _wants_json(request):
                return JsonResponse({"ok": True, "url": listing.get_absolute_url()})
            return redirect(listing)
        return _form_response(request, form, _wizard_context(form), status=400)

    # No type picked yet, so the first tap chooses it and moves on.
    initial = {"city": City.objects.filter(is_active=True).first(), "on_website": True, "property_type": None}
    lead = None
    lead_id = request.GET.get("lead", "")
    if lead_id.isdigit():
        lead = visible_leads(request.user).filter(pk=lead_id).first()
    if lead:
        initial.update({
            "purpose": Listing.Purpose.RENT if lead.intent == Lead.Intent.RENT_OUT else Listing.Purpose.SALE,
            "property_type": lead.property_type, "city": lead.city, "price": lead.price,
            "size": lead.size, "size_unit": lead.size_unit, "bedrooms": lead.bedrooms,
            "owner_name": lead.contact_name, "owner_phone": lead.phone, "description": lead.description,
            "area_name": lead.area.name if lead.area else "", "location_text": "" if lead.area else lead.area_text,
        })
    form = ListingForm(initial=initial)
    context = _wizard_context(form)
    context["from_lead"] = lead
    return render(request, "listings/listing_form.html", context)


@login_required
def listing_edit(request, pk):
    listing = _get_listing(request, pk, edit=True)
    if request.method == "POST":
        form = ListingForm(request.POST, instance=listing)
        if form.is_valid():
            listing = _save_from_request(request, form, is_new=False)
            if _wants_json(request):
                return JsonResponse({"ok": True, "url": listing.get_absolute_url()})
            return redirect(listing)
        return _form_response(request, form, _wizard_context(form, listing), status=400)
    return render(request, "listings/listing_form.html", _wizard_context(ListingForm(instance=listing), listing))


@login_required
def listing_detail(request, pk):
    listing = _get_listing(request, pk)
    share_lines = [f"*{listing.display_title}*", listing.location_label]
    if listing.price:
        share_lines.append(f"Price: Rs {pkr(listing.price)}" + (" / month" if listing.purpose == Listing.Purpose.RENT else ""))
    if listing.size_label:
        share_lines.append(f"Size: {listing.size_label}")
    if listing.bedrooms:
        share_lines.append(f"{listing.bedrooms} bed" + (f", {listing.bathrooms} bath" if listing.bathrooms else ""))
    share_lines += listing.feature_list[:6]
    share_lines.append(f"Ref {listing.ref}")
    return render(request, "listings/listing_detail.html", {
        "listing": listing,
        "photos": listing.photos.all(),
        "can_edit": services.can_edit(request.user, listing),
        "share_text": "\n".join(share_lines),
        "Listing": Listing,
        "max_photos": services.MAX_PHOTOS,
    })


@login_required
@require_POST
def listing_update_status(request, pk):
    listing = _get_listing(request, pk, edit=True)
    status = request.POST.get("status")
    if status in Listing.Status.values:
        listing.status = status
        listing.save(update_fields=["status", "updated_at"])
        note = "" if status in Listing.LIVE_STATUSES else " It no longer shows on the website."
        messages.success(request, f"Marked as {listing.get_status_display().lower()}.{note}")
    if "on_website" in request.POST:
        listing.on_website = request.POST["on_website"] == "1"
        listing.save(update_fields=["on_website", "updated_at"])
        messages.success(request, "Shown on the website." if listing.on_website else "Hidden from the website.")
    return redirect(listing)


@login_required
@require_POST
def listing_approve(request, pk):
    if not request.user.is_admin:
        raise PermissionDenied
    listing = _get_listing(request, pk)
    if request.POST.get("approve") == "0":
        services.unapprove(listing)
        messages.success(request, "Approval removed. It's off the website.")
    else:
        services.approve(listing, request.user)
        if listing.is_live:
            messages.success(request, "Approved. It's on the website now.")
        elif not listing.photos.exists():
            messages.success(request, "Approved. It will show on the website once it has a photo.")
        else:
            messages.success(request, "Approved.")
    return _redirect_next(request, listing)


@login_required
@require_POST
def listing_delete(request, pk):
    listing = _get_listing(request, pk, edit=True)
    for photo in listing.photos.all():
        services.delete_photo(photo)
    listing.delete()
    messages.success(request, "Listing deleted.")
    return redirect("listing_list")


@login_required
@require_POST
def photo_add(request, pk):
    listing = _get_listing(request, pk, edit=True)
    added, errors = services.add_photos(listing, request.FILES.getlist("photos"))
    for error in errors:
        messages.warning(request, error)
    if added:
        note = ""
        if not request.user.is_admin and listing.is_approved:
            services.unapprove(listing)
            note = " An admin needs to approve the new photos before they show on the website."
        messages.success(request, f"{added} photo(s) added.{note}")
    if _wants_json(request):
        return JsonResponse({"ok": True, "url": listing.get_absolute_url()})
    return redirect(listing)


def _get_photo_for_edit(request, photo_pk):
    photo = get_object_or_404(ListingPhoto.objects.select_related("listing"), pk=photo_pk)
    if not services.can_edit(request.user, photo.listing):
        raise PermissionDenied
    return photo


@login_required
@require_POST
def photo_cover(request, photo_pk):
    photo = _get_photo_for_edit(request, photo_pk)
    services.make_cover(photo)
    messages.success(request, "Cover photo changed.")
    return redirect(photo.listing)


@login_required
@require_POST
def photo_delete(request, photo_pk):
    photo = _get_photo_for_edit(request, photo_pk)
    listing = photo.listing
    services.delete_photo(photo)
    messages.success(request, "Photo removed.")
    return redirect(listing)


@require_GET
def photo(request, photo_pk):
    """Serves a listing photo. Photos of listings on the website are public; the rest need a login."""
    photo = get_object_or_404(ListingPhoto.objects.select_related("listing"), pk=photo_pk)
    listing = photo.listing
    public = listing.is_public
    if not public and not request.user.is_authenticated:
        raise Http404
    try:
        handle = photo.image.open("rb")
    except FileNotFoundError:
        raise Http404
    response = FileResponse(handle, content_type=mimetypes.guess_type(photo.image.name)[0] or "image/jpeg")
    response["Cache-Control"] = "public, max-age=86400" if public else "private, max-age=3600"
    return response


# ---------- Public feed for alfatah-marketing.com ----------

WEBSITE_TYPES = {
    Listing.PropertyType.HOUSE: "house", Listing.PropertyType.FLAT: "apartment",
    Listing.PropertyType.PLOT: "plot", Listing.PropertyType.COMMERCIAL: "commercial",
    Listing.PropertyType.FARMHOUSE: "house", Listing.PropertyType.OTHER: "house",
}


def _escape(text):
    """The website inserts these strings as HTML, so escape them here."""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def website_items(request):
    qs = (
        Listing.objects.public().filter(photos__isnull=False)
        .distinct().select_related("city", "area").prefetch_related("photos")
        .order_by("-featured", "-created_at")
    )
    items = []
    for listing in qs:
        photos = [request.build_absolute_uri(p.get_absolute_url()) for p in listing.photos.all()]
        badge = listing.badge
        if listing.status == Listing.Status.UNDER_OFFER:
            badge = "Under offer"
        elif not badge and listing.purpose == Listing.Purpose.RENT:
            badge = "For rent"
        item = {
            "id": listing.ref,
            "title": _escape(listing.display_title),
            "location": _escape(listing.location_label),
            "type": WEBSITE_TYPES.get(listing.property_type, "house"),
            "purpose": listing.purpose,
            "price": listing.price or 0,
            "img": photos[0],
            "imgs": photos,
            "desc": _escape(listing.description),
            "features": [_escape(f) for f in listing.feature_list],
            "hot": listing.featured,
        }
        if badge:
            item["badge"] = _escape(badge)
        if listing.bedrooms:
            item["beds"] = listing.bedrooms
        if listing.bathrooms:
            item["baths"] = listing.bathrooms
        if listing.size is not None:
            size = float(listing.size)
            if listing.size_unit == Listing.SizeUnit.KANAL:
                item["marla"] = round(size * 20, 2)
            elif listing.size_unit == Listing.SizeUnit.MARLA:
                item["marla"] = size
            else:
                item["sqft"] = size
        items.append(item)
    return items


@require_GET
@cache_control(public=True, max_age=60)
def website_feed_js(request):
    """Loaded by the website after its own listings.js. Replaces the sample listings once real ones exist."""
    data = json.dumps(website_items(request), ensure_ascii=False).replace("</", "<\\/")
    body = (
        "/* Live listings from the Alfatah CRM. */\n"
        f"(function () {{ var live = {data};\n"
        "  if (live.length) window.LISTINGS = live; })();\n"
    )
    return HttpResponse(body, content_type="application/javascript; charset=utf-8")


@require_GET
@cache_control(public=True, max_age=60)
def website_feed_json(request):
    response = JsonResponse({"listings": website_items(request)})
    response["Access-Control-Allow-Origin"] = "*"
    return response
