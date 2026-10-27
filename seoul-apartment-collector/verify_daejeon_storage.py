#!/usr/bin/env python3
"""Run the same full live-reread audit on completed Daejeon archives."""
import audit_storage


if __name__=='__main__':
    audit_storage.REPORT=audit_storage.BASE/'daejeon_coverage_audit.json'
    audit_storage.DETAILS=audit_storage.BASE/'daejeon_coverage_audit_scopes.jsonl.gz'
    raise SystemExit(audit_storage.run(['daejeon'],workers=12,live_source=True,max_requests=1200))
