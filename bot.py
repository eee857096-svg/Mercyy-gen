import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
import time
from pathlib import Path

# ── Config ───────────────────────────────────────────────────────────────────
REQUIRED_STATUS   = ".gg/VQ3YNgSr"
RESTOCK_CHANNEL   = 1478365146999947368
BOOST_BUY_CHANNEL = 1478365159520079943
PREM_BUY_CHANNEL  = 1478365160476381254

ROLE_PREMIUM  = 1478365092285251586
ROLE_MEMBER   = 1478365093732552847
ROLE_ANNOUNCE = 1478365094504304813
ROLE_RESTOCK  = 1478365095234109592
ROLE_GIVEAWAY = 1478365095909130242
ROLE_DROP     = 1478365097628930049

CASHAPP_TAG = "$ASHZ67"

BOOST_TIERS = {
    1: ("2 Weeks",  14),
    2: ("1 Month",  30),
    4: ("2 Months", 60),
    6: ("3 Months", 90),
}

# ── Cooldowns ─────────────────────────────────────────────────────────────────
COOLDOWNS = {
    "free":    24 * 3600,
    "premium": 12 * 3600,
    "booster":  6 * 3600,
}
cooldown_store = {t: {} for t in COOLDOWNS}

def check_cooldown(tier, user_id):
    last = cooldown_store[tier].get(user_id)
    if last is None:
        return None
    remaining = COOLDOWNS[tier] - (time.monotonic() - last)
    return remaining if remaining > 0 else None

def set_cooldown(tier, user_id):
    cooldown_store[tier][user_id] = time.monotonic()

def fmt_time(seconds):
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s   = divmod(rem, 60)
    parts  = []
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if s or not parts: parts.append(f"{s}s")
    return " ".join(parts)

def has_required_status(activities) -> bool:
    """Robustly check all activity fields for the required status string."""
    needle = REQUIRED_STATUS.lower()
    for act in activities:
        # Check every readable string attribute
        for attr in ("name", "state", "details", "large_image_text", "small_image_text"):
            try:
                val = getattr(act, attr, None)
                if val and needle in str(val).lower():
                    return True
            except Exception:
                pass
        # Fallback: stringify entire object
        try:
            if needle in str(act).lower():
                return True
        except Exception:
            pass
    return False

TOKEN = os.environ["TOKEN"]

# ── Bot setup ─────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ── Stock storage — separate files per tier ───────────────────────────────────
STOCK_DIR = Path("stock")
STOCK_DIR.mkdir(exist_ok=True)

def stock_file(service, tier="free"):
    # free uses roblox.txt, premium uses roblox_premium.txt, booster uses roblox_booster.txt
    if tier == "free":
        return STOCK_DIR / f"{service}.txt"
    return STOCK_DIR / f"{service}_{tier}.txt"

def read_stock(service, tier="free"):
    f = stock_file(service, tier)
    if not f.exists():
        return []
    return [l.strip() for l in f.read_text().splitlines() if l.strip()]

def pop_account(service, tier="free"):
    lines = read_stock(service, tier)
    if not lines:
        # fallback: try free stock if premium/booster empty
        if tier != "free":
            lines = read_stock(service, "free")
            if lines:
                account = lines[0]
                stock_file(service, "free").write_text("\n".join(lines[1:]))
                return account
        return None
    account = lines[0]
    stock_file(service, tier).write_text("\n".join(lines[1:]))
    return account

def stock_count(service, tier="free"):
    return len(read_stock(service, tier))

def total_stock(service):
    return stock_count(service, "free") + stock_count(service, "premium") + stock_count(service, "booster")

SERVICES = {"roblox": "Roblox"}

# ═════════════════════════════════════════════════════════════════════════════
#  GEN SELECT + PANEL
# ═════════════════════════════════════════════════════════════════════════════

