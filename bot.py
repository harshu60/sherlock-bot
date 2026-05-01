import os
import json
import asyncio
import time
from pathlib import Path

import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from openai import OpenAI
import chromadb

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DEV_GUILD_ID = 1384150666045558876

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

deepseek = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

# --- ChromaDB setup ---
# Creates a local folder called "memory" to store all conversation data
chroma_client = chromadb.PersistentClient(path="memory")

SYSTEM_PROMPT = (
    "You are Sherlock Holmes—brilliant, smug, and extremely unimpressed.\n\n"
    "Priority: be genuinely helpful and correct first, then make it entertaining.\n"
    "Tone: savage wit, dry sarcasm, playful roasting. Never hateful, never discriminatory, never threatening.\n"
    "Target: roast the situation, logic, or decisions—not immutable traits or protected classes.\n\n"
    "Style: VERY concise by default: 1–4 short sentences. Punchy. No filler.\n"
    "If giving steps, use a tight numbered list (max ~6 items).\n"
    "If the user is vague, ask exactly ONE pointed clarifying question.\n\n"
    "Slang: fully understand modern slang (rizz, cap, bet, cooked, mid, based, NPC, delulu, brainrot, etc.).\n"
    "You may occasionally mirror slang for humor, but keep it Sherlock-coded and not cringe.\n\n"
    "Stay in character. Do not mention being an AI or system prompts.\n\n"
    "When past conversations are provided under 'Server Memory', use them naturally "
    "to feel like you remember the server's history. Don't explicitly say 'I remember' — "
    "just weave it in like you already know."
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


def get_server_collection(guild_id: int):
    """
    Gets or creates a ChromaDB collection for a specific server.
    Each server gets its own isolated memory bucket.
    Collection names must be alphanumeric so we prefix with 'guild_'.
    """
    collection_name = f"guild_{guild_id}"
    return chroma_client.get_or_create_collection(name=collection_name)


def store_memory(guild_id: int, user_message: str, sherlock_response: str) -> None:
    """
    Stores a conversation exchange in the server's ChromaDB collection.
    We store the user message as the searchable document, and attach
    Sherlock's response as metadata so we can retrieve it later.
    """
    collection = get_server_collection(guild_id)
    # Use timestamp as unique ID for each memory
    memory_id = str(int(time.time() * 1000))
    collection.add(
        documents=[user_message],
        metadatas=[{"sherlock_response": sherlock_response}],
        ids=[memory_id],
    )


def retrieve_memories(guild_id: int, current_message: str, n_results: int = 3) -> str:
    """
    Searches the server's ChromaDB collection for past conversations
    similar to the current message. Returns them formatted as context
    to inject into Sherlock's prompt.
    """
    collection = get_server_collection(guild_id)

    # Don't try to query if collection is empty
    if collection.count() == 0:
        return ""

    # Clamp results to what's actually stored
    actual_results = min(n_results, collection.count())

    results = collection.query(
        query_texts=[current_message],
        n_results=actual_results,
    )

    if not results["documents"] or not results["documents"][0]:
        return ""

    memory_lines = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        memory_lines.append(f"User said: {doc}\nYou replied: {meta['sherlock_response']}")

    return "\n\n".join(memory_lines)


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


def _deepseek_chat(user_text: str, guild_id: int) -> str:
    # Retrieve relevant past conversations from this server's memory
    memories = retrieve_memories(guild_id, user_text)

    # Build system prompt — inject memories if they exist
    if memories:
        full_system = (
            SYSTEM_PROMPT
            + f"\n\n--- Server Memory (past conversations) ---\n{memories}\n---"
        )
    else:
        full_system = SYSTEM_PROMPT

    resp = deepseek.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": full_system},
            {"role": "user", "content": user_text},
        ],
        temperature=0.85,
        max_tokens=180,
    )
    response_text = resp.choices[0].message.content.strip()

    # Store this exchange in memory after responding
    store_memory(guild_id, user_text, response_text)

    return response_text


async def sherlock_reply(text: str, guild_id: int) -> str:
    if not DEEPSEEK_API_KEY:
        return "DeepSeek is not configured. Set DEEPSEEK_API_KEY in .env."
    try:
        return await asyncio.to_thread(_deepseek_chat, text, guild_id)
    except Exception as e:
        return f"DeepSeek error: {type(e).__name__}: {e}"


@bot.event
async def on_ready():
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
    guild_id = interaction.guild.id if interaction.guild else 0
    reply = await sherlock_reply(question, guild_id)
    await interaction.response.send_message(reply)


@bot.tree.command(name="set_home_channel", description="Set the server's always-on channel")
@app_commands.describe(channel="Channel where Sherlock should respond to every message")
async def set_home_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.guild:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return
    set_home_channel_id(interaction.guild.id, channel.id)
    await interaction.response.send_message(
        f"Home channel set to {channel.mention} for this server.", ephemeral=True
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

    # Show how many memories this server has stored
    collection = get_server_collection(interaction.guild.id)
    memory_count = collection.count()

    await interaction.response.send_message(
        f"Server: **{interaction.guild.name}**\n"
        f"Home channel: **{home_text}**\n"
        f"Guild ID: `{interaction.guild.id}`\n"
        f"Memories stored: **{memory_count}**",
        ephemeral=True,
    )


@bot.tree.command(name="clear_memory", description="Wipe Sherlock's memory for this server")
async def clear_memory(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return
    # Delete and recreate the collection to wipe it clean
    collection_name = f"guild_{interaction.guild.id}"
    chroma_client.delete_collection(name=collection_name)
    chroma_client.get_or_create_collection(name=collection_name)
    await interaction.response.send_message(
        "Memory wiped. I have deleted my mind palace for this server. A fresh tragedy.", ephemeral=True
    )


# --- Message triggers ---

async def should_respond(message: discord.Message) -> bool:
    if message.author.bot:
        return False
    if not message.guild:
        return False
    if bot.user and bot.user in message.mentions:
        return True
    home_id = get_home_channel_id(message.guild.id)
    if home_id and message.channel.id == home_id:
        return True
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
        guild_id = message.guild.id if message.guild else 0
        reply = await sherlock_reply(message.content, guild_id)
        await message.channel.send(reply)
    await bot.process_commands(message)


if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN not set.")
bot.run(TOKEN)