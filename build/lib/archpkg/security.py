import json
from pathlib import Path
from .paths import get_security_db_path

class SecurityDB:
    def __init__(self):
        self.db_path= get_security_db_path()
        with open(self.db_path, "r") as f:
            self.data= json.load(f)
    def check_package(self, pkg_name: str):
        if pkg_name in self.data.get("unsafe", []):
            return "blocked"
        elif pkg_name in self.data.get("safe",[]):
            return "safe"
        else:
            return "not_verified"
    def report_package(self,pkg_name: str, reason: str):
        self.data.setdefault("reports", []).append({
            "package": pkg_name,
            "reason": reason
        })
        self.save()
    def save(self):
        with open(self.db_path, "w") as f:
            json.dump(self.data,f, indent=2)
    def update_security_db(self, remote_data= None):
        """
        Update the local security DB.
        remote_data: dict fetched from server
        """
        if remote_data:
            self.data.update(remote_data)
            self.data["last_updated"]="2025-10-05"
            self.save()
            print("Security database updated from remote.")
        else:
            print("No remote data provided. Placeholder update.")