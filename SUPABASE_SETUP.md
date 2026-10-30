# Supabase setup

## 1. Create the database tables

In the Supabase project, open **SQL Editor**, paste the contents of
[`supabase_schema.sql`](./supabase_schema.sql), and run it.
If the tables already exist, run
[`supabase_migration_add_mileage.sql`](./supabase_migration_add_mileage.sql)
before deploying this version of the app. It adds min/max kilometer columns and
copies values from the previous `mileage_km` column into both bounds, keeping
existing exact odometer readings intact.

## 2. Create the first admin

1. In **Authentication → Users**, create an account for the tool owner.
2. Copy that user's UUID.
3. Run this SQL, replacing the UUID:

```sql
insert into public.admin_users (user_id)
values ('00000000-0000-0000-0000-000000000000');
```

The admin signs into the app using that email and password. Admin access is
checked against `admin_users`; creating a normal Auth account alone does not
grant admin permissions.

## 3. Configure app secrets

Set these values in the local Streamlit secrets file or the deployment's
Streamlit secrets settings. Never commit the service-role key.

```toml
SUPABASE_URL = "https://YOUR_PROJECT_ID.supabase.co"
SUPABASE_ANON_KEY = "YOUR_ANON_KEY"
SUPABASE_SERVICE_ROLE_KEY = "YOUR_SERVICE_ROLE_KEY"

CACHE_FRESHNESS_HOURS = "24"
CACHE_MIN_LISTINGS = "5"
PUBLIC_APP_URL = "https://valuasi-oto.duckdns.org"
LICENSE_SESSION_SECRET = "GENERATE_A_RANDOM_SECRET_WITH_AT_LEAST_32_CHARACTERS"
```

Locally, save the values in `.streamlit/secrets.toml`; that path is ignored by
Git. The service-role key is used only by the Streamlit server. Do not expose it
to browser-side code or share it publicly.
`PUBLIC_APP_URL` is used by the admin license generator to create activation links.
`LICENSE_SESSION_SECRET` signs persistent customer sessions. Use the same
random value for Streamlit and the license-session service; do not reuse the
Supabase service-role key.

## 4. Enable PWA on a VPS with Nginx

The PWA is online-only: it caches the app icon and manifest, but never caches
Streamlit pages, search results, API calls, or listing data. The PWA assets are
in [`pwa/`](./pwa/).

On the VPS, configure the three Supabase values in
`/home/valuasi-oto/valapp/.streamlit/secrets.toml`. Keep the file owned by the
app user and restrict it to that user (`chmod 600`); never add it to GitHub.
For example, copy it over SSH from a trusted local machine or edit it directly
on the server. Do not paste the values into chat or shell commands that are
saved in history.

1. Generate a session secret on the server, for example with
   `openssl rand -hex 32`. Add it as `LICENSE_SESSION_SECRET` to the Streamlit
   secrets/environment and to `/etc/valuasioto/license-session.env`:

   ```sh
   LICENSE_SESSION_SECRET=the_same_random_value_in_both_services
   LICENSE_SESSION_HOST=127.0.0.1
   LICENSE_SESSION_PORT=8765
   ```

2. Run `license_session_server.py` as a separate, unprivileged systemd service.
   The tailored unit
   [`deploy/valuasioto-license-session.service`](./deploy/valuasioto-license-session.service)
   uses the current VPS user and app path. Store the environment file with
   owner-only permissions (`chmod 600 /etc/valuasioto/license-session.env`).
   Enable and start the unit with `systemctl daemon-reload`, then
   `systemctl enable --now valuasioto-license-session`. The service listens only
   on localhost and must not be exposed directly to the internet.
3. Configure Nginx using
   [`deploy/nginx-pwa-locations.conf`](./deploy/nginx-pwa-locations.conf).
   Include it inside the existing HTTPS `server` block for the domain. In the
   existing Streamlit `location /` block, add
   [`deploy/nginx-pwa-injection.conf`](./deploy/nginx-pwa-injection.conf).
   Preserve the existing certificate and WebSocket proxy settings.
4. Restart Streamlit after adding `LICENSE_SESSION_SECRET`, then run
   `nginx -t` and reload Nginx.
5. Confirm that
   `https://valuasi-oto.duckdns.org/pwa/manifest.webmanifest`,
   `/sw.js`, and `/activate` load over HTTPS. The app should show **Pasang
   ValuasiOto** where the browser supports an install prompt.

Activation links use a URL fragment, so the license key is not sent in the
HTTP request or Nginx access logs. The activation page exchanges it over HTTPS
for a signed, 30-day `HttpOnly`, `Secure`, `SameSite=Lax` cookie. Only the
customer name and expiry are included in the signed cookie; the raw license key
is not stored in browser storage. At expiry, customers must activate again.

### Install on customer devices

- **Android / desktop Chrome or Edge:** open the HTTPS app URL and choose
  **Pasang ValuasiOto** or the browser's **Install app** menu.
- **iPhone / iPad:** open the HTTPS URL in Safari, tap **Share**, then **Add to
  Home Screen**.

The app and scrapers continue to run on the VPS. An internet connection is
required to use the dashboard and fetch market data.

## 5. Search and cache behavior

- Search first checks for matching make, model, year range, and location.
- Cache results are used when at least `CACHE_MIN_LISTINGS` are fresh within
  `CACHE_FRESHNESS_HOURS`.
- Otherwise, the existing source collectors run and their results are saved.
- Mobil123 and Carmudi collectors read vehicle and seller location fields from
  the listing page's structured metadata. OLX reads mileage from card text and
  location only when its card exposes a location-marked element. If a source
  does not expose a verifiable location, it stays null and is excluded from
  city-specific valuations.
- Admin CSV template: [`template_listing_admin.csv`](./template_listing_admin.csv).
- CSV columns: `source,make,model,variant,title,year,mileage_km,price,location,url,collected_at`.
- `mileage_km` is optional and accepts one odometer value (`105368`) or a range
  (`95000-100000`); leave it blank when unknown. Existing CSV files without
  this column remain supported.
- `price` must be the full Rupiah amount; `collected_at` uses `YYYY-MM-DD`.
- Kilometer ranges display both values. A single reading is stored with equal
  minimum and maximum values. The optional kilometer filter matches listings
  whose range overlaps the selected range.
- Mileage is shown and can optionally filter comparable listings, but is not
  yet used to adjust the recommended purchase price. Scrapers that do not
  reliably extract mileage leave it blank rather than estimating it.
- Mobil123 and Carmudi use structured vehicle mileage where available, with
  listing text as a fallback. OLX mileage is parsed from card text. Listings
  without readable mileage remain blank; source markup can change over time.
- Select **Ambil data terbaru (abaikan cache)** before searching to rerun the
  collectors immediately instead of using fresh cached rows from an earlier
  scraper version.

The collected marketplace values are asking prices, not confirmed transaction
prices. Check the source's terms and obtain any required permission before
enabling automated collection in production.
