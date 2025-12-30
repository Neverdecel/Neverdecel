# Technical Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Kubernetes                           │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │   FastAPI App   │  │   Static Assets │                  │
│  │   (Backend)     │  │   (Tailwind CSS)│                  │
│  └────────┬────────┘  └─────────────────┘                  │
│           │                                                 │
│           │ HTMX                                            │
│           ▼                                                 │
│  ┌─────────────────┐                                       │
│  │  Google ADK     │◄──── Gemini API                       │
│  │  (Ava Agent)    │                                       │
│  └─────────────────┘                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
neverdecel/
├── docs/                    # Documentation
│   ├── PROJECT.md
│   ├── AVA.md
│   └── ARCHITECTURE.md
├── image/                   # Brand assets
│   └── neverdecel.jpeg
├── src/
│   ├── app/
│   │   ├── main.py          # FastAPI application
│   │   ├── routes/
│   │   │   ├── pages.py     # HTML page routes
│   │   │   └── api.py       # HTMX endpoints
│   │   └── ava/
│   │       ├── agent.py     # Google ADK agent
│   │       └── prompts.py   # System prompts & personality
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html
│   │   └── components/
│   │       ├── terminal.html
│   │       └── projects.html
│   └── static/
│       ├── css/
│       │   └── styles.css   # Tailwind output
│       └── js/
│           └── terminal.js  # Terminal interaction
├── k8s/                     # Kubernetes manifests
│   ├── deployment.yaml
│   ├── service.yaml
│   └── ingress.yaml
├── Dockerfile
├── requirements.txt
├── tailwind.config.js
└── README.md
```

---

## Component Details

### Frontend (HTMX + Tailwind)

**Why HTMX:**
- Hypermedia-driven, no heavy JS framework
- Perfect for the terminal interaction pattern
- Fast, lightweight, progressive enhancement
- Demonstrates alternative to SPA bloat

**Key Features:**
- `hx-post` for Ava chat interactions
- `hx-swap` for seamless content updates
- CSS transitions for terminal effects

### Backend (FastAPI)

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Landing page |
| POST | `/api/ava/chat` | Send message to Ava |
| GET | `/api/projects` | Fetch project list (HTMX partial) |

### AI Layer (Google ADK + Gemini)

**Agent Configuration:**
- Model: Gemini Pro (or latest available)
- Temperature: 0.8 (for personality)
- System prompt: Loaded from `prompts.py`
- Context: Project data, personality guidelines

---

## Deployment

### Kubernetes Resources

1. **Deployment**: FastAPI container with Ava agent
2. **Service**: ClusterIP exposing port 8000
3. **Ingress**: TLS termination, routing to neverdecel.com

### Environment Variables

```
GEMINI_API_KEY=<google-api-key>
ENVIRONMENT=production
LOG_LEVEL=info
```

### CI/CD Pipeline

```
Push → Build Image → Run Tests → Push to Registry → Deploy to K8s
```

---

## Design System: Synthwave Hacker Professional

The visual language balances synthwave aesthetics with hacker authenticity—bold enough to stand out, refined enough to be taken seriously.

### Design Tokens

#### Color Palette

```css
/* Core Backgrounds */
--bg-void: #050508;           /* Deepest black, for hero sections */
--bg-primary: #0a0a0f;        /* Main background */
--bg-surface: #1a1a2e;        /* Cards, containers */
--bg-elevated: #252542;       /* Hover states, active elements */

/* Neon Accents (use sparingly) */
--neon-magenta: #ff00ff;      /* Primary CTA, key interactive elements */
--neon-cyan: #00ffff;         /* Secondary accent, links, highlights */
--neon-purple: #8b5cf6;       /* Tertiary, subtle accents */

/* Glow Variants (for box-shadow, text-shadow) */
--glow-magenta: rgba(255, 0, 255, 0.5);
--glow-cyan: rgba(0, 255, 255, 0.4);
--glow-purple: rgba(139, 92, 246, 0.4);

/* Text Hierarchy */
--text-primary: #f0f0f0;      /* Main content, high readability */
--text-secondary: #b0b0b0;    /* Supporting text */
--text-muted: #666666;        /* Timestamps, metadata */
--text-accent: var(--neon-cyan); /* Links, emphasis */

