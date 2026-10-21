# GSADF: official quarterly data / R2-first storage

Production dataflow (on `main` after merge):

1. Restore verified `gsadf/v1/latest.json` archive bundle from the existing private R2 bucket.
2. Download official OECD Korea quarterly RHP, PIR and PTR. Merge changes and log official revisions.
3. Compare current series fingerprint to the previous verified vintage. When unchanged, skip expensive simulations and uploads.
4. On changed observations only, perform 2,000 Monte Carlo null paths for each of the three series.
5. Upload a versioned SHA256-addressed ZIP bundle to R2, verify its size/hash metadata.
6. Independently back up the same ZIP to the existing OAuth user's private Google Drive folder `Edward_부동산데이터_R2백업/GSADF`, verifying Drive MD5 and size. Only then update the R2 latest pointer.
7. Keep **only** a very small status artifact in GitHub Actions for 7 days. Raw source and Monte Carlo history must NOT be committed, uploaded as GitHub artifacts, or exposed on GitHub Pages.

This uses the **same existing secrets** R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME, GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET and (for OAuth bootstrap if needed) GOOGLE_OAUTH_REFRESH_TOKEN. No OAuth client JSON or credentials in the repository. If R2 or Google Drive verification fails, the run fails rather than falsely recording success.

The previous regional housing CSV backup remains untouched; the new GSADF folder is separate and does not run the annual housing-CSV merger. It also does not modify `risk-data.js`, `index.html`, or composite scoring.

**Status:** New storage and statistical workflow code staged in PR #19, not proof of successful remote operations. The actual OECD API response, 2,000 rep Monte Carlo results, and private R2/Drive credentials must all be checked on a real GitHub Actions run. GSADF results always have `approval=PENDING_INDEPENDENT_VALIDATION` and `eligibleForComposite=false` until independently verified. The ADF lag-0 Gaussian random-walk model remains a research prototype requiring sensitivity tests.

Reference: https://data-explorer.oecd.org/
