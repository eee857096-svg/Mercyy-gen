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
    m, s = divmod(rem, 60)
    parts = []
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if s or not parts: parts.append(f"{s}s")
    return " ".join(parts)

TOKEN = os.environ["TOKEN"]

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)

STOCK_DIR = Path("stock")
STOCK_DIR.mkdir(exist_ok=True)

def stock_file(service):
    return STOCK_DIR / f"{service}.txt"

def read_stock(service):
    f = stock_file(service)
    if not f.exists():
        return []
    return [l.strip() for l in f.read_text().splitlines() if l.strip()]

def pop_account(service):
    lines = read_stock(service)
    if not lines:
        return None
    account = lines[0]
    stock_file(service).write_text("\n".join(lines[1:]))
    return account

def stock_count(service):
    return len(read_stock(service))

SERVICES = {"roblox": "Roblox"}

class GenSelect(discord.ui.Select):
    def __init__(self, tier):
        self.tier = tier
        options = [discord.SelectOption(label="Roblox", value="roblox", emoji="🎮")]
        super().__init__(placeholder="choose a service", options=options, custom_id=f"gen_select_{tier}")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        service = self.values[0]
        member = interaction.user
        guild = interaction.guild

        if self.tier == "free":
            mem_role = guild.get_role(ROLE_MEMBER)
            if mem_role and mem_role not in member.roles:
                await interaction.followup.send("❌ You need the **Member** role to use free gen.", ephemeral=True)
                return
            status_ok = False
            for act in member.activities:
                if isinstance(act, discord.CustomActivity):
                    text = (act.name or "") + (act.state or "")
                    if REQUIRED_STATUS in text:
                        status_ok = True
                if hasattr(act, "state") and act.state and REQUIRED_STATUS in act.state:
                    status_ok = True
            if not status_ok:
                await interaction.followup.send(f"❌ You must have `{REQUIRED_STATUS}` in your Discord status!\nSet it as a custom status and try again.", ephemeral=True)
                return

        elif self.tier == "premium":
            prem_role = guild.get_role(ROLE_PREMIUM)
            if prem_role and prem_role not in member.roles:
                await interaction.followup.send(f"❌ You need **Premium** to use this gen panel.\nPurchase in <#{PREM_BUY_CHANNEL}> — CashApp: `{CASHAPP_TAG}`", ephemeral=True)
                return

        elif self.tier == "booster":
            if not member.premium_since:
                await interaction.followup.send(f"❌ You need to be a **Server Booster** to use this panel.\nBoost the server or purchase in <#{BOOST_BUY_CHANNEL}>.", ephemeral=True)
                return

        remaining = check_cooldown(self.tier, member.id)
        if remaining is not None:
            cd_display = {"free": "24h", "premium": "12h", "booster": "6h"}
            await interaction.followup.send(f"⏳ **Cooldown active!** Come back in **{fmt_time(remaining)}**.\n*{self.tier.capitalize()} cooldown: {cd_display[self.tier]}*", ephemeral=True)
            return

        account = pop_account(service)
        if account is None:
            await interaction.followup.send(f"⚠️ **{SERVICES[service]}** is out of stock right now. Check back later!", ephemeral=True)
            return

        set_cooldown(self.tier, member.id)
        cd_display = {"free": "24h", "premium": "12h", "booster": "6h"}
        await interaction.followup.send(f"✅ **{SERVICES[service]} Account**\n```\n{account}\n```\n⏱️ *Next gen available in {cd_display[self.tier]}. Keep this account private!*", ephemeral=True)


