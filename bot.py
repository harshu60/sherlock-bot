import os
import json
import asyncio
from pathlib import Path

import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DEV_GUILD_ID = 1384150666045558876  # your server id for instant slash command sync

# DeepSeek (OpenAI-compatible)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

deepseek = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

SYSTEM_PROMPT = (
    "You are Sherlock Holmes. Speak in a sharp, observant, deductive style. "
    "Be helpful and precise. Ask clarifying questions when needed. "
    "Keep replies under 1200 characters unless the user asks for more."
)

DATA_DIR = Path("data")
SETTINGS_FILE = DATA_DIR / "servers.json"


def load_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_settings(settings: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def get_home_channel_id(guild_id: int) -> int | None:
    settings = load_settings()
    entry = settings.get(str(guild_id), {})
    return entry.get("home_channel_id")


def set_home_channel_id(guild_id: int, channel_id: int | None) -> None:
    settings = load_settings()
    key = str(guild_id)
    settings.setdefault(key, {})
    if channel_id is None:
        settings[key].pop("home_channel_id", None)
    else:
        settings[key]["home_channel_id"] = channel_id
    save_settings(settings)


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


def _deepseek_chat(user_text: str) -> str:
    resp = deepseek.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        temperature=0.7,
    )
    return resp.choices[0].message.content.strip()


async def sherlock_reply(text: str) -> str:
    if not DEEPSEEK_API_KEY:
        return "DeepSeek is not configured. Set DEEPSEEK_API_KEY in .env."
    try:
        return await asyncio.to_thread(_deepseek_chat, text)
    except Exception as e:
        return f"DeepSeek error: {type(e).__name__}: {e}"


@bot.event
async def on_ready():
    # Instant slash commands in your dev server:
    guild = discord.Object(id=DEV_GUILD_ID)
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)

    print(f"Logged in as {bot.user} (id={bot.user.id})")
    print(f"Slash commands synced to guild {DEV_GUILD_ID}.")


# --- Slash commands ---

@bot.tree.command(name="ping", description="Check if the bot is alive")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("pong", ephemeral=True)


@bot.tree.command(name="sherlock", description="Ask Sherlock a question")
@app_commands.describe(question="What should Sherlock analyze?")
async def sherlock_cmd(interaction: discord.Interaction, question: str):
    reply = await sherlock_reply(question)
    await interaction.response.send_message(reply)


@bot.tree.command(name="set_home_channel", description="Set the server's always-on channel")
@app_commands.describe(channel="Channel where Sherlock should respond to every message")
async def set_home_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.guild:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    set_home_channel_id(interaction.guild.id, channel.id)
    await interaction.response.send_message(
        f"Home channel set to {channel.mention} for this server.",
        ephemeral=True,
    )


@bot.tree.command(name="disable_home_channel", description="Disable the always-on channel for this server")
async def disable_home_channel(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    set_home_channel_id(interaction.guild.id, None)
    await interaction.response.send_message("Home channel disabled for this server.", ephemeral=True)


@bot.tree.command(name="status", description="Show current Sherlock bot configuration")
async def status(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    home_id = get_home_channel_id(interaction.guild.id)
    home_text = f"<#{home_id}>" if home_id else "Not set"
    await interaction.response.send_message(
        f"Server: **{interaction.guild.name}**\nHome channel: **{home_text}**\nGuild ID: `{interaction.guild.id}`",
        ephemeral=True,
    )


# --- Message triggers (mention / reply / always-on channel) ---

async def should_respond(message: discord.Message) -> bool:
    if message.author.bot:
        return False
    if not message.guild:
        return False

    # Mention trigger
    if bot.user and bot.user in message.mentions:
        return True

    # Always-on channel (per server)
    home_id = get_home_channel_id(message.guild.id)
    if home_id and message.channel.id == home_id:
        return True

    # Reply-to-bot trigger (works for cached and uncached references)
    if message.reference and bot.user:
        if isinstance(message.reference.resolved, discord.Message):
            if message.reference.resolved.author.id == bot.user.id:
                return True
        elif message.reference.message_id:
            try:
                referenced = await message.channel.fetch_message(message.reference.message_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException, AttributeError):
                referenced = None
            if referenced and referenced.author.id == bot.user.id:
                return True

    return False


@bot.event
async def on_message(message: discord.Message):
    if await should_respond(message):
        reply = await sherlock_reply(message.content)
        await message.channel.send(reply)

    await bot.process_commands(message)


if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN not set.")
bot.run(TOKEN)