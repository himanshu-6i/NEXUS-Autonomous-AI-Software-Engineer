import os
import subprocess
import logging
from typing import List, Tuple
from workspace.manager import workspace_manager, WorkspaceError
from models.tester import TestCommand

logger = logging.getLogger(__name__)

# Very strict allowlist for prototype security
ALLOWED_EXECUTABLES = {"pytest", "python", "npm", "npx", "jest", "vitest"}

class RunnerError(Exception):
    pass

class TestRunner:
    def __init__(self, timeout: int = 30, max_output_bytes: int = 1024 * 1024):
        self.timeout = timeout
        self.max_output_bytes = max_output_bytes

    def validate_command(self, workspace_id: str, command: TestCommand):
        """Ensures the command is safe to execute."""
        if command.executable not in ALLOWED_EXECUTABLES:
            raise RunnerError(f"Executable '{command.executable}' is not allowed.")
            
        for arg in command.arguments:
            if any(char in arg for char in ['&', '|', ';', '`', '$', '>', '<']):
                raise RunnerError(f"Argument contains forbidden shell characters: {arg}")
            if ".." in arg and not arg.startswith("-"):
                # Simple heuristic to prevent path traversal in arguments
                raise RunnerError(f"Argument contains path traversal attempt: {arg}")

    def execute(self, workspace_id: str, command: TestCommand) -> Tuple[int, str]:
        """
        Executes a validated command in the workspace directory.
        Returns (exit_code, combined_output).
        """
        self.validate_command(workspace_id, command)
        workspace_root = workspace_manager.get_workspace_path(workspace_id)
        
        # Build command array
        cmd = [command.executable] + command.arguments
        
        logger.info(f"Executing in {workspace_id}: {' '.join(cmd)}")
        
        # Create a clean, minimal environment
        # Do NOT pass the host's full environment.
        safe_env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": workspace_root,
            "CI": "true" # Common flag to disable interactive prompts
        }
        
        # Windows compatibility: npm/npx might need .cmd extension depending on the environment
        if os.name == 'nt' and command.executable in ['npm', 'npx', 'pytest']:
            # subprocess on Windows sometimes needs shell=True to find bat/cmd wrappers, 
            # but we explicitly forbid shell=True for security. 
            # We'll rely on shutil.which to find the actual executable.
            import shutil
            actual_exe = shutil.which(command.executable)
            if actual_exe:
                cmd[0] = actual_exe
                
        try:
            # We use subprocess.run with shell=False for security
            process = subprocess.run(
                cmd,
                cwd=workspace_root,
                env=safe_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Combine stdout/stderr
                timeout=self.timeout,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            output = process.stdout
            if len(output) > self.max_output_bytes:
                output = output[:self.max_output_bytes] + "\n...[TRUNCATED]"
                
            return process.returncode, output
            
        except subprocess.TimeoutExpired as e:
            output = e.stdout.decode('utf-8', 'replace') if e.stdout else ""
            if len(output) > self.max_output_bytes:
                output = output[:self.max_output_bytes] + "\n...[TRUNCATED]"
            return 124, output + "\n[ERROR: TIMEOUT EXPIRED]"
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            raise RunnerError(f"Failed to execute command: {str(e)}")

test_runner = TestRunner()
