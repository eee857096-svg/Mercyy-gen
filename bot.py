"""
╔══════════════════════════════════════════════╗
║          MERCYY GEN  —  v3.0                 ║
║      Roblox Account Generator Bot           ║
╚══════════════════════════════════════════════╝
"""

import discord
from discord.ext import commands
from discord import app_commands
import os, asyncio, time, json
from pathlib import Path
from datetime import datetime, timezone

# ══════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════
REQUIRED_STATUS   = ".gg/VQ3YNgSr"
RESTOCK_CHANNEL   = 1478365146999947368
PREM_BUY_CHANNEL  = 1478365160476381254
BOOST_BUY_CHANNEL = 1478365159520079943

ROLE_PREMIUM  = 1478365092285251586
ROLE_MEMBER   = 1478365093732552847
ROLE_ANNOUNCE = 1478365094504304813
ROLE_RESTOCK  = 1478365095234109592
ROLE_GIVEAWAY = 1478365095909130242
ROLE_DROP     = 1478365097628930049

CASHAPP_TAG = "$ASHZ67"

BOOST_TIERS = {1: "2 Weeks", 2: "1 Month", 4: "2 Months", 6: "3 Months"}

COOLDOWNS  = {"free": 86_400, "premium": 43_200, "booster": 21_600}
TIER_COLOR = {"free": 0x57f287, "premium": 0xf5c518, "booster": 0xff73fa}
TIER_ICON  = {"free": "🆓",    "premium": "⭐",      "booster": "⚡"}
TIER_CD    = {"free": "24h",   "premium": "12h",     "booster": "6h"}

TICKET_CATS = [
    ("🛒", "purchase", "Buy Premium or Booster access",  0xf5c518),
    ("🛠️", "support",  "Help with accounts or issues",   0x5865f2),
    ("⚠️", "report",   "Report a user or bug",           0xed4245),
    ("💬", "other",    "Anything else",                  0x8b8ff7),
]

RR_ROLES = [
    ("🔥", ROLE_DROP,     "Drop Pings"),
    ("📢", ROLE_ANNOUNCE, "Announcement Pings"),
    ("✅", ROLE_GIVEAWAY, "Giveaway Pings"),
    ("👑", ROLE_RESTOCK,  "Restock Pings"),
]

TOKEN = os.environ["TOKEN"]

# ══════════════════════════════════════════════════════════════════
#  BOT SETUP
# ══════════════════════════════════════════════════════════════════
intents = discord.Intents.all()
bot     = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ══════════════════════════════════════════════════════════════════
#  PERSISTENT STORAGE
# ══════════════════════════════════════════════════════════════════
DATA_DIR   = Path("data");    DATA_DIR.mkdir(exist_ok=True)
STOCK_DIR  = Path("stock");   STOCK_DIR.mkdir(exist_ok=True)
TICKET_DIR = Path("tickets"); TICKET_DIR.mkdir(exist_ok=True)
TICKET_DB  = DATA_DIR / "tickets.json"

def _tdb() -> dict:
    try:
        return json.loads(TICKET_DB.read_text("utf-8")) if TICKET_DB.exists() else {}
    except Exception:
        return {}

def _tsave(d: dict):
    TICKET_DB.write_text(json.dumps(d, indent=2), "utf-8")

def t_next() -> int:
    d = _tdb(); n = d.get("_count", 0) + 1
    d["_count"] = n; _tsave(d); return n

def t_save(cid: int, meta: dict):
    d = _tdb(); d[str(cid)] = meta; _tsave(d)

def t_get(cid: int) -> dict | None:
    return _tdb().get(str(cid))

def t_del(cid: int):
    d = _tdb(); d.pop(str(cid), None); _tsave(d)

def t_by_user(uid: int) -> int | None:
    for k, v in _tdb().items():
        if k.startswith("_"): continue
        if isinstance(v, dict) and v.get("user_id") == uid:
            return int(k)
    return None

def t_total() -> int:
    return _tdb().get("_count", 0)

def sf(svc: str, tier: str) -> Path:
    return STOCK_DIR / (f"{svc}.txt" if tier == "free" else f"{svc}_{tier}.txt")

def sread(svc: str, tier: str) -> list[str]:
    f = sf(svc, tier)
    return [l.strip() for l in f.read_text("utf-8").splitlines() if l.strip()] if f.exists() else []

def spop(svc: str, tier: str) -> str | None:
    lines = sread(svc, tier)
    if not lines: return None
    sf(svc, tier).write_text("\n".join(lines[1:]), "utf-8")
    return lines[0]

def sadd(svc: str, tier: str, accs: list[str]):
    sf(svc, tier).write_text("\n".join(sread(svc, tier) + accs), "utf-8")

def sc(svc: str, tier: str) -> int:
    return len(sread(svc, tier))

# ══════════════════════════════════════════════════════════════════
#  COOLDOWNS
# ══════════════════════════════════════════════════════════════════
cd_store: dict[str, dict[int, float]] = {t: {} for t in COOLDOWNS}

def cd_get(tier: str, uid: int) -> float | None:
    last = cd_store[tier].get(uid)
    if last is None: return None
    rem = COOLDOWNS[tier] - (time.monotonic() - last)
    return rem if rem > 0 else None

def cd_set(tier: str, uid: int):
    cd_store[tier][uid] = time.monotonic()

def fmt(s: float) -> str:
    s = int(s)
    h, r = divmod(s, 3600); m, s = divmod(r, 60)
    parts = []
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if s or not parts: parts.append(f"{s}s")
    return " ".join(parts)

