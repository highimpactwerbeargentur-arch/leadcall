# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LeadCall24 is a German-language lead management SaaS for trade businesses (Handwerksbetriebe). It captures customer inquiries via missed-call → voice greeting → SMS → form pipeline, prioritizes them by budget/urgency, and presents them in a dashboard with offer generation, follow-up emails, and review requests. The entire frontend is static HTML — no build system, no bundler, no framework.

**Owner:** Tristan Haupt, Unter den Linden 9, 14542 Werder (Havel). Contact: tristanhaupt01@gmail.com / 0163 1692010. Einzelunternehmer (Kleinunternehmerregelung § 19 UStG).

## Architecture

**Static HTML site deployed on Vercel.** All pages are self-contained single-file HTML documents with inline CSS and JavaScript. There is no build step, no package manager, and no test suite.

### Pages

- **`index.html`** — Marketing landing page with demo request form → writes to Supabase `interessenten` table
- **`dashboard.html`** — Main app (~120KB): login, lead management, KPI metrics, offer/PDF generation, email sending, tenant management (admin). Heavily minified inline JS
- **`lead-form.html`** — Generic customer-facing intake form sent via SMS; submits to `leads` table, sends email via EmailJS, sends confirmation SMS via edge function
- **`onboarding.html`** — 4-step onboarding wizard (Firma → Leistungen → Telefonie → Extras) → writes to `onboarding_requests` table
- **`kunden/sykora/index.html`** — Customer-specific branded lead form for Hausmeisterservice Sykora with custom categories (Hausmeisterpflege, Gebäudereinigung, Hausmeisterdienste, Sonstiges). Uses Edge Function `lead-notification` for SMS instead of direct Twilio call
- **`datenschutz.html`** / **`impressum.html`** — Legal pages (privacy policy / imprint)

---

## Supabase Configuration

- **Project:** "Lead generation" (ID: `fbkkyzvumytipjtnrjrn`, region: `eu-central-2`)
- **URL:** `https://fbkkyzvumytipjtnrjrn.supabase.co`
- **Anon Key:** `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZia2t5enZ1bXl0aXBqdG5yanJuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk2NzM0MTMsImV4cCI6MjA4NTI0OTQxM30.FsdSHmWuyP5QiKqGbaDG6XZJiAzaOKdsbqgrXKrfQCk`
- All files use the same URL and anon key (public, RLS-protected)

### Database Tables

#### `tenants` (RLS enabled, 4 rows)
Multi-tenant customer table. Each tenant is a Handwerksbetrieb using the platform.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid (PK) | `gen_random_uuid()` |
| `name` | varchar | Company display name |
| `email` | varchar | nullable |
| `phone_number` | varchar | nullable |
| `username` | text | unique, nullable — used for login (appended with `@leadcall24.de` for Supabase Auth) |
| `password` | text | nullable (legacy, actual auth via Supabase Auth) |
| `auth_user_id` | uuid | FK → `auth.users.id`, unique, nullable |
| `is_active` | bool | default `true` |
| `form_url` | text | URL to tenant's lead form |
| `twilio_number` | text | Twilio phone number assigned to this tenant |
| `sipgate_number` | text | Sipgate phone number (alternative telephony) |
| `forwarding_number` | text | Business number calls are forwarded from |
| `sms_text` | text | Custom SMS text sent to callers |
| `greeting_text` | text | Voice greeting for callers (default: German message about SMS link) |
| `greeting_audio_url` | text | URL to custom audio greeting |
| `sms_template_initial` | text | SMS template with `{{firma}}` and `{{link}}` placeholders |
| `sms_template_confirmation` | text | Confirmation SMS template with `{{firma}}` placeholder |
| `sms_template_followup_1/2/3` | text | Follow-up SMS templates with `{{name}}` and `{{firma}}` placeholders |
| `created_at` / `updated_at` | timestamptz | auto |

**RLS Policies:**
- `anon`: SELECT own tenant only (by `auth_user_id`); no INSERT/UPDATE/DELETE
- `authenticated`: SELECT/UPDATE own tenant (`auth_user_id = auth.uid()`) or admin; INSERT/DELETE admin only
- Edge functions use service role key to bypass RLS when needed

