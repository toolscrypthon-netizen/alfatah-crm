from django.core.management.base import BaseCommand

from leads.models import Area, City

LAHORE_AREAS = [
    "DHA Phase 1", "DHA Phase 2", "DHA Phase 3", "DHA Phase 4", "DHA Phase 5", "DHA Phase 6",
    "DHA Phase 7", "DHA Phase 8", "DHA Phase 9 Town", "DHA Rahbar", "Bahria Town", "Bahria Orchard",
    "Gulberg", "Model Town", "Johar Town", "Wapda Town", "Valencia", "Lake City", "Askari",
    "Cantt", "Garden Town", "Faisal Town", "Iqbal Town", "Township", "Samanabad", "Shadman",
    "Allama Iqbal Town", "Cavalry Ground", "EME Society", "Paragon City", "State Life",
    "Wapda City", "Park View City", "Al Rehman Garden", "Central Park", "Lahore Smart City",
    "Raiwind Road", "Bedian Road", "Canal Road", "Thokar Niaz Baig", "Sabzazar", "Mustafa Town",
]


class Command(BaseCommand):
    help = "Creates Lahore and its common housing areas. Safe to run more than once."

    def handle(self, *args, **options):
        city, created = City.objects.get_or_create(slug="lahore", defaults={"name": "Lahore"})
        added = sum(Area.objects.get_or_create(city=city, name=name)[1] for name in LAHORE_AREAS)
        self.stdout.write(self.style.SUCCESS(
            f"{'Created' if created else 'Found'} {city.name}; added {added} new area(s)."
        ))
