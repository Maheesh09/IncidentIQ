"""Issue content for create_issues.py.

Every task from DEVELOPMENT_PLAN.md, as data. Edit freely before publishing.

Placeholders usable in any text field:
  {{ref:KEY}}        link to another issue in this file (rendered as #12 or owner/repo#12)
  {{be:path}}        link to a file in the backend repo   (path may end with #L42)
  {{fe:path}}        link to a file in the frontend repo

Order matters: an issue may only reference issues that appear above it.
Changing a title after publishing creates a duplicate on the next run.
"""

OWNER = "Maheesh09"

REPOS = {
    "backend": {"name": "IncidentIQ", "branch": "main"},
    "frontend": {"name": "IncidentIQ-Frontend", "branch": "master"},
}

# (name, colour, description)
LABELS = [
    ("type: dev", "1D76DB", "Development work: application code"),
    ("type: qa", "FBCA04", "Quality: test plans, automated tests, verification"),
    ("type: devops", "5319E7", "Infrastructure, CI/CD, cloud configuration, repo settings"),
    ("epic", "3E4B9E", "Tracking issue for a roadmap step"),
    ("priority: P0", "B60205", "Security exposure or hard blocker. Do first"),
    ("priority: P1", "D93F0B", "Design gap that blocks the product"),
    ("priority: P2", "E99695", "Correctness or reliability under real load"),
    ("priority: P3", "F9D0C4", "Nice to have, cleanup"),
    ("size: S", "C2E0C6", "Half a day or less"),
    ("size: M", "7BD389", "One to two days"),
    ("size: L", "2DA44E", "Three to five days"),
    ("area: auth", "BFDADC", "Authentication and authorisation"),
    ("area: gcp", "BFDADC", "Google Cloud integration"),
    ("area: ingest", "BFDADC", "Alert ingest"),
    ("area: github", "BFDADC", "GitHub integration"),
    ("area: database", "BFDADC", "Models, migrations, queries"),
    ("area: pipeline", "BFDADC", "Agent pipeline and job execution"),
    ("area: api", "BFDADC", "HTTP endpoints"),
    ("area: ui", "BFDADC", "Frontend screens and components"),
    ("area: ci-cd", "BFDADC", "GitHub Actions, build, deploy"),
    ("area: infra", "BFDADC", "Cloud resources and IAM"),
    ("security", "EE0701", "Security relevant"),
    ("bug", "D73A4A", "Something isn't working"),
    ("documentation", "0075CA", "Improvements or additions to documentation"),
    ("good first issue", "7057FF", "Good for newcomers"),
]

MILESTONES = {
    0: {"title": "Step 0: Repo hygiene and CI",
        "description": "One working branch per repo, protected default branches, CI on every pull request."},
    2: {"title": "Step 2: Firebase authentication",
        "description": "Done when a new user signs up in the browser, creates an organisation, mints an API key, "
                       "and the old admin secret path returns 401."},
    3: {"title": "Step 3: Keyless GCP connection",
        "description": "Done when a GCP project is connected without any key leaving the customer's account, and a "
                       "missing grant produces a clear message."},
    4: {"title": "Step 4: Alert ingest",
        "description": "Done when a test alert policy in a real GCP project produces a completed RCA with no human "
                       "action, and resending the same alert does not create a second incident."},
    5: {"title": "Step 5: GitHub App",
        "description": "Done when the shared PAT is gone and every analysis uses a short lived installation token."},
    6: {"title": "Step 6: Reliability and correctness",
        "description": "Event loop never blocked, no silent secret loss, real timestamps, analyses survive Cloud Run "
                       "CPU throttling, migrations run on deploy."},
    7: {"title": "Step 7: Frontend on real data",
        "description": "Every authenticated screen reads from the backend, with loading, empty and error states."},
    8: {"title": "Step 8: Tests",
        "description": "Auth paths, tenant isolation, ingest dedup and agent nodes covered by tests running in CI."},
}


# Text shared by several QA issues.
MANUAL_QA_RECORD_TASK = "Record results as a comment; open linked bugs."
MANUAL_QA_ACCEPTANCE = "All cases pass or have accepted linked bugs."
AUTOMATED_QA_ACCEPTANCE = "All cases are automated and pass in CI."


