# Alfatah CRM

A lead CRM for Alfatah Marketing's property team. Leads come in from OLX (and later Facebook) through
an API, or are added by hand, and the team works them through calls, comments, statuses and follow-ups.

## What's in it

- **Leads** with intent (selling, looking to buy, renting out, looking to rent), property type, city and
  area, price or budget, size in marla/kanal/sq ft, contact details, and where the lead came from.
- **Lead list** with search and filters (intent, type, city, area, status, source, assignee, price range),
  sorting, CSV export and bulk assignment for managers.
- **Lead page** with one-tap Call and WhatsApp buttons, a timeline of every call, comment, status change
  and assignment, a pipeline box, and follow-ups. A warning shows when another lead has the same phone number.
- **Follow-ups**: overdue, today and upcoming for each person, with a red badge in the top bar when
  something is overdue. Logging a call completes the follow-ups that were due.
- **Dashboard** with today's numbers, your follow-ups, latest leads, and a team table for managers.
- **Roles**: admins and managers see and assign everything; agents see their own and unassigned leads,
  and a lead becomes theirs when they claim it or log a call on it.
- **Cities** are data, not code: add Karachi in *Settings & team → Cities* and its areas, and the
  collectors and filters pick it up.

## Run it locally

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
export DJANGO_DEBUG=1
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_cities          # Lahore and ~40 common areas
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver
```

Tests: `DJANGO_DEBUG=1 .venv/bin/python manage.py test`

## Deploy

See [docs/DEPLOY.md](docs/DEPLOY.md).

## Pushing leads in (for the collectors)

`POST /api/leads/ingest/` with header `X-Api-Token: <INGEST_API_TOKEN>` and a JSON body:

```json
{"leads": [{
  "source": "olx", "external_id": "1093847261", "intent": "selling", "property_type": "house",
  "title": "10 Marla house for sale", "description": "...", "city": "lahore",
  "area_text": "DHA Phase 6, Lahore", "price": 52000000, "size": 10, "size_unit": "marla",
  "bedrooms": 4, "contact_name": "Usman", "phone": "03001234567",
  "source_url": "https://www.olx.com.pk/item/...", "posted_at": "2026-10-29T09:15:00+05:00"
}]}
```

`intent`, `title` and `city` (a city slug) are required. Up to 200 leads per request. A lead with the
same `source` and `external_id` as an existing one is skipped. `area_text` is matched against the city's
known areas. The response lists how many were created, skipped as duplicates, or rejected and why.