/* Terminal Specific */
--terminal-green: #39ff14;    /* Success states, output */
--terminal-amber: #ffb000;    /* Warnings, prompts */
--terminal-red: #ff3366;      /* Errors */

/* Borders */
--border-subtle: rgba(255, 255, 255, 0.1);
--border-neon: var(--neon-cyan);
```

#### Typography

| Role | Font | Weight | Usage |
|------|------|--------|-------|
| **Display** | JetBrains Mono | 700 | Hero text, section headings |
| **Headings** | JetBrains Mono | 600 | H1-H3, important labels |
| **Body** | Inter | 400/500 | Paragraphs, descriptions |
| **Terminal** | Fira Code | 400 | All terminal UI, code blocks |
| **UI** | Inter | 500 | Buttons, navigation |

**Font Loading Strategy:**
```html
<!-- Preload critical fonts -->
<link rel="preload" href="/fonts/JetBrainsMono-Bold.woff2" as="font" crossorigin>
<link rel="preload" href="/fonts/FiraCode-Regular.woff2" as="font" crossorigin>
```

#### Spacing Scale

```css
--space-xs: 0.25rem;   /* 4px */
--space-sm: 0.5rem;    /* 8px */
--space-md: 1rem;      /* 16px */
--space-lg: 1.5rem;    /* 24px */
--space-xl: 2rem;      /* 32px */
--space-2xl: 3rem;     /* 48px */
--space-3xl: 4rem;     /* 64px */
```

### Visual Effects

#### Glow Effects (Professional Application)

```css
/* Subtle button glow on hover */
.btn-primary:hover {
  box-shadow: 0 0 20px var(--glow-magenta), 0 0 40px var(--glow-magenta);
}

/* Terminal cursor glow */
.cursor {
  box-shadow: 0 0 8px var(--neon-cyan);
  animation: pulse 1s ease-in-out infinite;
}

/* Text glow for emphasis (use rarely) */
.text-glow {
  text-shadow: 0 0 10px var(--glow-cyan);
}
```

#### Scan Lines (Subtle)

```css
.scanlines::after {
  content: '';
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(
    0deg,
    rgba(0, 0, 0, 0.1) 0px,
    rgba(0, 0, 0, 0.1) 1px,
    transparent 1px,
    transparent 2px
  );
  pointer-events: none;
  opacity: 0.3; /* Keep subtle */
}
```

#### Grid Background

```css
.grid-bg {
  background-image:
    linear-gradient(var(--border-subtle) 1px, transparent 1px),
    linear-gradient(90deg, var(--border-subtle) 1px, transparent 1px);
  background-size: 50px 50px;
  background-position: center;
}
```

### Component Patterns

#### Terminal Container

```css
.terminal {
  background: var(--bg-surface);
  border: 1px solid var(--border-neon);
  border-radius: 8px;
  box-shadow: 0 0 30px rgba(0, 255, 255, 0.1);
  font-family: 'Fira Code', monospace;
}

.terminal-header {
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-subtle);
  padding: var(--space-sm) var(--space-md);
}
```

#### Cards (Project Showcase)

```css
.project-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  transition: all 0.3s ease;
}

.project-card:hover {
  border-color: var(--neon-purple);
  box-shadow: 0 0 20px var(--glow-purple);
  transform: translateY(-2px);
}
```

### Animation Guidelines

| Type | Duration | Easing | Usage |
|------|----------|--------|-------|
| **Micro** | 150ms | ease-out | Button hover, focus states |
| **UI** | 300ms | ease-in-out | Card hover, menu open |
| **Terminal** | 50ms/char | linear | Typing animation |
| **Page** | 500ms | ease-out | Section transitions |

**Rule**: If an animation doesn't serve UX (feedback, context, delight), remove it.

### Accessibility Requirements

- Minimum contrast ratio: 4.5:1 for body text, 3:1 for large text
- All interactive elements must have visible focus states
- Animations respect `prefers-reduced-motion`
- Neon effects have sufficient contrast against backgrounds

---

## Performance Targets

- **First Contentful Paint**: < 1.5s
- **Time to Interactive**: < 2.5s
- **Lighthouse Score**: > 90
- **Ava Response Time**: < 2s (streaming preferred)