ISSUES = [
    # =====================================================================
    # STEP 0: Repo hygiene and CI
    # =====================================================================
    {
        "key": "BE-0.1", "repo": "backend", "type": "devops", "step": 0, "priority": "P1", "size": "S",
        "areas": ["ci-cd"],
        "title": "Consolidate backend branches to main plus one working branch",
        "summary": """
            Merge the last unmerged commit, delete the stale branches, and protect `main`, so it is obvious
            where work happens.
        """,
        "why": """
            Five branches (`main`, `dev`, `dev2`, `dev3`, `prod`) with no unique work on them make it unclear
            where to branch from and where to open pull requests.
        """,
        "current": """
            On `origin`, `dev`, `dev2`, `dev3` and `prod` have zero commits that are not on `main`.
            The **local** `dev2` has one unpushed commit: `afb7c41 fix: upgrade apk packages before adding
            libpq-dev in Dockerfile`. It must reach `main` before any branch is deleted.
        """,
        "tasks": [
            "Push `dev2`, open a PR into `main` for `afb7c41`, merge it, and confirm the Cloud Run deploy is green.",
            "Pick the single working branch. Recommended: keep `dev`, reset it to `main` "
            "(`git push origin main:dev --force-with-lease` after checking it has nothing unique).",
            "For each of the other branches run `git log --oneline origin/main..origin/<branch>`. It must print "
            "nothing. Then `git push origin --delete <branch>`.",
            "Locally: `git fetch --prune` and `git branch -D` the deleted branches.",
            "Add a branch ruleset on `main`: require a pull request, block force pushes and deletion. "
            "Required status checks are added by the next issue (pull request CI) once it exists.",
            "Write the branching rule (feature work on `dev`, PR `dev` to `main`, `main` deploys) in the README.",
        ],
        "acceptance": [
            "`git branch -r` lists only `origin/main` and the chosen working branch.",
            "`afb7c41` is on `main`.",
            "A direct push to `main` is rejected by GitHub.",
        ],
        "commit": "chore(repo): consolidate branches and document branching model",
    },
    {
        "key": "BE-0.2", "repo": "backend", "type": "devops", "step": 0, "priority": "P1", "size": "M",
        "areas": ["ci-cd"],
        "title": "Add pull request CI: lint, import check, migration heads, image scan",
        "summary": "Run fast checks on every pull request so problems are caught before they reach `main` and deploy.",
        "why": """
            {{be:.github/workflows/deploy.yml}} only runs on push to `main`. A broken import, a second Alembic
            head, or a HIGH CVE in the image is only discovered while deploying to production.
        """,
        "tasks": [
            "Create `.github/workflows/ci.yml` triggered on `pull_request` and on push to the working branch.",
            "Set up Python with the same minor version as the `Dockerfile` base image, cache pip, "
            "`pip install -r requirements.txt`.",
            "Add `ruff` (in a new `requirements-dev.txt`) with a minimal `ruff.toml`; run `ruff check .`. "
            "Fix or explicitly ignore existing findings in the same PR.",
            "Import smoke test: `python -c \"import main\"` with dummy env vars "
            "(`DATABASE_URL`, `GEMINI_API_KEY`, `GITHUB_PAT`, `API_KEY_PEPPER`), because `config.Settings()` "
            "is built at import time.",
            "Migration check: `alembic heads` must print exactly one head (fail the job otherwise).",
            "Build the Docker image (no push) and run the same Trivy step as `deploy.yml`.",
            "Pin every action by commit SHA, as `deploy.yml` already does.",
            "Mark the CI job as a required status check in the `main` ruleset.",
        ],
        "acceptance": [
            "A PR with a lint error, a broken import, or two Alembic heads shows a red check and cannot be merged.",
            "A clean PR passes in under 5 minutes.",
        ],
        "files": ["{{be:.github/workflows/deploy.yml}}", "`.github/workflows/ci.yml` (new)", "`requirements-dev.txt` (new)"],
        "depends": ["BE-0.1"],
        "notes": "Pytest and a Postgres service container are added to this workflow in Step 8.",
        "commit": "chore(ci): run lint, import and migration checks on pull requests",
    },
    {
        "key": "FE-0.1", "repo": "frontend", "type": "devops", "step": 0, "priority": "P2", "size": "S",
        "areas": ["ci-cd"],
        "title": "Consolidate frontend branches and protect master",
        "summary": "Keep `master` plus one working branch and protect `master`.",
        "current": "`dev` is fully merged into `master` (`495bd15`). No branch protection.",
        "tasks": [
            "Decide whether `dev` stays as the working branch (reset it to `master`) or is deleted.",
            "Add a ruleset on `master`: require a pull request, block force pushes and deletion.",
            "Document the branching rule in the README, matching the backend.",
        ],
        "acceptance": ["Only `master` and at most one working branch exist.", "Direct pushes to `master` are rejected."],
        "commit": "chore(repo): document branching model",
    },
    {
        "key": "FE-0.2", "repo": "frontend", "type": "devops", "step": 0, "priority": "P1", "size": "S",
        "areas": ["ci-cd"],
        "title": "Add pull request CI: lint, typecheck, build",
        "summary": "Run lint, TypeScript and a production build on every pull request.",
        "current": """
            There is no `.github/workflows` directory. The repo contains **both** `package-lock.json` and
            `bun.lock`, so installs are not reproducible.
        """,
        "tasks": [
            "Pick one package manager. Recommended: npm (CI images have it, `package-lock.json` exists). "
            "Delete the other lockfile and `bunfig.toml` if bun is dropped.",
            "Add `\"typecheck\": \"tsc --noEmit\"` to `package.json` scripts.",
            "Create `.github/workflows/ci.yml`: checkout, setup-node (LTS, npm cache), `npm ci`, "
            "`npm run lint`, `npm run typecheck`, `npm run build`. Pin actions by SHA.",
            "Provide placeholder `VITE_*` env values to the build step so the build does not fail on missing config.",
            "Make the job a required status check on `master`.",
        ],
        "acceptance": [
            "A PR with a type error fails CI.",
            "Exactly one lockfile is committed.",
        ],
        "files": ["{{fe:package.json}}", "`.github/workflows/ci.yml` (new)"],
        "depends": ["FE-0.1"],
        "commit": "chore(ci): lint, typecheck and build on pull requests",
    },

    # =====================================================================
    # STEP 2: Firebase authentication
    # =====================================================================
    {
        "key": "FE-2.0", "repo": "frontend", "type": "devops", "step": 2, "priority": "P1", "size": "S",
        "areas": ["auth", "infra"],
        "title": "Create the Firebase project and enable Email/Password and Google sign-in",
        "summary": "Set up Firebase Authentication so the frontend has an identity provider and the backend has a token audience.",
        "tasks": [
            "Add Firebase to the existing GCP project `incidentiq-prod` (recommended: one project, so the backend's "
            "`FIREBASE_PROJECT_ID` is `incidentiq-prod`). Optionally create a separate project for local development.",
            "Authentication > Sign-in method: enable **Email/Password** and **Google**.",
            "Authentication > Settings > Authorized domains: add `localhost` and the production frontend domain.",
            "Authentication > Settings: turn on **email enumeration protection**.",
            "Set the sender name and the action URL for verification and password reset emails.",
            "Register a Web app and record `apiKey`, `authDomain`, `projectId`, `appId`. These are public "
            "identifiers, not secrets, but keep them in one place (CI variables, password manager).",
        ],
        "acceptance": [
            "A test user can be created from the Firebase console.",
            "The four web config values are available to {{ref:FE-0.2}} CI and to developers.",
        ],
        "notes": """
            Firebase owns identity (passwords, Google sign-in, resets, MFA). Our database owns authorisation
            (which organisation, which role). Do not put `organisation_id` in custom claims: claims only refresh
            with the token, so revocation would lag by up to an hour.
        """,
    },
    {
        "key": "BE-2.0", "repo": "backend", "type": "devops", "step": 2, "priority": "P1", "size": "S",
        "areas": ["auth", "infra"],
        "title": "Configure backend environment for browser clients: Firebase project ID and CORS",
        "summary": "Give the backend the settings it needs to accept browser requests carrying Firebase ID tokens.",
        "tasks": [
            "Add `FIREBASE_PROJECT_ID` to Cloud Run: "
            "`gcloud run services update incidentiq --region us-central1 --update-env-vars FIREBASE_PROJECT_ID=incidentiq-prod`.",
            "Set `CORS_ALLOWED_ORIGINS` to the local dev origin (the port `npm run dev` prints) and the production "
            "frontend origin. The current default in {{be:config.py}} is only `http://localhost:3000`.",
            "Add both variables to `.env.example` with comments.",
        ],
        "acceptance": [
            "A browser `fetch` from the frontend origin passes CORS preflight against the deployed API.",
            "`FIREBASE_PROJECT_ID` is visible in the Cloud Run revision's env.",
        ],
        "files": ["{{be:config.py}}", "{{be:main.py#L65}}"],
        "depends": ["FE-2.0"],
    },
    {
        "key": "BE-2.1", "repo": "backend", "type": "dev", "step": 2, "priority": "P1", "size": "S",
        "areas": ["database", "auth"],
        "title": "Create users table with Alembic migration",
        "summary": "Add a `users` table linking a Firebase identity to an organisation and a role.",
        "tasks": [
            "Add a `User` model next to the other models in {{be:models/incident.py}} "
            "(or a new `models/user.py`, imported wherever Alembic collects metadata in {{be:alembic/env.py}}).",
            "Columns: `id` UUID PK; `firebase_uid` String(128) unique not null; `email` String(320) not null "
            "(store lowercased); `organisation_id` UUID FK `organisations.id`, **nullable** (a user exists before "
            "creating an org); `role` String(20) not null default `'member'` with a CHECK in (`owner`, `member`); "
            "`created_at` **`DateTime(timezone=True)`** server default `now()`.",
            "Do not add new `String(50)` timestamp columns. New tables use `TIMESTAMPTZ` from day one "
            "(old columns are migrated in Step 6).",
            "Index `organisation_id`.",
            "Generate the migration with `alembic revision --autogenerate -m \"create users table\"` and review it by hand.",
        ],
        "acceptance": [
            "`alembic upgrade head` then `alembic downgrade -1` both succeed on a fresh database.",
            "`alembic heads` still shows a single head.",
            "Inserting two users with the same `firebase_uid` fails.",
        ],
        "files": ["{{be:models/incident.py}}", "`alembic/versions/<rev>_create_users_table.py` (new)"],
        "commit": "feat(db): create users table with Alembic migration",
    },
    {
        "key": "BE-2.2", "repo": "backend", "type": "dev", "step": 2, "priority": "P0", "size": "M",
        "areas": ["auth"], "labels": ["security"],
        "title": "Verify Firebase ID tokens without blocking the event loop",
        "summary": "Add a module that validates a Firebase ID token and returns the caller's identity.",
        "why": """
            The middleware will accept Firebase tokens for every human request. Verification must be correct
            (signature and every claim) and must never do synchronous network I/O inside `async def`.
        """,
        "tasks": [
            "Create `utils/firebase_auth.py` exposing `async def verify_id_token(token: str) -> FirebaseIdentity` "
            "where `FirebaseIdentity` is a small dataclass (`uid`, `email`, `email_verified`, `sign_in_provider`).",
            "Recommended implementation: PyJWT (`pyjwt[crypto]`) plus Google's public certs fetched with "
            "`httpx.AsyncClient` from `https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com`.",
            "Cache the certs for the `max-age` in the response's `Cache-Control` header. Guard refresh with an "
            "`asyncio.Lock` so concurrent requests trigger a single fetch. If a token's `kid` is unknown, refetch once.",
            "Validate: `alg == RS256`; signature; `aud == settings.firebase_project_id`; "
            "`iss == https://securetoken.google.com/<project_id>`; `exp` in the future; `iat` and `auth_time` not in "
            "the future (60 s leeway); `sub` non-empty and at most 128 chars.",
            "Add `firebase_project_id: str | None = None` to {{be:config.py}}. If it is unset, reject every token "
            "and log an error (fail closed).",
            "Raise a single `InvalidFirebaseToken` exception. Log the precise reason server side; never return it to the client.",
            "Alternative if preferred: `firebase_admin.auth.verify_id_token`, but it is synchronous, so call it "
            "through `asyncio.to_thread`. Do not use `check_revoked=True` (one network call per request; "
            "revocation is handled by our database).",
        ],
        "acceptance": [
            "A valid token from the Firebase project returns the identity.",
            "Expired, wrong audience, wrong issuer, tampered signature and unknown `kid` tokens all raise.",
            "Under 100 concurrent verifications, Google's cert endpoint is called at most once.",
            "No synchronous HTTP call runs on the event loop (`grep -n 'requests\\.\\|httpx.get' utils/firebase_auth.py` is empty).",
        ],
        "files": ["`utils/firebase_auth.py` (new)", "{{be:config.py}}", "{{be:requirements.txt}}"],
        "depends": ["BE-2.0"],
        "notes": "Independent of the users table, so it can be built in parallel with it. Tests for every rejection path are in Step 8.",
        "commit": "feat(auth): verify Firebase ID tokens",
    },
    {
        "key": "BE-2.3", "repo": "backend", "type": "dev", "step": 2, "priority": "P0", "size": "M",
        "areas": ["auth", "api"], "labels": ["security"],
        "title": "Route requests to API key or Firebase auth in a single middleware",
        "summary": "Extend the auth middleware so humans (Firebase JWT) and machines (API key) can both authenticate, each only where allowed.",
        "current": """
            {{be:middleware/auth.py}} (`APIKeyMiddleware`) rejects anything that does not start with `iqk_live_`.
            The plan's table says `/incidents/*` is API key only, but the browser must read incidents too
            (Step 7), so `/incidents/*` has to accept both.
        """,
        "tasks": [
            "Rename `APIKeyMiddleware` to `AuthMiddleware` (update {{be:main.py#L64}}). Keep the existing API key code path unchanged.",
            "Detect the credential: `Bearer iqk_live_...` goes to the API key path, any other `Bearer` value goes to the Firebase path ({{ref:BE-2.2}}).",
            "Add an explicit route policy (see the table in Notes), evaluated top to bottom, default deny.",
            "Firebase path: look up `users` by `firebase_uid`. Set `request.state.user_id`, `firebase_uid`, `email`, "
            "`email_verified`, `role`, `organisation_id` and `auth_type = \"user\"`. API key path sets `auth_type = \"api_key\"`.",
            "Unknown Firebase user or user without an org: allowed on `/me*` only (the handler creates the row); "
            "elsewhere return 403 `{\"detail\": \"Create an organisation first\"}`.",
            "Inactive organisation: 403 on both paths.",
            "Change the generic 401 text from \"Missing API key\" to \"Missing credentials\".",
            "Leave `ADMIN_BOOTSTRAP_ROUTES` in place for now. It is removed in a later issue of this step.",
            "Check that CORS preflight (`OPTIONS`) still passes: `CORSMiddleware` is added after this middleware, so it is the outer layer.",
        ],
        "acceptance": [
            "API key on `/incidents/{id}`: 200 (unchanged behaviour).",
            "Firebase token on `/incidents/{id}` and `/management/*`: 200 for a user with an org.",
            "API key on `/management/*` or `/me`: 401.",
            "Firebase token for a user without org: 200 on `/me`, 403 on `/incidents`.",
            "`request.state.organisation_id` is set the same way on both paths, so existing routers need no change.",
        ],
        "files": ["{{be:middleware/auth.py}}", "{{be:main.py}}"],
        "depends": ["BE-2.1", "BE-2.2"],
        "notes": """
            Route policy:

            | Prefix | API key | Firebase | Org required |
            |-|-|-|-|
            | `/incidents` | yes | yes | yes |
            | `/management` | no | yes | yes |
            | `/me` | no | yes | no |
            | `/ingest` | no | no | ingest token only (Step 4) |
        """,
        "commit": "feat(auth): verify Firebase ID tokens alongside API keys",
    },
    {
        "key": "BE-2.4", "repo": "backend", "type": "dev", "step": 2, "priority": "P1", "size": "M",
        "areas": ["auth", "api"],
        "title": "Add /me endpoints and user-owned organisation creation",
        "summary": "Let a signed-in person see who they are and create their organisation, becoming its owner.",
        "tasks": [
            "Create `routers/me.py` and register it in {{be:main.py}}.",
            "`GET /me`: upsert the `users` row on first call (uid and email from the token). Return "
            "`{user: {id, email, email_verified, role}, organisation: {id, name} | null}`.",
            "`POST /me/organisation` `{name}`: 409 if the user already has an org. Otherwise, in one transaction, "
            "create `Organisation` (`admin_email` = token email), set `user.organisation_id` and `role = owner`. "
            "No API key is minted here; owners create keys explicitly (next issue).",
            "Require `email_verified` for password sign-ups before creating an org (Google sign-ins are already verified). Return 403 with a clear message.",
            "Decide on organisation name uniqueness. The current 409 on duplicate name in {{be:routers/management.py}} "
            "lets anyone probe which company names are customers. Recommended: drop the unique check (and constraint, if any) for user-created orgs.",
            "Reconcile with the existing `GET /management/organisations/me`: keep it working for Firebase callers or point it at the same code.",
            "Hook point for Step 3: after the org is created, call tenant service account provisioning (best effort, added in Step 3).",
        ],
        "acceptance": [
            "A brand new Firebase user calling `GET /me` gets `organisation: null` and a `users` row now exists.",
            "`POST /me/organisation` makes them `owner`; a second call returns 409.",
            "An unverified password user gets 403 on `POST /me/organisation`.",
        ],
        "files": ["`routers/me.py` (new)", "{{be:routers/management.py}}", "{{be:models/management_schemas.py}}", "{{be:main.py}}"],
        "depends": ["BE-2.3"],
        "commit": "feat(api): add /me endpoints and user-owned organisation creation",
    },
    {
        "key": "BE-2.5", "repo": "backend", "type": "dev", "step": 2, "priority": "P1", "size": "M",
        "areas": ["auth", "api"], "labels": ["security"],
        "title": "API key management under Firebase auth: list, create, revoke",
        "summary": "Move API key minting from the admin bootstrap flow to signed-in owners.",
        "current": "Today the only way to get an API key is `POST /management/organisations` with the admin secret.",
        "tasks": [
            "Add a `require_owner` FastAPI dependency (e.g. `routers/deps.py`) that returns 403 unless `request.state.auth_type == \"user\"` and role is `owner`.",
            "`GET /management/api-keys`: `id, name, key_prefix, created_at, last_used_at, is_active`. Never return `key_hash`.",
            "`POST /management/api-keys` `{name}` (owner): reuse `generate_api_key()` from {{be:utils/auth.py}}, "
            "`hash_version=2`, return the raw key **once**.",
            "`DELETE /management/api-keys/{id}` (owner): set `is_active = 0`. Scope the query by `organisation_id`; "
            "another org's key id returns 404.",
            "Log user id and key prefix for create and revoke.",
        ],
        "acceptance": [
            "An owner can create a key and use it on `/incidents/*` immediately.",
            "A revoked key gets 401 on the next request.",
            "A member gets 403 on create and revoke; can list.",
            "Revoking another org's key id returns 404.",
        ],
        "files": ["{{be:routers/management.py}}", "{{be:utils/auth.py}}", "{{be:models/management_schemas.py}}"],
        "depends": ["BE-2.4"],
        "commit": "feat(api): manage API keys as a signed-in owner",
    },
    {
        "key": "BE-2.6", "repo": "backend", "type": "dev", "step": 2, "priority": "P1", "size": "S",
        "areas": ["auth"], "labels": ["security"],
        "title": "Remove the admin bootstrap secret",
        "summary": "Retire the temporary `X-Admin-Secret` path from Step 1 now that users create organisations themselves.",
        "tasks": [
            "Delete `ADMIN_BOOTSTRAP_ROUTES` and its branch in {{be:middleware/auth.py}}.",
            "Delete `verify_admin_secret` from {{be:utils/auth.py}} and `admin_bootstrap_secret` from {{be:config.py}}.",
            "Delete `POST /management/organisations` (`register_organisation`) in {{be:routers/management.py}}.",
            "Update README and any docs that mention the admin secret.",
            "DevOps follow-up in the same PR description: after deploy, remove `ADMIN_BOOTSTRAP_SECRET` from Cloud Run "
            "and delete the secret from Secret Manager.",
        ],
        "acceptance": [
            "`curl -X POST $API/management/organisations -H 'X-Admin-Secret: <old>'` returns 401.",
            "`grep -rn admin_bootstrap .` returns nothing.",
        ],
        "depends": ["BE-2.5"],
        "commit": "refactor(auth): remove admin bootstrap secret",
    },
    {
        "key": "FE-2.1", "repo": "frontend", "type": "dev", "step": 2, "priority": "P1", "size": "S",
        "areas": ["auth"],
        "title": "Add .env.example and lazy Firebase client initialisation",
        "summary": "Install the Firebase SDK and expose a safe accessor that never runs on the server.",
        "tasks": [
            "`npm i firebase`.",
            "Create `.env.example` with `VITE_API_BASE_URL=http://localhost:8080` (absolute) and "
            "`VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_APP_ID`. "
            "Make sure `.env` is in `.gitignore`.",
            "Type the variables in `src/vite-env.d.ts` (`interface ImportMetaEnv`).",
            "Create `src/lib/firebase.ts` with `getFirebaseAuth(): Auth | null`: returns `null` when "
            "`typeof window === \"undefined\"`; otherwise `initializeApp` once (guarded by `getApps().length`) and returns `getAuth(app)`.",
            "If a variable is missing, throw an error listing exactly which ones.",
        ],
        "acceptance": [
            "SSR render of any page does not import-crash because of Firebase.",
            "Missing `VITE_FIREBASE_PROJECT_ID` produces a readable error naming that variable.",
        ],
        "files": ["`src/lib/firebase.ts` (new)", "`.env.example` (new)", "{{fe:.gitignore}}"],
        "depends": ["FE-2.0"],
        "commit": "feat(auth): add Firebase client and env template",
    },
    {
        "key": "FE-2.2", "repo": "frontend", "type": "dev", "step": 2, "priority": "P0", "size": "S",
        "areas": ["auth"], "labels": ["security", "bug"],
        "title": "Make the API client SSR-safe: per-request tokens, no window.location",
        "summary": "Remove module-level auth state and browser-only globals from the API client.",
        "why": """
            In an SSR app, module scope is shared by every request the server handles. A module-level token
            provider means two users rendering at the same time can read each other's token (problem 3).
            `window.location` does not exist during SSR (problem 12).
        """,
        "current": """
            {{fe:src/lib/api.ts}} has `let authTokenProvider` with `setAuthTokenProvider()`, defaults the base URL
            to the relative `/api`, and calls `new URL(..., window.location.origin)`. `ApiError` reads `message`
            and `error`, but FastAPI returns `{"detail": "..."}` (string, or a list for 422 validation errors).
        """,
        "tasks": [
            "Delete `authTokenProvider` and `setAuthTokenProvider`.",
            "Add `getToken?: () => Promise<string | null>` to `ApiRequestOptions`; `apiFetch` awaits it per request unless `skipAuth`.",
            "`getBaseUrl()`: read `VITE_API_BASE_URL`; throw if missing or not an absolute URL (`new URL(value)` must succeed).",
            "`buildUrl()`: `new URL(base + path)` with no `window` reference.",
            "`ApiError`: read `detail`. If it is an array (422), join the `msg` fields into one readable message and keep the array in `details`.",
            "Update {{fe:src/lib/api-hooks.ts}} so `useApiQuery` and `useApiMutation` accept and forward `getToken` (the auth context supplies it in the next issue).",
        ],
        "acceptance": [
            "`grep -n window src/lib/api.ts` returns nothing.",
            "No module-level mutable state remains in `api.ts`.",
            "A 422 from the backend shows a readable message, not `[object Object]`.",
        ],
        "files": ["{{fe:src/lib/api.ts}}", "{{fe:src/lib/api-hooks.ts}}"],
        "commit": "fix(api): pass auth token per request and remove window usage",
    },
    {
        "key": "FE-2.3", "repo": "frontend", "type": "dev", "step": 2, "priority": "P1", "size": "M",
        "areas": ["auth"],
        "title": "Add AuthProvider with onIdTokenChanged and a loading state",
        "summary": "Provide the signed-in user, a token getter and sign-out to the whole app.",
        "tasks": [
            "Create `src/lib/auth-context.tsx` exporting `AuthProvider` and `useAuth()` returning "
            "`{ user, isLoading, getToken, signOut }`.",
            "Subscribe to `onIdTokenChanged` inside `useEffect` (client only). `isLoading` stays `true` until the first callback fires, so guarded pages do not flash the login screen on refresh.",
            "`getToken` returns `auth.currentUser?.getIdToken()` (the SDK refreshes it automatically) or `null`.",
            "`signOut`: Firebase `signOut`, then `queryClient.clear()`, then navigate to `/login`.",
            "Mount `<AuthProvider>` inside `QueryClientProvider` in `RootComponent` of {{fe:src/routes/__root.tsx}}.",
            "Make `useApiQuery`/`useApiMutation` use `useAuth().getToken` by default.",
            "On a 401 from the API: force-refresh the token once (`getIdToken(true)`) and retry; if it still fails, sign out.",
            "Add `useMe()` that queries `GET /me` with key `[\"me\", user.uid]`.",
        ],
        "acceptance": [
            "Refreshing a page while signed in never shows signed-out UI first.",
            "After sign-out, the query cache is empty (no previous user data visible).",
        ],
        "files": ["`src/lib/auth-context.tsx` (new)", "{{fe:src/routes/__root.tsx}}", "{{fe:src/lib/api-hooks.ts}}"],
        "depends": ["FE-2.1", "FE-2.2", "BE-2.4"],
        "commit": "feat(auth): add Firebase client, auth context, and per-request tokens",
    },
    {
        "key": "FE-2.4", "repo": "frontend", "type": "dev", "step": 2, "priority": "P1", "size": "M",
        "areas": ["auth", "ui"],
        "title": "Wire login, signup and forgot password pages to Firebase",
        "summary": "Replace the static auth screens with working Firebase flows and readable errors.",
        "tasks": [
            "Login ({{fe:src/pages/login.jsx}}): `signInWithEmailAndPassword`; Google button uses `signInWithPopup(new GoogleAuthProvider())`, falling back to `signInWithRedirect` on `auth/popup-blocked`.",
            "Signup ({{fe:src/pages/signup.jsx}}): `createUserWithEmailAndPassword`, then `sendEmailVerification`.",
            "Forgot password ({{fe:src/pages/forgot-password.jsx}}): `sendPasswordResetEmail`; always show the same neutral confirmation (\"If an account exists, we sent a link\").",
            "Validate forms with `react-hook-form` + `zod` (`@hookform/resolvers` is already installed).",
            "Map Firebase error codes to friendly text in `src/lib/auth-errors.ts`: `auth/invalid-credential`, "
            "`auth/email-already-in-use`, `auth/weak-password`, `auth/invalid-email`, `auth/too-many-requests`, "
            "`auth/network-request-failed`; ignore `auth/popup-closed-by-user`.",
            "Disable submit buttons while a request is pending.",
            "After sign-in: go to the `redirect` search param if it is a relative path, otherwise `GET /me`: no org goes to `/onboarding`, else `/incidents`.",
            "A signed-in user visiting `/login` or `/signup` is redirected away.",
        ],
        "acceptance": [
            "Email signup, Google signup, login, logout and password reset all work against the real Firebase project.",
            "Every error shown to the user is a sentence, never a raw `auth/...` code.",
        ],
        "files": ["{{fe:src/pages/login.jsx}}", "{{fe:src/pages/signup.jsx}}", "{{fe:src/pages/forgot-password.jsx}}", "`src/lib/auth-errors.ts` (new)"],
        "depends": ["FE-2.3"],
        "commit": "feat(auth): wire login and signup pages to Firebase",
    },
    {
        "key": "FE-2.5", "repo": "frontend", "type": "dev", "step": 2, "priority": "P1", "size": "M",
        "areas": ["auth", "ui"], "labels": ["security"],
        "title": "Guard authenticated routes on session state",
        "summary": "Only signed-in users with an organisation can reach the app screens.",
        "tasks": [
            "Create a pathless layout `src/routes/_authed.tsx` that renders `<Outlet />`, and move `incidents/`, "
            "`api-keys.tsx`, `integrations.tsx` and `onboarding.tsx` under `src/routes/_authed/`. URLs do not change; `routeTree.gen.ts` regenerates.",
            "The Firebase session lives in the browser, so the server cannot know it. Set `ssr: false` on the `_authed` "
            "route (TanStack Start selective SSR) or guard inside the component. Do not attempt a server-side check.",
            "While `isLoading`: full-page skeleton. Signed out: redirect to `/login?redirect=<current path>`.",
            "Only accept `redirect` values that start with a single `/` (reject `//evil.com` and absolute URLs) to avoid an open redirect.",
            "Signed in but `me.organisation` is null: redirect to `/onboarding` (except when already there).",
            "Public routes stay public: `/`, `/login`, `/signup`, `/forgot-password`.",
        ],
        "acceptance": [
            "Signed out deep link to `/incidents/INC-1` goes to login, then back to `/incidents/INC-1`.",
            "`/login?redirect=https://example.com` lands on `/incidents`, not the external site.",
            "Refresh on `/incidents` while signed in shows no login flash.",
        ],
        "files": ["`src/routes/_authed.tsx` (new)", "{{fe:src/routes}}"],
        "depends": ["FE-2.3"],
        "commit": "feat(auth): guard authenticated routes on session state",
    },
    {
        "key": "FE-2.6", "repo": "frontend", "type": "dev", "step": 2, "priority": "P1", "size": "S",
        "areas": ["ui"],
        "title": "Onboarding step 1: create organisation",
        "summary": "Let a new user name and create their organisation from the onboarding screen.",
        "tasks": [
            "In {{fe:src/pages/onboarding.jsx}} step 1, submit `{name}` to `POST /me/organisation`.",
            "On success invalidate `[\"me\"]` and advance to step 2 (GCP connection, built in Step 3; show a placeholder until then).",
            "409: \"You already belong to an organisation\" and continue. 403 unverified: show a \"Verify your email\" banner with a resend button (`sendEmailVerification`).",
        ],
        "acceptance": ["A verified new user creates an org and the guard stops sending them to onboarding."],
        "files": ["{{fe:src/pages/onboarding.jsx}}"],
        "depends": ["FE-2.5", "BE-2.4"],
        "commit": "feat(ui): create organisation during onboarding",
    },
    {
        "key": "FE-2.7", "repo": "frontend", "type": "dev", "step": 2, "priority": "P1", "size": "M",
        "areas": ["ui"],
        "title": "API keys page on real data: list, create, revoke",
        "summary": "Replace the static API keys screen with the real key management API.",
        "tasks": [
            "List with `GET /management/api-keys`: name, prefix, created, last used, status.",
            "Create dialog (name) calls `POST /management/api-keys`. Show the raw key **once** with a copy button and the warning that it cannot be shown again.",
            "Revoke via `AlertDialog` confirmation, then `DELETE /management/api-keys/{id}`; invalidate the list.",
            "Members (non-owners) see the list but no create/revoke controls. The backend enforces this anyway.",
            "Loading skeleton, empty state (\"Create your first key to call the API from CI\"), error state.",
        ],
        "acceptance": ["An owner can mint a key, copy it, use it with curl, revoke it, and see the curl call then fail with 401."],
        "files": ["{{fe:src/pages/api-keys.jsx}}"],
        "depends": ["FE-2.5", "BE-2.5"],
        "commit": "feat(ui): manage API keys from the dashboard",
    },
    {
        "key": "FE-2.8", "repo": "frontend", "type": "qa", "step": 2, "priority": "P1", "size": "M",
        "areas": ["auth"],
        "title": "Test plan: Firebase sign-up to first API key (Step 2 exit)",
        "summary": "Verify the whole Step 2 flow end to end against the deployed backend before closing the milestone.",
        "tasks": [
            "Email signup: verification email arrives; before verifying, org creation is refused; after verifying, org is created and the user lands on `/incidents`.",
            "Google signup as a new user goes to onboarding.",
            "Wrong password shows a readable error; repeated failures show the too-many-requests message.",
            "Forgot password with an unknown email shows the same neutral message as a known one.",
            "Refresh `/incidents` while signed in: no login flash.",
            "Sign out, sign in as a different user: none of the first user's data is visible, including via the back button.",
            "Signed out deep link returns to the original page after login; `?redirect=https://example.com` is ignored.",
            "Mint an API key, call `GET $API/incidents/<id>` with it (200), revoke it, call again (401).",
            "Firebase token works on `/management/api-keys`; an API key on the same route gets 401.",
            "`POST $API/management/organisations` with `X-Admin-Secret` returns 401.",
            "Leave a tab idle for over an hour, then act: the token refreshes silently.",
            "Two browsers, two users, reload SSR pages at the same time: no cross-account data.",
            "Auth pages at 375 px width are usable.",
            "Record results as a comment on this issue; open a linked bug for each failure.",
        ],
        "acceptance": ["Every case above passes, or has an open linked bug accepted for later."],
        "depends": ["FE-2.4", "FE-2.5", "FE-2.6", "FE-2.7", "BE-2.6"],
    },

    # =====================================================================
    # STEP 3: Keyless GCP connection
    # =====================================================================
    {
        "key": "BE-3.0", "repo": "backend", "type": "devops", "step": 3, "priority": "P0", "size": "M",
        "areas": ["gcp", "infra"], "labels": ["security"],
        "title": "Grant the Cloud Run identity rights to provision tenant service accounts",
        "summary": "Prepare IAM so the backend can create one service account per tenant and impersonate it.",
        "tasks": [
            "Find the Cloud Run runtime identity: `gcloud run services describe incidentiq --region us-central1 "
            "--format='value(spec.template.spec.serviceAccountName)'`. If it is the default compute service account, "
            "create `incidentiq-runtime@incidentiq-prod.iam.gserviceaccount.com`, give it only the roles the app uses "
            "(Cloud SQL client, Secret Manager accessor, logging writer) and redeploy with `--service-account`.",
            "**Recommended:** create a dedicated project `incidentiq-tenants` that holds only tenant service accounts. "
            "Reason: the runtime needs `setIamPolicy` on service accounts to grant itself Token Creator; in "
            "`incidentiq-prod` that would let it grant itself impersonation of *any* account there, including the deployer. "
            "A separate project limits that power to tenant accounts and keeps the 100 account quota separate.",
            "Enable `iam.googleapis.com` and `iamcredentials.googleapis.com` (in both projects if split).",
            "Create a custom role `tenantServiceAccountProvisioner` with `iam.serviceAccounts.create`, `.get`, `.list`, "
            "`.delete`, `.disable`, `.getIamPolicy`, `.setIamPolicy`. Grant it to the runtime account on the tenants project.",
            "Add `TENANT_SA_PROJECT_ID` to Cloud Run env and `.env.example`.",
            "Record every command in `docs/infra.md` so the setup is reproducible.",
            "Check the service account quota and note when to request an increase (at about 70 tenants).",
        ],
        "acceptance": [
            "From Cloud Shell, impersonating the runtime account, you can create a test account in the tenants project, grant the runtime Token Creator on it, mint an access token for it, then delete it.",
            "The runtime account cannot create service accounts in `incidentiq-prod` (if the split is used).",
        ],
        "files": ["`docs/infra.md` (new)"],
    },
    {
        "key": "BE-3.0b", "repo": "backend", "type": "devops", "step": 3, "priority": "P1", "size": "S",
        "areas": ["gcp", "infra"],
        "title": "Create a sandbox customer GCP project for end-to-end testing",
        "summary": "A throwaway project that plays the customer, used by the Step 3 and Step 4 test plans.",
        "tasks": [
            "Create `incidentiq-sandbox` (any name) with a budget alert at a small amount.",
            "Deploy a tiny Cloud Run service with an `/error` endpoint that logs a stack trace and returns 500, so real error logs exist on demand.",
            "Keep a short README in `docs/sandbox.md`: project id, how to produce errors, how to clean up.",
        ],
        "acceptance": ["Hitting `/error` produces an ERROR entry visible in that project's Logs Explorer."],
    },
    {
        "key": "BE-3.1", "repo": "backend", "type": "dev", "step": 3, "priority": "P1", "size": "M",
        "areas": ["database", "gcp"],
        "title": "Add impersonation fields to log source config and allow several sources per org",
        "summary": "Schema changes for keyless GCP access, and removal of the one-source-per-org limit (problem 10).",
        "current": """
            `LogSourceConfig.organisation_id` is `unique=True` ({{be:models/incident.py#L119}}) and `secret_name` is
            NOT NULL ({{be:models/incident.py#L123}}). Several places read the config with `scalar_one_or_none()`,
            which will raise once an org has two rows.
        """,
        "tasks": [
            "`organisations.gcp_service_account_email` String(255), nullable, unique. **Deliberate deviation from the plan:** "
            "the service account is per tenant, not per log source, so it belongs on the organisation.",
            "`log_source_configs.auth_mode` String(20) NOT NULL, server default `'key'` for existing rows, CHECK in (`impersonation`, `key`).",
            "`log_source_configs.target_project_id` String(100), nullable.",
            "Make `log_source_configs.secret_name` nullable.",
            "Drop the unique constraint on `log_source_configs.organisation_id` (look up its real name in the DB or in "
            "{{be:alembic/versions/a6a50c5199e1_create_organisations_api_keys_log_.py}}) and keep a plain index.",
            "Update every reader to tolerate several rows: {{be:routers/incidents.py}}, {{be:pipeline/runner.py}} "
            "(`_fetch_logs_for_incident`), {{be:tools/connectors/factory.py}}, {{be:routers/management.py}} "
            "(`configure_log_source`). Until source selection is designed, use the most recently updated active row and log a warning if there is more than one.",
            "Mark `key` mode as deprecated in code comments and in the `LogSourceResponse` (`deprecated: true`).",
        ],
        "acceptance": [
            "Upgrade and downgrade succeed against a copy of production data; existing rows become `auth_mode = 'key'`.",
            "An org with two active sources can still create incidents.",
        ],
        "files": ["{{be:models/incident.py}}", "{{be:routers/incidents.py}}", "{{be:pipeline/runner.py}}", "{{be:tools/connectors/factory.py}}", "{{be:routers/management.py}}"],
        "commit": "feat(db): add impersonation fields to log source config",
    },
    {
        "key": "BE-3.2", "repo": "backend", "type": "dev", "step": 3, "priority": "P0", "size": "M",
        "areas": ["gcp"], "labels": ["security"],
        "title": "Provision and impersonate per-tenant service accounts",
        "summary": "Create one Google service account per organisation and obtain short lived credentials for it at analysis time.",
        "why": "Customers grant access to *their* account; no key ever leaves their project, and tenant isolation becomes an IAM boundary.",
        "tasks": [
            "Create `utils/gcp_iam.py`.",
            "**Naming:** service account IDs must be 6 to 30 chars, lowercase letters, digits and hyphens, starting with a letter. "
            "The plan's `tenant-<org_uuid>` is 43 chars and will be rejected. Use `t-` + the first 28 hex chars of the "
            "org UUID without hyphens. Always store the resulting email and never recompute it.",
            "`async def ensure_tenant_service_account(org) -> str`: create it in `TENANT_SA_PROJECT_ID` with display "
            "name `IncidentIQ tenant` and the org id in the description (treat `AlreadyExists` as success). "
            "Then add `roles/iam.serviceAccountTokenCreator` for the runtime account on it (read-modify-write the "
            "policy with the etag, retry on conflict). Save the email on `organisations`.",
            "`async def get_tenant_credentials(email)`: `google.auth.impersonated_credentials.Credentials(source_credentials=google.auth.default()[0], "
            "target_principal=email, target_scopes=['https://www.googleapis.com/auth/logging.read'], lifetime=3600)`.",
            "Every Google client call goes through `asyncio.to_thread` (problem 6).",
            "Call `ensure_tenant_service_account` after `POST /me/organisation` succeeds. Best effort: if it fails, the org "
            "is still created and provisioning is retried lazily when connection info is requested.",
            "Note for the UI: a freshly created account can take up to about a minute before customers can grant roles to it.",
        ],
        "acceptance": [
            "Creating an org creates exactly one service account and stores its email.",
            "Calling `ensure_tenant_service_account` twice is a no-op the second time.",
            "`get_tenant_credentials` returns a token whose `expiry` is at most one hour away.",
        ],
        "files": ["`utils/gcp_iam.py` (new)", "`routers/me.py`", "{{be:requirements.txt}}"],
        "depends": ["BE-3.0", "BE-3.1", "BE-2.4"],
        "commit": "feat(tools): add tenant service account provisioning and impersonation",
    },
    {
        "key": "BE-3.3", "repo": "backend", "type": "dev", "step": 3, "priority": "P0", "size": "M",
        "areas": ["gcp", "pipeline"],
        "title": "Read GCP logs with impersonated credentials off the event loop",
        "summary": "Switch the GCP connector to impersonation and stop it blocking the event loop.",
        "current": """
            {{be:tools/connectors/gcp_logging.py}} builds credentials from a customer JSON key and calls the
            synchronous `google.cloud.logging` client directly inside `async def fetch_logs`.
        """,
        "tasks": [
            "Accept `auth_mode`. `impersonation`: credentials from `get_tenant_credentials(org.gcp_service_account_email)` and project from `target_project_id`. `key`: existing path, plus a deprecation warning log.",
            "Move client creation and the whole `list_entries` iteration into one synchronous helper and run it with `asyncio.to_thread` (the iterator pages lazily, so it must be consumed inside the thread).",
            "Cap entries (`max_results`) and total bytes (`settings.max_log_size_bytes`).",
            "{{be:tools/connectors/factory.py}}: impersonation mode skips Secret Manager entirely.",
            "Translate `PermissionDenied` into an actionable error that names the service account and project; it ends up in `incident.error_message`.",
        ],
        "acceptance": [
            "An incident for an org in impersonation mode fetches real logs from the sandbox project.",
            "While logs are being fetched, `/health` still answers immediately.",
            "Without the grant, the incident fails with a message telling the customer which role to grant to which account.",
        ],
        "files": ["{{be:tools/connectors/gcp_logging.py}}", "{{be:tools/connectors/factory.py}}"],
        "depends": ["BE-3.2"],
        "commit": "refactor(tools): read GCP logs with impersonated credentials",
    },
    {
        "key": "BE-3.4", "repo": "backend", "type": "dev", "step": 3, "priority": "P0", "size": "M",
        "areas": ["gcp", "api"],
        "title": "Log source API for keyless GCP: connection info, save, and test",
        "summary": "Endpoints the onboarding screen needs to connect a project and prove it works.",
        "tasks": [
            "`GET /management/gcp/connection-info`: ensures the tenant account exists, returns `service_account_email`, "
            "`role: \"roles/logging.viewer\"`, a ready `gcloud projects add-iam-policy-binding <PROJECT_ID> "
            "--member=serviceAccount:<EMAIL> --role=roles/logging.viewer` command, and a Terraform "
            "`google_project_iam_member` snippet.",
            "`POST /management/log-source` with `source_type: gcp_logging`, `auth_mode: impersonation`, "
            "`target_project_id` (validate `^[a-z][a-z0-9-]{4,28}[a-z0-9]$`) and an optional `log_filter`. No credentials accepted in this mode.",
            "`POST /management/log-source/test` `{target_project_id, log_filter?}`: one `list_entries` call with page size 1 and a 10 s timeout. "
            "Return `{ok: true, sample_count}` or `{ok: false, code, message, fix}` where `code` is one of "
            "`permission_denied` (fix = the grant command), `project_not_found`, `api_disabled` "
            "(fix = `gcloud services enable logging.googleapis.com --project <id>`), `sa_not_ready`, `timeout`.",
            "Owner only. Simple per-org rate limit on the test endpoint (for example 10 per minute).",
        ],
        "acceptance": [
            "Each failure code above can be reproduced against the sandbox project and returns the documented `fix`.",
            "A successful test followed by save creates an impersonation log source with no Secret Manager write.",
        ],
        "files": ["{{be:routers/management.py}}", "{{be:models/management_schemas.py}}"],
        "depends": ["BE-3.3"],
        "commit": "feat(api): add log source connection test endpoint",
    },
    {
        "key": "BE-3.5", "repo": "backend", "type": "dev", "step": 3, "priority": "P2", "size": "S",
        "areas": ["gcp"], "labels": ["documentation"],
        "title": "Customer guide: connect a GCP project without keys",
        "summary": "Write `docs/gcp-setup.md`, linked from the onboarding screen.",
        "tasks": [
            "Console steps (IAM > Grant access), the `gcloud` command and the Terraform snippet.",
            "How to verify (the Test button) and how to revoke (remove the binding).",
            "What we can read: `roles/logging.viewer` covers normal logs; Data Access audit logs need `roles/logging.privateLogViewer` and are not requested.",
            "How customers can see our access in their own audit logs.",
        ],
        "acceptance": ["Someone unfamiliar with the product can connect the sandbox project by following only this page."],
        "files": ["`docs/gcp-setup.md` (new)"],
        "depends": ["BE-3.4"],
        "commit": "docs(gcp): add keyless project connection guide",
    },
    {
        "key": "FE-3.1", "repo": "frontend", "type": "dev", "step": 3, "priority": "P0", "size": "M",
        "areas": ["ui", "gcp"],
        "title": "Onboarding step 2: keyless GCP connection",
        "summary": "Show the customer exactly what to grant, then prove the connection works.",
        "tasks": [
            "Build a reusable `src/components/gcp-connect.tsx`, used by onboarding step 2 and the integrations page.",
            "Fetch `GET /management/gcp/connection-info`. Show the service account email and role with copy buttons (clipboard + `sonner` toast).",
            "Tabs: Console steps / gcloud command / Terraform snippet, each copyable.",
            "Project ID input validated with the same regex as the backend.",
            "Test connection button calls `POST /management/log-source/test`. Render success (sample count) and each error code with its `fix` text and a copyable command. `sa_not_ready`: \"Wait a minute and retry\".",
            "Save enabled after a successful test (offer \"Save anyway\" behind a secondary button).",
            "Skip link (manual log upload) continues onboarding.",
            "Link to the customer guide.",
        ],
        "acceptance": [
            "A user connects the sandbox project from the UI without touching a JSON key.",
            "Testing before granting shows the exact grant command for their project.",
        ],
        "files": ["{{fe:src/pages/onboarding.jsx}}", "{{fe:src/pages/integrations.jsx}}", "`src/components/gcp-connect.tsx` (new)"],
        "depends": ["FE-2.6", "BE-3.4", "BE-3.5"],
        "commit": "feat(ui): connect onboarding step to keyless GCP flow",
    },
    {
        "key": "BE-3.6", "repo": "backend", "type": "qa", "step": 3, "priority": "P1", "size": "M",
        "areas": ["gcp"], "labels": ["security"],
        "title": "Test plan: keyless GCP connection (Step 3 exit)",
        "summary": "Verify Step 3 against the sandbox project, including the isolation guarantees.",
        "tasks": [
            "No keys exist: `gcloud iam service-accounts keys list --iam-account <tenant sa> --managed-by=user` is empty, and no new Secret Manager secret was written.",
            "Test before granting: `permission_denied` with the exact command. After granting: success; note how long IAM propagation took.",
            "Wrong project id: `project_not_found`. Logging API disabled in the sandbox: `api_disabled`.",
            "Create an incident: logs are fetched with impersonation and the RCA completes.",
            "Remove the grant: the next incident fails fast with a clear `error_message`; nothing hangs.",
            "Isolation: org B testing against org A's sandbox project gets `permission_denied`.",
            "The sandbox project's audit logs show the tenant account reading logs.",
            "An existing org in legacy `key` mode still works.",
            "Record results as a comment; open linked bugs for failures.",
        ],
        "acceptance": [MANUAL_QA_ACCEPTANCE],
        "depends": ["BE-3.0b", "FE-3.1"],
    },

    # =====================================================================
    # STEP 4: Alert ingest
    # =====================================================================
    {
        "key": "BE-4.1", "repo": "backend", "type": "dev", "step": 4, "priority": "P1", "size": "M",
        "areas": ["database", "ingest"],
        "title": "Add ingest tokens, external incident IDs and trigger source",
        "summary": "Schema for alert-triggered incidents, deduplication and the per-org quota.",
        "tasks": [
            "`IngestToken` model: `id`, `organisation_id` FK, `token_hash` (HMAC with the pepper, same as API keys in {{be:utils/auth.py}}), "
            "`token_prefix` (display), `is_active`, `created_at`, `rotated_at`, `last_used_at` (all `TIMESTAMPTZ`). "
            "Token format `iqi_live_<32 url-safe random>`, a different prefix from API keys so neither can be used as the other.",
            "Partial unique index: one active token per org.",
            "`incidents.external_incident_id` String(255) nullable, unique index on `(organisation_id, external_incident_id)` (Postgres allows many NULLs).",
            "`incidents.triggered_by` String(10) NOT NULL default `'manual'`, CHECK in (`manual`, `alert`).",
            "`incidents.alert_payload` JSONB nullable (trimmed copy, for audit and debugging).",
            "**Repo gap:** alerts carry no GitHub repo, but `github_repo_url` is required today. Add "
            "`organisations.default_github_repo_url` (nullable) and make `incidents.github_repo_url` nullable; the pipeline skips deploy correlation when it is empty.",
            "`organisations.monthly_analysis_limit` Integer NOT NULL default 200 (used by the quota issue).",
        ],
        "acceptance": [
            "Migration upgrades and downgrades cleanly; existing incidents become `triggered_by = 'manual'`.",
            "Inserting two incidents with the same org and external id fails.",
        ],
        "files": ["{{be:models/incident.py}}", "{{be:models/schemas.py}}"],
        "commit": "feat(db): add ingest tokens and external incident ids",
    },
    {
        "key": "BE-4.2", "repo": "backend", "type": "dev", "step": 4, "priority": "P1", "size": "L",
        "areas": ["ingest", "api", "pipeline"], "labels": ["security"],
        "title": "Implement the Cloud Monitoring alert ingest endpoint",
        "summary": "`POST /ingest/gcp/alert` turns a customer's firing alert into an analysis with no human involved.",
        "tasks": [
            "**Auth, recommended:** Cloud Monitoring `webhook_basicauth` channel, which sends `Authorization: Basic base64(user:password)`. "
            "Use the ingest token as the password (username `incidentiq`). Also accept the `webhook_tokenauth` style "
            "`?auth_token=` query parameter as a fallback. Reason for preferring Basic: Cloud Run request logs record the full URL, "
            "so a query string token ends up in our logs.",
            "Middleware: `/ingest/*` accepts **only** ingest tokens (reject API keys and Firebase tokens). Hash, look up the active token "
            "(or a rotated one inside its grace period), set `request.state.organisation_id`, update `last_used_at` (throttled like API keys).",
            "Never log the query string for `/ingest/*` (check uvicorn's access log too).",
            "Parse the payload (schema version 1.2) with a Pydantic model using `extra=\"ignore\"`: `incident.incident_id`, `state`, "
            "`policy_name`, `condition_name`, `started_at` (epoch seconds), `summary`, `url`, `resource.type`, `resource.labels`, "
            "`metadata.user_labels`. Missing optional fields must not fail the request.",
            "`state != \"open\"`: return 200 `{\"status\": \"ignored\"}`.",
            "Dedupe with `INSERT ... ON CONFLICT (organisation_id, external_incident_id) DO NOTHING RETURNING id`. "
            "No row returned: 200 `{\"status\": \"duplicate\", \"incident_id\": ...}`.",
            "Build the incident: description from policy name and summary; `reported_at` from `started_at`; `triggered_by = alert`; "
            "`github_repo_url` from the org default; seed `affected_services` from `resource.labels` (`service_name`, "
            "`container_name`, `function_name`, ...) into the pipeline's initial state (see {{be:pipeline/state.py}}) so Triage does not have to guess.",
            "Check the quota (next issue) before starting the pipeline.",
            "Start the pipeline the same way as {{be:routers/incidents.py#L88}}, respecting the ordering invariant documented there (commit before the task runs).",
            "Respond in under a second. Authenticated but unusable payloads return 200 with a reason (avoids Cloud Monitoring retry storms). Bad token: 401. Non-JSON: 400. Body limit 256 KB.",
            "Add `tests/fixtures/gcp_alert_open.json` and `gcp_alert_closed.json` taken from a real notification.",
        ],
        "acceptance": [
            "A real alert from the sandbox creates an incident with `triggered_by = alert` and the pipeline starts.",
            "Re-posting the same payload returns `duplicate` and creates nothing.",
            "A `closed` payload is ignored.",
            "The token never appears in application logs.",
        ],
        "files": ["`routers/ingest.py` (new)", "{{be:middleware/auth.py}}", "{{be:main.py}}", "{{be:pipeline/runner.py}}"],
        "depends": ["BE-4.1"],
        "commit": "feat(api): implement Cloud Monitoring alert ingest endpoint",
    },
    {
        "key": "BE-4.3", "repo": "backend", "type": "dev", "step": 4, "priority": "P1", "size": "M",
        "areas": ["pipeline", "api"],
        "title": "Enforce per-organisation analysis quota and a global circuit breaker",
        "summary": "Protect the Gemini budget now that spend is driven by other people's alert volume.",
        "tasks": [
            "Create `pipeline/quota.py` with `async def check_analysis_budget(db, org_id) -> BudgetDecision` used by every path that starts the pipeline (manual create, log upload, ingest).",
            "Per org: count incidents started in the current UTC calendar month; at or over `monthly_analysis_limit`, do not start.",
            "Ingest path when over quota: still record the incident with status `skipped` and `error_message = \"Monthly analysis limit reached\"`, return 200, and notify through the org's existing Slack/PagerDuty config once per month.",
            "Manual API path when over quota: 429 with a clear message.",
            "Global breaker: `GLOBAL_MAX_ANALYSES_PER_HOUR` setting. When the count of analyses started in the last hour across all orgs reaches it, skip and log at ERROR (set up a log-based alert on that message).",
            "Concurrency: lock the organisation row (`SELECT ... FOR UPDATE`) while counting, or accept and document a small overshoot.",
        ],
        "acceptance": [
            "With the limit set to 1, the second alert in a month is recorded as `skipped` and one notification is sent.",
            "Manual creation over quota returns 429.",
            "Tripping the global breaker logs one ERROR line per skipped analysis.",
        ],
        "files": ["`pipeline/quota.py` (new)", "{{be:routers/incidents.py}}", "`routers/ingest.py`", "{{be:config.py}}"],
        "depends": ["BE-4.2"],
        "commit": "feat(api): enforce per-organisation analysis quota",
    },
    {
        "key": "BE-4.4", "repo": "backend", "type": "dev", "step": 4, "priority": "P1", "size": "S",
        "areas": ["ingest", "api"],
        "title": "Management endpoints to view and rotate the ingest token and org settings",
        "summary": "Everything the integrations page needs to set up alert delivery.",
        "tasks": [
            "`GET /management/ingest`: `{ingest_url, username: \"incidentiq\", token_prefix, created_at, last_used_at, has_token}`. "
            "Add a `PUBLIC_BASE_URL` setting for building the URL.",
            "`POST /management/ingest/token/rotate` (owner): deactivate the current token, create a new one, return the raw token "
            "**once**, plus ready `gcloud beta monitoring channels create --type=webhook_basicauth ...` text.",
            "Grace period: the previous token keeps working for 24 hours after rotation (`rotated_at`), so customers can update their channel.",
            "`PATCH /management/organisation` (owner): update `default_github_repo_url` (validated GitHub URL).",
        ],
        "acceptance": [
            "Rotate returns a new token once; the old one works for 24 h then gets 401.",
            "The default repo URL is used by the next alert-triggered incident.",
        ],
        "files": ["{{be:routers/management.py}}", "{{be:config.py}}"],
        "depends": ["BE-4.1"],
        "commit": "feat(api): add ingest token management endpoints",
    },
    {
        "key": "BE-4.5", "repo": "backend", "type": "devops", "step": 4, "priority": "P1", "size": "S",
        "areas": ["ingest", "infra"], "labels": ["security"],
        "title": "Configure Cloud Run for alert ingest",
        "summary": "Environment and log hygiene for the public ingest endpoint.",
        "tasks": [
            "Set `PUBLIC_BASE_URL` and `GLOBAL_MAX_ANALYSES_PER_HOUR` on Cloud Run and in `.env.example`.",
            "Confirm the service allows unauthenticated invocations (Cloud Monitoring cannot send Google IAM tokens).",
            "After the first real alert, search Cloud Logging (`httpRequest.requestUrl:\"auth_token\"`) to confirm no token is recorded when Basic auth is used.",
            "Restrict who can read the Cloud Run request logs, since query-string tokens (fallback mode) would appear there.",
            "Create a log-based alert on the global circuit breaker ERROR message.",
        ],
        "acceptance": ["Env vars present in the live revision; the log search returns nothing for Basic auth deliveries; the breaker alert exists."],
        "depends": ["BE-4.3", "BE-4.4"],
    },
    {
        "key": "FE-4.1", "repo": "frontend", "type": "dev", "step": 4, "priority": "P1", "size": "M",
        "areas": ["ui", "ingest"],
        "title": "Integrations page: alert ingest setup and token rotation",
        "summary": "Show customers how to send Cloud Monitoring alerts to IncidentIQ.",
        "tasks": [
            "Section \"Google Cloud alerts\" in {{fe:src/pages/integrations.jsx}}: ingest URL, username, masked token (prefix + dots), last used.",
            "Rotate button behind an `AlertDialog` (\"Existing notification channels keep working for 24 hours\"). Show the new token once with copy.",
            "Setup instructions in tabs: Console (Monitoring > Alerting > Edit notification channels > Webhook with basic auth) and the prefilled `gcloud` command from the rotate response.",
            "Default GitHub repository field saved with `PATCH /management/organisation`.",
            "Reuse the GCP connection component from Step 3 on this page.",
        ],
        "acceptance": ["A user can create the notification channel in the sandbox using only what this page shows."],
        "files": ["{{fe:src/pages/integrations.jsx}}"],
        "depends": ["FE-2.5", "FE-3.1", "BE-4.4"],
        "commit": "feat(ui): show ingest endpoint and token rotation",
    },
    {
        "key": "BE-4.6", "repo": "backend", "type": "qa", "step": 4, "priority": "P1", "size": "M",
        "areas": ["ingest"],
        "title": "Test plan: alert-triggered RCA (Step 4 exit)",
        "summary": "Prove the no-human path works and is safe against duplicates, bad tokens and floods.",
        "tasks": [
            "In the sandbox, create a log-based metric on ERROR entries and an alert policy (threshold > 0) with a Basic auth webhook channel from the integrations page.",
            "Hit `/error`: an incident with `triggered_by = alert` appears and the RCA completes with no human action. Record time from alert to report.",
            "Re-send the captured payload with curl: `duplicate`, no new incident.",
            "When the alert closes: `ignored`.",
            "Wrong token: 401. Rotate: old token works within 24 h, fails after (adjust grace temporarily to test).",
            "Quota limit 1: second distinct alert recorded as `skipped`, one notification sent.",
            "Payload without resource labels still creates an incident.",
            "20 distinct alerts in 10 seconds: all accepted, p95 response under 1 s, quota respected.",
            "Confirm no token in application or request logs.",
            MANUAL_QA_RECORD_TASK,
        ],
        "acceptance": [MANUAL_QA_ACCEPTANCE],
        "depends": ["BE-3.0b", "BE-4.5", "FE-4.1"],
    },

    # =====================================================================
    # STEP 5: GitHub App
    # =====================================================================
    {
        "key": "BE-5.0", "repo": "backend", "type": "devops", "step": 5, "priority": "P0", "size": "S",
        "areas": ["github", "infra"], "labels": ["security"],
        "title": "Register the IncidentIQ GitHub App and store its credentials",
        "summary": "Create the App that replaces the shared PAT.",
        "tasks": [
            "Create a GitHub App (owned by your account for now; ownership can be transferred to an org later). Installable by any account.",
            "Repository permissions: **Contents: Read**, **Metadata: Read**. Nothing else. Webhook: inactive.",
            "Enable **Request user authorization (OAuth) during installation**. The callback receives a `code` used to prove the installing user can access the installation (see the callback issue).",
            "Callback URL: `https://<api>/github/callback`. Tick \"Redirect on update\".",
            "Generate a private key, store it in Secret Manager as `github-app-private-key`, mount it on Cloud Run with `--set-secrets`, then delete the local `.pem`.",
            "Store the client secret in Secret Manager as well.",
            "Cloud Run env: `GITHUB_APP_ID`, `GITHUB_APP_SLUG`, `GITHUB_APP_CLIENT_ID`, `GITHUB_STATE_SECRET` (new random value), `FRONTEND_BASE_URL`.",
            "Create a second App for local development with a `http://localhost:8080/github/callback` callback.",
        ],
        "acceptance": ["Secrets exist in Secret Manager only, env vars are on the live revision, and the App's public page shows the two read permissions."],
    },
    {
        "key": "BE-5.1", "repo": "backend", "type": "dev", "step": 5, "priority": "P0", "size": "L",
        "areas": ["github", "database", "api"], "labels": ["security"],
        "title": "Add GitHub App installation model and install callback",
        "summary": "Bind a GitHub App installation to an organisation, securely.",
        "tasks": [
            "`GitHubInstallation` model + migration: `id`, `organisation_id` FK, `installation_id` BigInteger **unique**, `account_login`, `account_type`, `repository_selection`, `is_active`, `created_at`, `suspended_at`.",
            "`POST /management/github/install-url` (owner): returns `https://github.com/apps/<slug>/installations/new?state=<signed>`. "
            "State = base64 JSON `{org_id, user_id, exp: now+10min, nonce}` + HMAC-SHA256 with `GITHUB_STATE_SECRET`.",
            "`GET /github/callback`: a **public** route in the middleware (it is a browser redirect from GitHub with no bearer token). Verify the state signature and expiry.",
            "**Do not trust `installation_id` from the query string alone**, since anyone can type any id. Exchange the OAuth `code` for a user token and call `GET /user/installations`; the id must be in that list.",
            "Fetch `GET /app/installations/{id}` with the App JWT for `account_login`, `account_type` and `repository_selection`; upsert the row.",
            "If the installation is already bound to another organisation, refuse (`?github=error&reason=already_connected`).",
            "`setup_action=update`: refresh `repository_selection`.",
            "Redirect 302 to `${FRONTEND_BASE_URL}/integrations?github=connected` or `?github=error&reason=<code>`.",
            "`GET /management/github`: list the org's installations. `DELETE /management/github/installations/{id}`: mark inactive and return the GitHub settings URL for the customer to uninstall.",
        ],
        "acceptance": [
            "Installing from the UI creates one row bound to the right org.",
            "A tampered or expired state, or an installation id the user cannot access, creates nothing and redirects with an error.",
        ],
        "files": ["{{be:models/incident.py}}", "`routers/github.py` (new)", "{{be:middleware/auth.py}}"],
        "depends": ["BE-5.0"],
        "commit": "feat(github): add GitHub App installation model and callback",
    },
    {
        "key": "BE-5.2", "repo": "backend", "type": "dev", "step": 5, "priority": "P0", "size": "M",
        "areas": ["github", "pipeline"], "labels": ["security"],
        "title": "Use per-installation tokens instead of the shared PAT",
        "summary": "Every analysis uses a short lived token scoped to the customer's installation (problem 2).",
        "current": "{{be:tools/github_client.py#L18}} builds a module-level header from `settings.github_pat`, shared by every tenant.",
        "tasks": [
            "`tools/github_app.py`: App JWT (RS256 with PyJWT, `iat = now - 60`, `exp = now + 9 min`, `iss = app id`); "
            "installation token via `POST /app/installations/{id}/access_tokens`, optionally limited to the one repository being analysed.",
            "Cache tokens per installation until 5 minutes before `expires_at` (in memory, `asyncio.Lock`).",
            "{{be:tools/github_client.py}}: remove the module-level header; `fetch_commits_in_window` and helpers take a token.",
            "Resolve the installation for a repo: the org's active installation whose `account_login` matches the repo owner (case-insensitive).",
            "No installation, or the repo is not in its selection: skip deploy correlation and add a note in the report (\"GitHub not connected for <owner>\") instead of failing the analysis.",
            "404 when minting: mark the installation inactive.",
            "Remove `github_pat` from {{be:config.py}} and `.env.example`. After deploy, remove `GITHUB_PAT` from Cloud Run and **revoke the PAT on GitHub**.",
        ],
        "acceptance": [
            "`grep -rn github_pat .` returns nothing.",
            "An analysis on a repo covered by an installation includes deploy correlation; one without degrades gracefully.",
        ],
        "files": ["`tools/github_app.py` (new)", "{{be:tools/github_client.py}}", "{{be:config.py}}", "{{be:agents/deploy_correlation.py}}"],
        "depends": ["BE-5.1"],
        "commit": "refactor(github): use per-installation tokens instead of shared PAT",
    },
    {
        "key": "FE-5.1", "repo": "frontend", "type": "dev", "step": 5, "priority": "P1", "size": "M",
        "areas": ["ui", "github"],
        "title": "Connect GitHub on the integrations and onboarding screens",
        "summary": "Let customers install the GitHub App and see what is connected.",
        "tasks": [
            "\"Connect GitHub\" button: `POST /management/github/install-url`, then `window.location.assign(url)`.",
            "Handle `?github=connected|error&reason=` on return with a toast, then remove the params from the URL.",
            "List installations: account, all or selected repositories, a \"Manage on GitHub\" link, disconnect.",
            "Onboarding: optional step 3 \"Connect GitHub\" with Skip.",
        ],
        "acceptance": ["A user installs the App on a test account and sees it listed without reloading manually."],
        "files": ["{{fe:src/pages/integrations.jsx}}", "{{fe:src/pages/onboarding.jsx}}"],
        "depends": ["FE-2.5", "BE-5.1"],
        "commit": "feat(ui): connect GitHub App from integrations and onboarding",
    },
    {
        "key": "BE-5.3", "repo": "backend", "type": "qa", "step": 5, "priority": "P1", "size": "M",
        "areas": ["github"], "labels": ["security"],
        "title": "Test plan: GitHub App (Step 5 exit)",
        "summary": "Verify installation binding, token use and failure handling.",
        "tasks": [
            "Install on a test account with one selected repo; run an incident on it: commits appear in deploy correlation.",
            "Incident on a repo outside the selection: completes, report notes the missing access.",
            "Tampered state, expired state: error redirect, no row.",
            "Valid state but someone else's installation id (no access): rejected.",
            "Same installation from a second org: refused.",
            "Uninstall on GitHub: next analysis marks the installation inactive and degrades gracefully.",
            "PAT removed and revoked: everything still works.",
            MANUAL_QA_RECORD_TASK,
        ],
        "acceptance": [MANUAL_QA_ACCEPTANCE],
        "depends": ["BE-5.2", "FE-5.1"],
    },

    # =====================================================================
    # STEP 6: Reliability and correctness
    # =====================================================================
    {
        "key": "BE-6.0", "repo": "backend", "type": "devops", "step": 6, "priority": "P1", "size": "S",
        "areas": ["infra", "pipeline"],
        "title": "Stopgap: keep CPU allocated for background analyses on Cloud Run",
        "summary": "Stop long analyses dying silently while the Cloud Tasks worker is built (problem 9).",
        "why": "Analyses run in FastAPI `BackgroundTasks` after the response is sent. With request-based billing Cloud Run throttles the CPU at that point.",
        "tasks": [
            "`gcloud run services update incidentiq --region us-central1 --no-cpu-throttling`.",
            "Add `--no-cpu-throttling` to the deploy command in {{be:.github/workflows/deploy.yml}} so the setting is visible in code.",
            "Note the cost impact in the PR description; remove the flag once the worker from this step is live.",
        ],
        "acceptance": ["The live revision shows CPU always allocated; a long analysis completes after its HTTP response was returned."],
        "files": ["{{be:.github/workflows/deploy.yml}}"],
    },
    {
        "key": "BE-6.1", "repo": "backend", "type": "dev", "step": 6, "priority": "P2", "size": "S",
        "areas": ["gcp"], "labels": ["bug"],
        "title": "Stop blocking the event loop in Google API calls",
        "summary": "Remove the remaining synchronous Google calls from async code paths (problem 6).",
        "current": """
            {{be:utils/secret_manager.py}} calls the synchronous `SecretManagerServiceClient` inside `async def`, creates a new client per call,
            and `_get_project_id()` does a synchronous `httpx.get` to the metadata server.
        """,
        "tasks": [
            "Switch to `SecretManagerServiceAsyncClient`, created once and reused.",
            "Resolve the project id once at startup (async), and cache it.",
            "Search for other blocking calls inside `async def` (`grep -rn \"Client(\" tools utils pipeline`). GCP logging is handled in Step 3. AWS and Datadog connectors are frozen: leave them.",
            "Run locally with `PYTHONASYNCIODEBUG=1` during an analysis and fix any \"Executing ... took\" warnings over 100 ms from our code.",
        ],
        "acceptance": ["No slow-callback warnings from our modules during an analysis in asyncio debug mode."],
        "files": ["{{be:utils/secret_manager.py}}"],
        "commit": "fix(tools): stop blocking the event loop in Google API calls",
    },
    {
        "key": "BE-6.2", "repo": "backend", "type": "dev", "step": 6, "priority": "P2", "size": "S",
        "areas": ["infra"], "labels": ["bug", "security"],
        "title": "Fail closed when Secret Manager is unavailable outside development",
        "summary": "Credentials must never silently live in memory in production (problem 7).",
        "current": "On `ImportError`, {{be:utils/secret_manager.py}} stores and reads secrets from a module-level dict, so they vanish on restart.",
        "tasks": [
            "Add `env: Literal[\"development\", \"test\", \"production\"] = \"production\"` to {{be:config.py}} (safe default).",
            "Use the in-memory store only when `settings.env == \"development\"`, with a loud warning; otherwise raise.",
            "At startup in {{be:main.py}}, fail fast if `env` is not development and the Secret Manager library cannot be imported.",
            "Set `ENV=development` in the local `.env` / `docker-compose.yml`.",
        ],
        "acceptance": ["With the library missing and `ENV=production`, the app refuses to start with a clear message."],
        "files": ["{{be:utils/secret_manager.py}}", "{{be:config.py}}", "{{be:main.py}}", "{{be:docker-compose.yml}}"],
        "commit": "fix(config): disable in-memory secret fallback outside development",
    },
    {
        "key": "BE-6.3", "repo": "backend", "type": "dev", "step": 6, "priority": "P2", "size": "L",
        "areas": ["database"], "labels": ["bug"],
        "title": "Migrate timestamp columns from String(50) to TIMESTAMPTZ",
        "summary": "Real timestamps so ordering and range queries work (problem 8).",
        "current": "19 timestamp columns in {{be:models/incident.py}} are `String(50)`, so ordering is lexicographic and range queries are impossible.",
        "tasks": [
            "Columns: `incidents` (reported_at, started_at, completed_at, created_at), `organisations.created_at`, "
            "`api_keys` (created_at, last_used_at), `log_source_configs` (created_at, updated_at), `webhook_configs` (all three), "
            "`agent_runs` (started_at, completed_at), `rca_reports.created_at`, `feedback.created_at`, "
            "`notification_configs` (created_at, updated_at, last_notified_at). Confirm the list against the model file.",
            "Before migrating, find bad values: `SELECT id, col FROM t WHERE col IS NOT NULL AND col !~ '^\\d{4}-\\d{2}-\\d{2}'` and fix them.",
            "Migration: `SET LOCAL TIME ZONE 'UTC'` then `ALTER TABLE t ALTER COLUMN c TYPE TIMESTAMPTZ USING c::timestamptz` for each column. Downgrade converts back with `to_char` ISO format.",
            "Models: `Mapped[datetime]` with `DateTime(timezone=True)`.",
            "Code: replace every `datetime.now(timezone.utc).isoformat()` assignment with the datetime itself (`grep -rn \"isoformat()\" routers pipeline middleware utils`). "
            "Simplify `_touch_last_used` in {{be:middleware/auth.py}} (no more `fromisoformat`).",
            "Response schemas in {{be:models/schemas.py}}: type these fields as `datetime`, so the API still returns ISO 8601 strings.",
            "Add an index on `incidents (organisation_id, created_at DESC)`.",
            "Rehearse on a Cloud SQL clone of production before running it for real.",
        ],
        "acceptance": [
            "Rehearsal on the clone succeeds with zero data loss (row counts and spot checks).",
            "API responses keep the same field names with ISO 8601 values.",
            "`ORDER BY created_at` is correct across month boundaries.",
        ],
        "files": ["{{be:models/incident.py}}", "{{be:models/schemas.py}}", "{{be:middleware/auth.py}}", "{{be:routers/incidents.py}}", "{{be:pipeline/runner.py}}"],
        "depends": ["BE-4.1", "BE-5.1"],
        "notes": "Do this after the Step 2 to 5 migrations so all new tables are already TIMESTAMPTZ and this is the last big schema change.",
        "commit": "refactor(db): migrate timestamp columns to TIMESTAMPTZ",
    },
    {
        "key": "BE-6.4", "repo": "backend", "type": "devops", "step": 6, "priority": "P2", "size": "M",
        "areas": ["infra", "pipeline", "ci-cd"],
        "title": "Provision Cloud Tasks queue, worker service and upload bucket",
        "summary": "Infrastructure for running analyses outside the request lifecycle.",
        "tasks": [
            "Enable `cloudtasks.googleapis.com`. Create the queue: `gcloud tasks queues create incidentiq-analysis --location us-central1 --max-concurrent-dispatches=5 --max-attempts=3 --min-backoff=60s`.",
            "Service account `incidentiq-tasks-invoker` with `roles/run.invoker` on the worker service. The runtime account gets `roles/cloudtasks.enqueuer` and `roles/iam.serviceAccountUser` on the invoker account.",
            "Deploy a second Cloud Run service `incidentiq-worker` from the same image with `APP_ROLE=worker`, `--no-allow-unauthenticated`, `--timeout=1800`, low concurrency. Add it to {{be:.github/workflows/deploy.yml}}.",
            "GCS bucket for uploaded logs (uniform access, lifecycle delete after 30 days); runtime account gets object admin on it.",
            "Env on the API service: `TASKS_QUEUE`, `TASKS_LOCATION`, `WORKER_URL`, `TASKS_INVOKER_SA`, `UPLOADS_BUCKET`.",
        ],
        "acceptance": ["A task created by hand with `gcloud tasks create-http-task --oidc-service-account-email=...` reaches the worker; the same request without OIDC gets 403 from Cloud Run."],
        "files": ["{{be:.github/workflows/deploy.yml}}"],
        "depends": ["BE-6.0"],
    },
    {
        "key": "BE-6.5", "repo": "backend", "type": "dev", "step": 6, "priority": "P2", "size": "L",
        "areas": ["pipeline"],
        "title": "Run analyses through a Cloud Tasks worker",
        "summary": "Replace `BackgroundTasks` with a durable queue so analyses survive throttling, scale-in and deploys (problem 9).",
        "current": """
            {{be:routers/incidents.py#L88}} and {{be:routers/incidents.py#L166}} start `run_pipeline` with `BackgroundTasks`.
            Read the ordering invariant comment there and in `run_pipeline`'s docstring before changing anything.
            Uploaded logs (up to 10 MB) are passed as the `raw_logs` argument, but a Cloud Task payload is limited to 1 MB.
        """,
        "tasks": [
            "`pipeline/queue.py`: `async def enqueue_analysis(incident_id)`. Production: Cloud Task with an HTTP target `{WORKER_URL}/internal/tasks/run-analysis` and an OIDC token for the invoker account. Development: in-process `asyncio` task.",
            "Persist uploaded logs to the uploads bucket before enqueueing and pass only the object path.",
            "Enqueue only **after** `await db.commit()`, explicitly.",
            "Worker router mounted only when `APP_ROLE=worker`: `POST /internal/tasks/run-analysis {incident_id}`. Claim atomically with "
            "`UPDATE incidents SET status='processing', started_at=now() WHERE id=:id AND status IN ('pending','queued') RETURNING id`; nothing returned means another delivery already ran it, so return 200.",
            "Return non-2xx only for retryable errors; on the final attempt mark the incident failed with a message (read `X-CloudTasks-TaskRetryCount`).",
            "Reaper: incidents stuck in `processing` for over 45 minutes become `failed` with a clear message (run at worker startup and on a schedule).",
            "Switch the alert ingest path to `enqueue_analysis` as well.",
            "Once live, remove `--no-cpu-throttling` from the API service.",
        ],
        "acceptance": [
            "Deploying a new revision in the middle of an analysis does not leave the incident stuck.",
            "Delivering the same task twice runs the pipeline once.",
            "A 10 MB log upload is analysed successfully.",
        ],
        "files": ["`pipeline/queue.py` (new)", "`routers/internal.py` (new)", "{{be:routers/incidents.py}}", "{{be:pipeline/runner.py}}", "{{be:main.py}}"],
        "depends": ["BE-6.4", "BE-4.2"],
        "commit": "feat(pipeline): run analysis via Cloud Tasks worker",
    },
    {
        "key": "BE-6.6", "repo": "backend", "type": "devops", "step": 6, "priority": "P2", "size": "M",
        "areas": ["ci-cd", "database"],
        "title": "Run Alembic migrations in the deploy pipeline before rollout",
        "summary": "No more schema drift between deploys (problem 11).",
        "tasks": [
            "Create a Cloud Run Job `incidentiq-migrate` from the same image, command `alembic upgrade head`, with the same database connection, env and secrets as the service.",
            "In {{be:.github/workflows/deploy.yml}}, after pushing the image and before `gcloud run deploy`: update the job to the new image and run `gcloud run jobs execute incidentiq-migrate --region us-central1 --wait`. A failure stops the deploy.",
            "Grant the deploy identity what it needs for jobs (`roles/run.developer`, act-as on the runtime account).",
            "Document the rule in the README: migrations must be backward compatible with the revision still running (expand, deploy, then contract).",
            "In the PR CI workflow, run `alembic upgrade head` against a Postgres service container.",
        ],
        "acceptance": ["A deploy that includes a new migration applies it before traffic moves; a broken migration fails the workflow and the old revision keeps serving."],
        "files": ["{{be:.github/workflows/deploy.yml}}", "`.github/workflows/ci.yml`"],
        "depends": ["BE-0.2"],
        "commit": "chore(ci): run Alembic migrations before deploy",
    },
    {
        "key": "BE-6.7", "repo": "backend", "type": "dev", "step": 6, "priority": "P3", "size": "S",
        "areas": ["api"], "labels": ["good first issue"],
        "title": "Delete the empty reports router",
        "summary": "{{be:routers/reports.py}} is a 3 line stub with no endpoints.",
        "tasks": [
            "Reports are already served by `GET /incidents/{id}/report`. Delete `routers/reports.py`.",
            "Remove the import and `app.include_router(reports.router)` from {{be:main.py#L74}}.",
            "If a cross-incident reports API is wanted later, open a new issue with a concrete need.",
        ],
        "acceptance": ["The app starts and `/docs` no longer shows an empty `reports` tag."],
        "files": ["{{be:routers/reports.py}}", "{{be:main.py}}"],
        "commit": "refactor(api): remove empty reports router",
    },
    {
        "key": "BE-6.8", "repo": "backend", "type": "qa", "step": 6, "priority": "P2", "size": "M",
        "areas": ["pipeline", "database"],
        "title": "Test plan: reliability and correctness (Step 6 exit)",
        "summary": "Verify Step 6 under failure conditions.",
        "tasks": [
            "Deploy a new revision while an analysis is running: the incident finishes or is retried; nothing stays in `processing`.",
            "Deliver the same Cloud Task twice by hand: one pipeline run.",
            "Upload a 10 MB log file: analysis completes.",
            "Stop the worker for an hour (set min instances 0 and block it): the reaper marks stuck incidents failed.",
            "Deploy with a new migration: the job runs first. Deploy with a deliberately broken migration on a branch environment: the workflow fails and traffic stays on the old revision.",
            "Timestamps: incidents list ordering correct across a month boundary; API still returns ISO 8601.",
            "`ENV=production` without the Secret Manager library: startup fails with the clear message.",
            MANUAL_QA_RECORD_TASK,
        ],
        "acceptance": [MANUAL_QA_ACCEPTANCE],
        "depends": ["BE-6.1", "BE-6.2", "BE-6.3", "BE-6.5", "BE-6.6"],
    },

    # =====================================================================
    # STEP 7: Frontend on real data
    # =====================================================================
    {
        "key": "BE-7.1", "repo": "backend", "type": "dev", "step": 7, "priority": "P1", "size": "M",
        "areas": ["api"],
        "title": "Add GET /incidents list endpoint with pagination and filters",
        "summary": "The incidents screen needs a list endpoint; today there is only `GET /incidents/{id}`.",
        "tasks": [
            "`GET /incidents?limit=20&cursor=&status=&triggered_by=` returning `{items: [...], next_cursor}`.",
            "Item fields: `id`, short `description` (200 chars), `status`, `triggered_by`, `reported_at`, `created_at`, `completed_at`, top hypothesis title and confidence if a report exists.",
            "Keyset pagination on `(created_at, id)` descending; `limit` at most 100; the cursor is opaque (base64).",
            "Always filter by `request.state.organisation_id`; never accept an org id from the client.",
            "Check that `GET /incidents/{id}`, `/report` and `/feedback` return 404 (not 403) for another org's incident.",
        ],
        "acceptance": ["Paging through 250 incidents returns each exactly once, newest first, only for the caller's org."],
        "files": ["{{be:routers/incidents.py}}", "{{be:models/schemas.py}}"],
        "depends": ["BE-2.3", "BE-4.1"],
        "notes": "Works best after the TIMESTAMPTZ migration in Step 6 (correct ordering and the new index).",
        "commit": "feat(api): list incidents with cursor pagination",
    },
    {
        "key": "FE-7.0", "repo": "frontend", "type": "dev", "step": 7, "priority": "P2", "size": "S",
        "areas": ["ui"],
        "title": "Generate TypeScript API types from the backend OpenAPI schema",
        "summary": "Typed responses so backend changes surface as compile errors, not runtime blanks.",
        "tasks": [
            "Add `openapi-typescript` as a dev dependency and a script `gen:api` that reads `<backend>/openapi.json` and writes `src/lib/api-types.ts`. Commit the generated file.",
            "Export friendly aliases (`Incident`, `IncidentStatus`, `RcaReport`, `ApiKey`, ...) from one module.",
            "Convert pages touched in Step 7 from `.jsx` to `.tsx` as you go.",
        ],
        "acceptance": ["Changing a field name in the backend and regenerating makes `npm run typecheck` fail where the field is used."],
        "files": ["`src/lib/api-types.ts` (new)", "{{fe:package.json}}"],
        "depends": ["BE-7.1"],
        "commit": "chore(api): generate TypeScript types from OpenAPI",
    },
    {
        "key": "FE-7.1", "repo": "frontend", "type": "dev", "step": 7, "priority": "P1", "size": "S",
        "areas": ["ui"],
        "title": "Shared loading, empty and error state components",
        "summary": "Turn the designs on the system states screen into reusable components.",
        "tasks": [
            "Extract from {{fe:src/pages/system-states.jsx}}: `<PageSkeleton>`, `<EmptyState icon title body action>`, `<ErrorState error onRetry>`.",
            "`ErrorState` shows the `ApiError` message and a Retry that calls the query's `refetch`.",
            "Decide whether `/system-states` stays as a design reference (dev only) or is removed from production routes.",
        ],
        "acceptance": ["Each component is used by at least one Step 7 page."],
        "files": ["{{fe:src/pages/system-states.jsx}}", "`src/components/states/` (new)"],
        "commit": "feat(ui): add shared loading, empty and error states",
    },
    {
        "key": "FE-7.2", "repo": "frontend", "type": "dev", "step": 7, "priority": "P1", "size": "M",
        "areas": ["ui"],
        "title": "Load the incidents list from the API",
        "summary": "Replace the static incidents table with live data.",
        "tasks": [
            "`useInfiniteQuery` on `GET /incidents` with key `[\"incidents\", filters]`; \"Load more\" uses `next_cursor`.",
            "Status and trigger filters stored in the URL search params (`validateSearch` on the route).",
            "Badges for status (pending, processing, completed, failed, skipped) and **Auto / Manual** from `triggered_by` (plan Step 4, item 5).",
            "Refetch every 15 s while any visible incident is `pending` or `processing`.",
            "Rows link to `/incidents/$incidentId`.",
            "Empty state with a call to action pointing at the integrations page (connect alerts).",
            "Remove every hardcoded incident from {{fe:src/pages/incidents.jsx}}.",
        ],
        "acceptance": ["The list matches `GET /incidents` for the signed-in org; filters survive a page refresh."],
        "files": ["{{fe:src/pages/incidents.jsx}}", "{{fe:src/routes/incidents/index.tsx}}"],
        "depends": ["FE-7.0", "FE-7.1", "FE-2.5"],
        "commit": "feat(ui): load incidents list from API",
    },
    {
        "key": "FE-7.3", "repo": "frontend", "type": "dev", "step": 7, "priority": "P1", "size": "M",
        "areas": ["ui"],
        "title": "Poll incident status and render the RCA report",
        "summary": "The incident detail page follows the analysis live and shows the report when done.",
        "tasks": [
            "`GET /incidents/{id}` with `refetchInterval` of 3 s while status is `pending` or `processing`, and `false` once terminal. Polling pauses in background tabs.",
            "Show per-agent progress from the status response (see `IncidentStatusResponse` in the backend `models/schemas.py`).",
            "When `completed`, fetch `/incidents/{id}/report` and render hypotheses with confidence, evidence, deploy correlation commits (linked to GitHub) and remediation.",
            "`failed` or `skipped`: show `error_message` prominently.",
            "404: not found state with a link back to the list.",
            "Remove all static design data from {{fe:src/pages/incident-detail.jsx}}.",
        ],
        "acceptance": ["Creating an incident and opening its page shows it progress to a rendered report without a manual refresh; polling stops afterwards (check the network tab)."],
        "files": ["{{fe:src/pages/incident-detail.jsx}}", "{{fe:src/routes/incidents/$incidentId.tsx}}"],
        "depends": ["FE-7.2"],
        "commit": "feat(ui): poll incident status and render RCA report",
    },
    {
        "key": "FE-7.4", "repo": "frontend", "type": "dev", "step": 7, "priority": "P2", "size": "S",
        "areas": ["ui"],
        "title": "Submit hypothesis feedback",
        "summary": "Let users tell us whether the RCA was right; the backend stores one feedback per incident.",
        "tasks": [
            "Feedback buttons on the report call `POST /incidents/{id}/feedback` with the fields of `FeedbackRequest` (backend `models/schemas.py`).",
            "After submitting, show the submitted state; on reload, reflect existing feedback if the API returns it.",
            "Handle the \"already submitted\" error gracefully.",
        ],
        "acceptance": ["Feedback is stored once and the UI shows it as submitted."],
        "files": ["{{fe:src/pages/incident-detail.jsx}}"],
        "depends": ["FE-7.3"],
        "commit": "feat(ui): submit hypothesis feedback",
    },
    {
        "key": "FE-7.5", "repo": "frontend", "type": "devops", "step": 7, "priority": "P1", "size": "M",
        "areas": ["ci-cd", "infra"],
        "title": "Deploy the SSR frontend to Cloud Run",
        "summary": "Host the TanStack Start app next to the API with automated deploys.",
        "tasks": [
            "Run `npm run build` and confirm the server output and start command (the custom entry is {{fe:src/server.ts}}).",
            "Write a multi-stage `Dockerfile` (node LTS build stage, slim runtime, non-root user, listen on `$PORT`).",
            "`VITE_*` values are baked in at build time: pass them as build args from GitHub Actions variables.",
            "`.github/workflows/deploy.yml` on push to `master`: Workload Identity Federation (same pattern as the backend), build, Trivy scan, push to Artifact Registry, `gcloud run deploy incidentiq-web`.",
            "Custom domain; add it to Firebase authorized domains and to the backend `CORS_ALLOWED_ORIGINS`.",
        ],
        "acceptance": ["Merging to `master` deploys; the production URL serves SSR pages and login works there."],
        "files": ["`Dockerfile` (new)", "`.github/workflows/deploy.yml` (new)"],
        "depends": ["FE-0.2", "FE-2.0"],
    },
    {
        "key": "FE-7.6", "repo": "frontend", "type": "qa", "step": 7, "priority": "P1", "size": "M",
        "areas": ["ui"],
        "title": "Test plan: frontend on real data (Step 7 exit)",
        "summary": "Verify every authenticated screen against the production backend.",
        "tasks": [
            "No static design data left: `grep -rn \"INC-20\" src/pages` returns nothing.",
            "Each page shows its loading, empty and error states (stop the backend to force errors).",
            "Incident detail: polling starts and stops correctly; a failed incident shows its error.",
            "Feedback can be submitted once.",
            "API keys and integrations pages work for owners; members see read-only views.",
            "No hydration warnings in the browser console on any page.",
            "Keyboard-only navigation through list, detail and dialogs; visible focus.",
            "Layouts at 375 px, 768 px and 1440 px.",
            "Latest Chrome, Firefox and Safari.",
            MANUAL_QA_RECORD_TASK,
        ],
        "acceptance": [MANUAL_QA_ACCEPTANCE],
        "depends": ["FE-7.2", "FE-7.3", "FE-7.4", "FE-7.5", "FE-4.1", "FE-5.1"],
    },

    # =====================================================================
    # STEP 8: Tests
    # =====================================================================
    {
        "key": "BE-8.0", "repo": "backend", "type": "qa", "step": 8, "priority": "P2", "size": "M",
        "areas": ["ci-cd"],
        "title": "Set up backend test infrastructure: pytest, Postgres, fixtures",
        "summary": "The base every other test issue builds on. `tests/` holds only empty `__init__.py` files today.",
        "tasks": [
            "`requirements-dev.txt`: `pytest`, `pytest-asyncio`, `pytest-cov`, `httpx`, `respx` (mock outbound HTTP).",
            "`pyproject.toml` or `pytest.ini`: `asyncio_mode = auto`, `testpaths = tests`.",
            "`tests/conftest.py`: set the required env vars **before** importing `config` (Settings is built at import time); "
            "run `alembic upgrade head` once per session against a test database; truncate tables between tests.",
            "Test database: a `postgres-test` service in {{be:docker-compose.yml}} locally; a service container in CI.",
            "App client: `httpx.AsyncClient(transport=ASGITransport(app=main.app))`.",
            "Fixtures: `org`, `api_key` (returns the raw key), `firebase_token(uid, email, **claim_overrides)` signed with a test RSA key "
            "while patching the cert fetcher in `utils/firebase_auth.py`, `ingest_token`.",
            "Patch the pipeline entry point so no test ever calls Gemini.",
            "README section \"Running tests\".",
        ],
        "acceptance": ["`pytest` runs green locally and in CI with one trivial `/health` test."],
        "files": ["`tests/conftest.py` (new)", "`requirements-dev.txt`", "{{be:docker-compose.yml}}"],
        "notes": "This can be started any time. Doing it during Step 2 makes the middleware rewrite much safer.",
        "commit": "test: add pytest infrastructure and fixtures",
    },
    {
        "key": "BE-8.1", "repo": "backend", "type": "qa", "step": 8, "priority": "P2", "size": "M",
        "areas": ["auth"], "labels": ["security"],
        "title": "Cover the auth middleware credential paths",
        "summary": "Table-driven tests for every credential type on every route class.",
        "tasks": [
            "No header, malformed header, `Basic` on `/incidents`: 401.",
            "Valid API key: 200. Revoked key: 401. Key of an inactive org: rejected.",
            "Legacy SHA-256 key is accepted and upgraded to `hash_version = 2`.",
            "Valid Firebase token on `/management/*` and `/incidents/*`: 200.",
            "Expired token, wrong `aud`, wrong `iss`, bad signature, unknown `kid` (refetch once, then 401): 401.",
            "Firebase user without org: `/me` 200, `/incidents` 403.",
            "API key on `/management/*` and `/me`: 401.",
            "Ingest token on `/incidents`: 401. API key or Firebase token on `/ingest/*`: 401.",
            "`OPTIONS` preflight and `/health` pass without credentials.",
        ],
        "acceptance": [AUTOMATED_QA_ACCEPTANCE],
        "files": ["`tests/test_middleware/test_auth.py` (new)"],
        "depends": ["BE-8.0", "BE-2.6", "BE-4.2"],
        "commit": "test(api): cover auth middleware credential paths",
    },
    {
        "key": "BE-8.2", "repo": "backend", "type": "qa", "step": 8, "priority": "P2", "size": "M",
        "areas": ["api"], "labels": ["security"],
        "title": "Verify cross-tenant isolation",
        "summary": "Org A can never see or change org B's data, through any route.",
        "tasks": [
            "Org A cannot read org B's incident, status, report or feedback: 404 (not 403, to avoid confirming the id exists).",
            "Org A cannot submit feedback on org B's incident.",
            "`GET /incidents` only returns the caller's incidents.",
            "Revoking org B's API key id as org A: 404, and the key still works.",
            "Log source test uses the caller's own tenant service account, never one derived from the request body.",
            "GitHub installation of org B is never used for org A's analysis.",
        ],
        "acceptance": [AUTOMATED_QA_ACCEPTANCE],
        "files": ["`tests/test_routers/test_tenant_isolation.py` (new)"],
        "depends": ["BE-8.0", "BE-7.1"],
        "commit": "test(api): verify cross-tenant isolation",
    },
    {
        "key": "BE-8.3", "repo": "backend", "type": "qa", "step": 8, "priority": "P2", "size": "S",
        "areas": ["ingest"],
        "title": "Test alert ingest deduplication and quota",
        "summary": "Automated coverage for the rules in plan section 3.3.",
        "tasks": [
            "Open payload creates one incident with `triggered_by = alert` and seeded services.",
            "Same payload twice in sequence: second returns `duplicate`.",
            "Same payload twice concurrently (`asyncio.gather`): exactly one incident row.",
            "Closed payload: `ignored`.",
            "Non-JSON body: 400. Missing optional fields: accepted.",
            "Over quota: incident `skipped`, pipeline not called.",
            "Token rotation: old token valid inside the grace period, rejected after (freeze time).",
        ],
        "acceptance": [AUTOMATED_QA_ACCEPTANCE],
        "files": ["`tests/test_routers/test_ingest.py` (new)"],
        "depends": ["BE-8.0", "BE-4.3"],
        "commit": "test(api): cover alert ingest dedup and quota",
    },
    {
        "key": "BE-8.4", "repo": "backend", "type": "qa", "step": 8, "priority": "P2", "size": "L",
        "areas": ["pipeline"],
        "title": "Unit test agent nodes with a mocked LLM",
        "summary": "Each LangGraph node tested in isolation with deterministic LLM output.",
        "tasks": [
            "Find the seam where the Gemini client is created (search `agents/` and `pipeline/` for the model construction) and patch it with a fake returning canned responses.",
            "One test module per agent: {{be:agents/triage.py}}, {{be:agents/log_analysis.py}}, {{be:agents/deploy_correlation.py}}, {{be:agents/synthesis.py}}, {{be:agents/report.py}}. Assert the state keys each node writes.",
            "Malformed or empty LLM output: the node fails the way the pipeline expects (retry or a clear error), see {{be:pipeline/retry.py}}.",
            "Pure function tests for {{be:pipeline/calibration.py}} and {{be:tools/log_parser.py}}.",
            "One graph-level test of {{be:pipeline/graph.py}} with every node mocked, checking the fan-out / fan-in order.",
        ],
        "acceptance": ["All agent tests run in under 10 s with no network access."],
        "files": ["`tests/test_agents/` (existing, empty)"],
        "depends": ["BE-8.0"],
        "commit": "test(agent): unit test agent nodes with mocked LLM",
    },
    {
        "key": "BE-8.5", "repo": "backend", "type": "devops", "step": 8, "priority": "P2", "size": "S",
        "areas": ["ci-cd"],
        "title": "Run tests in CI and gate deploys on them",
        "summary": "Tests only protect `main` if they block merging and deploying.",
        "tasks": [
            "Add a Postgres service container and `pytest --cov` to `.github/workflows/ci.yml`; upload the coverage report as an artifact.",
            "In {{be:.github/workflows/deploy.yml}}, add a test job and make the deploy job `needs:` it.",
            "Make the test job a required status check on `main`.",
        ],
        "acceptance": ["A PR with a failing test cannot merge, and a failing test on `main` does not deploy."],
        "files": ["`.github/workflows/ci.yml`", "{{be:.github/workflows/deploy.yml}}"],
        "depends": ["BE-8.0", "BE-0.2"],
        "commit": "chore(ci): run tests on pull requests and before deploy",
    },
    {
        "key": "FE-8.1", "repo": "frontend", "type": "qa", "step": 8, "priority": "P2", "size": "M",
        "areas": ["auth"],
        "title": "Vitest unit tests for the API client and auth guard",
        "summary": "Lock in the SSR safety fixes and redirect rules with tests.",
        "tasks": [
            "Add `vitest`, `@testing-library/react`, `jsdom`; a `test` script; run it in the frontend CI workflow.",
            "`api.ts`: `getToken` is called on every request; two concurrent calls with different `getToken` functions send different headers; missing or relative `VITE_API_BASE_URL` throws; FastAPI `detail` strings and 422 arrays become readable messages.",
            "Extract the redirect rule into a pure function and test it: `/incidents` allowed; `//evil.com`, `https://evil.com` and `javascript:` rejected.",
            "Auth error mapping returns text for every mapped code and a generic fallback.",
        ],
        "acceptance": ["Tests pass in CI and fail if the module-level token provider is reintroduced."],
        "files": ["{{fe:src/lib/api.ts}}", "`src/lib/__tests__/` (new)"],
        "depends": ["FE-2.2", "FE-2.5", "FE-0.2"],
        "commit": "test(api): cover API client and auth redirect rules",
    },
    {
        "key": "FE-8.2", "repo": "frontend", "type": "qa", "step": 8, "priority": "P3", "size": "M",
        "areas": ["auth", "ui"],
        "title": "Playwright smoke test: sign up to first API key",
        "summary": "One end-to-end test that the most important journey still works.",
        "tasks": [
            "Playwright against the local dev server, the Firebase Auth emulator and a local backend (docker compose).",
            "Journey: sign up, verify the email through the emulator REST API, create an org, mint an API key, see it in the list, revoke it.",
            "Run it nightly in CI (not on every PR, to keep PRs fast).",
        ],
        "acceptance": ["The journey passes headless in CI."],
        "depends": ["FE-8.1", "FE-2.7"],
        "commit": "test(e2e): smoke test sign-up to first API key",
    },
]


