import csv
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import services
from .forms import ActivityForm, BulkAssignForm, FollowUpForm, LeadForm, PipelineForm
from .models import Activity, Area, City, FollowUp, Lead

User = get_user_model()


def _redirect_back(request, fallback):
    target = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return redirect(target)
    return redirect(fallback)


def _manager_required(user):
    if not user.can_manage:
        raise PermissionDenied


@login_required
def dashboard(request):
    user = request.user
    now = timezone.now()
    today_start = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
    leads = services.visible_leads(user)
    my_follow_ups = FollowUp.objects.filter(assigned_to=user, completed_at__isnull=True).select_related("lead")
    open_leads = leads.exclude(status__in=Lead.CLOSED_STATUSES)

    context = {
        "new_today": leads.filter(created_at__gte=today_start).count(),
        "unassigned": open_leads.filter(assigned_to__isnull=True).count(),
        "my_open": open_leads.filter(assigned_to=user).count(),
        "won_30d": leads.filter(status=Lead.Status.WON, updated_at__gte=now - timedelta(days=30)).count(),
        "overdue": my_follow_ups.filter(due_at__lt=now)[:20],
        "due_today": my_follow_ups.filter(due_at__gte=now, due_at__lt=today_start + timedelta(days=1)),
        "by_status": leads.values("status").annotate(n=Count("id")).order_by("status"),
        "by_source": leads.values("source").annotate(n=Count("id")).order_by("-n"),
        "recent": leads.order_by("-created_at")[:10],
    }
    status_labels, source_labels = dict(Lead.Status.choices), dict(Lead.Source.choices)
    for row in context["by_status"]:
        row["label"] = status_labels.get(row["status"], row["status"])
    for row in context["by_source"]:
        row["label"] = source_labels.get(row["source"], row["source"])
    if user.can_manage:
        context["team"] = (
            User.objects.filter(is_active=True)
            .annotate(
                open_count=Count("assigned_leads", filter=~Q(assigned_leads__status__in=Lead.CLOSED_STATUSES)),
                won_count=Count("assigned_leads", filter=Q(assigned_leads__status=Lead.Status.WON)),
                overdue_count=Count(
                    "follow_ups", filter=Q(follow_ups__completed_at__isnull=True, follow_ups__due_at__lt=now),
                    distinct=True,
                ),
            )
            .order_by("first_name", "username")
        )
    return render(request, "leads/dashboard.html", context)


def _filtered_leads(request):
    """Apply the filter bar on the lead list. Returns the queryset and the active filter values."""
    qs = services.visible_leads(request.user)
    f = {k: request.GET.get(k, "").strip() for k in (
        "q", "intent", "property_type", "status", "source", "city", "area",
        "assigned", "price_min", "price_max", "stage", "sort",
    )}
    if f["q"]:
        q = f["q"]
        qs = qs.filter(
            Q(title__icontains=q) | Q(description__icontains=q) | Q(contact_name__icontains=q)
            | Q(phone__icontains=q) | Q(area_text__icontains=q) | Q(area__name__icontains=q)
        )
    for field in ("intent", "property_type", "status", "source"):
        if f[field]:
            qs = qs.filter(**{field: f[field]})
    if f["city"]:
        qs = qs.filter(city__slug=f["city"])
    if f["area"].isdigit():
        qs = qs.filter(area_id=f["area"])
    if f["assigned"] == "me":
        qs = qs.filter(assigned_to=request.user)
    elif f["assigned"] == "none":
        qs = qs.filter(assigned_to__isnull=True)
    elif f["assigned"].isdigit():
        qs = qs.filter(assigned_to_id=f["assigned"])
    if f["price_min"].isdigit():
        qs = qs.filter(price__gte=int(f["price_min"]))
    if f["price_max"].isdigit():
        qs = qs.filter(price__lte=int(f["price_max"]))
    if f["stage"] == "closed":
        qs = qs.filter(status__in=Lead.CLOSED_STATUSES)
    elif f["stage"] != "all":
        qs = qs.exclude(status__in=Lead.CLOSED_STATUSES)
    ordering = {
        "oldest": "created_at", "price": "price", "-price": "-price",
        "follow_up": "next_follow_up", "priority": "-priority",
    }.get(f["sort"], "-created_at")
    return qs.order_by(ordering, "-id"), f


