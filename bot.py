import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────
REQUIRED_STATUS   = ".gg/VQ3YNgSr"          # free gen status requirement
RESTOCK_CHANNEL   = 1478365146999947368      # channel to announce restocks
BOOST_BUY_CHANNEL = 1478365159520079943      # purchase boost channel
PREM_BUY_CHANNEL  = 1478365160476381254      # buy premium channel

ROLE_PREMIUM      = 1478365092285251586
ROLE_MEMBER       = 1478365093732552847
ROLE_ANNOUNCE     = 1478365094504304813
ROLE_RESTOCK      = 1478365095234109592
ROLE_GIVEAWAY     = 1478365095909130242
ROLE_DROP         = 1478365097628930049

CASHAPP_TAG       = "$ASHZ67"

TOKEN = os.environ["TOKEN"]

# ── Bot setup ────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ── Stock storage (flat files in ./stock/) ───────────────────────────────────
STOCK_DIR = Path("stock")
STOCK_DIR.mkdir(exist_ok=True)

def stock_file(service: str) -> Path:
    return STOCK_DIR / f"{service}.txt"

def read_stock(service: str) -> list[str]:
    f = stock_file(service)
    if not f.exists():
        return []
    lines = [l.strip() for l in f.read_text().splitlines() if l.strip()]
    return lines

def pop_account(service: str) -> str | None:
    lines = read_stock(service)
    if not lines:
        return None
    account = lines[0]
    stock_file(service).write_text("\n".join(lines[1:]))
    return account

def stock_count(service: str) -> int:
    return len(read_stock(service))

SERVICES = {
    "roblox": "Roblox",
}

# ════════════════════════════════════════════════════════════════════════════
#  VIEWS
# ════════════════════════════════════════════════════════════════════════════

# ── Gen Panel (public – shown in #gen channel) ──────────────────────────────
class GenSelect(discord.ui.Select):
    def __init__(self, tier: str):
        self.tier = tier
        options = [discord.SelectOption(label="Roblox", value="roblox", emoji="🎮")]
        super().__init__(placeholder="choose a service", options=options, custom_id=f"gen_select_{tier}")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        service = self.values[0]
        member  = interaction.user
        guild   = interaction.guild

        # ── Free tier checks ──────────────────────────────────────────────
        if self.tier == "free":
            # must have member role
            mem_role = guild.get_role(ROLE_MEMBER)
            if mem_role and mem_role not in member.roles:
                await interaction.followup.send(
                    "❌ You need the **Member** role to use free gen.", ephemeral=True)
                return
            # must have required status
            status_ok = False
            if member.activity:
                for act in member.activities if hasattr(member, "activities") else [member.activity]:
                    if hasattr(act, "state") and act.state and REQUIRED_STATUS in act.state:
                        status_ok = True
                    if hasattr(act, "name") and act.name and REQUIRED_STATUS in act.name:
                        status_ok = True
            # also check custom status
            for act in member.activities:
                if isinstance(act, discord.CustomActivity):
                    text = (act.name or "") + (act.state or "")
                    if REQUIRED_STATUS in text:
                        status_ok = True
            if not status_ok:
                await interaction.followup.send(
                    f"❌ You must have `{REQUIRED_STATUS}` in your Discord status to use free gen!\n"
                    "Set it as a custom status and try again.", ephemeral=True)
                return

        # ── Premium tier checks ───────────────────────────────────────────
        elif self.tier == "premium":
            prem_role = guild.get_role(ROLE_PREMIUM)
            if prem_role and prem_role not in member.roles:
                await interaction.followup.send(
                    f"❌ You need **Premium** to use this gen panel.\n"
                    f"Purchase in <#{PREM_BUY_CHANNEL}> — CashApp: `{CASHAPP_TAG}`", ephemeral=True)
                return

        # ── Booster tier checks ───────────────────────────────────────────
        elif self.tier == "booster":
            if not member.premium_since:
                await interaction.followup.send(
                    f"❌ You need to be a **Server Booster** to use this gen panel.\n"
                    f"Boost the server or purchase in <#{BOOST_BUY_CHANNEL}>.", ephemeral=True)
                return

        # ── Pull account ──────────────────────────────────────────────────
        account = pop_account(service)
        if account is None:
            await interaction.followup.send(
                f"⚠️ **{SERVICES[service]}** is out of stock right now. Check back later!", ephemeral=True)
            return

        await interaction.followup.send(
            f"✅ **{SERVICES[service]} Account**\n```\n{account}\n```\n"
            f"*Keep this private! Do not share your account.*", ephemeral=True)