class GenSelect(discord.ui.Select):
    def __init__(self, tier):
        self.tier = tier
        cnt = stock_count("roblox", tier)
        options = [discord.SelectOption(
            label="Roblox", value="roblox", emoji="🎮",
            description=f"{cnt} accounts in stock")]
        super().__init__(
            placeholder="✨ Select a service to generate...",
            options=options,
            custom_id=f"gen_select_{tier}",
            min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        service = self.values[0]
        guild   = interaction.guild

        # Always fetch fresh member for up-to-date presence data
        try:
            member = await guild.fetch_member(interaction.user.id)
        except Exception:
            member = interaction.user

        # ── Free tier checks ──────────────────────────────────────────────
        if self.tier == "free":
            mem_role = guild.get_role(ROLE_MEMBER)
            if mem_role and mem_role not in member.roles:
                embed = discord.Embed(
                    title="❌ Access Denied",
                    description="You need the **Member** role to use the free generator.",
                    color=0xff4444)
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            if not has_required_status(member.activities):
                # Show debug info so user can diagnose
                debug_lines = []
                for act in member.activities:
                    name  = getattr(act, "name",  None)
                    state = getattr(act, "state", None)
                    debug_lines.append(f"`{type(act).__name__}` name=`{name}` state=`{state}`")
                debug_text = "\n".join(debug_lines) if debug_lines else "`No activities detected`"
                embed = discord.Embed(
                    title="❌ Status Not Detected",
                    description=(
                        f"Your custom status must contain `{REQUIRED_STATUS}`\n\n"
                        f"**Bot currently sees:**\n{debug_text}\n\n"
                        f"**Checklist:**\n"
                        f"• Set as **Custom Status** (click smiley → Set Custom Status)\n"
                        f"• Status must **not** be hidden in privacy settings\n"
                        f"• Set the status **before** clicking generate\n"
                        f"• Run `/checkstatus` to verify"),
                    color=0xff4444)
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

        # ── Premium tier checks ───────────────────────────────────────────
        elif self.tier == "premium":
            prem_role = guild.get_role(ROLE_PREMIUM)
            if prem_role and prem_role not in member.roles:
                embed = discord.Embed(
                    title="❌ Premium Required",
                    description=f"You need **Premium** to use this generator.\n\n💳 Purchase in <#{PREM_BUY_CHANNEL}>",
                    color=0xff4444)
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

        # ── Booster tier checks ───────────────────────────────────────────
        elif self.tier == "booster":
            if not member.premium_since:
                embed = discord.Embed(
                    title="❌ Booster Required",
                    description="You must be a **Server Booster** to use this generator.\n\nBoost the server to unlock access!",
                    color=0xff4444)
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

        # ── Cooldown check ────────────────────────────────────────────────
        remaining = check_cooldown(self.tier, member.id)
        if remaining is not None:
            cd_display = {"free": "24h", "premium": "12h", "booster": "6h"}
            embed = discord.Embed(
                title="⏳ Cooldown Active",
                description=(
                    f"You can generate again in **{fmt_time(remaining)}**\n"
                    f"*{self.tier.capitalize()} cooldown: {cd_display[self.tier]}*"),
                color=0xffaa00)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # ── Pull account from tier-specific stock ─────────────────────────
        account = pop_account(service, self.tier)
        if account is None:
            embed = discord.Embed(
                title="⚠️ Out of Stock",
                description=(
                    f"**{SERVICES[service]}** is currently out of stock for your tier.\n"
                    "Check back soon or wait for a restock ping!"),
                color=0xffaa00)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        set_cooldown(self.tier, member.id)

        parts    = account.split(":")
        username = parts[0] if len(parts) > 0 else account
        password = parts[1] if len(parts) > 1 else "N/A"
        combo    = account

        tier_colors = {"free": 0x57f287, "premium": 0xf5c518, "booster": 0xff73fa}
        tier_icons  = {"free": "🆓", "premium": "⭐", "booster": "⚡"}
        cd_display  = {"free": "24h", "premium": "12h", "booster": "6h"}

        dm_embed = discord.Embed(
            title=f"{tier_icons[self.tier]} your generated {SERVICES[service].lower()} account",
            color=tier_colors[self.tier])
        dm_embed.description = "> are you looking for better accounts? upgrade to **premium** today"
        dm_embed.add_field(name="[ username ]", value=f"```{username}```", inline=False)
        dm_embed.add_field(name="[ password ]", value=f"```{password}```", inline=False)
        dm_embed.add_field(name="[ combo ]",    value=f"```{combo}```",    inline=False)
        dm_embed.set_footer(text=f"Mercyy Gen • Next gen in {cd_display[self.tier]}")

        try:
            await member.send(embed=dm_embed)
            confirm = discord.Embed(
                title="✅ Account Sent!",
                description="Your account has been sent to your **DMs**!\n\n*Make sure your DMs are open for future gens.*",
                color=tier_colors[self.tier])
            confirm.set_footer(text=f"Mercyy Gen • Next gen in {cd_display[self.tier]}")
            await interaction.followup.send(embed=confirm, ephemeral=True)
        except discord.Forbidden:
            dm_embed.set_footer(text=f"⚠️ Could not DM you — showing here instead. Open your DMs next time. Next gen in {cd_display[self.tier]}")
            await interaction.followup.send(embed=dm_embed, ephemeral=True)


class GenPanelView(discord.ui.View):
    def __init__(self, tier):
        super().__init__(timeout=None)
        self.add_item(GenSelect(tier))

    @discord.ui.button(label="upgrade", style=discord.ButtonStyle.secondary,
                       emoji="⬆️", custom_id="btn_upgrade_gen")
    async def upgrade_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="💎 Upgrade to Premium",
            description=(
                f"Unlock **12h cooldown**, priority stock & more!\n\n"
                f"💳 CashApp: `{CASHAPP_TAG}`\n"
                f"Open a ticket in <#{PREM_BUY_CHANNEL}>"),
            color=0xf5c518)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="stock", style=discord.ButtonStyle.secondary,
                       emoji="📦", custom_id="btn_stock_gen")
    async def stock_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="📦 Current Stock", color=0x2b2d31)
        embed.add_field(name="🆓 Free Roblox",    value=f"`{stock_count('roblox', 'free')}` accounts",    inline=True)
        embed.add_field(name="⭐ Premium Roblox", value=f"`{stock_count('roblox', 'premium')}` accounts", inline=True)
        embed.add_field(name="⚡ Booster Roblox", value=f"`{stock_count('roblox', 'booster')}` accounts", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="login guide", style=discord.ButtonStyle.secondary,
                       emoji="❓", custom_id="btn_guide_gen")
    async def guide_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="❓ Login Guide",
            description=(
                "**How to use your generated account:**\n\n"
                "1. Copy the username & password from your DM\n"
                "2. Log into the platform\n"
                "3. Change email/password immediately\n"
                "4. Do **not** share the account\n\n"
                "⚠️ Accounts are first-come-first-served. If it doesn't work it may already be claimed."),
            color=0x5865f2)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ═════════════════════════════════════════════════════════════════════════════
