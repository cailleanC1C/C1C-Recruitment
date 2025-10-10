# APISURF

## Discord usage (heuristics)
work/Matchmaker/REVIEW/THREATS.md:11:2. **Permission abuse** — Prefix commands rely on role ID gates; missing checks for future override/move flows could let members escalate. Monitor when adding those commands.
work/Matchmaker/REVIEW/THREATS.md:18:- Expand permission decorators once override/move commands are added (e.g., `@commands.has_any_role(*ADMIN_ROLE_IDS)`).
work/Matchmaker/requirements.txt:1:discord.py>=2.3,<3
work/Matchmaker/README.md:166:1. **Python** 3.10+ recommended (discord.py 2.x).
work/Matchmaker/README.md:171:   pip install discord.py gspread google-auth aiohttp pillow
work/Matchmaker/welcome.py:3:# Drop-in Cog. No external deps beyond discord.py.
work/Matchmaker/welcome.py:11:from discord.ext import commands
work/Matchmaker/welcome.py:17:async def log_to_channel(bot: commands.Bot, log_channel_id: int, level: str, msg: str, **kv):
work/Matchmaker/welcome.py:37:def _resolve_emoji(guild: discord.Guild, token: str) -> str:
work/Matchmaker/welcome.py:52:def _replace_emoji_tokens(text: str, guild: discord.Guild) -> str:
work/Matchmaker/welcome.py:55:def _emoji_cdn_url_from_id(guild: discord.Guild, emoji_id: int) -> Optional[str]:
work/Matchmaker/welcome.py:79:    guild: discord.Guild,
work/Matchmaker/welcome.py:82:    inviter: Optional[discord.Member],
work/Matchmaker/welcome.py:83:    target: Optional[discord.Member],
work/Matchmaker/welcome.py:180:class Welcome(commands.Cog):
work/Matchmaker/welcome.py:185:        bot: commands.Bot,
work/Matchmaker/welcome.py:212:    async def reload_templates(self, _ctx_user: Optional[discord.Member] = None):
work/Matchmaker/welcome.py:261:        guild: discord.Guild,
work/Matchmaker/welcome.py:275:    def _has_permission(self, member: discord.Member) -> bool:
work/Matchmaker/welcome.py:282:    async def _send_general_notice(self, guild: discord.Guild, text: str,
work/Matchmaker/welcome.py:283:                                   mention_target: Optional[discord.Member], tag: str, clan_name: str):
work/Matchmaker/welcome.py:303:    @commands.command(name="welcome")
work/Matchmaker/welcome.py:304:    @commands.cooldown(1, 10, commands.BucketType.user)
work/Matchmaker/welcome.py:305:    async def welcome(self, ctx: commands.Context, clantag: str, *args):
work/Matchmaker/welcome.py:355:        embed = discord.Embed(title=title or None, description=body, color=discord.Color.blue())
work/Matchmaker/welcome.py:407:    @commands.command(name="welcome-refresh")
work/Matchmaker/welcome.py:408:    async def welcome_refresh(self, ctx: commands.Context):
work/Matchmaker/welcome.py:419:    @commands.command(name="welcome-on")
work/Matchmaker/welcome.py:420:    async def welcome_on(self, ctx: commands.Context):
work/Matchmaker/welcome.py:428:    @commands.command(name="welcome-off")
work/Matchmaker/welcome.py:429:    async def welcome_off(self, ctx: commands.Context):
work/Matchmaker/welcome.py:437:    @commands.command(name="welcome-status")
work/Matchmaker/welcome.py:438:    async def welcome_status(self, ctx: commands.Context):
work/Matchmaker/bot_clanmatch_prefix.py:9:from discord.ext import commands
work/Matchmaker/bot_clanmatch_prefix.py:11:from discord.utils import get
work/Matchmaker/bot_clanmatch_prefix.py:25:from discord.ext import tasks
work/Matchmaker/bot_clanmatch_prefix.py:170:async def build_tag_thumbnail(guild: discord.Guild | None, tag: str | None, *, size: int = 256, box: float = 0.88):
work/Matchmaker/bot_clanmatch_prefix.py:172:    Returns (discord.File, attachment_url) or (None, None).
work/Matchmaker/bot_clanmatch_prefix.py:181:    raw = await emj.read()  # discord.py 2.x
work/Matchmaker/bot_clanmatch_prefix.py:209:    file = discord.File(fp=out, filename=filename)
work/Matchmaker/bot_clanmatch_prefix.py:312:def emoji_for_tag(guild: discord.Guild | None, tag: str | None):
work/Matchmaker/bot_clanmatch_prefix.py:319:def padded_emoji_url(guild: discord.Guild | None, tag: str | None, size: int | None = None, box: float | None = None) -> str | None:
work/Matchmaker/bot_clanmatch_prefix.py:397:def make_embed_for_row_classic(row, filters_text: str, guild: discord.Guild | None = None) -> discord.Embed:
work/Matchmaker/bot_clanmatch_prefix.py:418:    e = discord.Embed(title=title, description="\n\n".join(sections))
work/Matchmaker/bot_clanmatch_prefix.py:433:def make_embed_for_row_search(row, filters_text: str, guild: discord.Guild | None = None) -> discord.Embed:
work/Matchmaker/bot_clanmatch_prefix.py:472:    e = discord.Embed(title=title, description="\n".join(lines))
work/Matchmaker/bot_clanmatch_prefix.py:488:def make_embed_for_row_lite(row, _filters_text: str, guild: discord.Guild | None = None) -> discord.Embed:
work/Matchmaker/bot_clanmatch_prefix.py:501:    e = discord.Embed(title=title, description=tail)
work/Matchmaker/bot_clanmatch_prefix.py:513:def make_embed_for_profile_member(row, filters_text: str, guild: discord.Guild | None = None) -> discord.Embed:
work/Matchmaker/bot_clanmatch_prefix.py:662:def build_recruiters_summary_embed(guild: discord.Guild | None = None) -> discord.Embed:
work/Matchmaker/bot_clanmatch_prefix.py:688:    e = discord.Embed(title="## Summary open spots", description="\n".join(lines))
work/Matchmaker/bot_clanmatch_prefix.py:760:class PagedResultsView(discord.ui.View):
work/Matchmaker/bot_clanmatch_prefix.py:762:    def __init__(self, *, author_id: int, rows, builder, filters_text: str, guild: discord.Guild | None, timeout: float = 300):
work/Matchmaker/bot_clanmatch_prefix.py:770:        self.message: discord.Message | None = None
work/Matchmaker/bot_clanmatch_prefix.py:771:        self.results_message: discord.Message | None = None  # last results message we posted
work/Matchmaker/bot_clanmatch_prefix.py:772:        self._active_view: discord.ui.View | None = None     # last pager view (if any) attached to results
work/Matchmaker/bot_clanmatch_prefix.py:774:    async def interaction_check(self, itx: discord.Interaction) -> bool:
work/Matchmaker/bot_clanmatch_prefix.py:787:            if isinstance(child, discord.ui.Button):
work/Matchmaker/bot_clanmatch_prefix.py:793:    async def _edit(self, itx: discord.Interaction):
work/Matchmaker/bot_clanmatch_prefix.py:801:    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary, custom_id="pm_prev")
work/Matchmaker/bot_clanmatch_prefix.py:802:    async def prev_btn(self, itx: discord.Interaction, _btn: discord.ui.Button):
work/Matchmaker/bot_clanmatch_prefix.py:807:    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.primary, custom_id="pm_next")
work/Matchmaker/bot_clanmatch_prefix.py:808:    async def next_btn(self, itx: discord.Interaction, _btn: discord.ui.Button):
work/Matchmaker/bot_clanmatch_prefix.py:814:    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="pm_close")
work/Matchmaker/bot_clanmatch_prefix.py:815:    async def close_btn(self, itx: discord.Interaction, _btn: discord.ui.Button):
work/Matchmaker/bot_clanmatch_prefix.py:854:class MemberSearchPagedView(discord.ui.View):
work/Matchmaker/bot_clanmatch_prefix.py:859:    def __init__(self, *, author_id: int, rows, filters_text: str, guild: discord.Guild | None, timeout: float = 900):
work/Matchmaker/bot_clanmatch_prefix.py:867:        self.message: discord.Message | None = None
work/Matchmaker/bot_clanmatch_prefix.py:870:    async def interaction_check(self, itx: discord.Interaction) -> bool:
work/Matchmaker/bot_clanmatch_prefix.py:882:            if isinstance(child, discord.ui.Button):
work/Matchmaker/bot_clanmatch_prefix.py:884:                    child.style = discord.ButtonStyle.primary if self.mode == "lite" else discord.ButtonStyle.secondary
work/Matchmaker/bot_clanmatch_prefix.py:886:                    child.style = discord.ButtonStyle.primary if self.mode == "entry" else discord.ButtonStyle.secondary
work/Matchmaker/bot_clanmatch_prefix.py:888:                    child.style = discord.ButtonStyle.primary if self.mode == "profile" else discord.ButtonStyle.secondary
work/Matchmaker/bot_clanmatch_prefix.py:925:    async def _edit(self, itx: discord.Interaction):
work/Matchmaker/bot_clanmatch_prefix.py:947:    @discord.ui.button(emoji="📇", label="Short view", style=discord.ButtonStyle.primary, row=0, custom_id="ms_lite")
work/Matchmaker/bot_clanmatch_prefix.py:948:    async def ms_lite(self, itx: discord.Interaction, _btn: discord.ui.Button):
work/Matchmaker/bot_clanmatch_prefix.py:952:    @discord.ui.button(emoji="📑", label="Entry Criteria", style=discord.ButtonStyle.secondary, row=0, custom_id="ms_entry")
work/Matchmaker/bot_clanmatch_prefix.py:953:    async def ms_entry(self, itx: discord.Interaction, _btn: discord.ui.Button):
work/Matchmaker/bot_clanmatch_prefix.py:957:    @discord.ui.button(emoji="🪪", label="Clan Profile", style=discord.ButtonStyle.secondary, row=0, custom_id="ms_profile")
work/Matchmaker/bot_clanmatch_prefix.py:958:    async def ms_profile(self, itx: discord.Interaction, _btn: discord.ui.Button):
work/Matchmaker/bot_clanmatch_prefix.py:963:    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary, row=1, custom_id="ms_prev")
work/Matchmaker/bot_clanmatch_prefix.py:964:    async def prev(self, itx: discord.Interaction, _btn: discord.ui.Button):
work/Matchmaker/bot_clanmatch_prefix.py:969:    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.primary, row=1, custom_id="ms_next")
work/Matchmaker/bot_clanmatch_prefix.py:970:    async def next(self, itx: discord.Interaction, _btn: discord.ui.Button):
work/Matchmaker/bot_clanmatch_prefix.py:976:    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, row=1, custom_id="ms_close")
work/Matchmaker/bot_clanmatch_prefix.py:977:    async def close(self, itx: discord.Interaction, _btn: discord.ui.Button):
work/Matchmaker/bot_clanmatch_prefix.py:1005:class SearchResultFlipView(discord.ui.View):
work/Matchmaker/bot_clanmatch_prefix.py:1013:    def __init__(self, *, author_id: int, row, filters_text: str, guild: discord.Guild | None, timeout: float = 900):
work/Matchmaker/bot_clanmatch_prefix.py:1020:        self.message: discord.Message | None = None
work/Matchmaker/bot_clanmatch_prefix.py:1023:    async def interaction_check(self, itx: discord.Interaction) -> bool:
work/Matchmaker/bot_clanmatch_prefix.py:1033:    def _build_embed(self) -> discord.Embed:
work/Matchmaker/bot_clanmatch_prefix.py:1043:            if isinstance(child, discord.ui.Button):
work/Matchmaker/bot_clanmatch_prefix.py:1045:                    child.style = discord.ButtonStyle.primary if self.mode == "profile" else discord.ButtonStyle.secondary
work/Matchmaker/bot_clanmatch_prefix.py:1047:                    child.style = discord.ButtonStyle.primary if self.mode == "entry" else discord.ButtonStyle.secondary
work/Matchmaker/bot_clanmatch_prefix.py:1049:    async def _edit(self, itx: discord.Interaction):
work/Matchmaker/bot_clanmatch_prefix.py:1053:        except discord.InteractionResponded:
work/Matchmaker/bot_clanmatch_prefix.py:1066:    @discord.ui.button(emoji="👤", label="See clan profile", style=discord.ButtonStyle.secondary, custom_id="sr_profile")
work/Matchmaker/bot_clanmatch_prefix.py:1067:    async def profile_btn(self, itx: discord.Interaction, _btn: discord.ui.Button):
work/Matchmaker/bot_clanmatch_prefix.py:1071:    @discord.ui.button(emoji="✅", label="See entry criteria", style=discord.ButtonStyle.secondary, custom_id="sr_entry")
work/Matchmaker/bot_clanmatch_prefix.py:1072:    async def entry_btn(self, itx: discord.Interaction, _btn: discord.ui.Button):
work/Matchmaker/bot_clanmatch_prefix.py:1090:intents = discord.Intents.default()
work/Matchmaker/bot_clanmatch_prefix.py:1092:bot = commands.Bot(command_prefix="!", intents=intents)
work/Matchmaker/bot_clanmatch_prefix.py:1126:def _has_role_id(member: discord.Member, ids: set[int]) -> bool:
work/Matchmaker/bot_clanmatch_prefix.py:1127:    if not ids or not isinstance(member, discord.Member):
work/Matchmaker/bot_clanmatch_prefix.py:1131:def _is_admin_perm(member: discord.Member) -> bool:
work/Matchmaker/bot_clanmatch_prefix.py:1134:def _allowed_recruiter(member: discord.Member) -> bool:
work/Matchmaker/bot_clanmatch_prefix.py:1142:def _allowed_admin_or_lead(member: discord.Member) -> bool:
work/Matchmaker/bot_clanmatch_prefix.py:1161:class ClanMatchView(discord.ui.View):
work/Matchmaker/bot_clanmatch_prefix.py:1173:        self.message: discord.Message | None = None  # set after sending
work/Matchmaker/bot_clanmatch_prefix.py:1174:        self.results_message: discord.Message | None = None  # last results message we posted
work/Matchmaker/bot_clanmatch_prefix.py:1175:        self._active_view: discord.ui.View | None = None     # pager attached to that message
work/Matchmaker/bot_clanmatch_prefix.py:1184:                expired = discord.Embed(
work/Matchmaker/bot_clanmatch_prefix.py:1194:            if isinstance(child, discord.ui.Select):
work/Matchmaker/bot_clanmatch_prefix.py:1203:            elif isinstance(child, discord.ui.Button):
work/Matchmaker/bot_clanmatch_prefix.py:1206:                    child.style = discord.ButtonStyle.success if self.cvc == "1" else (
work/Matchmaker/bot_clanmatch_prefix.py:1207:                        discord.ButtonStyle.danger if self.cvc == "0" else discord.ButtonStyle.secondary
work/Matchmaker/bot_clanmatch_prefix.py:1211:                    child.style = discord.ButtonStyle.success if self.siege == "1" else (
work/Matchmaker/bot_clanmatch_prefix.py:1212:                        discord.ButtonStyle.danger if self.siege == "0" else discord.ButtonStyle.secondary
work/Matchmaker/bot_clanmatch_prefix.py:1217:                        child.style = discord.ButtonStyle.success
work/Matchmaker/bot_clanmatch_prefix.py:1220:                        child.style = discord.ButtonStyle.danger
work/Matchmaker/bot_clanmatch_prefix.py:1223:                        child.style = discord.ButtonStyle.primary
work/Matchmaker/bot_clanmatch_prefix.py:1226:                        child.style = discord.ButtonStyle.secondary
work/Matchmaker/bot_clanmatch_prefix.py:1228:    async def _maybe_refresh(self, itx: discord.Interaction):
work/Matchmaker/bot_clanmatch_prefix.py:1309:    async def interaction_check(self, itx: discord.Interaction) -> bool:
work/Matchmaker/bot_clanmatch_prefix.py:1322:    @discord.ui.select(placeholder="CB Difficulty (optional)", min_values=0, max_values=1, row=0,
work/Matchmaker/bot_clanmatch_prefix.py:1323:                       options=[discord.SelectOption(label=o, value=o) for o in CB_CHOICES])
work/Matchmaker/bot_clanmatch_prefix.py:1324:    async def cb_select(self, itx: discord.Interaction, select: discord.ui.Select):
work/Matchmaker/bot_clanmatch_prefix.py:1332:    @discord.ui.select(placeholder="Hydra Difficulty (optional)", min_values=0, max_values=1, row=1,
work/Matchmaker/bot_clanmatch_prefix.py:1333:                       options=[discord.SelectOption(label=o, value=o) for o in HYDRA_CHOICES])
work/Matchmaker/bot_clanmatch_prefix.py:1334:    async def hydra_select(self, itx: discord.Interaction, select: discord.ui.Select):
work/Matchmaker/bot_clanmatch_prefix.py:1342:    @discord.ui.select(placeholder="Chimera Difficulty (optional)", min_values=0, max_values=1, row=2,
work/Matchmaker/bot_clanmatch_prefix.py:1343:                       options=[discord.SelectOption(label=o, value=o) for o in CHIMERA_CHOICES])
work/Matchmaker/bot_clanmatch_prefix.py:1344:    async def chimera_select(self, itx: discord.Interaction, select: discord.ui.Select):
work/Matchmaker/bot_clanmatch_prefix.py:1352:    @discord.ui.select(placeholder="Playstyle (optional)", min_values=0, max_values=1, row=3,
work/Matchmaker/bot_clanmatch_prefix.py:1353:                       options=[discord.SelectOption(label=o, value=o) for o in PLAYSTYLE_CHOICES])
work/Matchmaker/bot_clanmatch_prefix.py:1354:    async def playstyle_select(self, itx: discord.Interaction, select: discord.ui.Select):
work/Matchmaker/bot_clanmatch_prefix.py:1369:    @discord.ui.button(label="CvC: —", style=discord.ButtonStyle.secondary, row=4)
work/Matchmaker/bot_clanmatch_prefix.py:1370:    async def toggle_cvc(self, itx: discord.Interaction, button: discord.ui.Button):
work/Matchmaker/bot_clanmatch_prefix.py:1377:    @discord.ui.button(label="Siege: —", style=discord.ButtonStyle.secondary, row=4)
work/Matchmaker/bot_clanmatch_prefix.py:1378:    async def toggle_siege(self, itx: discord.Interaction, button: discord.ui.Button):
work/Matchmaker/bot_clanmatch_prefix.py:1385:    @discord.ui.button(label="Open Spots Only", style=discord.ButtonStyle.success, row=4, custom_id="roster_btn")
work/Matchmaker/bot_clanmatch_prefix.py:1386:    async def toggle_roster(self, itx: discord.Interaction, button: discord.ui.Button):
work/Matchmaker/bot_clanmatch_prefix.py:1403:    @discord.ui.button(label="Reset", style=discord.ButtonStyle.secondary, row=4)
work/Matchmaker/bot_clanmatch_prefix.py:1404:    async def reset_filters(self, itx: discord.Interaction, _btn: discord.ui.Button):
work/Matchmaker/bot_clanmatch_prefix.py:1415:    @discord.ui.button(label="Search Clans", style=discord.ButtonStyle.primary, row=4, custom_id="cm_search")
work/Matchmaker/bot_clanmatch_prefix.py:1416:    async def search(self, itx: discord.Interaction, _btn: discord.ui.Button):
work/Matchmaker/bot_clanmatch_prefix.py:1567:async def help_cmd(ctx: commands.Context, *, topic: str = None):
work/Matchmaker/bot_clanmatch_prefix.py:1626:        e = discord.Embed(
work/Matchmaker/bot_clanmatch_prefix.py:1633:            color=discord.Color.blurple()
work/Matchmaker/bot_clanmatch_prefix.py:1668:    e = discord.Embed(title=f"!help {topic}", description=txt, color=discord.Color.blurple())
work/Matchmaker/bot_clanmatch_prefix.py:1672:async def _safe_delete(message: discord.Message):
work/Matchmaker/bot_clanmatch_prefix.py:1678:async def _resolve_recruiter_panel_channel(ctx: commands.Context) -> discord.abc.Messageable | None:
work/Matchmaker/bot_clanmatch_prefix.py:1691:        if isinstance(dest, discord.Thread):
work/Matchmaker/bot_clanmatch_prefix.py:1708:@commands.cooldown(1, 2, commands.BucketType.user)
work/Matchmaker/bot_clanmatch_prefix.py:1710:async def clanmatch_cmd(ctx: commands.Context, *, extra: str | None = None):
work/Matchmaker/bot_clanmatch_prefix.py:1721:    if not isinstance(ctx.author, discord.Member) or not _allowed_recruiter(ctx.author):
work/Matchmaker/bot_clanmatch_prefix.py:1731:    embed = discord.Embed(
work/Matchmaker/bot_clanmatch_prefix.py:1752:    allowed = discord.AllowedMentions(users=[ctx.author])
work/Matchmaker/bot_clanmatch_prefix.py:1806:@commands.cooldown(1, 2, commands.BucketType.user)
work/Matchmaker/bot_clanmatch_prefix.py:1808:async def clansearch_cmd(ctx: commands.Context, *, extra: str | None = None):
work/Matchmaker/bot_clanmatch_prefix.py:1824:    embed = discord.Embed(
work/Matchmaker/bot_clanmatch_prefix.py:1875:def make_embed_for_profile(row, guild: discord.Guild | None = None) -> discord.Embed:
work/Matchmaker/bot_clanmatch_prefix.py:1921:    e = discord.Embed(title=title, description="\n".join(lines))
work/Matchmaker/bot_clanmatch_prefix.py:1937:async def clanprofile_cmd(ctx: commands.Context, *, query: str | None = None):
work/Matchmaker/bot_clanmatch_prefix.py:1982:    if isinstance(error, commands.CommandNotFound):
work/Matchmaker/bot_clanmatch_prefix.py:1990:async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
work/Matchmaker/bot_clanmatch_prefix.py:2040:async def on_message_delete(message: discord.Message):
work/Matchmaker/bot_clanmatch_prefix.py:2046:async def ping(ctx: commands.Context):
work/Matchmaker/bot_clanmatch_prefix.py:2055:async def health_prefix(ctx: commands.Context):
work/Matchmaker/bot_clanmatch_prefix.py:2056:    if not isinstance(ctx.author, discord.Member) or not _allowed_admin_or_lead(ctx.author):
work/Matchmaker/bot_clanmatch_prefix.py:2086:    if not isinstance(ctx.author, discord.Member) or not _allowed_admin_or_lead(ctx.author):
work/Matchmaker/bot_clanmatch_prefix.py:2094:async def _purge_one_target(channel: discord.abc.Messageable, cutoff_dt: datetime) -> int:
work/Matchmaker/bot_clanmatch_prefix.py:2104:    if isinstance(channel, discord.Thread) and channel.archived:
work/Matchmaker/bot_clanmatch_prefix.py:2110:    def _check(m: discord.Message) -> bool:
work/Matchmaker/bot_clanmatch_prefix.py:2220:# --- Welcome module wiring (discord.py v2: add_cog is async) ---
work/WelcomeCrew/REVIEW/REVIEW.md:27:  -from discord.ext import commands
work/WelcomeCrew/REVIEW/REVIEW.md:28:  +from discord.ext import commands
work/WelcomeCrew/REVIEW/REVIEW.md:33:  -        async def wrapper(ctx: commands.Context, *a, **k):
work/WelcomeCrew/REVIEW/REVIEW.md:39:  +ADMIN_PERMS = commands.has_guild_permissions(manage_guild=True)
work/WelcomeCrew/REVIEW/REVIEW.md:44:  +        async def wrapper(ctx: commands.Context, *a, **k):
work/WelcomeCrew/REVIEW/REVIEW.md:133:  async def infer_clantag_from_thread(thread: discord.Thread) -> Optional[str]:
work/WelcomeCrew/REVIEW/REVIEW.md:139:  async def scan_welcome_channel(channel: discord.TextChannel, progress_cb=None):
work/WelcomeCrew/REVIEW/REVIEW.md:146:  async def scan_promo_channel(channel: discord.TextChannel, progress_cb=None):
work/WelcomeCrew/REVIEW/REVIEW.md:149:  async def on_message(message: discord.Message):
work/WelcomeCrew/REVIEW/REVIEW.md:150:       if isinstance(message.channel, discord.Thread):
work/WelcomeCrew/REVIEW/REVIEW.md:155:  - Simulate Sheets outage (invalid credentials) and ensure `on_message` continues to process commands.
work/WelcomeCrew/REVIEW/THREATS.md:16:- Add `Manage Server` (or recruiter role) checks before executing maintenance commands.
work/WelcomeCrew/requirements.txt:1:discord.py>=2.4
work/WelcomeCrew/.github/issue-batches/issues.json:6:    "body": "Close privilege escalation for destructive/maintenance prefix commands.\n\n**Why**: Non-admins can trigger ops commands.\n\n**Acceptance Criteria**\n- Destructive/maintenance prefix commands (`!reboot`, `!backfill_tickets`, `!dedupe`, env/diag) fail for non-admins with a clear message; succeed for users with **Manage Server** or the designated admin role.\n- `/help` and command catalog accurately reflect gating.\n- Unit smoke: non-admin vs admin behavior verified.\n\n**Notes**\n- Align with Reminder Bot’s permission model.\n"
work/WelcomeCrew/README.md:25:   * `discord.py`, `gspread`, `google-auth`, `aiohttp`
work/WelcomeCrew/README.md:28:   pip install discord.py gspread google-auth aiohttp
work/WelcomeCrew/bot_welcomecrew.py:18:from discord.ext import commands
work/WelcomeCrew/bot_welcomecrew.py:28:from discord.ext import tasks
work/WelcomeCrew/bot_welcomecrew.py:90:intents = discord.Intents.default()
work/WelcomeCrew/bot_welcomecrew.py:92:bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
work/WelcomeCrew/bot_welcomecrew.py:191:def _mk_help_embed_mobile(guild: discord.Guild | None = None) -> discord.Embed:
work/WelcomeCrew/bot_welcomecrew.py:192:    e = discord.Embed(
work/WelcomeCrew/bot_welcomecrew.py:238:async def help_cmd(ctx: commands.Context, *, topic: str = None):
work/WelcomeCrew/bot_welcomecrew.py:267:    e = discord.Embed(title=f"!help {topic}", description=txt, color=EMBED_COLOR)
work/WelcomeCrew/bot_welcomecrew.py:274:async def slash_help(interaction: discord.Interaction):
work/WelcomeCrew/bot_welcomecrew.py:582:def _aggregate_msg_text(msg: discord.Message) -> str:
work/WelcomeCrew/bot_welcomecrew.py:599:async def infer_clantag_from_thread(thread: discord.Thread) -> Optional[str]:
work/WelcomeCrew/bot_welcomecrew.py:610:    except discord.Forbidden:
work/WelcomeCrew/bot_welcomecrew.py:657:async def find_close_timestamp(thread: discord.Thread) -> Optional[datetime]:
work/WelcomeCrew/bot_welcomecrew.py:665:    except discord.Forbidden: pass
work/WelcomeCrew/bot_welcomecrew.py:692:def thread_link(thread: discord.Thread) -> str:
work/WelcomeCrew/bot_welcomecrew.py:694:    return f"https://discord.com/channels/{gid}/{thread.id}"
work/WelcomeCrew/bot_welcomecrew.py:727:def _notify_prefix(guild: discord.Guild, closer: Optional[discord.User]) -> str:
work/WelcomeCrew/bot_welcomecrew.py:736:async def _notify_channel(guild: discord.Guild, content: str):
work/WelcomeCrew/bot_welcomecrew.py:740:    if not isinstance(ch, (discord.TextChannel, discord.Thread)):
work/WelcomeCrew/bot_welcomecrew.py:748:async def _try_join_private_thread(thread: discord.Thread) -> bool:
work/WelcomeCrew/bot_welcomecrew.py:764:def _who_to_ping(msg: discord.Message, thread: discord.Thread) -> Optional[discord.User]:
work/WelcomeCrew/bot_welcomecrew.py:773:async def _prompt_for_tag(thread: discord.Thread, ticket: str, username: str,
work/WelcomeCrew/bot_welcomecrew.py:774:                          msg_to_reply: Optional[discord.Message], mode: str):
work/WelcomeCrew/bot_welcomecrew.py:788:    except discord.Forbidden:
work/WelcomeCrew/bot_welcomecrew.py:807:async def _rename_welcome_thread_if_needed(thread: discord.Thread, ticket: str, username: str, clantag: str) -> bool:
work/WelcomeCrew/bot_welcomecrew.py:824:    except discord.Forbidden:
work/WelcomeCrew/bot_welcomecrew.py:830:async def _finalize_welcome(thread: discord.Thread, ticket: str, username: str, clantag: str, close_dt: Optional[datetime]):
work/WelcomeCrew/bot_welcomecrew.py:841:async def _finalize_promo(thread: discord.Thread, ticket: str, username: str, clantag: str, close_dt: Optional[datetime]):
work/WelcomeCrew/bot_welcomecrew.py:864:async def scan_welcome_channel(channel: discord.TextChannel, progress_cb=None):
work/WelcomeCrew/bot_welcomecrew.py:871:    async def handle(th: discord.Thread):
work/WelcomeCrew/bot_welcomecrew.py:885:    except discord.Forbidden:
work/WelcomeCrew/bot_welcomecrew.py:891:    except discord.Forbidden:
work/WelcomeCrew/bot_welcomecrew.py:894:async def _handle_welcome_thread(th: discord.Thread, ws, st):
work/WelcomeCrew/bot_welcomecrew.py:920:async def scan_promo_channel(channel: discord.TextChannel, progress_cb=None):
work/WelcomeCrew/bot_welcomecrew.py:927:    async def handle(th: discord.Thread):
work/WelcomeCrew/bot_welcomecrew.py:941:    except discord.Forbidden:
work/WelcomeCrew/bot_welcomecrew.py:947:    except discord.Forbidden:
work/WelcomeCrew/bot_welcomecrew.py:950:async def _handle_promo_thread(th: discord.Thread, ws, st):
work/WelcomeCrew/bot_welcomecrew.py:982:async def detect_promo_type(thread: discord.Thread) -> Optional[str]:
work/WelcomeCrew/bot_welcomecrew.py:991:    except discord.Forbidden: pass
work/WelcomeCrew/bot_welcomecrew.py:1010:        async def wrapper(ctx: commands.Context, *a, **k):
work/WelcomeCrew/bot_welcomecrew.py:1154:            if isinstance(ch, discord.TextChannel):
work/WelcomeCrew/bot_welcomecrew.py:1158:            if isinstance(ch2, discord.TextChannel):
work/WelcomeCrew/bot_welcomecrew.py:1188:        await ctx.send(file=discord.File(buf, filename=f"backfill_details_{ts}.txt"))
work/WelcomeCrew/bot_welcomecrew.py:1199:async def cmd_backfill_details(ctx: commands.Context):
work/WelcomeCrew/bot_welcomecrew.py:1203:    await ctx.reply(file=discord.File(buf, filename=f"backfill_details_{ts}.txt"), mention_author=False)
work/WelcomeCrew/bot_welcomecrew.py:1287:class TagPickerReloadView(discord.ui.View):
work/WelcomeCrew/bot_welcomecrew.py:1293:    @discord.ui.button(label="Reload picker", style=discord.ButtonStyle.primary, emoji="🔄")
work/WelcomeCrew/bot_welcomecrew.py:1294:    async def reload(self, interaction: discord.Interaction, button: discord.ui.Button):
work/WelcomeCrew/bot_welcomecrew.py:1313:class TagPickerView(discord.ui.View):
work/WelcomeCrew/bot_welcomecrew.py:1315:    def __init__(self, mode: str, thread: discord.Thread, ticket: str, username: str,
work/WelcomeCrew/bot_welcomecrew.py:1325:        self.message: Optional[discord.Message] = None
work/WelcomeCrew/bot_welcomecrew.py:1328:        self.select = discord.ui.Select(
work/WelcomeCrew/bot_welcomecrew.py:1331:            options=[discord.SelectOption(label=t, value=t) for t in self.pages[0]]
work/WelcomeCrew/bot_welcomecrew.py:1333:        async def _on_select(interaction: discord.Interaction):
work/WelcomeCrew/bot_welcomecrew.py:1341:            prev_btn = discord.ui.Button(label="◀ Prev", style=discord.ButtonStyle.secondary)
work/WelcomeCrew/bot_welcomecrew.py:1342:            next_btn = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary)
work/WelcomeCrew/bot_welcomecrew.py:1344:            async def _prev_cb(interaction: discord.Interaction):
work/WelcomeCrew/bot_welcomecrew.py:1349:            async def _next_cb(interaction: discord.Interaction):
work/WelcomeCrew/bot_welcomecrew.py:1359:        self.select.options = [discord.SelectOption(label=t, value=t) for t in self.pages[self.page]]
work/WelcomeCrew/bot_welcomecrew.py:1362:    async def _handle_pick(self, interaction: discord.Interaction, tag: str):
work/WelcomeCrew/bot_welcomecrew.py:1606:                if isinstance(ch, (discord.TextChannel, discord.Thread)):
work/WelcomeCrew/bot_welcomecrew.py:1620:def _is_thread_in_parent(thread: discord.Thread, parent_id: int) -> bool:
work/WelcomeCrew/bot_welcomecrew.py:1627:async def on_thread_create(thread: discord.Thread):
work/WelcomeCrew/bot_welcomecrew.py:1637:    if isinstance(error, commands.CommandNotFound):
work/WelcomeCrew/bot_welcomecrew.py:1645:async def on_message(message: discord.Message):
work/WelcomeCrew/bot_welcomecrew.py:1647:    if isinstance(message.channel, discord.Thread):
work/WelcomeCrew/bot_welcomecrew.py:1727:async def on_thread_update(before: discord.Thread, after: discord.Thread):

## Google Sheets / HTTP
work/Matchmaker/REVIEW/ARCH_MAP.md:5:2. **Data access** — `get_rows()` lazily connects to the `bot_info` worksheet via gspread and caches the full table in memory. All matching, summaries, and profiles reuse this cache.
work/Matchmaker/REVIEW/ARCH_MAP.md:14:- **Sheets adapter** — Introduce an async wrapper service that owns the gspread client, enforces schema, and exposes typed accessors (brackets, open spots, recruiters summary).
work/Matchmaker/REVIEW/REVIEW.md:15:**Issue.** `get_rows()` and helpers call gspread’s `worksheet.get_all_values()`, which uses synchronous `requests`. The calls happen directly inside interaction handlers (`ClanMatchView.search` / `_maybe_refresh`), the daily poster, and the `!clan` command. When Sheets is slow (common at peak), the entire Discord event loop blocks for several seconds, delaying heartbeats and triggering disconnects/zombie watchdog exits. This violates the async hygiene goal in the brief.
work/Matchmaker/requirements.txt:2:gspread>=6
work/Matchmaker/.github/issue-batches/issues.json:10:      "body": "Synchronous gspread calls in interaction handlers, daily poster, and !clan freeze the event loop and risk disconnects. See REVIEW.md (F-01) and FINDINGS.md. Move all Sheets work off the loop, track call sites, and add a latency regression test.",
work/Matchmaker/README.md:171:   pip install discord.py gspread google-auth aiohttp pillow
work/Matchmaker/bot_clanmatch_prefix.py:13:import gspread
work/Matchmaker/bot_clanmatch_prefix.py:131:    _gc = gspread.authorize(creds)
work/Matchmaker/bot_clanmatch_prefix.py:2510:    gc = gspread.authorize(creds)
work/WelcomeCrew/REVIEW/ARCH_MAP.md:6:3. **Sheets access** — Helpers such as `get_ws`, `upsert_welcome`, and `_load_clan_tags` use gspread synchronously and are offloaded via `_run_blocking` in some call sites.
work/WelcomeCrew/REVIEW/ARCH_MAP.md:12:- **Sheets Adapter Layer** — gspread client factory, worksheet cache, and upsert/dedupe helpers (candidate for extraction into `welcomecrew/sheets.py`).
work/WelcomeCrew/requirements.txt:2:gspread>=6.0
work/WelcomeCrew/README.md:25:   * `discord.py`, `gspread`, `google-auth`, `aiohttp`
work/WelcomeCrew/README.md:28:   pip install discord.py gspread google-auth aiohttp
work/WelcomeCrew/bot_welcomecrew.py:19:import gspread
work/WelcomeCrew/bot_welcomecrew.py:20:from gspread.exceptions import APIError
work/WelcomeCrew/bot_welcomecrew.py:136:        _gs_client = gspread.service_account_from_dict(json.loads(raw))
work/WelcomeCrew/bot_welcomecrew.py:145:    except gspread.WorksheetNotFound:
