# -*- coding: utf-8 -*-
"""
🤖 BOT DISCORD ALL-IN-ONE
Modération • Fame • Stats • XP • Bienvenue • Fun • Utilitaires
"""

import discord
from discord.ext import commands
import json
import os
import datetime
import random
import asyncio
from collections import defaultdict

# ─────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────
TOKEN = os.environ.get("TOKEN")
PREFIX = "!"
VOTE_EMOJI = "⭐"
EMOJI_1 = "🔴"
EMOJI_2 = "🔵"
DATA_FAME = "fame_data.json"
DATA_WARNS = "warns_data.json"
DATA_STATS = "stats_data.json"
DATA_XP = "xp_data.json"
DATA_CONFIG = "config_data.json"

# ─────────────────────────────────────────
#  INTENTS & BOT
# ─────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True
intents.guilds = True
intents.voice_states = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# En mémoire
vocal_actif = {}
spam_tracker = defaultdict(list)
COOLDOWN_ANTISPAM = 3  # secondes entre messages

# ─────────────────────────────────────────
#  GESTION DES DONNÉES
# ─────────────────────────────────────────

def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default.copy() if isinstance(default, dict) else default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_fame():
    return load_json(DATA_FAME, {"votes": {}, "voters": {}, "vote_message_id": None, "duels": {}, "duel_voters": {}})

def save_fame(data):
    save_json(DATA_FAME, data)

def load_warns():
    return load_json(DATA_WARNS, {})

def save_warns(data):
    save_json(DATA_WARNS, data)

def load_stats():
    return load_json(DATA_STATS, {
        "messages": {},
        "vocal_minutes": {},
        "last_reset": datetime.datetime.utcnow().isoformat()
    })

def save_stats(data):
    save_json(DATA_STATS, data)

def load_xp():
    return load_json(DATA_XP, {"users": {}, "cooldown": {}})

def save_xp(data):
    save_json(DATA_XP, data)

def load_config():
    return load_json(DATA_CONFIG, {
        "welcome_channel": {},
        "leave_channel": {},
        "welcome_msg": "Bienvenue **{user}** sur **{server}** ! Tu es le membre #{count} 🎉",
        "leave_msg": "**{user}** a quitté le serveur. À bientôt ! 👋",
        "log_channel": {},
        "antispam": {}
    })

def save_config(data):
    save_json(DATA_CONFIG, data)

def format_time(minutes):
    m = int(minutes)
    if m < 60:
        return f"{m} min"
    h, m = m // 60, m % 60
    if h < 24:
        return f"{h}h {m}min"
    j, h = h // 24, h % 24
    return f"{j}j {h}h {m}min"

def check_reset_stats(data):
    last = datetime.datetime.fromisoformat(data["last_reset"])
    if (datetime.datetime.utcnow() - last).days >= 7:
        data["messages"] = {}
        data["vocal_minutes"] = {}
        data["last_reset"] = datetime.datetime.utcnow().isoformat()
        save_stats(data)
        return True
    return False

def xp_to_level(xp):
    return int((xp / 100) ** 0.5) + 1

def level_to_xp(level):
    return (level - 1) ** 2 * 100

# ─────────────────────────────────────────
#  ÉVÉNEMENTS
# ─────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"✅ Bot All-in-One connecté : {bot.user}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"Modération & Stats | {PREFIX}aide"))
    bot.loop.create_task(weekly_reset_loop())

@bot.event
async def on_member_join(member):
    if member.bot:
        return
    cfg = load_config()
    cid = cfg["welcome_channel"].get(str(member.guild.id))
    if cid:
        ch = bot.get_channel(cid)
        if ch:
            msg = cfg["welcome_msg"].format(user=member.mention, server=member.guild.name, count=member.guild.member_count)
            embed = discord.Embed(description=msg, color=discord.Color.green(), timestamp=datetime.datetime.utcnow())
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"Membre #{member.guild.member_count}")
            await ch.send(embed=embed)