# ══════════════════════════════════════════════════════════════════
#  UTILITY
# ══════════════════════════════════════════════════════════════════
def has_status(m: discord.Member) -> bool:
    needle = REQUIRED_STATUS.lower()
    for act in m.activities:
        if isinstance(act, discord.CustomActivity):
            if needle in (act.name  or "").lower(): return True
            if needle in (act.state or "").lower(): return True
    return False

def is_staff(m: discord.Member) -> bool:
    return m.guild_permissions.administrator

def gicon(g: discord.Guild) -> str | None:
    return g.icon.url if g.icon else None

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

async def reply(i: discord.Interaction, desc: str,
                color: int = 0xff4444, ephemeral: bool = True):
    e = discord.Embed(description=desc, color=color)
    try:
        if i.response.is_done():
            await i.followup.send(embed=e, ephemeral=ephemeral)
        else:
            await i.response.send_message(embed=e, ephemeral=ephemeral)
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════
#  REACTION ROLES
# ══════════════════════════════════════════════════════════════════
@bot.event
async def on_raw_reaction_add(p: discord.RawReactionActionEvent):
    if p.member and p.member.bot: return
    if getattr(bot, "rr_id", None) != p.message_id: return
    g = bot.get_guild(p.guild_id)
    if not g: return
    for emoji, rid, _ in RR_ROLES:
        if str(p.emoji) == emoji:
            r = g.get_role(rid)
            m = p.member or g.get_member(p.user_id)
            if r and m: await m.add_roles(r, reason="Reaction role")
            break

@bot.event
async def on_raw_reaction_remove(p: discord.RawReactionActionEvent):
    if getattr(bot, "rr_id", None) != p.message_id: return
    g = bot.get_guild(p.guild_id)
    if not g: return
    for emoji, rid, _ in RR_ROLES:
        if str(p.emoji) == emoji:
            r = g.get_role(rid)
            m = g.get_member(p.user_id)
            if r and m: await m.remove_roles(r, reason="Reaction role removed")
            break

# ══════════════════════════════════════════════════════════════════
#  GEN SYSTEM
# ══════════════════════════════════════════════════════════════════
class GenSelect(discord.ui.Select):
    def __init__(self, tier: str):
        self.tier = tier
        cnt = sc("roblox", tier)
        super().__init__(
            placeholder="  ↓  select a service to generate",
            options=[discord.SelectOption(
                label="Roblox", value="roblox", emoji="🎮",
                description=f"{cnt} account{'s' if cnt != 1 else ''} in stock")],
            custom_id=f"gen_select_{tier}",
            min_values=1, max_values=1)

    async def callback(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        tier   = self.tier
        member = i.guild.get_member(i.user.id)

        if not member:
            await reply(i, "> couldn't load your profile — try again in a moment")
            return

        # access checks
        if tier == "free":
            mr = i.guild.get_role(ROLE_MEMBER)
            if mr and mr not in member.roles:
                await reply(i, f"> you need the <@&{ROLE_MEMBER}> role to use free gen")
                return
            # STATUS CHECK DISABLED — uncomment to re-enable:
            # if not has_status(member):
            #     await reply(i, f"> custom status must contain `{REQUIRED_STATUS}`\n-# use `/checkstatus` for help")
            #     return

        elif tier == "premium":
            pr = i.guild.get_role(ROLE_PREMIUM)
            if pr and pr not in member.roles:
                await reply(i, f"> you need <@&{ROLE_PREMIUM}> to use premium gen\n> purchase in <#{PREM_BUY_CHANNEL}>")
                return

        elif tier == "booster":
            if not member.premium_since:
                await reply(i, "> you need to be a **Server Booster** to use this")
                return

        # cooldown
        rem = cd_get(tier, member.id)
        if rem:
            ready_ts = f"<t:{int(time.time() + rem)}:R>"
            await reply(i,
                f"> ⏳ you're on cooldown — ready {ready_ts}\n"
                f"-# {tier} resets every {TIER_CD[tier]}",
                color=0xffaa00)
            return

        # pull account
        account = spop("roblox", tier)
        if not account:
            await reply(i,
                f"> ⚠️ **{tier} roblox** is out of stock\n"
                f"-# a restock ping will go out soon",
                color=0xffaa00)
            return

        cd_set(tier, member.id)
        parts    = account.split(":", 1)
        username = parts[0]
        password = parts[1] if len(parts) > 1 else "N/A"

        dm = discord.Embed(color=TIER_COLOR[tier], timestamp=utcnow())
        dm.set_author(
            name=f"your generated roblox account  ·  {TIER_ICON[tier]} {tier}",
            icon_url=gicon(i.guild))
        dm.description = (
            "> keep this private — do not share with anyone\n"
            f"-# generated <t:{int(time.time())}:R>"
        )
        dm.add_field(name="username", value=f"```{username}```", inline=True)
        dm.add_field(name="password", value=f"```{password}```", inline=True)
        dm.add_field(name="combo",    value=f"```{account}```",  inline=False)
        dm.set_footer(text=f"Mercyy Gen  ·  {tier} tier  ·  next gen in {TIER_CD[tier]}")

        try:
            await member.send(embed=dm)
            conf = discord.Embed(color=TIER_COLOR[tier], timestamp=utcnow())
            conf.set_author(
                name="✓  account sent to your DMs",
                icon_url=member.display_avatar.url)
            conf.description = (
                f"> change the password immediately after logging in\n"
                f"-# next gen available in **{TIER_CD[tier]}**"
            )
            await i.followup.send(embed=conf, ephemeral=True)
        except discord.Forbidden:
            dm.set_footer(text=f"⚠️  DMs closed — shown here · open DMs for next time · next gen in {TIER_CD[tier]}")
            await i.followup.send(embed=dm, ephemeral=True)


class GenView(discord.ui.View):
    def __init__(self, tier: str):
        super().__init__(timeout=None)
        self.tier = tier
        self.add_item(GenSelect(tier))

    @discord.ui.button(label="upgrade", emoji="⬆️",
                       style=discord.ButtonStyle.secondary, custom_id="gv_upgrade")
    async def btn_upgrade(self, i: discord.Interaction, _: discord.ui.Button):
        e = discord.Embed(color=0xf5c518)
        e.set_author(name="upgrade to premium", icon_url=gicon(i.guild))
        e.description = (
            "**perks**\n"
            f"‣  `{TIER_CD['premium']}` cooldown  *(free is `{TIER_CD['free']}`)*\n"
            f"‣  premium-only account stock\n"
            f"‣  priority queue\n\n"
            f"**payment**\n"
            f"‣  CashApp `{CASHAPP_TAG}`\n"
            f"‣  open a 🛒 purchase ticket with proof\n\n"
            f"-# <#{PREM_BUY_CHANNEL}>"
        )
        await i.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="stock", emoji="📦",
                       style=discord.ButtonStyle.secondary, custom_id="gv_stock")
    async def btn_stock(self, i: discord.Interaction, _: discord.ui.Button):
        total = sc("roblox", "free") + sc("roblox", "premium") + sc("roblox", "booster")
        e = discord.Embed(color=0x2b2d31, timestamp=utcnow())
        e.set_author(name="live stock", icon_url=gicon(i.guild))
        e.add_field(name=f"{TIER_ICON['free']}  free",
                    value=f"`{sc('roblox','free')}` accounts", inline=True)
        e.add_field(name=f"{TIER_ICON['premium']}  premium",
                    value=f"`{sc('roblox','premium')}` accounts", inline=True)
        e.add_field(name=f"{TIER_ICON['booster']}  booster",
                    value=f"`{sc('roblox','booster')}` accounts", inline=True)
        e.set_footer(text=f"Mercyy Gen  ·  {total} total")
        await i.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="guide", emoji="📖",
                       style=discord.ButtonStyle.secondary, custom_id="gv_guide")
    async def btn_guide(self, i: discord.Interaction, _: discord.ui.Button):
        e = discord.Embed(color=0x5865f2)
        e.set_author(name="how to use your account", icon_url=gicon(i.guild))
        e.description = (
            "**1.**  copy the credentials from your DM\n"
            "**2.**  go to [roblox.com](https://roblox.com) and log in\n"
            "**3.**  immediately change the **email and password**\n"
            "**4.**  do not share the account with anyone\n\n"
            "**if it doesn't work:**\n"
            "‣  the account may have been claimed already\n"
            "‣  open a 🛠️ support ticket for help\n\n"
            "-# accounts are first-come-first-served · no refunds"
        )
        await i.response.send_message(embed=e, ephemeral=True)


# ══════════════════════════════════════════════════════════════════
#  TICKET SYSTEM
# ══════════════════════════════════════════════════════════════════

class TicketCatSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="  ↓  choose a category to open a ticket",
            options=[
                discord.SelectOption(label=label.capitalize(), value=label,
                                     emoji=emoji, description=desc)
                for emoji, label, desc, _ in TICKET_CATS],
            custom_id="tcs_main", min_values=1, max_values=1)

    async def callback(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        cat   = self.values[0]
        cdata = next((c for c in TICKET_CATS if c[1] == cat), None)
        if not cdata: return
        emoji, label, _, color = cdata
        g = i.guild; m = i.user

        # duplicate check
        existing_cid = t_by_user(m.id)
        if existing_cid:
            ch = g.get_channel(existing_cid)
            if ch:
                await reply(i, f"> you already have an open ticket — {ch.mention}\n-# close it before opening a new one", color=0xffaa00)
                return
            else:
                t_del(existing_cid)

        num     = t_next()
        ch_name = f"ticket-{num:04d}"
        tick_cat = (
            discord.utils.get(g.categories, name="🎫 tickets") or
            discord.utils.get(g.categories, name="tickets")    or
            discord.utils.get(g.categories, name="Tickets")
        )

        ow = {
            g.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False),
            m:              discord.PermissionOverwrite(read_messages=True,  send_messages=True,
                                                        attach_files=True,   embed_links=True,
                                                        read_message_history=True),
            g.me:           discord.PermissionOverwrite(read_messages=True,  send_messages=True,
                                                        manage_channels=True, manage_messages=True,
                                                        read_message_history=True),
        }
        for r in g.roles:
            if r.permissions.administrator and r != g.default_role:
                ow[r] = discord.PermissionOverwrite(read_messages=True, send_messages=True,
                                                     manage_messages=True, read_message_history=True)

        ch = await g.create_text_channel(
            ch_name, overwrites=ow, category=tick_cat,
            topic=f"owner:{m.id} | #{num:04d} | {label}",
            reason=f"Ticket #{num:04d} — {m} ({label})")

        t_save(ch.id, {
            "number":     num,
            "user_id":    m.id,
            "username":   str(m),
            "category":   label,
            "color":      color,
            "opened_at":  utcnow().isoformat(),
            "claimed_by": None,
        })

        e = discord.Embed(color=color, timestamp=utcnow())
        e.set_author(name=f"{emoji}  {label}  ·  ticket #{num:04d}", icon_url=gicon(g))

        body = {
            "purchase": (
                f"hey {m.mention}!\n\n"
                f"**what would you like to purchase?**\n\n"
                f"💎  **premium**\n"
                f"    ‣  `{TIER_CD['premium']}` cooldown  ·  premium stock  ·  priority access\n"
                f"    ‣  CashApp `{CASHAPP_TAG}`\n\n"
                f"⚡  **booster**\n"
                f"    ‣  `{TIER_CD['booster']}` cooldown  ·  exclusive stock\n"
                f"    ‣  just boost the server — access is automatic\n\n"
                f"-# attach your payment screenshot and staff will verify it shortly"
            ),
            "support": (
                f"hey {m.mention}!\n\n"
                f"**describe your issue** and staff will help you out\n\n"
                f"to speed things up, include:\n"
                f"‣  what happened and when\n"
                f"‣  what you were doing\n"
                f"‣  any screenshots or error messages\n\n"
                f"-# average response time: under 1 hour"
            ),
            "report": (
                f"hey {m.mention}!\n\n"
                f"**who or what are you reporting?**\n\n"
                f"please provide:\n"
                f"‣  their username or user ID\n"
                f"‣  what they did\n"
                f"‣  screenshots or evidence\n\n"
                f"-# all reports are handled confidentially"
            ),
            "other": (
                f"hey {m.mention}!\n\n"
                f"**what do you need help with?**\n\n"
                f"-# a staff member will be with you shortly"
            ),
        }
        e.description = body.get(label, body["other"])
        e.add_field(name="user",     value=m.mention,           inline=True)
        e.add_field(name="category", value=f"{emoji}  {label}", inline=True)
        e.add_field(name="ticket",   value=f"`#{num:04d}`",      inline=True)
        e.set_footer(text="Mercyy Gen  ·  use the buttons below to manage this ticket")

        await ch.send(content=m.mention, embed=e, view=TicketControlView())

        try:
            dm_e = discord.Embed(color=color, timestamp=utcnow())
            dm_e.set_author(name=f"ticket #{num:04d} opened  ·  {g.name}", icon_url=gicon(g))
            dm_e.description = f"your **{label}** ticket has been created\n\n→ {ch.mention}\n\n-# staff will respond shortly"
            await m.send(embed=dm_e)
        except discord.Forbidden:
            pass

        conf = discord.Embed(color=color)
        conf.set_author(name=f"✓  ticket #{num:04d} created")
        conf.description = f"> {ch.mention}"
        await i.followup.send(embed=conf, ephemeral=True)


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketCatSelect())