class GenPanelView(discord.ui.View):
    def __init__(self, tier: str):
        super().__init__(timeout=None)
        self.add_item(GenSelect(tier))

    @discord.ui.button(label="generate", style=discord.ButtonStyle.success,
                       emoji="🤖", custom_id="btn_generate_placeholder")
    async def generate_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Use the dropdown above to select a service!", ephemeral=True)

    @discord.ui.button(label="upgrade", style=discord.ButtonStyle.primary,
                       emoji="⬆️", custom_id="btn_upgrade")
    async def upgrade_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"💎 **Upgrade to Premium**\nSend payment to CashApp: `{CASHAPP_TAG}`\n"
            f"Then open a ticket in <#{PREM_BUY_CHANNEL}>!", ephemeral=True)

    @discord.ui.button(label="stock", style=discord.ButtonStyle.secondary,
                       emoji="📦", custom_id="btn_stock_view")
    async def stock_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        lines = [f"🎮 **Roblox**: `{stock_count('roblox')}` accounts"]
        await interaction.response.send_message(
            "📦 **Current Stock**\n" + "\n".join(lines), ephemeral=True)


# ── Reaction Role View ───────────────────────────────────────────────────────
class ReactionRoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _toggle_role(self, interaction: discord.Interaction, role_id: int, label: str):
        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message("Role not found.", ephemeral=True)
            return
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"✅ Removed **{label}** ping.", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ Added **{label}** ping.", ephemeral=True)

    @discord.ui.button(label="Announcements", style=discord.ButtonStyle.secondary,
                       emoji="📢", custom_id="rr_announce")
    async def announce(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle_role(interaction, ROLE_ANNOUNCE, "Announcements")

    @discord.ui.button(label="Restock Ping", style=discord.ButtonStyle.secondary,
                       emoji="🔄", custom_id="rr_restock")
    async def restock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle_role(interaction, ROLE_RESTOCK, "Restock")

    @discord.ui.button(label="Giveaway Ping", style=discord.ButtonStyle.secondary,
                       emoji="🎉", custom_id="rr_giveaway")
    async def giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle_role(interaction, ROLE_GIVEAWAY, "Giveaway")

    @discord.ui.button(label="Drop Ping", style=discord.ButtonStyle.secondary,
                       emoji="💧", custom_id="rr_drop")
    async def drop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle_role(interaction, ROLE_DROP, "Drop")


# ── Ticket Views ─────────────────────────────────────────────────────────────
class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Ticket", style=discord.ButtonStyle.danger,
                       emoji="🎫", custom_id="ticket_open")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild    = interaction.guild
        member   = interaction.user
        existing = discord.utils.get(guild.text_channels, name=f"ticket-{member.name.lower()}")
        if existing:
            await interaction.response.send_message(
                f"You already have an open ticket: {existing.mention}", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        for rid in [ROLE_PREMIUM]:
            r = guild.get_role(rid)
            if r:
                overwrites[r] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        channel = await guild.create_text_channel(
            f"ticket-{member.name}", overwrites=overwrites,
            category=interaction.channel.category)

        embed = discord.Embed(
            title="🎫 Support Ticket",
            description=(
                f"Welcome {member.mention}!\n\n"
                "**Please describe your issue or purchase request.**\n\n"
                f"💎 **Buy Premium** → CashApp: `{CASHAPP_TAG}`\n"
                f"⚡ **Buy Boost** → CashApp: `{CASHAPP_TAG}`\n\n"
                "Staff will assist you shortly."
            ),
            color=0x2b2d31
        )
        close_view = CloseTicketView()
        await channel.send(embed=embed, view=close_view)
        await interaction.response.send_message(
            f"✅ Ticket created: {channel.mention}", ephemeral=True)


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger,
                       emoji="🔒", custom_id="ticket_close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Closing ticket in 5 seconds...")
        await asyncio.sleep(5)
        await interaction.channel.delete()


