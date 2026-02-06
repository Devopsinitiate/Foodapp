import requests
import json

base_url = "http://localhost:8001"

# 1. Register/Login
username = "payment_tester"
password = "testpassword123"
email = "payment@test.com"

session = requests.Session()

# Try login first
print(f"Logging in as {username}...")
login_payload = {"username": username, "password": password}
response = session.post(f"{base_url}/api/token/", json=login_payload)

if response.status_code != 200:
    print("User not found, registering...")
    reg_payload = {
        "username": username,
        "email": email, 
        "password": password,
        "password2": password
    }
    # Register API might be /api/users/register/
    response = session.post(f"{base_url}/api/users/register/", json=reg_payload)
    if response.status_code == 201:
        print("Registration successful.")
        # Login again
        response = session.post(f"{base_url}/api/token/", json=login_payload)
    else:
        print(f"Registration failed: {response.text}")
        exit(1)

if response.status_code == 200:
    tokens = response.json()
    access_token = tokens['access']
    print("Login API successful, got token.")
    
    # Set Auth header for subsequent API calls
    session.headers.update({"Authorization": f"Bearer {access_token}"})
    
    # 2. ALSO perform Django Session login for checkout view (if we were testing the view, but here we test API)
    # The API calls in checkout.html use the browser session OR the token.
    # The checkout.html JS uses fetch() which by DEFAULT doesn't send cookies unless credentials: 'include' is set
    # BUT in checkout.html I saw: fetch('/api/orders/orders/', ...) 
    # It did NOT have credentials: 'include'. 
    # AND it did NOT have Authorization header (I noticed that!).
    # This means checkout.html might FAIL if it relies on SessionAuthentication but fetch doesn't send cookies.
    # Wait, simple fetch() within same origin DOES send cookies usually? 
    # MDN: "credentials: 'same-origin'" is the default. So it SHOULD send cookies.
    # So if I use SessionAuthentication, I need to make sure I am logged in via session.
    
    # For this script, I will stick to JWT for API calls to verify backend logic first.
else:
    print(f"Login failed: {response.text}")
    exit(1)

# 3. Find a restaurant and menu item directly via API
print("Fetching restaurants...")
response = session.get(f"{base_url}/api/restaurants/restaurants/")
if response.status_code != 200:
    print(f"Failed to fetch restaurants: {response.text}")
    exit(1)

results = response.json().get('results', [])
if not results:
    print("No restaurants found. Please seed data.")
    exit(1)

restaurant = results[0]
restaurant_id = restaurant['id']
restaurant_slug = restaurant['slug']
print(f"Using Restaurant: {restaurant['name']} (ID: {restaurant_id}, Slug: {restaurant_slug})")

# Get menu items
print(f"Fetching menu items from /api/restaurants/restaurants/{restaurant_slug}/menu/...")
response = session.get(f"{base_url}/api/restaurants/restaurants/{restaurant_slug}/menu/")

if response.status_code != 200:
    print(f"Failed to fetch menu items: Status {response.status_code}, Response: {response.text}")
    exit(1)

try:
    items = response.json()
    # Pagination or list support?
    if isinstance(items, dict) and 'results' in items:
        items = items['results']
except json.JSONDecodeError:
    print(f"Failed to decode menu JSON. Response: {response.text}")
    exit(1)
    
if not items:
    print("No menu items found.")
    exit(1)

item = items[0]
menu_item_id = item['id']
print(f"Using Menu Item: {item['name']} (ID: {menu_item_id})")

# 4. Add to Cart
print("Adding to cart...")
cart_payload = {
    "menu_item_id": menu_item_id,
    "quantity": 1
}
response = session.post(f"{base_url}/api/orders/cart/add/", json=cart_payload)
if response.status_code == 201:
    print("Item added to cart.")
else:
    print(f"Failed to add to cart: {response.text}")
    exit(1)

# 5. Create Order
print("Creating order...")
order_payload = {
    "restaurant_id": restaurant_id,
    "items": [
        {
            "menu_item_id": menu_item_id,
            "quantity": 1,
            "customizations": {},
            "special_instructions": ""
        }
    ],
    "delivery_address": "123 Test St",
    "delivery_city": "Test City",
    "delivery_state": "Test State",
    "contact_phone": "1234567890",
    "contact_email": email
}

response = session.post(f"{base_url}/api/orders/orders/", json=order_payload)
if response.status_code == 201:
    order_data = response.json()
    print(f"Order created successfully! Order Number: {order_data['order_number']}")
    print(f"Total: {order_data['total']}")
else:
    print(f"Order creation failed: {response.text}")
    exit(1)

print("Test Passed: Payment Flow API (Order Creation) works.")
