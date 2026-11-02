# Mitra POS

Small Django and MongoDB dropshipping POS with account-isolated products and orders.

## Start locally

1. Start MongoDB or set `MONGO_URI` and optionally `MONGO_DB`.
2. Create/activate a Python virtual environment.
3. Install dependencies: `pip install -r requirements.txt`.
4. Run `py manage.py runserver`.
5. Open `/signup/`. The first account becomes admin; later self-registered accounts have regular-user access and separate data.

Categories are managed by the workspace admin and shared with its user accounts. Each new product requires a category; subcategory is optional free text. Admins set the category's monthly minimum margin. When a category falls under target during the month, the dashboard asks whether to retain or archive the category and its active products. The choice is remembered for that month. Archiving preserves old orders and reports.

Sale entry, product updates, and status changes use background requests and update the relevant table without a full page reload. Sales become reportable when marked `completed`. Reports support year/month and admin user filters, category/subcategory profit and loss, interactive revenue/profit trend lines, and PDF downloads.

## Calculations and deployment

Tax defaults to 11% if no saved rate exists. Set `TAX_RATE_URL` to a trusted JSON endpoint returning `{"rate": 11}` to enable `/tax/refresh/`. Effective VAT for many Indonesian non-luxury goods is 11%; applicability depends on the transaction and seller. Revenue reports use pre-tax sales subtotal. Estimated profit is subtotal less supplier capital and excludes platform fees, shipping, returns, discounts, and income tax.

Before public deployment, set a strong `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, configure allowed hosts and secure cookies, add account recovery and rate limiting, and use HTTPS. Keep MongoDB credentials private and back up the database.