class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="claim", emoji="🙋",
                       style=discord.ButtonStyle.success, custom_id="tcv_claim")
    async def btn_claim(self, i: discord.Interaction, _: discord.ui.Button):
        if not is_staff(i.user):
            await reply(i, "> only staff can claim tickets")
            return
        meta = t_get(i.channel.id)
        if meta and meta.get("claimed_by"):
            await reply(i, f"> already claimed by <@{meta['claimed_by']}>", color=0xffaa00)
            return
        if meta:
            meta["claimed_by"] = i.user.id
            t_save(i.channel.id, meta)
        e = discord.Embed(color=0x57f287, timestamp=utcnow())
        e.set_author(name=f"claimed  ·  {i.user.display_name}", icon_url=i.user.display_avatar.url)
        e.description = "-# this ticket is now being handled"
        await i.response.send_message(embed=e)

    @discord.ui.button(label="add user", emoji="➕",
                       style=discord.ButtonStyle.secondary, custom_id="tcv_add")
    async def btn_add(self, i: discord.Interaction, _: discord.ui.Button):
        if not is_staff(i.user):
            await reply(i, "> only staff can add users")
            return
        await i.response.send_modal(AddUserModal())

    @discord.ui.button(label="remove user", emoji="➖",
                       style=discord.ButtonStyle.secondary, custom_id="tcv_remove")
    async def btn_remove(self, i: discord.Interaction, _: discord.ui.Button):
        if not is_staff(i.user):
            await reply(i, "> only staff can remove users")
            return
        await i.response.send_modal(RemoveUserModal())

    @discord.ui.button(label="transcript", emoji="📋",
                       style=discord.ButtonStyle.secondary, custom_id="tcv_transcript")
    async def btn_transcript(self, i: discord.Interaction, _: discord.ui.Button):
        if not is_staff(i.user):
            await reply(i, "> only staff can generate transcripts")
            return
        await i.response.defer(ephemeral=True)
        await _build_transcript(i, dm_user=False)

    @discord.ui.button(label="close", emoji="🔒",
                       style=discord.ButtonStyle.danger, custom_id="tcv_close")
    async def btn_close(self, i: discord.Interaction, _: discord.ui.Button):
        meta = t_get(i.channel.id)
        uid  = meta["user_id"] if meta else None
        if not is_staff(i.user) and i.user.id != uid:
            await reply(i, "> only the ticket owner or staff can close this")
            return
        e = discord.Embed(color=0xed4245, timestamp=utcnow())
        e.set_author(name="closing ticket", icon_url=i.user.display_avatar.url)
        e.description = f"> closed by {i.user.mention}  ·  deleting in **10 seconds**\n-# click cancel to abort"
        await i.response.send_message(embed=e, view=CancelCloseView())
        await asyncio.sleep(10)
        if i.channel:
            t_del(i.channel.id)
            try:
                await i.channel.delete(reason=f"Ticket closed by {i.user}")
            except Exception:
                pass


