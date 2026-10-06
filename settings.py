import json
from pathlib import Path


class ServerSettings:
    def __init__(self, settings_path: str | Path) -> None:
        self.path = Path(settings_path)

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid server settings file: {self.path}") from exc

    def _save(self, settings: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(settings, indent=2), encoding="utf-8")

    def get_home_channel_id(self, guild_id: int) -> int | None:
        entry = self._load().get(str(guild_id), {})
        return entry.get("home_channel_id")

    def set_home_channel_id(self, guild_id: int, channel_id: int | None) -> None:
        settings = self._load()
        guild_settings = settings.setdefault(str(guild_id), {})
        if channel_id is None:
            guild_settings.pop("home_channel_id", None)
        else:
            guild_settings["home_channel_id"] = channel_id
        self._save(settings)