@bot.event
async def on_member_remove(member):
    if member.bot:
        return
    cfg = load_config()
    cid = cfg["leave_channel"].get(str(member.guild.id))
    if cid:
        ch = bot.get_channel(cid)
        if ch:
            msg = cfg["leave_msg"].format(user=str(member), server=member.guild.name)
            embed = discord.Embed(description=msg, color=discord.Color.orange(), timestamp=datetime.datetime.utcnow())
            embed.set_thumbnail(url=member.display_avatar.url)
            await ch.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return await bot.process_commands(message)

    now = datetime.datetime.utcnow()

    # Anti-spam
    cfg = load_config()
    if cfg["antispam"].get(str(message.guild.id), True):
        now = datetime.datetime.utcnow()
        uid = str(message.author.id)
        spam_tracker[uid].append(now)
        spam_tracker[uid] = [t for t in spam_tracker[uid] if (now - t).total_seconds() < 5]
        if len(spam_tracker[uid]) > 5:
            try:
                await message.delete()
            except:
                pass
            return

    # Stats messages
    data = load_stats()
    check_reset_stats(data)
    uid = str(message.author.id)
    data["messages"][uid] = data["messages"].get(uid, 0) + 1
    save_stats(data)

    # XP
    xp_data = load_xp()
    xp_cd = xp_data.get("cooldown", {})
    xp_key = f"{message.guild.id}-{uid}"
    if xp_key not in xp_cd or (now - datetime.datetime.fromisoformat(xp_cd[xp_key])).total_seconds() > 60:
        xp_data["cooldown"][xp_key] = datetime.datetime.utcnow().isoformat()
        users = xp_data.get("users", {})
        key = f"{message.guild.id}-{uid}"
        users[key] = users.get(key, 0) + random.randint(15, 25)
        xp_data["users"] = users
        save_xp(xp_data)

    await bot.process_commands(message)

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return
    uid = str(member.id)
    if before.channel is None and after.channel:
        vocal_actif[uid] = datetime.datetime.utcnow()
    elif before.channel and after.channel is None:
        if uid in vocal_actif:
            debut = vocal_actif.pop(uid)
            mins = (datetime.datetime.utcnow() - debut).total_seconds() / 60
            data = load_stats()
            data["vocal_minutes"][uid] = data["vocal_minutes"].get(uid, 0) + mins
            save_stats(data)

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    data = load_fame()
    msg_id = str(reaction.message.id)

    if msg_id in data.get("duels", {}):
        duel = data["duels"][msg_id]
        vid = str(user.id)
        emoji = str(reaction.emoji)
        if emoji not in [EMOJI_1, EMOJI_2]:
            await reaction.remove(user)
            return
        dv = data.get("duel_voters", {}).get(msg_id, {})
        if vid in dv:
            await reaction.remove(user)
            return
        target = duel["user1_id"] if emoji == EMOJI_1 else duel["user2_id"]
        if vid == target:
            await reaction.remove(user)
            return
        if msg_id not in data["duel_voters"]:
            data["duel_voters"][msg_id] = {}
        data["duel_voters"][msg_id][vid] = emoji
        if emoji == EMOJI_1:
            data["duels"][msg_id]["votes1"] = data["duels"][msg_id].get("votes1", 0) + 1
        else:
            data["duels"][msg_id]["votes2"] = data["duels"][msg_id].get("votes2", 0) + 1
        save_fame(data)
        return

    if msg_id != str(data.get("vote_message_id")) or str(reaction.emoji) != VOTE_EMOJI:
        return
    vid = str(user.id)
    if vid in data["voters"]:
        await reaction.remove(user)
        return
    target_id = None
    for emb in reaction.message.embeds:
        if emb.footer and emb.footer.text and "user_id:" in emb.footer.text:
            target_id = emb.footer.text.replace("user_id:", "").strip()
            break
    if not target_id or vid == target_id:
        await reaction.remove(user)
        return
    data["voters"][vid] = target_id
    data["votes"][target_id] = data["votes"].get(target_id, 0) + 1
    save_fame(data)

async def weekly_reset_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        data = load_stats()
        if check_reset_stats(data):
            cfg = load_config()
            for guild in bot.guilds:
                ch = discord.utils.get(guild.text_channels, name="général") or guild.system_channel
                if ch:
                    emb = discord.Embed(title="🔄 Reset Hebdomadaire", description="Les stats de la semaine ont été remises à zéro. Bonne semaine ! 💪", color=discord.Color.blurple())
                    try:
                        await ch.send(embed=emb)
                    except:
                        pass
        await asyncio.sleep(3600)

# ─────────────────────────────────────────
#  MODÉRATION
# ─────────────────────────────────────────

@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick(ctx, membre: discord.Member, *, raison: str = "Aucune raison"):
    """Expulser un membre."""
    if not membre.kickable:
        return await ctx.send("❌ Rôle supérieur, impossible d'expulser.")
    try:
        await membre.send(f"Tu as été expulsé de **{ctx.guild.name}**\nRaison : {raison}")
    except:
        pass
    await membre.kick(reason=raison)
    await ctx.send(f"✅ **{membre}** a été expulsé. Raison : {raison}")

@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban(ctx, membre: discord.Member, *args):
    """Bannir un membre. !ban @user [jours 0-7] [raison]"""
    jours, raison = 0, "Aucune raison"
    if args and str(args[0]).isdigit():
        jours = min(7, max(0, int(args[0])))
        raison = " ".join(args[1:]) or "Aucune raison"
    elif args:
        raison = " ".join(args)
    if not membre.bannable:
        return await ctx.send("❌ Rôle supérieur, impossible de bannir.")
    try:
        await membre.send(f"Tu as été banni de **{ctx.guild.name}**\nRaison : {raison}")
    except:
        pass
    await membre.ban(reason=raison, delete_message_days=jours)
    await ctx.send(f"✅ **{membre}** a été banni. Raison : {raison}")

@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, identifiant: str):
    """Débannir par ID ou username."""
    bans = await ctx.guild.bans()
    b = next((x for x in bans if str(x.user.id) == identifiant or str(x.user).lower() == identifiant.lower()), None)
    if not b:
        return await ctx.send("❌ Utilisateur non banni.")
    await ctx.guild.unban(b.user)
    await ctx.send(f"✅ **{b.user}** a été débanni.")

@bot.command(name="timeout")
@commands.has_permissions(moderate_members=True)
async def timeout_cmd(ctx, membre: discord.Member, minutes: int, *, raison: str = "Aucune raison"):
    """Mettre en timeout. !timeout @user minutes [raison]"""
    if not membre.moderatable:
        return await ctx.send("❌ Impossible de timeout ce membre.")
    await membre.timeout(datetime.timedelta(minutes=minutes), reason=raison)
    await ctx.send(f"✅ **{membre}** en timeout pour {minutes} min. Raison : {raison}")

@bot.command(name="untimeout")
@commands.has_permissions(moderate_members=True)
async def untimeout(ctx, membre: discord.Member):
    """Retirer le timeout."""
    await membre.timeout(None)
    await ctx.send(f"✅ Timeout retiré pour **{membre}**")

@bot.command(name="clear", aliases=["purge", "nuke"])
@commands.has_permissions(manage_messages=True)
async def clear(ctx, nombre: int = 10, membre: discord.Member = None):
    """Supprimer des messages. !clear [nombre] [@user]"""
    nombre = min(100, max(1, nombre))
    def check(m):
        return (membre is None or m.author == membre) and not m.pinned
    deleted = await ctx.channel.purge(limit=nombre, check=check)
    await ctx.send(f"✅ {len(deleted)} message(s) supprimé(s).", delete_after=3)

@bot.command(name="warn")
@commands.has_permissions(moderate_members=True)
async def warn(ctx, membre: discord.Member, *, raison: str):
    """Avertir un membre."""
    data = load_warns()
    key = f"{ctx.guild.id}-{membre.id}"
    if key not in data:
        data[key] = []
    data[key].append({"raison": raison, "mod": str(ctx.author), "date": datetime.datetime.utcnow().isoformat()})
    save_warns(data)
    try:
        await membre.send(f"Avertissement sur **{ctx.guild.name}**\nRaison : {raison}\nTotal : {len(data[key])} avertissement(s)")
    except:
        pass
    await ctx.send(f"✅ **{membre}** averti. ({len(data[key])} avertissement(s))")

