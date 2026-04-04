"""ForgeGod i18n — lightweight translation support (en + es-419)."""

from __future__ import annotations

import locale
import os

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        # Onboarding wizard
        "welcome": "Let's set up ForgeGod in 2 minutes",
        "provider_prompt": "How do you want to run AI models?",
        "opt_local": "Free local mode (Ollama — $0, runs on your machine)",
        "opt_openai": "OpenAI API key (GPT-4o, o4-mini)",
        "opt_anthropic": "Anthropic API key (Claude)",
        "opt_openrouter": "OpenRouter API key (300+ models)",
        "opt_gemini": "Google Gemini API key (Gemini 2.5 Pro, Gemini 3 Flash)",
        "opt_multi": "I have multiple providers",
        "enter_key": "Paste your API key",
        "verifying": "Verifying connection...",
        "verify_ok": "Connection verified!",
        "verify_fail": "Connection failed",
        "saving_env": "Saving to .forgegod/.env...",
        "success": "You're ready!",
        "try_it": 'Try it: forgegod run "Add a hello world endpoint"',
        "init_done": "Initialized at {path}",
        "quick_start": "Quick start:",
        "run_hint": '  forgegod run "Describe your task here"',
        "local_only_hint": "Running in local-only mode ($0). Add API keys for cloud models.",
        # Errors
        "no_providers": "No API keys or Ollama found.",
        "set_one": "Set at least one:",
        "error_ollama_down": "Ollama isn't running. Start it with: ollama serve",
        "error_ollama_no_model": (
            "Model '{model}' not found in Ollama. Pull it with: ollama pull {model}"
        ),
        "error_key_invalid": "API key invalid. Check it at: {url}",
        "error_key_missing": "No API key set for {provider}.",
        "error_rate_limit": (
            "Rate limited by {provider}. Retrying in {seconds}s... (attempt {n}/{max})"
        ),
        "error_rate_persist": (
            "If this persists, consider switching to local mode: forgegod init --quick"
        ),
        "error_timeout": "Request timed out. The model may be loading. Retry in a moment.",
        "error_all_failed": "All models failed for role={role}.",
        # CLI commands
        "task_done": "Task completed",
        "task_fail": "Task failed",
        "loop_started": "Ralph Loop started. Press Ctrl+C to stop.",
        "loop_stopped": "Loop stopped by user.",
        "loop_complete": "All stories complete!",
        "dry_run_header": "DRY RUN MODE — No agents will be executed.",
        "story_order": "Story Execution Order:",
        "dry_run_done": "Dry run complete.",
        # Doctor
        "doctor_title": "ForgeGod Health Check",
        "doctor_pass": "PASS",
        "doctor_fail": "FAIL",
        "doctor_warn": "WARN",
        "doctor_python": "Python >= 3.11",
        "doctor_config": "Config file",
        "doctor_ollama": "Ollama reachable",
        "doctor_api_keys": "API keys valid",
        "doctor_git": "Git installed",
        "doctor_tests": "Test runner detected",
        "doctor_all_ok": "All checks passed!",
        "doctor_has_issues": "{count} issue(s) found. Fix them above.",
        # Benchmark
        "bench_running": "Running benchmark...",
        "bench_done": "Benchmark complete!",
        "bench_task": "Task {n}/{total}: {name}",
        "bench_attempt": "Attempt {n}/2",
        "bench_model": "Model: {model}",
        "bench_results_title": "Benchmark Results",
        "bench_composite": "Composite Score",
        "bench_correctness": "Correctness",
        "bench_quality": "Quality",
        "bench_speed": "Speed",
        "bench_cost": "Cost",
        "bench_self_repair": "Self-Repair",
        "bench_saved": "Results saved to {path}",
        "bench_readme_updated": "Leaderboard inserted into README.md",
        "bench_no_models": "No models available. Run 'forgegod init' first.",
        "bench_detecting": "Auto-detecting available models...",
        # Terse / Caveman mode
        "terse_enabled": "Caveman mode enabled — ultra-terse prompts",
        "terse_savings": "Terse savings: {pct}% ({tokens} tokens saved)",
    },
    "es": {
        # Onboarding wizard
        "welcome": "Configuremos ForgeGod en 2 minutos",
        "provider_prompt": "¿Cómo querés ejecutar los modelos de IA?",
        "opt_local": "Modo local gratuito (Ollama — $0, corre en tu máquina)",
        "opt_openai": "Clave API de OpenAI (GPT-4o, o4-mini)",
        "opt_anthropic": "Clave API de Anthropic (Claude)",
        "opt_openrouter": "Clave API de OpenRouter (300+ modelos)",
        "opt_gemini": "Clave API de Google Gemini (Gemini 2.5 Pro, Gemini 3 Flash)",
        "opt_multi": "Tengo varios proveedores",
        "enter_key": "Pegá tu clave API",
        "verifying": "Verificando conexión...",
        "verify_ok": "¡Conexión verificada!",
        "verify_fail": "La conexión falló",
        "saving_env": "Guardando en .forgegod/.env...",
        "success": "¡Listo!",
        "try_it": 'Probalo: forgegod run "Agregá un endpoint de hello world"',
        "init_done": "Inicializado en {path}",
        "quick_start": "Inicio rápido:",
        "run_hint": '  forgegod run "Describí tu tarea acá"',
        "local_only_hint": (
            "Corriendo en modo local ($0). Agregá claves API para modelos en la nube."
        ),
        # Errors
        "no_providers": "No se encontraron claves API ni Ollama.",
        "set_one": "Configurá al menos uno:",
        "error_ollama_down": "Ollama no está corriendo. Inicialo con: ollama serve",
        "error_ollama_no_model": (
            "Modelo '{model}' no encontrado en Ollama. Descargalo con: ollama pull {model}"
        ),
        "error_key_invalid": "Clave API inválida. Revisala en: {url}",
        "error_key_missing": "No hay clave API configurada para {provider}.",
        "error_rate_limit": (
            "Límite de tasa de {provider}. Reintentando en {seconds}s... (intento {n}/{max})"
        ),
        "error_rate_persist": (
            "Si continúa, considerá cambiar a modo local: forgegod init --quick"
        ),
        "error_timeout": (
            "La solicitud expiró. El modelo puede estar cargando. Reintentá en un momento."
        ),
        "error_all_failed": "Todos los modelos fallaron para rol={role}.",
        # CLI commands
        "task_done": "Tarea completada",
        "task_fail": "Tarea fallida",
        "loop_started": "Ralph Loop iniciado. Presioná Ctrl+C para detener.",
        "loop_stopped": "Loop detenido por el usuario.",
        "loop_complete": "¡Todas las historias completadas!",
        "dry_run_header": "MODO PRUEBA — No se ejecutarán agentes.",
        "story_order": "Orden de Ejecución de Historias:",
        "dry_run_done": "Prueba completada.",
        # Doctor
        "doctor_title": "Chequeo de Salud de ForgeGod",
        "doctor_pass": "OK",
        "doctor_fail": "ERROR",
        "doctor_warn": "AVISO",
        "doctor_python": "Python >= 3.11",
        "doctor_config": "Archivo de configuración",
        "doctor_ollama": "Ollama accesible",
        "doctor_api_keys": "Claves API válidas",
        "doctor_git": "Git instalado",
        "doctor_tests": "Test runner detectado",
        "doctor_all_ok": "¡Todos los chequeos pasaron!",
        "doctor_has_issues": "{count} problema(s) encontrado(s). Corregílos arriba.",
        # Benchmark
        "bench_running": "Ejecutando benchmark...",
        "bench_done": "¡Benchmark completo!",
        "bench_task": "Tarea {n}/{total}: {name}",
        "bench_attempt": "Intento {n}/2",
        "bench_model": "Modelo: {model}",
        "bench_results_title": "Resultados del Benchmark",
        "bench_composite": "Puntaje Compuesto",
        "bench_correctness": "Correctitud",
        "bench_quality": "Calidad",
        "bench_speed": "Velocidad",
        "bench_cost": "Costo",
        "bench_self_repair": "Auto-Reparación",
        "bench_saved": "Resultados guardados en {path}",
        "bench_readme_updated": "Leaderboard insertado en README.md",
        "bench_no_models": "No hay modelos disponibles. Ejecutá 'forgegod init' primero.",
        "bench_detecting": "Auto-detectando modelos disponibles...",
        # Terse / Caveman mode
        "terse_enabled": "Modo cavernícola activado — prompts ultra-concisos",
        "terse_savings": "Ahorro terse: {pct}% ({tokens} tokens ahorrados)",
    },
}

_lang = "en"


def detect_lang() -> str:
    """Detect language from system locale. Returns 'es' for es_* locales, else 'en'."""
    try:
        # getdefaultlocale() deprecated in 3.15 — use getlocale() first
        loc = locale.getlocale()[0] or ""
        if not loc or loc == "C":
            loc = os.environ.get("LANG", os.environ.get("LC_ALL", ""))
        if loc.startswith("es"):
            return "es"
    except Exception:
        pass
    return "en"


def set_lang(lang: str) -> None:
    """Set the active language. Use 'auto' for locale detection."""
    global _lang
    if lang == "auto":
        _lang = detect_lang()
    elif lang in STRINGS:
        _lang = lang
    else:
        _lang = "en"


def get_lang() -> str:
    """Return the current language code."""
    return _lang


def t(key: str, **kwargs: str) -> str:
    """Translate a key. Supports {placeholder} formatting via kwargs."""
    msg = STRINGS.get(_lang, STRINGS["en"]).get(key, STRINGS["en"].get(key, key))
    if kwargs:
        try:
            return msg.format(**kwargs)
        except KeyError:
            return msg
    return msg
