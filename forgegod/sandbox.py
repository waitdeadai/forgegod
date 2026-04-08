"""Real sandbox backends for strict-mode command execution.

Current backend:
- Docker Engine container isolation with no network access

Strict mode should never silently fall back to host execution. If no real
sandbox backend is available, callers should block the command instead.
"""

from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

DEFAULT_SANDBOX_IMAGE = "mcr.microsoft.com/devcontainers/python:1-3.13-bookworm"
CONTAINER_WORKSPACE_ROOT = PurePosixPath("/workspace")

CONTAINER_EXECUTABLE_MAP = {
    "python.exe": "python",
    "dir": "ls",
    "type": "cat",
    "findstr": "grep",
}


@dataclass(frozen=True)
class SandboxExecutionResult:
    backend: str
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class SandboxReadiness:
    ready: bool
    detail: str
    fix: str = ""


class SandboxUnavailableError(RuntimeError):
    """Raised when strict mode cannot obtain a real sandbox backend."""


def _run_probe(*args: str, timeout: int = 8) -> tuple[bool, str]:
    """Run a short synchronous probe command."""
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return False, f"Command not found: {args[0]}"
    except subprocess.TimeoutExpired:
        return False, f"Probe timed out: {' '.join(args)}"

    if proc.returncode == 0:
        return True, ""

    detail = proc.stderr.strip() or proc.stdout.strip() or "unknown error"
    return False, detail


def detect_real_sandbox_backend(security) -> tuple[str | None, str | None]:
    """Pick an available real sandbox backend for strict mode."""
    backend = getattr(security, "sandbox_backend", "auto")
    if backend not in {"auto", "docker"}:
        return None, f"Unsupported sandbox backend: {backend}"

    ok, reason = _run_probe("docker", "info", "--format", "{{json .ServerVersion}}")
    if ok:
        return "docker", None

    return None, (
        "Strict mode requires a real sandbox backend. "
        f"Docker is unavailable: {reason}. "
        "Open Docker Desktop, wait for the engine to start, and rerun `forgegod doctor`."
    )


def _docker_image(security) -> str:
    return getattr(security, "sandbox_image", DEFAULT_SANDBOX_IMAGE)


def _ensure_docker_image_available(image: str) -> str | None:
    ok, reason = _run_probe("docker", "image", "inspect", image)
    if ok:
        return None
    return (
        f"Docker sandbox image is not available locally: {image}. "
        f"Inspect error: {reason}. Pull it once on the host with "
        f"`docker pull {image}` and keep strict mode enabled."
    )


def diagnose_strict_sandbox(security) -> SandboxReadiness:
    """Return a user-facing readiness check for strict sandbox prerequisites."""
    image = _docker_image(security)
    backend = getattr(security, "sandbox_backend", "auto")

    if backend not in {"auto", "docker"}:
        return SandboxReadiness(
            ready=False,
            detail=f"Unsupported sandbox backend: {backend}",
            fix="Set [security].sandbox_backend to `auto` or `docker` in .forgegod/config.toml.",
        )

    ok, reason = _run_probe("docker", "version", "--format", "{{.Client.Version}}")
    if not ok:
        return SandboxReadiness(
            ready=False,
            detail=f"Docker CLI is not available: {reason}",
            fix=(
                "1. Install Docker Desktop from docs.docker.com. "
                "2. Open Docker Desktop once. "
                "3. Rerun `forgegod doctor`."
            ),
        )

    ok, reason = _run_probe("docker", "info", "--format", "{{json .ServerVersion}}")
    if not ok:
        return SandboxReadiness(
            ready=False,
            detail=f"Docker daemon is not ready: {reason}",
            fix=(
                "1. Open Docker Desktop. "
                "2. Wait until it shows the engine as running. "
                "3. Rerun `forgegod doctor`."
            ),
        )

    image_error = _ensure_docker_image_available(image)
    if image_error:
        return SandboxReadiness(
            ready=False,
            detail=f"Strict sandbox image missing: {image}",
            fix=(
                f"1. Run `docker pull {image}` once on the host. "
                "2. Rerun `forgegod doctor`. "
                "3. Keep `sandbox_mode = \"strict\"` if you want real isolation."
            ),
        )

    return SandboxReadiness(
        ready=True,
        detail=f"Docker strict sandbox ready with local image {image}",
    )


def _host_sandbox_home(sandbox_root: Path) -> Path:
    home_dir = sandbox_root / "container-home"
    home_dir.mkdir(parents=True, exist_ok=True)
    return home_dir


def _container_path_for(host_path: Path, workspace_root: Path) -> str:
    rel = host_path.resolve(strict=False).relative_to(workspace_root)
    if not rel.parts:
        return str(CONTAINER_WORKSPACE_ROOT)
    return str(CONTAINER_WORKSPACE_ROOT.joinpath(*rel.parts))


def rewrite_argv_for_docker(argv: list[str], workspace_root: Path) -> list[str]:
    """Rewrite strict argv to run inside a Linux container sandbox."""
    exe = Path(argv[0]).name.lower()
    mapped_exe = CONTAINER_EXECUTABLE_MAP.get(exe, exe)
    rewritten = [mapped_exe]

    for arg in argv[1:]:
        if arg == ".":
            rewritten.append(".")
            continue

        raw = Path(arg)
        if raw.is_absolute():
            try:
                rewritten.append(_container_path_for(raw, workspace_root))
                continue
            except ValueError:
                rewritten.append(arg)
                continue

        if "/" in arg or "\\" in arg:
            candidate = (workspace_root / raw).resolve(strict=False)
            try:
                rewritten.append(_container_path_for(candidate, workspace_root))
                continue
            except ValueError:
                rewritten.append(arg)
                continue

        rewritten.append(arg)

    return rewritten


async def run_in_real_sandbox(
    argv: list[str],
    workspace_root: Path,
    sandbox_root: Path,
    timeout: int,
    security,
) -> SandboxExecutionResult:
    """Execute argv in a real sandbox backend."""
    backend, reason = detect_real_sandbox_backend(security)
    if backend is None:
        raise SandboxUnavailableError(reason or "No real sandbox backend available")

    if backend != "docker":
        raise SandboxUnavailableError(f"Unsupported real sandbox backend: {backend}")

    image = _docker_image(security)
    image_error = _ensure_docker_image_available(image)
    if image_error:
        raise SandboxUnavailableError(image_error)

    sandbox_home = _host_sandbox_home(sandbox_root)
    container_argv = rewrite_argv_for_docker(argv, workspace_root)

    cmd = [
        "docker",
        "run",
        "--rm",
        "--init",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges=true",
        "--pids-limit",
        "256",
        "--mount",
        f"type=bind,src={workspace_root},dst={CONTAINER_WORKSPACE_ROOT}",
        "--mount",
        f"type=bind,src={sandbox_home},dst=/home/forgegod",
        "--mount",
        "type=tmpfs,dst=/tmp",
        "--mount",
        "type=tmpfs,dst=/var/tmp",
        "--workdir",
        str(CONTAINER_WORKSPACE_ROOT),
        "--env",
        "HOME=/home/forgegod",
        "--env",
        "TMPDIR=/tmp",
        "--env",
        f"FORGEGOD_WORKSPACE_ROOT={CONTAINER_WORKSPACE_ROOT}",
        image,
        *container_argv,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    return SandboxExecutionResult(
        backend=backend,
        returncode=proc.returncode,
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
    )