# ── Purchase Views ────────────────────────────────────────────────────────────
class PurchaseView(discord.ui.View):
    def __init__(self, product: str):
        super().__init__(timeout=None)
        self.product = product

    @discord.ui.button(label="Purchase", style=discord.ButtonStyle.success,
                       emoji="💳", custom_id="purchase_btn")
    async def purchase(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title=f"💳 Purchase {self.product}",
            description=(
                f"**Send payment to CashApp:** `{CASHAPP_TAG}`\n\n"
                f"**{'Premium' if self.product == 'Premium' else 'Booster'} Price:** DM staff for pricing\n\n"
                "After paying:\n"
                "1. Screenshot your payment\n"
                "2. Open a ticket\n"
                "3. Send proof & your Discord username\n\n"
                "⚡ Roles are given within 24 hours."
            ),
            color=0xf5c518
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ════════════════════════════════════════════════════════════════════════════
#  EVENTS
# ════════════════════════════════════════════════════════════════════════════
@bot.event
async def on_ready():
    print(f"✅  Mercyy Gen online as {bot.user}")
    bot.add_view(GenPanelView("free"))
    bot.add_view(GenPanelView("premium"))
    bot.add_view(GenPanelView("booster"))
    bot.add_view(ReactionRoleView())
    bot.add_view(TicketView())
    bot.add_view(CloseTicketView())
    bot.add_view(PurchaseView("Premium"))
    bot.add_view(PurchaseView("Booster"))
    try:
        synced = await bot.tree.sync()
        print(f"✅  Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌  Sync error: {e}")


# ════════════════════════════════════════════════════════════════════════════
#  SLASH COMMANDS
# ════════════════════════════════════════════════════════════════════════════

# ── /setup-gen ───────────────────────────────────────────────────────────────
@bot.tree.command(name="setup-gen", description="Post the gen panel (Admin only)")
@app_commands.describe(tier="Which gen panel: free / premium / booster")
@app_commands.choices(tier=[
    app_commands.Choice(name="free",    value="free"),
    app_commands.Choice(name="premium", value="premium"),
    app_commands.Choice(name="booster", value="booster"),
])
@app_commands.checks.has_permissions(administrator=True)
async def setup_gen(interaction: discord.Interaction, tier: app_commands.Choice[str]):
    tier_val = tier.value
    colours  = {"free": 0x57f287, "premium": 0xf5c518, "booster": 0xff73fa}
    icons    = {"free": "🆓", "premium": "💎", "booster": "⚡"}

    descriptions = {
        "free": (
            f"**{icons['free']} Free Generator**\n\n"
            f"📦 **stocks** — stocked 24/7 with checked accounts\n"
            f"🛡️ **safety** — your generated accounts are secured\n"
            f"⭐ **accounts** — all accounts checked before restocking\n"
            f"💰 **pricing** — completely free!\n\n"
            f"⚠️ **Requirement:** You must have `{REQUIRED_STATUS}` in your Discord status."
        ),
        "premium": (
            f"**{icons['premium']} Premium Generator**\n\n"
            f"📦 **stocks** — stocked 24/7 with 100% full access accounts\n"
            f"🛡️ **safety** — your generated accounts are secured\n"
            f"⭐ **accounts** — all accounts checked before restocking\n"
            f"💰 **pricing** — requires Premium role\n\n"
            f"Purchase Premium → <#{PREM_BUY_CHANNEL}>"
        ),
        "booster": (
            f"**{icons['booster']} Booster Generator**\n\n"
            f"📦 **stocks** — exclusive stocked accounts for boosters\n"
            f"🛡️ **safety** — your generated accounts are secured\n"
            f"⭐ **accounts** — all accounts checked before restocking\n"
            f"💰 **pricing** — boost the server or purchase in <#{BOOST_BUY_CHANNEL}>"
        ),
    }

    embed = discord.Embed(
        title=f"✨ Mercyy Gen — {tier_val.capitalize()} Generator",
        description=descriptions[tier_val],
        color=colours[tier_val]
    )
    embed.set_footer(text="Mercyy Gen • Only Roblox accounts")

    view = GenPanelView(tier_val)
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("✅ Gen panel posted!", ephemeral=True)


# ── /restock ──────────────────────────────────────────────────────────────────
@bot.tree.command(name="restock", description="Restock accounts from a .txt file (Admin only)")
@app_commands.describe(service="Service to restock", file="Text file with accounts (one per line)")
@app_commands.choices(service=[
    app_commands.Choice(name="Roblox", value="roblox"),
])
@app_commands.checks.has_permissions(administrator=True)
async def restock(interaction: discord.Interaction,
                  service: app_commands.Choice[str],
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

    # append to existing stock
    existing = read_stock(service.value)
    combined = existing + new_accounts
    stock_file(service.value).write_text("\n".join(combined))

    count = len(new_accounts)
    total = len(combined)

    # announce in restock channel
    restock_ch = bot.get_channel(RESTOCK_CHANNEL)
    if restock_ch:
        restock_role = interaction.guild.get_role(ROLE_RESTOCK)
        ping = restock_role.mention if restock_role else ""
        embed = discord.Embed(
            title="🔄 Restock!",
            description=(
                f"**{service.name}** has been restocked!\n\n"
                f"➕ **Added:** `{count}` accounts\n"
                f"📦 **Total Stock:** `{total}` accounts"
            ),
            color=0x57f287
        )
        embed.set_footer(text="Mercyy Gen")
        await restock_ch.send(content=ping, embed=embed)

    await interaction.followup.send(
        f"✅ Restocked **{service.name}** with `{count}` accounts. Total: `{total}`",
        ephemeral=True)


# ── /stock ────────────────────────────────────────────────────────────────────
@bot.tree.command(name="stock", description="View current stock counts")
async def stock_cmd(interaction: discord.Interaction):
    lines = [f"🎮 **Roblox:** `{stock_count('roblox')}` accounts"]
    embed = discord.Embed(title="📦 Mercyy Gen Stock", description="\n".join(lines), color=0x2b2d31)
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ── /setup-reaction-roles ────────────────────────────────────────────────────
@bot.tree.command(name="setup-reaction-roles", description="Post reaction role panel (Admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_rr(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🔔 Notification Roles",
        description=(
            "Click the buttons below to toggle ping roles!\n\n"
            "📢 **Announcements** — Server announcements\n"
            "🔄 **Restock Ping** — Get notified on restocks\n"
            "🎉 **Giveaway Ping** — Giveaway notifications\n"
            "💧 **Drop Ping** — Drop alerts"
        ),
        color=0x5865f2
    )
    embed.set_footer(text="Mercyy Gen • Click to toggle roles")
    await interaction.channel.send(embed=embed, view=ReactionRoleView())
    await interaction.response.send_message("✅ Reaction role panel posted!", ephemeral=True)


# ── /setup-tickets ────────────────────────────────────────────────────────────
@bot.tree.command(name="setup-tickets", description="Post the ticket panel (Admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_tickets(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎫 Support Tickets",
        description=(
            "Need help or want to purchase?\n"
            "Click the button below to open a private ticket!\n\n"
            "💎 **Buy Premium** → DM or ticket\n"
            "⚡ **Buy Booster** → DM or ticket\n\n"
            f"All purchases via CashApp: `{CASHAPP_TAG}`"
        ),
        color=0xed4245
    )
    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message("✅ Ticket panel posted!", ephemeral=True)


# ── /setup-purchase ───────────────────────────────────────────────────────────
@bot.tree.command(name="setup-purchase", description="Post purchase panel in buy channel (Admin only)")
@app_commands.describe(product="premium or booster")
@app_commands.choices(product=[
    app_commands.Choice(name="Premium", value="Premium"),
    app_commands.Choice(name="Booster", value="Booster"),
])
@app_commands.checks.has_permissions(administrator=True)
async def setup_purchase(interaction: discord.Interaction, product: app_commands.Choice[str]):
    colours = {"Premium": 0xf5c518, "Booster": 0xff73fa}
    embed = discord.Embed(
        title=f"{'💎' if product.value == 'Premium' else '⚡'} Buy {product.value}",
        description=(
            f"Interested in **{product.value}**?\n\n"
            f"💳 **Payment Method:** CashApp only\n"
            f"📲 **CashApp Tag:** `{CASHAPP_TAG}`\n\n"
            "**How to purchase:**\n"
            "1. Click **Purchase** below\n"
            "2. Send payment via CashApp\n"
            "3. Open a ticket with proof\n"
            "4. Receive your role!\n\n"
            "*Roles given within 24 hours of payment verification.*"
        ),
        color=colours[product.value]
    )
    await interaction.channel.send(embed=embed, view=PurchaseView(product.value))
    await interaction.response.send_message("✅ Purchase panel posted!", ephemeral=True)


# ── /clear-stock ──────────────────────────────────────────────────────────────
@bot.tree.command(name="clear-stock", description="Clear all stock for a service (Admin only)")
@app_commands.describe(service="Service to clear")
@app_commands.choices(service=[
    app_commands.Choice(name="Roblox", value="roblox"),
])
@app_commands.checks.has_permissions(administrator=True)
async def clear_stock(interaction: discord.Interaction, service: app_commands.Choice[str]):
    stock_file(service.value).write_text("")
    await interaction.response.send_message(
        f"✅ Cleared all **{service.name}** stock.", ephemeral=True)


# ── Error handler ─────────────────────────────────────────────────────────────
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Error: {error}", ephemeral=True)
        raise error


bot.run(TOKEN)
