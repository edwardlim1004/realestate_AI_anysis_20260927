# Korean GSADF official-data isolation

Runs on GitHub Actions monthly or on workflow_dispatch. Downloads OECD RHP/PIR/PTR (quarterly), records source manifest and original response, rejects absent or inconsistent inputs and runs 2,000 Monte Carlo null simulations per measure. Outputs are uploaded as a workflow artifact; neither risk-data.js nor index.html is modified.

## Gate

This is a **research prototype**, using an intercept-only lag-0 ADF with an iid Gaussian random-walk null. It does NOT satisfy independent lag-order sensitivity, bootstrap and historical out-of-sample validation. Every output has approval=PENDING_INDEPENDENT_VALIDATION and eligibleForComposite=false. The raw data must be audited before publication. The scheduled workflow runs only on the repository default branch.

## Source
OECD Analytical house prices: https://data-explorer.oecd.org/