#  REACTION ROLES
# ═════════════════════════════════════════════════════════════════════════════

REACTION_ROLES = [
    ("🔥", ROLE_DROP,     "Drop Ping"),
    ("📢", ROLE_ANNOUNCE, "Announcement Ping"),
    ("✅", ROLE_GIVEAWAY, "Giveaway Ping"),
    ("👑", ROLE_RESTOCK,  "Restock Ping"),
]

@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.member and payload.member.bot:
        return
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    rr_msg_id = getattr(bot, "rr_message_id", None)
    if rr_msg_id and payload.message_id != rr_msg_id:
        return
    emoji_str = str(payload.emoji)
    for emoji, role_id, _ in REACTION_ROLES:
        if emoji_str == emoji:
            role = guild.get_role(role_id)
            if role:
                member = payload.member or guild.get_member(payload.user_id)
                if member:
                    await member.add_roles(role)
            break

@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    rr_msg_id = getattr(bot, "rr_message_id", None)
    if rr_msg_id and payload.message_id != rr_msg_id:
        return
    emoji_str = str(payload.emoji)
    for emoji, role_id, _ in REACTION_ROLES:
        if emoji_str == emoji:
            role = guild.get_role(role_id)
            if role:
                member = guild.get_member(payload.user_id)
                if member:
                    await member.remove_roles(role)
            break


