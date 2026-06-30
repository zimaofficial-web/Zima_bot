# Study Group Bot — Setup

A Telegram bot for class/study groups: tagging, moderation, polls, reminders, and activity stats.

## Files
```
bot.py          entrypoint — run this
db.py           SQLite storage (members, warnings, rules)
helpers.py      shared admin checks, user resolution
info.py         /stats /active /tagall
utility.py      /rules /setrules /poll /remind
moderation.py   /warn /unwarn /mute /unmute /kick
```

## 1. Create the bot
- Message **@BotFather** on Telegram
- `/newbot` → name it → copy the token (`123456:ABC-def...`)

## 2. Turn off privacy mode
This is the one step people skip and then the bot mysteriously doesn't work.
- @BotFather → `/mybots` → your bot → **Bot Settings** → **Group Privacy** → **Turn off**
- This lets the bot see all group messages (needed to track who's active), not just commands

## 3. Install
```
pip install -r requirements.txt
```

## 4. Set your token
```
export TELEGRAM_BOT_TOKEN="123456:ABC-defGhIJklmNoPQRstuVwxyz"
```
or edit `BOT_TOKEN` directly in `bot.py`.

## 5. Run
```
python3 bot.py
```
Keep this running — reminders, mute timers, and member tracking all depend on the process staying alive.

## 6. Add to your group
- Add the bot, then **make it admin** (Group Settings → Administrators)
- It needs admin rights to mute/kick people and to behave reliably in larger groups

---

## Commands

**Info**
| Command | What it does |
|---|---|
| `/stats` | Known members vs. active in last 7 days |
| `/active` | List of who's talked in the last 7 days, with timestamps |
| `/tagall [note]` | Tags everyone known, admin only |

**Utility**
| Command | What it does |
|---|---|
| `/rules` | Shows the saved rules |
| `/setrules <text>` | Sets the rules, admin only |
| `/poll Question? \| Opt1 \| Opt2 \| ...` | Sends a native Telegram poll |
| `/remind 30m <message>` | Schedules a reminder (`m`/`h`/`d`), admin only |

**Moderation** (admin only — reply to the person's message, or use `@username`)
| Command | What it does |
|---|---|
| `/warn` | Adds a warning. At 3 warnings → auto-mute 1 hour, count resets |
| `/unwarn` | Clears someone's warning count |
| `/mute [minutes]` | Mutes, default 60 min |
| `/unmute` | Lifts a mute |
| `/kick` | Removes the person (they can rejoin via invite link — not a permanent ban) |

---

## Notes
- People are only "known" (taggable/moderatable by @username) once they've sent at least one message — Telegram doesn't let bots pull a full member list
- If someone has no @username, moderation commands still work via reply-to-message, but `/warn @username` lookup needs an actual username
- All data lives in `bot.db` (SQLite) next to the script — delete it to wipe everything
- Warning auto-mute threshold (3) and duration (1 hour) are constants at the top of `moderation.py` if you want to change them
