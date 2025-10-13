# CoreOps RBAC Smoke Checklist

- [ ] Set `ADMIN_ROLE_ID` to an admin-only Discord role ID and `STAFF_ROLE_IDS` to any additional staff role IDs (comma separated).
- [ ] As a member holding the admin role, send `health`, `!rec health`, and `@RecruitmentBot health` — all should execute successfully.
- [ ] As a non-staff member, send `health` (no prefix) — should receive “Staff only”.
- [ ] As the same non-staff member, send `!rec health` — should also receive “Staff only”.
- [ ] Run `!rec help` (staff and non-staff) — ensure sections are correct and the footer shows `Bot vX • CoreOps v1.0.0 • <time>`.
- [ ] Mention the bot (`@RecruitmentBot ping`) — ensure standard mention behavior still works.
