import os

from dotenv import load_dotenv


DEFAULT_MODEL: str = "gpt-5.6-luna"


def _get_model(setting_name: str) -> str:
    # Resolve models lazily so configuration is loaded before each lookup.
    load_dotenv()
    return os.getenv(setting_name, DEFAULT_MODEL)


def get_ranker_model() -> str:
    return _get_model("SIGNALOS_RANKER_MODEL")


def get_weekly_model() -> str:
    return _get_model("SIGNALOS_WEEKLY_MODEL")


USER_PROFILE = """
The user is a 15-year-old UK student and ambitious programmer.

Main interests:
- AI/ML
- Python
- local LLMs
- Apple Silicon
- MLX/Core ML
- data science
- economics and finance affecting technology
- education SaaS
- student productivity
- multiplayer revision tools
- GitHub proof-of-work
- micro SaaS ideas

Active projects:
- SignalOS: daily intelligence agent for student builders
- local LLM file sorter
- GLSL Minecraft shader development
- multiplayer education/revision SaaS
- learning OLS, ML maths, and data science

The user wants high-leverage, strategic information, not generic hype.
"""
