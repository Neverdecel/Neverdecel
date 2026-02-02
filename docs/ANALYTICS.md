# Analytics

Custom privacy-focused analytics for neverdecel.com.

## Features

- **Server-side tracking** - All pageviews tracked via FastAPI middleware
- **Project click tracking** - See which portfolio tiles get clicked
- **Outbound link tracking** - Know when visitors click to external sites
- **UTM parameter capture** - Track campaign sources (`?utm_source=linkedin`)
- **Full referrer URLs** - See exactly where traffic comes from
- **Bot filtering** - Automatic detection and exclusion of crawlers/bots
- **Geo lookup** - Country/city from IP using ip-api.com
- **Session tracking** - 30-minute session windows with entry/exit pages
- **Admin dashboard** - Password-protected at `/admin/analytics`

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANALYTICS_PASSWORD` | Yes | Password for admin dashboard login |

Example:
```bash
export ANALYTICS_PASSWORD="your-secure-password"
```

## Data Storage

Analytics data is stored in SQLite at `data/analytics.db`. The `data/` directory is:
- Git-ignored (not committed to repo)
- Mounted as a Docker volume for persistence

### Tables

- `pageviews` - Every tracked page request
- `events` - Custom frontend events
- `sessions` - Visitor sessions (30-min window)
- `admin_sessions` - Dashboard login sessions

## Admin Dashboard

Access at: `/admin/analytics`

Shows:
- Live visitor count
- Pageviews & unique visitors over time
- Top pages, referrers, countries
- Browser/OS/device breakdown
- Custom events
- Bot traffic (excluded from main stats)
- Recent visitor activity

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              FastAPI Middleware                     │
│  - Intercepts all requests                          │
│  - Extracts: path, user-agent, IP, referrer         │
│  - Looks up geo data (async)                        │
│  - Stores in SQLite                                 │
└─────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│              Optional Frontend JS                   │
│  - Tracks custom events (Ava chat interactions)     │
│  - Uses navigator.sendBeacon() for reliability      │
│  - ~15 lines in terminal.js                         │
└─────────────────────────────────────────────────────┘
```

## Excluded from Tracking

- `/health` - Health check endpoint
- `/favicon.ico`, `/robots.txt`, `/sitemap.xml`
- `/static/*` - Static assets
- `/image/*` - Image files
- `/admin/analytics/*` - Dashboard itself
- `/_*` - Internal routes
- Bot/crawler requests (detected via user-agent)

## UTM Tracking

Add UTM parameters to links you share to track their performance:

```
https://neverdecel.com/?utm_source=linkedin&utm_medium=post&utm_campaign=job-hunt
https://neverdecel.com/?utm_source=twitter&utm_medium=bio
https://neverdecel.com/?utm_source=resume&utm_medium=pdf
```

Tracked parameters:
- `utm_source` - Where the traffic comes from (linkedin, twitter, email)
- `utm_medium` - Marketing medium (post, bio, signature)
- `utm_campaign` - Campaign name (job-hunt, networking)
- `utm_content` - Differentiates similar content
- `utm_term` - Paid search keywords

## What Gets Tracked

| Data | How |
|------|-----|
| Page views | Server-side middleware (automatic) |
| Project clicks | Frontend JS on `.project-card` elements |
| Outbound clicks | Frontend JS on external links |
| Ava chat usage | Frontend JS on form submit |
| Visitor identity | IP address |
| Location | IP geolocation lookup |
| Device info | User-agent parsing |
| Traffic source | Referrer header + UTM params |

## Deployment

The analytics module is automatically enabled. Just ensure:

1. Set environment variable:
   ```bash
   ANALYTICS_PASSWORD=your-password
   ```

2. Mount the data volume (Docker):
   ```yaml
   volumes:
     - ./data:/app/data
   ```

3. Access dashboard at `/admin/analytics`
