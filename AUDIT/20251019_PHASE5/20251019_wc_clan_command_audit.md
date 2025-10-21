### Entrypoint
- `!clan` is registered via `@bot.command(name="clan")` with the signature `async def clanprofile_cmd(ctx: commands.Context, *, query: str | None = None)`; it lacks cooldown/permission decorators and immediately replies with a usage hint when invoked without a query, wrapping the rest of the handler in a broad `try/except`.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1936-L1978】

`bot_clanmatch_prefix.py:L1936-L1978`
```python
@bot.command(name="clan")
async def clanprofile_cmd(ctx: commands.Context, *, query: str | None = None):
    if not query:
        await ctx.reply("Usage: `!clan <tag or name>` — e.g., `!clan C1CE` or `!clan Elders`", mention_author=False)
        return
    try:
        row = find_clan_row(query)
        if not row:
            await ctx.reply(f"Couldn’t find a clan matching **{query}**.", mention_author=False)
            return

# Build the profile embed as before
        embed = make_embed_for_profile(row, ctx.guild)

# NEW: build attachment for top-right clan tag and send with files=[...]
        tag = (row[COL_C_TAG] or "").strip()
        file, url = await build_tag_thumbnail(ctx.guild, tag, size=TAG_BADGE_PX, box=TAG_BADGE_BOX)
        if url:
            embed.set_thumbnail(url=url)
            msg = await ctx.reply(embed=embed, files=[file], mention_author=False)
        else:
# Fallback: send without thumbnail if we couldn't build one
            msg = await ctx.reply(embed=embed, mention_author=False)

# Keep the 💡 flip and index registration exactly as before
        try:
            await msg.add_reaction("💡")
        except Exception:
            pass

        REACT_INDEX[msg.id] = {
            "row": row,
            "kind": "entry_from_profile",
            "guild_id": ctx.guild.id if ctx.guild else None,
            "channel_id": msg.channel.id,
            "filters": "",
        }

        await _safe_delete(ctx.message)

    except Exception as e:
        await ctx.reply(f"❌ Error: {type(e).__name__}: {e}", mention_author=False)
```

- The command lives in the monolithic prefix bot module that instantiates and runs the bot inline: `REACT_INDEX` is a module-global dict, the bot is created with `commands.Bot(command_prefix="!")`, and the script calls `asyncio.run(main())` in its `__main__` block, so loading the module as a script brings the command online.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1086-L1094】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L2530-L2544】

`bot_clanmatch_prefix.py:L1086-L1094`
```python
# ------------------- Reaction flip registry -------------------
REACT_INDEX: dict[int, dict] = {}  # message_id -> {row, kind, guild_id, channel_id, filters}

# ------------------- Discord bot -------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
```

`bot_clanmatch_prefix.py:L2530-L2544`
```python
async def main():
    try:
        asyncio.create_task(start_webserver())
        token = os.environ.get("DISCORD_TOKEN", "").strip()
        if not token or len(token) < 50:
            raise RuntimeError("Missing/short DISCORD_TOKEN.")
        print("[boot] starting discord bot…", flush=True)
        await bot.start(token)
    except Exception as e:
        print("[boot] FATAL:", e, flush=True)
        traceback.print_exc()
        raise

if __name__ == "__main__":
    asyncio.run(main())
```

### Routing
- Replies are sent back to the invoking channel via `ctx.reply(..., mention_author=False)`, optionally with a crest attachment, and the source command message is cleaned up with `_safe_delete(ctx.message)`; no alternate channel/thread routing occurs.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1936-L1978】

### UI
- The handler seeds a single 💡 reaction and stores toggle metadata in `REACT_INDEX`. The raw reaction event listens for 💡 presses, swaps between profile and entry embeds in-place, updates the stored `kind`, and removes the user’s reaction so it can be re-used.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1936-L1978】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1980-L2034】