# ═════════════════════════════════════════════════════════════════════════════
#  TICKET VIEWS
# ═════════════════════════════════════════════════════════════════════════════

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Ticket", style=discord.ButtonStyle.danger,
                       emoji="🎫", custom_id="ticket_open")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild  = interaction.guild
        member = interaction.user
        safe_name = member.name.lower().replace(" ", "-")[:20]
        existing  = discord.utils.get(guild.text_channels, name=f"ticket-{safe_name}")
        if existing:
            await interaction.response.send_message(
                f"You already have an open ticket: {existing.mention}", ephemeral=True)
            return
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        r = guild.get_role(ROLE_PREMIUM)
        if r:
            overwrites[r] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        channel = await guild.create_text_channel(
            f"ticket-{safe_name}", overwrites=overwrites,
            category=interaction.channel.category)
        embed = discord.Embed(
            title="🎫 Support Ticket",
            description=(
                f"Welcome {member.mention}!\n\n"
                "Describe your issue or purchase request below.\n\n"
                f"💎 **Buy Premium** → CashApp: `{CASHAPP_TAG}`\n"
                f"⚡ **Booster Access** → Boost the server!\n\n"
                "Staff will assist you shortly."),
            color=0x2b2d31)
        await channel.send(embed=embed, view=CloseTicketView())
        await interaction.response.send_message(
            f"✅ Ticket created: {channel.mention}", ephemeral=True)


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger,
                       emoji="🔒", custom_id="ticket_close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔒 Closing ticket in 5 seconds...")
        await asyncio.sleep(5)
        await interaction.channel.delete()


class PurchaseView(discord.ui.View):
    def __init__(self, product):
        super().__init__(timeout=None)
        self.product = product

    @discord.ui.button(label="Purchase", style=discord.ButtonStyle.success,
                       emoji="💳", custom_id="purchase_btn")
    async def purchase(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title=f"💳 Purchase {self.product}",
            description=(
                f"**Payment:** CashApp only → `{CASHAPP_TAG}`\n\n"
                "**Steps:**\n"
                "1. Send payment via CashApp\n"
                "2. Screenshot your payment\n"
                "3. Open a ticket & send proof\n"
                "4. Receive your role within 24h"),
            color=0xf5c518)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ═════════════════════════════════════════════════════════════════════════════
#  EVENTS
# ═════════════════════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    print(f"✅  Mercyy Gen online as {bot.user}")
    bot.add_view(GenPanelView("free"))
    bot.add_view(GenPanelView("premium"))
    bot.add_view(GenPanelView("booster"))
    bot.add_view(TicketView())
    bot.add_view(CloseTicketView())
    bot.add_view(PurchaseView("Premium"))
    bot.add_view(PurchaseView("Booster"))
    try:
        synced = await bot.tree.sync()
        print(f"✅  Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌  Sync error: {e}")


# ═════════════════════════════════════════════════════════════════════════════
#  SLASH COMMANDS
# ═════════════════════════════════════════════════════════════════════════════

@bot.tree.command(name="checkstatus", description="See exactly what the bot detects in your status")
async def check_status(interaction: discord.Interaction):
    try:
        member = await interaction.guild.fetch_member(interaction.user.id)
    except Exception:
        member = interaction.user
    lines = []
    if not member.activities:
        lines.append("`No activities detected`\nEnsure Presence Intent is enabled in the Dev Portal.")
    for act in member.activities:
        name  = getattr(act, "name",  None)
        state = getattr(act, "state", None)
        lines.append(f"**{type(act).__name__}**\n• name: `{name}`\n• state: `{state}`")
    detected = has_required_status(member.activities)
    embed = discord.Embed(
        title="🔍 Status Debug",
        description="\n\n".join(lines) if lines else "`Nothing detected`",
        color=0x57f287 if detected else 0xff4444)
    embed.add_field(name="Required String", value=f"`{REQUIRED_STATUS}`", inline=True)
    embed.add_field(name="Detected?", value="✅ Yes — you can gen!" if detected else "❌ No", inline=True)
    embed.set_footer(text="If nothing shows, check Presence Intent in the Discord Developer Portal")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="setup_gen", description="Post a gen panel (Admin only)")
