# Recruiter Panel Interaction Model

The recruiter panel (`!clanmatch`) renders the interactive filter controls as one
message. Search results are posted as a **separate, persistent message** in the
target recruiter thread. When filters change we edit those two messages in
place:

* The panel message updates silently — no progress pings or extra replies.
* Results reuse the same thread message so recruiters always have a single,
  up-to-date results card (with pager buttons when multiple pages exist).
* If a search returns no matches, the results message is edited with a neutral
  "No matching clans found" embed rather than posting new follow-ups.

Ephemeral messages are reserved for guard rails (for example preventing other
users from pressing the controls); the panel refresh flow itself never emits
"Updating…" or other transient notices.