`bot_clanmatch_prefix.py:L1980-L2034`
```python
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return  # ignore silently
    try:
        await ctx.reply(f"⚠️ Command error: `{type(error).__name__}: {error}`")
    except:
        pass

@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    try:
        # ignore DMs / self / non-bulb
        if not payload.guild_id or payload.user_id == (bot.user.id if bot.user else None):
            return
        if str(payload.emoji) != "💡":
            return

        info = REACT_INDEX.get(payload.message_id)
        if not info:
            return

        guild = bot.get_guild(info["guild_id"]) if info.get("guild_id") else bot.get_guild(payload.guild_id)
        channel = bot.get_channel(info["channel_id"]) or await bot.fetch_channel(info["channel_id"])
        try:
            msg = await channel.fetch_message(payload.message_id)
        except Exception:
            return

        row = info["row"]

        if info["kind"] == "entry_from_profile":
            # Profile → show Entry Criteria in-place
            embed = make_embed_for_row_search(row, info.get("filters", ""), guild)
            ft = embed.footer.text or ""
            hint = "React with 💡 for Clan Profile"
            embed.set_footer(text=(f"{ft} • {hint}" if ft else hint))

            await msg.edit(embed=embed)
            info["kind"] = "profile_from_search"          # flip the kind for next toggle
            REACT_INDEX[payload.message_id] = info

        else:  # "profile_from_search" → show Profile in-place
            embed = make_embed_for_profile(row, guild)
            await msg.edit(embed=embed)
            info["kind"] = "entry_from_profile"           # flip back
            REACT_INDEX[payload.message_id] = info

# Let users press 💡 again without removing it manually
        try:
            user = payload.member or (guild and guild.get_member(payload.user_id))
            if user:
                await msg.remove_reaction(payload.emoji, user)
        except Exception:
            pass
```

### Embeds & Data
- Profile view builder: `make_embed_for_profile` assembles leadership, boss ranges, CvC/Siege stats, and progression/style, setting a footer that instructs users to react with 💡 for entry criteria.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1875-L1933】

`bot_clanmatch_prefix.py:L1875-L1933`
```python
def make_embed_for_profile(row, guild: discord.Guild | None = None) -> discord.Embed:
# Top line with rank fallback
    rank_raw = (row[COL_A_RANK] or "").strip()
    rank = rank_raw if rank_raw and rank_raw not in {"-", "—"} else ">1k"

    name  = (row[COL_B_CLAN]        or "").strip()
    tag   = (row[COL_C_TAG]         or "").strip()
    lvl   = (row[COL_D_LEVEL]       or "").strip()

# Leadership
    lead  = (row[COL_G_LEAD]        or "").strip()
    deps  = (row[COL_H_DEPUTIES]    or "").strip()

# Ranges
    cb    = (row[COL_M_CB]          or "").strip()
    hydra = (row[COL_N_HYDRA]       or "").strip()
    chim  = (row[COL_O_CHIMERA]     or "").strip()

# CvC / Siege
    cvc_t = (row[COL_I_CVC_TIER]    or "").strip()
    cvc_w = (row[COL_J_CVC_WINS]    or "").strip()
    sg_t  = (row[COL_K_SIEGE_TIER]  or "").strip()
    sg_w  = (row[COL_L_SIEGE_WINS]  or "").strip()

# Footer
    prog  = (row[COL_F_PROGRESSION] or "").strip()
    style = (row[COL_U_STYLE]       or "").strip()

    title = f"{name} | {tag} | **Level** {lvl} | **Global Rank** {rank}"

    lines = [
        f"**Clan Lead:** {lead or '—'}",
        f"**Clan Deputies:** {deps or '—'}",
        "",
        f"**Clan Boss:** {cb or '—'}",
        f"**Hydra:** {hydra or '—'}",
        f"**Chimera:** {chim or '—'}",
        "",
        f"**CvC**: Tier {cvc_t or '—'} | Wins {cvc_w or '—'}",
        f"**Siege:** Tier {sg_t or '—'} | Wins {sg_w or '—'}",
        "",
    ]
    tail = " | ".join([p for p in [prog, style] if p])
    if tail:
        lines.append(tail)

    e = discord.Embed(title=title, description="\n".join(lines))

    thumb = padded_emoji_url(guild, tag)
    if thumb:
        e.set_thumbnail(url=thumb)
    elif not STRICT_EMOJI_PROXY:
        em = emoji_for_tag(guild, tag)
        if em:
            e.set_thumbnail(url=str(em.url))

# Add hint so 💡 can flip to Entry Criteria
    e.set_footer(text="React with 💡 for Entry Criteria")
    return e
```

- Entry criteria view builder: `make_embed_for_row_search` constructs a separate embed for level/spots plus criteria breakdown and also applies the crest thumbnail logic and optional filters footer.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L433-L484】

