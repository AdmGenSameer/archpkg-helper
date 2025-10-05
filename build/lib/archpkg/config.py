# config.py
"""Configuration constants and settings for the Universal Package Helper CLI."""

# Timeout values for different package managers (in seconds)
TIMEOUTS = {
    'aur': 15,
    'pacman': 30,
    'apt': 30,
    'dnf': 45,  # DNF can be slower
    'flatpak': 30,
    'snap': 30,
    'command_check': 5
}

# Keywords used for filtering/scoring
JUNK_KEYWORDS = ["icon", "dummy", "meta", "symlink", "wrap", "material", "launcher", "unionfs"]
LOW_PRIORITY_KEYWORDS = ["extension", "plugin", "helper", "daemon", "patch", "theme"]
BOOST_KEYWORDS = ["editor", "browser", "ide", "official", "gui", "android", "studio", "stable", "canary", "beta"]

# Supported platforms
SUPPORTED_PLATFORMS = ["arch", "debian", "ubuntu", "linuxmint", "fedora", "manjaro"]

# Distribution mapping
DISTRO_MAP = {
    "arch": "arch",
    "manjaro": "arch", 
    "endeavouros": "arch",
    "arco": "arch",
    "garuda": "arch",
    "ubuntu": "debian",
    "debian": "debian", 
    "linuxmint": "debian",
    "pop": "debian",
    "elementary": "debian",
    "fedora": "fedora",
    "rhel": "fedora",
    "centos": "fedora", 
    "rocky": "fedora",
    "alma": "fedora"
}

# AUR helpers in order of preference
AUR_HELPERS = ['yay', 'paru', 'trizen', 'yaourt']

# Logging configuration
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'simple': {
            'format': '%(levelname)s - %(name)s - %(message)s'
        }
    },
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '~/.local/share/archpkg-helper/archpkg-helper.log',
            'maxBytes': 5242880,  # 5MB
            'backupCount': 3,
            'formatter': 'detailed',
            'level': 'DEBUG',
            'encoding': 'utf-8'
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'level': 'WARNING',
            'stream': 'ext://sys.stderr'
        }
    },
    'loggers': {
        '': {  # root logger
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': False
        }
    }
}

# Log levels for different components
LOG_LEVELS = {
    'cli': 'INFO',
    'search': 'INFO', 
    'command_gen': 'INFO',
    'validation': 'DEBUG',
    'network': 'INFO',
    'subprocess': 'DEBUG'
}

# Performance monitoring settings
PERFORMANCE_CONFIG = {
    'enable_timing_logs': True,
    'log_slow_operations_threshold': 5.0,  # seconds
    'enable_memory_logging': False,
    'enable_detailed_tracing': False
}