@bot.command(name="warns")
@commands.has_permissions(moderate_members=True)
async def warns(ctx, membre: discord.Member):
    """Voir les avertissements d'un membre."""
    data = load_warns()
    key = f"{ctx.guild.id}-{membre.id}"
    liste = data.get(key, [])
    if not liste:
        return await ctx.send(f"**{membre}** n'a aucun avertissement.")
    txt = "\n".join(f"{i+1}. {w['raison']} (par {w['mod']})" for i, w in enumerate(liste))
    await ctx.send(f"**Avertissements de {membre}** ({len(liste)}) :\n{txt}")

# ─────────────────────────────────────────
#  CONFIG SERVEUR (Bienvenue, Logs)
# ─────────────────────────────────────────

@bot.command(name="setwelcome")
@commands.has_permissions(manage_guild=True)
async def setwelcome(ctx, channel: discord.TextChannel = None):
    """Définir le salon de bienvenue. Variables : {user}, {server}, {count}"""
    ch = channel or ctx.channel
    cfg = load_config()
    cfg["welcome_channel"][str(ctx.guild.id)] = ch.id
    save_config(cfg)
    await ctx.send(f"✅ Salon de bienvenue : {ch.mention}")

@bot.command(name="setleave")
@commands.has_permissions(manage_guild=True)
async def setleave(ctx, channel: discord.TextChannel = None):
    """Définir le salon de départ. Variables : {user}, {server}"""
    ch = channel or ctx.channel
    cfg = load_config()
    cfg["leave_channel"][str(ctx.guild.id)] = ch.id
    save_config(cfg)
    await ctx.send(f"✅ Salon de départ : {ch.mention}")

@bot.command(name="setlogs")
@commands.has_permissions(manage_guild=True)
async def setlogs(ctx, channel: discord.TextChannel = None):
    """Définir le salon des logs de modération."""
    ch = channel or ctx.channel
    cfg = load_config()
    if "log_channel" not in cfg:
        cfg["log_channel"] = {}
    cfg["log_channel"][str(ctx.guild.id)] = ch.id
    save_config(cfg)
    await ctx.send(f"✅ Salon des logs : {ch.mention}")

@bot.command(name="antispam")
@commands.has_permissions(manage_guild=True)
async def antispam(ctx, on_off: str = None):
    """Activer/désactiver l'anti-spam. !antispam on/off"""
    cfg = load_config()
    if "antispam" not in cfg:
        cfg["antispam"] = {}
    gid = str(ctx.guild.id)
    if on_off:
        cfg["antispam"][gid] = on_off.lower() in ("on", "1", "true", "oui")
        save_config(cfg)
        await ctx.send(f"✅ Anti-spam : {'activé' if cfg['antispam'][gid] else 'désactivé'}")
    else:
        état = cfg["antispam"].get(gid, True)
        await ctx.send(f"Anti-spam : **{'activé' if état else 'désactivé'}**")

# ─────────────────────────────────────────
#  FAME & DUEL
# ─────────────────────────────────────────

@bot.command(name="nomine")
@commands.has_permissions(manage_messages=True)
async def nomine(ctx, membre: discord.Member):
    """Crée un vote de fame pour un membre."""
    if membre.bot:
        return await ctx.send("❌ On ne peut pas nominer un bot !")
    data = load_fame()
    emb = discord.Embed(
        title=f"⭐ Vote de Fame — {membre.display_name}",
        description=f"Réagis avec {VOTE_EMOJI} pour donner ta **fame** à {membre.mention} !\n\n🔒 1 vote par personne.",
        color=discord.Color.gold(),
        timestamp=datetime.datetime.utcnow()
    )
    emb.set_thumbnail(url=membre.display_avatar.url)
    emb.set_footer(text=f"user_id:{membre.id}")
    msg = await ctx.send(embed=emb)
    await msg.add_reaction(VOTE_EMOJI)
    data["vote_message_id"] = str(msg.id)
    save_fame(data)
    await ctx.message.delete()

