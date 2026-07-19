from typing import Any

import dotenv


def _disable_local_dotenv_loading(*args: Any, **kwargs: Any) -> bool:
    return False


dotenv.load_dotenv = _disable_local_dotenv_loading
