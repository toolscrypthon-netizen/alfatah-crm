import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import services
from .models import Activity, Area, City, FollowUp, Lead, normalize_phone
from .templatetags.crm import pkr

User = get_user_model()


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.city = City.objects.create(name="Lahore", slug="lahore")
        cls.dha = Area.objects.create(city=cls.city, name="DHA Phase 6")
        cls.manager = User.objects.create_user("manager", password="pw", role=User.Role.MANAGER)
        cls.agent = User.objects.create_user("agent", password="pw", first_name="Ali")
        cls.other_agent = User.objects.create_user("other", password="pw")

    def make_lead(self, **kwargs):
        data = {"intent": Lead.Intent.SELLING, "title": "10 marla house", "city": self.city, "phone": "0300-1234567"}
        data.update(kwargs)
        return Lead.objects.create(**data)


class HelperTests(TestCase):
    def test_normalize_phone(self):
        for raw in ("0300-1234567", "+92 300 1234567", "923001234567", "3001234567", "0092-300-1234567"):
            self.assertEqual(normalize_phone(raw), "03001234567", raw)

    def test_pkr(self):
        self.assertEqual(pkr(25_000_000), "2.5 Crore")
        self.assertEqual(pkr(8_500_000), "85 Lakh")
        self.assertEqual(pkr(45_000), "45,000")
        self.assertEqual(pkr(None), "")


class VisibilityTests(Base):
    def test_agents_see_own_and_unassigned_only(self):
        mine = self.make_lead(assigned_to=self.agent)
        free = self.make_lead()
        theirs = self.make_lead(assigned_to=self.other_agent)
        self.assertEqual(set(services.visible_leads(self.agent)), {mine, free})
        self.assertEqual(set(services.visible_leads(self.manager)), {mine, free, theirs})
        self.client.force_login(self.agent)
        self.assertEqual(self.client.get(reverse("lead_detail", args=[theirs.pk])).status_code, 404)

    def test_agent_cannot_export(self):
        self.client.force_login(self.agent)
        self.assertEqual(self.client.get(reverse("lead_export")).status_code, 403)


class WorkflowTests(Base):
    def test_logging_a_call_moves_lead_forward(self):
        lead = self.make_lead()
        due = timezone.now() + timedelta(days=1)
        self.client.force_login(self.agent)
        self.client.post(reverse("lead_log_activity", args=[lead.pk]), {
            "kind": "call", "outcome": "answered", "body": "Wants 2.4 crore, flexible",
            "follow_up_at": timezone.localtime(due).strftime("%Y-%m-%dT%H:%M"), "follow_up_note": "Send photos",
        })
        lead.refresh_from_db()
        self.assertEqual(lead.status, Lead.Status.CONTACTED)
        self.assertEqual(lead.assigned_to, self.agent)  # agent claimed it by working it
        self.assertIsNotNone(lead.last_contacted_at)
        self.assertIsNotNone(lead.next_follow_up)
        self.assertEqual(FollowUp.objects.get(lead=lead).assigned_to, self.agent)
        kinds = set(lead.activities.values_list("kind", flat=True))
        self.assertTrue({"call", "status", "assignment", "follow_up"} <= kinds)

    def test_contact_completes_due_follow_ups(self):
        lead = self.make_lead(assigned_to=self.agent)
        services.add_follow_up(lead, timezone.now() - timedelta(hours=1), self.agent)
        services.log_activity(lead, self.agent, kind=Activity.Kind.CALL, outcome="answered")
        self.assertFalse(lead.follow_ups.filter(completed_at__isnull=True).exists())
        lead.refresh_from_db()
        self.assertIsNone(lead.next_follow_up)

    def test_closing_lead_clears_follow_ups(self):
        lead = self.make_lead(assigned_to=self.agent)
        services.add_follow_up(lead, timezone.now() + timedelta(days=2), self.agent)
        services.set_status(lead, Lead.Status.WON, self.manager)
        self.assertFalse(lead.follow_ups.filter(completed_at__isnull=True).exists())

    def test_agent_cannot_reassign_to_someone_else(self):
        lead = self.make_lead(assigned_to=self.agent)
        self.client.force_login(self.agent)
        self.client.post(reverse("lead_pipeline", args=[lead.pk]), {
            "status": "interested", "priority": 2, "assigned_to": self.other_agent.pk,
        })
        lead.refresh_from_db()
        self.assertEqual(lead.assigned_to, self.agent)
        self.assertEqual(lead.status, Lead.Status.INTERESTED)

    def test_manager_bulk_assign(self):
        leads = [self.make_lead(), self.make_lead()]
        self.client.force_login(self.manager)
        self.client.post(reverse("lead_bulk_assign"), {
            "lead_ids": ",".join(str(l.pk) for l in leads), "assigned_to": self.agent.pk,
        })
        self.assertEqual(Lead.objects.filter(assigned_to=self.agent).count(), 2)

    def test_edit_records_assignment(self):
        lead = self.make_lead()
        self.client.force_login(self.manager)
        data = {
            "intent": "selling", "property_type": "house", "title": "Updated", "city": self.city.pk,
            "size_unit": "marla", "source": "manual", "priority": 2, "assigned_to": self.agent.pk,
            "phone": lead.phone,
        }
        response = self.client.post(reverse("lead_edit", args=[lead.pk]), data)
        self.assertEqual(response.status_code, 302)
        lead.refresh_from_db()
        self.assertEqual((lead.title, lead.assigned_to), ("Updated", self.agent))
        self.assertTrue(lead.activities.filter(kind="assignment").exists())


class PageTests(Base):
    def test_pages_render_for_each_role(self):
        lead = self.make_lead(price=25_000_000, area=self.dha)
        services.add_follow_up(lead, timezone.now() - timedelta(hours=2), self.manager)
        for user in (self.manager, self.agent):
            self.client.force_login(user)
            for url in (
                reverse("dashboard"), reverse("lead_list"), reverse("lead_list") + "?city=lahore&q=house",
                reverse("lead_detail", args=[lead.pk]), reverse("lead_create"), reverse("follow_up_list"),
            ):
                self.assertEqual(self.client.get(url).status_code, 200, (user, url))

    def test_login_required(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])


@override_settings(INGEST_API_TOKEN="secret")
class IngestTests(Base):
    url = reverse("api_ingest")

    def post(self, leads, token="secret"):
        return self.client.post(
            self.url, json.dumps({"leads": leads}), content_type="application/json", HTTP_X_API_TOKEN=token
        )

    def item(self, **kwargs):
        data = {
            "source": "olx", "external_id": "olx-1", "intent": "selling", "title": "1 kanal house DHA",
            "city": "lahore", "area_text": "DHA Phase 6, Lahore", "price": "52000000", "size": 1,
            "size_unit": "kanal", "phone": "03001234567",
        }
        data.update(kwargs)
        return data

    def test_rejects_bad_token(self):
        self.assertEqual(self.post([self.item()], token="nope").status_code, 401)

    def test_creates_and_dedupes(self):
        result = self.post([self.item(), self.item(), self.item(external_id="olx-2")]).json()
        self.assertEqual((result["created"], result["duplicates"]), (2, 1))
        lead = Lead.objects.get(external_id="olx-1")
        self.assertEqual(lead.area, self.dha)
        self.assertEqual(lead.price, 52_000_000)
        self.assertEqual(self.post([self.item()]).json()["duplicates"], 1)

    def test_reports_invalid_items(self):
        result = self.post([self.item(city="karachi"), self.item(intent="wrong", external_id="x")]).json()
        self.assertEqual(result["created"], 0)
        self.assertEqual(len(result["errors"]), 2)