@bot.command(name="top", aliases=["topfame"])
async def top(ctx):
    """Top 10 Hall of Fame."""
    data = load_fame()
    if not data["votes"]:
        return await ctx.send("📭 Aucun vote pour l'instant !")
    classement = sorted(data["votes"].items(), key=lambda x: x[1], reverse=True)[:10]
    medailles = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
    desc = ""
    for i, (uid, votes) in enumerate(classement):
        m = ctx.guild.get_member(int(uid))
        nom = m.display_name if m else "Inconnu"
        desc += f"{medailles[i]} **{nom}** — `{votes}` vote{'s' if votes > 1 else ''}\n"
    emb = discord.Embed(title="🏆 Top 10 — Hall of Fame", description=desc, color=discord.Color.gold())
    await ctx.send(embed=emb)

@bot.command(name="mafame")
async def mafame(ctx):
    """Ton score de fame."""
    data = load_fame()
    uid = str(ctx.author.id)
    votes = data["votes"].get(uid, 0)
    a_vote = uid in data["voters"]
    emb = discord.Embed(title=f"⭐ Fame de {ctx.author.display_name}", color=discord.Color.gold())
    emb.set_thumbnail(url=ctx.author.display_avatar.url)
    emb.add_field(name="⭐ Votes reçus", value=str(votes), inline=True)
    emb.add_field(name="🗳️ A voté ?", value="Oui" if a_vote else "Non", inline=True)
    await ctx.send(embed=emb)

@bot.command(name="duel")
async def duel(ctx, membre1: discord.Member, membre2: discord.Member):
    """Lance un duel entre 2 membres."""
    if membre1.bot or membre2.bot:
        return await ctx.send("❌ On ne peut pas faire dueller un bot !")
    if membre1.id == membre2.id:
        return await ctx.send("❌ Même personne !")

    emb_vote = discord.Embed(
        title="⚔️ DUEL DE FAME",
        description=f"**{membre1.display_name}** {EMOJI_1} VS {EMOJI_2} **{membre2.display_name}**\n\nRéagis {EMOJI_1} pour {membre1.display_name}\nRéagis {EMOJI_2} pour {membre2.display_name}\n\n🔒 1 vote par personne.",
        color=discord.Color.gold()
    )
    emb1 = discord.Embed(title=f"🔴 {membre1.display_name}", color=membre1.color or discord.Color.red())
    emb1.set_thumbnail(url=membre1.display_avatar.url)
    emb2 = discord.Embed(title=f"🔵 {membre2.display_name}", color=membre2.color or discord.Color.blue())
    emb2.set_thumbnail(url=membre2.display_avatar.url)

    await ctx.send(embed=emb_vote)
    await ctx.send(embed=emb1)
    msg = await ctx.send(embed=emb2)
    await msg.add_reaction(EMOJI_1)
    await msg.add_reaction(EMOJI_2)

    data = load_fame()
    data["duels"][str(msg.id)] = {"user1_id": str(membre1.id), "user2_id": str(membre2.id), "votes1": 0, "votes2": 0}
    save_fame(data)

@bot.command(name="resultat")
async def resultat(ctx, membre1: discord.Member, membre2: discord.Member):
    """Affiche le résultat d'un duel."""
    data = load_fame()
    duel_trouve = None
    for mid, d in data.get("duels", {}).items():
        if (d["user1_id"] == str(membre1.id) and d["user2_id"] == str(membre2.id)) or (d["user1_id"] == str(membre2.id) and d["user2_id"] == str(membre1.id)):
            duel_trouve = d
            break
    if not duel_trouve:
        return await ctx.send("❌ Aucun duel trouvé !")
    v1, v2 = duel_trouve.get("votes1", 0), duel_trouve.get("votes2", 0)
    if v1 == v2:
        return await ctx.send(f"🤝 Égalité ! **{v1}** votes chacun.")
    gagnant, vg = (membre1, v1) if v1 > v2 else (membre2, v2)
    perdant, vp = (membre2, v2) if v1 > v2 else (membre1, v1)
    emb = discord.Embed(title="🏆 Résultat du Duel", description=f"🏆 **{gagnant.display_name}** remporte le duel !", color=discord.Color.gold())
    emb.set_thumbnail(url=gagnant.display_avatar.url)
    emb.add_field(name=f"🏆 {gagnant.display_name}", value=f"{vg} vote(s)", inline=True)
    emb.add_field(name=f"💀 {perdant.display_name}", value=f"{vp} vote(s)", inline=True)
    await ctx.send(embed=emb)

