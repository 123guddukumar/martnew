"""
Management command: python manage.py seed_products
Seeds the database with sample products for testing.
"""
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from products.models import Product, Category


SAMPLE_DATA = {
    "Fast Food": [
        ("Chicken Burger", "Juicy grilled chicken with lettuce and mayo", 149),
        ("Veg Burger", "Crispy veggie patty with fresh veggies", 99),
        ("French Fries (Large)", "Golden crispy fries with seasoning", 79),
        ("Paneer Wrap", "Spiced paneer with veggies in a soft tortilla", 129),
    ],
    "Beverages": [
        ("Cold Coffee", "Chilled coffee with milk and ice cream", 89),
        ("Mango Lassi", "Fresh mango blended with yogurt", 69),
        ("Lemon Soda", "Refreshing lemon soda with mint", 49),
        ("Masala Chai", "Spiced Indian tea with ginger", 29),
    ],
    "Snacks": [
        ("Samosa (2 pcs)", "Crispy fried pastry with spiced potato filling", 39),
        ("Aloo Tikki", "Spiced potato patties with chutney", 49),
        ("Vada Pav", "Mumbai street-style spiced potato bun", 35),
        ("Dhokla", "Steamed savory gram flour cake", 59),
    ],
    "Desserts": [
        ("Gulab Jamun (2 pcs)", "Soft fried milk dumplings in sugar syrup", 49),
        ("Kulfi", "Traditional Indian ice cream with pistachio", 59),
        ("Rasgulla", "Soft cottage cheese balls in sugar syrup", 55),
    ],
}


class Command(BaseCommand):
    help = 'Seed the database with sample products'

    def handle(self, *args, **kwargs):
        count = 0
        for cat_name, products in SAMPLE_DATA.items():
            category, _ = Category.objects.get_or_create(
                name=cat_name,
                defaults={'slug': slugify(cat_name)}
            )
            for name, desc, price in products:
                _, created = Product.objects.get_or_create(
                    name=name,
                    defaults={
                        'description': desc,
                        'price': price,
                        'category': category,
                        'is_available': True,
                        'stock': 100,
                    }
                )
                if created:
                    count += 1

        self.stdout.write(self.style.SUCCESS(f'✅ Seeded {count} products across {len(SAMPLE_DATA)} categories'))
