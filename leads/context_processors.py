from django.utils import timezone


def nav_counts(request):
    """Shows the overdue follow-up count in the top bar on every page."""
    if not request.user.is_authenticated:
        return {}
    overdue = request.user.follow_ups.filter(completed_at__isnull=True, due_at__lt=timezone.now()).count()
    counts = {"nav_overdue": overdue}
    if request.user.is_admin:
        from listings.models import Listing

        counts["nav_pending_listings"] = Listing.objects.pending_approval().count()
    return counts
