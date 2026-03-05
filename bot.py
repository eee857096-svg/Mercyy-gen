import discord
from discord.ext import commands
from discord import app_commands
import os, asyncio, time, json
from pathlib import Path

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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

COOLDOWNS  = {"free": 86400, "premium": 43200, "booster": 21600}
TIER_COLOR = {"free": 0x57f287, "premium": 0xf5c518, "booster": 0xff73fa}
TIER_ICON  = {"free": "🆓", "premium": "⭐", "booster": "⚡"}
TIER_CD    = {"free": "24h", "premium": "12h", "booster": "6h"}

TOKEN = os.environ["TOKEN"]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  BOT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  COOLDOWNS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
cooldown_store: dict[str, dict[int, float]] = {t: {} for t in COOLDOWNS}

def get_cooldown(tier: str, uid: int):
    last = cooldown_store[tier].get(uid)
    if last is None:
        return None
    rem = COOLDOWNS[tier] - (time.monotonic() - last)
    return rem if rem > 0 else None

def set_cooldown(tier: str, uid: int):
    cooldown_store[tier][uid] = time.monotonic()

def fmt(s: float) -> str:
    s = int(s)
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    out = []
    if h: out.append(f"{h}h")
    if m: out.append(f"{m}m")
    if s or not out: out.append(f"{s}s")
    return " ".join(out)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  STATUS CHECK
#  MUST use guild.get_member() — NOT fetch_member()
#  fetch_member() uses REST API which strips activity data.
#  get_member() reads from gateway cache which has presences.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def has_status(member: discord.Member) -> bool:
    needle = REQUIRED_STATUS.lower()
    for act in member.activities:
        if isinstance(act, discord.CustomActivity):
            if needle in (act.name or "").lower():
                return True
            if needle in (act.state or "").lower():
                return True
    return False

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  STOCK
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STOCK = Path("stock")
STOCK.mkdir(exist_ok=True)

def sf(svc: str, tier: str) -> Path:
    return STOCK / (f"{svc}.txt" if tier == "free" else f"{svc}_{tier}.txt")

def sread(svc: str, tier: str) -> list[str]:
    f = sf(svc, tier)
    return [l.strip() for l in f.read_text("utf-8").splitlines() if l.strip()] if f.exists() else []

def spop(svc: str, tier: str) -> str | None:
    lines = sread(svc, tier)
    if not lines:
        return None
    sf(svc, tier).write_text("\n".join(lines[1:]), "utf-8")
    return lines[0]

def sadd(svc: str, tier: str, accs: list[str]):
    sf(svc, tier).write_text("\n".join(sread(svc, tier) + accs), "utf-8")

def sc(svc: str, tier: str) -> int:
    return len(sread(svc, tier))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  REACTION ROLES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RR = [
    ("🔥", ROLE_DROP,     "Drop Ping"),
    ("📢", ROLE_ANNOUNCE, "Announcement Ping"),
    ("✅", ROLE_GIVEAWAY, "Giveaway Ping"),
    ("👑", ROLE_RESTOCK,  "Restock Ping"),
]

@bot.event
async def on_raw_reaction_add(p: discord.RawReactionActionEvent):
    if p.member and p.member.bot:
        return
    if getattr(bot, "rr_id", None) != p.message_id:
        return
    g = bot.get_guild(p.guild_id)
    if not g:
        return
    for emoji, rid, _ in RR:
        if str(p.emoji) == emoji:
            r = g.get_role(rid)
            m = p.member or g.get_member(p.user_id)
            if r and m:
                await m.add_roles(r)
            break

@bot.event
async def on_raw_reaction_remove(p: discord.RawReactionActionEvent):
    if getattr(bot, "rr_id", None) != p.message_id:
        return
    g = bot.get_guild(p.guild_id)
    if not g:
        return
    for emoji, rid, _ in RR:
        if str(p.emoji) == emoji:
            r = g.get_role(rid)
            m = g.get_member(p.user_id)
            if r and m:
                await m.remove_roles(r)
            break

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HELPER — send clean error
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def err(interaction: discord.Interaction, msg: str):
    e = discord.Embed(description=f"> {msg}", color=0xff4444)
    await interaction.followup.send(embed=e, ephemeral=True)

