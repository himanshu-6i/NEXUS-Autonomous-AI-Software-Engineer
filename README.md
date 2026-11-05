<truncated 27 lines>
    Workspace --> GitHub[GitHub API]
    Reviewer --> PR[Pull Request]
```

## Agent Responsibilities
- **Planner Agent:** Creates the JSON execution plan containing steps, files to modify, tests to run, and risks.
- **Researcher Agent:** Understands the repo context, dependencies, and similar implementations to guide the Coder.
- **Coding Agent:** Makes the actual source code modifications in a temporary sandbox.
- **Test Agent:** Identifies and runs tests in a sandbox environment securely, producing a parsed report.
- **Debugger Agent:** Analyzes any test failures and triggers the Coding Agent to fix them, maintaining a max 3-retry bounded loop.
- **Reviewer Agent:** Acts as an independent quality gate, evaluating the diff against correctness, test quality, maintainability, scope, and security before final approval.
- **PR Agent:** Integrates directly with GitHub to construct branches, commit validated changes via the Git Tree API without local Git clones, scans for embedded secrets (e.g., .env keys), and produces a detailed Pull Request.

## Persistence
NEXUS uses **Google Cloud Firestore** to store durable execution history, workflow stage transitions, agent artifacts (structured responses, not raw files), debug history logs, and test results.
The frontend surfaces this through the **Execution History** panel, allowing users to trace older sessions and workflows without relying solely on ephemeral frontend browser state. All stored credentials or secrets are strictly blocked and redacted by a backend filter before insertion into the DB.

## Production Deployment (Cloud Run)
NEXUS is designed to be deployed securely via Google Cloud Run, utilizing Application Default Credentials and Secret Manager for configuration without exposing secrets.

### Prerequisites
1. Create a Google Cloud Project with billing enabled.
2. Enable APIs: `run.googleapis.com`, `cloudbuild.googleapis.com`, `firestore.googleapis.com`, `secretmanager.googleapis.com`.
3. Create a Native Firestore database.
4. Add your secrets to Secret Manager (named `gemini-api-key` and `github-token`).

### Backend Deployment
Deploy the backend using the provided scripts (requires `gcloud` CLI):
```bash
# MacOS/Linux
./deploy.sh <YOUR_GCP_PROJECT_ID> <YOUR_REGION>

# Windows PowerShell
.\deploy.ps1 -ProjectId <YOUR_GCP_PROJECT_ID> -Region <YOUR_REGION>
```

**Security & Resource Controls Enforced in Deployment:**
- Automatically uses Google Service Accounts/ADC for Firestore connection without JSON keys.
- Container executes as a non-root `appuser`.
- Enforces a concurrency limit of 80 requests per instance.
- Limits execution timeout to 300 seconds.
- Minimum 0 instances (scale to zero), Maximum 10 instances (protects against runaway costs).
- Prevents CORS attacks by using a configurable `ALLOWED_ORIGINS` environment parameter.
- Binds secrets exclusively at runtime via Secret Manager mount. No secrets are copied into the Docker image.

### Frontend Deployment
The frontend can be deployed to Vercel, Firebase Hosting, or Cloud Run.
Before building, ensure the `.env` specifies the new backend API URL securely:
```env
NEXT_PUBLIC_API_URL="https://your-cloud-run-backend-url/api"
```
Then, update the Cloud Run backend's `ALLOWED_ORIGINS` to accept your frontend's real domain:
```bash
gcloud run services update nexus-backend --update-env-vars ALLOWED_ORIGINS="https://your-frontend-domain.com"
```

## Tech Stack
- **Frontend:** Next.js (App Router), React, Tailwind CSS
- **Backend:** FastAPI, Python, Pydantic
- **AI/LLM:** Google Gemini SDK (`google-genai`), `PromptOrchestrator` for structured generation
- **Agents:**
  - **Planner Agent:** Understands the task, retrieves context, and produces an actionable, grounded implementation plan without hallucinating details.
  - **Coding Agent:** Makes the actual source code modifications in a temporary sandbox.
  - **Test Agent:** Intelligently detects test frameworks, applies a strict command execution policy (anti shell-injection), and runs targeted tests against the temporary workspace with resource timeouts, parsing the output to a structured format.
  - **Debugger Agent:** Automatically inspects failed test results, proposes fixes with Gemini, applies them securely, and runs a strict, bounded retry loop (up to 3 attempts) to fix tests without getting stuck in infinite loops.
  - **Reviewer Agent:** An independent quality gate that scores changes based on scope, maintainability, tests, correctness, and security. Automatically overrides LLM approvals to BLOCK if tests are failing or critical security issues are detected.
- **Services:** 
  - `LLMService`: Singleton wrapper for Gemini.
  - `GitHubService`: Handles fetching metadata, file trees, and downloading repository tarballs securely.
  - `RetrievalService`: Implements Lightweight Code RAG (Keyword/Lexical Chunking & Indexing).
  - `FirestoreService`: Interfaces safely with DB tracking using server-side timestamps.

## Local Setup
1. Clone the repository.
2. Setup Environment Variables:
   Copy `.env.example` to `.env` and fill in the required values.
3. Install frontend dependencies:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
4. Install backend dependencies:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   uvicorn api.main:app --reload
   ```
5. Test the AI integration:
   NEXUS now includes a test endpoint for the Gemini integration.
   You can test it via the frontend dashboard or by sending a request:
   ```bash
   curl -X POST "http://localhost:8000/api/ai/test" \
        -H "Content-Type: application/json" \
        -d '{"prompt": "Explain what a software repository is in three steps."}'
   ```
6. Test the GitHub integration:
   You can analyze a repository via the frontend dashboard or via API:
   ```bash
   curl -X POST "http://localhost:8000/api/github/analyze" \
        -H "Content-Type: application/json" \
        -d '{"repository": "facebook/react"}'
   ```
7. Test the Lightweight Code RAG (Repository Retrieval):
   ```bash
   curl -X POST "http://localhost:8000/api/repository/retrieve" \
        -H "Content-Type: application/json" \
        -d '{"repository": "facebook/react", "query": "function useState", "top_k": 3}'
   ```

## Environment Variables
See `backend/.env.example` and `frontend/.env.example`. You will need:
- `GEMINI_API_KEY`: API key for Google Gemini (Required for the `google-genai` SDK)
- `GITHUB_TOKEN`: Optional, but highly recommended GitHub access token for repository operations to avoid strict rate limits.
- `GOOGLE_CLOUD_PROJECT`: Your GCP project ID
- `FIRESTORE_DATABASE`: The name of the Firestore database

## Docker
Build the container:
```bash
cd backend
docker build -t nexus-backend .
```
Run the container locally:
```bash
docker run -p 8080:8080 --env-file .env nexus-backend
```
Test health endpoint:
```bash
curl http://localhost:8080/health
```

## Security Model
NEXUS executes all AI-generated code and test commands inside an isolated temporary workspace. The system enforces execution time limits, restricts commands, and NEVER exposes the user's main environment or API credentials to the AI execution sandbox. Modifications are pushed via new branches to GitHub ONLY after explicit user approval.

## Known Limitations
- Vector search (RAG) is lightweight and initially relies on text file indexing rather than a dedicated vector database.
- Agent retries are capped at a safe maximum (e.g., 3 retries).
- Deployment requires `gcloud` CLI.

## Future Improvements
- Deeper integration with Google Cloud Pub/Sub for highly distributed agent orchestration.
- Integration of a dedicated Vector Database for massive monorepos.
