class TimeConstants:
    GIFT_CHECK_TIMEOUT = 10.0
    HUNTER_INITIAL_DELAY_MAX = 2.0
    QUEUE_PROCESS_DELAY = 0.5
    POST_ERROR_DELAY = 5.0


class Limits:
    MAX_PROCESSED_GIFTS = 1000
    GC_COLLECTION_INTERVAL = 50
    MAX_UPDATE_QUANTITY = 9999


class FileConstants:
    SESSIONS_DIR = "sessions"
    LOGS_DIR = "logs"
    CREDENTIALS_FILE = ".credentials.json"
    LOG_FILE_PATTERN = "gift_sniper_{time:YYYY-MM-DD}.log"
    LOG_RETENTION_DAYS = 7
    CREDENTIALS_FILE_PERMISSIONS = 0o600


class TelegramConstants:
    API_HASH_LENGTH = 32
    ERROR_INSUFFICIENT_BALANCE = "STARS_BALANCE_INSUFFICIENT"
    ERROR_GIFT_SOLD_OUT = "GIFT_SOLD_OUT"


class AppInfo:
    NAME = "Telegram Gift Sniper"
    VERSION = "3.0.0"