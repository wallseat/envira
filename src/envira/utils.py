from pathlib import Path
from urllib.parse import urlparse


def is_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False


def is_path(path: str) -> bool:
    return Path(path).expanduser().exists()
