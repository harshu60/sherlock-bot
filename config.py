import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    discord_token: str
    dev_guild_ids: tuple[int, ...]
    deepseek_api_key: str | None
    deepseek_base_url: str
    deepseek_model: str
    memory_path: str = "memory"
    settings_path: str = "data/servers.json"

    @classmethod
    def from_env(cls) -> "AppConfig":
        load_dotenv()
        return cls(
            discord_token=os.getenv("DISCORD_BOT_TOKEN", "").strip(),
            dev_guild_ids=(
                1384150666045558876,
                1497567983978156154,
            ),
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
            deepseek_base_url=os.getenv(
                "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
            ),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        )

    def validate(self) -> None:
        if not self.discord_token:
            raise RuntimeError("DISCORD_BOT_TOKEN not set.")
