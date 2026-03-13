# JARVIS SSH Configuration

## Passwordless Agent Key

Gateway has a dedicated passwordless key for overnight agent automation:
- **Private key:** `~infranet/.ssh/jarvis_agent` (Gateway only)
- **Public key:** Added to Brain and Endpoint `authorized_keys`
- **Purpose:** Non-interactive SSH for agent tasks

## SSH Config (Gateway)
- Brain: Uses `jarvis_agent` key
- Endpoint: Uses `jarvis_agent` key
- GitHub: Uses `id_ed25519_github` key
- All hosts: `IdentitiesOnly yes` to prevent "Too many authentication failures"

## Key Fingerprint
SHA256:dSCu7pV5gs/xNzLYu69WRdLAMcOT4Fc3bJUXKf13Q5s jarvis-overnight-agent

## Troubleshooting
If overnight agent gets "Too many authentication failures":
1. Verify Gateway SSH config has `IdentitiesOnly yes`
2. Check that jarvis_agent key is passwordless
3. Confirm public key is in both nodes' authorized_keys
