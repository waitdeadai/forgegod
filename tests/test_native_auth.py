from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def test_resolve_codex_backend_supports_native_windows(monkeypatch):
    from forgegod import native_auth

    monkeypatch.setattr(native_auth.sys, "platform", "win32")
    monkeypatch.setattr(native_auth, "_inside_wsl", lambda: False)
    monkeypatch.setattr(native_auth.platform, "release", lambda: "11")
    monkeypatch.setattr(
        native_auth,
        "find_command",
        lambda command: "C:\\Users\\User\\AppData\\Roaming\\npm\\codex.CMD"
        if command == "codex"
        else None,
    )

    backend = native_auth.resolve_codex_backend()

    assert backend.mode == "native"
    assert "native Windows" in backend.detail
    assert backend.command.endswith("codex.CMD")


def test_resolve_codex_backend_falls_back_to_wsl(monkeypatch):
    from forgegod import native_auth

    monkeypatch.setattr(native_auth.sys, "platform", "win32")
    monkeypatch.setattr(native_auth, "_inside_wsl", lambda: False)
    monkeypatch.setattr(native_auth.platform, "release", lambda: "11")
    monkeypatch.setattr(
        native_auth,
        "find_command",
        lambda command: "C:\\Windows\\System32\\wsl.exe"
        if command in {"wsl.exe", "wsl"}
        else None,
    )
    monkeypatch.setattr(native_auth, "_list_wsl_distributions", lambda _wsl: ["Ubuntu"])
    monkeypatch.setattr(
        native_auth,
        "_wsl_command_exists",
        lambda _wsl, command, distro: command == "codex" and distro == "Ubuntu",
    )

    backend = native_auth.resolve_codex_backend()

    assert backend.mode == "wsl"
    assert backend.wsl_distribution == "Ubuntu"
    assert "WSL" in backend.detail


def test_codex_login_argv_uses_wsl_shell(monkeypatch):
    from forgegod import native_auth

    monkeypatch.setattr(
        native_auth,
        "resolve_codex_backend",
        lambda command="codex": native_auth.CodexBackend(
            mode="wsl",
            detail="Codex automation supported through WSL (Ubuntu)",
            command=command,
            wsl_exe="C:\\Windows\\System32\\wsl.exe",
            wsl_distribution="Ubuntu",
        ),
    )

    argv = native_auth.codex_login_argv()

    assert argv[:3] == ["C:\\Windows\\System32\\wsl.exe", "--distribution", "Ubuntu"]
    assert argv[3:5] == ["bash", "-lc"]
    assert "codex" in argv[-1]
    assert "login" in argv[-1]


def test_codex_login_status_sync_uses_wsl_backend(monkeypatch):
    from forgegod import native_auth

    monkeypatch.setattr(
        native_auth,
        "resolve_codex_backend",
        lambda command="codex": native_auth.CodexBackend(
            mode="wsl",
            detail="Codex automation supported through WSL (Ubuntu)",
            command=command,
            wsl_exe="C:\\Windows\\System32\\wsl.exe",
            wsl_distribution="Ubuntu",
        ),
    )

    seen: dict[str, list[str]] = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout="Logged in using ChatGPT\n",
            stderr="",
        )

    monkeypatch.setattr(native_auth.subprocess, "run", fake_run)

    ready, detail = native_auth.codex_login_status_sync()

    assert ready is True
    assert "Logged in" in detail
    assert seen["argv"][:3] == ["C:\\Windows\\System32\\wsl.exe", "--distribution", "Ubuntu"]
    assert seen["argv"][3:5] == ["bash", "-lc"]


@pytest.mark.asyncio
async def test_codex_exec_uses_wsl_backend(monkeypatch, tmp_path):
    from forgegod import native_auth

    monkeypatch.setattr(
        native_auth,
        "resolve_codex_backend",
        lambda command="codex": native_auth.CodexBackend(
            mode="wsl",
            detail="Codex automation supported through WSL (Ubuntu)",
            command=command,
            wsl_exe="C:\\Windows\\System32\\wsl.exe",
            wsl_distribution="Ubuntu",
        ),
    )
    monkeypatch.setattr(
        native_auth,
        "_windows_path_to_wsl",
        lambda path, *_args: f"/mnt/c/{Path(path).name}",
    )

    seen: dict[str, object] = {}

    async def fake_run_command(argv, cwd=None, timeout=30.0, stdin_text=None):
        seen["argv"] = argv
        seen["cwd"] = cwd
        seen["timeout"] = timeout
        seen["stdin_text"] = stdin_text
        stdout = (
            '{"type":"item.completed","item":{"type":"agent_message","text":"ok"}}\n'
            '{"type":"turn.completed","usage":{"input_tokens":11,"output_tokens":7}}\n'
        )
        return 0, stdout, ""

    monkeypatch.setattr(native_auth, "run_command", fake_run_command)

    text, usage = await native_auth.codex_exec(
        "hello from forgegod",
        tmp_path,
        model="gpt-5.4",
        sandbox="read-only",
        ephemeral=True,
    )

    assert text == "ok"
    assert usage["input_tokens"] == 11
    assert usage["output_tokens"] == 7
    assert usage["subscription_billing"] is True
    assert seen["cwd"] is None
    assert seen["stdin_text"] == "hello from forgegod"
    argv = seen["argv"]
    assert argv[:3] == ["C:\\Windows\\System32\\wsl.exe", "--distribution", "Ubuntu"]
    assert argv[3:5] == ["bash", "-lc"]
    assert "codex" in argv[-1]
    assert "--disable" in argv[-1]
    assert "plugins" in argv[-1]
    assert "shell_snapshot" in argv[-1]
    assert "--json" in argv[-1]


@pytest.mark.asyncio
async def test_codex_exec_native_disables_plugins_and_shell_snapshot(monkeypatch, tmp_path):
    from forgegod import native_auth

    monkeypatch.setattr(
        native_auth,
        "resolve_codex_backend",
        lambda command="codex": native_auth.CodexBackend(
            mode="native",
            detail="Codex automation supported on native Windows",
            command="C:\\Users\\User\\AppData\\Roaming\\npm\\codex.CMD",
        ),
    )

    seen: dict[str, object] = {}

    async def fake_run_command(argv, cwd=None, timeout=30.0, stdin_text=None):
        seen["argv"] = argv
        seen["cwd"] = cwd
        seen["timeout"] = timeout
        seen["stdin_text"] = stdin_text
        stdout = (
            '{"type":"item.completed","item":{"type":"agent_message","text":"ok"}}\n'
            '{"type":"turn.completed","usage":{"input_tokens":7,"output_tokens":3}}\n'
        )
        return 0, stdout, ""

    monkeypatch.setattr(native_auth, "run_command", fake_run_command)

    text, usage = await native_auth.codex_exec(
        "hello from forgegod",
        tmp_path,
        model="gpt-5.4",
        sandbox="read-only",
        ephemeral=True,
    )

    assert text == "ok"
    assert usage["subscription_billing"] is True
    argv = seen["argv"]
    assert argv[0].endswith("codex.CMD")
    assert argv[1:7] == [
        "exec",
        "--disable",
        "plugins",
        "--disable",
        "shell_snapshot",
        "--skip-git-repo-check",
    ]
