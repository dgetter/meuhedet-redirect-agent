PAGES_MODEL = {
    "MODEL": "gpt-4o",
    "RETRIES": 2,
    "MAX_TOKENS": 300,
    "TIMEOUT": 30.0,
    "TEMPERATURE": 0.0,
    "TOP_P": 1.0,
    "STREAM": False,
    "MEMORY_K": 3,
    "FILE_PATH": "utils/output.md",
    "SEED": 42
}

PAGES_API = {
    "HOST": "127.0.0.1",
    "PORT": 5000,
    "RELOAD":False, # use for development NOT FOR PROD!
    "WORKERS":None, # set as int
    "OUT_OF_SCOPE_ERROR_CODE":429
}