#### `leads` (RLS enabled, ~90 rows)
Core lead/inquiry table.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid (PK) | `gen_random_uuid()` |
| `tenant_id` | uuid (FK → tenants) | Required |
| `name` | varchar | nullable |
| `phone` | varchar | Required, formatted to +49... |
| `email` | varchar | nullable |
| `company` | varchar | nullable |
| `service_type` | varchar | e.g. "gebaeudereinigung / glasreinigung (150 m²) – 1×/Woche" |
| `description` | text | nullable |
| `urgency` | varchar | `today`, `this_week`, `flexible` (default) |
| `budget` | varchar | `under_500`, `500_2000`, `2000_5000`, `over_5000`, `unknown` |
| `status` | varchar | `new` (default), `contacted`, `offer_sent`, `won`, `lost`, `bestandskunde` |
| `notes` | text | Internal notes |
| `offer_amount` | numeric | nullable |
| `close_reason` | varchar | nullable |
| `image_urls` | text[] | Array of Supabase Storage URLs |
| `privacy_accepted` | bool | default false |
| `privacy_accepted_at` | timestamptz | nullable |
| `call_received_at` | timestamptz | When the call came in |
| `sms_sent_at` | timestamptz | When SMS was sent |
| `form_submitted_at` | timestamptz | When form was filled |
| `offer_sent_at` | timestamptz | When offer was sent |
| `closed_at` | timestamptz | When lead was won/lost |
| `followup_1/2/3_sent_at` | timestamptz | Follow-up tracking (2, 5, 10 days after offer) |
| `created_at` / `updated_at` | timestamptz | auto |

**RLS Policies:**
- `anon`: INSERT allowed (for lead forms), UPDATE allowed only for `image_urls` column (for image URL patching), SELECT restricted to own `tenant_id`
- `authenticated`: SELECT/UPDATE/DELETE own tenant or admin; INSERT always

#### `onboarding_requests` (RLS enabled, 3 rows)
New customer signup requests from the onboarding wizard.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid (PK) | |
| `company` | text | Required |
| `contact_name` | text | Required |
| `position` | text | nullable |
| `phone` | text | Required |
| `email` | text | Required |
| `notification_email` | text | Email for new lead notifications |
| `address` | text | nullable |
| `services` | text[] | Array like `["sanitaer","heizung","elektro"]` |
| `services_other` | text | nullable, free text |
| `phone_setup` | text | `redirect` or `new_number` (CHECK constraint) |
| `business_phone` | text | nullable, existing business number for forwarding |
| `phone_type` | text | `festnetz` or `mobil` |
| `device` | text | `iphone` or `android` (CHECK constraint) |
| `greeting` | text | nullable |
| `subdomain` | text | Requested subdomain (e.g. "ihre-firma" → ihre-firma.leadcall24.de) |
| `notes` | text | nullable |
| `status` | text | `new`, `in_progress`, `completed`, `rejected` (CHECK constraint) |
| `tenant_id` | uuid (FK → tenants) | nullable, set when customer is activated |
| `created_at` / `updated_at` | timestamptz | auto |

**RLS:** `anon`: INSERT allowed (for onboarding form submissions), no SELECT/UPDATE/DELETE. `authenticated`: SELECT/UPDATE/DELETE admin only.

#### `interessenten` (RLS enabled, 1 row)
Marketing leads from the landing page demo form. RLS policy: `anon` INSERT only (for form submissions), `authenticated` SELECT/UPDATE/DELETE admin only.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid (PK) | |
| `name` | text | Required |
| `firma` | text | nullable |
| `telefon` | text | Required |
| `email` | text | Required |
| `branche` | text | nullable |
| `nachricht` | text | nullable |
| `quelle` | text | default `landingpage` |
| `created_at` | timestamptz | |

#### `activities` (RLS enabled, 0 rows)
Activity log for leads. **Planned but currently unused** — schema exists but no application code writes to this table. Intended for future lead activity tracking (calls, emails, status changes).

### Database Functions

- **`is_admin()`** — Returns true if current auth user has `role: 'admin'` in `user_metadata`
- **`my_tenant_id()`** — Returns the tenant ID for the current auth user
- **`send_followup_notifications()`** — Marks follow-up timestamps on leads with `offer_sent` status (2 days → followup_1, 5 days → followup_2, 10 days → followup_3). Only updates timestamps, does not send actual SMS/email
- **`update_updated_at()`** — Trigger function that sets `updated_at = NOW()` on row update

### Storage Buckets

- **`lead-images`** — Public bucket. Stores photos uploaded via lead forms. Path: `{lead_id}/{timestamp}_{index}.{ext}`
- **`angebote`** — Public bucket. Stores generated offer PDFs. Path: `{lead_id}/{timestamp}_angebot.pdf`

### Edge Functions

All edge functions have `verify_jwt: false` (publicly accessible).

