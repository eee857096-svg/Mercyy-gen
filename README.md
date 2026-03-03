# Mercyy Gen Bot 🌟

A fully-featured Discord generator bot for Roblox accounts.

---

## ⚙️ Railway Setup

1. Push this folder to a **GitHub repo**
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Under **Variables**, add:
   ```
   TOKEN = your_discord_bot_token_here
   ```
4. Railway will auto-deploy. Done!

---

## 📂 Adding Stock (Restocking Accounts)

Create a `.txt` file with one account per line, e.g.:
```
username1:password1
username2:password2
```
Then use the `/restock` command in Discord and upload the file.

The bot will:
- Add accounts to stock
- Announce restock in channel `1478365146999947368` with the count

---

## 🛠️ Slash Commands (Admin only unless noted)

| Command | Description |
|---|---|
| `/setup-gen free` | Posts the **Free** gen panel |
| `/setup-gen premium` | Posts the **Premium** gen panel |
| `/setup-gen booster` | Posts the **Booster** gen panel |
| `/restock [service] [file]` | Restocks accounts from .txt file |
| `/stock` | Shows current stock counts (everyone) |
| `/clear-stock [service]` | Clears all stock for a service |
| `/setup-reaction-roles` | Posts notification role panel |
| `/setup-tickets` | Posts ticket panel |
| `/setup-purchase premium` | Posts premium buy panel |
| `/setup-purchase booster` | Posts booster buy panel |

---

## 🎮 Free Gen Requirements

Users must:
1. Have the **Member** role (`1478365093732552847`)
2. Have `.gg/VQ3YNgSr` in their **Discord custom status**

---

## 💎 Role IDs

| Role | ID |
|---|---|
| Premium | `1478365092285251586` |
| Member (free) | `1478365093732552847` |
| Announcement Ping | `1478365094504304813` |
| Restock Ping | `1478365095234109592` |
| Giveaway Ping | `1478365095909130242` |
| Drop Ping | `1478365097628930049` |

---

## 📌 Channel IDs

| Channel | ID |
|---|---|
| Restock Announcements | `1478365146999947368` |
| Purchase Boost | `1478365159520079943` |
| Buy Premium | `1478365160476381254` |

---

## 💳 Payment

CashApp: `$ASHZ67`
