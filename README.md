
# Vendor Service - Complete Documentation

## Overview

The Vendor Service is a Django-based microservice that manages vendor onboarding, profiles, payouts, and analytics for the multivendor e-commerce platform. It provides complete vendor lifecycle management from registration to payout processing.

## ✨ Features

### 🏢 Vendor Management
- **Vendor Onboarding** with multi-step registration process  
- **Vendor Profiles** with business information and documents  
- **Vendor Approval Workflow** with admin review  
- **Vendor Analytics** with sales and performance metrics  
- **Vendor Settings** with customizable preferences  

### 💰 Payout Management
- **Multiple Payout Methods** (Stripe, PayPal, Bank Transfer)  
- **Payout Scheduling** with automatic processing  
- **Balance Tracking** with real-time updates  
- **Fee Calculation** with commission management  
- **Payout History** with detailed tracking  

### 📊 Analytics & Reporting
- **Sales Analytics** with monthly performance tracking  
- **Product Statistics** with inventory management  
- **Performance Reports** with vendor insights  
- **Dashboard Metrics** with key performance indicators  

### 🔒 Security & Compliance
- **Role-Based Access Control** (Admin, Vendor)  
- **Document Verification** with secure file uploads  
- **Payment Processor Integration** (Stripe, PayPal)  
- **Audit Logging** with comprehensive tracking  



## 🚀 Quick Start

### 1. Environment Setup

Create a `.env` file in the project root with the following configuration:

```env
# Django
DEBUG=True
SECRET_KEY=your-vendor-service-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

# Database
DB_NAME=vendor_service
DB_USER=postgres
DB_PASSWORD=password
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_URL=redis://localhost:6379/0

# Service URLs
AUTH_SERVICE_URL=http://localhost:8000
PRODUCT_SERVICE_URL=http://localhost:8002
ORDER_SERVICE_URL=http://localhost:8003

# Payment Processors
STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key
STRIPE_PUBLISHABLE_KEY=pk_test_your_stripe_publishable_key
PAYPAL_CLIENT_ID=your_paypal_client_id
PAYPAL_CLIENT_SECRET=your_paypal_client_secret
PAYPAL_MODE=sandbox

# File Upload
MAX_FILE_SIZE=10485760
ALLOWED_IMAGE_TYPES=image/jpeg,image/png,image/webp

# Email
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@yourapp.com

# Business
DEFAULT_COMMISSION_RATE=15.0
MIN_PAYOUT_AMOUNT=50.00


```

### 2. Installation & Setup

##### Clone and setup
```bash
git clone <repository>
cd vendor_service
```

##### Install dependencies
```bash
pip install -r requirements.txt
```

##### Database setup
```bash
python manage.py migrate
```

##### Create sample data (optional)
```bash
python manage.py create_sample_vendors
```

##### Run server
```bash
python manage.py runserver 8001
```

##### Run Celery worker (in separate terminal)
```bash
celery -A vendor_service worker --loglevel=info
```

##### Run Celery beat (for scheduled tasks)
```bash
celery -A vendor_service beat --loglevel=info
```

### 3. Docker Setup

```bash
# Using Docker Compose
docker-compose up -d

# Run migrations
docker-compose exec vendor-service python manage.py migrate

```


## 📡 API Endpoints

### 🏢 Vendor Management

| Method | Endpoint | Description | Authentication |
|:--------|:----------|:-------------|:----------------|
| `GET` | `/api/vendors/` | List vendors | Required |
| `POST` | `/api/vendors/` | Create vendor | Required |
| `GET` | `/api/vendors/{id}/` | Get vendor details | Vendor Owner / Admin |
| `PUT` | `/api/vendors/{id}/` | Update vendor | Vendor Owner / Admin |
| `POST` | `/api/vendors/{id}/approve/` | Approve vendor | Admin |
| `POST` | `/api/vendors/{id}/reject/` | Reject vendor | Admin |
| `GET` | `/api/vendors/{id}/dashboard/` | Vendor dashboard | Vendor Owner |