async def _build_transcript(i: discord.Interaction, dm_user: bool = True) -> Path | None:
    meta = t_get(i.channel.id)
    num  = meta["number"] if meta else "?"

    header = [
        "╔══════════════════════════════════════════════╗",
        "║         MERCYY GEN  ·  TICKET TRANSCRIPT     ║",
        "╚══════════════════════════════════════════════╝",
        f"Ticket:    #{num:04d}" if isinstance(num, int) else f"Ticket:    {num}",
        f"Channel:   #{i.channel.name}",
        f"Category:  {meta.get('category', '—') if meta else '—'}",
        f"Opened by: {meta.get('username', '—') if meta else '—'}",
        f"Opened at: {meta.get('opened_at', '—') if meta else '—'}",
        f"Claimed by: {meta.get('claimed_by', 'unclaimed') if meta else '—'}",
        f"Generated: {utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "─" * 50, "",
    ]
    lines = header[:]
    async for msg in i.channel.history(limit=1000, oldest_first=True):
        ts_str = msg.created_at.strftime("%Y-%m-%d %H:%M")
        author = msg.author.display_name
        if msg.content:
            lines.append(f"[{ts_str}] {author}: {msg.content}")
        for emb in msg.embeds:
            raw = (emb.description or "").replace("-# ", "").replace("> ", "")
            if raw:
                lines.append(f"[{ts_str}] [embed] {author}: {raw[:300]}")
        for att in msg.attachments:
            lines.append(f"[{ts_str}] [attachment] {author}: {att.url}")

    fpath = TICKET_DIR / f"transcript-{i.channel.name}.txt"
    fpath.write_text("\n".join(lines), "utf-8")

    if dm_user and meta:
        user = i.guild.get_member(meta["user_id"])
        if user:
            try:
                dm_e = discord.Embed(color=0x5865f2, timestamp=utcnow())
                dm_e.set_author(name=f"ticket #{num:04d}  ·  transcript", icon_url=gicon(i.guild))
                dm_e.description = "-# your ticket has been closed — full transcript attached"
                await user.send(embed=dm_e, file=discord.File(fpath))
            except discord.Forbidden:
                pass

    e = discord.Embed(color=0x57f287, timestamp=utcnow())
    e.set_author(name="transcript ready")
    e.description = f"> {len(lines) - len(header)} messages captured"
    if dm_user and meta:
        e.description += f"\n-# sent to <@{meta['user_id']}>"
    await i.followup.send(embed=e, file=discord.File(fpath), ephemeral=True)
    return fpath


class CancelCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=9)

    @discord.ui.button(label="cancel", emoji="↩️",
                       style=discord.ButtonStyle.secondary, custom_id="ccv_cancel")
    async def cancel(self, i: discord.Interaction, btn: discord.ui.Button):
        btn.disabled = True; self.stop()
        e = discord.Embed(color=0x57f287)
        e.description = "> close cancelled"
        await i.response.edit_message(embed=e, view=self)


class AddUserModal(discord.ui.Modal, title="Add User to Ticket"):
    user_id = discord.ui.TextInput(
        label="User ID", placeholder="right-click user → Copy ID",
        min_length=15, max_length=20)

    async def on_submit(self, i: discord.Interaction):
        try:
            uid = int(self.user_id.value.strip())
            m   = i.guild.get_member(uid) or await i.guild.fetch_member(uid)
            await i.channel.set_permissions(m, read_messages=True, send_messages=True,
                                             attach_files=True, read_message_history=True)
            e = discord.Embed(color=0x57f287)
            e.description = f"> {m.mention} added to the ticket"
            await i.response.send_message(embed=e)
        except Exception:
            await reply(i, "> couldn't find that user — double-check the ID")


class RemoveUserModal(discord.ui.Modal, title="Remove User from Ticket"):
    user_id = discord.ui.TextInput(
        label="User ID", placeholder="right-click user → Copy ID",
        min_length=15, max_length=20)

    async def on_submit(self, i: discord.Interaction):
        try:
            uid  = int(self.user_id.value.strip())
            meta = t_get(i.channel.id)
            if meta and uid == meta.get("user_id"):
                await reply(i, "> can't remove the ticket owner — close the ticket instead")
                return
            m = i.guild.get_member(uid) or await i.guild.fetch_member(uid)
            await i.channel.set_permissions(m, overwrite=None)
            e = discord.Embed(color=0x57f287)
            e.description = f"> {m.mention} removed from the ticket"
            await i.response.send_message(embed=e)
        except Exception:
            await reply(i, "> couldn't find that user — double-check the ID")


class PurchaseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="buy premium", emoji="💎",
                       style=discord.ButtonStyle.success, custom_id="pv_premium")
    async def buy_premium(self, i: discord.Interaction, _: discord.ui.Button):
        e = discord.Embed(color=0xf5c518)
        e.set_author(name="buy premium", icon_url=gicon(i.guild))
        e.description = (
            f"**CashApp:** `{CASHAPP_TAG}`\n\n"
            "**1.**  send payment\n"
            "**2.**  screenshot the receipt\n"
            "**3.**  open a 🛒 purchase ticket\n"
            "**4.**  role given within **24 hours**"
        )
        await i.response.send_message(embed=e, ephemeral=True)


# ══════════════════════════════════════════════════════════════════
#  EVENTS
# ══════════════════════════════════════════════════════════════════
@bot.event
async def on_ready():
    print(f"\n{'═'*50}")
    print(f"  Mercyy Gen  ·  v3.0  ·  {bot.user}")
    print(f"  Guilds: {len(bot.guilds)}")
    print(f"{'═'*50}\n")
    for t in ("free", "premium", "booster"):
        bot.add_view(GenView(t))
    bot.add_view(TicketPanelView())
    bot.add_view(TicketControlView())
    bot.add_view(CancelCloseView())
    bot.add_view(PurchaseView())
    try:
        synced = await bot.tree.sync()
        print(f"✅  synced {len(synced)} commands")
    except Exception as ex:
        print(f"❌  sync error: {ex}")
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="mercyy gen"))


# ══════════════════════════════════════════════════════════════════
#  SLASH COMMANDS
# ══════════════════════════════════════════════════════════════════

@bot.tree.command(name="checkstatus",
                  description="Check if your status meets the free gen requirement")
