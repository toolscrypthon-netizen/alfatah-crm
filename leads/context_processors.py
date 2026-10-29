from django.utils import timezone


def nav_counts(request):
    """Shows the overdue follow-up count in the top bar on every page."""
    if not request.user.is_authenticated:
        return {}
    overdue = request.user.follow_ups.filter(completed_at__isnull=True, due_at__lt=timezone.now()).count()
    return {"nav_overdue": overdue}
