# APISURF

## Discord usage (heuristics)
work/Achievements/claims/middleware/coreops_prefix_old.py:21:from discord.ext import commands
work/Achievements/claims/middleware/coreops_prefix_old.py:64:class CoreOpsPrefixCog(commands.Cog):
work/Achievements/claims/middleware/coreops_prefix_old.py:67:    def __init__(self, bot: commands.Bot):
work/Achievements/claims/middleware/coreops_prefix_old.py:75:    @commands.command(name=OUR_PREFIX)
work/Achievements/claims/middleware/coreops_prefix_old.py:76:    async def route_to_scribe(self, ctx: commands.Context, *, rest: Optional[str] = None):
work/Achievements/claims/middleware/coreops_prefix_old.py:104:        except commands.CommandError as e:
work/Achievements/claims/middleware/coreops_prefix_old.py:109:class CoreOpsPrefixCog(commands.Cog):
work/Achievements/claims/middleware/coreops_prefix_old.py:110:    def __init__(self, bot: commands.Bot):
work/Achievements/claims/middleware/coreops_prefix_old.py:114:async def setup(bot: commands.Bot):
work/Achievements/claims/help.py:12:HELP_COLOR = discord.Color.blurple()
work/Achievements/claims/help.py:33:def build_help_overview_embed(bot_version: str) -> discord.Embed:
work/Achievements/claims/help.py:35:    e = discord.Embed(
work/Achievements/claims/help.py:42:            "**Admins** can run CoreOps with plain commands. **Everyone else** must use a **prefix**."
work/Achievements/claims/help.py:89:def build_help_subtopic_embed(bot_version: str, topic: str) -> discord.Embed | None:
work/Achievements/claims/help.py:122:    e = discord.Embed(title=f"!help {topic}", description=txt, color=HELP_COLOR)
work/Achievements/claims/ops.py:25:def build_health_embed(bot_version: str, summary: dict) -> discord.Embed:
work/Achievements/claims/ops.py:33:    e = discord.Embed(title="🏆 Appreciation & Claims — Health", color=discord.Color.blurple())
work/Achievements/claims/ops.py:113:def build_config_embed(bot_version: str, config_snapshot: dict) -> discord.Embed:
work/Achievements/claims/ops.py:115:    e = discord.Embed(title="Current configuration", color=discord.Color.blurple())
work/Achievements/claims/ops.py:139:def build_env_embed(bot_version: str, env_info: dict) -> discord.Embed:
work/Achievements/claims/ops.py:141:    e = discord.Embed(title="Environment (sanitized)", description="\n".join(lines) or "—", color=discord.Color.blurple())
work/Achievements/claims/ops.py:146:def build_checksheet_embed(bot_version: str, backend: str, items: list[dict]) -> discord.Embed:
work/Achievements/claims/ops.py:156:    e = discord.Embed(title="Checksheet — Tabs & Headers", color=discord.Color.blurple())
work/Achievements/claims/ops.py:175:def build_reload_embed(bot_version: str, source: str, loaded_at: str, counts: dict) -> discord.Embed:
work/Achievements/claims/ops.py:176:    e = discord.Embed(title="Reloaded config", color=discord.Color.blurple())
work/Achievements/claims/ops.py:187:def build_rebooting_embed(bot_version: str) -> discord.Embed:
work/Achievements/claims/ops.py:188:    e = discord.Embed(title="Rebooting…", color=discord.Color.blurple())
work/Achievements/REVIEW/MODULE_SHARD/SHARDS_AUDIT.md:10:1. **Manual-first gap on the public prompt (medium).** The first panel exposes only Scan Image and Dismiss, so the promised “Manual entry (Skip OCR)” path is absent until after a scan succeeds. If no attachment OCR succeeds, users must fall back to chat commands.【F:cogs/shards/cog.py†L160-L206】
work/Achievements/REVIEW/CODEREVIEW_20251005/THREATS.md:11:- Guardian Knights / staff interactions via privileged commands.
work/Achievements/REVIEW/CODEREVIEW_20251005/FINDINGS.md:26:-async def reloadconfig(ctx: commands.Context):
work/Achievements/REVIEW/CODEREVIEW_20251005/FINDINGS.md:27:+async def reloadconfig(ctx: commands.Context):
work/Achievements/requirements.txt:1:discord.py==2.3.2
work/Achievements/.github/scripts/feature-setup-shards-mercy.js:52:    'Dry-run in 1–2 clans; keep manual entry available; simple rollback: disable watcher, leave commands.'
work/Achievements/cogs/ops.py:7:from discord.ext import commands
work/Achievements/cogs/ops.py:32:def _coreops_guard(ctx: commands.Context) -> tuple[bool, str]:
work/Achievements/cogs/ops.py:50:class OpsCog(commands.Cog):
work/Achievements/cogs/ops.py:51:    def __init__(self, bot: commands.Bot):
work/Achievements/cogs/ops.py:54:            log.info("OpsCog loaded: commands=%s", ", ".join(sorted(bot.all_commands.keys())))
work/Achievements/cogs/ops.py:59:    @commands.command(name="health")
work/Achievements/cogs/ops.py:60:    async def health_cmd(self, ctx: commands.Context):
work/Achievements/cogs/ops.py:110:    @commands.command(name="digest")
work/Achievements/cogs/ops.py:111:    async def digest_cmd(self, ctx: commands.Context):
work/Achievements/cogs/ops.py:165:    @commands.command(name="reload")
work/Achievements/cogs/ops.py:166:    async def reload_cmd(self, ctx: commands.Context):
work/Achievements/cogs/ops.py:189:    @commands.command(name="checksheet")
work/Achievements/cogs/ops.py:190:    async def checksheet_cmd(self, ctx: commands.Context):
work/Achievements/cogs/ops.py:239:    @commands.command(name="env")
work/Achievements/cogs/ops.py:240:    async def env_cmd(self, ctx: commands.Context):
work/Achievements/cogs/ops.py:258:    @commands.command(name="reboot", aliases=["restart", "rb"])
work/Achievements/cogs/ops.py:259:    async def reboot_cmd(self, ctx: commands.Context):
work/Achievements/cogs/ops.py:304:async def setup(bot: commands.Bot):
work/Achievements/cogs/shards/cog.py:10:from discord.ext import commands
work/Achievements/cogs/shards/cog.py:27:def _has_any_role(member: discord.Member, role_ids: List[int]) -> bool:
work/Achievements/cogs/shards/cog.py:32:def _is_image_attachment(att: discord.Attachment) -> bool:
work/Achievements/cogs/shards/cog.py:41:class ShardsCog(commands.Cog):
work/Achievements/cogs/shards/cog.py:42:    def __init__(self, bot: commands.Bot):
work/Achievements/cogs/shards/cog.py:45:        self._live_views: Dict[int, discord.ui.View] = {}  # keep views referenced until timeout
work/Achievements/cogs/shards/cog.py:64:    def _clan_for_member(self, member: discord.Member) -> Optional[str]:
work/Achievements/cogs/shards/cog.py:70:    def _is_shard_thread(self, channel: discord.abc.GuildChannel) -> bool:
work/Achievements/cogs/shards/cog.py:71:        if isinstance(channel, discord.Thread):
work/Achievements/cogs/shards/cog.py:82:    async def _ocr_prefill_from_attachment(self, att: discord.Attachment) -> Dict[ShardType, int]:
work/Achievements/cogs/shards/cog.py:127:    @commands.Cog.listener()
work/Achievements/cogs/shards/cog.py:128:    async def on_message(self, message: discord.Message):
work/Achievements/cogs/shards/cog.py:131:        if not isinstance(message.channel, discord.Thread):
work/Achievements/cogs/shards/cog.py:149:                    files = [discord.File(_io.BytesIO(b), filename=name) for name, b in dbg_imgs]
work/Achievements/cogs/shards/cog.py:160:        view = discord.ui.View(timeout=300)
work/Achievements/cogs/shards/cog.py:161:        scan_btn = discord.ui.Button(
work/Achievements/cogs/shards/cog.py:162:            label="Scan Image", style=discord.ButtonStyle.primary, custom_id=f"shards:scan:{message.id}"
work/Achievements/cogs/shards/cog.py:164:        dismiss_btn = discord.ui.Button(
work/Achievements/cogs/shards/cog.py:165:            label="Dismiss", style=discord.ButtonStyle.secondary, custom_id=f"shards:dismiss:{message.id}"
work/Achievements/cogs/shards/cog.py:168:        async def _scan_callback(inter: discord.Interaction):
work/Achievements/cogs/shards/cog.py:194:            eview = discord.ui.View(timeout=180)
work/Achievements/cogs/shards/cog.py:196:            use_btn = discord.ui.Button(
work/Achievements/cogs/shards/cog.py:197:                label="Use these counts", style=discord.ButtonStyle.success, custom_id=f"shards:use:{message.id}"
work/Achievements/cogs/shards/cog.py:199:            manual_btn = discord.ui.Button(
work/Achievements/cogs/shards/cog.py:200:                label="Manual entry", style=discord.ButtonStyle.primary, custom_id=f"shards:manual:{message.id}"
work/Achievements/cogs/shards/cog.py:202:            retry_btn = discord.ui.Button(
work/Achievements/cogs/shards/cog.py:203:                label="Retry OCR", style=discord.ButtonStyle.secondary, custom_id=f"shards:retry:{message.id}"
work/Achievements/cogs/shards/cog.py:205:            close_btn = discord.ui.Button(
work/Achievements/cogs/shards/cog.py:206:                label="Close", style=discord.ButtonStyle.danger, custom_id=f"shards:close:{message.id}"
work/Achievements/cogs/shards/cog.py:209:            async def _use_counts(i2: discord.Interaction):
work/Achievements/cogs/shards/cog.py:235:            async def _manual(i2: discord.Interaction):
work/Achievements/cogs/shards/cog.py:261:            async def _retry(i2: discord.Interaction):
work/Achievements/cogs/shards/cog.py:280:            async def _close(i2: discord.Interaction):
work/Achievements/cogs/shards/cog.py:310:        async def _dismiss_callback(inter: discord.Interaction):
work/Achievements/cogs/shards/cog.py:346:    @commands.command(name="ocr")
work/Achievements/cogs/shards/cog.py:347:    async def ocr_cmd(self, ctx: commands.Context, sub: Optional[str] = None):
work/Achievements/cogs/shards/cog.py:385:    @commands.command(name="shards")
work/Achievements/cogs/shards/cog.py:386:    async def shards_cmd(self, ctx: commands.Context, sub: Optional[str] = None, *, tail: Optional[str] = None):
work/Achievements/cogs/shards/cog.py:387:        if not isinstance(ctx.channel, discord.Thread) or not self._is_shard_thread(ctx.channel):
work/Achievements/cogs/shards/cog.py:400:    async def _cmd_shards_help(self, ctx: commands.Context):
work/Achievements/cogs/shards/cog.py:411:    async def _cmd_shards_set(self, ctx: commands.Context, tail: Optional[str]):
work/Achievements/cogs/shards/cog.py:413:        target: discord.Member = ctx.author
work/Achievements/cogs/shards/cog.py:421:        view = discord.ui.View(timeout=60)
work/Achievements/cogs/shards/cog.py:422:        btn = discord.ui.Button(label="Open Set Shard Counts", style=discord.ButtonStyle.primary)
work/Achievements/cogs/shards/cog.py:424:        async def _open(inter: discord.Interaction):
work/Achievements/cogs/shards/cog.py:453:    @commands.command(name="mercy")
work/Achievements/cogs/shards/cog.py:454:    async def mercy_cmd(self, ctx: commands.Context, sub: Optional[str] = None, *, tail: Optional[str] = None):
work/Achievements/cogs/shards/cog.py:455:        if not isinstance(ctx.channel, discord.Thread) or not self._is_shard_thread(ctx.channel):
work/Achievements/cogs/shards/cog.py:464:    async def _cmd_addpulls(self, ctx: commands.Context, tail: Optional[str]):
work/Achievements/cogs/shards/cog.py:469:        def _check_shard(i: discord.Interaction):
work/Achievements/cogs/shards/cog.py:474:            inter: discord.Interaction = await self.bot.wait_for("interaction", timeout=120, check=_check_shard)
work/Achievements/cogs/shards/cog.py:519:        v = discord.ui.View(timeout=60)
work/Achievements/cogs/shards/cog.py:520:        open_btn = discord.ui.Button(label="Open rarity form", style=discord.ButtonStyle.primary)
work/Achievements/cogs/shards/cog.py:522:        async def _open2(i: discord.Interaction):
work/Achievements/cogs/shards/cog.py:691:async def setup(bot: commands.Bot):
work/Achievements/cogs/shards/renderer.py:35:) -> discord.Embed:
work/Achievements/cogs/shards/renderer.py:38:    embed = discord.Embed(title=title, description=f"Updated: {updated_utc}")
work/Achievements/cogs/shards/views.py:9:class SetCountsModal(discord.ui.Modal):
work/Achievements/cogs/shards/views.py:14:        self.mys = discord.ui.TextInput(label="🟩 Mystery", style=discord.TextStyle.short, default=str(pre.get(ShardType.MYSTERY, "")), required=False)
work/Achievements/cogs/shards/views.py:15:        self.anc = discord.ui.TextInput(label="🟦 Ancient", style=discord.TextStyle.short, default=str(pre.get(ShardType.ANCIENT, "")), required=False)
work/Achievements/cogs/shards/views.py:16:        self.void = discord.ui.TextInput(label="🟪 Void",    style=discord.TextStyle.short, default=str(pre.get(ShardType.VOID, "")), required=False)
work/Achievements/cogs/shards/views.py:17:        self.pri = discord.ui.TextInput(label="🟥 Primal",  style=discord.TextStyle.short, default=str(pre.get(ShardType.PRIMAL, "")), required=False)
work/Achievements/cogs/shards/views.py:18:        self.sac = discord.ui.TextInput(label="🟨 Sacred",  style=discord.TextStyle.short, default=str(pre.get(ShardType.SACRED, "")), required=False)
work/Achievements/cogs/shards/views.py:36:class AddPullsStart(discord.ui.View):
work/Achievements/cogs/shards/views.py:47:            self.add_item(discord.ui.Button(label=label, style=discord.ButtonStyle.primary, custom_id=f"addpulls:shard:{st.value}"))
work/Achievements/cogs/shards/views.py:49:    async def interaction_check(self, interaction: discord.Interaction) -> bool:
work/Achievements/cogs/shards/views.py:52:class AddPullsCount(discord.ui.Modal):
work/Achievements/cogs/shards/views.py:56:        self.count_inp = discord.ui.TextInput(label="How many pulls?", placeholder="1 or 10 or any whole number", style=discord.TextStyle.short)
work/Achievements/cogs/shards/views.py:64:class AddPullsRarities(discord.ui.Modal):
work/Achievements/cogs/shards/views.py:74:            ti = discord.ui.TextInput(label=label, style=discord.TextStyle.short, required=False)
work/Achievements/docs/DEVELOPMENT.md:10:* **Cogs (UI only)**: `cogs/` — admin/CoreOps commands. These call into `claims/*`.
work/Achievements/docs/DEVELOPMENT.md:35:| `!sc health`     | Admins   | `cogs/ops.py`                         | `OpsCog.health`     | `@commands.command(name="health")`     |
work/Achievements/docs/DEVELOPMENT.md:36:| `!sc digest`     | Admins   | `cogs/ops.py`                         | `OpsCog.digest`     | `@commands.command(name="digest")`     |
work/Achievements/docs/DEVELOPMENT.md:37:| `!sc reload`     | Admins   | `cogs/ops.py`                         | `OpsCog.reload`     | `@commands.command(name="reload")`     |
work/Achievements/docs/DEVELOPMENT.md:38:| `!sc checksheet` | Admins   | `cogs/ops.py`                         | `OpsCog.checksheet` | `@commands.command(name="checksheet")` |
work/Achievements/docs/DEVELOPMENT.md:39:| `!sc env`        | Admins   | `cogs/ops.py`                         | `OpsCog.env`        | `@commands.command(name="env")`        |
work/Achievements/core/prefix.py:18:    """Return the runtime prefix list for discord.py."""
work/Achievements/c1c_claims_appreciation.py:11:from discord.ext import commands
work/Achievements/c1c_claims_appreciation.py:98:intents = discord.Intents.default()
work/Achievements/c1c_claims_appreciation.py:102:bot = commands.Bot(command_prefix=get_prefix, intents=intents, strip_after_prefix=True)
work/Achievements/c1c_claims_appreciation.py:164:def _color_from_hex(hex_str: Optional[str]) -> Optional[discord.Color]:
work/Achievements/c1c_claims_appreciation.py:168:        return discord.Color(int(s, 16))
work/Achievements/c1c_claims_appreciation.py:369:def _is_image(att: discord.Attachment) -> bool:
work/Achievements/c1c_claims_appreciation.py:376:def _big_role_icon_url(role: discord.Role) -> Optional[str]:
work/Achievements/c1c_claims_appreciation.py:383:def _get_role_by_config(guild: discord.Guild, ach_row: dict) -> Optional[discord.Role]:
work/Achievements/c1c_claims_appreciation.py:389:    return discord.utils.get(guild.roles, name=name)
work/Achievements/c1c_claims_appreciation.py:399:def resolve_emoji_text(guild: discord.Guild, value: Optional[str], fallback: Optional[str]=None) -> str:
work/Achievements/c1c_claims_appreciation.py:408:        e = discord.utils.get(guild.emojis, id=int(v))
work/Achievements/c1c_claims_appreciation.py:410:    e = discord.utils.get(guild.emojis, name=v)
work/Achievements/c1c_claims_appreciation.py:413:def _inject_tokens(text: str, *, user: discord.Member, role: discord.Role, emoji: str) -> str:
work/Achievements/c1c_claims_appreciation.py:422:def resolve_hero_image(guild: discord.Guild, role: discord.Role, ach_row: dict) -> Optional[str]:
work/Achievements/c1c_claims_appreciation.py:426:async def safe_send_embed(dest, embed: discord.Embed, *, ping_user: Optional[discord.abc.User] = None):
work/Achievements/c1c_claims_appreciation.py:429:        am = discord.AllowedMentions(
work/Achievements/c1c_claims_appreciation.py:433:    except discord.Forbidden:
work/Achievements/c1c_claims_appreciation.py:441:def _resolve_target_channel(ctx: commands.Context, where: Optional[str]):
work/Achievements/c1c_claims_appreciation.py:456:def _match_levels_row_by_role(role: discord.Role) -> Optional[dict]:
work/Achievements/c1c_claims_appreciation.py:478:async def _fmt_chan_or_thread(guild: discord.Guild, chan_id: int | None) -> str:
work/Achievements/c1c_claims_appreciation.py:493:def _fmt_role(guild: discord.Guild, role_id: int | None) -> str:
work/Achievements/c1c_claims_appreciation.py:502:def build_achievement_embed(guild: discord.Guild, user: discord.Member, role: discord.Role, ach_row: dict) -> discord.Embed:
work/Achievements/c1c_claims_appreciation.py:508:    color = _color_from_hex(ach_row.get("ColorHex")) or (role.color if getattr(role.color, "value", 0) else discord.Color.blurple())
work/Achievements/c1c_claims_appreciation.py:510:    emb = discord.Embed(title=title, description=body, color=color, timestamp=datetime.datetime.utcnow())
work/Achievements/c1c_claims_appreciation.py:528:def build_group_embed(guild: discord.Guild, user: discord.Member, items: List[Tuple[discord.Role, dict]]) -> discord.Embed:
work/Achievements/c1c_claims_appreciation.py:530:    color = _color_from_hex(a0.get("ColorHex")) or (r0.color if getattr(r0.color, "value", 0) else discord.Color.blurple())
work/Achievements/c1c_claims_appreciation.py:531:    emb = discord.Embed(title=f"{user.display_name} unlocked {len(items)} achievements", color=color, timestamp=datetime.datetime.utcnow())
work/Achievements/c1c_claims_appreciation.py:556:def build_level_embed(guild: discord.Guild, user: discord.Member, row: dict) -> discord.Embed:
work/Achievements/c1c_claims_appreciation.py:562:    color = _color_from_hex(row.get("ColorHex")) or discord.Color.gold()
work/Achievements/c1c_claims_appreciation.py:564:    emb = discord.Embed(title=title, description=body, color=color, timestamp=datetime.datetime.utcnow())
work/Achievements/c1c_claims_appreciation.py:581:async def _flush_group(guild: discord.Guild, user_id: int):
work/Achievements/c1c_claims_appreciation.py:599:def _buffer_item(guild: discord.Guild, user_id: int, role: discord.Role, ach: dict):
work/Achievements/c1c_claims_appreciation.py:624:async def audit(guild: discord.Guild, text: str):
work/Achievements/c1c_claims_appreciation.py:638:class TryAgainView(discord.ui.View):
work/Achievements/c1c_claims_appreciation.py:639:    def __init__(self, owner_id: int, att: Optional[discord.Attachment], claim_id: int):
work/Achievements/c1c_claims_appreciation.py:645:    async def interaction_check(self, itx: discord.Interaction) -> bool:
work/Achievements/c1c_claims_appreciation.py:658:    @discord.ui.button(label="Try again", style=discord.ButtonStyle.primary)
work/Achievements/c1c_claims_appreciation.py:659:    async def try_again(self, itx: discord.Interaction, _btn: discord.ui.Button):
work/Achievements/c1c_claims_appreciation.py:662:class GKReview(discord.ui.View):
work/Achievements/c1c_claims_appreciation.py:663:    def __init__(self, claimant_id: int, ach_key: str, att: Optional[discord.Attachment], claim_id: int):
work/Achievements/c1c_claims_appreciation.py:670:    async def _only_gk(self, itx: discord.Interaction) -> bool:
work/Achievements/c1c_claims_appreciation.py:682:    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success)
work/Achievements/c1c_claims_appreciation.py:683:    async def approve(self, itx: discord.Interaction, _btn: discord.ui.Button):
work/Achievements/c1c_claims_appreciation.py:695:                emb = discord.Embed(
work/Achievements/c1c_claims_appreciation.py:698:                    color=discord.Color.yellow(),
work/Achievements/c1c_claims_appreciation.py:711:                emb = discord.Embed(
work/Achievements/c1c_claims_appreciation.py:714:                    color=discord.Color.green(),
work/Achievements/c1c_claims_appreciation.py:721:                emb = discord.Embed(
work/Achievements/c1c_claims_appreciation.py:725:                    color=discord.Color.red(),
work/Achievements/c1c_claims_appreciation.py:734:    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger)
work/Achievements/c1c_claims_appreciation.py:735:    async def deny(self, itx: discord.Interaction, _btn: discord.ui.Button):
work/Achievements/c1c_claims_appreciation.py:743:            opts.append(discord.SelectOption(label=label, value=code))
work/Achievements/c1c_claims_appreciation.py:745:            opts = [discord.SelectOption(label="Proof unclear. Please include the full result banner.", value="NEED_BANNER")]
work/Achievements/c1c_claims_appreciation.py:747:        v = discord.ui.View(timeout=300)
work/Achievements/c1c_claims_appreciation.py:748:        sel = discord.ui.Select(placeholder="Pick a denial reason…", options=opts)
work/Achievements/c1c_claims_appreciation.py:750:        async def _on_pick(sel_itx: discord.Interaction):
work/Achievements/c1c_claims_appreciation.py:756:                emb = discord.Embed(
work/Achievements/c1c_claims_appreciation.py:759:                    color=discord.Color.orange(),
work/Achievements/c1c_claims_appreciation.py:773:    @discord.ui.button(label="Grant different role…", style=discord.ButtonStyle.secondary)
work/Achievements/c1c_claims_appreciation.py:774:    async def grant_other(self, itx: discord.Interaction, _btn: discord.ui.Button):
work/Achievements/c1c_claims_appreciation.py:795:            opts.append(discord.SelectOption(label=label, value=a["key"]))
work/Achievements/c1c_claims_appreciation.py:797:        v = discord.ui.View(timeout=600)
work/Achievements/c1c_claims_appreciation.py:798:        sel = discord.ui.Select(placeholder="Pick a role to grant instead…", options=opts)
work/Achievements/c1c_claims_appreciation.py:800:        async def _on_pick(sel_itx: discord.Interaction):
work/Achievements/c1c_claims_appreciation.py:810:                    await itx.message.edit(embed=discord.Embed(
work/Achievements/c1c_claims_appreciation.py:813:                        color=discord.Color.green(),
work/Achievements/c1c_claims_appreciation.py:820:                    await itx.message.edit(embed=discord.Embed(
work/Achievements/c1c_claims_appreciation.py:824:                        color=discord.Color.red(),
work/Achievements/c1c_claims_appreciation.py:836:class BaseView(discord.ui.View):
work/Achievements/c1c_claims_appreciation.py:842:        self.message: Optional[discord.Message] = None
work/Achievements/c1c_claims_appreciation.py:856:    async def interaction_check(self, itx: discord.Interaction) -> bool:
work/Achievements/c1c_claims_appreciation.py:870:    def __init__(self, owner_id: int, atts: List[discord.Attachment], claim_id: int, announce: bool = False):
work/Achievements/c1c_claims_appreciation.py:874:    @discord.ui.button(label="Proceed with one role", style=discord.ButtonStyle.primary)
work/Achievements/c1c_claims_appreciation.py:875:    async def proceed_one(self, itx: discord.Interaction, _btn: discord.ui.Button):
work/Achievements/c1c_claims_appreciation.py:881:    @discord.ui.button(label="I want multiple roles", style=discord.ButtonStyle.secondary)
work/Achievements/c1c_claims_appreciation.py:882:    async def want_multiple(self, itx: discord.Interaction, _btn: discord.ui.Button):
work/Achievements/c1c_claims_appreciation.py:892:        except discord.InteractionResponded:
work/Achievements/c1c_claims_appreciation.py:905:    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
work/Achievements/c1c_claims_appreciation.py:906:    async def cancel(self, itx: discord.Interaction, _btn: discord.ui.Button):
work/Achievements/c1c_claims_appreciation.py:916:    def __init__(self, owner_id: int, atts: List[discord.Attachment], claim_id: int, announce: bool = False):
work/Achievements/c1c_claims_appreciation.py:919:        opts = [discord.SelectOption(label=f"#{i} – {a.filename}", value=str(i-1)) for i,a in enumerate(atts, start=1)]
work/Achievements/c1c_claims_appreciation.py:920:        sel = discord.ui.Select(placeholder="Choose a screenshot…", options=opts)
work/Achievements/c1c_claims_appreciation.py:924:    async def _on_pick(self, itx: discord.Interaction):
work/Achievements/c1c_claims_appreciation.py:929:    def __init__(self, owner_id: int, att: Optional[discord.Attachment],
work/Achievements/c1c_claims_appreciation.py:930:                 batch_list: Optional[List[discord.Attachment]], claim_id: int, announce: bool = False):
work/Achievements/c1c_claims_appreciation.py:935:            btn = discord.ui.Button(label=c["label"], style=discord.ButtonStyle.primary, custom_id=f"cat::{c['category']}")
work/Achievements/c1c_claims_appreciation.py:938:        cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger)
work/Achievements/c1c_claims_appreciation.py:942:    async def _cancel(self, itx: discord.Interaction):
work/Achievements/c1c_claims_appreciation.py:949:    async def _pick_cat(self, itx: discord.Interaction, cat_key: str):
work/Achievements/c1c_claims_appreciation.py:955:    def __init__(self, owner_id: int, cat_key: str, att: Optional[discord.Attachment],
work/Achievements/c1c_claims_appreciation.py:956:                 batch_list: Optional[List[discord.Attachment]], claim_id: int, announce: bool = False, page: int = 0):
work/Achievements/c1c_claims_appreciation.py:976:            opts.append(discord.SelectOption(label=label, value=a["key"]))
work/Achievements/c1c_claims_appreciation.py:978:        sel = discord.ui.Select(placeholder="Choose the exact achievement…", options=opts, min_values=1, max_values=1)
work/Achievements/c1c_claims_appreciation.py:983:        prev_btn = discord.ui.Button(label="◀ Prev", style=discord.ButtonStyle.secondary, disabled=(self.page == 0))
work/Achievements/c1c_claims_appreciation.py:984:        next_btn = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary,
work/Achievements/c1c_claims_appreciation.py:986:        back = discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary)
work/Achievements/c1c_claims_appreciation.py:987:        cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger)
work/Achievements/c1c_claims_appreciation.py:989:        async def _prev(itx: discord.Interaction):
work/Achievements/c1c_claims_appreciation.py:992:        async def _next(itx: discord.Interaction):
work/Achievements/c1c_claims_appreciation.py:995:        async def _back(itx: discord.Interaction):
work/Achievements/c1c_claims_appreciation.py:998:        async def _cancel(itx: discord.Interaction):
work/Achievements/c1c_claims_appreciation.py:1015:    async def _on_pick(self, itx: discord.Interaction):
work/Achievements/c1c_claims_appreciation.py:1023:async def show_category_picker(itx: discord.Interaction, attachment: Optional[discord.Attachment],
work/Achievements/c1c_claims_appreciation.py:1024:                               batch_list: Optional[List[discord.Attachment]] = None, claim_id: int = 0):
work/Achievements/c1c_claims_appreciation.py:1029:    except discord.InteractionResponded:
work/Achievements/c1c_claims_appreciation.py:1033:async def show_role_picker(itx: discord.Interaction, cat_key: str, attachment: Optional[discord.Attachment],
work/Achievements/c1c_claims_appreciation.py:1034:                           batch_list: Optional[List[discord.Attachment]] = None, claim_id: int = 0, page: int = 0):
work/Achievements/c1c_claims_appreciation.py:1039:    except discord.InteractionResponded:
work/Achievements/c1c_claims_appreciation.py:1044:async def finalize_grant(guild: discord.Guild, user_id: int, ach_key: str) -> bool:
work/Achievements/c1c_claims_appreciation.py:1098:            emb = discord.Embed(
work/Achievements/c1c_claims_appreciation.py:1101:                color=discord.Color.green(),
work/Achievements/c1c_claims_appreciation.py:1113:async def process_claim(itx: discord.Interaction, ach_key: str,
work/Achievements/c1c_claims_appreciation.py:1114:                        att: Optional[discord.Attachment],
work/Achievements/c1c_claims_appreciation.py:1115:                        batch_list: Optional[List[discord.Attachment]],
work/Achievements/c1c_claims_appreciation.py:1133:    async def _one(a: Optional[discord.Attachment]):
work/Achievements/c1c_claims_appreciation.py:1181:        emb = discord.Embed(
work/Achievements/c1c_claims_appreciation.py:1184:            color=discord.Color.orange(),
work/Achievements/c1c_claims_appreciation.py:1208:def _is_staff(member: discord.Member) -> bool:
work/Achievements/c1c_claims_appreciation.py:1216:async def help_cmd(ctx: commands.Context, *, topic: str = None):
work/Achievements/c1c_claims_appreciation.py:1243:    e = discord.Embed(title=f"!help {topic}", description=txt, color=HELP_COLOR)
work/Achievements/c1c_claims_appreciation.py:1249:async def testconfig(cmdx: commands.Context):
work/Achievements/c1c_claims_appreciation.py:1259:    emb = discord.Embed(title="Current configuration", color=discord.Color.blurple())
work/Achievements/c1c_claims_appreciation.py:1277:async def configstatus(ctx: commands.Context):
work/Achievements/c1c_claims_appreciation.py:1284:async def reloadconfig(ctx: commands.Context):
work/Achievements/c1c_claims_appreciation.py:1295:async def listach(ctx: commands.Context, filter_text: str = ""):
work/Achievements/c1c_claims_appreciation.py:1308:async def findach(ctx: commands.Context, *, text: str):
work/Achievements/c1c_claims_appreciation.py:1322:async def testach(ctx: commands.Context, key: str, where: Optional[str] = None):
work/Achievements/c1c_claims_appreciation.py:1338:async def testlevel(ctx: commands.Context, *, args: str = ""):
work/Achievements/c1c_claims_appreciation.py:1361:async def flushpraise(ctx: commands.Context):
work/Achievements/c1c_claims_appreciation.py:1372:async def ping(ctx: commands.Context):
work/Achievements/c1c_claims_appreciation.py:1380:HELP_COLOR = discord.Color.blurple()
work/Achievements/c1c_claims_appreciation.py:1382:def _mk_help_embed_claims(guild: discord.Guild | None = None) -> discord.Embed:
work/Achievements/c1c_claims_appreciation.py:1383:    e = discord.Embed(
work/Achievements/c1c_claims_appreciation.py:1423:    if isinstance(error, commands.CommandNotFound):
work/Achievements/c1c_claims_appreciation.py:1438:async def on_member_update(before: discord.Member, after: discord.Member):
work/Achievements/c1c_claims_appreciation.py:1459:async def on_message(msg: discord.Message):
work/Achievements/c1c_claims_appreciation.py:1621:        except discord.LoginFailure as e:
work/Achievements/c1c_claims_appreciation.py:1629:        except discord.HTTPException as e:
work/Achievements/c1c_claims_appreciation.py:1641:                log.exception("[startup] discord.HTTPException (status=%s)", status)
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
work/Achievements/REVIEW/CODEREVIEW_20251005/REVIEW.md:15:- **F-03 — Correctness:** `cogs/shards/sheets_adapter.set_summary_msg` always issues an empty `append_row` when the worksheet already has rows, triggering gspread’s “Row values must not be empty” error and preventing subsequent summary updates.【F:cogs/shards/sheets_adapter.py†L139-L165】  
work/Achievements/REVIEW/CODEREVIEW_20251005/FINDINGS.md:65:- **Issue:** When the `SUMMARY_MSGS` worksheet already contains data, the code still executes `ws.append_row([])`, which gspread rejects (`ValueError: Row values must not be empty`). Result: subsequent summary updates crash instead of updating the row.
work/Achievements/requirements.txt:5:gspread==6.1.2
work/Achievements/cogs/shards/sheets_adapter.py:18:import gspread
work/Achievements/cogs/shards/sheets_adapter.py:37:_gc = gspread.authorize(_creds)
work/Achievements/cogs/shards/sheets_adapter.py:44:    except gspread.WorksheetNotFound:
work/Achievements/c1c_claims_appreciation.py:32:    import gspread
work/Achievements/c1c_claims_appreciation.py:35:    gspread = None
work/Achievements/c1c_claims_appreciation.py:204:             f"gspread_loaded={gspread is not None} | pandas_loaded={pd is not None}")
work/Achievements/c1c_claims_appreciation.py:213:    if sid and gspread:
work/Achievements/c1c_claims_appreciation.py:218:            gc = gspread.authorize(creds)
work/WelcomeCrew/REVIEW/ARCH_MAP.md:6:3. **Sheets access** — Helpers such as `get_ws`, `upsert_welcome`, and `_load_clan_tags` use gspread synchronously and are offloaded via `_run_blocking` in some call sites.
work/WelcomeCrew/REVIEW/ARCH_MAP.md:12:- **Sheets Adapter Layer** — gspread client factory, worksheet cache, and upsert/dedupe helpers (candidate for extraction into `welcomecrew/sheets.py`).
work/WelcomeCrew/requirements.txt:2:gspread>=6.0
work/WelcomeCrew/README.md:25:   * `discord.py`, `gspread`, `google-auth`, `aiohttp`
work/WelcomeCrew/README.md:28:   pip install discord.py gspread google-auth aiohttp
work/WelcomeCrew/bot_welcomecrew.py:19:import gspread
work/WelcomeCrew/bot_welcomecrew.py:20:from gspread.exceptions import APIError
work/WelcomeCrew/bot_welcomecrew.py:136:        _gs_client = gspread.service_account_from_dict(json.loads(raw))
work/WelcomeCrew/bot_welcomecrew.py:145:    except gspread.WorksheetNotFound:
