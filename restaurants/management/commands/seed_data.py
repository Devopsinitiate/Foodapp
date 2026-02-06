from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from restaurants.models import Category, Restaurant, MenuItem
from decimal import Decimal

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds the database with initial data'
    
    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding database...')
        
        # Create users
        admin = User.objects.create_superuser(
            username='admin',
            email='admin@foodapp.com',
            password='admin123'
        )
        
        vendor = User.objects.create_user(
            username='vendor1',
            email='vendor@foodapp.com',
            password='vendor123',
            user_type='vendor'
        )
        
        driver = User.objects.create_user(
            username='driver1',
            email='driver@foodapp.com',
            password='driver123',
            user_type='driver',
            phone='08012345678'
        )
        
        # Create categories
        categories_data = [
            ('Fast Food', '🍔'),
            ('Pizza', '🍕'),
            ('Asian', '🍜'),
            ('Desserts', '🍰'),
            ('Drinks', '🥤'),
        ]
        
        categories = {}
        for name, icon in categories_data:
            cat, _ = Category.objects.get_or_create(
                name=name,
                slug=name.lower().replace(' ', '-'),
                icon=icon
            )
            categories[name] = cat
        
        # Create restaurants
        restaurant = Restaurant.objects.create(
            owner=vendor,
            name='Quick Bites',
            slug='quick-bites',
            description='Fast and delicious food delivered to your door',
            address='123 Main Street, Lagos',
            phone='08098765432',
            rating=Decimal('4.5'),
            total_reviews=120,
            min_order_amount=Decimal('1000'),
            delivery_fee=Decimal('500'),
            estimated_delivery_time=30,
            is_open=True,
            status='active'
        )
        
        # Create menu items
        menu_items = [
            ('Cheese Burger', 'Fast Food', Decimal('2500'), 'Juicy beef patty with cheese'),
            ('Chicken Pizza', 'Pizza', Decimal('4500'), 'Large pizza with chicken toppings'),
            ('Fried Rice', 'Asian', Decimal('3000'), 'Nigerian-style fried rice'),
            ('Chocolate Cake', 'Desserts', Decimal('1500'), 'Rich chocolate cake slice'),
            ('Fresh Juice', 'Drinks', Decimal('800'), 'Freshly squeezed juice'),
        ]
        
        for name, cat_name, price, desc in menu_items:
            MenuItem.objects.create(
                restaurant=restaurant,
                category=categories[cat_name],
                name=name,
                slug=name.lower().replace(' ', '-'),
                description=desc,
                price=price,
                is_available=True
            )
        
        self.stdout.write(self.style.SUCCESS('Database seeded successfully!'))
        self.stdout.write(f'Admin: admin / admin123')
        self.stdout.write(f'Vendor: vendor1 / vendor123')
        self.stdout.write(f'Driver: driver1 / driver123')