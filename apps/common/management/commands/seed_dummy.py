"""
Seed a larger volume of dummy data for exercising discovery, pagination and
distance ranking. Builds extra verified neighbours spread across Dhaka and a mix
of open requests and offers across every category, jittered around each author's
area so ``ST_DWithin`` / ``ST_Distance`` return meaningful results.

Idempotent: deterministic phones/titles mean re-running tops up to the target
counts without creating duplicates. Run ``seed_demo`` first for categories/staff.

    python manage.py seed_dummy                 # defaults: 20 users, 80 listings
    python manage.py seed_dummy --users 50 --listings 200
    python manage.py seed_dummy --flush          # delete dummy rows first
"""
import random
from datetime import timedelta

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.identity.models import User
from apps.listings.models import Category, Listing

# Dhaka neighbourhoods with an approximate centre point to scatter around.
AREAS = [
    ("Mirpur, Dhaka", 23.8069, 90.3687),
    ("Dhanmondi, Dhaka", 23.7461, 90.3742),
    ("Gulshan, Dhaka", 23.7925, 90.4078),
    ("Uttara, Dhaka", 23.8759, 90.3795),
    ("Mohammadpur, Dhaka", 23.7657, 90.3589),
    ("Banani, Dhaka", 23.7937, 90.4066),
    ("Bashundhara, Dhaka", 23.8103, 90.4125),
    ("Mohakhali, Dhaka", 23.7780, 90.4030),
    ("Old Dhaka", 23.7104, 90.4074),
    ("Tejgaon, Dhaka", 23.7639, 90.3950),
]

FIRST_NAMES = [
    "Aarav", "Ayesha", "Imran", "Sadia", "Tanvir", "Nusrat", "Rifat", "Jannat",
    "Sabbir", "Tasnim", "Hasan", "Farhana", "Arif", "Maliha", "Sajid", "Rumana",
    "Zahid", "Lamia", "Naimur", "Sumaiya", "Fahim", "Nabila", "Shakib", "Tania",
]

# category_key -> (request titles, offer titles)
TITLES = {
    "food": (
        ["Need a hot meal for the family", "Iftar for 4 people tonight",
         "Baby formula running low", "Rice for the week"],
        ["Extra biryani — 8 plates", "Home-cooked dal & rice to share",
         "Fresh vegetables from our garden", "Surplus bread & eggs"],
    ),
    "clothes": (
        ["Winter sweater for a toddler", "School uniform, age 8",
         "Warm blanket needed", "Shoes for work, size 42"],
        ["Bag of men's shirts (M/L)", "Kids' winter jackets",
         "Gently used sarees", "Pair of sneakers, size 40"],
    ),
    "medicine": (
        ["Paracetamol for a sick child", "Blood pressure meds this week",
         "Asthma inhaler urgently", "First-aid supplies"],
        ["Unopened vitamins to give", "Spare crutches available",
         "Glucose strips, sealed", "Thermometer & masks"],
    ),
    "goods": (
        ["Need a small study table", "Looking for a working fan",
         "Kitchen utensils for a new home", "A mattress for one"],
        ["Giving away a bookshelf", "Working table fan", "Set of plates & cups",
         "Single bed frame, pickup only"],
    ),
    "shelter": (
        ["Temporary place to stay, 2 nights", "Shelter from the rain tonight",
         "Room needed near Mirpur"],
        ["Spare room for a few nights", "Floor space available for one",
         "Quiet room to offer briefly"],
    ),
    "other": (
        ["Help moving boxes Saturday", "Need a phone charger",
         "Umbrella for the commute"],
        ["Free moving boxes", "Spare umbrellas", "Phone charger to give"],
    ),
}

URGENCIES = ["low", "medium", "high", "critical"]


class Command(BaseCommand):
    help = "Seed a larger volume of dummy neighbours and listings across Dhaka."

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=20, help="target dummy users")
        parser.add_argument("--listings", type=int, default=80, help="target dummy listings")
        parser.add_argument("--flush", action="store_true", help="delete dummy rows first")

    def handle(self, *args, **options):
        rng = random.Random(42)  # deterministic across runs

        if options["flush"]:
            n_l = Listing.objects.filter(title__startswith="[dummy]").delete()[0]
            n_u = User.objects.filter(phone__startswith="+8801999").delete()[0]
            self.stdout.write(self.style.WARNING(f"flushed {n_l} listings, {n_u} users"))

        categories = list(Category.objects.filter(is_active=True))
        if not categories:
            self.stderr.write("No categories — run `python manage.py seed_demo` first.")
            return
        cat_by_key = {c.key: c for c in categories}

        # ── Users ── deterministic phones in the +8801999xxxxx dummy block.
        people = []
        for i in range(options["users"]):
            area, _, _ = AREAS[i % len(AREAS)]
            phone = f"+88019990{i:05d}"
            name = f"{FIRST_NAMES[i % len(FIRST_NAMES)]} {i + 1}"
            user, _ = User.objects.get_or_create(
                phone=phone,
                defaults={
                    "display_name": name,
                    "default_area": area,
                    "is_phone_verified": True,
                    "is_id_verified": rng.random() < 0.6,
                    "trust_score": rng.randint(30, 95),
                },
            )
            people.append((user, AREAS[i % len(AREAS)]))
        self.stdout.write(self.style.SUCCESS(f"✓ {len(people)} dummy neighbours"))

        # ── Listings ── jittered around each author's area; mix of types.
        made = skipped = 0
        for n in range(options["listings"]):
            author, (area, clat, clng) = people[n % len(people)]
            ltype = "request" if rng.random() < 0.5 else "offer"
            cat_key = rng.choice(list(TITLES.keys()))
            reqs, offers = TITLES[cat_key]
            base = rng.choice(reqs if ltype == "request" else offers)
            title = f"[dummy] {base} #{n + 1}"
            if Listing.objects.filter(title=title).exists():
                skipped += 1
                continue
            # Scatter ~0–6 km around the area centre (≈0.05° lat/lng).
            lat = clat + rng.uniform(-0.05, 0.05)
            lng = clng + rng.uniform(-0.05, 0.05)
            kwargs = dict(
                type=ltype, author=author, category=cat_by_key[cat_key], title=title,
                description="Auto-generated dummy listing for testing discovery.",
                quantity=rng.choice(["1", "2", "3 items", "a few", "5+"]),
                location=Point(lng, lat, srid=4326), area_label=area,
            )
            if ltype == "request":
                kwargs["urgency"] = rng.choice(URGENCIES)
            else:
                kwargs["available_until"] = timezone.now() + timedelta(hours=rng.randint(6, 96))
            Listing.objects.create(**kwargs)
            made += 1

        self.stdout.write(self.style.SUCCESS(f"✓ {made} dummy listings ({skipped} already existed)"))
        total = Listing.objects.count()
        self.stdout.write(self.style.SUCCESS(f"Done. {total} listings total in the database."))
