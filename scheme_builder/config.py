from configparser import ConfigParser
from pathlib import Path

CONFIG_FILE = Path(__file__).resolve().parent.parent / "config.ini"

config = ConfigParser(interpolation=None)
if not config.read(CONFIG_FILE, encoding="utf-8"):
    raise RuntimeError(f"Не найден файл конфигурации: {CONFIG_FILE}")


def _items(section: str, option: str) -> tuple[str, ...]:
    items = tuple(
        item.strip()
        for item in config.get(section, option).split(",")
        if item.strip()
    )
    if not items:
        raise RuntimeError(f"Параметр {section}.{option} не должен быть пустым.")
    return items


WINDOW_WIDTH = config.getint("window", "width")
WINDOW_HEIGHT = config.getint("window", "height")
MIN_WINDOW_WIDTH = config.getint("window", "min_width")
MIN_WINDOW_HEIGHT = config.getint("window", "min_height")

METRIC_TYPES = _items("metrics", "types")
METRIC_DIMENSIONS = _items("metrics", "dimensions")
DEFAULT_QUERY_INTERVAL = config.getint("metrics", "default_query_interval")
MIN_QUERY_INTERVAL = config.getint("metrics", "min_query_interval")
MAX_QUERY_INTERVAL = config.getint("metrics", "max_query_interval")

if "none" not in METRIC_DIMENSIONS:
    raise RuntimeError("Список metrics.dimensions должен содержать none.")
if not MIN_QUERY_INTERVAL <= DEFAULT_QUERY_INTERVAL <= MAX_QUERY_INTERVAL:
    raise RuntimeError("Период опроса по умолчанию находится вне допустимого диапазона.")
