# Naukri Auto-Apply

Automated job application bot for Naukri.com using browser-use.

## Features

- AI-powered visual browser automation via browser-use
- Automated Easy Apply for Naukri.com internal applications
- External ATS form detection and auto-fill (Greenhouse, Lever, Workday, custom)
- Real-time CSV logging of all application attempts
- Session persistence (log in once, reuse session)
- Configurable via YAML + environment variables
- Graceful error handling (continues on individual failures)

## Prerequisites

- Python 3.11+
- A Naukri.com account with profile and resume set up
- Your resume as a PDF file
- A Groq API key (for LLM-powered automation)

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd computer_use

# Set Python version
pyenv local 3.11.15

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install the package with dependencies
pip install -e '.[dev]'
```

## Configuration

This project uses a two-layer configuration approach:

- **YAML file** (`config.yaml`) - All application settings, user profile, and browser options
- **Environment file** (`.env`) - Secrets only (email and password)

Credentials set in `.env` override those in `config.yaml`.

### Step 1: Create config.yaml

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` and fill in your profile details.

### Step 2: Create .env

```bash
cp .env.example .env
```

Edit `.env` and set your Naukri.com credentials and Groq API key.

### Configuration Reference

| Field | Description | Default |
|-------|-------------|---------|
| `user_profile.name` | Your full name as shown on applications | (required) |
| `user_profile.email` | Your email address | (required) |
| `user_profile.phone` | Phone number with country code | (required) |
| `user_profile.resume_path` | Path to your resume PDF file | (required) |
| `user_profile.linkedin_url` | Your LinkedIn profile URL | `null` |
| `user_profile.experience_years` | Total years of experience | `null` |
| `user_profile.current_company` | Your current employer name | `null` |
| `user_profile.current_designation` | Your current job title | `null` |
| `user_profile.notice_period` | Notice period (e.g., "30 days") | `null` |
| `naukri_email` | Naukri.com login email | (from .env) |
| `naukri_password` | Naukri.com login password | (from .env) |
| `output_csv` | Path for the application results CSV | `applications.csv` |
| `headless` | Run browser without visible window | `false` |
| `slow_mo` | Delay between actions in milliseconds | `100` |
| `user_data_dir` | Directory for browser session data | `.browser_data` |

> **Note:** Credentials in `.env` (NAUKRI_EMAIL, NAUKRI_PASSWORD) override those in `config.yaml`.

## Usage

### First run - verify session

```bash
python -m naukri_apply check-session -c config.yaml
```

If the output shows "NOT logged in", run with `headless: false` in your config, manually log in to Naukri.com in the browser window, and the session will persist for future runs.

### Apply to jobs from a URLs file

```bash
python -m naukri_apply apply -c config.yaml -f urls.txt
```

### Apply to a single URL

```bash
python -m naukri_apply apply -c config.yaml -u "https://www.naukri.com/job-listings-software-engineer-company-city-1-to-3-years-123456789"
```

### Apply to multiple URLs

```bash
python -m naukri_apply apply -c config.yaml -u URL1 -u URL2
```

## Input Format

The URLs file should contain one Naukri.com job listing URL per line:

- Lines starting with `#` are treated as comments
- Empty lines are ignored

Example:

```text
# Backend roles
https://www.naukri.com/job-listings-software-engineer-acme-corp-bangalore-3-to-5-years-123456789
https://www.naukri.com/job-listings-senior-developer-techco-mumbai-5-to-8-years-987654321

# Frontend roles
https://www.naukri.com/job-listings-react-developer-startup-pune-2-to-4-years-111222333
```

See `sample_urls.txt` for a template.

## Output - Application Log

All application attempts are logged to a CSV file (default: `applications.csv`) in real-time.

### Column Headers

```
timestamp,company_name,job_title,location,url,apply_type,status,notes
```

### Sample Rows

```csv
timestamp,company_name,job_title,location,url,apply_type,status,notes
2024-01-15T10:30:00,Acme Corp,Software Engineer,Bangalore,https://www.naukri.com/job-listings-...,easy_apply,applied,
2024-01-15T10:31:15,TechCo,Senior Developer,Mumbai,https://www.naukri.com/job-listings-...,external,external_partial,Filled name and email on Greenhouse form
2024-01-15T10:32:00,StartupXYZ,React Developer,Pune,https://www.naukri.com/job-listings-...,easy_apply,failed,Apply button not found
```

### Status Values

| Status | Meaning |
|--------|---------|
| `applied` | Application submitted successfully |
| `failed` | Application could not be completed |
| `skipped` | Job was skipped (e.g., unknown apply type) |
| `external_partial` | External form was partially filled but may need manual completion |
| `direct_applied` | Applied directly on the company's career page |

### Using the CSV for follow-up

The CSV file can be opened in any spreadsheet application. Use it to:
- Track which companies you have applied to
- Follow up on LinkedIn with recruiters at those companies
- Identify failed applications to retry manually

## Architecture

| Module | Responsibility |
|--------|---------------|
| `main.py` | CLI entry point (Click) |
| `config.py` | Configuration loading from YAML + environment variables |
| `models.py` | Data models (Pydantic) for user profile, job listings, and results |
| `browser.py` | Browser session management via browser-use |
| `agent.py` | AI-powered job application agent using browser-use Agent |
| `logger.py` | Real-time CSV logging |

## Security Notes

- Never commit `.env` or `config.yaml` with real credentials
- `.gitignore` already excludes these files
- Session data is stored in `.browser_data/` (also gitignored)
- Resume PDF path should be absolute or relative to the working directory
- Keep your `.env` file readable only by your user (`chmod 600 .env`)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "NOT logged in" | Run with `headless: false` in config, manually log in to Naukri.com in the browser window. The session persists in `.browser_data/`. |
| Timeouts | Increase `slow_mo` in config.yaml. Check your internet connection. |
| Agent failures | Check Groq API key is set correctly. Increase `max_steps` in config if tasks are timing out. |
| External apply failures | External sites vary widely. `external_partial` status is expected for many sites. |
| Import errors | Make sure you installed with `pip install -e '.[dev]'` and activated your venv. |

## Limitations & Disclaimer

- This tool is for personal use to save time on repetitive applications
- Respect Naukri.com's Terms of Service and rate limits
- External ATS form filling is best-effort (sites vary too much for 100% coverage)
- The tool does not solve CAPTCHAs
- Use responsibly and at your own risk

## Development

### Running tests

```bash
pytest tests/ -v
```

### Project structure

This project uses a `src` layout managed by `pyproject.toml`. Install in editable mode for development:

```bash
pip install -e '.[dev]'
```