@app_commands.describe(tier="free / premium / booster")
@app_commands.choices(tier=[
    app_commands.Choice(name="free",    value="free"),
    app_commands.Choice(name="premium", value="premium"),
    app_commands.Choice(name="booster", value="booster"),
])
@app_commands.checks.has_permissions(administrator=True)
async def setup_gen(interaction: discord.Interaction, tier: app_commands.Choice[str]):
    t = tier.value
    colours = {"free": 0x57f287, "premium": 0xf5c518, "booster": 0xff73fa}
    icons   = {"free": "🆓", "premium": "⭐", "booster": "⚡"}
    cd_info = {"free": "24 hours", "premium": "12 hours", "booster": "6 hours"}
    descs = {
        "free": (
            f"**{icons['free']} free generator**\n"
            f"> looking for more? upgrade to **premium** today\n\n"
            f"**📦 stocks**\n`Roblox — {stock_count('roblox', 'free')} accounts`\n\n"
            f"**🛡️ safety**\nAll generated accounts are secured\n\n"
            f"**⭐ accounts**\nAll checked before restocking\n\n"
            f"**⏱️ cooldown**\n`{cd_info['free']}` between generations\n\n"
            f"**⚠️ requirement**\nMust have `{REQUIRED_STATUS}` in your custom status"
        ),
        "premium": (
            f"**{icons['premium']} premium generator**\n"
            f"> enjoying premium? check out our **booster** perks\n\n"
            f"**📦 stocks**\n`Roblox — {stock_count('roblox', 'premium')} accounts`\n\n"
            f"**🛡️ safety**\nAll generated accounts are secured\n\n"
            f"**⭐ accounts**\n100% full access, checked before restocking\n\n"
            f"**⏱️ cooldown**\n`{cd_info['premium']}` between generations\n\n"
            f"**💰 pricing**\nPurchase in <#{PREM_BUY_CHANNEL}>"
        ),
        "booster": (
            f"**{icons['booster']} booster generator**\n"
            f"> thank you for supporting the server!\n\n"
            f"**📦 stocks**\n`Roblox — {stock_count('roblox', 'booster')} accounts`\n\n"
            f"**🛡️ safety**\nAll generated accounts are secured\n\n"
            f"**⭐ accounts**\nExclusive stock, checked before restocking\n\n"
            f"**⏱️ cooldown**\n`{cd_info['booster']}` between generations\n\n"
            f"**⚡ access**\nBoost the server to unlock!"
        ),
    }
    embed = discord.Embed(description=descs[t], color=colours[t])
    embed.set_author(
        name=f"Mercyy Gen — {t.capitalize()} Generator",
        icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.set_footer(text="Mercyy Gen • Roblox accounts only")
    await interaction.channel.send(embed=embed, view=GenPanelView(t))
    await interaction.response.send_message("✅ Gen panel posted!", ephemeral=True)


@bot.tree.command(name="restock", description="Restock accounts from a .txt file (Admin only)")
@app_commands.describe(
    service="Service to restock",
    tier="Which gen tier to restock",
    file="Text file — one account per line (user:pass or email:pass)")
@app_commands.choices(
    service=[app_commands.Choice(name="Roblox", value="roblox")],
    tier=[
        app_commands.Choice(name="Free",    value="free"),
        app_commands.Choice(name="Premium", value="premium"),
        app_commands.Choice(name="Booster", value="booster"),
    ])
@app_commands.checks.has_permissions(administrator=True)
async def restock(interaction: discord.Interaction,
                  service: app_commands.Choice[str],
                  tier: app_commands.Choice[str],
                  file: discord.Attachment):
    await interaction.response.defer(ephemeral=True)
    if not file.filename.endswith(".txt"):
        await interaction.followup.send("❌ Please upload a `.txt` file.", ephemeral=True)
        return
    content = (await file.read()).decode("utf-8", errors="ignore")
    new_accounts = [l.strip() for l in content.splitlines() if l.strip()]
    if not new_accounts:
        await interaction.followup.send("❌ File is empty or invalid.", ephemeral=True)
        return
    existing = read_stock(service.value, tier.value)
    combined = existing + new_accounts
    stock_file(service.value, tier.value).write_text("\n".join(combined))
    count = len(new_accounts)
    total = len(combined)

    tier_icons = {"free": "🆓", "premium": "⭐", "booster": "⚡"}

    restock_ch = bot.get_channel(RESTOCK_CHANNEL)
    if restock_ch:
        restock_role = interaction.guild.get_role(ROLE_RESTOCK)
        ping = restock_role.mention if restock_role else ""
        embed = discord.Embed(
            title="🔄 Restock!",
            description=(
                f"{tier_icons[tier.value]} **{tier.name} {service.name}** has been restocked!\n\n"
                f"➕ **Added:** `{count}` accounts\n"
                f"📦 **Total Stock:** `{total}` accounts"),
            color=0x57f287)
        embed.set_footer(text="Mercyy Gen")
        await restock_ch.send(content=ping, embed=embed)

    await interaction.followup.send(
        f"✅ Restocked **{tier.name} {service.name}** with `{count}` accounts. Total: `{total}`",
        ephemeral=True)


@bot.tree.command(name="stock", description="View current stock counts")
async def stock_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="📦 Mercyy Gen — Stock", color=0x2b2d31)
    embed.add_field(name="🆓 Free Roblox",    value=f"`{stock_count('roblox', 'free')}` accounts",    inline=True)
    embed.add_field(name="⭐ Premium Roblox", value=f"`{stock_count('roblox', 'premium')}` accounts", inline=True)
    embed.add_field(name="⚡ Booster Roblox", value=f"`{stock_count('roblox', 'booster')}` accounts", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="cooldown", description="Check your remaining cooldowns")
