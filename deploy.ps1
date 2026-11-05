param (
    [Parameter(Mandatory=$true)]
    [string]$ProjectId,
    
    [Parameter(Mandatory=$true)]
    [string]$Region
)

$ErrorActionPreference = "Stop"
$ServiceName = "nexus-backend"

Write-Host "Deploying NEXUS Backend to Google Cloud Run..."
Write-Host "Project: $ProjectId"
Write-Host "Region: $Region"

gcloud config set project $ProjectId

Write-Host "Checking secrets..."
try {
    gcloud secrets describe gemini-api-key *>&1 | Out-Null
} catch {
    Write-Host "Creating gemini-api-key secret..."
    gcloud secrets create gemini-api-key --replication-policy="automatic"
}

try {
    gcloud secrets describe github-token *>&1 | Out-Null
} catch {
    Write-Host "Creating github-token secret..."
    gcloud secrets create github-token --replication-policy="automatic"
}

Write-Host "IMPORTANT: Make sure you have added versions to the 'gemini-api-key' and 'github-token' secrets in GCP!"
Start-Sleep -Seconds 5

Write-Host "Deploying Cloud Run service..."
gcloud run deploy $ServiceName `
    --source backend/ `
    --region $Region `
    --platform managed `
    --allow-unauthenticated `
    --memory 512Mi `
    --cpu 1 `
    --min-instances 0 `
    --max-instances 10 `
    --concurrency 80 `
    --timeout 300 `
    --set-env-vars="ENVIRONMENT=production,USE_MOCK_FIRESTORE=false,ALLOWED_ORIGINS=https://nexus-frontend-xxx.web.app" `
    --set-secrets="GEMINI_API_KEY=gemini-api-key:latest,GITHUB_TOKEN=github-token:latest"

Write-Host "======================================================"
Write-Host "DEPLOYMENT COMPLETE"
Write-Host "======================================================"
Write-Host "1. Get the generated backend URL from the output above."
Write-Host "2. Update your frontend's .env NEXT_PUBLIC_API_URL to point to this backend."
Write-Host "3. Update the ALLOWED_ORIGINS environment variable in Cloud Run with your real frontend URL."
