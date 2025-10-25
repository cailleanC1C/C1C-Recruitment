# Phase 5 Diagnostics — `!clansearch` Member Runtime (2025-10-25)

## Executive Summary
The freshly wired member controller reproduces the Sheets-backed clan lookup, but its zero-result branch stops after sending a plain embed without attaching `MemberSearchPagedView`. Because the view never binds in that path, members see a bare "No matching clans" message and lose access to pagination/view-mode controls, diverging from the legacy expectation that the panel stays interactive even when empty. The legacy audit confirms the results panel should always remain available so the opener can rerun the search or adjust filters without reissuing the command.【F:modules/recruitment/views/member_panel.py†L170-L188】【F:AUDIT/20251019_PHASE5/MM_clansearch_audit.md†L58-L63】

The command responding only in `#bot-test` aligns with an unhandled send-permission failure. `_send_or_edit` calls `ctx.reply` (or `channel.send`) without trapping `discord.Forbidden`/`HTTPException`; when the bot lacks send/embed/component privileges in a channel, the coroutine raises, the global `on_command_error` logs and swallows it, and the user sees nothing. `bot-test` is the one venue where the bot currently retains full send rights, so the command behaves there but silently fails elsewhere.【F:modules/recruitment/views/member_panel.py†L256-L280】【F:app.py†L284-L297】

## Symptoms Observed
- Zero-match invocations post only the "No matching clans found" embed without the navigation view.
- Outside `#bot-test`, issuing `!clansearch` yields no response (only a backend log entry).

## Evidence Map
- **Zero-state short-circuit** – `update_results` returns immediately after sending the empty-state embed with `view=None`, never constructing `MemberSearchPagedView` for that message.【F:modules/recruitment/views/member_panel.py†L170-L188】
- **Legacy contract** – Phase 5 baseline documents that the member panel should stay interactive, even after an empty result set, to let the opener adjust filters and retry without re-invoking the command.【F:AUDIT/20251019_PHASE5/MM_clansearch_audit.md†L58-L63】
- **Send path lacks guards** – `_send_or_edit` chooses `ctx.reply` (falling back to `channel.send`) but does not wrap the awaitable, so permission errors bubble out as command exceptions.【F:modules/recruitment/views/member_panel.py†L256-L280】
- **Silent error handling** – The global `on_command_error` only logs the exception; it never notifies the caller, explaining the "nothing happens" report when the send fails.【F:app.py†L284-L297】
- **No channel allowlist** – Intake cog has no per-channel gate or RBAC beyond the cooldown, so behavior differences are environmental rather than intentional gating.【F:cogs/recruitment_member.py†L13-L27】

## Root-Cause Hypotheses (ranked)
1. **Empty-state bypasses view attachment** – `update_results` returns early when `visible_rows` is falsy, leaving the results message without `MemberSearchPagedView`. This strips pagination/view-mode controls and conflicts with the legacy UX that kept controls active after a zero-hit search.【F:modules/recruitment/views/member_panel.py†L170-L188】【F:AUDIT/20251019_PHASE5/MM_clansearch_audit.md†L58-L63】
2. **Unhandled send failures mask channel permission gaps** – `_send_or_edit` does not catch `discord.Forbidden`/`HTTPException` from `ctx.reply`/`channel.send`. In channels where the bot lacks `Send Messages`/`Embed Links`/`Use External Emojis`, the coroutine raises and the global handler logs quietly, so only the `bot-test` channel (where permissions are intact) appears to work.【F:modules/recruitment/views/member_panel.py†L256-L280】【F:app.py†L284-L297】

## Minimal Patch Sketches
> Illustrative snippets only—actual fixes belong in a follow-up PR.

