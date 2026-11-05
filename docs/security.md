# NEXUS Security Model

Security is a primary concern for NEXUS, as it involves executing AI-generated code and commands.

## Key Principles

1. **Isolation:** All code changes and tests occur within an isolated temporary workspace. 
2. **Restricted Execution:** The AI is not allowed to run arbitrary commands on the host machine. Test commands are predefined or severely restricted.
3. **No Direct Production Commits:** NEXUS will never automatically push code to the `main` or `master` branch. All changes must be explicitly approved by the user and are submitted via a Pull Request.
4. **Secret Management:** User credentials, API keys, and GitHub tokens are kept securely on the server environment. They are never exposed to the code being executed in the temporary workspace.

## Agent Boundaries

Each agent has specific, restricted access:
- **Planner / Researcher:** Read-only access to repository metadata and files.
- **Coder:** Write access to the temporary workspace only.
- **Tester:** Execute access for specific testing frameworks within the workspace.
- **Reviewer:** Read-only access to the proposed diff.
