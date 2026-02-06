# Food Ordering & Delivery Web Application

A full-featured food ordering and delivery platform built with Django, Django REST Framework, and TailwindCSS. Features real-time order tracking, Paystack payment integration, and a modern responsive UI.

## 🚀 Features

### For Customers
- **Browse Restaurants**: Search and filter restaurants by cuisine, rating, and location
- **Menu Ordering**: Add items to cart with customization options
- **Secure Payments**: Integrated with Paystack for card payments
- **Real-time Tracking**: Track your order status and delivery in real-time
- **Order History**: View past orders and reorder favorites
- **Reviews & Ratings**: Rate restaurants and leave feedback
- **Coupons & Discounts**: Apply promo codes for discounts

### For Vendors
- **Restaurant Management**: Manage restaurant profile and settings
- **Menu Management**: Add, edit, and manage menu items
- **Order Management**: View and update order status
- **Analytics Dashboard**: Track sales and performance metrics

### For Drivers
- **Delivery Dashboard**: View available deliveries
- **Real-time Navigation**: Get directions to pickup and delivery locations
- **Status Updates**: Update delivery status in real-time
- **Earnings Tracking**: Monitor delivery earnings

### For Admins
- **Platform Management**: Oversee all restaurants, orders, and users
- **Verification System**: Approve vendor and driver accounts
- **Analytics**: Platform-wide statistics and reports
- **Support System**: Handle disputes and customer support

## 🛠️ Technology Stack

### Backend
- **Django 5.0**: Web framework
- **Django REST Framework**: API development
- **PostgreSQL**: Production database
- **Redis**: Caching and real-time features
- **Django Channels**: WebSocket support for real-time updates
- **Celery**: Background task processing

### Frontend
- **TailwindCSS**: Utility-first CSS framework
- **Alpine.js**: Lightweight JavaScript framework
- **Vanilla JavaScript**: Custom interactions
- **Fetch API**: AJAX requests

### Integrations
- **Paystack**: Payment processing
- **Leaflet.js/Google Maps**: Location and mapping
- **WebSockets**: Real-time order tracking

## 📋 Prerequisites

- Python 3.9 or higher
- PostgreSQL 12 or higher
- Redis 6 or higher
- Node.js (optional, for TailwindCSS compilation)
- Git

## 🔧 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/food-ordering-app.git
cd food-ordering-app
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# On macOS/Linux
source venv/bin/activate

# On Windows
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Configuration

Create a `.env` file in the root directory:

```env
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_NAME=foodapp_db
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

# Paystack
PAYSTACK_PUBLIC_KEY=pk_test_your_public_key
PAYSTACK_SECRET_KEY=sk_test_your_secret_key

# Redis
REDIS_URL=redis://localhost:6379

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
```

### 5. Database Setup

```bash
# Create PostgreSQL database
createdb foodapp_db

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Load initial data (optional)
python manage.py loaddata fixtures/categories.json
```

### 6. Collect Static Files

```bash
python manage.py collectstatic --noinput
```

### 7. Run Development Server

```bash
# Start Redis (in a separate terminal)
redis-server

# Start Django with Channels support
daphne -b 0.0.0.0 -p 8000 config.asgi:application

# Or use Django's runserver for basic testing
python manage.py runserver
```

Visit `http://localhost:8000` in your browser.

## 📁 Project Structure

```
foodapp/
├── config/                 # Django project settings
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── users/                  # User management
│   ├── models.py          # User, UserProfile
│   ├── views.py           # Auth views & API
│   ├── serializers.py     # DRF serializers
│   ├── urls.py            # Template URLs
│   └── api_urls.py        # API URLs
├── restaurants/            # Restaurant management
│   ├── models.py          # Restaurant, MenuItem, Category, Review
│   ├── views.py           # Restaurant views & API
│   ├── serializers.py
│   ├── urls.py
│   └── api_urls.py
├── orders/                 # Order management
│   ├── models.py          # Order, OrderItem, Cart, Coupon
│   ├── views.py           # Order views & API
│   ├── serializers.py
│   ├── urls.py
│   └── api_urls.py
├── delivery/               # Delivery tracking
│   ├── models.py          # Delivery, DeliveryLocation, DriverAvailability
│   ├── views.py
│   ├── consumers.py       # WebSocket consumers
│   ├── routing.py
│   ├── urls.py
│   └── api_urls.py
├── payments/               # Payment processing
│   ├── models.py          # Payment, Refund, SavedCard
│   ├── views.py
│   ├── webhooks.py        # Paystack webhook handler
│   └── urls.py
├── static/                 # Static files
│   ├── css/
│   ├── js/
│   │   ├── main.js
│   │   └── modules/
│   │       ├── cart.js
│   │       ├── payments.js
│   │       └── real-time.js
│   └── images/
├── templates/              # HTML templates
│   ├── base.html
│   ├── home.html
│   ├── users/
│   ├── restaurants/
│   ├── orders/
│   └── delivery/
├── media/                  # User uploads
├── logs/                   # Application logs
├── .env                    # Environment variables
├── .gitignore
├── requirements.txt
└── manage.py
```