async def checkstatus(interaction: discord.Interaction):
    m = interaction.guild.get_member(interaction.user.id)
    if not m:
        await reply(interaction, "> couldn't read your profile — try again in a moment")
        return
    ok     = has_status(m)
    custom = next((a for a in m.activities if isinstance(a, discord.CustomActivity)), None)
    current = f"`{custom.name}`" if custom and custom.name else "`(no custom status set)`"
    if ok:
        e = discord.Embed(color=0x57f287)
        e.set_author(name="✓  status verified", icon_url=m.display_avatar.url)
        e.description = f"your status contains `{REQUIRED_STATUS}` — you're all good!\n\n**current status:** {current}"
    else:
        e = discord.Embed(color=0xed4245)
        e.set_author(name="status not found", icon_url=m.display_avatar.url)
        e.description = (
            f"**current status:** {current}\n"
            f"**required:** `{REQUIRED_STATUS}`\n\n"
            f"**how to fix:**\n"
            f"‣  click your avatar at the bottom-left of Discord\n"
            f"‣  click **Set Custom Status**\n"
            f"‣  type or paste `{REQUIRED_STATUS}`\n"
            f"‣  save, then run `/checkstatus` again\n\n"
            f"-# status must be set before generating"
        )
    await interaction.response.send_message(embed=e, ephemeral=True)


@bot.tree.command(name="setup_gen", description="Post a generator panel (Admin)")
@app_commands.describe(tier="tier to post")
@app_commands.choices(tier=[
    app_commands.Choice(name="Free",    value="free"),
    app_commands.Choice(name="Premium", value="premium"),
    app_commands.Choice(name="Booster", value="booster"),
])
@app_commands.checks.has_permissions(administrator=True)
async def setup_gen(interaction: discord.Interaction, tier: app_commands.Choice[str]):
    t   = tier.value
    cnt = sc("roblox", t)
    access = {
        "free":    f"‣  requires <@&{ROLE_MEMBER}>\n‣  custom status `{REQUIRED_STATUS}` *(currently disabled)*",
        "premium": f"‣  requires <@&{ROLE_PREMIUM}>\n‣  purchase in <#{PREM_BUY_CHANNEL}>",
        "booster": f"‣  server boosters only\n‣  info in <#{BOOST_BUY_CHANNEL}>",
    }
    e = discord.Embed(color=TIER_COLOR[t], timestamp=utcnow())
    e.set_author(name=f"mercyy gen  ·  {t} generator", icon_url=gicon(interaction.guild))
    e.description = (
        f"### {TIER_ICON[t]}  {t} generator\n"
        f"> select a service from the dropdown below\n\n"
        f"**[ stocks ]**  `🎮  roblox  ·  {cnt} accounts`\n"
        f"**[ cooldown ]**  `{TIER_CD[t]} per generation`\n"
        f"**[ access ]**\n{access[t]}"
    )
    e.set_footer(text="Mercyy Gen  ·  accounts sent to your DMs")
    await interaction.channel.send(embed=e, view=GenView(t))
    await interaction.response.send_message(f"> ✅  {t} gen panel posted", ephemeral=True)


@bot.tree.command(name="restock", description="Upload accounts to stock (Admin)")
@app_commands.describe(tier="tier to restock", service="which service",
                        file=".txt — one account per line")
@app_commands.choices(
    tier=[
        app_commands.Choice(name="Free",    value="free"),
        app_commands.Choice(name="Premium", value="premium"),
        app_commands.Choice(name="Booster", value="booster"),
    ],
    service=[app_commands.Choice(name="Roblox", value="roblox")])
@app_commands.checks.has_permissions(administrator=True)
async def restock(interaction: discord.Interaction,
                  tier: app_commands.Choice[str],
                  service: app_commands.Choice[str],
                  file: discord.Attachment):
    await interaction.response.defer(ephemeral=True)
    if not file.filename.endswith(".txt"):
        await interaction.followup.send("> ❌  attach a `.txt` file", ephemeral=True)
        return
    raw = (await file.read()).decode("utf-8", errors="ignore")
    new = [l.strip() for l in raw.splitlines() if l.strip()]
    if not new:
        await interaction.followup.send("> ❌  the file is empty", ephemeral=True)
        return
    sadd(service.value, tier.value, new)
    total = sc(service.value, tier.value)
    ch = bot.get_channel(RESTOCK_CHANNEL)
    if ch:
        rr   = interaction.guild.get_role(ROLE_RESTOCK)
        ping = rr.mention if rr else ""
        re   = discord.Embed(color=TIER_COLOR[tier.value], timestamp=utcnow())
        re.set_author(name="restock", icon_url=gicon(interaction.guild))
        re.description = (
            f"**{TIER_ICON[tier.value]}  {tier.name} roblox** has been restocked!\n\n"
            f"`+{len(new)} accounts added  ·  {total} total in stock`"
        )
        re.set_footer(text="Mercyy Gen")
        await ch.send(content=ping, embed=re)
    await interaction.followup.send(
        f"> ✅  restocked **{tier.name} roblox** — `+{len(new)}` added, `{total}` total",
        ephemeral=True)


