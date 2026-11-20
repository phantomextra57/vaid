
import discord
from discord.ext import commands
import sqlite3
import random
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

# ================= CONFIG =================

WELCOME_CHANNEL_ID = 123456789012345678
TICKET_CATEGORY_ID = 123456789012345678
STAFF_ROLE_ID = 123456789012345678
APPLICATION_CHANNEL_ID = 123456789012345678

# اكتب أسئلة التقديم هنا
QUESTIONS = [
    "ما اسمك؟",
    "كم عمرك؟",
    "ما خبرتك في المجال؟",
    "لماذا تريد الانضمام إلينا؟",
    "كم ساعة تستطيع التواجد يومياً؟"
]

# ==========================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

db = sqlite3.connect("bot.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS levels (
    user_id INTEGER PRIMARY KEY,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 0
)
""")
db.commit()


# ================ WELCOME =================

@bot.event
async def on_member_join(member):

    channel = bot.get_channel(WELCOME_CHANNEL_ID)

    if channel is None:
        return

    embed = discord.Embed(
        title="أهلاً وسهلاً بك ❤️",
        description=f"""
مرحباً {member.mention} في سيرفرنا!

نتمنى لك وقتاً ممتعاً معنا.
أنت العضو رقم {member.guild.member_count}
""",
        color=discord.Color.blurple()
    )

    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_image(url="https://i.imgur.com/your-image.png")
    embed.set_footer(text=member.guild.name)

    await channel.send(embed=embed)


# ================= LEVELS =================

def get_xp_needed(level):
    return 100 + (level * 50)


@bot.event
async def on_message(message):

    if message.author.bot:
        return

    user_id = message.author.id

    cursor.execute(
        "SELECT xp, level FROM levels WHERE user_id=?",
        (user_id,)
    )

    data = cursor.fetchone()

    if data is None:
        xp, level = 0, 0
        cursor.execute(
            "INSERT INTO levels VALUES (?, ?, ?)",
            (user_id, xp, level)
        )
    else:
        xp, level = data

    xp += random.randint(10, 20)

    needed = get_xp_needed(level)

    if xp >= needed:
        xp -= needed
        level += 1

        await message.channel.send(
            f"🎉 مبروك {message.author.mention} وصلت للمستوى {level}!"
        )

    cursor.execute(
        "UPDATE levels SET xp=?, level=? WHERE user_id=?",
        (xp, level, user_id)
    )

    db.commit()

    await bot.process_commands(message)


@bot.command(name="rank")
async def rank(ctx):

    cursor.execute(
        "SELECT xp, level FROM levels WHERE user_id=?",
        (ctx.author.id,)
    )

    data = cursor.fetchone()

    if data is None:
        xp, level = 0, 0
    else:
        xp, level = data

    embed = discord.Embed(
        title="🏆 مستواك",
        description=f"""
العضو: {ctx.author.mention}
المستوى: **{level}**
الخبرة: **{xp}/{get_xp_needed(level)}**
""",
        color=discord.Color.gold()
    )

    await ctx.send(embed=embed)


# ================= TICKETS =================

class TicketView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="فتح تذكرة",
        emoji="🎫",
        style=discord.ButtonStyle.green,
        custom_id="open_ticket"
    )
    async def open_ticket(self, interaction, button):

        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)

        if category is None:
            await interaction.response.send_message(
                "قسم التذاكر غير موجود. راجع الإعدادات.",
                ephemeral=True
            )
            return

        existing = discord.utils.get(
            category.text_channels,
            name=f"ticket-{interaction.user.id}"
        )

        if existing:
            await interaction.response.send_message(
                f"لديك تذكرة مفتوحة بالفعل: {existing.mention}",
                ephemeral=True
            )
            return

        staff_role = guild.get_role(STAFF_ROLE_ID)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False
            ),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True
            )
        }

        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )

        channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.id}",
            category=category,
            overwrites=overwrites
        )

        embed = discord.Embed(
            title="🎫 تذكرتك مفتوحة",
            description=(
                f"مرحباً {interaction.user.mention}\n"
                "اكتب مشكلتك وسيقوم فريق الإدارة بمساعدتك."
            ),
            color=discord.Color.green()
        )

        await channel.send(
            embed=embed,
            view=CloseTicketView()
        )

        await interaction.response.send_message(
            f"تم فتح تذكرتك: {channel.mention}",
            ephemeral=True
        )


class CloseTicketView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="إغلاق التذكرة",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="close_ticket"
    )
    async def close_ticket(self, interaction, button):

        await interaction.response.send_message(
            "سيتم إغلاق التذكرة خلال ثوانٍ."
        )

        await asyncio.sleep(3)
        await interaction.channel.delete()


@bot.command()
@commands.has_permissions(administrator=True)
async def ticketpanel(ctx):

    embed = discord.Embed(
        title="🎫 نظام التذاكر",
        description="اضغط على الزر بالأسفل لفتح تذكرة مع الإدارة.",
        color=discord.Color.blurple()
    )

    await ctx.send(embed=embed, view=TicketView())


# ================= APPLICATIONS =================

class ApplicationView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="تقديم طلب",
        emoji="📝",
        style=discord.ButtonStyle.primary,
        custom_id="start_application"
    )
    async def apply(self, interaction, button):

        await interaction.response.send_message(
            "تم إرسال رسالة خاصة لك لبدء التقديم.",
            ephemeral=True
        )

        try:
            await run_application(interaction.user, interaction.guild)
        except discord.Forbidden:
            await interaction.followup.send(
                "افتح الرسائل الخاصة حتى يستطيع البوت سؤالك.",
                ephemeral=True
            )


async def run_application(user, guild):

    answers = []

    dm = await user.create_dm()

    await dm.send(
        "📝 **بدأ التقديم!**\n"
        "أجب عن الأسئلة التالية واحداً تلو الآخر."
    )

    for number, question in enumerate(QUESTIONS, start=1):

        await dm.send(f"**السؤال {number}:** {question}")

        def check(message):
            return (
                message.author.id == user.id
                and message.channel.id == dm.id
            )

        try:
            answer = await bot.wait_for(
                "message",
                check=check,
                timeout=300
            )

            answers.append((question, answer.content))

        except asyncio.TimeoutError:
            await dm.send("انتهى وقت التقديم. يمكنك المحاولة لاحقاً.")
            return

    channel = bot.get_channel(APPLICATION_CHANNEL_ID)

    if channel is None:
        await dm.send("حدث خطأ في إعدادات روم التقديم.")
        return

    embed = discord.Embed(
        title="📋 تقديم جديد",
        description=f"المتقدم: {user.mention}",
        color=discord.Color.blue()
    )

    for question, answer in answers:
        embed.add_field(
            name=question,
            value=answer[:1024],
            inline=False
        )

    await channel.send(embed=embed)
    await dm.send("✅ تم استلام تقديمك بنجاح!")


@bot.command()
@commands.has_permissions(administrator=True)
async def applypanel(ctx):

    embed = discord.Embed(
        title="📝 التقديم للإدارة",
        description="اضغط على الزر بالأسفل وابدأ الإجابة عن الأسئلة.",
        color=discord.Color.blue()
    )

    await ctx.send(embed=embed, view=ApplicationView())


# ================= READY =================

@bot.event
async def on_ready():

    bot.add_view(TicketView())
    bot.add_view(CloseTicketView())
    bot.add_view(ApplicationView())

    print(f"Bot is online: {bot.user}")


if not TOKEN:
    raise RuntimeError("ضع BOT_TOKEN في ملف .env")

bot.run(TOKEN)
