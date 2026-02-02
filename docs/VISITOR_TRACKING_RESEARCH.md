# Visitor Tracking Research

## Current State

The Neverdecel portfolio has **no existing analytics or tracking**. The codebase is clean and ready for a fresh implementation.

**Tech Stack:** FastAPI (Python) + HTMX + Jinja2 templates

---

## Why Not Google Analytics?

Valid concerns with GA4:
- **Privacy:** Collects extensive personal data, cross-site tracking
- **GDPR Issues:** Data sent to US servers, legal grey area in EU
- **Cookie Consent Required:** Need annoying cookie banners
- **Complexity:** Over-engineered for simple portfolio sites
- **Data Ownership:** Google owns your data, uses it for advertising
- **Performance:** Heavy script (~45KB) that slows page load

---

## Modern Privacy-First Alternatives

### Tier 1: Self-Hosted Open Source (Recommended)

| Tool | Script Size | Backend | Best For |
|------|-------------|---------|----------|
| **Umami** | ~2 KB | Node.js + PostgreSQL | Easy self-hosting, free |
| **Plausible CE** | ~1 KB | Elixir + ClickHouse | High scale, EU focused |
| **Matomo** | ~22 KB | PHP + MySQL | Full GA replacement |

#### Umami (Top Recommendation)
- **Free forever** when self-hosted
- Single Docker container deployment
- Built-in admin portal with team support
- Custom event tracking
- No cookies, no personal data
- City-level geo tracking (self-hosted)
- Rename tracker script to avoid ad-blockers
- **Perfect fit for FastAPI stack** (can share PostgreSQL)

#### Plausible Community Edition
- Smallest script (1 KB)
- More complex to self-host (Elixir + ClickHouse)
- Higher RAM requirements (~2GB minimum)
- Some features locked to cloud version

### Tier 2: Paid SaaS (Low Effort)

| Tool | Starting Price | Notes |
|------|----------------|-------|
| Plausible Cloud | €9/mo | Hosted, EU servers |
| Fathom | $15/mo | US-based, cookieless |
| Simple Analytics | €9/mo | No IP tracking at all |
| Umami Cloud | Free up to 100K events | Then $20/mo |

---

## Option 3: Build Your Own

### Pros
- Full control and customization
- No third-party dependencies
- Exactly the features you need
- Learning opportunity
- Integrates perfectly with existing FastAPI app

### Cons
- Development time
- Maintenance burden
- Need to build admin portal from scratch
- Edge cases (bots, crawlers, ad-blockers)

### Minimal Custom Implementation

A lean custom tracker needs:

```
┌─────────────────────────────────────────────────────┐
│                   Frontend (Optional)               │
│  - Tiny JS snippet (~500 bytes)                     │
│  - Sends: page URL, referrer, screen size           │
│  - Uses navigator.sendBeacon() for reliability      │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│                   FastAPI Backend                   │
│  - POST /api/track endpoint                         │
│  - Extract: User-Agent, Accept-Language from headers│
│  - Hash IP for unique visitors (privacy-safe)       │
│  - Store in SQLite/PostgreSQL                       │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│                   Admin Portal                      │
│  - Page views over time                             │
│  - Top pages                                        │
│  - Referrers                                        │
│  - Browsers/devices                                 │
│  - Geographic data (from IP geolocation)            │
└─────────────────────────────────────────────────────┘
```

### Server-Side Only Approach (Even Leaner)

Skip JavaScript entirely by tracking in FastAPI middleware:

```python
# Captures every request server-side
# No JS required, works even with blockers
# Limitations: no client-side events, JS interactions
```

---

## Recommendation

### For Minimal Effort: **Umami Self-Hosted**

```yaml
# Add to docker-compose.yml
umami:
  image: ghcr.io/umami-software/umami:postgresql-latest
  environment:
    DATABASE_URL: postgresql://user:pass@db:5432/umami
  ports:
    - "3000:3000"
```

Then add one line to your HTML:
```html
<script defer src="https://your-umami/script.js" data-website-id="xxx"></script>
```

**Time to implement:** ~30 minutes

### For Full Control: **Custom Hybrid Approach**

Build a minimal custom solution:

1. **Server-side middleware** - Catches all page views automatically
2. **Optional tiny JS** (~500 bytes) - For client events (Ava interactions)
3. **Simple admin page** - Add route at `/admin/analytics`
4. **SQLite storage** - Zero additional infrastructure

**Time to implement:** ~4-8 hours for MVP

### Comparison Matrix

| Approach | Setup Time | Maintenance | Features | Privacy |
|----------|------------|-------------|----------|---------|
| Umami | 30 min | Low | Full | Excellent |
| Plausible CE | 2 hours | Medium | Full | Excellent |
| Custom Build | 4-8 hours | Medium | Custom | Full control |
| Paid SaaS | 10 min | None | Full | Good |

---

## Data Points to Track

### Essential (Server-Side)
- Page URL and path
- Timestamp
- Referrer (where they came from)
- User-Agent (browser/device)
- Country (from IP, then discard IP)
- Unique visitor hash (salted IP hash, rotated daily)

### Optional (Client-Side JS)
- Screen dimensions
- Ava chat interactions
- Scroll depth
- Time on page

### Never Collect
- Raw IP addresses (hash immediately)
- Personal identifiers
- Cross-site tracking data
- Cookies for tracking

---

## Next Steps

1. **Decide approach:** Umami vs Custom
2. If Umami: Add to docker-compose, configure
3. If Custom: Create tracking middleware, storage, admin UI
4. Add to templates (script or rely on middleware)
5. Test locally, deploy

---

## Sources

- [Plausible Analytics](https://plausible.io/) - Privacy-focused GA alternative
- [Umami](https://umami.is/) - Open source, self-hosted analytics
- [Fathom Analytics](https://usefathom.com/) - Cookieless tracking
- [Umami vs Plausible Comparison](https://aaronjbecker.com/posts/umami-vs-plausible-vs-matomo-self-hosted-analytics/)
- [Self-Hosted Analytics Comparison](https://www.self-host.app/blogs/self-host-analytics)
- [Server-Side Tracking Introduction](https://dev.to/codesphere/introduction-to-server-side-tracking-2pjc)
- [PostHog Open Source Analytics Tools](https://posthog.com/blog/best-open-source-analytics-tools)
- [Open Source Analytics Overview](https://swetrix.com/blog/open-source-website-analytics)
