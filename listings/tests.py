import json
import shutil
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from leads.models import Area, City, Lead

from .models import Listing, ListingPhoto

User = get_user_model()
MEDIA = tempfile.mkdtemp()


def jpeg(name="p.jpg", size=(2400, 1800), color="red"):
    out = BytesIO()
    Image.new("RGB", size, color).save(out, "JPEG")
    return SimpleUploadedFile(name, out.getvalue(), content_type="image/jpeg")


@override_settings(MEDIA_ROOT=MEDIA)
class ListingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.city = City.objects.create(name="Lahore", slug="lahore")
        cls.dha = Area.objects.create(city=cls.city, name="DHA Phase 6")
        cls.admin = User.objects.create_user("boss", password="pw", role=User.Role.ADMIN)
        cls.manager = User.objects.create_user("manager", password="pw", role=User.Role.MANAGER)
        cls.agent = User.objects.create_user("agent", password="pw")
        cls.other = User.objects.create_user("other", password="pw")

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def post_listing(self, **extra):
        data = {
            "purpose": "sale", "property_type": "house", "city": self.city.pk, "area_name": "dha phase 6",
            "size": "10", "size_unit": "marla", "price": "38500000", "bedrooms": "5", "bathrooms": "5",
            "feature": ["Corner", "Solar system", "corner"], "on_website": "on", "owner_phone": "0300 1234567",
            "photos": [jpeg("a.jpg"), jpeg("b.jpg", color="blue")],
        }
        data.update(extra)
        return self.client.post(reverse("listing_create"), data, HTTP_X_REQUESTED_WITH="fetch")

    def test_create_with_photos_from_phone(self):
        self.client.force_login(self.agent)
        res = self.post_listing()
        self.assertEqual(res.status_code, 200, res.content)
        listing = Listing.objects.get()
        self.assertEqual(res.json()["url"], listing.get_absolute_url())
        self.assertEqual(listing.area, self.dha)
        self.assertEqual(listing.created_by, self.agent)
        self.assertEqual(listing.feature_list, ["Corner", "Solar system"])
        self.assertEqual(listing.display_title, "10 Marla House")
        self.assertEqual(listing.photos.count(), 2)
        with Image.open(listing.cover.image.path) as img:
            self.assertLessEqual(max(img.size), 1600)
        # An agent's listing waits for an admin before it goes on the website.
        self.assertFalse(listing.is_live)
        self.assertTrue(listing.awaiting_approval)

    def test_unknown_area_is_kept_as_text(self):
        self.client.force_login(self.agent)
        self.post_listing(area_name="Ghosia Colony", location_text="")
        listing = Listing.objects.get()
        self.assertIsNone(listing.area)
        self.assertEqual(listing.location_label, "Ghosia Colony, Lahore")

    def test_not_an_image_is_rejected_but_listing_saves(self):
        self.client.force_login(self.agent)
        bad = SimpleUploadedFile("x.jpg", b"not an image", content_type="image/jpeg")
        self.post_listing(photos=[bad])
        self.assertEqual(Listing.objects.get().photos.count(), 0)

    def test_missing_type_returns_errors(self):
        self.client.force_login(self.agent)
        res = self.post_listing(property_type="")
        self.assertEqual(res.status_code, 400)
        self.assertIn("property_type", res.json()["errors"])

    def test_only_owner_or_manager_can_edit(self):
        self.client.force_login(self.agent)
        self.post_listing()
        listing = Listing.objects.get()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("listing_detail", args=[listing.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("listing_edit", args=[listing.pk])).status_code, 403)
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(reverse("listing_edit", args=[listing.pk])).status_code, 200)

    def test_website_feed(self):
        self.client.force_login(self.agent)
        self.post_listing(title="Corner <house> & lawn", description="Nice")
        listing = Listing.objects.get()
        self.client.logout()
        self.assertEqual(self.client.get(reverse("website_feed_json")).json()["listings"], [])
        photo_url = reverse("listing_photo", args=[listing.cover.pk])
        self.assertEqual(self.client.get(photo_url).status_code, 404)
        self.client.force_login(self.admin)
        self.client.post(reverse("listing_approve", args=[listing.pk]), {"approve": "1"})
        self.client.logout()
        data = self.client.get(reverse("website_feed_json")).json()["listings"]
        self.assertEqual(len(data), 1)
        item = data[0]
        self.assertEqual(item["id"], listing.ref)
        self.assertEqual(item["title"], "Corner &lt;house&gt; &amp; lawn")
        self.assertEqual(item["marla"], 10)
        self.assertEqual(item["type"], "house")
        self.assertEqual(len(item["imgs"]), 2)
        self.assertNotIn("0300", json.dumps(item))  # owner phone stays private
        js = self.client.get(reverse("website_feed_js")).content.decode()
        self.assertIn("window.LISTINGS = live", js)
        self.assertNotIn("</", js.replace("<\\/", ""))

        # Public photo works while live, then disappears once sold.
        self.assertEqual(self.client.get(photo_url).status_code, 200)
        listing.status = Listing.Status.SOLD
        listing.save()
        self.assertEqual(self.client.get(reverse("website_feed_json")).json()["listings"], [])
        self.assertEqual(self.client.get(photo_url).status_code, 404)

    def test_approval_rules(self):
        self.client.force_login(self.agent)
        self.post_listing()
        listing = Listing.objects.get()
        # Agents and managers can't approve.
        for user in (self.agent, self.manager):
            self.client.force_login(user)
            self.assertEqual(self.client.post(reverse("listing_approve", args=[listing.pk])).status_code, 403)
        self.client.force_login(self.admin)
        self.client.post(reverse("listing_approve", args=[listing.pk]), {"approve": "1"})
        listing.refresh_from_db()
        self.assertTrue(listing.is_live)
        self.assertEqual(listing.approved_by, self.admin)
        # An agent's edit sends it back for approval.
        self.client.force_login(self.agent)
        data = {"purpose": "sale", "property_type": "house", "city": self.city.pk, "price": "40000000",
                "size": "10", "size_unit": "marla", "on_website": "on"}
        self.client.post(reverse("listing_edit", args=[listing.pk]), data, HTTP_X_REQUESTED_WITH="fetch")
        listing.refresh_from_db()
        self.assertEqual(listing.price, 40_000_000)
        self.assertFalse(listing.is_approved)
        # So do new photos from an agent.
        self.client.force_login(self.admin)
        self.client.post(reverse("listing_approve", args=[listing.pk]), {"approve": "1"})
        self.client.force_login(self.agent)
        self.client.post(reverse("listing_photo_add", args=[listing.pk]), {"photos": [jpeg()]})
        listing.refresh_from_db()
        self.assertFalse(listing.is_approved)
        # Marking it sold doesn't need approval.
        self.client.post(reverse("listing_update_status", args=[listing.pk]), {"status": "sold"})
        listing.refresh_from_db()
        self.assertEqual(listing.status, "sold")

    def test_admin_listing_is_approved_straight_away(self):
        self.client.force_login(self.admin)
        self.post_listing()
        self.assertTrue(Listing.objects.get().is_live)

    def test_pending_shows_for_admin(self):
        self.client.force_login(self.agent)
        self.post_listing()
        self.client.force_login(self.admin)
        res = self.client.get(reverse("listing_list") + "?status=pending")
        self.assertEqual(len(res.context["listings"]), 1)
        self.assertEqual(res.context["nav_pending_listings"], 1)

    def test_links_to_seller_lead_by_phone(self):
        lead = Lead.objects.create(intent=Lead.Intent.SELLING, title="House", city=self.city, phone="+92 300 1234567")
        self.client.force_login(self.agent)
        self.post_listing()
        self.assertEqual(Listing.objects.get().lead, lead)

    def test_listing_without_photo_stays_off_website(self):
        self.client.force_login(self.admin)
        self.post_listing(photos=[])
        self.assertEqual(self.client.get(reverse("website_feed_json")).json()["listings"], [])

    def test_kanal_converts_to_marla_for_website(self):
        self.client.force_login(self.admin)
        self.post_listing(size="1", size_unit="kanal")
        self.assertEqual(self.client.get(reverse("website_feed_json")).json()["listings"][0]["marla"], 20)

    def test_status_cover_and_delete(self):
        self.client.force_login(self.agent)
        self.post_listing()
        listing = Listing.objects.get()
        second = listing.photos.all()[1]
        self.client.post(reverse("listing_photo_cover", args=[second.pk]))
        self.assertEqual(listing.cover, second)
        self.client.post(reverse("listing_update_status", args=[listing.pk]), {"status": "under_offer"})
        listing.refresh_from_db()
        self.assertEqual(listing.status, "under_offer")
        self.client.post(reverse("listing_update_status", args=[listing.pk]), {"on_website": "0"})
        listing.refresh_from_db()
        self.assertFalse(listing.on_website)
        self.client.post(reverse("listing_delete", args=[listing.pk]))
        self.assertFalse(Listing.objects.exists())
        self.assertFalse(ListingPhoto.objects.exists())

    def test_prefill_from_lead(self):
        lead = Lead.objects.create(
            intent=Lead.Intent.RENT_OUT, title="Flat", city=self.city, area=self.dha, phone="03001112222",
            property_type=Lead.PropertyType.FLAT, contact_name="Usman",
        )
        self.client.force_login(self.manager)
        res = self.client.get(reverse("listing_create") + f"?lead={lead.pk}")
        self.assertContains(res, 'value="Usman"')
        self.assertContains(res, 'id="purpose-rent" value="rent"\n                 checked')
        self.post_listing(lead=str(lead.pk))
        self.assertEqual(Listing.objects.get().lead, lead)

    def test_pages_render(self):
        self.client.force_login(self.agent)
        self.post_listing()
        listing = Listing.objects.get()
        for url in (reverse("listing_list"), reverse("listing_create"), listing.get_absolute_url(),
                    reverse("listing_edit", args=[listing.pk]), reverse("listing_list") + "?status=live"):
            self.assertEqual(self.client.get(url).status_code, 200, url)