@bot.command(name="resetfame")
@commands.has_permissions(administrator=True)
async def resetfame(ctx):
    """Remettre les votes fame à zéro."""
    save_fame({"votes": {}, "voters": {}, "vote_message_id": None, "duels": {}, "duel_voters": {}})
    await ctx.send("🔄 Fame remise à zéro !")

# ─────────────────────────────────────────
#  STATS (Messages + Vocal)
# ─────────────────────────────────────────

@bot.command(name="stats")
async def stats(ctx, membre: discord.Member = None):
    """Stats d'un membre (messages + vocal)."""
    m = membre or ctx.author
    data = load_stats()
    uid = str(m.id)
    msgs = data["messages"].get(uid, 0)
    vocal = data["vocal_minutes"].get(uid, 0)
    if uid in vocal_actif:
        vocal += (datetime.datetime.utcnow() - vocal_actif[uid]).total_seconds() / 60

    rmsg = next((i+1 for i, (k, _) in enumerate(sorted(data["messages"].items(), key=lambda x: x[1], reverse=True)) if k == uid), "N/A")
    rvoc = next((i+1 for i, (k, _) in enumerate(sorted(data["vocal_minutes"].items(), key=lambda x: x[1], reverse=True)) if k == uid), "N/A")

    last = datetime.datetime.fromisoformat(data["last_reset"])
    jr = (last + datetime.timedelta(days=7) - datetime.datetime.utcnow()).days

    emb = discord.Embed(title=f"📊 Stats de {m.display_name}", color=m.color or discord.Color.blurple(), timestamp=datetime.datetime.utcnow())
    emb.set_thumbnail(url=m.display_avatar.url)
    emb.add_field(name="💬 Messages", value=f"**{msgs:,}**", inline=True)
    emb.add_field(name="🎙️ Vocal", value=f"**{format_time(vocal)}**", inline=True)
    emb.add_field(name="​", value="​", inline=True)
    emb.add_field(name="🏅 Rang messages", value=f"**#{rmsg}**", inline=True)
    emb.add_field(name="🏅 Rang vocal", value=f"**#{rvoc}**", inline=True)
    emb.set_footer(text=f"🔄 Reset dans {jr} jour(s)")
    await ctx.send(embed=emb)

@bot.command(name="classement", aliases=["topstats"])
async def classement(ctx):
    """Classement messages et vocal."""
    data = load_stats()
    vocal_data = dict(data["vocal_minutes"])
    for uid, debut in vocal_actif.items():
        vocal_data[uid] = vocal_data.get(uid, 0) + (datetime.datetime.utcnow() - debut).total_seconds() / 60

    top_msg = sorted(data["messages"].items(), key=lambda x: x[1], reverse=True)[:5]
    top_voc = sorted(vocal_data.items(), key=lambda x: x[1], reverse=True)[:5]
    med = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

    emb = discord.Embed(title="📊 Classements", color=discord.Color.blurple(), timestamp=datetime.datetime.utcnow())
    if top_msg:
        txt = "\n".join(f"{med[i]} {ctx.guild.get_member(int(u)).display_name if ctx.guild.get_member(int(u)) else 'Inconnu'} — {n:,} msg" for i, (u, n) in enumerate(top_msg))
        emb.add_field(name="💬 Messages", value=txt, inline=True)
    if top_voc:
        txt = "\n".join(f"{med[i]} {ctx.guild.get_member(int(u)).display_name if ctx.guild.get_member(int(u)) else 'Inconnu'} — {format_time(n)}" for i, (u, n) in enumerate(top_voc))
        emb.add_field(name="🎙️ Vocal", value=txt, inline=True)
    if not top_msg and not top_voc:
        emb.description = "📭 Aucune donnée pour l'instant."
    await ctx.send(embed=emb)