@login_required
def lead_list(request):
    qs, filters = _filtered_leads(request)
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render(request, "leads/lead_list.html", {
        "page": page,
        "filters": filters,
        "querystring": query.urlencode(),
        "cities": City.objects.filter(is_active=True),
        "areas": Area.objects.filter(city__slug=filters["city"]) if filters["city"] else Area.objects.none(),
        "users": User.objects.filter(is_active=True).order_by("first_name", "username"),
        "Lead": Lead,
        "bulk_form": BulkAssignForm() if request.user.can_manage else None,
    })


@login_required
def lead_export(request):
    _manager_required(request.user)
    qs, _ = _filtered_leads(request)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="leads-{timezone.localdate():%Y-%m-%d}.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "ID", "Created", "Intent", "Type", "Title", "City", "Area", "Price", "Size", "Unit",
        "Contact", "Phone", "Source", "Source URL", "Status", "Assigned to", "Next follow-up",
    ])
    for lead in qs.iterator():
        writer.writerow([
            lead.pk, timezone.localtime(lead.created_at).strftime("%Y-%m-%d %H:%M"),
            lead.get_intent_display(), lead.get_property_type_display(), lead.title, lead.city,
            lead.area.name if lead.area else lead.area_text, lead.price or "", lead.size or "",
            lead.get_size_unit_display(), lead.contact_name, lead.phone, lead.get_source_display(),
            lead.source_url, lead.get_status_display(), lead.assigned_to or "",
            timezone.localtime(lead.next_follow_up).strftime("%Y-%m-%d %H:%M") if lead.next_follow_up else "",
        ])
    return response


@login_required
@require_POST
def lead_bulk_assign(request):
    _manager_required(request.user)
    form = BulkAssignForm(request.POST)
    if form.is_valid():
        assignee = form.cleaned_data["assigned_to"]
        changed = sum(
            services.assign(lead, assignee, request.user)
            for lead in Lead.objects.filter(pk__in=form.cleaned_data["lead_ids"])
        )
        messages.success(request, f"{changed} lead(s) assigned to {assignee or 'nobody'}.")
    else:
        messages.error(request, "Select at least one lead.")
    return _redirect_back(request, "lead_list")


@login_required
def lead_create(request):
    form = LeadForm(request.POST or None, user=request.user, initial={"city": City.objects.filter(is_active=True).first()})
    if request.method == "POST" and form.is_valid():
        lead = form.save(commit=False)
        lead.created_by = request.user
        if not request.user.can_manage:
            lead.assigned_to = request.user
        lead.save()
        Activity.objects.create(lead=lead, user=request.user, kind=Activity.Kind.SYSTEM, body="Lead created")
        duplicates = lead.duplicates().count()
        if duplicates:
            messages.warning(request, f"Heads up: {duplicates} other lead(s) have the same phone number.")
        messages.success(request, "Lead added.")
        return redirect(lead)
    return render(request, "leads/lead_form.html", {"form": form, "is_new": True})


def _get_lead_for(request, pk, edit=False):
    lead = get_object_or_404(services.visible_leads(request.user), pk=pk)
    if edit and not services.can_edit(request.user, lead):
        raise PermissionDenied
    return lead


@login_required
def lead_edit(request, pk):
    lead = _get_lead_for(request, pk, edit=True)
    form = LeadForm(request.POST or None, instance=lead, user=request.user)
    if request.method == "POST" and form.is_valid():
        new_assignee = form.cleaned_data.get("assigned_to", lead.assigned_to)
        lead = form.save(commit=False)
        # Keep the stored assignee for now so services.assign can record the change on the timeline.
        lead.assigned_to_id = Lead.objects.values_list("assigned_to", flat=True).get(pk=pk)
        lead.save()
        edited = [form.fields[name].label or name for name in form.changed_data if name != "assigned_to"]
        if edited:
            Activity.objects.create(
                lead=lead, user=request.user, kind=Activity.Kind.SYSTEM, body="Edited: " + ", ".join(str(e) for e in edited)
            )
        services.assign(lead, new_assignee, request.user)
        messages.success(request, "Lead updated.")
        return redirect(lead)
    return render(request, "leads/lead_form.html", {"form": form, "lead": lead, "is_new": False})


