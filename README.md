# LaunchLoop — AI Workshop Growth Engine

LaunchLoop is a local Streamlit application for planning and simulating growth for NxtWave's free online workshop, **Build Your First AI Project in 60 Minutes**. It demonstrates how a growth team could track registrations, compare acquisition channels, inspect referral attribution, and explore message variants against a 500-registration goal and hypothetical ₹2,000 budget.

## Simulation notice

This is a product and analytics simulation. Sample data is synthetic, manual entries are demo records, experiment metrics are hypothetical, and no campaign has been executed. The application does not contact students, send messages, make payments, or spend real money. Sample emails use the reserved `.invalid` domain. Do not enter real student personal information.

## Features

- Growth overview with registration, target, progress, channel, referral, and daily metrics.
- SQLite-backed registration tracker with email validation, duplicate prevention, filters, and CSV export.
- Idempotent sample-data loading and confirmation-gated removal of sample rows only.
- Referral code creation and validation, attribution leaderboard, and registration capture.
- Editable, explicitly simulated A/B funnel metrics with safe CTR and conversion calculations.
- Local template-based campaign copy for WhatsApp, email, college clubs, and social media.
- Editable channel targets and budget allocation, a seven-day schedule, and separately stored simulated spend.
- No paid APIs, API keys, or third-party hosted backend.

## Technology

Python 3.11+, Streamlit, SQLite, Pandas, Plotly, and pytest for tests. The interface uses Streamlit's native widgets and Plotly charts. Campaign copy generation uses local templates rather than a live AI model.

## Project structure

```text
launchloop/
├── app.py
├── database.py
├── growth_metrics.py
├── referral_manager.py
├── campaign_generator.py
├── requirements.txt
├── README.md
├── .gitignore
├── sample_data/
│   └── sample_registrations.csv
└── tests/
    ├── test_database.py
    ├── test_growth_metrics.py
    └── test_campaign_generator.py
```

## Deploying on Streamlit Community Cloud

Push the application source to a GitHub repository, then create an app in Streamlit Community Cloud using `app.py` as the entry point and the repository root as the app directory. Cloud installs the Python packages listed in `requirements.txt`. Keep `app.py`, the four application modules, and `sample_data/sample_registrations.csv` in the repository; the SQLite database file is created and initialized automatically on startup.

The app stores registrations and editable simulation values in `launchloop.db` beside `database.py`. Community Cloud's local filesystem is temporary: database changes can be lost when the app restarts or is redeployed, and local SQLite is not a durable shared database for multiple app instances. The checked-in database file is not required for deployment. Use this deployment only for the existing demo/simulation data; do not rely on it for durable records or enter real student personal information.

## Windows setup

Open PowerShell in this project folder. Python 3.11 or newer must be installed and available as `py`.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

If PowerShell blocks environment activation, either use `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` for the current terminal session, or run the environment's executable directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Streamlit prints a local URL, normally `http://localhost:8501`.

## Database and demo data

On first launch, SQLite initializes `launchloop.db` beside `app.py`. The file is local and ignored by Git. Five fictional ambassador codes, two message variants, and the initial channel plan are seeded idempotently. Registration samples are loaded only when the user clicks **Load synthetic sample data**; duplicate emails are skipped on subsequent loads. **Reset sample data** removes only rows with the sample source, leaving manual simulations intact.

## Metrics and assumptions

- Target progress and remaining registrations use the 500-registration objective.
- The initial channel plan allocates 200 + 150 + 100 + 50 registration targets and budgets ₹0 + ₹0 + ₹0 + ₹1,500, with a separate ₹500 contingency reserve.
- ₹0 organic allocations assume existing student communities and volunteer distribution; they do not imply zero operational effort or cost.
- Simulated spend is an editable local demo value, separate from planned budget. It is not a real transaction.
- Referral attribution is based on the code stored with the registration. Unique email is the basic duplicate guard.
- Experiment reach, clicks, and registrations are user-entered hypothetical inputs. A higher conversion callout requires at least 20 clicks per variant and is descriptive only; no statistical significance is calculated.
- Daily charts use saved registration timestamps. The date and channel filters affect chart views; headline KPIs remain all-time totals.

## Tests

```powershell
python -m pytest -q
```

## Limitations and future improvements

The app is intended for a single-user local demonstration, not production collection of personal data. It has no authentication, multi-user access control, real campaign integrations, scheduling, or statistical experiment analysis. Possible next steps include a stricter role/access model, an auditable event history, privacy-reviewed production data handling, configurable campaign dates, and a vetted integration layer for a real registration platform.