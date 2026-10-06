import discord
from discord import app_commands
from discord.ext import commands

from config import AppConfig
from memory import ConversationMemory
from settings import ServerSettings
from sherlock import SherlockService


class SherlockBot(commands.Bot):
    def __init__(
        self,
        config: AppConfig,
        settings: ServerSettings,
        memory: ConversationMemory,
        sherlock: SherlockService,
    ) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.config = config
        self.settings = settings
        self.memory = memory
        self.sherlock = sherlock
        self._register_commands()

    def _register_commands(self) -> None:
        self.tree.add_command(
            app_commands.Command(name="ping", description="Check if the bot is alive", callback=self.ping)
        )
        sherlock_command = app_commands.Command(
            name="sherlock", description="Ask Sherlock a question", callback=self.sherlock_command
        )
        app_commands.describe(question="What should Sherlock analyze?")(sherlock_command)
        self.tree.add_command(sherlock_command)
        self.tree.add_command(
            app_commands.Command(
                name="set_home_channel",
                description="Set the server's always-on channel",
                callback=self.set_home_channel,
            )
        )
        self.tree.add_command(
            app_commands.Command(
                name="disable_home_channel",
                description="Disable the always-on channel for this server",
                callback=self.disable_home_channel,
            )
        )
        self.tree.add_command(
            app_commands.Command(
                name="status",
                description="Show current Sherlock bot configuration",
                callback=self.status,
            )
        )
        self.tree.add_command(
            app_commands.Command(
                name="clear_memory",
                description="Wipe Sherlock's memory for this server",
                callback=self.clear_memory,
            )
        )

    async def setup_hook(self) -> None:
        for guild_id in self.config.dev_guild_ids:
            guild = discord.Object(id=guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)

    async def on_ready(self) -> None:
        print(f"Logged in as {self.user} (id={self.user.id})")
        print(
            "Slash commands synced to guilds: "
            f"{', '.join(str(guild_id) for guild_id in self.config.dev_guild_ids)}."
        )

    async def ping(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("pong", ephemeral=True)

    async def sherlock_command(
        self, interaction: discord.Interaction, question: str
    ) -> None:
        guild_id = interaction.guild.id if interaction.guild else 0
        reply = await self.sherlock.reply(question, guild_id)
        await interaction.response.send_message(reply)

    async def set_home_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        if not interaction.guild:
            await self._require_guild(interaction)
            return
        self.settings.set_home_channel_id(interaction.guild.id, channel.id)
        await interaction.response.send_message(
            f"Home channel set to {channel.mention} for this server.", ephemeral=True
        )

    async def disable_home_channel(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await self._require_guild(interaction)
            return
        self.settings.set_home_channel_id(interaction.guild.id, None)
        await interaction.response.send_message(
            "Home channel disabled for this server.", ephemeral=True
        )

    async def status(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await self._require_guild(interaction)
            return
        home_id = self.settings.get_home_channel_id(interaction.guild.id)
        home_text = f"<#{home_id}>" if home_id else "Not set"
        await interaction.response.send_message(
            f"Server: **{interaction.guild.name}**\n"
            f"Home channel: **{home_text}**\n"
            f"Guild ID: `{interaction.guild.id}`\n"
            f"Memories stored: **{self.memory.count(interaction.guild.id)}**",
            ephemeral=True,
        )

    async def clear_memory(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await self._require_guild(interaction)
            return
        self.memory.clear(interaction.guild.id)
        await interaction.response.send_message(
            "Memory wiped. I have deleted my mind palace for this server. A fresh tragedy.",
            ephemeral=True,
        )

    async def _require_guild(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "This command can only be used in a server.", ephemeral=True
        )

    async def should_respond(self, message: discord.Message) -> bool:
        if message.author.bot or not message.guild:
            return False
        if self.user and self.user in message.mentions:
            return True
        home_channel_id = self.settings.get_home_channel_id(message.guild.id)
        if home_channel_id and message.channel.id == home_channel_id:
            return True
        if message.reference and self.user:
            referenced = message.reference.resolved
            if isinstance(referenced, discord.Message):
                return referenced.author.id == self.user.id
            if message.reference.message_id:
                try:
                    referenced = await message.channel.fetch_message(
                        message.reference.message_id
                    )
                except (
                    discord.NotFound,
                    discord.Forbidden,
                    discord.HTTPException,
                    AttributeError,
                ):
                    referenced = None
                return bool(referenced and referenced.author.id == self.user.id)
        return False

    async def on_message(self, message: discord.Message) -> None:
        if await self.should_respond(message):
            guild_id = message.guild.id if message.guild else 0
            reply = await self.sherlock.reply(message.content, guild_id)
            await message.channel.send(reply)
        await self.process_commands(message)


def create_bot(config: AppConfig | None = None) -> SherlockBot:
    config = config or AppConfig.from_env()
    memory = ConversationMemory(config.memory_path)
    return SherlockBot(
        config=config,
        settings=ServerSettings(config.settings_path),
        memory=memory,
        sherlock=SherlockService(
            api_key=config.deepseek_api_key,
            base_url=config.deepseek_base_url,
            model=config.deepseek_model,
            memory=memory,
        ),
    )


def main() -> None:
    config = AppConfig.from_env()
    config.validate()
    bot = create_bot(config)
    try:
        bot.run(config.discord_token)
    except discord.LoginFailure as exc:
        raise RuntimeError(
            "Discord rejected DISCORD_BOT_TOKEN. Generate a new token in the "
            "Discord Developer Portal, update .env, and restart the bot. "
            "Use the bot token itself, without a 'Bot ' prefix."
        ) from exc


if __name__ == "__main__":
    main()