@bot.command(name="resetstats")
@commands.has_permissions(administrator=True)
async def resetstats(ctx):
    """Reset manuel des stats."""
    data = load_stats()
    data["messages"] = {}
    data["vocal_minutes"] = {}
    data["last_reset"] = datetime.datetime.utcnow().isoformat()
    save_stats(data)
    await ctx.send("🔄 Stats remises à zéro !")

# ─────────────────────────────────────────
#  XP & NIVEAU
# ─────────────────────────────────────────

@bot.command(name="niveau", aliases=["level", "xp", "rang"])
async def niveau(ctx, membre: discord.Member = None):
    """Affiche ton niveau / XP."""
    m = membre or ctx.author
    data = load_xp()
    key = f"{ctx.guild.id}-{m.id}"
    xp = data.get("users", {}).get(key, 0)
    lvl = xp_to_level(xp)
    xp_actuel = xp - level_to_xp(lvl)
    xp_requis = level_to_xp(lvl + 1) - level_to_xp(lvl)
    pct = min(100, int(100 * xp_actuel / xp_requis)) if xp_requis else 0

    emb = discord.Embed(title=f"📈 Niveau de {m.display_name}", color=discord.Color.green(), timestamp=datetime.datetime.utcnow())
    emb.set_thumbnail(url=m.display_avatar.url)
    emb.add_field(name="⭐ Niveau", value=str(lvl), inline=True)
    emb.add_field(name="💎 XP", value=f"{xp:,}", inline=True)
    bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
    emb.add_field(name="Progression", value=f"`{bar}` {pct}%", inline=False)
    await ctx.send(embed=emb)

@bot.command(name="leaderboard", aliases=["lb", "topxp"])
async def leaderboard(ctx):
    """Top 10 niveau/XP du serveur."""
    data = load_xp()
    gid = str(ctx.guild.id)
    users = [(k.replace(f"{gid}-", ""), v) for k, v in data.get("users", {}).items() if k.startswith(f"{gid}-")]
    users = sorted(users, key=lambda x: x[1], reverse=True)[:10]
    if not users:
        return await ctx.send("📭 Aucun XP enregistré !")
    med = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
    desc = "\n".join(f"{med[i]} {ctx.guild.get_member(int(uid)).display_name if ctx.guild.get_member(int(uid)) else 'Inconnu'} — Niv. {xp_to_level(xp)} ({xp:,} XP)" for i, (uid, xp) in enumerate(users))
    emb = discord.Embed(title="🏆 Classement XP", description=desc, color=discord.Color.green())
    await ctx.send(embed=emb)

# ─────────────────────────────────────────
#  FUN & UTILITAIRES
# ─────────────────────────────────────────

@bot.command(name="ping")
async def ping(ctx):
    """Latence du bot."""
    await ctx.send(f"🏓 Pong ! **{round(bot.latency * 1000)}** ms")

@bot.command(name="userinfo", aliases=["ui", "whois"])
async def userinfo(ctx, membre: discord.Member = None):
    """Infos sur un membre."""
    u = membre or ctx.author
    roles = [r.mention for r in u.roles if r.name != "@everyone"]
    emb = discord.Embed(title=str(u), color=u.color or discord.Color.blue())
    emb.set_thumbnail(url=u.display_avatar.url)
    emb.add_field(name="ID", value=u.id, inline=True)
    emb.add_field(name="Créé le", value=f"<t:{int(u.created_at.timestamp())}:R>", inline=True)
    emb.add_field(name="Rejoint le", value=f"<t:{int(u.joined_at.timestamp())}:R>" if u.joined_at else "N/A", inline=True)
    emb.add_field(name="Rôles", value=", ".join(roles) if roles else "Aucun", inline=False)
    await ctx.send(embed=emb)

