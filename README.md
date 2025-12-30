# Neverdecel Portfolio

A cyberpunk-themed portfolio website for a DevOps & AI Engineer, featuring Ava - an AI assistant powered by Google Gemini.

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: HTMX + Tailwind CSS
- **AI**: Google Gemini API
- **Container**: Docker

## Quick Start

### Prerequisites

- Python 3.12+
- Google Gemini API key

### Local Development

1. **Clone and setup environment**

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env from example
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

2. **Run the development server**

```bash
uvicorn src.app.main:app --reload --port 8000
```

3. **Open in browser**

Visit [http://localhost:8000](http://localhost:8000)

### Docker Development

```bash
# Build and run
docker-compose up --build

# Or with hot reload
docker-compose --profile dev up --build
```

## Project Structure

```
neverdecel/
├── src/
│   ├── app/
│   │   ├── main.py           # FastAPI application
│   │   ├── config.py         # Settings
│   │   ├── routes/           # API routes
│   │   └── ava/              # AI agent
│   ├── templates/            # Jinja2 templates
│   └── static/               # CSS/JS assets
├── image/                    # Brand assets
├── docs/                     # Documentation
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GEMINI_API_KEY` | Google Gemini API key | Yes |
| `ENVIRONMENT` | `development` or `production` | No |
| `LOG_LEVEL` | Logging level | No |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Landing page |
| POST | `/api/ava/chat` | Chat with Ava |
| GET | `/health` | Health check |

## Ava Commands

Type these in the terminal:

- `help` - Show available commands
- `projects` - List projects
- `skills` - Technical expertise
- `contact` - Contact info
- `whoami` - Who are you?
- `clear` - Clear terminal

## License

MIT