`bot_clanmatch_prefix.py:L433-L484`
```python
def make_embed_for_row_search(row, filters_text: str, guild: discord.Guild | None = None) -> discord.Embed:
    """Member-facing Entry Criteria card: Level + Spots only (no Inactives/Reserved)."""
    b = (row[COL_B_CLAN] or "").strip()
    c = (row[COL_C_TAG]  or "").strip()
    d = (row[COL_D_LEVEL] or "").strip()
    e_spots = (row[COL_E_SPOTS] or "").strip()

    v  = (row[IDX_V]  or "").strip()
    w  = (row[IDX_W]  or "").strip()
    x  = (row[IDX_X]  or "").strip()
    y  = (row[IDX_Y]  or "").strip()
    z  = (row[IDX_Z]  or "").strip()
    aa = (row[IDX_AA] or "").strip()
    ab = (row[IDX_AB] or "").strip()

# Title: no Inactives/Reserved in member view
    title = f"{b} | {c} | **Level** {d} | **Spots:** {e_spots}"

    lines = ["**Entry Criteria:**"]
    if z:
        lines.append(f"Clan Boss: {z}")
    if v or x:
        hx = []
        if v: hx.append(f"{v} keys")
        if x: hx.append(x)
        lines.append("Hydra: " + " — ".join(hx))
    if w or y:
        cy = []
        if w: cy.append(f"{w} keys")
        if y: cy.append(y)
        lines.append("Chimera: " + " — ".join(cy))
    if aa or ab:
        cvc_bits = []
        if aa: cvc_bits.append(f"non PR minimum: {aa}")
        if ab: cvc_bits.append(f"PR minimum: {ab}")
        lines.append("CvC: " + " | ".join(cvc_bits))
    if len(lines) == 1:
        lines.append("—")

    e = discord.Embed(title=title, description="\n".join(lines))

    thumb = padded_emoji_url(guild, c)
    if thumb:
        e.set_thumbnail(url=thumb)
    elif not STRICT_EMOJI_PROXY:
        em = emoji_for_tag(guild, c)
        if em:
            e.set_thumbnail(url=str(em.url))

    if filters_text:
        e.set_footer(text=f"Filters used: {filters_text}")
    return e
```

- Clan lookup resolves the `<tag>` (or name) through `find_clan_row`, which uppercases the trimmed query, iterates cached sheet rows from `get_rows(False)`, and returns the first exact-tag, exact-name, or partial match; the sheet cache lazily refreshes via `get_rows`.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1851-L1873】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L136-L143】

`bot_clanmatch_prefix.py:L1851-L1873`
```python
def find_clan_row(query: str):
    if not query:
        return None
    q = query.strip().upper()
    rows = get_rows(False)
    exact_tag = None
    exact_name = None
    partials = []
    for row in rows[1:]:
        if is_header_row(row):
            continue
        name = (row[COL_B_CLAN] or "").strip()
        tag  = (row[COL_C_TAG]  or "").strip()
        if not name and not tag:
            continue
        nU, tU = (name.upper(), tag.upper())
        if q == tU:
            exact_tag = row; break
        if q == nU and exact_name is None:
            exact_name = row
        if q in tU or q in nU:
            partials.append(row)
    return exact_tag or exact_name or (partials[0] if partials else None)
```

`bot_clanmatch_prefix.py:L136-L143`
```python
def get_rows(force: bool = False):
    """Return all rows with simple 60s cache."""
    global _cache_rows, _cache_time
    if force or _cache_rows is None or (time.time() - _cache_time) > CACHE_TTL:
        ws = get_ws(False)
        _cache_rows = ws.get_all_values()
        _cache_time = time.time()
    return _cache_rows
```

### Emoji/Crest
- Crest handling first tries to build a padded emoji proxy URL (`padded_emoji_url`) and, if unavailable, conditionally falls back to the raw emoji unless `STRICT_EMOJI_PROXY` blocks it; both profile and entry embeds call this helper. The command also attempts to generate an attachment-based thumbnail with `build_tag_thumbnail` before sending the reply.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L170-L229】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L312-L336】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1875-L1933】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L433-L484】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1936-L1978】

`bot_clanmatch_prefix.py:L170-L229`
```python
async def build_tag_thumbnail(guild: discord.Guild | None, tag: str | None, *, size: int = 256, box: float = 0.88):
    """
    Returns (discord.File, attachment_url) or (None, None).
    Use with: embed.set_thumbnail(url=attachment_url) and send with files=[file].
    """
    if not guild or not tag:
        return None, None
    emj = get(guild.emojis, name=tag.strip())
    if not emj:
        return None, None

    raw = await emj.read()  # discord.py 2.x

    import io
    from PIL import Image
    buf = io.BytesIO(raw)
    img = Image.open(buf).convert("RGBA")

# Trim transparent borders
    alpha = img.split()[-1]
    bbox = alpha.getbbox()
    if bbox:
        img = img.crop(bbox)

# Scale into square canvas
    w, h = img.size
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    target = int(size * max(0.2, min(0.95, box)))
    scale  = target / float(max(w, h) or 1)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    img = img.resize((nw, nh), RESAMPLE_LANCZOS)
    x, y = (size - nw) // 2, (size - nh) // 2
    canvas.paste(img, (x, y), img)

    out = io.BytesIO()
    canvas.save(out, format="PNG")
    out.seek(0)

    filename = f"tag_{emj.id}.png"
    file = discord.File(fp=out, filename=filename)
    return file, f"attachment://{filename}"
```