@login_required
def lead_detail(request, pk):
    lead = _get_lead_for(request, pk)
    return render(request, "leads/lead_detail.html", {
        "lead": lead,
        "can_edit": services.can_edit(request.user, lead),
        "activity_form": ActivityForm(),
        "pipeline_form": PipelineForm(initial={
            "status": lead.status, "priority": lead.priority, "assigned_to": lead.assigned_to,
        }),
        "follow_up_form": FollowUpForm(),
        "activities": lead.activities.select_related("user"),
        "follow_ups": lead.follow_ups.select_related("assigned_to").order_by("completed_at", "due_at"),
        "duplicates": services.visible_leads(request.user).filter(pk__in=lead.duplicates().values("pk")),
    })


@login_required
@require_POST
def lead_log_activity(request, pk):
    lead = _get_lead_for(request, pk, edit=True)
    form = ActivityForm(request.POST)
    if form.is_valid():
        services.log_activity(lead, request.user, **form.cleaned_data)
        messages.success(request, "Saved to the timeline.")
    else:
        messages.error(request, "Could not save: " + "; ".join(e for errs in form.errors.values() for e in errs))
    return redirect(lead)


@login_required
@require_POST
def lead_pipeline(request, pk):
    lead = _get_lead_for(request, pk, edit=True)
    form = PipelineForm(request.POST)
    if form.is_valid():
        data = form.cleaned_data
        if lead.priority != data["priority"]:
            lead.priority = data["priority"]
            lead.save(update_fields=["priority", "updated_at"])
        services.set_status(lead, data["status"], request.user)
        assignee = data["assigned_to"]
        if request.user.can_manage:
            services.assign(lead, assignee, request.user)
        elif assignee not in (None, request.user) or (assignee is None and lead.assigned_to == request.user):
            messages.warning(request, "Only a manager can hand a lead to someone else.")
        else:
            services.assign(lead, assignee, request.user)
        messages.success(request, "Lead updated.")
    return redirect(lead)


@login_required
@require_POST
def lead_claim(request, pk):
    lead = _get_lead_for(request, pk)
    if lead.assigned_to is None:
        services.assign(lead, request.user, request.user)
        messages.success(request, "This lead is now yours.")
    return redirect(lead)


@login_required
@require_POST
def lead_add_follow_up(request, pk):
    lead = _get_lead_for(request, pk, edit=True)
    form = FollowUpForm(request.POST)
    if form.is_valid():
        assignee = form.cleaned_data["assigned_to"] if request.user.can_manage else None
        services.add_follow_up(
            lead, form.cleaned_data["due_at"], request.user, assignee=assignee or request.user,
            note=form.cleaned_data["note"],
        )
        messages.success(request, "Follow-up scheduled.")
    else:
        messages.error(request, "Pick a date and time for the follow-up.")
    return redirect(lead)


@login_required
@require_POST
def follow_up_complete(request, pk):
    follow_up = get_object_or_404(FollowUp.objects.select_related("lead"), pk=pk)
    if follow_up.assigned_to != request.user and not request.user.can_manage:
        raise PermissionDenied
    services.complete_follow_up(follow_up, request.user)
    messages.success(request, "Follow-up marked done.")
    return _redirect_back(request, follow_up.lead)


@login_required
def follow_up_list(request):
    now = timezone.now()
    end_of_today = timezone.localtime(now).replace(hour=23, minute=59, second=59)
    qs = FollowUp.objects.filter(completed_at__isnull=True).select_related("lead", "lead__city", "assigned_to")
    who = request.GET.get("who", "me")
    if who == "all" and request.user.can_manage:
        pass
    elif who.isdigit() and request.user.can_manage:
        qs = qs.filter(assigned_to_id=who)
    else:
        who = "me"
        qs = qs.filter(assigned_to=request.user)
    return render(request, "leads/follow_ups.html", {
        "overdue": qs.filter(due_at__lt=now),
        "today": qs.filter(due_at__gte=now, due_at__lte=end_of_today),
        "upcoming": qs.filter(due_at__gt=end_of_today)[:100],
        "who": who,
        "users": User.objects.filter(is_active=True).order_by("first_name", "username"),
    })
