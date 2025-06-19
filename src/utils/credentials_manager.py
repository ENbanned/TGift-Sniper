import json
from pathlib import Path
from typing import Optional, Dict, Any

from src.core.constants import FileConstants


class CredentialsManager:
    
    def __init__(self, sessions_dir: Path):
        self.sessions_dir = sessions_dir
        self.credentials_file = sessions_dir / FileConstants.CREDENTIALS_FILE
    

    def exists(self) -> bool:
        return self.credentials_file.exists()
    

    def load(self, session_name: str) -> Optional[Dict[str, Any]]:
        if not self.credentials_file.exists():
            return None
        
        try:
            with open(self.credentials_file, 'r') as f:
                credentials = json.load(f)
                return credentials.get(session_name)
        except Exception:
            return None
    

    def save(self, session_name: str, data: Dict[str, Any]) -> None:
        credentials = {}
        if self.credentials_file.exists():
            with open(self.credentials_file, 'r') as f:
                credentials = json.load(f)
        
        credentials[session_name] = data
        
        with open(self.credentials_file, 'w') as f:
            json.dump(credentials, f, indent=2)
        
        self.credentials_file.chmod(FileConstants.CREDENTIALS_FILE_PERMISSIONS)
    

    def delete(self, session_name: str) -> bool:
        if not self.credentials_file.exists():
            return False
        
        try:
            with open(self.credentials_file, 'r') as f:
                credentials = json.load(f)
            
            if session_name in credentials:
                del credentials[session_name]
                
                with open(self.credentials_file, 'w') as f:
                    json.dump(credentials, f, indent=2)
                return True
            
            return False
        except Exception:
            return False
        