---

### 💰 Payout Management

| Method | Endpoint | Description | Authentication |
|:--------|:----------|:-------------|:----------------|
| `GET` | `/api/payouts/accounts/` | List payout accounts | Vendor |
| `POST` | `/api/payouts/accounts/` | Create payout account | Vendor |
| `POST` | `/api/payouts/accounts/{id}/verify/` | Verify account | Vendor |
| `GET` | `/api/payouts/balance/` | Get balance | Vendor |
| `POST` | `/api/payouts/payouts/` | Request payout | Vendor |
| `GET` | `/api/payouts/payouts/` | Payout history | Vendor |
| `GET` | `/api/payouts/summary/` | Payout summary | Vendor |

---

### 📁 Document Management

| Method | Endpoint | Description | Authentication |
|:--------|:----------|:-------------|:----------------|
| `GET` | `/api/vendors/documents/` | List documents | Vendor |
| `POST` | `/api/vendors/documents/` | Upload document | Vendor |
| `DELETE` | `/api/vendors/documents/{id}/` | Delete document | Vendor Owner |

---

### 🌍 Public Endpoints

| Method | Endpoint | Description | Authentication |
|:--------|:----------|:-------------|:----------------|
| `GET` | `/api/public/vendors/` | Public vendor list | None |
| `GET` | `/api/public/vendors/{slug}/` | Public vendor profile | None |



## 💻 Usage Examples

### 1. 📝 Vendor Registration
```javascript
// Register as a vendor
const response = await fetch('http://localhost:8001/api/vendors/', {
    method: 'POST',
    headers: {
        'Authorization': `Bearer ${access_token}`,
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({
        business_name: 'My Awesome Store',
        business_type: 'llc',
        business_description: 'We sell amazing products',
        contact_email: 'business@example.com',
        contact_phone: '+1234567890',
        address_line1: '123 Business St',
        city: 'New York',
        state: 'NY',
        country: 'US',
        postal_code: '10001',
        tax_id: '12-3456789'
    })
});

const vendor = await response.json();
console.log(vendor);

```

### 2. 📄 Upload Business Documents


``` javascript 
// Upload business license
const formData = new FormData();
formData.append('document_type', 'business_license');
formData.append('document_file', fileInput.files[0]);
formData.append('document_name', 'Business License');

const response = await fetch('http://localhost:8001/api/vendors/documents/', {
    method: 'POST',
    headers: {
        'Authorization': `Bearer ${access_token}`,
    },
    body: formData
});

const document = await response.json();
console.log(document);


```

### 3. 💳 Setup Payout Account

``` javascript 
// Add PayPal payout account
const response = await fetch('http://localhost:8001/api/payouts/accounts/', {
    method: 'POST',
    headers: {
        'Authorization': `Bearer ${access_token}`,
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({
        account_type: 'paypal',
        account_name: 'My Business PayPal',
        email: 'paypal@business.com',
        is_primary: true
    })
});

const account = await response.json();
console.log(account);
```

### 4. 💰 Request Payout

```javascript 
// Request payout
const response = await fetch('http://localhost:8001/api/payouts/payouts/', {
    method: 'POST',
    headers: {
        'Authorization': `Bearer ${access_token}`,
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({
        amount: 150.00,
        payout_account_id: 1
    })
});

const payout = await response.json();
console.log(payout);
```

### 5. 📊 Get Vendor Dashboard

```javascript 
// Get vendor dashboard
const response = await fetch('http://localhost:8001/api/vendors/1/dashboard/', {
    method: 'GET',
    headers: {
        'Authorization': `Bearer ${access_token}`,
        'Content-Type': 'application/json',
    }
});

const dashboard = await response.json();
console.log(dashboard);
```

## 👥 User Roles & Permissions

### 🧩 Role Definitions

| Role   | Description | Vendor Service Permissions |
| :------ | :----------- | :------------------------- |
| **Vendor** | Business seller | Manage own profile, products, payouts, view analytics |
| **Admin** | Platform administrator | Approve/reject vendors, view all vendors, manage payouts |

