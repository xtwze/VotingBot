import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_IDS: list[int] = [
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
]
CHANNEL_ID: str = os.getenv("CHANNEL_ID", "@your_channel_username")  # или -1001234567890 (числовой ID)