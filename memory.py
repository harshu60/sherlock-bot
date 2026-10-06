import time

import chromadb


class ConversationMemory:
    def __init__(self, path: str) -> None:
        self.client = chromadb.PersistentClient(path=path)

    def _collection(self, guild_id: int):
        return self.client.get_or_create_collection(name=f"guild_{guild_id}")

    def store(self, guild_id: int, user_message: str, response: str) -> None:
        self._collection(guild_id).add(
            documents=[user_message],
            metadatas=[{"sherlock_response": response}],
            ids=[str(int(time.time() * 1000))],
        )

    def retrieve(self, guild_id: int, message: str, limit: int = 3) -> str:
        collection = self._collection(guild_id)
        count = collection.count()
        if count == 0:
            return ""

        results = collection.query(
            query_texts=[message],
            n_results=min(limit, count),
        )
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        return "\n\n".join(
            f"User said: {document}\nYou replied: {metadata['sherlock_response']}"
            for document, metadata in zip(documents, metadatas)
        )

    def count(self, guild_id: int) -> int:
        return self._collection(guild_id).count()

    def clear(self, guild_id: int) -> None:
        self.client.delete_collection(name=f"guild_{guild_id}")
        self._collection(guild_id)