`bot_clanmatch_prefix.py:L312-L336`
```python
# ----- padded emoji URL helper (proxy only) -----
def padded_emoji_url(guild: discord.Guild | None, tag: str | None, size: int | None = None, box: float | None = None) -> str | None:
    """
    Build a URL to our /emoji-pad proxy that fetches the discord emoji, trims transparent
    borders, pads into a square with consistent margins, and returns a PNG.
    """
    if not guild or not tag:
        return None
    emj = emoji_for_tag(guild, tag)
    if not emj:
        return None
    src  = str(emj.url)
    base = BASE_URL
    if not base:
        return None
    size = size or EMOJI_PAD_SIZE
    box  = box  or EMOJI_PAD_BOX
    q = urllib.parse.urlencode({"u": src, "s": str(size), "box": str(box), "v": str(emj.id)})
    return f"{base.rstrip('/')}/emoji-pad?{q}"
```

### Validation & Errors
- Input normalization uppercases a trimmed query (`q = query.strip().upper()`), accepts matches on tag or clan name (exact or substring), and otherwise returns `None`, causing the command to send “Couldn’t find a clan matching …” publicly. Any exception bubbles to the outer `except`, which replies with `❌ Error: <type>: <message>`; missing parameters yield `Usage: !clan <tag or name>`. Unknown prefix commands elsewhere fall through the shared `on_command_error`, which silently ignores `CommandNotFound` but reports other errors.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1851-L1873】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1936-L1978】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1980-L1999】

### Toggles & Help
- Feature flags affecting crest generation live in the environment block (`TAG_BADGE_PX`, `TAG_BADGE_BOX`, `EMOJI_PAD_SIZE`, `EMOJI_PAD_BOX`, `STRICT_EMOJI_PROXY`), but no flag gates the `!clan` command itself. Boot-time logs only note missing sheet/env settings. The custom help command documents `!clan` as public-facing and highlights the 💡 reaction flip.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L80-L112】【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L1566-L1589】

`bot_clanmatch_prefix.py:L80-L112`
```python
# Max bytes we'll download for an emoji file (2 MB default) Padded-emoji tunables
EMOJI_MAX_BYTES = int(os.environ.get("EMOJI_MAX_BYTES", "2000000"))
TAG_BADGE_PX  = int(os.environ.get("TAG_BADGE_PX", "128"))   # 96–128 feels good
TAG_BADGE_BOX = float(os.environ.get("TAG_BADGE_BOX", "0.90"))
EMOJI_PAD_SIZE = int(os.environ.get("EMOJI_PAD_SIZE", "256"))   # canvas px
EMOJI_PAD_BOX  = float(os.environ.get("EMOJI_PAD_BOX", "0.85")) # glyph fill (0..1)
STRICT_EMOJI_PROXY = os.environ.get("STRICT_EMOJI_PROXY", "1") == "1"  # if True: no raw fallback

# Results per page for multi-card output
PAGE_SIZE = 10

if not CREDS_JSON:
    print("[boot] GSPREAD_CREDENTIALS missing", flush=True)
if not SHEET_ID:
    print("[boot] GOOGLE_SHEET_ID missing", flush=True)
print(f"[boot] WORKSHEET_NAME={WORKSHEET_NAME}", flush=True)
print(f"[boot] BASE_URL={BASE_URL}", flush=True)
```

`bot_clanmatch_prefix.py:L1566-L1589`
```python
@bot.command(name="help")
async def help_cmd(ctx: commands.Context, *, topic: str = None):
    topic = (topic or "").strip().lower()

    pages = {
        "clanmatch": (
            "`!clanmatch`\n"
            "Opens the recruiter panel for placing new players.\n"
            "Pick filters (CB, Hydra, Chimera, CvC Yes/No, Siege Yes/No, Playstyle, Roster).\n"
            "⚠️ Only the person who opens a panel can use it."
        ),
        "clansearch": (
            "`!clansearch`\n"
            "Opens the member panel for browsing open clans.\n"
            "Pick filters and click **Search Clans**.\n"
            "Each result shows a slim card. use the buttons to flip views."
        ),
        "clan": (
            "`!clan <tag or name>`\n"
            "Show a full clan profile (level, rank, leadership, CB/Hydra/Chimera ranges, "
            "CvC & Siege stats, progression, playstyle).\n"
            "💡 React with the bulb to flip to entry criteria."
        ),
        "welcome": (
```

### Divergences from Prod (observed)
- Entry criteria responses reuse the embed builder that applies crest thumbnails (`set_thumbnail` via `padded_emoji_url`), so the entry view is not text-only; prod screenshots expect a text-only entry pane.【F:AUDIT/20251010_src/MM/bot_clanmatch_prefix.py†L433-L484】