async def cooldown_cmd(interaction: discord.Interaction):
    lines = []
    for tier in ("free", "premium", "booster"):
        rem = check_cooldown(tier, interaction.user.id)
        lines.append(
            f"**{tier.capitalize()}:** ⏳ `{fmt_time(rem)}` remaining"
            if rem else f"**{tier.capitalize()}:** ✅ Ready")
    embed = discord.Embed(title="⏱️ Your Cooldowns", description="\n".join(lines), color=0x5865f2)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="reset_cooldown", description="Reset a user's cooldown (Admin only)")
@app_commands.describe(member="The user to reset", tier="Which tier to reset")
@app_commands.choices(tier=[
    app_commands.Choice(name="free",    value="free"),
    app_commands.Choice(name="premium", value="premium"),
    app_commands.Choice(name="booster", value="booster"),
    app_commands.Choice(name="all",     value="all"),
])
@app_commands.checks.has_permissions(administrator=True)
async def reset_cooldown(interaction: discord.Interaction,
                         member: discord.Member,
                         tier: app_commands.Choice[str]):
    if tier.value == "all":
        for t in COOLDOWNS:
            cooldown_store[t].pop(member.id, None)
        await interaction.response.send_message(
            f"✅ Reset **all** cooldowns for {member.mention}.", ephemeral=True)
    else:
        cooldown_store[tier.value].pop(member.id, None)
        await interaction.response.send_message(
            f"✅ Reset **{tier.value}** cooldown for {member.mention}.", ephemeral=True)


