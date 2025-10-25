# Phase 5 Feature Audit — Recruitment Emoji & Asset Handling

1) **Sources of emojis/icons**
- Legacy prefix bot loads emoji proxy toggles, thumbnail sizing, and sheet/cache controls from environment variables before any embed assembly:

```python
C1C_FOOTER_EMOJI_ID = int(os.getenv("C1C_FOOTER_EMOJI_ID", "0")) or None
CREDS_JSON = os.environ.get("GSPREAD_CREDENTIALS")
SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")
BASE_URL = os.environ.get("PUBLIC_BASE_URL") or os.environ.get("RENDER_EXTERNAL_URL")
ALLOWED_EMOJI_HOSTS = {
    "cdn.discordapp.com",
    "media.discordapp.net",
}
EMOJI_MAX_BYTES = int(os.environ.get("EMOJI_MAX_BYTES", "2000000"))
TAG_BADGE_PX  = int(os.environ.get("TAG_BADGE_PX", "128"))
TAG_BADGE_BOX = float(os.environ.get("TAG_BADGE_BOX", "0.90"))
EMOJI_PAD_SIZE = int(os.environ.get("EMOJI_PAD_SIZE", "256"))
EMOJI_PAD_BOX  = float(os.environ.get("EMOJI_PAD_BOX", "0.85"))
STRICT_EMOJI_PROXY = os.environ.get("STRICT_EMOJI_PROXY", "1") == "1"
CACHE_TTL = int(os.environ.get("SHEETS_CACHE_TTL_SEC", "28800"))
```

- Sheets helpers keep worksheet handles and row data cached until TTL expiry, giving emoji/tag lookups a refresh path via `clear_cache()`:

```python
_gc = None
_ws = None
_cache_rows = None
_cache_time = 0.0
CACHE_TTL = int(os.environ.get("SHEETS_CACHE_TTL_SEC", "28800"))

def get_rows(force: bool = False):
    global _cache_rows, _cache_time
    if force or _cache_rows is None or (time.time() - _cache_time) > CACHE_TTL:
        ws = get_ws(False)
        _cache_rows = ws.get_all_values()
        _cache_time = time.time()
    return _cache_rows

def clear_cache():
    global _cache_rows, _cache_time, _ws
    _cache_rows = None
    _cache_time = 0.0
    _ws = None
```

- Guild emoji assets drive thumbnails through lightweight helpers that locate Discord emoji objects, construct proxy URLs, or generate Pillow attachments:

```python
def emoji_for_tag(guild: discord.Guild | None, tag: str | None):
    if not guild or not tag:
        return None
    return get(guild.emojis, name=tag.strip())

def padded_emoji_url(guild: discord.Guild | None, tag: str | None, size: int | None = None, box: float | None = None) -> str | None:
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

async def build_tag_thumbnail(guild: discord.Guild | None, tag: str | None, *, size: int = 256, box: float = 0.88):
    if not guild or not tag:
        return None, None
    emj = get(guild.emojis, name=tag.strip())
    if not emj:
        return None, None
    raw = await emj.read()
    buf = io.BytesIO(raw)
    img = Image.open(buf).convert("RGBA")
    alpha = img.split()[-1]
    bbox = alpha.getbbox()
    if bbox:
        img = img.crop(bbox)
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

- `/emoji-pad` web handler sanitises Discord CDN URLs, enforces byte caps, trims transparent borders, and serves cached PNGs used by embed thumbnails:

```python
async def emoji_pad_handler(request: web.Request):
    src = request.query.get("u")
    s_raw = request.query.get("s")
    size = int(s_raw) if s_raw is not None else EMOJI_PAD_SIZE
    size = max(64, min(512, size))
    b_raw = request.query.get("box")
    box = float(b_raw) if b_raw is not None else EMOJI_PAD_BOX
    box = max(0.2, min(0.95, box))
    if not src:
        return web.Response(status=400, text="missing u")
    parsed = urlparse(src)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or host not in ALLOWED_EMOJI_HOSTS:
        return web.Response(status=400, text="invalid source host")
    async with request.app["session"].get(
        src,
        timeout=ClientTimeout(total=8),
        allow_redirects=False,
        headers={"User-Agent": "c1c-matchmaker/emoji-pad"}
    ) as resp:
        if resp.status != 200:
            return web.Response(status=resp.status, text=f"fetch failed: {resp.status}")
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if not ctype.startswith("image/"):
            return web.Response(status=415, text="unsupported media type")
        if resp.content_length is not None and resp.content_length > EMOJI_MAX_BYTES:
            return web.Response(status=413, text="image too large")
        buf = bytearray()
        async for chunk in resp.content.iter_chunked(65536):
            buf.extend(chunk)
            if len(buf) > EMOJI_MAX_BYTES:
                return web.Response(status=413, text="image too large")
        raw = bytes(buf)
    img = Image.open(io.BytesIO(raw))
    img = img.convert("RGBA")
    alpha = img.split()[-1]
    bbox = alpha.getbbox()
    if bbox:
        img = img.crop(bbox)
    w, h = img.size
    max_side = max(w, h) or 1
    target   = max(1, int(size * box))
    scale    = target / float(max_side)
    new_w    = max(1, int(w * scale))
    new_h    = max(1, int(h * scale))
    img = img.resize((new_w, new_h), RESAMPLE_LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    x = (size - new_w) // 2
    y = (size - new_h) // 2
    canvas.paste(img, (x, y), img)
    out = io.BytesIO()
    canvas.save(out, format="PNG")
    return web.Response(
        body=out.getvalue(),
        headers={"Cache-Control": "public, max-age=86400"},
        content_type="image/png",
    )
```

2) **Usage in cards/panels/buttons**
- Recruiter embeds add emoji thumbnails (when enabled) and stash filter metadata in the footer:

```python
def make_embed_for_row_classic(row, filters_text: str, guild: discord.Guild | None = None) -> discord.Embed:
    title = f"{clan} `{tag}`  — Spots: {spots}"
    e = discord.Embed(title=title, description="\n\n".join(sections))
    if SHOW_TAG_IN_CLASSIC:
        thumb = padded_emoji_url(guild, tag)
        if thumb:
            e.set_thumbnail(url=thumb)
        elif not STRICT_EMOJI_PROXY:
            em = emoji_for_tag(guild, tag)
            if em:
                e.set_thumbnail(url=str(em.url))
    e.set_footer(text=f"Filters used: {filters_text}")
    return e
```

- Member search, lite, and profile embeds all request padded emoji thumbnails and arrange entry criteria text around them:

```python
def make_embed_for_row_search(row, filters_text: str, guild: discord.Guild | None = None) -> discord.Embed:
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


def make_embed_for_row_lite(row, _filters_text: str, guild: discord.Guild | None = None) -> discord.Embed:
    e = discord.Embed(title=title, description=tail)
    thumb = padded_emoji_url(guild, tag)
    if thumb:
        e.set_thumbnail(url=thumb)
    elif not STRICT_EMOJI_PROXY:
        em = emoji_for_tag(guild, tag)
        if em:
            e.set_thumbnail(url=str(em.url))
    return e


def make_embed_for_profile(row, guild: discord.Guild | None = None) -> discord.Embed:
    e = discord.Embed(title=title, description="\n".join(lines))
    thumb = padded_emoji_url(guild, tag)
    if thumb:
        e.set_thumbnail(url=thumb)
    elif not STRICT_EMOJI_PROXY:
        em = emoji_for_tag(guild, tag)
        if em:
            e.set_thumbnail(url=str(em.url))
    e.set_footer(text="React with 💡 for Entry Criteria")
    return e
```

- Member pagination view builds embeds plus crest attachments, decorating buttons with 📇/📑/🪪 and appending pager info to the footer:

```python
class MemberSearchPagedView(discord.ui.View):
    async def _build_page(self):
        embeds, files = [], []
        for r in slice_:
            e = _build(r)
            tag = (r[COL_C_TAG] or "").strip()
            f, u = await build_tag_thumbnail(self.guild, tag, size=TAG_BADGE_PX, box=TAG_BADGE_BOX)
            if u and f:
                e.set_thumbnail(url=u)
                files.append(f)
            embeds.append(e)
        if embeds:
            total_pages = max(1, math.ceil(len(self.rows) / PAGE_SIZE))
            page_info = f"Page {self.page + 1}/{total_pages} • {len(self.rows)} total"
            last = embeds[-1]; ft = last.footer.text or ""
            last.set_footer(text=f"{ft} • {page_info}" if ft else page_info)
        return embeds, files

    @discord.ui.button(emoji="📇", label="Short view", ...)
    async def ms_lite(...): ...

    @discord.ui.button(emoji="📑", label="Entry Criteria", ...)
    async def ms_entry(...): ...

    @discord.ui.button(emoji="🪪", label="Clan Profile", ...)
    async def ms_profile(...): ...
```

- `SearchResultFlipView` swaps a single result between lite/profile/entry embeds using 👤/✅ button emojis while editing in place:

```python
class SearchResultFlipView(discord.ui.View):
    def _build_embed(self) -> discord.Embed:
        if self.mode == "profile":
            return make_embed_for_profile_member(self.row, self.filters_text, self.guild)
        if self.mode == "entry":
            return make_embed_for_row_search(self.row, self.filters_text, self.guild)
        return make_embed_for_row_lite(self.row, self.filters_text, self.guild)

    @discord.ui.button(emoji="👤", label="See clan profile", ...)
    async def profile_btn(...):
        self.mode = "profile"
        await self._edit(itx)

    @discord.ui.button(emoji="✅", label="See entry criteria", ...)
    async def entry_btn(...):
        self.mode = "entry"
        await self._edit(itx)
```

- Recruiter `ClanMatchView` precomputes the first page of member results with attachment thumbnails while fallback recruiter pages reuse classic embeds without files:

```python
if self.embed_variant == "search":
    for r in slice_:
        e = _build(r)
        tag = (r[COL_C_TAG] or "").strip()
        f, u = await build_tag_thumbnail(itx.guild, tag, size=TAG_BADGE_PX, box=TAG_BADGE_BOX)
        if u and f:
            e.set_thumbnail(url=u)
            files.append(f)
        embeds.append(e)
    total_pages = max(1, math.ceil(len(matches) / PAGE_SIZE))
    page_info = f"Page 1/{total_pages} • {len(matches)} total"
    last = embeds[-1]; ft = last.footer.text or ""
    last.set_footer(text=f"{ft} • {page_info}" if ft else page_info)
    sent = await itx.followup.send(embeds=embeds, files=files, view=view)
```

3) **Fallback behavior**
- Thumbnail helpers bail out when guild emojis are missing, letting embeds continue without attachments:

```python
if not guild or not tag:
    return None, None
emj = get(guild.emojis, name=tag.strip())
if not emj:
    return None, None
```

- Embed builders fall back to raw CDN emoji URLs only when `STRICT_EMOJI_PROXY` is disabled; otherwise thumbnails are omitted:

```python
thumb = padded_emoji_url(guild, tag)
if thumb:
    e.set_thumbnail(url=thumb)
elif not STRICT_EMOJI_PROXY:
    em = emoji_for_tag(guild, tag)
    if em:
        e.set_thumbnail(url=str(em.url))
```

- `clanprofile_cmd` sends the embed even when attachment generation fails, preserving the 💡 reaction flip:

```python
file, url = await build_tag_thumbnail(ctx.guild, tag, size=TAG_BADGE_PX, box=TAG_BADGE_BOX)
if url:
    embed.set_thumbnail(url=url)
    msg = await ctx.reply(embed=embed, files=[file], mention_author=False)
else:
    msg = await ctx.reply(embed=embed, mention_author=False)

try:
    await msg.add_reaction("💡")
except Exception:
    pass
```

- `/emoji-pad` defends against invalid hosts, oversize payloads, and network errors by returning HTTP 4xx/5xx responses instead of propagating untrusted images:

```python
if parsed.scheme not in {"http", "https"} or host not in ALLOWED_EMOJI_HOSTS:
    return web.Response(status=400, text="invalid source host")
if resp.content_length is not None and resp.content_length > EMOJI_MAX_BYTES:
    return web.Response(status=413, text="image too large")
async for chunk in resp.content.iter_chunked(65536):
    buf.extend(chunk)
    if len(buf) > EMOJI_MAX_BYTES:
        return web.Response(status=413, text="image too large")
...
except asyncio.TimeoutError:
    return web.Response(status=504, text="image fetch timeout")
except Exception as e:
    return web.Response(status=500, text=f"err {type(e).__name__}: {e}")
```

4) **Caching & refresh**
- Legacy caches store rows and worksheet handles until TTL expires, and `!reload` clears them via `clear_cache()` allowing emoji updates to flow without restarts (see snippet above).
- Runtime panel state maintains emoji-rich messages through shared registries:

```python
REACT_INDEX: dict[int, dict] = {}
...
info = REACT_INDEX.get(payload.message_id)
if info["kind"] == "entry_from_profile":
    embed = make_embed_for_row_search(...)
    await msg.edit(embed=embed)
    info["kind"] = "profile_from_search"
    REACT_INDEX[payload.message_id] = info
```

- `/emoji-pad` replies include `Cache-Control: public, max-age=86400`, enabling downstream CDN/browser caching (see handler snippet).
- Unified Sheets module registers async caches for recruitment data but has no emoji pipeline yet:

```python
_CACHE_TTL = int(os.getenv("SHEETS_CACHE_TTL_SEC", "900"))
_CLAN_ROWS: List[List[str]] | None = None
_CLAN_ROWS_TS: float = 0.0

def fetch_clans(force: bool = False) -> List[List[str]]:
    global _CLAN_ROWS, _CLAN_ROWS_TS
    now = time.time()
    if not force and _CLAN_ROWS and (now - _CLAN_ROWS_TS) < _CACHE_TTL:
        return _CLAN_ROWS
    rows = core.fetch_values(_sheet_id(), _clans_tab())
    _CLAN_ROWS = rows
    _CLAN_ROWS_TS = now
    return rows

cache.register("clans", _TTL_CLANS_SEC, _load_clans_async)
cache.register("templates", _TTL_TEMPLATES_SEC, _load_templates_async)
```

5) **Configuration surface**
- README documents the deployment knobs controlling emoji proxying, thumbnail sizing, and panel behaviour:

```markdown
* `PUBLIC_BASE_URL` or `RENDER_EXTERNAL_URL` — public base URL for the bot’s web server (for `/emoji-pad` links).
* `EMOJI_MAX_BYTES` — max downloaded image size (default 2 MB).
* `EMOJI_PAD_SIZE` — canvas size in px (default 256).
* `EMOJI_PAD_BOX` — glyph fill ratio 0.2–0.95 (default 0.85).
* `TAG_BADGE_PX` / `TAG_BADGE_BOX` — size/fill for the attachment thumbnails (default 128 / 0.90).
* `STRICT_EMOJI_PROXY` — `1` to require proxy URLs; `0` allows direct CDN thumbnails when proxy is unavailable.
* `SEARCH_RESULTS_SOFT_CAP` — max results shown per search (default 25).
* `SHOW_TAG_IN_CLASSIC` — `1` to show tag thumbnails on recruiter results (default off to save space).
```

- Unified config helpers only expose sheet/result settings today—no emoji controls yet:

```python
async def setup(bot: commands.Bot) -> None:
    # TODO(phase3): wire recruitment search commands once Sheets access lands.
    await ensure_loaded(bot)
```

6) **Command-specific call sites**
- `!clanmatch` searches load Sheets rows, filter matches, and either render recruiter embeds or spawn member pagination with crest attachments:

```python
if self.embed_variant == "search":
    view = MemberSearchPagedView(...)
    for r in slice_:
        f, u = await build_tag_thumbnail(itx.guild, tag, size=TAG_BADGE_PX, box=TAG_BADGE_BOX)
        if u and f:
            e.set_thumbnail(url=u)
            files.append(f)
    sent = await itx.followup.send(embeds=embeds, files=files, view=view)
    view.message = sent
    self.results_message = sent
    return
```

- `!clansearch` reuses `ClanMatchView` in search mode, wiring `MemberSearchPagedView` for attachment thumbnails and emoji buttons (see snippets above).
- `!clan <tag>` builds the profile embed, attempts to attach the padded crest PNG, and registers the 💡 flip metadata:

```python
embed = make_embed_for_profile(row, ctx.guild)
file, url = await build_tag_thumbnail(ctx.guild, tag, size=TAG_BADGE_PX, box=TAG_BADGE_BOX)
if url:
    embed.set_thumbnail(url=url)
    msg = await ctx.reply(embed=embed, files=[file], mention_author=False)
else:
    msg = await ctx.reply(embed=embed, mention_author=False)
REACT_INDEX[msg.id] = {
    "row": row,
    "kind": "entry_from_profile",
    "guild_id": ctx.guild.id if ctx.guild else None,
    "channel_id": msg.channel.id,
    "filters": "",
}
```

7) **Legacy vs Unified**
- Legacy Matchmaker repo contains the full emoji pipeline, embed builders, panel views, reaction flips, and proxy service showcased in the snippets above.
- Unified recruitment module currently stubs command registration with a TODO, providing no emoji handling:

```python
async def setup(bot: commands.Bot) -> None:
    # TODO(phase3): wire recruitment search commands once Sheets access lands.
    await ensure_loaded(bot)
```

- Unified Sheets backend prepares cached clan/template data but does not yet expose emoji assets or crest attachments (see caching snippet in section 4).

8) **Porting checklist (facts only)**
1. Resolve guild emojis into padded PNG thumbnails via Pillow and `/emoji-pad`, respecting host/size guards and cache headers shown above.
2. Honour `STRICT_EMOJI_PROXY`: only fall back to raw CDN emoji URLs when the flag is disabled; otherwise omit thumbnails gracefully.
3. Attach crest files for member pagination, recruiter search results, and `!clan` replies using `build_tag_thumbnail`, keeping the embed-only fallback path intact.
4. Maintain the 💡 reaction flip system (footer hints, reaction removal, and `REACT_INDEX` bookkeeping) so profile and entry views toggle without resending commands.
5. Preserve Sheets caching semantics (`CACHE_TTL`, `clear_cache()`, async cache registrations) so emoji/tag updates refresh via TTL expiry or `!reload`.
6. Reproduce panel buttons and pagers with the same emoji labels (📇/📑/🪪, 👤/✅) and footer page summaries across recruiter/member views.

Doc last updated: 2025-10-19 (v0.9.5)
