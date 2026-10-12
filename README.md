# Property Revenue Dashboard Debugging Assignment

## Loom Walkthrough

Video walkthrough: https://www.loom.com/share/6fbba5b9e24044c58eaa2fead21dc341

## SetUp

I followed the instructions in ASSIGNMENT.md and investigated the clients and their data in the db.

From the problem description and the client reports, a few possible bugs came to mind:

- Database misconfiguration
- Invalid cache
- Incorrect date handling
- Rounding errors
- Bugs in the UI

## Investigation Approach

I like starting with running the whole test suite, but the project has none. I thus started by installing the project and logging in as both clients.

I compared what I saw in the UI with the API response and the data in the PostgreSQL Docker service:

~~~bash
docker compose exec db psql -U postgres -d propertyflow
~~~

I then checked the backend logs, Redis, the database queries and finally the code that handled each request. I worked from the data source towards the UI so that each later result was based on real data.

## What I Discovered and How

### 1. The application was returning mock revenue

The first thing I noticed was that Sunset's prop-001 result did not match the records in the db. The logs contained:

~~~text
Database pool initialization failed: 'Settings' object has no attribute 'supabase_db_user'
~~~

I searched for this configuration and found that database_pool.py expected settings that did not exist. I then followed the error into reservations.py and found that the error was caught and replaced with hardcoded revenue data. This made a database failure look like a valid financial result.

### 2. Revenue cache entries were shared between tenants

After tracing the revenue request, I checked Redis and found a key in this format:

~~~text
revenue:prop-001
~~~

Sunset and Ocean both have a property with the ID prop-001. This meant that the first client to load the property populated the value returned to the other client for five minutes. The database query included the tenant, but Redis returned its value before that query ran.

### 3. The monthly dashboard calculated all-time revenue

The UI described the result as monthly performance, but the endpoint did not accept a month or year. The active SQL query only filtered by property and tenant.

I also found an unfinished calculate_monthly_revenue function. It returned zero, was not used, and created date boundaries without using the property's timezone.

### 4. March was being interpreted in the wrong timezone

While checking the seeded records, I found this reservation:

~~~text
UTC:          2024-02-29 23:30
Europe/Paris: 2024-03-01 00:30
Amount:       1250.000
~~~

It is a February timestamp in UTC but a March booking for the Paris property. A UTC-only March filter would therefore exclude valid March revenue.

### 5. Exact database decimals were converted to floats

The database stores amounts as NUMERIC(10, 3) and the service initially used Decimal. The route converted the value to a Python float, after which the frontend rounded a JavaScript number using Math.round.

The seeded values 333.333, 333.333 and 333.334 made it clear that the financial rounding rule needed to be explicit and applied in one place.

### 6. Both clients saw the same hardcoded property list

While switching accounts, I noticed that both clients saw the same five properties. Ocean's prop-001 was even labelled as Sunset's “Beach House Alpha” instead of “Mountain Lodge Beta.”

I found that the entire list was hardcoded in Dashboard.tsx. The frontend also sent a simulated tenant header even though the tenant should only come from the authenticated user.

## Fixes Applied

I applied the fixes in the same order in which I found the issues:

### 1. Database connection and mock revenue

[backend/app/core/database_pool.py](backend/app/core/database_pool.py) now uses the configured DATABASE_URL and an async-compatible pool. [backend/app/main.py](backend/app/main.py) manages that shared pool, while [backend/app/services/reservations.py](backend/app/services/reservations.py) no longer replaces database errors with mock financial data. I also updated [backend/requirements.txt](backend/requirements.txt), [backend/pyproject.toml](backend/pyproject.toml) and [backend/uv.lock](backend/uv.lock) with SQLAlchemy's async dependency.

### 2. Cross-tenant cache

[backend/app/services/cache.py](backend/app/services/cache.py) now includes the tenant, property, year and month in every revenue cache key.

### 3. Monthly revenue

[backend/app/api/v1/dashboard.py](backend/app/api/v1/dashboard.py) now requires a reporting month and year. [backend/app/services/reservations.py](backend/app/services/reservations.py) filters reservations using that period instead of returning an all-time total.

### 4. Property timezone

[backend/app/services/reservations.py](backend/app/services/reservations.py) now builds the calendar month in the property's named timezone and converts the boundaries to UTC before querying.

### 5. Financial precision

[backend/app/services/reservations.py](backend/app/services/reservations.py) rounds the final Decimal using ROUND_HALF_UP. [backend/app/api/v1/dashboard.py](backend/app/api/v1/dashboard.py) returns that exact value as a string, and [frontend/src/components/RevenueSummary.tsx](frontend/src/components/RevenueSummary.tsx) displays it without JavaScript rounding.

### 6. Tenant-specific properties

[backend/app/api/v1/dashboard.py](backend/app/api/v1/dashboard.py) exposes a tenant-filtered property endpoint and rejects properties outside the authenticated tenant. [frontend/src/lib/secureApi.ts](frontend/src/lib/secureApi.ts) no longer sends a simulated tenant header, while [frontend/src/components/Dashboard.tsx](frontend/src/components/Dashboard.tsx) loads the authenticated client's properties and provides the month selector.

Finally, [.gitignore](.gitignore) excludes .idea, virtual environments, __pycache__ directories and compiled Python files.

## How I Will Demonstrate the Fixes

I will rebuild the application from a clean environment and demonstrate the following:

1. The backend connects to PostgreSQL and the API result agrees with the db instead of returning mock data.
2. When the database is unavailable, revenue returns a service error rather than a fabricated total.
3. Sunset and Ocean receive separate results for their shared prop-001 identifier.
4. Redis contains separate keys in this format:

~~~text
revenue:<tenant_id>:<property_id>:<year>:<month>
~~~

5. Sunset's March 2024 report includes the reservation stored at February 29 23:30 UTC because it is March 1 in Paris.
6. The raw API response contains the same exact two-decimal value displayed in the UI.
7. Sunset sees only Sunset properties and Ocean sees only Ocean properties.
8. A direct request for another tenant's property returns no property or revenue data.

## Recommendations

This is what I would do if I had more time:

1. Add regression tests for tenant cache isolation, local month boundaries, property authorization and decimal rounding.
2. Add structured logs for the tenant, property, reporting period and cache hit or miss without logging tokens or financial data.
3. Add cache invalidation when reservations or property timezone information changes.
