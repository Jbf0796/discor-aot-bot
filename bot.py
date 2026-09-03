import discord
from discord.ext import commands, tasks
import sqlite3
from datetime import datetime, time
from zoneinfo import ZoneInfo
import os


# ==================================================
# SETTINGS
# ==================================================

OWNER_ID = 1531647986503913546

WELCOME_CHANNEL = "🥀│welcome-to-paradis"
BIRTHDAY_CHANNEL = "🥀│birthday"
AGE_CHANNEL = "🥀│age-verification"
CADET_CHANNEL = "🥀│cadet-registry"
POINTS_CHANNEL = "⚒️│teams-points"
NICKNAME_REQUEST_CHANNEL = "🥀│request-nickname"

STATIONARY_CHANNEL = "🌹│stationary-troops"
SCOUTING_CHANNEL = "🌀│scouting-legion"
MILITARY_CHANNEL = "🐴│military-police"

WELCOME_GIF = "download.gif"

UNDER_18_ROLE = "Under 18"
ADULT_ROLE = "18+"

STATIONARY_ROLE = "Stationary Troops"
SCOUTING_ROLE = "Scouting Legion"
MILITARY_ROLE = "Military Police"

POINT_COOLDOWN = 30
DAILY_POINTS = 10

TIMEZONE = ZoneInfo("Asia/Manila")


# ==================================================
# TEAM PROMOTION TIERS
# ==================================================

TEAM_TIERS = [
    ("Common", 0),
    ("Uncommon", 100),
    ("Rare", 500),
    ("Epic", 1000),
    ("Legendary", 5000),
    ("Mythic", 10000)
]


# ==================================================
# BOT SETUP
# ==================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# ==================================================
# DATABASE
# ==================================================

connection = sqlite3.connect(
    "bot_database.db"
)

cursor = connection.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS birthdays (
    user_id INTEGER PRIMARY KEY,
    month INTEGER NOT NULL,
    day INTEGER NOT NULL,
    last_greeted TEXT
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS age_verification (
    user_id INTEGER PRIMARY KEY,
    age_group TEXT NOT NULL
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS cadets (
    user_id INTEGER PRIMARY KEY,
    team TEXT NOT NULL
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS personal_points (
    user_id INTEGER PRIMARY KEY,
    points INTEGER DEFAULT 0
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS team_points (
    team TEXT PRIMARY KEY,
    total_points INTEGER DEFAULT 0,
    daily_points INTEGER DEFAULT 0,
    weekly_points INTEGER DEFAULT 0,
    tier TEXT DEFAULT 'Common'
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS message_cooldowns (
    user_id INTEGER PRIMARY KEY,
    last_message REAL
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS daily_claims (
    user_id INTEGER PRIMARY KEY,
    last_claim TEXT
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS nickname_requests (
    message_id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    requested_nickname TEXT NOT NULL,
    status TEXT DEFAULT 'pending'
)
""")


connection.commit()


# ==================================================
# FIX OLD DATABASE
# ==================================================

try:

    cursor.execute("""
        ALTER TABLE team_points
        ADD COLUMN tier TEXT DEFAULT 'Common'
    """)

    connection.commit()

except sqlite3.OperationalError:

    pass


# ==================================================
# CREATE TEAM RECORDS
# ==================================================

teams = [
    STATIONARY_ROLE,
    SCOUTING_ROLE,
    MILITARY_ROLE
]


for team in teams:

    cursor.execute("""
        INSERT OR IGNORE INTO team_points
        (
            team,
            total_points,
            daily_points,
            weekly_points,
            tier
        )
        VALUES (?, 0, 0, 0, 'Common')
    """, (team,))


connection.commit()


# ==================================================
# PERMISSIONS
# ==================================================

def is_owner_or_admin(member):

    return (
        member.id == OWNER_ID
        or member.guild_permissions.administrator
    )


# ==================================================
# ADD POINTS
# ==================================================

async def add_points(member, amount):

    cursor.execute("""
        SELECT team
        FROM cadets
        WHERE user_id = ?
    """, (member.id,))

    result = cursor.fetchone()

    if not result:

        return False


    team = result[0]


    cursor.execute("""
        INSERT INTO personal_points
        (user_id, points)

        VALUES (?, ?)

        ON CONFLICT(user_id)
        DO UPDATE SET
        points = points + excluded.points
    """, (
        member.id,
        amount
    ))


    cursor.execute("""
        UPDATE team_points

        SET
            total_points = total_points + ?,
            daily_points = daily_points + ?,
            weekly_points = weekly_points + ?

        WHERE team = ?
    """, (
        amount,
        amount,
        amount,
        team
    ))


    connection.commit()


    await check_team_promotion(
        member.guild,
        team
    )


    return True


# ==================================================
# TEAM PROMOTION
# ==================================================

async def check_team_promotion(guild, team):

    cursor.execute("""
        SELECT total_points, tier
        FROM team_points
        WHERE team = ?
    """, (team,))

    result = cursor.fetchone()

    if not result:

        return


    total_points = result[0]
    current_tier = result[1]

    new_tier = "Common"


    for tier_name, required_points in TEAM_TIERS:

        if total_points >= required_points:

            new_tier = tier_name


    if new_tier == current_tier:

        return


    cursor.execute("""
        UPDATE team_points
        SET tier = ?
        WHERE team = ?
    """, (
        new_tier,
        team
    ))

    connection.commit()


    channel = discord.utils.get(
        guild.text_channels,
        name=POINTS_CHANNEL
    )

    if not channel:

        return


    team_emojis = {
        STATIONARY_ROLE: "🌹",
        SCOUTING_ROLE: "🌀",
        MILITARY_ROLE: "🐴"
    }


    emoji = team_emojis.get(
        team,
        "⚔️"
    )


    embed = discord.Embed(
        title="🏆⚔️ TEAM PROMOTION! ⚔️🏆",

        description=(
            f"{emoji} **{team}** has earned a promotion!\n\n"
            f"🏅 New Tier: **{new_tier}**\n"
            f"⚒️ Total Points: **{total_points}**\n\n"
            "The division continues to grow stronger!\n\n"
            "**SHINZOU WO SASAGEYO! ❤️⚔️**"
        ),

        color=discord.Color.red()
    )


    await channel.send(embed=embed)


# ==================================================
# NICKNAME REQUEST SYSTEM
# ==================================================

async def create_nickname_request(message, nickname):

    member = message.author


    if not nickname:

        await message.channel.send(
            "❌ Please provide the nickname you want to request."
        )

        return


    if len(nickname) > 32:

        await message.channel.send(
            "❌ Nicknames cannot be longer than 32 characters."
        )

        return


    embed = discord.Embed(
        title="⚔️ NICKNAME REQUEST ⚔️",

        description=(
            f"👤 **Member:** {member.mention}\n\n"
            f"📝 **Requested Nickname:** `{nickname}`\n\n"
            "👑 React below:\n"
            "✅ — Approve\n"
            "❌ — Reject"
        ),

        color=discord.Color.red()
    )


    request_message = await message.channel.send(
        embed=embed
    )


    await request_message.add_reaction("✅")
    await request_message.add_reaction("❌")


    cursor.execute("""
        INSERT OR REPLACE INTO nickname_requests
        (
            message_id,
            user_id,
            guild_id,
            channel_id,
            requested_nickname,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        request_message.id,
        member.id,
        message.guild.id,
        message.channel.id,
        nickname,
        "pending"
    ))


    connection.commit()


# ==================================================
# NICKNAME REQUEST REACTION
# ==================================================

@bot.event
async def on_raw_reaction_add(payload):

    if bot.user and payload.user_id == bot.user.id:

        return


    # Only the owner can approve or reject
    if payload.user_id != OWNER_ID:

        return


    emoji = str(payload.emoji)


    if emoji not in ["✅", "❌"]:

        return


    cursor.execute("""
        SELECT
            user_id,
            guild_id,
            channel_id,
            requested_nickname,
            status

        FROM nickname_requests

        WHERE message_id = ?
    """, (payload.message_id,))


    request = cursor.fetchone()


    if not request:

        return


    user_id = request[0]
    guild_id = request[1]
    channel_id = request[2]
    nickname = request[3]
    status = request[4]


    if status != "pending":

        return


    guild = bot.get_guild(
        guild_id
    )


    if not guild:

        return


    member = guild.get_member(
        user_id
    )


    channel = guild.get_channel(
        channel_id
    )


    if not member:

        return


    # ==================================================
    # APPROVE
    # ==================================================

    if emoji == "✅":

        try:

            await member.edit(
                nick=nickname,
                reason="Nickname request approved"
            )


        except discord.Forbidden:

            if channel:

                await channel.send(
                    f"❌ {member.mention}, I could not change "
                    "your nickname. Make sure I have the "
                    "**Manage Nicknames** permission and my "
                    "role is above yours."
                )

            return


        except discord.HTTPException:

            if channel:

                await channel.send(
                    f"❌ {member.mention}, Discord could not "
                    "change your nickname."
                )

            return


        cursor.execute("""
            UPDATE nickname_requests
            SET status = 'approved'
            WHERE message_id = ?
        """, (
            payload.message_id,
        ))


        connection.commit()


        if channel:

            embed = discord.Embed(
                title="⚔️ NICKNAME APPROVED ⚔️",

                description=(
                    f"✅ {member.mention}, your nickname request "
                    "has been approved!\n\n"
                    f"📝 New Nickname: **{nickname}**\n\n"
                    "**Dedicate your heart! ❤️⚔️**"
                ),

                color=discord.Color.green()
            )


            await channel.send(
                embed=embed
            )


    # ==================================================
    # REJECT
    # ==================================================

    elif emoji == "❌":

        cursor.execute("""
            UPDATE nickname_requests
            SET status = 'rejected'
            WHERE message_id = ?
        """, (
            payload.message_id,
        ))


        connection.commit()


        if channel:

            embed = discord.Embed(
                title="⚔️ NICKNAME REQUEST REJECTED ⚔️",

                description=(
                    f"❌ {member.mention}, your nickname request "
                    "has been rejected."
                ),

                color=discord.Color.red()
            )


            await channel.send(
                embed=embed
            )


# ==================================================
# AGE VERIFICATION
# ==================================================

class AgeVerificationView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )


    @discord.ui.button(
        label="Under 18",
        emoji="🛡️",
        style=discord.ButtonStyle.secondary,
        custom_id="age_under_18"
    )
    async def under_18_button(
        self,
        interaction,
        button
    ):

        await choose_age(
            interaction,
            "Under 18"
        )


    @discord.ui.button(
        label="18+",
        emoji="⚔️",
        style=discord.ButtonStyle.danger,
        custom_id="age_18_plus"
    )
    async def adult_button(
        self,
        interaction,
        button
    ):

        await choose_age(
            interaction,
            "18+"
        )


async def choose_age(
    interaction,
    age_group
):

    member = interaction.user
    guild = interaction.guild


    cursor.execute("""
        SELECT user_id
        FROM age_verification
        WHERE user_id = ?
    """, (
        member.id,
    ))


    if cursor.fetchone():

        await interaction.response.send_message(
            "⚔️ You have already chosen your age group.",
            ephemeral=True
        )

        return


    role_name = (
        UNDER_18_ROLE
        if age_group == "Under 18"
        else ADULT_ROLE
    )


    role = discord.utils.get(
        guild.roles,
        name=role_name
    )


    if not role:

        await interaction.response.send_message(
            f"❌ Role `{role_name}` was not found.",
            ephemeral=True
        )

        return


    await member.add_roles(
        role
    )


    cursor.execute("""
        INSERT INTO age_verification
        (user_id, age_group)

        VALUES (?, ?)
    """, (
        member.id,
        age_group
    ))


    connection.commit()


    await interaction.response.send_message(
        "⚔️ Verification completed!",
        ephemeral=True
    )


# ==================================================
# CADET REGISTRY
# ==================================================

class CadetRegistryView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )


    @discord.ui.button(
        label="Stationary Troops",
        emoji="🌹",
        style=discord.ButtonStyle.secondary,
        custom_id="team_stationary"
    )
    async def stationary_button(
        self,
        interaction,
        button
    ):

        await choose_team(
            interaction,
            STATIONARY_ROLE
        )


    @discord.ui.button(
        label="Scouting Legion",
        emoji="🌀",
        style=discord.ButtonStyle.primary,
        custom_id="team_scouting"
    )
    async def scouting_button(
        self,
        interaction,
        button
    ):

        await choose_team(
            interaction,
            SCOUTING_ROLE
        )


    @discord.ui.button(
        label="Military Police",
        emoji="🐴",
        style=discord.ButtonStyle.secondary,
        custom_id="team_military"
    )
    async def military_button(
        self,
        interaction,
        button
    ):

        await choose_team(
            interaction,
            MILITARY_ROLE
        )


async def choose_team(
    interaction,
    team
):

    member = interaction.user
    guild = interaction.guild


    cursor.execute("""
        SELECT team
        FROM cadets
        WHERE user_id = ?
    """, (
        member.id,
    ))


    existing = cursor.fetchone()


    if existing:

        await interaction.response.send_message(
            f"⚔️ You are already registered in "
            f"**{existing[0]}**.",
            ephemeral=True
        )

        return


    role = discord.utils.get(
        guild.roles,
        name=team
    )


    if not role:

        await interaction.response.send_message(
            f"❌ Role `{team}` was not found.",
            ephemeral=True
        )

        return


    await member.add_roles(
        role
    )


    cursor.execute("""
        INSERT INTO cadets
        (user_id, team)

        VALUES (?, ?)
    """, (
        member.id,
        team
    ))


    cursor.execute("""
        INSERT OR IGNORE INTO personal_points
        (user_id, points)

        VALUES (?, 0)
    """, (
        member.id,
    ))


    connection.commit()


    await interaction.response.send_message(
        f"⚔️ You joined **{team}**!",
        ephemeral=True
    )


    team_channels = {
        STATIONARY_ROLE: STATIONARY_CHANNEL,
        SCOUTING_ROLE: SCOUTING_CHANNEL,
        MILITARY_ROLE: MILITARY_CHANNEL
    }


    channel_name = team_channels.get(
        team
    )


    team_channel = discord.utils.get(
        guild.text_channels,
        name=channel_name
    )


    if team_channel:

        embed = discord.Embed(
            title="⚔️ CADET REGISTERED ⚔️",

            description=(
                f"{member.mention} has officially registered "
                f"in the **{team}**!\n\n"
                "**Shinzou wo Sasageyo! ❤️⚔️**"
            ),

            color=discord.Color.red()
        )


        embed.set_thumbnail(
            url=member.display_avatar.url
        )


        await team_channel.send(
            embed=embed
        )


# ==================================================
# READY
# ==================================================

@bot.event
async def on_ready():

    print(
        f"Logged in as {bot.user}"
    )


    bot.add_view(
        AgeVerificationView()
    )


    bot.add_view(
        CadetRegistryView()
    )


    if not check_birthdays.is_running():

        check_birthdays.start()


    if not daily_team_ranking.is_running():

        daily_team_ranking.start()


    if not weekly_team_ranking.is_running():

        weekly_team_ranking.start()


# ==================================================
# WELCOME MESSAGE
# ==================================================

@bot.event
async def on_member_join(member):

    channel = discord.utils.get(
        member.guild.text_channels,
        name=WELCOME_CHANNEL
    )


    if not channel:

        return


    embed = discord.Embed(
        title="🪽 Welcome to the Attack on Titan Community!",

        description=(
            f"Welcome, {member.mention}!\n\n"
            f"You have officially joined "
            f"**{member.guild.name}**!\n\n"
            "Dedicate your heart and enjoy your stay.\n\n"
            "**Shinzou wo Sasageyo! ❤️⚔️**"
        ),

        color=discord.Color.red()
    )


    embed.set_thumbnail(
        url=member.display_avatar.url
    )


    try:

        file = discord.File(
            WELCOME_GIF,
            filename=WELCOME_GIF
        )


        embed.set_image(
            url=f"attachment://{WELCOME_GIF}"
        )


        await channel.send(
            embed=embed,
            file=file
        )


    except FileNotFoundError:

        await channel.send(
            embed=embed
        )


# ==================================================
# DAILY COMMAND
# ==================================================

@bot.command()
async def daily(ctx):

    cursor.execute("""
        SELECT team
        FROM cadets
        WHERE user_id = ?
    """, (
        ctx.author.id,
    ))


    if not cursor.fetchone():

        await ctx.send(
            "❌ You must register as a cadet first!"
        )

        return


    today = datetime.now(
        TIMEZONE
    ).strftime("%Y-%m-%d")


    cursor.execute("""
        SELECT last_claim
        FROM daily_claims
        WHERE user_id = ?
    """, (
        ctx.author.id,
    ))


    result = cursor.fetchone()


    if result and result[0] == today:

        await ctx.send(
            "⚠️ You already claimed your daily points today!"
        )

        return


    await add_points(
        ctx.author,
        DAILY_POINTS
    )


    cursor.execute("""
        INSERT INTO daily_claims
        (user_id, last_claim)

        VALUES (?, ?)

        ON CONFLICT(user_id)
        DO UPDATE SET
        last_claim = excluded.last_claim
    """, (
        ctx.author.id,
        today
    ))


    connection.commit()


    await ctx.send(
        f"🎯 {ctx.author.mention} claimed "
        f"**+{DAILY_POINTS} points!** ⚒️"
    )


# ==================================================
# ADMIN GIVE POINTS
# ==================================================

@bot.command()
async def givepoints(
    ctx,
    member: discord.Member,
    amount: int
):

    if not is_owner_or_admin(
        ctx.author
    ):

        await ctx.send(
            "❌ Only the owner or admins can use this."
        )

        return


    if amount <= 0:

        await ctx.send(
            "❌ Points must be greater than 0."
        )

        return


    success = await add_points(
        member,
        amount
    )


    if not success:

        await ctx.send(
            "❌ That member is not registered in a team."
        )

        return


    await ctx.send(
        f"⚔️ {member.mention} received "
        f"**+{amount} points!**"
    )


# ==================================================
# PERSONAL POINTS
# ==================================================

@bot.command()
async def points(ctx):

    cursor.execute("""
        SELECT points
        FROM personal_points
        WHERE user_id = ?
    """, (
        ctx.author.id,
    ))


    result = cursor.fetchone()

    points = result[0] if result else 0


    cursor.execute("""
        SELECT team
        FROM cadets
        WHERE user_id = ?
    """, (
        ctx.author.id,
    ))


    result = cursor.fetchone()

    team = result[0] if result else "Not Registered"


    embed = discord.Embed(
        title="⚔️ CADET RECORD ⚔️",

        description=(
            f"👤 Cadet: {ctx.author.mention}\n\n"
            f"🪖 Team: **{team}**\n"
            f"⚒️ Personal Points: **{points}**"
        ),

        color=discord.Color.red()
    )


    await ctx.send(
        embed=embed
    )


# ==================================================
# CREATE TEAM RANKING
# ==================================================

async def create_total_ranking():

    cursor.execute("""
        SELECT team, total_points, tier
        FROM team_points
        ORDER BY total_points DESC
    """)


    rows = cursor.fetchall()

    description = ""


    for position, row in enumerate(
        rows,
        start=1
    ):

        description += (
            f"**#{position} {row[0]}**\n"
            f"🏅 Tier: **{row[2]}**\n"
            f"⚒️ Total Points: **{row[1]}**\n\n"
        )


    return discord.Embed(
        title="🏆 ALL-TIME TEAM RANKING 🏆",
        description=description,
        color=discord.Color.red()
    )


# ==================================================
# DAILY TEAM RANKING
# ==================================================

async def create_daily_ranking():

    cursor.execute("""
        SELECT team, daily_points
        FROM team_points
        ORDER BY daily_points DESC
    """)


    rows = cursor.fetchall()

    description = ""


    for position, row in enumerate(
        rows,
        start=1
    ):

        description += (
            f"**#{position} {row[0]}** — "
            f"⚒️ **{row[1]} Points**\n"
        )


    return discord.Embed(
        title="⚔️ DAILY TEAM REPORT ⚔️",
        description=description,
        color=discord.Color.red()
    )


# ==================================================
# WEEKLY TEAM RANKING
# ==================================================

async def create_weekly_ranking():

    cursor.execute("""
        SELECT team, weekly_points
        FROM team_points
        ORDER BY weekly_points DESC
    """)


    rows = cursor.fetchall()

    description = ""


    for position, row in enumerate(
        rows,
        start=1
    ):

        description += (
            f"**#{position} {row[0]}** — "
            f"⚒️ **{row[1]} Points**\n"
        )


    return discord.Embed(
        title="🏆 WEEKLY TEAM REPORT 🏆",
        description=description,
        color=discord.Color.red()
    )


# ==================================================
# GET POINTS CHANNEL
# ==================================================

async def get_points_channel():

    for guild in bot.guilds:

        channel = discord.utils.get(
            guild.text_channels,
            name=POINTS_CHANNEL
        )


        if channel:

            return channel


    return None


# ==================================================
# AUTOMATIC DAILY REPORT
# ==================================================

@tasks.loop(
    time=time(
        hour=23,
        minute=59,
        tzinfo=TIMEZONE
    )
)
async def daily_team_ranking():

    channel = await get_points_channel()


    if not channel:

        return


    embed = await create_daily_ranking()

    await channel.send(
        embed=embed
    )


    cursor.execute("""
        UPDATE team_points
        SET daily_points = 0
    """)


    connection.commit()


# ==================================================
# AUTOMATIC WEEKLY REPORT
# ==================================================

@tasks.loop(
    time=time(
        hour=23,
        minute=58,
        tzinfo=TIMEZONE
    )
)
async def weekly_team_ranking():

    now = datetime.now(
        TIMEZONE
    )


    # Sunday
    if now.weekday() != 6:

        return


    channel = await get_points_channel()


    if not channel:

        return


    embed = await create_weekly_ranking()

    await channel.send(
        embed=embed
    )


    cursor.execute("""
        UPDATE team_points
        SET weekly_points = 0
    """)


    connection.commit()


# ==================================================
# TEAM RANK COMMANDS
# ==================================================

@bot.command()
async def teamrank(ctx):

    embed = await create_total_ranking()

    await ctx.send(
        embed=embed
    )


@bot.command()
async def dailyrank(ctx):

    embed = await create_daily_ranking()

    await ctx.send(
        embed=embed
    )


@bot.command()
async def weeklyrank(ctx):

    embed = await create_weekly_ranking()

    await ctx.send(
        embed=embed
    )


# ==================================================
# BIRTHDAY REGISTRATION
# ==================================================

@bot.command()
async def register(
    ctx,
    member: discord.Member,
    month: str,
    day: int
):

    if ctx.channel.name != BIRTHDAY_CHANNEL:

        return


    if not is_owner_or_admin(
        ctx.author
    ):

        await ctx.send(
            "❌ Only the owner and admins can "
            "register birthdays."
        )

        return


    try:

        birthday = datetime.strptime(
            f"{month} {day}",
            "%B %d"
        )


    except ValueError:

        await ctx.send(
            "❌ Example: `!register @member March 07`"
        )

        return


    cursor.execute("""
        INSERT OR REPLACE INTO birthdays
        (
            user_id,
            month,
            day,
            last_greeted
        )

        VALUES (?, ?, ?, NULL)
    """, (
        member.id,
        birthday.month,
        birthday.day
    ))


    connection.commit()


    await ctx.send(
        f"🎂 Birthday registered for "
        f"{member.mention}!"
    )


# ==================================================
# BIRTHDAY LIST
# ==================================================

@bot.command()
async def birthdaylist(ctx):

    if ctx.channel.name != BIRTHDAY_CHANNEL:

        return


    cursor.execute("""
        SELECT user_id, month, day
        FROM birthdays
        ORDER BY month, day
    """)


    rows = cursor.fetchall()


    if not rows:

        await ctx.send(
            "No birthdays registered."
        )

        return


    description = ""


    for user_id, month, day in rows:

        date = datetime(
            2024,
            month,
            day
        ).strftime(
            "%B %d"
        )


        description += (
            f"🎂 **{date}** — "
            f"<@{user_id}>\n"
        )


    embed = discord.Embed(
        title="⚔️ BIRTHDAY REGISTRY ⚔️",
        description=description,
        color=discord.Color.red()
    )


    await ctx.send(
        embed=embed
    )


# ==================================================
# BIRTHDAY CHECKER
# ==================================================

@tasks.loop(minutes=1)
async def check_birthdays():

    now = datetime.now(
        TIMEZONE
    )


    today = now.strftime(
        "%Y-%m-%d"
    )


    cursor.execute("""
        SELECT user_id, last_greeted
        FROM birthdays
        WHERE month = ? AND day = ?
    """, (
        now.month,
        now.day
    ))


    rows = cursor.fetchall()


    for user_id, last_greeted in rows:


        if last_greeted == today:

            continue


        for guild in bot.guilds:


            member = guild.get_member(
                user_id
            )


            channel = discord.utils.get(
                guild.text_channels,
                name=BIRTHDAY_CHANNEL
            )


            if member and channel:


                embed = discord.Embed(
                    title="🎂⚔️ HAPPY BIRTHDAY! ⚔️🎂",

                    description=(
                        f"Today we celebrate "
                        f"{member.mention}!\n\n"
                        "Another year of courage and "
                        "strength begins.\n\n"
                        "**Shinzou wo Sasageyo! ❤️⚔️**"
                    ),

                    color=discord.Color.red()
                )


                await channel.send(
                    embed=embed
                )


        cursor.execute("""
            UPDATE birthdays
            SET last_greeted = ?
            WHERE user_id = ?
        """, (
            today,
            user_id
        ))


        connection.commit()


# ==================================================
# SETUP AGE VERIFICATION
# ==================================================

@bot.command()
async def setupage(ctx):

    if not is_owner_or_admin(
        ctx.author
    ):

        return


    if ctx.channel.name != AGE_CHANNEL:

        await ctx.send(
            "❌ Use this command in the age verification channel."
        )

        return


    embed = discord.Embed(
        title="⚔️ AGE VERIFICATION ⚔️",

        description=(
            "Choose your age group.\n\n"
            "🛡️ Under 18\n"
            "⚔️ 18+\n\n"
            "You can only choose once.\n\n"
            "**Shinzou wo Sasageyo! ❤️⚔️**"
        ),

        color=discord.Color.red()
    )


    await ctx.send(
        embed=embed,
        view=AgeVerificationView()
    )


# ==================================================
# SETUP CADET REGISTRY
# ==================================================

@bot.command()
async def setupcadet(ctx):

    if not is_owner_or_admin(
        ctx.author
    ):

        return


    if ctx.channel.name != CADET_CHANNEL:

        await ctx.send(
            "❌ Use this command in the Cadet Registry channel."
        )

        return


    embed = discord.Embed(
        title="⚔️ CADET REGISTRY ⚔️",

        description=(
            "Choose your division.\n\n"
            "🌹 Stationary Troops\n"
            "🌀 Scouting Legion\n"
            "🐴 Military Police\n\n"
            "You can only choose one.\n\n"
            "**Dedicate your heart! ❤️⚔️**"
        ),

        color=discord.Color.red()
    )


    await ctx.send(
        embed=embed,
        view=CadetRegistryView()
    )


# ==================================================
# MESSAGE EVENT
# ==================================================

@bot.event
async def on_message(message):

    if message.author.bot:

        return


    # ==================================================
    # NICKNAME REQUEST SYSTEM
    # ==================================================

    if message.channel.name == NICKNAME_REQUEST_CHANNEL:


        if bot.user in message.mentions:


            text = message.content


            text = text.replace(
                f"<@{bot.user.id}>",
                ""
            )


            text = text.replace(
                f"<@!{bot.user.id}>",
                ""
            )


            text = text.strip()


            prefix = "sys request nn"


            if text.lower().startswith(prefix):


                nickname = text[
                    len(prefix):
                ].strip()


                await create_nickname_request(
                    message,
                    nickname
                )


                try:

                    await message.delete()


                except discord.Forbidden:

                    pass


                return


    # ==================================================
    # ANNOUNCEMENT SYSTEM
    # ==================================================

    if bot.user in message.mentions:


        if is_owner_or_admin(
            message.author
        ):


            text = message.content


            text = text.replace(
                f"<@{bot.user.id}>",
                ""
            )


            text = text.replace(
                f"<@!{bot.user.id}>",
                ""
            )


            text = text.strip()


            embed = discord.Embed(
                description=text if text else " ",
                color=discord.Color.red()
            )


            files = []
            image_added = False


            for attachment in message.attachments:


                file = await attachment.to_file()

                files.append(file)


                if (
                    not image_added
                    and attachment.content_type
                    and attachment.content_type.startswith(
                        "image/"
                    )
                ):


                    embed.set_image(
                        url=(
                            f"attachment://"
                            f"{attachment.filename}"
                        )
                    )


                    image_added = True


            try:

                await message.delete()


            except discord.Forbidden:

                pass


            await message.channel.send(
                embed=embed,
                files=files
            )


            return


    # ==================================================
    # MESSAGE POINTS
    # ==================================================

    excluded_channels = [
        AGE_CHANNEL,
        CADET_CHANNEL,
        POINTS_CHANNEL,
        NICKNAME_REQUEST_CHANNEL
    ]


    if message.channel.name not in excluded_channels:


        cursor.execute("""
            SELECT team
            FROM cadets
            WHERE user_id = ?
        """, (
            message.author.id,
        ))


        result = cursor.fetchone()


        if result:


            current_time = datetime.now().timestamp()


            cursor.execute("""
                SELECT last_message
                FROM message_cooldowns
                WHERE user_id = ?
            """, (
                message.author.id,
            ))


            cooldown = cursor.fetchone()


            can_receive = False


            if not cooldown:

                can_receive = True


            elif (
                current_time - cooldown[0]
                >= POINT_COOLDOWN
            ):

                can_receive = True


            if can_receive:


                await add_points(
                    message.author,
                    1
                )


                cursor.execute("""
                    INSERT INTO message_cooldowns
                    (
                        user_id,
                        last_message
                    )

                    VALUES (?, ?)

                    ON CONFLICT(user_id)
                    DO UPDATE SET
                    last_message = excluded.last_message
                """, (
                    message.author.id,
                    current_time
                ))


                connection.commit()


    # Keep commands working
    await bot.process_commands(
        message
    )


# ==================================================
# PING
# ==================================================

@bot.command()
async def ping(ctx):

    await ctx.send(
        "Pong! 🏓"
    )


# ==================================================
# START BOT
# ==================================================

bot.run(os.getenv("DISCORD_TOKEN"))
