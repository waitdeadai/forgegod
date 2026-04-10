"""Real sandbox backends for strict-mode command execution.

Current backend:
- Docker Engine container isolation with no network access

Strict mode should never silently fall back to host execution. If no real
sandbox backend is available, callers should block the command instead.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

DEFAULT_SANDBOX_IMAGE = "auto"
DEFAULT_PYTHON_SANDBOX_IMAGE = "mcr.microsoft.com/devcontainers/python:1-3.13-bookworm"
DEFAULT_POLYGLOT_SANDBOX_IMAGE = "forgegod/strict-sandbox:python3.13-node22-bookworm"
DEFAULT_NODE_MAJOR = "22"
CONTAINER_WORKSPACE_ROOT = PurePosixPath("/workspace")
OBSERVATIONAL_NODE_FLAGS = {"-v", "--version", "version", "help", "--help"}
NODE_EXECUTABLES = {"node", "npm", "npx", "pnpm", "yarn", "bun"}
NODE_WORKSPACE_MARKERS = (
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "bun.lock",
    "bun.lockb",
)
NODE_RUNTIME_GLOBS = ("next.config.*", "vite.config.*", "vitest.config.*")
POLYGLOT_SANDBOX_DOCKERFILE = textwrap.dedent(
    f"""\
    FROM {DEFAULT_PYTHON_SANDBOX_IMAGE}

    SHELL ["/bin/bash", "-o", "pipefail", "-c"]

    ENV DEBIAN_FRONTEND=noninteractive
    ENV NPM_CONFIG_UPDATE_NOTIFIER=false

    RUN rm -f /etc/apt/sources.list.d/*yarn* \\
        && apt-get update \\
        && apt-get install -y --no-install-recommends ca-certificates curl gnupg \\
        && mkdir -p /etc/apt/keyrings \\
        && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \\
            | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \\
        && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] \\
            https://deb.nodesource.com/node_{DEFAULT_NODE_MAJOR}.x nodistro main" \\
            > /etc/apt/sources.list.d/nodesource.list \\
        && apt-get update \\
        && apt-get install -y --no-install-recommends nodejs \\
        && corepack enable \\
        && rm -rf /var/lib/apt/lists/*
    """
)

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
    image = getattr(security, "sandbox_image", DEFAULT_SANDBOX_IMAGE)
    return image or DEFAULT_SANDBOX_IMAGE


def _uses_node_runtime(workspace_root: Path, argv: list[str] | None = None) -> bool:
    if argv:
        exe = Path(argv[0]).name.lower()
        if exe in NODE_EXECUTABLES:
            return True

    for marker in NODE_WORKSPACE_MARKERS:
        if (workspace_root / marker).exists():
            return True

    for pattern in NODE_RUNTIME_GLOBS:
        if any(workspace_root.glob(pattern)):
            return True

    return False


def resolve_sandbox_image(
    security,
    workspace_root: Path | None = None,
    argv: list[str] | None = None,
) -> str:
    configured = _docker_image(security)
    if configured != "auto":
        return configured

    if workspace_root and _uses_node_runtime(workspace_root, argv=argv):
        return DEFAULT_POLYGLOT_SANDBOX_IMAGE
    return DEFAULT_PYTHON_SANDBOX_IMAGE


def _is_managed_image(image: str) -> bool:
    return image == DEFAULT_POLYGLOT_SANDBOX_IMAGE


def _managed_image_build_dir(sandbox_root: Path, image: str) -> Path:
    build_name = image.replace("/", "_").replace(":", "_")
    build_dir = sandbox_root / "managed-images" / build_name
    build_dir.mkdir(parents=True, exist_ok=True)
    return build_dir


def _write_managed_image_context(sandbox_root: Path, image: str) -> Path:
    build_dir = _managed_image_build_dir(sandbox_root, image)
    if image == DEFAULT_POLYGLOT_SANDBOX_IMAGE:
        (build_dir / "Dockerfile").write_text(POLYGLOT_SANDBOX_DOCKERFILE, encoding="utf-8")
        return build_dir
    raise ValueError(f"No managed image context for {image}")


def _build_managed_image(image: str, sandbox_root: Path) -> tuple[bool, str]:
    build_dir = _write_managed_image_context(sandbox_root, image)
    proc = subprocess.run(
        ["docker", "build", "--pull", "-t", image, str(build_dir)],
        capture_output=True,
        text=True,
        timeout=1200,
        check=False,
    )
    if proc.returncode == 0:
        return True, ""

    detail = proc.stderr.strip() or proc.stdout.strip() or "docker build failed"
    return False, detail[-4000:]


def _ensure_docker_image_available(
    image: str,
    *,
    sandbox_root: Path | None = None,
    allow_build: bool = False,
) -> str | None:
    ok, reason = _run_probe("docker", "image", "inspect", image)
    if ok:
        return None

    if allow_build and sandbox_root and _is_managed_image(image):
        built, detail = _build_managed_image(image, sandbox_root)
        if built:
            return None
        return (
            f"ForgeGod could not build the managed sandbox image {image}. "
            f"Build error: {detail}"
        )

    if _is_managed_image(image):
        return (
            f"Managed sandbox image is not available locally yet: {image}. "
            "ForgeGod can build it automatically on the first strict Node/Next run."
        )

    return (
        f"Docker sandbox image is not available locally: {image}. "
        f"Inspect error: {reason}. Pull it once on the host with "
        f"`docker pull {image}` and keep strict mode enabled."
    )


def diagnose_strict_sandbox(security, workspace_root: Path | None = None) -> SandboxReadiness:
    """Return a user-facing readiness check for strict sandbox prerequisites."""
    root = workspace_root.resolve() if workspace_root else None
    image = resolve_sandbox_image(security, workspace_root=root)
    backend = getattr(security, "sandbox_backend", "auto")

    if backend not in {"auto", "docker"}:
        return SandboxReadiness(
            ready=False,
            detail=f"Unsupported sandbox backend: {backend}",
            fix="Set [security].sandbox_backend to `auto` or `docker` in .forgegod/config.toml.",
        )

    ok, reason = _run_probe("docker", "--version")
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
        if _is_managed_image(image):
            return SandboxReadiness(
                ready=True,
                detail=(
                    "Docker strict sandbox ready. "
                    f"ForgeGod will build the managed polyglot image {image} automatically "
                    "on the first strict Node/Next run."
                ),
            )
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


def _docker_run_command(
    *,
    image: str,
    workspace_root: Path,
    sandbox_home: Path,
    argv: list[str],
    network_mode: str,
) -> list[str]:
    user_spec = _docker_user_spec()
    cmd = [
        "docker",
        "run",
        "--rm",
        "--init",
        "--network",
        network_mode,
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
    ]
    if _uses_node_runtime(workspace_root, argv=argv):
        cmd.extend([
            "--mount",
            (
                "type=volume,"
                f"src={_node_dependency_volume_name(workspace_root)},"
                f"dst={CONTAINER_WORKSPACE_ROOT / 'node_modules'},"
                "volume-nocopy"
            ),
        ])
    if user_spec:
        cmd.extend(["--user", user_spec])
    cmd.extend([image, *argv])
    return cmd


def _docker_user_spec() -> str | None:
    """Pick a stable container user mapping for bind-mounted workspaces."""
    if os.name == "nt":
        return "0:0"
    getuid = getattr(os, "getuid", None)
    getgid = getattr(os, "getgid", None)
    if callable(getuid) and callable(getgid):
        return f"{getuid()}:{getgid()}"
    return None


def _docker_volume_exists(name: str) -> bool:
    ok, _ = _run_probe("docker", "volume", "inspect", name)
    return ok


def _node_dependency_volume_name(workspace_root: Path) -> str:
    resolved = str(workspace_root.resolve(strict=False)).lower()
    base_digest = hashlib.sha1(resolved.encode("utf-8")).hexdigest()[:10]
    manifest_digest = _node_manifest_hash(workspace_root)[:10]
    digest = f"{base_digest}-{manifest_digest}"
    return f"forgegod-node-{digest}"


def _node_dependency_stamp_path(sandbox_root: Path) -> Path:
    return sandbox_root / "node-deps-stamp.txt"


def _node_manifest_hash(workspace_root: Path) -> str:
    hasher = hashlib.sha256()
    for rel_path in (
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "bun.lock",
        "bun.lockb",
    ):
        path = workspace_root / rel_path
        if not path.exists() or not path.is_file():
            continue
        hasher.update(rel_path.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()


def _node_command_requires_dependencies(
    argv: list[str], workspace_root: Path, sandbox_root: Path,
) -> bool:
    if not (workspace_root / "package.json").exists():
        return False

    exe = Path(argv[0]).name.lower()
    if exe not in NODE_EXECUTABLES:
        return False

    args = [arg.lower() for arg in argv[1:]]
    if not args:
        return False
    if all(arg in OBSERVATIONAL_NODE_FLAGS for arg in args):
        return False

    if exe == "npm":
        subcommand = next((arg for arg in args if not arg.startswith("-")), "")
        return subcommand in {"test", "run", "exec", "start", "build", "lint"}

    if exe == "node":
        return False

    expected_hash = _node_manifest_hash(workspace_root)
    stamp_path = _node_dependency_stamp_path(sandbox_root)
    if stamp_path.exists():
        recorded = stamp_path.read_text(
            encoding="utf-8", errors="ignore",
        ).strip()
        if (
            recorded == expected_hash
            and _docker_volume_exists(_node_dependency_volume_name(workspace_root))
        ):
            return False

    return True


def _node_dependency_argv(workspace_root: Path) -> list[str] | None:
    if not (workspace_root / "package.json").exists():
        return None
    if (workspace_root / "package-lock.json").exists():
        return ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"]
    return ["npm", "install", "--ignore-scripts", "--no-audit", "--no-fund"]


async def _ensure_node_dependencies(
    *,
    image: str,
    workspace_root: Path,
    sandbox_root: Path,
    timeout: int,
    security,
) -> str | None:
    permission_mode = getattr(security, "permission_mode", "workspace-write")
    if permission_mode == "read-only":
        return None

    install_argv = _node_dependency_argv(workspace_root)
    if install_argv is None:
        return None

    sandbox_home = _host_sandbox_home(sandbox_root)
    proc = await asyncio.create_subprocess_exec(
        *_docker_run_command(
            image=image,
            workspace_root=workspace_root,
            sandbox_home=sandbox_home,
            argv=install_argv,
            network_mode="bridge",
        ),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=max(timeout, 900))
    except asyncio.TimeoutError:
        proc.kill()
        try:
            await proc.wait()
        except ProcessLookupError:
            pass
        raise

    if proc.returncode == 0:
        _node_dependency_stamp_path(sandbox_root).write_text(
            _node_manifest_hash(workspace_root),
            encoding="utf-8",
        )
        return None

    detail = stderr.decode("utf-8", errors="replace").strip()
    if not detail:
        detail = stdout.decode("utf-8", errors="replace").strip()
    detail = detail or "unknown npm bootstrap error"
    return (
        "ForgeGod could not prepare Node dependencies for strict sandbox validation. "
        f"Bootstrap command: {' '.join(install_argv)}. Error: {detail[-3000:]}"
    )


async def run_in_real_sandbox(
    argv: list[str],
    workspace_root: Path,
    sandbox_root: Path,
    timeout: int,
    security,
    network_mode: str = "none",
) -> SandboxExecutionResult:
    """Execute argv in a real sandbox backend."""
    backend, reason = detect_real_sandbox_backend(security)
    if backend is None:
        raise SandboxUnavailableError(reason or "No real sandbox backend available")

    if backend != "docker":
        raise SandboxUnavailableError(f"Unsupported real sandbox backend: {backend}")

    image = resolve_sandbox_image(security, workspace_root=workspace_root, argv=argv)
    image_error = await asyncio.to_thread(
        _ensure_docker_image_available,
        image,
        sandbox_root=sandbox_root,
        allow_build=True,
    )
    if image_error:
        raise SandboxUnavailableError(image_error)

    if _node_command_requires_dependencies(argv, workspace_root, sandbox_root):
        dependency_error = await _ensure_node_dependencies(
            image=image,
            workspace_root=workspace_root,
            sandbox_root=sandbox_root,
            timeout=timeout,
            security=security,
        )
        if dependency_error:
            raise SandboxUnavailableError(dependency_error)

    sandbox_home = _host_sandbox_home(sandbox_root)
    container_argv = rewrite_argv_for_docker(argv, workspace_root)
    cmd = _docker_run_command(
        image=image,
        workspace_root=workspace_root,
        sandbox_home=sandbox_home,
        argv=container_argv,
        network_mode=network_mode,
    )

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        try:
            await proc.wait()
        except ProcessLookupError:
            pass
        raise
    return SandboxExecutionResult(
        backend=backend,
        returncode=proc.returncode,
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
    )
