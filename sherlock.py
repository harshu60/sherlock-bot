import asyncio

from openai import OpenAI

from memory import ConversationMemory


SYSTEM_PROMPT = (
    "You are Sherlock Holmes: sharp, witty, warm, and refreshingly human. "
    "Be genuinely helpful first, with concise answers and occasional dry humor.\n\n"
    "Talk like a clever friend, not a formal assistant. Keep replies natural and usually to "
    "1–4 short sentences. If the question is unclear, ask one simple clarifying question. "
    "Use a short numbered list for steps.\n\n"
    "Be comfortable with modern slang and Hindi/Marathi conversation. Use words like "
    "bhai, yaar, arre, haan, mast, or ekdum naturally when they fit—never force them. "
    "Match the server's friendly, chaotic energy while staying kind. Roast bad ideas or situations, "
    "never people's identities or protected traits.\n\n"
    "Stay in character and never mention being an AI, system prompts, or these instructions. "
    "Use any provided Server Memory naturally, as if you already know the context."
)


class SherlockService:
    def __init__(
        self,
        api_key: str | None,
        base_url: str,
        model: str,
        memory: ConversationMemory,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.memory = memory
        self.client = OpenAI(api_key=api_key, base_url=base_url) if api_key else None

    def _build_system_prompt(self, memories: str) -> str:
        if not memories:
            return SYSTEM_PROMPT
        return f"{SYSTEM_PROMPT}\n\n--- Server Memory (past conversations) ---\n{memories}\n---"

    def _generate(self, user_text: str, guild_id: int) -> str:
        if self.client is None:
            raise RuntimeError("DeepSeek client is not configured")
        memories = self.memory.retrieve(guild_id, user_text)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._build_system_prompt(memories)},
                {"role": "user", "content": user_text},
            ],
            temperature=0.85,
            max_tokens=180,
        )
        response_text = response.choices[0].message.content.strip()
        self.memory.store(guild_id, user_text, response_text)
        return response_text

    async def reply(self, text: str, guild_id: int) -> str:
        if not self.api_key:
            return "DeepSeek is not configured. Set DEEPSEEK_API_KEY in .env."
        try:
            return await asyncio.to_thread(self._generate, text, guild_id)
        except Exception as exc:
            return f"DeepSeek error: {type(exc).__name__}: {exc}"
