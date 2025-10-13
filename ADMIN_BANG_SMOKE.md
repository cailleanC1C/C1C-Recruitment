# Admin Bang Shortcuts – Smoke Checklist

- [ ] Startup logs show parsed Admin role ID and Staff role IDs.
- [ ] User with Admin role can run `!health` and `!rec health` successfully.
- [ ] User with Staff (non-Admin) role can run `!rec health` but `!health` is denied as "Staff only".
- [ ] User without Staff roles is denied for both `!rec health` and `!health` with the "Staff only" message.
- [ ] Ping command and mention prefixes continue to function without regression.