async def ok_msg(interaction: discord.Interaction, msg: str, color=0x57f287):
    e = discord.Embed(description=f"> {msg}", color=color)
    await interaction.followup.send(embed=e, ephemeral=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GEN DROPDOWN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class GenSelect(discord.ui.Select):
    def __init__(self, tier: str):
        self.tier = tier
        cnt = sc("roblox", tier)
        super().__init__(
            placeholder="generate an account  ↓",
            options=[discord.SelectOption(
                label="Roblox",
                value="roblox",
                emoji="🎮",
                description=f"{cnt} accounts in stock")],
            custom_id=f"gs_{tier}",
            min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        tier = self.tier

        # always get from cache — REST strips activities
        member = interaction.guild.get_member(interaction.user.id)
        if not member:
            await err(interaction, "Couldn't find you in cache. Try again in a moment.")
            return

        # ── checks ────────────────────────────────────────────────────────
        if tier == "free":
            mr = interaction.guild.get_role(ROLE_MEMBER)
            if mr and mr not in member.roles:
                await err(interaction, "You need the **Member** role to use free gen.")
                return
            # STATUS CHECK DISABLED — re-enable when ready
            # if not has_status(member):
            #     await err(interaction,
            #         f"Your Discord **custom status** must contain `{REQUIRED_STATUS}`\n\n"
            #         f"**How to set it:**\n"
            #         f"Click your avatar → **Set Custom Status** → type `{REQUIRED_STATUS}`\n\n"
            #         f"Already set it? Use `/checkstatus` to verify the bot can see it.")
            #     return

        elif tier == "premium":
            pr = interaction.guild.get_role(ROLE_PREMIUM)
            if pr and pr not in member.roles:
                await err(interaction, f"You need **Premium** to use this.\n> Purchase in <#{PREM_BUY_CHANNEL}>")
                return

        elif tier == "booster":
            if not member.premium_since:
                await err(interaction, "You must be a **Server Booster** to use this.")
                return

        # ── cooldown ───────────────────────────────────────────────────────
        rem = get_cooldown(tier, member.id)
        if rem:
            await err(interaction, f"You're on cooldown for **{fmt(rem)}**\n> {tier.capitalize()} cooldown resets every {TIER_CD[tier]}")
            return

        # ── stock ──────────────────────────────────────────────────────────
        account = spop("roblox", tier)
        if not account:
            await err(interaction, "No stock available for your tier right now.\n> Wait for a restock ping!")
            return

        set_cooldown(tier, member.id)

        parts    = account.split(":", 1)
        username = parts[0]
        password = parts[1] if len(parts) > 1 else "N/A"

        # ── DM embed ───────────────────────────────────────────────────────
        dm = discord.Embed(color=TIER_COLOR[tier])
        dm.set_author(name=f"{TIER_ICON[tier]}  your generated roblox account",
                      icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        dm.description = f"-# looking for better accounts? upgrade to **premium** today"
        dm.add_field(name="username", value=f"```{username}```", inline=False)
        dm.add_field(name="password", value=f"```{password}```", inline=False)
        dm.add_field(name="combo",    value=f"```{account}```",  inline=False)
        dm.set_footer(text=f"Mercyy Gen  •  next gen in {TIER_CD[tier]}")

        try:
            await member.send(embed=dm)
            conf = discord.Embed(color=TIER_COLOR[tier])
            conf.set_author(name="account sent to your DMs ✓")
            conf.description = f"-# next generation available in **{TIER_CD[tier]}**"
            await interaction.followup.send(embed=conf, ephemeral=True)
        except discord.Forbidden:
            dm.set_footer(text=f"⚠️  DMs closed — showing here  •  next gen in {TIER_CD[tier]}")
            await interaction.followup.send(embed=dm, ephemeral=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GEN PANEL VIEW
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class GenView(discord.ui.View):
    def __init__(self, tier: str):
        super().__init__(timeout=None)
        self.tier = tier
        self.add_item(GenSelect(tier))

    @discord.ui.button(label="upgrade", emoji="⬆️",
                       style=discord.ButtonStyle.secondary, custom_id="gv_upgrade")
    async def upgrade(self, i: discord.Interaction, _: discord.ui.Button):
        e = discord.Embed(color=0xf5c518)
        e.set_author(name="upgrade to premium")
        e.description = (f"**12h cooldown**  ·  priority stock  ·  premium-only accounts\n\n"
                         f"-# CashApp `{CASHAPP_TAG}`  •  <#{PREM_BUY_CHANNEL}>")
        await i.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="stock", emoji="📦",
                       style=discord.ButtonStyle.secondary, custom_id="gv_stock")
    async def stock_btn(self, i: discord.Interaction, _: discord.ui.Button):
        e = discord.Embed(title="stock", color=0x2b2d31)
        e.add_field(name="🆓  free",    value=f"`{sc('roblox','free')}`",    inline=True)
        e.add_field(name="⭐  premium", value=f"`{sc('roblox','premium')}`", inline=True)
        e.add_field(name="⚡  booster", value=f"`{sc('roblox','booster')}`", inline=True)
        await i.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="guide", emoji="❓",
                       style=discord.ButtonStyle.secondary, custom_id="gv_guide")
    async def guide(self, i: discord.Interaction, _: discord.ui.Button):
        e = discord.Embed(color=0x5865f2)
        e.set_author(name="login guide")
        e.description = ("1. Copy the credentials from your DM\n"
                         "2. Log into roblox.com\n"
                         "3. Change the password immediately\n"
                         "4. Don't share the account\n\n"
                         "-# Accounts are first-come-first-served")
        await i.response.send_message(embed=e, ephemeral=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TICKET VIEWS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="open a ticket", emoji="🎫",
                       style=discord.ButtonStyle.danger, custom_id="tv_open")
    async def open_ticket(self, i: discord.Interaction, _: discord.ui.Button):
        g  = i.guild
        m  = i.user
        ch_name = f"ticket-{m.name.lower()[:18].replace(' ', '-')}"
        if discord.utils.get(g.text_channels, name=ch_name):
            await i.response.send_message("> You already have an open ticket!", ephemeral=True)
            return
        ow = {
            g.default_role: discord.PermissionOverwrite(read_messages=False),
            m: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        pr = g.get_role(ROLE_PREMIUM)
        if pr:
            ow[pr] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        ch = await g.create_text_channel(ch_name, overwrites=ow, category=i.channel.category)
        e = discord.Embed(color=0x2b2d31)
        e.set_author(name="support ticket")
        e.description = (f"welcome {m.mention} — describe your issue below\n\n"
                         f"💎  **premium** → CashApp `{CASHAPP_TAG}`\n"
                         f"⚡  **booster** → boost the server\n\n"
                         f"-# staff will be with you shortly")
        await ch.send(embed=e, view=CloseView())
        await i.response.send_message(f"> ticket created → {ch.mention}", ephemeral=True)


class CloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="close ticket", emoji="🔒",
                       style=discord.ButtonStyle.danger, custom_id="cv_close")
    async def close(self, i: discord.Interaction, _: discord.ui.Button):
        await i.response.send_message("> closing in 5 seconds…")
        await asyncio.sleep(5)
        await i.channel.delete()


class PurchaseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="purchase", emoji="💳",
                       style=discord.ButtonStyle.success, custom_id="pv_buy")
    async def buy(self, i: discord.Interaction, _: discord.ui.Button):
        e = discord.Embed(color=0xf5c518)
        e.set_author(name="purchase premium")
        e.description = (f"**CashApp:** `{CASHAPP_TAG}`\n\n"
                         "1. send payment\n"
                         "2. screenshot proof\n"
                         "3. open a ticket\n"
                         "4. receive role within 24h")
        await i.response.send_message(embed=e, ephemeral=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  EVENTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@bot.event
async def on_ready():
    print(f"✅  {bot.user}  online")
    for t in ("free", "premium", "booster"):
        bot.add_view(GenView(t))
    bot.add_view(TicketView())
    bot.add_view(CloseView())
    bot.add_view(PurchaseView())
    try:
        s = await bot.tree.sync()
        print(f"✅  synced {len(s)} commands")
    except Exception as ex:
        print(f"❌  sync error: {ex}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SLASH COMMANDS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# /checkstatus — clean, just tells them yes or no
@bot.tree.command(name="checkstatus", description="Check if your status is set correctly")
async def checkstatus(interaction: discord.Interaction):
    member = interaction.guild.get_member(interaction.user.id)
    if not member:
        await interaction.response.send_message(
            embed=discord.Embed(description="> couldn't read your status — try again in a moment", color=0xff4444),
            ephemeral=True)
        return

    detected = has_status(member)

    if detected:
        e = discord.Embed(color=0x57f287)
        e.set_author(name="status verified ✓")
        e.description = f"-# `{REQUIRED_STATUS}` detected — you're good to gen!"
    else:
        # show what was actually found without being harsh
        custom = next((a for a in member.activities if isinstance(a, discord.CustomActivity)), None)
        current = f"`{custom.name}`" if custom and custom.name else "`(none set)`"
        e = discord.Embed(color=0xff4444)
        e.set_author(name="status not found")
        e.description = (
            f"your current status: {current}\n\n"
            f"**needs to contain:** `{REQUIRED_STATUS}`\n\n"
            f"click your avatar → **Set Custom Status** → type `{REQUIRED_STATUS}`\n"
            f"-# run `/checkstatus` again after setting it")

    await interaction.response.send_message(embed=e, ephemeral=True)


# /setup_gen
@bot.tree.command(name="setup_gen", description="Post a gen panel (Admin)")
@app_commands.describe(tier="free / premium / booster")
@app_commands.choices(tier=[
    app_commands.Choice(name="Free",    value="free"),
    app_commands.Choice(name="Premium", value="premium"),
    app_commands.Choice(name="Booster", value="booster"),
])
@app_commands.checks.has_permissions(administrator=True)
async def setup_gen(interaction: discord.Interaction, tier: app_commands.Choice[str]):
    t   = tier.value
    cnt = sc("roblox", t)
    icon_url = interaction.guild.icon.url if interaction.guild.icon else None

    extras = {
        "free":    f"-# must have `{REQUIRED_STATUS}` in your custom status",
        "premium": f"-# requires <@&{ROLE_PREMIUM}>  ·  purchase in <#{PREM_BUY_CHANNEL}>",
        "booster": f"-# server boosters only  ·  <#{BOOST_BUY_CHANNEL}>",
    }

    e = discord.Embed(color=TIER_COLOR[t])
    e.set_author(name=f"mercyy gen  ·  {t} generator", icon_url=icon_url)
    e.description = (
        f"### {TIER_ICON[t]}  {t} generator\n"
        f"> use the dropdown below to generate an account\n\n"
        f"**stocks**\n`🎮  roblox  —  {cnt} accounts`\n\n"
        f"**cooldown**\n`⏱️  {TIER_CD[t]} between generations`\n\n"
        f"**access**\n{extras[t]}"
    )
    e.set_footer(text="Mercyy Gen")
    await interaction.channel.send(embed=e, view=GenView(t))
    await interaction.response.send_message("> gen panel posted!", ephemeral=True)


# /restock
@bot.tree.command(name="restock", description="Restock accounts (Admin)")
@app_commands.describe(tier="Tier to restock", service="Service", file=".txt — one account per line")
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
        await interaction.followup.send("> ❌  upload a `.txt` file", ephemeral=True)
        return
    raw  = (await file.read()).decode("utf-8", errors="ignore")
    new  = [l.strip() for l in raw.splitlines() if l.strip()]
    if not new:
        await interaction.followup.send("> ❌  file is empty", ephemeral=True)
        return
    sadd(service.value, tier.value, new)
    total = sc(service.value, tier.value)

    ch = bot.get_channel(RESTOCK_CHANNEL)
    if ch:
        rr   = interaction.guild.get_role(ROLE_RESTOCK)
        ping = rr.mention if rr else ""
        re   = discord.Embed(color=TIER_COLOR[tier.value])
        re.set_author(name="restock", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        re.description = (f"**{TIER_ICON[tier.value]}  {tier.name} roblox** has been restocked\n\n"
                          f"`+{len(new)} added  ·  {total} total`")
        re.set_footer(text="Mercyy Gen")
        await ch.send(content=ping, embed=re)

    await interaction.followup.send(
        f"> ✅  added `{len(new)}` to **{tier.name} roblox**  ·  `{total}` total",
        ephemeral=True)


# /stock
@bot.tree.command(name="stock", description="View current stock counts")
async def stock_cmd(interaction: discord.Interaction):
    e = discord.Embed(color=0x2b2d31)
    e.set_author(name="stock")
    e.add_field(name="🆓  free",    value=f"`{sc('roblox','free')}` accs",    inline=True)
    e.add_field(name="⭐  premium", value=f"`{sc('roblox','premium')}` accs", inline=True)
    e.add_field(name="⚡  booster", value=f"`{sc('roblox','booster')}` accs", inline=True)
    e.set_footer(text="Mercyy Gen")
    await interaction.response.send_message(embed=e, ephemeral=True)


# /cooldown
@bot.tree.command(name="cooldown", description="Check your cooldowns")
async def cooldown_cmd(interaction: discord.Interaction):
    uid   = interaction.user.id
    lines = []
    for t in ("free", "premium", "booster"):
        rem = get_cooldown(t, uid)
        if rem:
            lines.append(f"{TIER_ICON[t]}  **{t}** — `{fmt(rem)}` remaining")
        else:
            lines.append(f"{TIER_ICON[t]}  **{t}** — `ready`")
    e = discord.Embed(color=0x5865f2)
    e.set_author(name="your cooldowns")
    e.description = "\n".join(lines)
    await interaction.response.send_message(embed=e, ephemeral=True)


# /reset_cooldown
@bot.tree.command(name="reset_cooldown", description="Reset a user's cooldown (Admin)")
@app_commands.describe(member="User", tier="Tier")
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
        cooldown_store[t].pop(member.id, None)
    await interaction.response.send_message(
        f"> ✅  reset **{tier.name}** cooldown for {member.mention}", ephemeral=True)


# /setup_reaction_roles
@bot.tree.command(name="setup_reaction_roles", description="Post reaction role panel (Admin)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_rr(interaction: discord.Interaction):
    e = discord.Embed(color=0x2b2d31)
    e.set_author(name="notification roles",
                 icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
    e.description = (
        "\n".join(f"{emoji}  —  **{label}**" for emoji, _, label in RR) +
        "\n\n-# react to get a role  ·  react again to remove it"
    )
    msg = await interaction.channel.send(embed=e)
    for emoji, _, _ in RR:
        await msg.add_reaction(emoji)
    bot.rr_id = msg.id
    await interaction.response.send_message(
        f"> ✅  posted  ·  save this id: `{msg.id}`", ephemeral=True)


# /set_rr_message
@bot.tree.command(name="set_rr_message", description="Re-link reaction roles after restart (Admin)")
@app_commands.describe(message_id="Message ID of the reaction role panel")
@app_commands.checks.has_permissions(administrator=True)
async def set_rr(interaction: discord.Interaction, message_id: str):
    try:
        bot.rr_id = int(message_id)
        await interaction.response.send_message(f"> ✅  linked to `{message_id}`", ephemeral=True)
    except ValueError:
        await interaction.response.send_message("> ❌  invalid id", ephemeral=True)


# /setup_tickets
@bot.tree.command(name="setup_tickets", description="Post ticket panel (Admin)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_tickets(interaction: discord.Interaction):
    e = discord.Embed(color=0xed4245)
    e.set_author(name="support & purchases",
                 icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
    e.description = (f"open a ticket for support or to purchase\n\n"
                     f"💎  **premium** → CashApp `{CASHAPP_TAG}`\n"
                     f"⚡  **booster** → boost the server\n\n"
                     f"-# a staff member will assist you shortly")
    await interaction.channel.send(embed=e, view=TicketView())
    await interaction.response.send_message("> ✅  posted!", ephemeral=True)


# /setup_purchase
@bot.tree.command(name="setup_purchase", description="Post purchase panel (Admin)")
@app_commands.describe(product="premium or booster")
@app_commands.choices(product=[
    app_commands.Choice(name="Premium", value="premium"),
    app_commands.Choice(name="Booster", value="booster"),
])
@app_commands.checks.has_permissions(administrator=True)
async def setup_purchase(interaction: discord.Interaction, product: app_commands.Choice[str]):
    if product.value == "booster":
        tiers_text = "\n".join(
            f"`{b} boost{'s' if b > 1 else ''}`  →  **{l}** access"
            for b, l in BOOST_TIERS.items())
        e = discord.Embed(color=0xff73fa)
        e.set_author(name="booster generator access",
                     icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        e.description = (f"boost the server to unlock the booster generator\n\n"
                         f"**boost tiers**\n{tiers_text}\n\n"
                         f"-# access is granted automatically when you boost")
        await interaction.channel.send(embed=e)
    else:
        e = discord.Embed(color=0xf5c518)
        e.set_author(name="buy premium",
                     icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        e.description = (f"**what you get**\n"
                         f"`⏱️`  12h cooldown  *(vs 24h free)*\n"
                         f"`📦`  premium-only stock\n"
                         f"`⭐`  priority access\n\n"
                         f"**how to buy**\n"
                         f"send payment to CashApp `{CASHAPP_TAG}` then open a ticket with proof\n\n"
                         f"-# role given within 24 hours of verification")
        await interaction.channel.send(embed=e, view=PurchaseView())
    await interaction.response.send_message("> ✅  posted!", ephemeral=True)


# /clear_stock
@bot.tree.command(name="clear_stock", description="Clear stock (Admin)")
@app_commands.describe(service="Service", tier="Tier")
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


# ── error handler ──────────────────────────────────────────
@bot.tree.error
async def on_err(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        try:
            await interaction.response.send_message(
                embed=discord.Embed(description="> you don't have permission to use this", color=0xff4444),
                ephemeral=True)
        except Exception:
            pass
    else:
        try:
            await interaction.response.send_message(
                embed=discord.Embed(description=f"> something went wrong: `{error}`", color=0xff4444),
                ephemeral=True)
        except Exception:
            pass
        raise error


bot.run(TOKEN)