class GenPanelView(discord.ui.View):
    def __init__(self, tier):
        super().__init__(timeout=None)
        self.add_item(GenSelect(tier))

    @discord.ui.button(label="generate", style=discord.ButtonStyle.success, emoji="🤖", custom_id="btn_generate_placeholder")
    async def generate_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Use the dropdown above to select a service!", ephemeral=True)

    @discord.ui.button(label="upgrade", style=discord.ButtonStyle.primary, emoji="⬆️", custom_id="btn_upgrade")
    async def upgrade_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"💎 **Upgrade to Premium**\nCashApp: `{CASHAPP_TAG}`\nThen open a ticket in <#{PREM_BUY_CHANNEL}>!", ephemeral=True)

    @discord.ui.button(label="stock", style=discord.ButtonStyle.secondary, emoji="📦", custom_id="btn_stock_view")
    async def stock_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"📦 **Current Stock**\n🎮 **Roblox**: `{stock_count('roblox')}` accounts", ephemeral=True)


class ReactionRoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _toggle_role(self, interaction, role_id, label):
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

    @discord.ui.button(label="Announcements", style=discord.ButtonStyle.secondary, emoji="📢", custom_id="rr_announce")
    async def announce(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle_role(interaction, ROLE_ANNOUNCE, "Announcements")

    @discord.ui.button(label="Restock Ping", style=discord.ButtonStyle.secondary, emoji="🔄", custom_id="rr_restock")
    async def restock_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle_role(interaction, ROLE_RESTOCK, "Restock")

    @discord.ui.button(label="Giveaway Ping", style=discord.ButtonStyle.secondary, emoji="🎉", custom_id="rr_giveaway")
    async def giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle_role(interaction, ROLE_GIVEAWAY, "Giveaway")

    @discord.ui.button(label="Drop Ping", style=discord.ButtonStyle.secondary, emoji="💧", custom_id="rr_drop")
    async def drop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle_role(interaction, ROLE_DROP, "Drop")


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Ticket", style=discord.ButtonStyle.danger, emoji="🎫", custom_id="ticket_open")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = interaction.user
        existing = discord.utils.get(guild.text_channels, name=f"ticket-{member.name.lower()}")
        if existing:
            await interaction.response.send_message(f"You already have an open ticket: {existing.mention}", ephemeral=True)
            return
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        r = guild.get_role(ROLE_PREMIUM)
        if r:
            overwrites[r] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        channel = await guild.create_text_channel(f"ticket-{member.name}", overwrites=overwrites, category=interaction.channel.category)
        embed = discord.Embed(title="🎫 Support Ticket", description=f"Welcome {member.mention}!\n\n**Describe your issue or purchase request below.**\n\n💎 **Buy Premium** → CashApp: `{CASHAPP_TAG}`\n⚡ **Buy Boost** → CashApp: `{CASHAPP_TAG}`\n\nStaff will assist you shortly.", color=0x2b2d31)
        await channel.send(embed=embed, view=CloseTicketView())
        await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="ticket_close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Closing ticket in 5 seconds...")
        await asyncio.sleep(5)
        await interaction.channel.delete()


class PurchaseView(discord.ui.View):
    def __init__(self, product):
        super().__init__(timeout=None)
        self.product = product

    @discord.ui.button(label="Purchase", style=discord.ButtonStyle.success, emoji="💳", custom_id="purchase_btn")
    async def purchase(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title=f"💳 Purchase {self.product}", description=f"**Payment Method:** CashApp only\n**CashApp Tag:** `{CASHAPP_TAG}`\n\n**How to purchase:**\n1. Click **Purchase** below\n2. Send payment via CashApp\n3. Open a ticket with proof\n4. Receive your role!\n\n*Roles given within 24 hours of payment verification.*", color=0xf5c518)
        await interaction.response.send_message(embed=embed, ephemeral=True)


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