@bot.tree.command(name="setup_reaction_roles", description="Post reaction role panel (Admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_rr(interaction: discord.Interaction):
    lines = "\n".join([f"{emoji} — **{label}**" for emoji, _, label in REACTION_ROLES])
    embed = discord.Embed(
        title="Get Your Role To Get Notified About",
        description=(
            f"{lines}\n\n"
            "React with the emoji to get the role!\n"
            "React or unreact to add/remove roles"),
        color=0x2b2d31)
    msg = await interaction.channel.send(embed=embed)
    for emoji, _, _ in REACTION_ROLES:
        await msg.add_reaction(emoji)
    bot.rr_message_id = msg.id
    await interaction.response.send_message(
        f"✅ Reaction roles posted! Message ID: `{msg.id}`", ephemeral=True)


@bot.tree.command(name="set_rr_message", description="Reconnect reaction roles to existing message (Admin only)")
@app_commands.describe(message_id="The message ID of the reaction role panel")
@app_commands.checks.has_permissions(administrator=True)
async def set_rr_message(interaction: discord.Interaction, message_id: str):
    try:
        bot.rr_message_id = int(message_id)
        await interaction.response.send_message(
            f"✅ Reaction role message set to `{message_id}`", ephemeral=True)
    except ValueError:
        await interaction.response.send_message("❌ Invalid message ID.", ephemeral=True)


@bot.tree.command(name="setup_tickets", description="Post the ticket panel (Admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_tickets(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎫 Support Tickets",
        description=(
            "Need help or want to purchase?\n"
            "Click below to open a private ticket!\n\n"
            f"💎 **Buy Premium** → CashApp: `{CASHAPP_TAG}`\n"
            f"⚡ **Booster Access** → Boost the server!"),
        color=0xed4245)
    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message("✅ Ticket panel posted!", ephemeral=True)


@bot.tree.command(name="setup_purchase", description="Post purchase panel (Admin only)")
@app_commands.describe(product="premium or booster")
@app_commands.choices(product=[
    app_commands.Choice(name="Premium", value="Premium"),
    app_commands.Choice(name="Booster", value="Booster"),
])
@app_commands.checks.has_permissions(administrator=True)
async def setup_purchase(interaction: discord.Interaction, product: app_commands.Choice[str]):
    if product.value == "Booster":
        tiers_text = "\n".join([
            f"**{boosts} boost{'s' if boosts > 1 else ''}** → `{label}` access"
            for boosts, (label, _) in BOOST_TIERS.items()])
        embed = discord.Embed(
            title="⚡ Booster Generator Access",
            description=(
                f"Boost the server to unlock the **Booster Generator**!\n\n"
                f"**Boost Tiers:**\n{tiers_text}\n\n"
                f"Simply boost and your access is granted automatically.\n"
                f"Open a ticket if you need help!"),
            color=0xff73fa)
        await interaction.channel.send(embed=embed)
    else:
        embed = discord.Embed(
            title="💎 Buy Premium",
            description=(
                f"**Payment:** CashApp only → `{CASHAPP_TAG}`\n\n"
                "**Steps:**\n"
                "1. Send payment via CashApp\n"
                "2. Screenshot your payment\n"
                "3. Open a ticket & send proof\n"
                "4. Receive your role within 24h\n\n"
                "**Perks:**\n"
                "⭐ 12h cooldown (vs 24h free)\n"
                "⭐ Priority stock access\n"
                "⭐ Premium-only services"),
            color=0xf5c518)
        await interaction.channel.send(embed=embed, view=PurchaseView(product.value))
    await interaction.response.send_message("✅ Purchase panel posted!", ephemeral=True)


@bot.tree.command(name="clear_stock", description="Clear stock for a service and tier (Admin only)")
@app_commands.describe(service="Service to clear", tier="Tier to clear")
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
    if tier.value == "all":
        for t in ("free", "premium", "booster"):
            stock_file(service.value, t).write_text("")
        await interaction.response.send_message(
            f"✅ Cleared **all tiers** of **{service.name}** stock.", ephemeral=True)
    else:
        stock_file(service.value, tier.value).write_text("")
        await interaction.response.send_message(
            f"✅ Cleared **{tier.name} {service.name}** stock.", ephemeral=True)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
    else:
        try:
            await interaction.response.send_message(f"❌ Error: {error}", ephemeral=True)
        except Exception:
            pass
        raise error


bot.run(TOKEN)
