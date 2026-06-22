import os
import json
from pathlib import Path

def get_config_dir() -> Path:
    """Return the XDG-compliant config directory for archpkg."""
    config_home= Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_home / "archpkg"
def get_security_db_path()-> Path:
    """Return the full path to the security database JSON file."""
    return get_config_dir() / "security-db.json"
def init_security_db():
    """Ensure the security DB directory and file exist."""
    db_path= get_security_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        default_data={
            "last_updated": None,
            "safe": ["yay","paru"],
            "unsafe": ["malicoius-pkg"],
            "reports": []
        }
        with open(db_path, "w") as f:
            json.dump(default_data, f, indent=2)
        print(f"Created new security database at {db_path}")
    else:
        print(f"Security database already exists at {db_path}")
    return db_path
if __name__== "__main__":
    init_security_db()