@bot.tree.command(name="setup_gen", description="Post a gen panel (Admin only)")
@app_commands.describe(tier="free / premium / booster")
@app_commands.choices(tier=[app_commands.Choice(name="free", value="free"), app_commands.Choice(name="premium", value="premium"), app_commands.Choice(name="booster", value="booster")])
@app_commands.checks.has_permissions(administrator=True)
async def setup_gen(interaction: discord.Interaction, tier: app_commands.Choice[str]):
    t = tier.value
    colours = {"free": 0x57f287, "premium": 0xf5c518, "booster": 0xff73fa}
    cd_info = {"free": "24 hours", "premium": "12 hours", "booster": "6 hours"}
    descs = {
        "free": f"**🆓 Free Generator**\n\n📦 **stocks** — stocked 24/7\n🛡️ **safety** — accounts secured\n⭐ **accounts** — all checked before restocking\n💰 **pricing** — free!\n⏱️ **cooldown** — `{cd_info['free']}` between gens\n\n⚠️ **Requirement:** Have `{REQUIRED_STATUS}` in your Discord status.",
        "premium": f"**💎 Premium Generator**\n\n📦 **stocks** — stocked 24/7 with full access\n🛡️ **safety** — accounts secured\n⭐ **accounts** — all checked before restocking\n💰 **pricing** — requires Premium role\n⏱️ **cooldown** — `{cd_info['premium']}` between gens\n\nPurchase Premium → <#{PREM_BUY_CHANNEL}>",
        "booster": f"**⚡ Booster Generator**\n\n📦 **stocks** — exclusive booster accounts\n🛡️ **safety** — accounts secured\n⭐ **accounts** — all checked before restocking\n💰 **pricing** — boost or purchase in <#{BOOST_BUY_CHANNEL}>\n⏱️ **cooldown** — `{cd_info['booster']}` between gens",
    }
    embed = discord.Embed(title=f"✨ Mercyy Gen — {t.capitalize()} Generator", description=descs[t], color=colours[t])
    embed.set_footer(text="Mercyy Gen • Roblox accounts only")
    await interaction.channel.send(embed=embed, view=GenPanelView(t))
    await interaction.response.send_message("✅ Gen panel posted!", ephemeral=True)


@bot.tree.command(name="restock", description="Restock accounts from a .txt file (Admin only)")
@app_commands.describe(service="Service to restock", file="Text file — one account per line")
@app_commands.choices(service=[app_commands.Choice(name="Roblox", value="roblox")])
@app_commands.checks.has_permissions(administrator=True)
async def restock(interaction: discord.Interaction, service: app_commands.Choice[str], file: discord.Attachment):
    await interaction.response.defer(ephemeral=True)
    if not file.filename.endswith(".txt"):
        await interaction.followup.send("❌ Please upload a `.txt` file.", ephemeral=True)
        return
    content = (await file.read()).decode("utf-8", errors="ignore")
    new_accounts = [l.strip() for l in content.splitlines() if l.strip()]
    if not new_accounts:
        await interaction.followup.send("❌ File is empty or invalid.", ephemeral=True)
        return
    existing = read_stock(service.value)
    combined = existing + new_accounts
    stock_file(service.value).write_text("\n".join(combined))
    count = len(new_accounts)
    total = len(combined)
    restock_ch = bot.get_channel(RESTOCK_CHANNEL)
    if restock_ch:
        restock_role = interaction.guild.get_role(ROLE_RESTOCK)
        ping = restock_role.mention if restock_role else ""
        embed = discord.Embed(title="🔄 Restock!", description=f"**{service.name}** has been restocked!\n\n➕ **Added:** `{count}` accounts\n📦 **Total Stock:** `{total}` accounts", color=0x57f287)
        embed.set_footer(text="Mercyy Gen")
        await restock_ch.send(content=ping, embed=embed)
    await interaction.followup.send(f"✅ Restocked **{service.name}** with `{count}` accounts. Total: `{total}`", ephemeral=True)


@bot.tree.command(name="stock", description="View current stock counts")
async def stock_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="📦 Mercyy Gen Stock", description=f"🎮 **Roblox:** `{stock_count('roblox')}` accounts", color=0x2b2d31)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="cooldown", description="Check your remaining cooldowns")
async def cooldown_cmd(interaction: discord.Interaction):
    lines = []
    for tier in ("free", "premium", "booster"):
        rem = check_cooldown(tier, interaction.user.id)
        lines.append(f"**{tier.capitalize()}:** ⏳ `{fmt_time(rem)}` remaining" if rem else f"**{tier.capitalize()}:** ✅ Ready")
    embed = discord.Embed(title="⏱️ Your Cooldowns", description="\n".join(lines), color=0x5865f2)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="reset_cooldown", description="Reset a user's cooldown (Admin only)")
