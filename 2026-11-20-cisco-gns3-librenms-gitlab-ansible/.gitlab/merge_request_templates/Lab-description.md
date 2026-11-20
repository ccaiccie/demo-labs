## Manual-first Cisco adoption / description proposal
- Target: lab-r1 IOSv router or lab-sw1 IOSv-L2 switch:
- Verified image/version and practice interface:
- Manual baseline evidence (sanitized managed slice only):
- No-op adoption result:
- Description before / after:
- Baseline and intent hashes from review.json:
- Offline test result / native syntax-check / live dry-run (label separately):
- Rollback and verification:

## Review checklist
- [ ] Dedicated Ubuntu guest only; isolated lab, no production management route.
- [ ] Existing manual configuration adopted without change first.
- [ ] Exact non-management practice interface verified.
- [ ] One router and one switch proposal reviewed individually.
- [ ] Change and revert affect only approved description.
- [ ] No credentials or raw backups committed.
- [ ] CI renders only; no deployment job.
- [ ] Separate approved live execution and post-change verification required.