- **Attach the view even when empty**
  ```diff
  diff --git a/modules/recruitment/views/member_panel.py b/modules/recruitment/views/member_panel.py
  --- a/modules/recruitment/views/member_panel.py
  +++ b/modules/recruitment/views/member_panel.py
  @@
  -        if not visible_rows:
  -            embed = discord.Embed(
  -                title="No matching clans found.",
  -                description="Try adjusting your filters and search again.",
  -            )
  -            if filters_text:
  -                embed.set_footer(text=f"Filters used: {filters_text}")
  -            await self._send_or_edit(..., embeds=[embed], files=[], view=None, ...)
  -            return
  +        view = MemberSearchPagedView(
  +            author_id=int(author_id),
  +            rows=visible_rows,
  +            filters_text=filters_text,
  +            guild=guild,
  +        )
  +        if not visible_rows:
  +            empty_embed = discord.Embed(
  +                title="No matching clans found.",
  +                description="Try adjusting your filters and search again.",
  +            )
  +            if filters_text:
  +                empty_embed.set_footer(text=f"Filters used: {filters_text}")
  +            await self._send_or_edit(..., embeds=[empty_embed], files=[], view=view, ...)
  +            return
  ```

- **Harden send/edit path against permission failures**
  ```diff
  diff --git a/modules/recruitment/views/member_panel.py b/modules/recruitment/views/member_panel.py
  --- a/modules/recruitment/views/member_panel.py
  +++ b/modules/recruitment/views/member_panel.py
  @@
  -        if existing is None:
  -            ...
  -            sent = await send(...)
  +        if existing is None:
  +            ...
  +            try:
  +                sent = await send(...)
  +            except discord.Forbidden:
  +                log.warning("member clansearch send blocked", extra={"key": key})
  +                if send is not getattr(channel, "send", None) and getattr(channel, "send", None):
  +                    sent = await channel.send(...)
  +                else:
  +                    await self._notify_permission_block(ctx, interaction)
  +                    return
  +            except discord.HTTPException:
  +                log.exception("member clansearch send failed", extra={"key": key})
  +                await self._notify_permission_block(ctx, interaction)
  +                return
  ```

## Verification Plan
1. Invoke `!clansearch` in a low-permission channel and confirm the bot surfaces a permission warning (or gracefully falls back) instead of silently failing.
2. Trigger a zero-result scenario (e.g., temporarily stub `fetch_clans_async` to return an empty list) and ensure the message still carries `MemberSearchPagedView` controls with disabled navigation.
3. Exercise a non-empty result set to verify pagination still works and the `ACTIVE_PANELS` registry updates as expected.
4. Monitor logs for the new warning/error messages to ensure they fire once per failure and include the `(guild_id, channel_id, user_id)` key for support.

## Risk Notes
- **Permission echoes** – Surfacing permission failures publicly may spam restricted channels; consider short, localized notices (one per invocation) with logging throttled.
- **Component limits** – `MemberSearchPagedView` already uses two component rows; any zero-state tweaks must avoid exceeding Discord’s five-row cap.【F:modules/recruitment/views/shared.py†L90-L164】
- **Sheets latency** – Hardening send logic should maintain the current behavior where data fetch failures fall back to an empty list without crashing.【F:modules/recruitment/views/member_panel.py†L297-L304】

## Appendix – Files Reviewed
- `cogs/recruitment_member.py` – Intake command lacks channel gating; baseline cooldown only.【F:cogs/recruitment_member.py†L13-L27】
- `modules/recruitment/views/member_panel.py` – Core controller; identified zero-state and permission-handling gaps.【F:modules/recruitment/views/member_panel.py†L120-L305】
- `modules/recruitment/views/shared.py` – Paged view component layout, confirming button rows for risk analysis.【F:modules/recruitment/views/shared.py†L15-L189】
- `shared/sheets/async_facade.py` – Sheets adapter simply proxies data; no channel branching.【F:shared/sheets/async_facade.py†L21-L102】
- `app.py` – Global command error handling swallows user feedback, contributing to the silent failure symptom.【F:app.py†L284-L297】
- `AUDIT/20251019_PHASE5/MM_clansearch_audit.md` – Legacy behavior reference for empty-state expectations.【F:AUDIT/20251019_PHASE5/MM_clansearch_audit.md†L58-L63】