@bot.tree.command(name="stock", description="View live stock counts")
async def stock_cmd(interaction: discord.Interaction):
    totals = {t: sc("roblox", t) for t in ("free", "premium", "booster")}
    grand  = sum(totals.values())
    e = discord.Embed(color=0x2b2d31, timestamp=utcnow())
    e.set_author(name="stock overview", icon_url=gicon(interaction.guild))
    for t, n in totals.items():
        bar = "█" * min(n // 5, 10) + "░" * max(0, 10 - n // 5)
        e.add_field(name=f"{TIER_ICON[t]}  {t}",
                    value=f"`{bar}`\n`{n} accounts`", inline=True)
    e.set_footer(text=f"Mercyy Gen  ·  {grand} accounts total")
    await interaction.response.send_message(embed=e, ephemeral=True)


@bot.tree.command(name="cooldown", description="Check your gen cooldowns")
async def cooldown_cmd(interaction: discord.Interaction):
    uid   = interaction.user.id
    lines = []
    for t in ("free", "premium", "booster"):
        rem = cd_get(t, uid)
        if rem:
            ready_ts = f"<t:{int(time.time() + rem)}:R>"
            lines.append(f"{TIER_ICON[t]}  **{t}**  —  ⏳ ready {ready_ts}")
        else:
            lines.append(f"{TIER_ICON[t]}  **{t}**  —  ✅ `ready to gen`")
    e = discord.Embed(color=0x5865f2, timestamp=utcnow())
    e.set_author(name="your cooldowns", icon_url=interaction.user.display_avatar.url)
    e.description = "\n".join(lines)
    await interaction.response.send_message(embed=e, ephemeral=True)


@bot.tree.command(name="reset_cooldown", description="Reset a user's cooldown (Admin)")
@app_commands.describe(member="user to reset", tier="tier to reset")
@app_commands.choices(tier=[
    app_commands.Choice(name="Free",    value="free"),
    app_commands.Choice(name="Premium", value="premium"),
    app_commands.Choice(name="Booster", value="booster"),
    app_commands.Choice(name="All",     value="all"),
])
@app_commands.checks.has_permissions(administrator=True)
async def reset_cd(interaction: discord.Interaction,
                   member: discord.Member,
                   tier: app_commands.Choice[str]):
    tiers = list(COOLDOWNS) if tier.value == "all" else [tier.value]
    for t in tiers:
        cd_store[t].pop(member.id, None)
    await interaction.response.send_message(
        f"> ✅  reset **{tier.name}** cooldown for {member.mention}", ephemeral=True)


@bot.tree.command(name="setup_reaction_roles",
                  description="Post the notification ping roles panel (Admin)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_rr(interaction: discord.Interaction):
    rows = "\n".join(f"{emoji}  —  **{label}**" for emoji, _, label in RR_ROLES)
    e = discord.Embed(color=0x2b2d31)
    e.set_author(name="notification roles", icon_url=gicon(interaction.guild))
    e.description = f"{rows}\n\n-# react to get a role  ·  react again to remove it"
    msg = await interaction.channel.send(embed=e)
    for emoji, _, _ in RR_ROLES:
        await msg.add_reaction(emoji)
    bot.rr_id = msg.id
    await interaction.response.send_message(
        f"> ✅  posted — run `/set_rr_message {msg.id}` after every bot restart",
        ephemeral=True)


@bot.tree.command(name="set_rr_message",
                  description="Re-link reaction roles after a restart (Admin)")
@app_commands.describe(message_id="message ID of the reaction role panel")
@app_commands.checks.has_permissions(administrator=True)
async def set_rr(interaction: discord.Interaction, message_id: str):
    try:
        bot.rr_id = int(message_id)
        await interaction.response.send_message(
            f"> ✅  reaction roles linked to `{message_id}`", ephemeral=True)
    except ValueError:
        await interaction.response.send_message("> ❌  invalid message ID", ephemeral=True)


@bot.tree.command(name="setup_tickets",
                  description="Post the ticket support panel (Admin)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_tickets(interaction: discord.Interaction):
    e = discord.Embed(color=0x2b2d31)
    e.set_author(name="mercyy gen  ·  support", icon_url=gicon(interaction.guild))
    e.description = (
        "### 🎫  need help? open a ticket\n"
        "> choose a category from the dropdown below\n\n"
        "🛒  **purchase**  —  buy premium or booster access\n"
        "🛠️  **support**   —  account help or general issues\n"
        "⚠️  **report**    —  report a user or bug\n"
        "💬  **other**     —  anything else\n\n"
        "-# tickets are typically answered within a few hours"
    )
    e.set_footer(text="Mercyy Gen")
    await interaction.channel.send(embed=e, view=TicketPanelView())
    await interaction.response.send_message("> ✅  ticket panel posted", ephemeral=True)


@bot.tree.command(name="setup_purchase",
                  description="Post a purchase info panel (Admin)")
@app_commands.describe(product="premium or booster")
@app_commands.choices(product=[
    app_commands.Choice(name="Premium", value="premium"),
    app_commands.Choice(name="Booster", value="booster"),
])
@app_commands.checks.has_permissions(administrator=True)
async def setup_purchase(interaction: discord.Interaction, product: app_commands.Choice[str]):
    ic = gicon(interaction.guild)
    if product.value == "booster":
        tiers = "\n".join(
            f"‣  `{b} boost{'s' if b > 1 else ''}`  →  **{l}** access"
            for b, l in BOOST_TIERS.items())
        e = discord.Embed(color=0xff73fa)
        e.set_author(name="booster generator access", icon_url=ic)
        e.description = (
            f"boost the server to unlock the **booster generator**\n\n"
            f"**boost tiers**\n{tiers}\n\n"
            f"‣  `{TIER_CD['booster']}` cooldown\n"
            f"‣  exclusive stock\n\n"
            f"-# access is granted automatically — no purchase needed"
        )
        await interaction.channel.send(embed=e)
    else:
        e = discord.Embed(color=0xf5c518)
        e.set_author(name="buy premium", icon_url=ic)
        e.description = (
            f"**perks**\n"
            f"‣  `{TIER_CD['premium']}` cooldown  *(free is `{TIER_CD['free']}`)*\n"
            f"‣  premium-only account stock\n"
            f"‣  priority access\n\n"
            f"**how to buy**\n"
            f"‣  send payment to CashApp **`{CASHAPP_TAG}`**\n"
            f"‣  open a 🛒 purchase ticket with screenshot proof\n"
            f"‣  role given within **24 hours** of verification\n\n"
            f"-# payments are non-refundable"
        )
        await interaction.channel.send(embed=e, view=PurchaseView())
    await interaction.response.send_message("> ✅  purchase panel posted", ephemeral=True)


@bot.tree.command(name="clear_stock", description="Wipe stock for a tier (Admin)")
@app_commands.describe(service="service", tier="tier to clear")
@app_commands.choices(
    service=[app_commands.Choice(name="Roblox", value="roblox")],
    tier=[
        app_commands.Choice(name="Free",    value="free"),
        app_commands.Choice(name="Premium", value="premium"),
        app_commands.Choice(name="Booster", value="booster"),
        app_commands.Choice(name="All",     value="all"),
    ])
@app_commands.checks.has_permissions(administrator=True)
async def clear_stock(interaction: discord.Interaction,
                      service: app_commands.Choice[str],
                      tier: app_commands.Choice[str]):
    tiers = ["free", "premium", "booster"] if tier.value == "all" else [tier.value]
    for t in tiers:
        sf(service.value, t).write_text("", "utf-8")
    await interaction.response.send_message(
        f"> ✅  cleared **{tier.name} {service.name}**", ephemeral=True)


@bot.tree.command(name="add", description="Add a user to this ticket (Admin)")
@app_commands.describe(member="user to add")
@app_commands.checks.has_permissions(administrator=True)
async def add_cmd(interaction: discord.Interaction, member: discord.Member):
    await interaction.channel.set_permissions(
        member, read_messages=True, send_messages=True,
        attach_files=True, read_message_history=True)
    e = discord.Embed(color=0x57f287)
    e.description = f"> {member.mention} added to the ticket"
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="remove", description="Remove a user from this ticket (Admin)")
@app_commands.describe(member="user to remove")
@app_commands.checks.has_permissions(administrator=True)
async def remove_cmd(interaction: discord.Interaction, member: discord.Member):
    meta = t_get(interaction.channel.id)
    if meta and member.id == meta.get("user_id"):
        await reply(interaction, "> can't remove the ticket owner — close the ticket instead")
        return
    await interaction.channel.set_permissions(member, overwrite=None)
    e = discord.Embed(color=0x57f287)
    e.description = f"> {member.mention} removed from the ticket"
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="rename", description="Rename this ticket channel (Admin)")
@app_commands.describe(name="new channel name")
@app_commands.checks.has_permissions(administrator=True)
async def rename_cmd(interaction: discord.Interaction, name: str):
    old = interaction.channel.name
    await interaction.channel.edit(name=name.lower().replace(" ", "-"))
    e = discord.Embed(color=0x57f287)
    e.description = f"> renamed `#{old}` → `#{name}`"
    await interaction.response.send_message(embed=e, ephemeral=True)


@bot.tree.command(name="ticket_info", description="View info about this ticket (Admin)")
@app_commands.checks.has_permissions(administrator=True)
async def ticket_info(interaction: discord.Interaction):
    meta = t_get(interaction.channel.id)
    if not meta:
        await reply(interaction, "> this doesn't appear to be a ticket channel")
        return
    cat   = next((c for c in TICKET_CATS if c[1] == meta.get("category")), None)
    color = cat[3] if cat else 0x2b2d31
    e = discord.Embed(color=color, timestamp=utcnow())
    e.set_author(name=f"ticket #{meta['number']:04d}", icon_url=gicon(interaction.guild))
    e.add_field(name="user",     value=f"<@{meta['user_id']}>",              inline=True)
    e.add_field(name="category", value=meta.get("category", "—"),            inline=True)
    e.add_field(name="claimed",
                value=f"<@{meta['claimed_by']}>" if meta.get("claimed_by") else "unclaimed",
                inline=True)
    opened = meta.get("opened_at", "")
    if opened:
        try:
            dt = datetime.fromisoformat(opened)
            e.add_field(name="opened", value=f"<t:{int(dt.timestamp())}:R>", inline=True)
        except Exception:
            pass
    await interaction.response.send_message(embed=e, ephemeral=True)


@bot.tree.command(name="stats", description="View bot statistics (Admin)")
@app_commands.checks.has_permissions(administrator=True)
async def stats_cmd(interaction: discord.Interaction):
    total_stock = sum(sc("roblox", t) for t in ("free", "premium", "booster"))
    e = discord.Embed(color=0x2b2d31, timestamp=utcnow())
    e.set_author(name="mercyy gen  ·  stats", icon_url=gicon(interaction.guild))
    e.add_field(name="total stock",   value=f"`{total_stock}` accounts", inline=True)
    e.add_field(name="total tickets", value=f"`{t_total()}` created",    inline=True)
    e.add_field(name="users tracked",
                value=f"`{sum(len(v) for v in cd_store.values())}` users", inline=True)
    e.add_field(name="free",    value=f"`{sc('roblox','free')}`",    inline=True)
    e.add_field(name="premium", value=f"`{sc('roblox','premium')}`", inline=True)
    e.add_field(name="booster", value=f"`{sc('roblox','booster')}`", inline=True)
    e.set_footer(text="Mercyy Gen  ·  v3.0")
    await interaction.response.send_message(embed=e, ephemeral=True)


@bot.tree.error
async def on_err(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await reply(interaction, "> you don't have permission to use this command")
    elif isinstance(error, app_commands.CommandOnCooldown):
        await reply(interaction, f"> slow down — retry in `{error.retry_after:.1f}s`", color=0xffaa00)
    else:
        await reply(interaction, f"> something went wrong\n```\n{error}\n```")
        raise error


bot.run(TOKEN)