## 🔐 API Endpoints

### Authentication
- `POST /api/users/register/` - Register new user
- `POST /api/token/` - Obtain JWT token
- `POST /api/token/refresh/` - Refresh JWT token
- `GET /api/users/me/` - Get current user profile
- `PATCH /api/users/me/` - Update user profile
- `POST /api/users/change_password/` - Change password

### Restaurants
- `GET /api/restaurants/` - List restaurants
- `GET /api/restaurants/{id}/` - Restaurant details
- `GET /api/restaurants/categories/` - List categories
- `GET /api/restaurants/{id}/menu-items/` - Restaurant menu
- `GET /api/restaurants/menu-items/{id}/` - Menu item details
- `POST /api/restaurants/{id}/reviews/` - Add review

### Orders
- `GET /api/orders/cart/` - Get shopping cart
- `POST /api/orders/cart/add/` - Add item to cart
- `PATCH /api/orders/cart/items/{id}/` - Update cart item
- `DELETE /api/orders/cart/items/{id}/` - Remove from cart
- `POST /api/orders/cart/clear/` - Clear cart
- `GET /api/orders/orders/` - List user orders
- `POST /api/orders/orders/` - Create new order
- `GET /api/orders/orders/{id}/` - Order details
- `PATCH /api/orders/orders/{id}/` - Update order status
- `POST /api/orders/coupons/validate/` - Validate coupon

### Delivery
- `GET /api/delivery/deliveries/` - List deliveries
- `GET /api/delivery/deliveries/{id}/` - Delivery details
- `PATCH /api/delivery/deliveries/{id}/update_location/` - Update driver location
- `POST /api/delivery/deliveries/{id}/mark_delivered/` - Mark as delivered

### Payments
- `POST /payments/initialize/{order_id}/` - Initialize payment
- `GET /payments/verify/{reference}/` - Verify payment
- `POST /payments/webhook/` - Paystack webhook (server-to-server)

## 🔌 WebSocket Connections

### Real-time Order Tracking
```javascript
const socket = new WebSocket(`ws://localhost:8000/ws/orders/${orderId}/`);

socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Order update:', data);
};
```

### Real-time Delivery Tracking
```javascript
const socket = new WebSocket(`ws://localhost:8000/ws/delivery/${deliveryId}/`);

socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // Update map with driver location
};
```

## 💳 Paystack Integration

### Test Cards
- **Success**: 4084084084084081
- **Insufficient Funds**: 5060666666666666666
- **OTP**: Use `123456` for OTP verification

### Webhook Setup
1. Go to Paystack Dashboard > Settings > Webhooks
2. Add your webhook URL: `https://yourdomain.com/payments/webhook/`
3. Copy your webhook secret and add to `.env`

### Local Testing with ngrok
```bash
# Install ngrok
npm install -g ngrok

# Start tunnel
ngrok http 8000

# Use ngrok HTTPS URL in Paystack dashboard
```

## 🧪 Testing

### Run Tests
```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test users
python manage.py test restaurants
python manage.py test orders

# Run with coverage
coverage run --source='.' manage.py test
coverage report
```

### Test Paystack Integration
```python
# Use Django shell
python manage.py shell

from payments.models import Payment
from orders.models import Order

# Create test payment
order = Order.objects.first()
payment = Payment.objects.create(
    user=order.user,
    order=order,
    amount=order.total
)
```

## 🚀 Deployment

### Production Checklist
- [ ] Set `DEBUG=False` in settings
- [ ] Configure allowed hosts
- [ ] Use PostgreSQL database
- [ ] Set up SSL/HTTPS
- [ ] Configure static file serving
- [ ] Set up email service
- [ ] Configure Redis for production
- [ ] Set up background workers (Celery)
- [ ] Configure monitoring (Sentry)
- [ ] Set up backups
- [ ] Configure webhook URLs in Paystack

### Deploy to Heroku
```bash
# Install Heroku CLI
heroku login

# Create app
heroku create your-app-name

# Add buildpacks
heroku buildpacks:add heroku/python

# Set environment variables
heroku config:set SECRET_KEY=your-secret-key
heroku config:set DATABASE_URL=your-database-url
heroku config:set PAYSTACK_SECRET_KEY=your-key

# Deploy
git push heroku main

# Run migrations
heroku run python manage.py migrate

# Create superuser
heroku run python manage.py createsuperuser
```

## 📚 Additional Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [Paystack API Docs](https://paystack.com/docs/api/)
- [TailwindCSS](https://tailwindcss.com/docs)
- [Django Channels](https://channels.readthedocs.io/)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 👥 Authors

Your Name - [your-email@example.com](mailto:your-email@example.com)

## 🙏 Acknowledgments

- Django community
- Paystack for payment infrastructure
- TailwindCSS for UI components
- All contributors

---

For questions or support, please open an issue or contact [support@yourapp.com](mailto:support@yourapp.com).