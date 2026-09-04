import os

from dotenv import load_dotenv


load_dotenv()


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set in the environment.")

OPENAI_BASE_URL = os.getenv(
    "OPENAI_BASE_URL",
    "https://api.openai.com/v1",
)

PLANNER_MODEL = os.getenv("PLANNER_MODEL", "gpt-5.5")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gpt-image-2")

MAX_PLAN_RETRIES = int(os.getenv("MAX_PLAN_RETRIES", "2"))
MAX_REPAIR_ATTEMPTS = int(os.getenv("MAX_REPAIR_ATTEMPTS", "3"))

DEFAULT_FPS = int(os.getenv("DEFAULT_FPS", "30"))

