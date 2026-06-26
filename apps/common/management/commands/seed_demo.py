"""
Seed demo data so the API is explorable straight after migration.

Creates the six categories (§9.4), an admin + moderator staff account, a handful
of verified neighbours in Dhaka, and a spread of open requests and offers. Idempotent:
safe to run repeatedly.

    python manage.py seed_demo
"""
from datetime import timedelta

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.adminpanel.models import PlatformConfig
from apps.identity.models import User
from apps.listings.models import Category, Listing

CATEGORIES = [
    ("food", "Food", "খাবার", "🍚", 1),
    ("clothes", "Clothes", "পোশাক", "👕", 2),
    ("medicine", "Medicine", "ওষুধ", "💊", 3),
    ("goods", "Household", "সামগ্রী", "🪑", 4),
    ("shelter", "Shelter", "আশ্রয়", "🏠", 5),
    ("other", "Other", "অন্যান্য", "📦", 6),
]

# (display_name, phone, area, lat, lng, verified)
PEOPLE = [
    ("Nadia", "+8801710000001", "Mirpur, Dhaka", 23.8069, 90.3687, True),
    ("Faruk", "+8801710000002", "Dhanmondi, Dhaka", 23.7461, 90.3742, True),
    ("Shahana", "+8801710000003", "Gulshan, Dhaka", 23.7925, 90.4078, True),
    ("Rakib", "+8801710000004", "Uttara, Dhaka", 23.8759, 90.3795, False),
    ("Mim", "+8801710000005", "Mohammadpur, Dhaka", 23.7657, 90.3589, True),
]

# (author_idx, type, category_key, title, description, quantity, urgency/window_hours)
LISTINGS = [
    (0, "request", "food", "Need a cooked meal for tonight",
     "Lost my job last week, two kids at home.", "3 meals", "high"),
    (1, "request", "medicine", "Insulin pen needed urgently",
     "Diabetic father ran out, pharmacy closed.", "1 pen", "critical"),
    (3, "request", "clothes", "Warm jacket for a 10-year-old",
     "Winter is coming and we can't afford one.", "1 jacket, M", "medium"),
    (2, "offer", "food", "Surplus rice & chicken curry — 6 portions",
     "Cooked too much for an event. Fresh and packed.", "6 portions", 5),
    (4, "offer", "goods", "Giving away a study desk",
     "Moving out, desk in good condition. Pickup only.", "1 desk", 48),
    (2, "offer", "clothes", "Bag of kids' clothes (2–4 yrs)",
     "Outgrown but clean and folded.", "~15 items", 72),
]


class Command(BaseCommand):
    help = "Seed demo categories, staff, neighbours, and listings."

    def handle(self, *args, **options):
        PlatformConfig.load()

        for key, en, bn, icon, order in CATEGORIES:
            Category.objects.update_or_create(
                key=key,
                defaults={"name_en": en, "name_bn": bn, "icon": icon, "sort_order": order},
            )
        self.stdout.write(self.style.SUCCESS(f"✓ {len(CATEGORIES)} categories"))

        admin, created = User.objects.get_or_create(
            phone="+8801700000000",
            defaults={"display_name": "Admin", "staff_role": User.StaffRole.ADMIN,
                      "is_staff": True, "is_superuser": True, "is_phone_verified": True},
        )
        if created:
            admin.set_password("admin12345")
            admin.save()
        User.objects.get_or_create(
            phone="+8801700000001",
            defaults={"display_name": "Moderator", "staff_role": User.StaffRole.MODERATOR,
                      "is_staff": True, "is_phone_verified": True},
        )
        self.stdout.write(self.style.SUCCESS("✓ staff (admin +8801700000000 / pw admin12345, moderator)"))

        people = []
        for name, phone, area, lat, lng, verified in PEOPLE:
            user, _ = User.objects.get_or_create(
                phone=phone,
                defaults={"display_name": name, "default_area": area,
                          "is_phone_verified": True, "is_id_verified": verified},
            )
            people.append(user)
        self.stdout.write(self.style.SUCCESS(f"✓ {len(people)} neighbours"))

        made = 0
        for idx, ltype, cat_key, title, desc, qty, extra in LISTINGS:
            if Listing.objects.filter(title=title).exists():
                continue
            author = people[idx]
            _, plat, plng = author.display_name, *self._coords(idx)
            category = Category.objects.get(key=cat_key)
            kwargs = dict(
                type=ltype, author=author, category=category, title=title,
                description=desc, quantity=qty, location=Point(plng, plat, srid=4326),
                area_label=author.default_area,
            )
            if ltype == "request":
                kwargs["urgency"] = extra
            else:
                kwargs["available_until"] = timezone.now() + timedelta(hours=extra)
            Listing.objects.create(**kwargs)
            made += 1
        self.stdout.write(self.style.SUCCESS(f"✓ {made} listings"))
        self.stdout.write(self.style.SUCCESS("Demo data ready. Try GET /v1/categories and /v1/listings/nearby."))

    @staticmethod
    def _coords(idx):
        return PEOPLE[idx][3], PEOPLE[idx][4]