---

### 🧱 Permission Classes

```python
# Example usage in views
from apps.vendors.permissions import IsVendorOwner, IsAdminUser, IsApprovedVendor

class VendorProfileView(APIView):
    permission_classes = [IsVendorOwner]
    # Only vendor owners can access

class AdminVendorView(APIView):
    permission_classes = [IsAdminUser]
    # Only admin users can access

class VendorDashboardView(APIView):
    permission_classes = [IsApprovedVendor]
    # Only approved vendors can access
```
## 💳 Payout Processors

### 💰 Supported Payment Methods

#### 🟦 Stripe Connect
- Bank account payouts  
- Credit card processing  
- Real-time balance updates  

#### 🟨 PayPal Payouts
- Mass payments  
- International payouts  
- Email-based transfers  

#### 🏦 Bank Transfer
- Direct bank deposits  
- ACH transfers (US)  
- SEPA transfers (EU)  

---

### ⚙️ Payout Configuration

```python
# Example payout schedule
{
    "schedule_type": "weekly",
    "minimum_payout_amount": 50.00,
    "auto_process": true,
    "next_payout_date": "2023-12-01"
}

```

## 🧾 Vendor Onboarding Flow

### 🪜 Step 1: Basic Information
- Business name and type  
- Contact information  
- Business address  

---

### 📄 Step 2: Document Upload
- Business license  
- Tax certificate  
- Identity verification  
- Bank account proof  

---

### 💵 Step 3: Payout Setup
- Payment method selection  
- Account verification  
- Payout schedule setup  

---

### ✅ Step 4: Admin Approval
- Document review  
- Background verification  
- Account activation  



## 🔗 Integration with Other Services

### 🧠 Auth Service Integration
```python
from shared.clients.auth_client import auth_client

# ✅ Validate user token
user_data = auth_client.validate_token(token)

# 👤 Get user profile
user_profile = auth_client.get_user_profile(user_id)

# 🔄 Update user role
auth_client.update_user_role(user_id, 'vendor')


```

### 🛍️ Product Service Integration
```python
from shared.clients.product_client import product_client

# 📦 Get vendor product count
product_count = product_client.get_vendor_product_count(vendor_id)

# 🔄 Sync vendor products
product_client.sync_vendor_products(vendor_id)

# 📊 Get product analytics
analytics = product_client.get_product_analytics(vendor_id)
```

## 🔔 Webhook Handling
Vendor Service supports asynchronous payout updates via webhooks from payment processors such as **PayPal** and **Stripe**.  
These webhooks automatically update payout statuses, balances, and transaction histories.

---

### 🟦 PayPal Webhooks
```python
# Handle PayPal payout webhooks
def handle_paypal_webhook(webhook_data):
    processor = PayPalProcessor()
    return processor.webhook_handler(webhook_data)
```

### 🟪 Stripe Webhooks

``` python
# Handle Stripe connect webhooks
def handle_stripe_webhook(webhook_data):
    processor = StripeProcessor()
    return processor.webhook_handler(webhook_data)

```

## 🧪 Testing

The `vendor_service` includes a complete test suite for vendors, payouts, and document management.

---

### ✅ Run Test Suite
```bash
python manage.py test apps.vendors apps.payouts --verbosity=2
```

## 🔧 Test API Endpoints

You can test the Vendor Service APIs directly using **cURL** commands.

---

### 🧱 Create Vendor
```bash
curl -X POST http://localhost:8001/api/vendors/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
        "business_name": "Test Vendor",
        "business_type": "individual",
        "contact_email": "test@vendor.com",
        "contact_phone": "+1234567890",
        "address_line1": "123 Test St",
        "city": "Test City",
        "state": "TS",
        "country": "US",
        "postal_code": "12345"
      }'
```

## 🩺 Monitoring & Logging

Logging helps track service activity, debug issues, and monitor application health in production.

---

