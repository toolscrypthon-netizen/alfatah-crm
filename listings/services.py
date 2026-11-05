import uuid
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db.models import Max
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import Listing, ListingPhoto

MAX_PHOTOS = 20
MAX_EDGE = 1600  # pixels; plenty for a website gallery and keeps each photo around 200-400 KB
MAX_UPLOAD_BYTES = 15 * 1024 * 1024

# Pillow refuses images bigger than this many pixels, which guards against decompression bombs.
Image.MAX_IMAGE_PIXELS = 60_000_000


def can_edit(user, listing):
    return user.can_manage or listing.created_by_id == user.id


def approve(listing, user, save=True):
    listing.approved_at, listing.approved_by = timezone.now(), user
    if save:
        listing.save(update_fields=["approved_at", "approved_by", "updated_at"])


def unapprove(listing, save=True):
    listing.approved_at, listing.approved_by = None, None
    if save:
        listing.save(update_fields=["approved_at", "approved_by", "updated_at"])


def visible_listings():
    return Listing.objects.select_related("city", "area", "created_by").prefetch_related("photos")


def process_image(upload):
    """Straighten, shrink and re-encode a phone photo as JPEG. Raises ValidationError if it isn't an image."""
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError(f"{upload.name} is too large.")
    try:
        img = Image.open(upload)
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValidationError(f"{upload.name} is not a photo we can read.") from exc
    img.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
    out = BytesIO()
    img.save(out, "JPEG", quality=82, optimize=True, progressive=True)
    return ContentFile(out.getvalue(), name=f"{uuid.uuid4().hex[:12]}.jpg")


def add_photos(listing, uploads):
    """Save photos after the ones the listing already has. Returns (added, errors)."""
    added, errors = 0, []
    position = (listing.photos.aggregate(m=Max("position"))["m"] or 0) + 1
    room = MAX_PHOTOS - listing.photos.count()
    for upload in uploads:
        if room <= 0:
            errors.append(f"Only {MAX_PHOTOS} photos fit on one listing.")
            break
        try:
            content = process_image(upload)
        except ValidationError as exc:
            errors.extend(exc.messages)
            continue
        ListingPhoto.objects.create(listing=listing, image=content, position=position)
        position += 1
        room -= 1
        added += 1
    return added, errors


def make_cover(photo):
    """Move a photo to the front; the rest keep their order behind it."""
    others = list(photo.listing.photos.exclude(pk=photo.pk))
    for index, item in enumerate([photo, *others]):
        if item.position != index:
            item.position = index
            item.save(update_fields=["position"])


def delete_photo(photo):
    photo.image.delete(save=False)
    photo.delete()
