DEFAULT_LOGGING = {
    "version": 1,
    "formatters": {
        "long": {
            "format": "%(asctime)-24s %(levelname)-8s [%(name)s] %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "long",
            "stream": "ext://sys.stdout"
        }
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO"
    },
    "loggers": {
        "asyncio": {
            "level": "WARNING"
        },
        "slixmpp": {
            "level": "WARNING"
        },
        "aiohttp.web": {
            "level": "WARNING"
        }
    },
    "disable_existing_loggers": False
}