@app_commands.describe(member="The user to reset", tier="Which tier to reset")
@app_commands.choices(tier=[app_commands.Choice(name="free", value="free"), app_commands.Choice(name="premium", value="premium"), app_commands.Choice(name="booster", value="booster"), app_commands.Choice(name="all", value="all")])
@app_commands.checks.has_permissions(administrator=True)
async def reset_cooldown(interaction: discord.Interaction, member: discord.Member, tier: app_commands.Choice[str]):
    if tier.value == "all":
        for t in COOLDOWNS:
            cooldown_store[t].pop(member.id, None)
        await interaction.response.send_message(f"✅ Reset **all** cooldowns for {member.mention}.", ephemeral=True)
    else:
        cooldown_store[tier.value].pop(member.id, None)
        await interaction.response.send_message(f"✅ Reset **{tier.value}** cooldown for {member.mention}.", ephemeral=True)


@bot.tree.command(name="setup_reaction_roles", description="Post reaction role panel (Admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_rr(interaction: discord.Interaction):
    embed = discord.Embed(title="🔔 Notification Roles", description="Click buttons to toggle ping roles!\n\n📢 **Announcements**\n🔄 **Restock Ping**\n🎉 **Giveaway Ping**\n💧 **Drop Ping**", color=0x5865f2)
    embed.set_footer(text="Mercyy Gen • Click to toggle")
    await interaction.channel.send(embed=embed, view=ReactionRoleView())
    await interaction.response.send_message("✅ Reaction roles panel posted!", ephemeral=True)


@bot.tree.command(name="setup_tickets", description="Post the ticket panel (Admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_tickets(interaction: discord.Interaction):
    embed = discord.Embed(title="🎫 Support Tickets", description=f"Need help or want to purchase?\nClick below to open a private ticket!\n\n💎 **Buy Premium** → CashApp: `{CASHAPP_TAG}`\n⚡ **Buy Booster** → CashApp: `{CASHAPP_TAG}`", color=0xed4245)
    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message("✅ Ticket panel posted!", ephemeral=True)


@bot.tree.command(name="setup_purchase", description="Post purchase panel (Admin only)")
@app_commands.describe(product="premium or booster")
@app_commands.choices(product=[app_commands.Choice(name="Premium", value="Premium"), app_commands.Choice(name="Booster", value="Booster")])
@app_commands.checks.has_permissions(administrator=True)
async def setup_purchase(interaction: discord.Interaction, product: app_commands.Choice[str]):
    colours = {"Premium": 0xf5c518, "Booster": 0xff73fa}
    embed = discord.Embed(title=f"{'💎' if product.value == 'Premium' else '⚡'} Buy {product.value}", description=f"**Payment Method:** CashApp only\n**CashApp Tag:** `{CASHAPP_TAG}`\n\n1. Click **Purchase** below\n2. Send payment via CashApp\n3. Open a ticket with proof\n4. Receive your role!\n\n*Roles given within 24 hours.*", color=colours[product.value])
    await interaction.channel.send(embed=embed, view=PurchaseView(product.value))
    await interaction.response.send_message("✅ Purchase panel posted!", ephemeral=True)


@bot.tree.command(name="clear_stock", description="Clear all stock for a service (Admin only)")
@app_commands.describe(service="Service to clear")
@app_commands.choices(service=[app_commands.Choice(name="Roblox", value="roblox")])
@app_commands.checks.has_permissions(administrator=True)
async def clear_stock(interaction: discord.Interaction, service: app_commands.Choice[str]):
    stock_file(service.value).write_text("")
    await interaction.response.send_message(f"✅ Cleared all **{service.name}** stock.", ephemeral=True)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
    else:
        try:
            await interaction.response.send_message(f"❌ Error: {error}", ephemeral=True)
        except Exception:
            pass
        raise error


bot.run(TOKEN)
