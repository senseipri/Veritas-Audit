param(
  [switch]$ApiOnly
)

$ErrorActionPreference = "Stop"

Write-Host "Starting Veritas (API + optional dashboard)..."

if (Test-Path ".env") {
  Write-Host "Loading .env via python-dotenv (handled by app)."
} else {
  Write-Host "No .env found. Copy .env.example to .env and set keys."
}

if ($ApiOnly) {
  uvicorn src.api:app --reload
  exit 0
}

Start-Process powershell -ArgumentList "-NoExit", "-Command", "uvicorn src.api:app --reload"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "streamlit run app.py"
Write-Host "Launched API + Streamlit in separate terminals."

