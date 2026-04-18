"""ForgeGod i18n: lightweight translation support (en + es-419)."""

from __future__ import annotations

import locale
import os

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        # Onboarding wizard
        "welcome": "Let's set up ForgeGod in 2 minutes",
        "provider_prompt": "How do you want to run AI models?",
        "provider_recommended": "Recommended path",
        "provider_detected": "What ForgeGod already found",
        "provider_storage_note": (
            "ForgeGod stores new keys in repo-local .forgegod/.env, "
            "not in your global shell profile."
        ),
        "provider_friendly_hint": (
            "Pick the path you want. ForgeGod will verify it before relying on it."
        ),
        "harness_prompt": "How should ForgeGod route work across models?",
        "harness_recommended_body": (
            "Adversarial mode splits builder and reviewer roles across the best "
            "available models. Single-model mode keeps one model on every role."
        ),
        "harness_adversarial": "Adversarial harness (builder + reviewer split)",
        "harness_single": "Single-model harness (one model for every role)",
        "harness_selected": "Selected harness profile: {profile}",
        "provider_pref_prompt": "Should ForgeGod stay provider-agnostic or bias toward OpenAI?",
        "provider_pref_body": (
            "Auto keeps the general best available split. OpenAI-first prefers "
            "OpenAI API + Codex when both are connected."
        ),
        "provider_pref_auto": "Auto routing across all connected providers",
        "provider_pref_openai": "OpenAI-first (API builder + Codex reviewer when available)",
        "provider_pref_selected": "Provider preference: {provider}",
        "openai_surface_prompt": "How should ForgeGod use OpenAI API and Codex surfaces?",
        "openai_surface_body": (
            "Auto keeps provider-agnostic routing. API-only uses OpenAI API only. "
            "Codex-only stays on the ChatGPT/Codex subscription surface. API + Codex "
            "splits builder roles onto the API and reviewer roles onto Codex. "
            "If you only have a subscription, choose Codex-only."
        ),
        "openai_surface_auto": "Auto (keep provider-agnostic routing)",
        "openai_surface_api_only": "OpenAI API only",
        "openai_surface_codex_only": "Codex subscription only",
        "openai_surface_hybrid": "OpenAI API + Codex subscription",
        "openai_surface_selected": "OpenAI surface: {surface}",
        "opt_local": "Free local mode (Ollama - $0, runs on your machine)",
        "opt_openai": "OpenAI API key (GPT-5.4, GPT-5.4-mini)",
        "opt_openai_codex": "OpenAI ChatGPT subscription via Codex login",
        "opt_anthropic": "Anthropic API key (Claude)",
        "opt_openrouter": "OpenRouter API key (300+ models)",
        "opt_gemini": "Google Gemini API key (Gemini 2.5 Pro, Gemini 3 Flash)",
        "opt_deepseek": "DeepSeek API key (V3.2 - 22x cheaper, 74% SWE-bench)",
        "opt_kimi": "Moonshot / Kimi API key (Kimi K2.5, Kimi K2 Thinking)",
        "opt_zai": "Z.AI API key (GLM-5.1, GLM Coding Plan / API)",
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
        "dry_run_header": "DRY RUN MODE - No agents will be executed.",
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
        "doctor_api_keys": "Auth surfaces detected",
        "doctor_git": "Git installed",
        "doctor_sandbox": "Strict sandbox ready",
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
        "terse_enabled": "Caveman mode enabled - ultra-terse prompts",
        "terse_savings": "Terse savings: {pct}% ({tokens} tokens saved)",
    },
    "es": {
        # Onboarding wizard
        "welcome": "Configuremos ForgeGod en 2 minutos",
        "provider_prompt": "Como queres ejecutar los modelos de IA?",
        "provider_recommended": "Camino recomendado",
        "provider_detected": "Lo que ForgeGod ya encontro",
        "provider_storage_note": (
            "ForgeGod guarda claves nuevas en .forgegod/.env del repo, "
            "no en tu perfil global de shell."
        ),
        "provider_friendly_hint": (
            "Elegi el camino que quieras. ForgeGod lo verifica antes de depender de el."
        ),
        "harness_prompt": "Como queres que ForgeGod reparta el trabajo entre modelos?",
        "harness_recommended_body": (
            "El modo adversarial separa builder y reviewer entre los mejores "
            "modelos disponibles. El modo single-model usa un solo modelo para todo."
        ),
        "harness_adversarial": "Harness adversarial (builder + reviewer separados)",
        "harness_single": "Harness single-model (un modelo para todos los roles)",
        "harness_selected": "Perfil de harness elegido: {profile}",
        "provider_pref_prompt": "Queres que ForgeGod siga agnostico o que priorice OpenAI?",
        "provider_pref_body": (
            "Auto mantiene el mejor split general disponible. OpenAI-first prioriza "
            "OpenAI API + Codex cuando ambos estan conectados."
        ),
        "provider_pref_auto": "Auto entre todos los proveedores conectados",
        "provider_pref_openai": "OpenAI-first (API builder + Codex reviewer si estan disponibles)",
        "provider_pref_selected": "Preferencia de proveedor: {provider}",
        "openai_surface_prompt": "Como queres que ForgeGod use OpenAI API y Codex?",
        "openai_surface_body": (
            "Auto mantiene ruteo agnostico. API-only usa solo OpenAI API. "
            "Codex-only se queda solo en la suscripcion ChatGPT/Codex. API + Codex "
            "pone builder en la API y reviewer en Codex. "
            "Si solo tenes suscripcion, elegi Codex-only."
        ),
        "openai_surface_auto": "Auto (mantener ruteo agnostico)",
        "openai_surface_api_only": "Solo OpenAI API",
        "openai_surface_codex_only": "Solo suscripcion Codex",
        "openai_surface_hybrid": "OpenAI API + suscripcion Codex",
        "openai_surface_selected": "Superficie OpenAI: {surface}",
        "opt_local": "Modo local gratuito (Ollama - $0, corre en tu maquina)",
        "opt_openai": "Clave API de OpenAI (GPT-5.4, GPT-5.4-mini)",
        "opt_openai_codex": "Suscripcion ChatGPT de OpenAI via login de Codex",
        "opt_anthropic": "Clave API de Anthropic (Claude)",
        "opt_openrouter": "Clave API de OpenRouter (300+ modelos)",
        "opt_gemini": "Clave API de Google Gemini (Gemini 2.5 Pro, Gemini 3 Flash)",
        "opt_deepseek": "Clave API de DeepSeek (V3.2 - 22x mas barato, 74% SWE-bench)",
        "opt_kimi": "Clave API de Moonshot / Kimi (Kimi K2.5, Kimi K2 Thinking)",
        "opt_zai": "Clave API de Z.AI (GLM-5.1, Coding Plan / API)",
        "opt_multi": "Tengo varios proveedores",
        "enter_key": "Pega tu clave API",
        "verifying": "Verificando conexion...",
        "verify_ok": "Conexion verificada!",
        "verify_fail": "La conexion fallo",
        "saving_env": "Guardando en .forgegod/.env...",
        "success": "Listo!",
        "try_it": 'Probalo: forgegod run "Agrega un endpoint de hello world"',
        "init_done": "Inicializado en {path}",
        "quick_start": "Inicio rapido:",
        "run_hint": '  forgegod run "Describi tu tarea aca"',
        "local_only_hint": (
            "Corriendo en modo local ($0). Agrega claves API para modelos en la nube."
        ),
        # Errors
        "no_providers": "No se encontraron claves API ni Ollama.",
        "set_one": "Configura al menos uno:",
        "error_ollama_down": "Ollama no esta corriendo. Inicialo con: ollama serve",
        "error_ollama_no_model": (
            "Modelo '{model}' no encontrado en Ollama. Descargalo con: ollama pull {model}"
        ),
        "error_key_invalid": "Clave API invalida. Revisala en: {url}",
        "error_key_missing": "No hay clave API configurada para {provider}.",
        "error_rate_limit": (
            "Limite de tasa de {provider}. Reintentando en {seconds}s... (intento {n}/{max})"
        ),
        "error_rate_persist": (
            "Si continua, considera cambiar a modo local: forgegod init --quick"
        ),
        "error_timeout": (
            "La solicitud expiro. El modelo puede estar cargando. Reintenta en un momento."
        ),
        "error_all_failed": "Todos los modelos fallaron para rol={role}.",
        # CLI commands
        "task_done": "Tarea completada",
        "task_fail": "Tarea fallida",
        "loop_started": "Ralph Loop iniciado. Presiona Ctrl+C para detener.",
        "loop_stopped": "Loop detenido por el usuario.",
        "loop_complete": "Todas las historias completadas!",
        "dry_run_header": "MODO PRUEBA - No se ejecutaran agentes.",
        "story_order": "Orden de ejecucion de historias:",
        "dry_run_done": "Prueba completada.",
        # Doctor
        "doctor_title": "Chequeo de salud de ForgeGod",
        "doctor_pass": "OK",
        "doctor_fail": "ERROR",
        "doctor_warn": "AVISO",
        "doctor_python": "Python >= 3.11",
        "doctor_config": "Archivo de configuracion",
        "doctor_ollama": "Ollama accesible",
        "doctor_api_keys": "Superficies de auth detectadas",
        "doctor_git": "Git instalado",
        "doctor_sandbox": "Sandbox strict listo",
        "doctor_tests": "Test runner detectado",
        "doctor_all_ok": "Todos los chequeos pasaron!",
        "doctor_has_issues": "{count} problema(s) encontrado(s). Corregilos arriba.",
        # Benchmark
        "bench_running": "Ejecutando benchmark...",
        "bench_done": "Benchmark completo!",
        "bench_task": "Tarea {n}/{total}: {name}",
        "bench_attempt": "Intento {n}/2",
        "bench_model": "Modelo: {model}",
        "bench_results_title": "Resultados del benchmark",
        "bench_composite": "Puntaje compuesto",
        "bench_correctness": "Correctitud",
        "bench_quality": "Calidad",
        "bench_speed": "Velocidad",
        "bench_cost": "Costo",
        "bench_self_repair": "Auto-reparacion",
        "bench_saved": "Resultados guardados en {path}",
        "bench_readme_updated": "Leaderboard insertado en README.md",
        "bench_no_models": "No hay modelos disponibles. Ejecuta 'forgegod init' primero.",
        "bench_detecting": "Auto-detectando modelos disponibles...",
        # Terse / Caveman mode
        "terse_enabled": "Modo cavernicola activado - prompts ultra-concisos",
        "terse_savings": "Ahorro terse: {pct}% ({tokens} tokens ahorrados)",
    },
}

_lang = "en"


def detect_lang() -> str:
    """Detect language from system locale. Returns 'es' for es_* locales, else 'en'."""
    try:
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
