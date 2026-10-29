"""Changes to a lead go through these helpers so every change lands on the lead's timeline."""

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Activity, FollowUp, Lead


def visible_leads(user):
    qs = Lead.objects.select_related("city", "area", "assigned_to")
    if user.sees_all_leads:
        return qs
    return qs.filter(Q(assigned_to=user) | Q(assigned_to__isnull=True))


def can_edit(user, lead):
    return user.sees_all_leads or lead.assigned_to_id in (None, user.id)


def set_status(lead, status, user):
    if status == lead.status:
        return False
    old = lead.get_status_display()
    lead.status = status
    lead.save(update_fields=["status", "updated_at"])
    Activity.objects.create(
        lead=lead, user=user, kind=Activity.Kind.STATUS,
        body=f"Status changed from {old} to {lead.get_status_display()}",
    )
    if lead.is_closed:
        # A closed lead needs no more chasing.
        lead.follow_ups.filter(completed_at__isnull=True).update(completed_at=timezone.now())
        lead.refresh_follow_up()
    return True


def assign(lead, assignee, user):
    if assignee == lead.assigned_to:
        return False
    lead.assigned_to = assignee
    lead.save(update_fields=["assigned_to", "updated_at"])
    body = f"Assigned to {assignee}" if assignee else "Unassigned"
    Activity.objects.create(lead=lead, user=user, kind=Activity.Kind.ASSIGNMENT, body=body)
    return True


def add_follow_up(lead, due_at, user, assignee=None, note=""):
    follow_up = FollowUp.objects.create(
        lead=lead, due_at=due_at, note=note, assigned_to=assignee or lead.assigned_to or user, created_by=user
    )
    Activity.objects.create(
        lead=lead, user=user, kind=Activity.Kind.FOLLOW_UP,
        body=f"Follow-up scheduled for {timezone.localtime(due_at):%d %b %Y, %I:%M %p}"
        + (f" with {follow_up.assigned_to}" if follow_up.assigned_to != user else "")
        + (f": {note}" if note else ""),
    )
    lead.refresh_follow_up()
    return follow_up


def complete_follow_up(follow_up, user):
    if follow_up.completed_at:
        return
    follow_up.completed_at = timezone.now()
    follow_up.save(update_fields=["completed_at"])
    Activity.objects.create(
        lead=follow_up.lead, user=user, kind=Activity.Kind.FOLLOW_UP,
        body="Follow-up done" + (f": {follow_up.note}" if follow_up.note else ""),
    )
    follow_up.lead.refresh_follow_up()


@transaction.atomic
def log_activity(lead, user, kind, body="", outcome="", new_status="", follow_up_at=None, follow_up_note=""):
    activity = Activity.objects.create(lead=lead, user=user, kind=kind, body=body, outcome=outcome)
    if kind in Activity.CONTACT_KINDS:
        lead.last_contacted_at = activity.created_at
        if lead.status == Lead.Status.NEW and not new_status:
            new_status = Lead.Status.CONTACTED
        lead.save(update_fields=["last_contacted_at", "updated_at"])
        # Reaching the person counts as doing the follow-ups that were due.
        for follow_up in lead.follow_ups.filter(completed_at__isnull=True, due_at__lte=timezone.now()):
            complete_follow_up(follow_up, user)
    if lead.assigned_to is None and not user.sees_all_leads:
        # An agent working an unassigned lead takes ownership of it.
        assign(lead, user, user)
    if new_status:
        set_status(lead, new_status, user)
    if follow_up_at:
        add_follow_up(lead, follow_up_at, user, note=follow_up_note)
    return activity