### ⚙️ Logging Configuration

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'vendor_service.log',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'apps': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}


```

## 📈 Key Metrics to Monitor

Tracking key metrics helps ensure vendor operations run smoothly and payout processes remain reliable.

| Metric | Description | Monitoring Tool |
|--------|--------------|----------------|
| **Vendor Registration Rate** | Number of new vendors registered per day/week | Prometheus / Grafana |
| **Vendor Approval Rate** | Percentage of vendors approved after review | Admin dashboard / Celery task logs |
| **Document Verification Time** | Average time between document upload and approval | Celery metrics / Database query logs |
| **Payout Success Rate** | Percentage of successful payouts vs. total attempts | Payment processor logs (Stripe/PayPal) |
| **Average Payout Amount** | Mean amount of vendor payouts per period | Analytics dashboard |
| **API Response Times** | Average response latency per endpoint | APM tools (New Relic, Sentry, Datadog) |
| **Error Rate** | Failed requests and exceptions | Django logging / Sentry alerts |

> 💡 Tip: Configure alerts for any metric that exceeds a defined threshold (e.g., payout failure rate > 5%).

---

## 🚀 Deployment

### ✅ Production Checklist

Before deploying the **Vendor Service**, complete the following steps:

1. **Set `DEBUG=False`**
   - Ensures sensitive debug information is not exposed in production.

2. **Generate a New `SECRET_KEY`**
   - Use a secure random key generator (e.g., `python -c 'import secrets; print(secrets.token_urlsafe(50))'`).

3. **Configure Production Database**
   - Use PostgreSQL or another production-ready DB.
   - Enable SSL and backups.

4. **Set Up SSL Certificates**
   - Use **Let’s Encrypt** or **Cloudflare SSL** for HTTPS.

5. **Configure Production Payment Processors**
   - Add live keys for Stripe and PayPal.
   - Verify webhook endpoints are publicly accessible and secured.

6. **Set Up Monitoring and Alerting**
   - Integrate **Sentry**, **Prometheus**, or **Grafana** for logs and performance metrics.
   - Create alert rules for downtime and payment errors.

7. **Configure Backup Strategy**
   - Schedule automatic daily backups for both the database and uploaded files.

8. **Set Up CI/CD Pipeline**
   - Automate testing, build, and deployment using **GitHub Actions**, **GitLab CI**, or **Jenkins**.

---


## 🌍 Environment Variables for Production

Your `.env` file should contain secure and production-ready values.  
Never commit this file to version control.

```env
# General
DEBUG=False
SECRET_KEY=your-production-secret-key
ALLOWED_HOSTS=vendors.yourdomain.com,api.yourdomain.com

# Database (Production)
DB_NAME=production_vendors
DB_USER=your_production_user
DB_PASSWORD=your_strong_password
DB_HOST=your-production-db-host
DB_PORT=5432

# Redis (Production)
REDIS_URL=redis://your-redis-host:6379/0

# Payment Processors
STRIPE_SECRET_KEY=sk_live_your_live_stripe_key
STRIPE_PUBLISHABLE_KEY=pk_live_your_live_stripe_key
PAYPAL_CLIENT_ID=your_live_paypal_client_id
PAYPAL_CLIENT_SECRET=your_live_paypal_secret
PAYPAL_MODE=live

# Service Endpoints
AUTH_SERVICE_URL=https://auth.yourdomain.com
PRODUCT_SERVICE_URL=https://products.yourdomain.com
ORDER_SERVICE_URL=https://orders.yourdomain.com

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=your-sendgrid-api-key
DEFAULT_FROM_EMAIL=noreply@yourdomain.com

# Business Rules
DEFAULT_COMMISSION_RATE=15.0
MIN_PAYOUT_AMOUNT=50.00
AUTO_PAYOUT_SCHEDULE=weekly


