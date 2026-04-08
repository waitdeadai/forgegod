# Strict Sandbox Setup

This guide is for people who want ForgeGod's real `strict` sandbox without
guesswork.

`strict` mode is the safer path because commands run inside Docker with:

- no network
- read-only root filesystem
- dropped Linux capabilities
- the workspace mounted as the only writable project surface

Do not disable `strict` just to work around setup friction unless you
intentionally want the less isolated `standard` mode.

## What you need

1. Docker Desktop installed
2. Docker Desktop open and fully started
3. The ForgeGod sandbox image pulled once on the host

## Fast path

### Windows PowerShell

```powershell
docker pull mcr.microsoft.com/devcontainers/python:1-3.13-bookworm
python -m forgegod doctor
```

### macOS / Linux shell

```bash
docker pull mcr.microsoft.com/devcontainers/python:1-3.13-bookworm
python -m forgegod doctor
```

If `forgegod doctor` reports `Strict sandbox ready`, ForgeGod can execute
strict-mode commands safely.

## Optional proof test

If you want to prove that ForgeGod is using the real Docker strict backend and
not a mock path, run the opt-in integration test.

### Windows PowerShell

```powershell
$env:FORGEGOD_RUN_DOCKER_STRICT_TESTS="1"
python -m pytest tests/test_strict_sandbox_integration.py -q
```

### macOS / Linux shell

```bash
FORGEGOD_RUN_DOCKER_STRICT_TESTS=1 python -m pytest tests/test_strict_sandbox_integration.py -q
```

Expected result:

- `1 passed`

That test runs ForgeGod CLI against a local mock provider while strict mode
uses the real Docker backend underneath.

## Step by step

### 1. Install Docker Desktop

Use the official Docker Desktop installer for your OS:

- https://docs.docker.com/desktop/setup/install/windows-install/
- https://docs.docker.com/desktop/setup/install/mac-install/
- https://docs.docker.com/desktop/setup/install/linux/

### 2. Open Docker Desktop

Wait until Docker Desktop shows the engine as running. If Docker is still
starting, ForgeGod will block strict-mode execution on purpose.

### 3. Pull the sandbox image once

Run:

```bash
docker pull mcr.microsoft.com/devcontainers/python:1-3.13-bookworm
```

ForgeGod does not auto-pull this image from inside `strict` mode because that
would weaken the trust model around the sandbox bootstrap.

### 4. Run ForgeGod Doctor

```bash
python -m forgegod doctor
```

The doctor command now checks:

- whether Docker CLI exists
- whether the Docker daemon is reachable
- whether the strict sandbox image is already cached locally

### 5. Keep `strict` enabled

If your config uses:

```toml
[security]
sandbox_mode = "strict"
```

ForgeGod will block command execution instead of silently falling back to the
host. That is intentional.

## Common failures

### Docker CLI not found

Meaning:

- Docker Desktop is not installed
- or the Docker CLI is not on your PATH

Safe fix:

1. Install Docker Desktop from the official docs above
2. Open it once
3. Rerun `python -m forgegod doctor`

### Docker daemon not ready

Meaning:

- Docker Desktop is installed but not started
- or the engine is still booting

Safe fix:

1. Open Docker Desktop
2. Wait until it says the engine is running
3. Rerun `python -m forgegod doctor`

### Sandbox image missing

Meaning:

- Docker is healthy
- but the ForgeGod strict image has not been pulled yet

Safe fix:

```bash
docker pull mcr.microsoft.com/devcontainers/python:1-3.13-bookworm
python -m forgegod doctor
```

## Security notes

- `strict` is safer than `standard`, but it is still container isolation, not a
  microVM.
- Only use ForgeGod on repositories you trust.
- Do not store secrets in the repo itself.
- Use a disposable branch or worktree when testing autonomous loops.

## Official references

- Docker Desktop installation:
  https://docs.docker.com/desktop/setup/install/windows-install/
- Docker image pull reference:
  https://docs.docker.com/reference/cli/docker/image/pull/