@bot.command(name="serverinfo", aliases=["si", "serveur"])
async def serverinfo(ctx):
    """Infos sur le serveur."""
    g = ctx.guild
    emb = discord.Embed(title=g.name, color=discord.Color.blue())
    if g.icon:
        emb.set_thumbnail(url=g.icon.url)
    emb.add_field(name="Membres", value=str(g.member_count), inline=True)
    emb.add_field(name="Rôles", value=str(len(g.roles)), inline=True)
    emb.add_field(name="Salons", value=str(len(g.channels)), inline=True)
    emb.add_field(name="Créé le", value=f"<t:{int(g.created_at.timestamp())}:R>", inline=False)
    await ctx.send(embed=emb)

@bot.command(name="avatar", aliases=["avi", "pp"])
async def avatar(ctx, membre: discord.Member = None):
    """Affiche l'avatar d'un membre."""
    u = membre or ctx.author
    emb = discord.Embed(title=f"Avatar de {u.display_name}", color=u.color or discord.Color.blurple())
    emb.set_image(url=u.display_avatar.url)
    emb.add_field(name="Lien", value=f"[Cliquer ici]({u.display_avatar.url})", inline=False)
    await ctx.send(embed=emb)

@bot.command(name="8ball")
async def ball8(ctx, *, question: str):
    """Boule magique."""
    rep = ["Oui.", "Non.", "Peut-être.", "Sans aucun doute.", "Probablement pas.", "C'est certain.", "Demande plus tard.", "Les signes disent oui."]
    await ctx.send(f"🎱 **{question}**\n{random.choice(rep)}")

@bot.command(name="roll", aliases=["dice", "d"])
async def roll(ctx, faces: int = 6):
    """Lancer un dé. !roll [faces]"""
    faces = min(100, max(2, faces))
    r = random.randint(1, faces)
    await ctx.send(f"🎲 Tu as lancé un dé **{faces}** : **{r}**")

@bot.command(name="sondage", aliases=["poll"])
@commands.has_permissions(manage_messages=True)
async def sondage(ctx, question: str, *options):
    """Créer un sondage. !sondage Question opt1 opt2 opt3... (max 10)"""
    if len(options) < 2 or len(options) > 10:
        return await ctx.send("❌ Donne entre 2 et 10 options.")
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    txt = "\n".join(f"{emojis[i]} {opt}" for i, opt in enumerate(options))
    emb = discord.Embed(title=f"📊 Sondage", description=f"**{question}**\n\n{txt}", color=discord.Color.blue(), timestamp=datetime.datetime.utcnow())
    emb.set_footer(text=f"Par {ctx.author}")
    msg = await ctx.send(embed=emb)
    for i in range(len(options)):
        await msg.add_reaction(emojis[i])

# ─────────────────────────────────────────
#  AIDE
# ─────────────────────────────────────────

@bot.command(name="aide", aliases=["help", "commands"])
async def aide(ctx):
    """Affiche toutes les commandes."""
    emb = discord.Embed(title="📖 Bot All-in-One — Aide", color=discord.Color.blurple(), timestamp=datetime.datetime.utcnow())
    emb.add_field(name="🛡️ Modération", value="`!kick` `!ban` `!unban` `!timeout` `!untimeout` `!clear` `!warn` `!warns`", inline=False)
    emb.add_field(name="⚙️ Config", value="`!setwelcome` `!setleave` `!setlogs` `!antispam`", inline=False)
    emb.add_field(name="⭐ Fame & Duel", value="`!nomine` `!top` `!mafame` `!duel` `!resultat` `!resetfame`", inline=False)
    emb.add_field(name="📊 Stats", value="`!stats` `!classement` `!resetstats`", inline=False)
    emb.add_field(name="📈 XP / Niveau", value="`!niveau` `!leaderboard`", inline=False)
    emb.add_field(name="🔧 Utilitaires", value="`!ping` `!userinfo` `!serverinfo` `!avatar`", inline=False)
    emb.add_field(name="🎮 Fun", value="`!8ball` `!roll` `!sondage`", inline=False)
    emb.set_footer(text=f"Préfixe : {PREFIX}")
    await ctx.send(embed=emb)

# ─────────────────────────────────────────
#  LANCEMENT
# ─────────────────────────────────────────
if __name__ == "__main__":
    bot.run(TOKEN)
