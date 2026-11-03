#copy folder
# Smart Image Text Search — Self-Contained Windows Desktop App

This version uses a native PyQt6 desktop interface and bundles Tesseract OCR
into the application during the Windows build. The legacy HTML interface is
not loaded by the desktop application.

## Client does not need

- Python
- pip
- virtual environment
- Tesseract installation
- PATH configuration
- PostgreSQL

## Build

On the Windows development computer:

```bat
scripts\setup_windows.bat
```

Then:

```bat
scripts\build_windows.bat
```

The script downloads Tesseract OCR, temporarily installs it on the BUILD computer, copies the Tesseract executable/DLLs/language data into the project, and packages everything with PyInstaller.

Output:

```text
dist\SmartImageSearch\SmartImageSearch.exe
```

Copy the whole `dist\SmartImageSearch` folder to the client.

## Windows installer

To create a normal Windows installer with Start Menu/Desktop shortcuts and an
uninstaller, install [Inno Setup 6](https://jrsoftware.org/isinfo.php), ensure
`ISCC.exe` is on `PATH`, and run:

```bat
scripts\build_installer.bat
```

The installer is created at:

```text
dist\installer\SmartImageSearch-Setup.exe
```

For the licensing-enabled installer, run:

```bat
scripts\build_licensed_installer.bat
```

Use the resulting `dist\installer\SmartImageSearch-Licensing-Setup.exe`.
It installs the current licensing-enabled desktop executable, clears any
cached local licence during install or reinstall, and launches the app after
setup; the app then asks for the product key. The existing
`SmartImageSearch-Setup.exe` is preserved and does not include this change.

The installed application can be removed from Windows Settings > Apps or from
the Start Menu. Uninstalling removes the app files and its local data under
`%LOCALAPPDATA%\SmartImageSearch`, including the search index, OCR word boxes,
and settings. It does not remove the image and PDF files in folders you scanned.
The local data is reused when you restart the app while it is installed.
Rescans only OCR files whose modification time or file size has changed, except
that an OCR pipeline update triggers a one-time refresh of indexed images.
Sparse OCR results and tables with a lot-number heading but no recognized row
ID get a second page-layout pass. More expensive contrast and rotation retries
run only when those passes still recognize very little text. This keeps
ordinary pages to one OCR pass while preserving extra recovery work for
difficult scans. Preprocessing can improve faded or low-contrast pages, but
cannot recover character detail missing from the source image.

The desktop app completes folder discovery and text extraction before enabling
search. During a scan, the search controls remain disabled; after the full scan
finishes, search is enabled and the current query is run against the completed
index. A first full-text scan still takes time proportional to the number, size,
and quality of the images: OCR must inspect each page, and low-confidence pages
may need multiple passes. The first scan of a large folder should not be
expected to finish in a few seconds; unchanged files are skipped on later scans.

## Single EXE

After `build_windows.bat` completes:

```bat
scripts\build_onefile.bat
```

Output:

```text
dist\SmartImageSearch.exe
```

Copy this one EXE to the client.

## Client usage

1. Double-click `SmartImageSearch.exe` and enter the product key issued by the administrator the first time it starts.
2. Click `Scan / Index Folder` to index images and PDFs under that folder.
3. Search any word, name, ID, certificate number, or other text.
4. Open a matching image with `View Image` or open a PDF in the system viewer.

Search accepts quoted exact phrases (for example, `"annual report"`), AND
queries (for example, `smith AND 2024`), and OR alternatives (for example,
`invoice OR receipt`). Partial-word and exact matches rank first, followed by
minor spelling-error/OCR-confusion matches and then partial matches for
space-separated multi-word queries. Numeric searches tolerate common OCR
confusions such as `O`/`0` and `I`/`1`. As a final fallback, long numeric IDs
may match one digit off when OCR misreads a character.

The native application provides the same workflows without opening a browser:
folder selection, recursive indexing of images and PDFs, re-scan OCR, archive
search, image preview, PDF opening in the system viewer, and file-path copying.
PDF text is extracted directly; pages without a text layer are OCR-scanned when
Tesseract is available. Folder traversal does not follow symbolic links.
<!-- The old browser workflow is retained in source only for reference. -->
<!--
The installed application can be removed from Windows Settings > Apps or from
3. Enter the main folder containing images.
4. Click `Scan / Index Folder`.
5. OCR scans images in all nested folders.
6. Search any word, name, ID, certificate number, or other text.
7. Matching images are displayed.
-->

## Licensing platform

The licensing backend and browser-based admin dashboard are separate from the
OCR client. The client activates against the public licence endpoint and checks
a signed, device-bound entitlement at startup. It allows up to the configured
offline grace period after successful online validation.

### Development

From PowerShell, configure and start the backend:

```powershell
cd backend
Copy-Item .env.example .env
python -m pip install -r requirements.txt
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The example now targets local PostgreSQL. Before starting, create the
`scanora_licensing` database in PostgreSQL and replace
`REPLACE_WITH_LOCAL_PASSWORD` in `backend/.env` with the local PostgreSQL role's
password. URL-encode reserved characters in the password. The existing
`backend/.env` and SQLite database are not modified by this example change.

Set a local development admin password in `backend/.env` before first startup.
The development email provider defaults to `mock`; it records mail activity but
does not deliver messages. Licence creation now sends the product key to the
selected customer's email automatically; with `mock`, the dashboard explicitly
reports that delivery was simulated. To send real local test email, first
revoke any exposed mail credential, then set `EMAIL_PROVIDER=smtp`, use the
provider's SMTP host/port, set `SMTP_USERNAME` to the full mailbox address,
store a newly generated app password in `SMTP_PASSWORD`, and set
`SMTP_FROM_EMAIL` to an authorized sender. Restart the backend after editing
`.env`. Start the dashboard in another terminal:

```powershell
cd admin-dashboard
$env:VITE_API_BASE_URL = "http://localhost:8000/api/v1"
npm install
npm run dev
```

### Production configuration

Production startup refuses development secrets, SQLite, mock email, and
non-HTTPS CORS origins. Put deployment values in an untracked `backend/.env`
or the hosting platform's secret manager. Configure at least:

- `ENVIRONMENT=production`
- `SECRET_KEY`: unique, random, at least 32 characters, and backed up securely
- `ADMIN_EMAIL` and a unique `ADMIN_PASSWORD` of at least 12 characters
- `DATABASE_URL`: PostgreSQL using `postgresql+psycopg://`
- `EMAIL_PROVIDER=smtp`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM_EMAIL`, and either
	STARTTLS or SMTP-over-SSL; provide `SMTP_USERNAME` and `SMTP_PASSWORD` when
	required by the provider
- `CORS_ORIGINS`: JSON array containing only HTTPS admin-dashboard origins
- `LICENCE_OFFLINE_GRACE_HOURS`: signed offline allowance from 0 to 720 hours

The `.env` file is ignored by Git; `.env.example` contains placeholders only.
Apply database migrations from `backend` before starting the API:

```powershell
python -m alembic upgrade head
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Render Blueprint deployment

`render.yaml` defines the API, PostgreSQL database, and admin dashboard. Push
this project to a private GitHub repository and create a Blueprint from it in
Render. The API and database use Oregon; keep them in the same region or change
their region consistently. The static dashboard is served through Render's
global CDN.

Before deploying, set the API's manual environment variables in Render:
`ADMIN_EMAIL`, `SMTP_HOST`, `SMTP_FROM_EMAIL`, and `CORS_ORIGINS`. The
`CORS_ORIGINS` value must be a JSON array containing the dashboard's exact
HTTPS origin, for example `["https://scanora-admin-dashboard.onrender.com"]`.
Set `SMTP_USERNAME` and `SMTP_PASSWORD` together if the SMTP provider requires
authentication. The Blueprint generates `SECRET_KEY` and `ADMIN_PASSWORD`;
retrieve the generated admin password from Render's secret environment and
store it securely. Do not commit `.env` or credentials.

The static site obtains the API hostname from the Blueprint and configures its
HTTPS `/api/v1` URL at build time. Migrations run as the API's pre-deploy
command, and `/health` verifies a database connection. Confirm
`https://<api-service>.onrender.com/health` returns `{"status":"ok"}` after
deployment. Then fetch the production signing public key using the command
below and place it with the API URL in each desktop client's
`licence-config.json`.

### Manual Render deployment (alternative)

1. Push this repository to a private GitHub repository. Do not commit `.env` or
	any SMTP/database credentials.
2. In Render, create a PostgreSQL database in the same region as the API. Copy
	its **Internal Database URL** from the database Connect panel.
3. Create a Web Service for the repository with root directory `backend`, build
	command `pip install -r requirements.txt`, and start command
	`uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Set the pre-deploy command
	to `python -m alembic upgrade head` when available. If the selected Render
	plan has no pre-deploy command, use
	`python -m alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
	as the start command for a single API instance.
4. Add the production secrets in Render's Environment settings: `ENVIRONMENT`,
	`DATABASE_URL` (the internal URL from step 2), `SECRET_KEY`, `ADMIN_EMAIL`,
	`ADMIN_PASSWORD`, SMTP settings, and `LICENCE_OFFLINE_GRACE_HOURS`. The
	PostgreSQL URL is normalized to psycopg v3 by the application. Do not add
	quotes around values in Render's environment editor. `CORS_ORIGINS` can be
	set after creating the dashboard in step 5.
5. Create a Render Static Site from the same repository with root directory
	`admin-dashboard`, build command `npm ci && npm run build`, and publish
	directory `dist`. Set `VITE_API_BASE_URL` to
	`https://<api-service>.onrender.com/api/v1`.
6. Copy the dashboard's HTTPS origin into the API's `CORS_ORIGINS` as a JSON
	array, for example `["https://<dashboard>.onrender.com"]`, then redeploy the
	API. Verify `https://<api-service>.onrender.com/health` returns `{"status":"ok"}`.
7. Fetch the production signing public key using the command above and put it
	with the API URL in each desktop client's `licence-config.json`.

The dashboard build fails if its production API URL is missing, insecure, or
does not point to `/api/v1`; local development still defaults to localhost.
GitHub Actions runs the Python suites and dashboard tests/build, and produces
a Windows desktop build artifact. That artifact is unsigned; configure Windows
code signing with the release owner before distributing a production installer.

Changing `DATABASE_URL` only points the app at PostgreSQL; it does not copy
existing rows from the local `backend/licensing_dev.db`. Back up and migrate
customers, products, licences, and activation records separately before
switching if those records must be retained. Do not run `alembic upgrade head`
against a production database until its URL and backup have been verified.

Put the API and dashboard behind HTTPS. Configure the dashboard build with
`VITE_API_BASE_URL=https://<api-host>/api/v1`. Get the matching signing key
from the production backend environment:

```powershell
python -c "from app.core.security import get_licence_signing_public_key; print(get_licence_signing_public_key())"
```

Create `%LOCALAPPDATA%\SmartImageSearch\licence-config.json` on each desktop
client with the deployed API URL and matching public key:

```json
{
	"api_base_url": "https://<api-host>/api/v1",
	"public_key": "<base64-ed25519-public-key>"
}
```

The external file configures packaged clients without rebuilding the EXE.
`SCANORA_LICENCE_API_URL` and `SCANORA_LICENCE_PUBLIC_KEY` environment
variables override the file values. Keep the public key paired with the
backend's stable `SECRET_KEY`; remote endpoints are rejected without a valid
signing-key pin. The client defaults to localhost only for development.

The signing and product-key encryption keys are derived from `SECRET_KEY`.
Keep it stable and backed up: changing it invalidates issued signatures and
prevents decryption of stored product keys. Back up PostgreSQL and secrets
before changing it. Deployment, real SMTP delivery, TLS termination, and
production client packaging still require your hosting URL and provider details.

## Important

This source ZIP contains the automatic bundling/build mechanism. It does not contain a Windows Tesseract binary because this build environment cannot execute/package a Windows PE executable. The supplied Windows build script creates the fully self-contained client EXE on a Windows development PC.

The Windows Tesseract binary referenced by the build script is from the UB Mannheim distribution, which is documented by the Tesseract project as a Windows binary provider.
