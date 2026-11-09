# ITHutir Pinterest OS — Google Sheets (Linux Mint)

## Data flow
Google Sheets (selected spreadsheet) ↔ explicit import/export ↔ local SQLite.
No Pinterest API, no automatic posting, no scheduled synchronization.

## Setup
1. In Google Cloud Console, create or select a project and enable **Google Sheets API**.
2. Configure the OAuth consent screen. For an external app in testing mode, add the Google account as a test user. Google may impose testing-mode refresh-token restrictions.
3. Create an OAuth client of type **Desktop app** and download its JSON configuration. **Never commit that JSON to GitHub**.
4. In the app's Python environment run `pip install -r requirements-google.txt`.
5. Ensure Linux Mint has an available, unlocked Secret Service keyring (e.g. GNOME Keyring). The app must not fall back to storing OAuth tokens in plaintext.
6. Open SETTINGS → Google Sheets, paste the specific spreadsheet URL and click **Validate and save link**.
7. Click **Connect Google (OAuth desktop)**, select your local OAuth client JSON, authorize in the browser.
8. Click **List authorized worksheets** and select a tab. Use **Preview selected private worksheet** to verify access.

## Data operations
- **Import selected worksheet as NEW products** requires exactly `name,category,target_url` headers; it validates the whole selection and rejects existing-name collisions. Confirm before adding records to SQLite.
- **Export products to NEW worksheet** creates a fresh tab; existing tabs are not overwritten.
- **Export USD report to NEW worksheet** creates a fresh tab with estimated metrics. It does not claim verified net profit.
- Private-sheet access is granted by Google OAuth, not by a pasted link alone.
- The current integration does **not** import pins, export time records, update existing Google rows, resolve edit conflicts, or synchronize automatically.
- Disconnect deletes locally stored credentials; separately revoke Google authorization from Google Account security settings if needed.

## Security and limits
- OAuth scope: `spreadsheets` (read/write access to spreadsheets the account can access). This is broader than a single URL; the app UI intentionally operates on the selected spreadsheet. Review the consent screen carefully.
- OAuth credentials are held in the OS keyring; SQLite and QSettings store no tokens.
- Google operations are synchronous; a slow connection can temporarily freeze the settings window. Background worker support is a later improvement.
- Never import from untrusted spreadsheets. Validate names and target URLs before using them in marketing.
- Failed creation of a new export tab can leave an empty or partial tab for manual cleanup.
- Run tests before deployment; no live Google API test is implied by this implementation.