# One tracking issue per step, created in the backend repo after all issues.
EPICS = [
    {"step": 0, "priority": "P1", "title": "Step 0: Repo hygiene and CI",
         "goal": "One working branch per repo, protected default branches, and CI on every pull request in both repos.",
         "done_when": "Both repos have a single working branch, protected defaults, and required CI checks."},
    {"step": 2, "priority": "P0", "title": "Step 2: Firebase authentication",
         "goal": "Humans sign in with Firebase; machines keep API keys; the admin bootstrap secret is gone. Fixes problems 3, 4 and 12.",
         "done_when": "A new user signs up in the browser, creates an organisation, mints an API key, and the old admin secret path returns 401."},
    {"step": 3, "priority": "P0", "title": "Step 3: Keyless GCP connection",
         "goal": "Customers grant a per-tenant service account read access; we impersonate it. No customer key ever leaves their account. Fixes problems 1 and 10.",
         "done_when": "A GCP project is connected without any key leaving the customer's account, and a missing grant produces a clear message instead of a failed incident at 3am."},
    {"step": 4, "priority": "P1", "title": "Step 4: Alert ingest",
         "goal": "Cloud Monitoring alerts start analyses automatically, deduplicated and within a budget. Fixes problem 5.",
         "done_when": "A test alert policy in a real GCP project produces a completed RCA with no human action, and resending the same alert does not create a second incident."},
    {"step": 5, "priority": "P0", "title": "Step 5: GitHub App",
         "goal": "Replace the shared personal access token with a GitHub App installed by each customer. Fixes problem 2.",
         "done_when": "The PAT is revoked and every analysis uses a short lived installation token scoped to the customer's installation."},
    {"step": 6, "priority": "P2", "title": "Step 6: Reliability and correctness",
         "goal": "Fix problems 6, 7, 8, 9 and 11, and remove the reports stub.",
         "done_when": "Analyses survive deploys and scale-in, timestamps are real, migrations run on deploy, and nothing blocks the event loop."},
    {"step": 7, "priority": "P1", "title": "Step 7: Frontend on real data",
         "goal": "Every authenticated screen reads from the backend, and the frontend is deployed.",
         "done_when": "No static design data remains and every page has loading, empty and error states."},
    {"step": 8, "priority": "P2", "title": "Step 8: Tests",
         "goal": "The minimum test suite before calling this production ready (problem 13).",
         "done_when": "Auth paths, tenant isolation, ingest dedup and agent nodes are tested and the tests gate merges and deploys."},
]