1. **`sms-webhook`** (slug: `sms-webhook`) — Handles incoming Twilio/Sipgate webhooks for missed calls. Triggered by telephony provider when a call comes in.
2. **`smooth-worker`** (slug: `smooth-worker`, name: `sms-webhook`) — Earlier version of SMS webhook handler
3. **`swift-worker`** — Worker function (likely for background processing)
4. **`lead-notification`** — Called by customer-specific forms (e.g. Sykora) after lead submission. Sends SMS confirmation. Endpoint: `POST /functions/v1/lead-notification` with body `{ phone, name, tenant_name }`
5. **`voice-handler`** (22 versions) — Handles voice call flow. Likely serves TwiML for the voice greeting and triggers SMS sending.

---

## Telephony Integration

### Twilio
- **Account SID:** `AC69e8a043f6049873ad18f1a84fd46e42`
- **Auth Token:** Rotated and stored server-side only (in Supabase edge function secrets, not in client code)
- **Phone Number:** `+13135460107` (US number)
- **Usage:** SMS sending via edge functions (no client-side Twilio calls), voice call handling via `voice-handler` edge function
- Per-tenant Twilio numbers stored in `tenants.twilio_number`
- Edge functions use the Supabase service role key to access Twilio credentials securely

### Sipgate
- Per-tenant Sipgate numbers stored in `tenants.sipgate_number`
- Used as alternative telephony provider for some tenants

### Call Flow
1. Customer calls tenant's business number
2. Call is forwarded to Twilio/Sipgate number (configured per tenant)
3. `voice-handler` edge function answers with greeting (`tenants.greeting_text` or `greeting_audio_url`)
4. System sends SMS to caller with form link (`sms_template_initial` with `{{firma}}` and `{{link}}` placeholders)
5. Customer fills out lead form → lead saved to `leads` table
6. Tenant gets email notification via EmailJS + sees lead in dashboard

---

## EmailJS Configuration

- **Public Key (User ID):** `fc6zzeTCmrKyrkxJ2`
- **Service ID:** `service_te0rxxz`
- **Templates used:**
  - `template_qr2bxjn` — New lead notification email. Params: `name`, `phone`, `email`, `company`, `service_type`, `urgency`, `description`, `dashboard_link`
  - `template_oyi750j` — General-purpose email (offers, booking links, follow-ups, review requests). Params: `to_email`, `kunde_name`, `firma_name`, `nachricht`, `booking_link`

**Email triggers:**
- **New lead form submission** → `template_qr2bxjn` sent to notify tenant
- **Offer sent via PDF** → `template_oyi750j` with PDF URL as `booking_link`
- **Booking/appointment invitation** → `template_oyi750j` with Google Calendar link
- **Follow-up after offer** → `template_oyi750j` with custom follow-up message
- **Review request (won leads)** → `template_oyi750j` with Google review URL

---

## Dashboard Functionality (`dashboard.html`)

### External Libraries (CDN)
- `@supabase/supabase-js@2`
- `@emailjs/browser@4`
- `jspdf@2.5.2` + `jspdf-autotable@3.8.2` (PDF generation)

### Auth Flow
1. User enters username (e.g. `mueller-sanitaer`)
2. System converts to email: `{username}@leadcall24.de` (special case: `admin` → `admin@leadcall24.de`)
3. Checks if user exists in `tenants` table by username
4. If tenant has `auth_user_id` → existing user → password login via `sbClient.auth.signInWithPassword`
5. If tenant has no `auth_user_id` → first login → user sets password, account is created via Supabase Auth
6. Admin users have `role: 'admin'` in `user_metadata`
7. Auth token stored in `authToken` variable, used for all subsequent API calls

### Admin vs Tenant Views
- **Admin** sees: Onboarding tab, All Leads tab, Kunden (Tenants) tab
- **Tenant** sees: Anfragen (Leads) tab only, filtered to their `tenant_id`

### Minified JS Conventions
- `$(id)` → `document.getElementById(id)`
- `sG(table, query)` → Supabase GET (fetch with apikey/auth headers)
- `sU(table, id, data)` → Supabase PATCH (update)
- `sI(table, data)` → Supabase POST (insert)
- `sD(table, id)` → Supabase DELETE
- `getH()` / `getJH()` → Headers builders (apikey + auth token)
- `SL` → Status labels map, `OL` → Onboarding labels, `UL` → Urgency labels, `BL` → Budget labels
- `BV` → Budget numeric values for sorting (under_500→250, 500_2000→1250, etc.)
- `lf` → lead filter, `ls` → lead sort, `lyf` → lead year filter
- `of` → onboarding filter

### Lead Statuses & Workflow
`new` → `contacted` → `offer_sent` → `won` / `lost` / `bestandskunde`

