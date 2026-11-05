import os
import re
from typing import List

class SecretScannerError(Exception):
    pass

class SecretScanner:
    SENSITIVE_FILES = [
        r"\.env.*",
        r".*key\.json$",
        r".*\.pem$",
        r".*\.key$",
        r"credentials\.json$",
        r"secret.*"
    ]
    
    SENSITIVE_PATTERNS = [
        r"(?i)api_?key\s*[:=]\s*['\"].+['\"]",
        r"(?i)aws_access_key_id\s*[:=]\s*['\"].+['\"]",
        r"(?i)ghp_[a-zA-Z0-9]{36}"
    ]
    
    @classmethod
    def scan_files(cls, workspace_root: str, changed_files: List[str]) -> None:
        """
        Scans a list of files for secrets. Raises SecretScannerError if secrets are detected.
        """
        for file_path in changed_files:
            # 1. Filename check
            filename = os.path.basename(file_path)
            for pattern in cls.SENSITIVE_FILES:
                if re.match(pattern, filename):
                    raise SecretScannerError(f"Sensitive file blocked from commit: {file_path}")
            
            # 2. Content check
            abs_path = os.path.join(workspace_root, file_path)
            if not os.path.exists(abs_path):
                continue
                
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    for pattern in cls.SENSITIVE_PATTERNS:
                        if re.search(pattern, content):
                            raise SecretScannerError(f"Sensitive content detected in file: {file_path}")
            except UnicodeDecodeError:
                # Binary files skipped
                pass