```


## 🧩 Troubleshooting

### ⚙️ Common Issues

#### 🏢 Vendor Registration Fails
- Ensure the **business name** is unique.
- Verify all **required documents** are uploaded.
- Check that **contact email and phone** are valid.
- Review server logs for detailed validation errors.

#### 💰 Payout Processing Issues
- Confirm **payout account** has been verified.
- Verify vendor **balance** meets the minimum payout threshold.
- Check **payout amount** does not exceed available balance.
- Inspect processor logs for Stripe/PayPal webhook errors.

#### 📄 Document Upload Problems
- Check **file size limits** defined in environment (`MAX_FILE_SIZE`).
- Verify **allowed file types** (JPEG, PNG, WEBP).
- Ensure the user is **authenticated** with a valid access token.
- Review upload folder permissions and storage backend.

#### 🔗 Service Integration Issues
- Verify **Auth, Product, and Order service URLs** in `.env`.
- Check **authentication tokens** for expiration.
- Confirm **inter-service communication** via network or API gateway.
- Monitor service **health endpoints** (e.g., `/health/`).

---

### 🆘 Support

If you encounter issues:

- Check application logs:  
  📜 `vendor_service.log`
- Verify all environment variables are correctly set.
- Test payment processor connectivity (`Stripe`, `PayPal`).
- Validate inter-service API responses manually via `curl` or `Postman`.
- Consult official API documentation (below).

---

## 📘 API Documentation

Access the interactive documentation in your browser:

- **Swagger UI:** [http://localhost:8001/swagger/](http://localhost:8001/swagger/)  
- **ReDoc:** [http://localhost:8001/redoc/](http://localhost:8001/redoc/)

---

## ⚡ Performance Optimization

### 🗄️ Database Optimization

Efficient database queries help improve performance, especially for large-scale vendor data.

```python
# Example: Optimize vendor data retrieval using select_related and prefetch_related
vendors = Vendor.objects.select_related(
    'analytics', 'balance'
).prefetch_related(
    'documents', 'payout_accounts'
)
```

### 🚀 Caching Strategy

```python 

Reduce repeated database queries with intelligent caching.

# Example: Cache vendor profiles for faster repeated access
cache_key = f"vendor_profile_{vendor_id}"
cached_profile = cache.get(cache_key)

if not cached_profile:
    cached_profile = get_vendor_profile(vendor_id)
    cache.set(cache_key, cached_profile, 600)  # Cache for 10 minutes

```


## 🛡️ Security Best Practices

### 1. 🧾 Data Protection

Ensure all uploaded vendor documents are securely validated and stored.

```python
# Secure file upload model configuration
from django.core.validators import FileExtensionValidator
from apps.vendors.validators import validate_file_size

document_file = models.FileField(
    upload_to='vendor/documents/',
    validators=[
        FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'png']),
        validate_file_size
    ]
)
```

### 2. 🔐 API Security

```python 

Use JWT authentication, enforce permission classes, and rate-limit API requests.

# Secure API configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day',
    },
}

```

### 3. 💰 Payment Security

```python 
Ensure safe payout handling and validation to prevent fraudulent or incorrect transactions.

# Secure payout validation logic
def process_payout(payout):
    if not payout.account.is_verified:
        raise PayoutError("Payout account not verified")

    if payout.amount > payout.balance.available_balance:
        raise PayoutError("Insufficient balance")

    # Proceed with payout processing securely
    payout.execute()

```
## 🤝 Contributing

We welcome contributions to improve the **Vendor Service**.  
Please follow these guidelines to maintain consistency and quality:

### 🧩 Contribution Guidelines
- Follow the **[PEP 8](https://peps.python.org/pep-0008/)** style guide.
- Write **unit tests** and **integration tests** for all new features.
- Update the **documentation** and **README.md** when introducing changes.
- Use **meaningful commit messages** that describe your changes clearly.
- Submit **pull requests** to the `develop` branch for review before merging.
- Ensure all tests pass before requesting a review.

### 🧪 Recommended Tools
- **Black** for code formatting  
- **Flake8** for linting  
- **pytest** for testing  
- **pre-commit hooks** to enforce code quality before commits  

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](./LICENSE) file for details.

---