### KPI Dashboard
Displays: Total leads, New leads, Offer sent, Won, Lost, Bestandskunde, Conversion rate, Total offer amount (for won leads)

### Offer/PDF Generation
- Full offer editor with sender info (pre-filled for Hausmeisterservice Sykora), recipient, line items, totals
- Generates professional PDF with logo via jsPDF
- PDF can be: downloaded, previewed, or emailed via EmailJS
- Sent PDFs uploaded to `angebote` storage bucket
- Offer updates lead status to `offer_sent` with `offer_amount` and `offer_sent_at`
- Angebotstypen: Hausmeistertätigkeiten, Gebäudereinigung, Grünflächenpflege, Winterdienst, Sonstiges

### Follow-Up System
- After offer is sent, manual follow-up emails can be sent via the dashboard
- DB function `send_followup_notifications()` tracks 2/5/10 day follow-up milestones
- Follow-up email pre-fills a professional German message referencing the original offer

### Review Requests
- For won leads, a review request email can be sent
- Links to Google Review: `https://search.google.com/local/writereview?placeid=ChIJZbNrxJk8fAURDeLejnl34FE`

### Booking/Appointment
- Sends booking link via email: `https://calendar.app.google/h2duMnoPvg3dCjPNA`

### Tenant Management (Admin only)
- View all tenants as cards with lead counts
- Set/change usernames for dashboard login
- Activate onboarding requests → creates tenant + Supabase Auth user

---

## Customer Onboarding Process

1. Prospect fills out `onboarding.html` (4 steps: company info, services, telephony setup, extras)
2. Data saved to `onboarding_requests` with status `new`
3. Admin sees request in dashboard Onboarding tab
4. Admin reviews details in slide-out panel
5. Admin clicks "Activate" → sets a username → system creates:
   - A new Supabase Auth user (`{username}@leadcall24.de`)
   - A new `tenants` row linked to the auth user
   - Updates `onboarding_requests.status` to `completed`
6. Tenant logs in for the first time → sets their own password
7. Admin configures telephony (Twilio/Sipgate number, forwarding) and sets up customer-specific form

---

## Vercel Deployment

- **Domain:** `leadcall24.de`
- **Subdomain routing** in `vercel.json`:
  - `sykora.leadcall24.de` → `/kunden/sykora/index.html`
- Push to `main` branch to deploy
- Supabase anon key is embedded in HTML (public, RLS-protected). Sensitive credentials (Twilio auth token, service role key) are stored as Supabase edge function secrets only
- Preview URL: `leadcall-git-main-tristans-projects-7ffa8023.vercel.app`

---

## Tenant IDs (Known)

- **Generic/default:** `38ead1f3-74be-4db3-a61b-27f9152d2478` (used in `lead-form.html`)
- **Hausmeisterservice Sykora:** `754f32de-bf1c-412e-9c7b-c3c2ecdf1c4a` (used in `kunden/sykora/index.html`)

---

## Development

No build, lint, or test commands. To develop:
1. Open any `.html` file directly in a browser, or use a local server (`npx serve .`)
2. The site is deployed via Vercel — push to `main` to deploy

## Language

All user-facing content is in German. Code comments and variable names mix German and English.

---

## Resolved Issues

1. ~~**Twilio credentials exposed client-side**~~ — Fixed: Twilio auth token rotated, all SMS sending moved to edge functions using service role key. No credentials in client code.
2. ~~**Overly permissive RLS policies**~~ — Fixed: RLS tightened on `tenants`, `leads`, `onboarding_requests`, and `interessenten` tables. Anon access restricted to minimum needed.
3. ~~**`interessenten` table has no RLS**~~ — Fixed: RLS enabled with anon INSERT only.
4. ~~**Duplicate jsPDF CDN includes**~~ — Fixed: Removed duplicate 2.5.1 include, keeping only 2.5.2.
5. ~~**Phone number formatting duplicated**~~ — Fixed: Unified to `formatPhone()` function across all files.

## Known Issues & Technical Debt

1. **`activities` table unused** — Schema exists but no data, no code writes to it. Planned for future activity tracking.
2. **`send_followup_notifications()` only sets timestamps** — Does not actually send SMS/emails. The actual sending must be triggered separately or is manual.
3. **Dashboard is hardcoded for Sykora** — Offer editor defaults, logo, and review URL are specific to Hausmeisterservice Sykora. Multi-tenant offer generation needs per-tenant config.
4. **No mobile nav for admin tabs** — Mobile nav is built dynamically but the header nav is hidden on mobile.
5. **All pages are single monolithic HTML files** — No code splitting or shared components. Changes to common elements (nav, footer) must be replicated across files.
