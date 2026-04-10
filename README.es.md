<p align="center">
  <a href="README.md"><img src="https://img.shields.io/badge/lang-en-blue.svg" alt="English"></a>
  <a href="README.es.md"><img src="https://img.shields.io/badge/lang-es-yellow.svg" alt="Español"></a>
</p>

<p align="center">
  <img src="docs/mascot.png" alt="Mascota oficial de ForgeGod" width="120" />
</p>

<p align="center">
  <sub>Diseño oficial de la mascota por <a href="https://www.linkedin.com/in/matt-mesa/">Matias Mesa</a>.</sub>
</p>

<h1 align="center">ForgeGod</h1>

<p align="center">
  <strong>El agente de código que trabaja 24/7, aprende de sus errores, y cuesta $0 cuando quieras.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/forgegod/"><img src="https://img.shields.io/pypi/v/forgegod?color=00e5ff&style=flat-square" alt="PyPI"></a>
  <a href="https://github.com/waitdeadai/forgegod/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-00e5ff?style=flat-square" alt="Licencia"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11+-00e5ff?style=flat-square" alt="Python 3.11+"></a>
  <a href="https://github.com/waitdeadai/forgegod/actions"><img src="https://img.shields.io/github/actions/workflow/status/waitdeadai/forgegod/ci.yml?style=flat-square&color=00e5ff" alt="CI"></a>
  <a href="https://forgegod.com"><img src="https://img.shields.io/badge/site-forgegod.com-00e5ff?style=flat-square" alt="Website"></a>
  <a href="docs/AUDIT_2026-04-07.md"><img src="https://img.shields.io/badge/auditoria-2026.04.07-00e5ff?style=flat-square" alt="Auditoria"></a>
</p>

<p align="center">
  <code>23 herramientas</code> &bull; <code>8 proveedores LLM</code> &bull; <code>Memoria de 5 niveles</code> &bull; <code>Autónomo 24/7</code> &bull; <code>Modo local $0</code>
</p>

---

ForgeGod orquesta múltiples LLMs (OpenAI, Anthropic, Google Gemini, Ollama, OpenRouter, DeepSeek, Kimi via Moonshot y Z.AI GLM) en un único motor de código autónomo. Enruta tareas al modelo correcto, corre 24/7 desde un PRD, aprende de cada resultado, y mejora su propia estrategia. Ejecutalo localmente por $0 con Ollama, usá API keys cuando haga falta, o conectá autenticación nativa de OpenAI Codex y Z.AI Coding Plan dentro del CLI de ForgeGod.

```bash
pip install forgegod
```

> Nota de auditoria (re-verificada 2026-04-10): la baseline verificada ahora incluye `23` herramientas registradas, `8` familias de proveedores, `9` superficies de ruteo, `541` tests recolectados, `456` tests no-stress pasando por defecto, `84/84` stress tests pasando, lint en verde y build en verde. El camino de integracion strict con Docker sigue siendo opt-in y solo corre cuando el daemon local realmente esta listo. La entrada principal para personas ahora es el modo conversacional `forgegod`; auto-crea config local en el primer uso y ahora respeta los mismos overrides de runtime que las superficies para scripts, incluyendo `--terse`, overrides de modelo, flags de permisos/aprobacion y preferencia de proveedor OpenAI-first. `forgegod run` queda como superficie explicita para scripts, `forgegod evals` ahora cubre regresiones deterministicas de chat, run, loop, worktree e interfaz strict, y `forgegod loop` ya no auto-commitea ni hace auto-push por defecto. Lee [docs/AUDIT_2026-04-07.md](docs/AUDIT_2026-04-07.md), [docs/OPERATIONS.md](docs/OPERATIONS.md) y [docs/WEB_RESEARCH_2026-04-07.md](docs/WEB_RESEARCH_2026-04-07.md) antes de tocar comportamiento de runtime.

### Harness Experimental Recomendado: GLM-5.1 + Codex

Para la configuración por suscripción más fuerte hoy dentro de ForgeGod, usá
`glm-5.1` para `planner` / `researcher` / `coder` y `openai-codex:gpt-5.4`
para `reviewer` / `sentinel` / `escalation`.

Mirá [docs/GLM_CODEX_HARNESS_2026-04-08.md](docs/GLM_CODEX_HARNESS_2026-04-08.md),
[docs/examples/glm_codex_coding_plan.toml](docs/examples/glm_codex_coding_plan.toml),
y corré `python scripts/smoke_glm_codex_harness.py` antes de usarlo en tareas críticas.
El camino con `ZAI_CODING_API_KEY` funciona hoy en ForgeGod, pero sigue siendo
experimental hasta que Z.AI reconozca explícitamente a ForgeGod como coding
tool soportada.

### Harness OpenAI-First: Builder por API + Reviewer por Codex

Si querés mantener ForgeGod dentro de superficies OpenAI, aplicá una
preferencia explícita OpenAI-first:

- `planner = openai:gpt-5.4`
- `coder = openai:gpt-5.4-mini`
- `reviewer = openai-codex:gpt-5.4`
- `sentinel = openai:gpt-5.4`
- `escalation = openai:gpt-5.4`
- `researcher = openai:gpt-5.4-mini`

```bash
forgegod auth sync --profile adversarial --prefer-provider openai
```

Eso mantiene el split adversarial, pero sesga el harness hacia OpenAI API más
la suscripción Codex cuando ambas superficies están conectadas. El billing de
ChatGPT/Codex y el billing del API de OpenAI siguen siendo superficies separadas.

Si querés una configuración más simple, ForgeGod también soporta `single-model`
durante `forgegod init` y `forgegod auth sync --profile single-model`. Eso
fuerza todos los roles a un solo modelo detectado en lugar del split
adversarial recomendado.

`forgegod` ahora es la entrada principal conversacional para personas y
auto-crea config local en el primer uso. Usá `forgegod init` si querés el
wizard guiado, y `forgegod run "..."` cuando necesites una superficie no
interactiva y reproducible para scripts, CI o automatización. Esa misma
entrada raíz también acepta overrides de sesión como `--terse`, `--model`,
`--review/--no-review`, `--permission-mode`, `--approval-mode` y
`--allow-tool`.

## Inicio Rápido (Sin Saber Programar)

No necesitás ser desarrollador para usar ForgeGod. Si podés describir lo que querés en español, ForgeGod escribe el código.

### Opción A: Modo Local Gratuito ($0)

1. Instalá Ollama: https://ollama.com/download
2. Descargá un modelo: `ollama pull qwen3.5:9b`
3. Instalá ForgeGod: `pip install forgegod`
4. Iniciá la sesión: `forgegod`
5. Pedile algo en lenguaje natural, por ejemplo: `Creá un sitio web simple con un formulario de contacto`
6. Si querés el wizard guiado, corré: `forgegod init --lang es`


### Opción B: Modo Suscripción OpenAI Nativa

1. Instalá ForgeGod: `pip install forgegod`
2. Ejecutá: `forgegod auth login openai-codex`
3. Ejecutá: `forgegod auth sync --profile adversarial --prefer-provider openai`
4. Iniciá la sesión: `forgegod`
5. Pedile algo en lenguaje natural, por ejemplo: `Construí una API REST con autenticación de usuarios`

### Opción C: Modo Z.AI Coding Plan

1. Exportá `ZAI_CODING_API_KEY=...`
2. Instalá ForgeGod: `pip install forgegod`
3. Ejecutá: `forgegod auth sync --profile adversarial --prefer-provider openai`
4. Iniciá la sesión: `forgegod`
5. Pedile algo en lenguaje natural, por ejemplo: `Construí una API REST con autenticación de usuarios`

### ¿Algo no funciona?

Ejecutá `forgegod doctor` — revisa tu instalación y te dice exactamente qué corregir.

## Por Qué ForgeGod es Diferente

Todos los demás CLIs de código usan **un modelo a la vez** y **se reinician a cero** cada sesión. ForgeGod no.

| Capacidad | Claude Code | Codex CLI | Aider | Cursor | **ForgeGod** |
|:----------|:----------:|:---------:|:-----:|:------:|:------------:|
| Ruteo multi-modelo automático | - | - | manual | - | **sí** |
| Híbrido local + nube | - | básico | básico | - | **nativo** |
| Loops autónomos 24/7 | - | - | - | - | **sí** |
| Memoria entre sesiones | básica | - | - | removida | **5 niveles** |
| Estrategia auto-mejorable | - | - | - | - | **sí (SICA)** |
| Modos de presupuesto | - | - | - | - | **sí** |
| Generación Reflexión | - | - | - | - | **3 intentos** |
| Worktrees git paralelos | subagentes | - | - | - | **experimental** |
| Probado bajo estrés + benchmarks | - | - | - | - | **[linea base auditada](docs/AUDIT_2026-04-07.md)** |

### La Ventaja: Harness > Modelo

El scaffolding agrega [~11 puntos en SWE-bench](https://arxiv.org/abs/2410.06992) — la ingeniería del harness importa tanto como el modelo. ForgeGod es el harness:

- **Ralph Loop** — Código 24/7 desde un PRD. El progreso vive en git, no en el contexto del LLM. Agente fresco por historia. Sin degradación de contexto.
- **Memoria de 5 Niveles** — Episódica (qué pasó) + Semántica (qué sé) + Procedimental (cómo lo hago) + Grafo (cómo se conectan las cosas) + Errores-Soluciones (qué arregla qué). Las memorias decaen, se consolidan y se refuerzan automáticamente.
- **Coder Reflexión** — 3 intentos de generación de código con modelos escalonados: local (gratis) → nube (barato) → frontier (cuando importa). El repo ya conecta scoping de workspace, auditoría de comandos, rutas bloqueadas y advertencias de código generado en runtime, mientras la auditoría sigue marcando los gaps de hardening que quedan.
- **DESIGN.md Nativo** — Importás un preset, dejás `DESIGN.md` en la raíz, y las tareas frontend heredan ese lenguaje visual automáticamente.
- **Modo Contribución** — Lee `CONTRIBUTING.md`, inspecciona el repo, detecta issues abordables, y planifica o ejecuta cambios chicos respetando reglas del proyecto.
- **SICA** — Agente de Código Auto-Mejorable. Modifica sus propios prompts, ruteo de modelos y estrategia basado en resultados. 6 capas de seguridad previenen la desviación.
- **Modos de Presupuesto** — `normal` → `throttle` → `local-only` → `halt`. Activados automáticamente por gasto. Corre para siempre en Ollama por $0.

## Inicio Rápido

```bash
# Instalar
pip install forgegod

# Camino más rápido: hablar con ForgeGod directo
forgegod

# Setup guiado opcional
forgegod init --lang es

# O forzar un estilo de harness explícitamente
forgegod init --lang es --profile adversarial
forgegod init --lang es --profile single-model

# Ver superficies de auth nativas
forgegod auth status

# Vincular la suscripción de OpenAI Codex y sincronizar defaults
forgegod auth login openai-codex
forgegod auth sync --profile adversarial --prefer-provider openai

# Hablar con ForgeGod en lenguaje natural
forgegod

# Superficie explícita para scripts
forgegod run "Agregá un endpoint /health a server.py con uptime e info de versión"

# Evals deterministicas del harness
forgegod evals
forgegod evals --case chat_natural_language_roundtrip

# Planificar un proyecto → genera PRD
forgegod plan "Construí una API REST para una app de tareas con auth, CRUD y tests"

# Loop autónomo 24/7 desde PRD
# Valores por defecto del loop: sin auto-commit ni auto-push salvo que lo actives explícitamente
# Los workers paralelos requieren un repo git con al menos un commit porque ForgeGod usa worktrees aislados
forgegod loop --prd .forgegod/prd.json

# Modo cavernícola — 50-75% ahorro de tokens con prompts ultra-concisos
forgegod --terse

# Ver qué aprendió
forgegod memory

# Ver desglose de costos
forgegod cost

# Benchmark de modelos
forgegod benchmark

# Evals del harness
forgegod evals

# Instalar un preset DESIGN.md para trabajo frontend
forgegod design pull claude

# Planear una contribución sobre otro repo
forgegod contribute https://github.com/owner/repo --goal "Mejorar tests"

# Chequeo de salud
forgegod doctor
```

## Cómo Funciona el Ralph Loop

```
┌─────────────────────────────────────────────────┐
│                  RALPH LOOP                     │
│                                                 │
│  ┌──────┐   ┌───────┐   ┌─────────┐   ┌─────┐   │
│  │ LEER │──▶│ CREAR │──▶│EJECUTAR │──▶│VALI-│   │
│  │ PRD  │   │AGENTE │   │HISTORIA │   │ DAR │   │
│  └──────┘   └───────┘   └─────────┘   └──┬──┘   │
│      ▲                                     │     │
│      │         ┌────────┐    ┌────────┐    │     │
│      └─────────│ ROTAR  │◀───│ COMMIT │◀───┘     │
│                │CONTEXTO│    │O RETRY │   ok     │
│                └────────┘    └────────┘          │
│                                                 │
│  El progreso está en GIT, no en contexto LLM.  │
│  Agente fresco por historia. Sin degradación.  │
│  Creá .forgegod/KILLSWITCH para detener.       │
└─────────────────────────────────────────────────┘
```

1. **Leer PRD** — Elegir la historia TODO de mayor prioridad
2. **Crear agente** — Contexto fresco (el progreso está en git, no en memoria)
3. **Ejecutar** — El agente usa 23 herramientas para implementar la historia
4. **Validar** — Tests, lint, sintaxis, revisión frontier
5. **Finalizar o retry** — Pasa: revisar diff + marcar hecho. Falla: reintentar hasta 3x con escalamiento de modelo
6. **Rotar** — Siguiente historia. El contexto siempre es fresco.

## Sistema de Memoria de 5 Niveles

ForgeGod tiene el sistema de memoria más avanzado de cualquier agente de código open-source:

| Nivel | Qué | Cómo | Retención |
|:------|:----|:-----|:----------|
| **Episódica** | Qué pasó por tarea | Registros completos de resultado | 90 días |
| **Semántica** | Principios extraídos | Confianza + decaimiento + refuerzo | Indefinido |
| **Procedimental** | Patrones de código y recetas | Seguimiento de tasa de éxito | Indefinido |
| **Grafo** | Relaciones + aristas causales | Auto-extraído de resultados | Indefinido |
| **Errores-Soluciones** | Patrón de error → solución | Búsqueda fuzzy | Indefinido |

Las memorias **decaen** sin refuerzo (vida media de 30 días), se **consolidan** automáticamente (fusionan similares, podan débiles), y se **inyectan** en cada prompt como un Memory Spine ranqueado por relevancia + recencia + importancia.

## Modos de Presupuesto

| Modo | Comportamiento | Disparador |
|:-----|:---------------|:-----------|
| `normal` | Usa todos los modelos configurados | Por defecto |
| `throttle` | Preferir local, nube solo para revisión | 80% del límite diario |
| `local-only` | Solo Ollama, **operación $0** | Manual o 95% del límite |
| `halt` | Detener todas las llamadas LLM | 100% del límite diario |

## Modo Cavernícola (`--terse`)

Prompts ultra-concisos que reducen el uso de tokens 50-75% sin pérdida de precisión para tareas de código. Respaldado por investigación 2026:

- [Mini-SWE-Agent](https://github.com/SWE-agent/mini-swe-agent) — 100 líneas, >74% SWE-bench Verified
- [Chain of Draft](https://arxiv.org/abs/2502.18600) — 7.6% tokens, misma precisión
- [CCoT](https://arxiv.org/abs/2401.05618) — 48.7% más corto, impacto insignificante

```bash
# Agregá --terse a cualquier comando
forgegod --terse
forgegod run --terse "Construí una API REST"
forgegod loop --terse --prd .forgegod/prd.json

# O habilitalo globalmente en config
# [terse]
# enabled = true
```

## Leaderboard de Modelos

Ejecutá el tuyo: `forgegod benchmark`

| Modelo | Compuesto | Correctitud | Calidad | Velocidad | Costo | Auto-Reparación |
|:-------|:---------:|:-----------:|:-------:|:---------:|:-----:|:---------------:|
| openai:gpt-4o-mini | 81.5 | 10/12 | 7.4 | 12s prom | $0.08 | 4/4 |
| ollama:qwen3.5:9b | 72.3 | 8/12 | 6.8 | 45s prom | $0.00 | 3/4 |

*Ejecutá `forgegod benchmark --update-readme` para actualizar con tus propios resultados.*

## Configuración

ForgeGod usa config TOML con prioridad de 3 niveles: variables de entorno > proyecto > global.

`forgegod` auto-crea `.forgegod/config.toml` en la primera sesión conversacional con defaults sensibles a la auth detectada cuando puede. `forgegod init` y `forgegod auth sync` también escriben esos defaults y guardan `harness.profile` como `adversarial` o `single-model`. El ejemplo de abajo muestra la forma del archivo, no la única combinación recomendada.

```toml
# .forgegod/config.toml

[models]
planner = "openai:gpt-5.4"            # Planificación frontier
coder = "ollama:qwen3-coder-next"     # Código local gratis
reviewer = "openai:gpt-5.4"           # Puerta de calidad
sentinel = "openai:gpt-5.4"           # Muestreo frontier
escalation = "openai:gpt-5.4"         # Fallback para problemas difíciles
researcher = "openai:gpt-5.4-mini"    # Recon / síntesis web

[budget]
daily_limit_usd = 5.00
mode = "normal"

[ollama]
host = "http://localhost:11434"
model = "qwen3-coder-next"
```

### Variables de Entorno

```bash
export OPENAI_API_KEY="sk-..."
forgegod auth login openai-codex           # Auth nativa OpenAI con ChatGPT
export ANTHROPIC_API_KEY="sk-ant-..."     # Opcional
export OPENROUTER_API_KEY="sk-or-..."     # Opcional
export GOOGLE_API_KEY="AIza..."           # Opcional (Gemini)
export DEEPSEEK_API_KEY="sk-..."          # Opcional
export MOONSHOT_API_KEY="sk-..."          # Opcional (Kimi / Moonshot)
export ZAI_CODING_API_KEY="..."           # Opcional (Z.AI Coding Plan)
export ZAI_API_KEY="..."                  # Opcional (Z.AI API general)
```

O usá el archivo `.forgegod/.env` — `forgegod init` lo crea automáticamente.

## Modelos Soportados

| Proveedor | Modelos | Costo | Setup |
|:----------|:--------|:------|:------|
| **Ollama** | qwen3-coder-next, devstral, cualquiera | **$0** | `ollama serve` |
| OpenAI API | gpt-5.4, gpt-5.4-mini, gpt-5.4-nano, o3, o4-mini | $$ | `OPENAI_API_KEY` |
| Suscripción OpenAI Codex | gpt-5.4 vía superficie Codex | Incluida en planes ChatGPT soportados | `forgegod auth login openai-codex` |
| Anthropic | claude-sonnet-4-6, claude-opus-4-6 | $$$ | `ANTHROPIC_API_KEY` |
| Google Gemini | gemini-2.5-pro, gemini-3-flash | $$ | `GOOGLE_API_KEY` |
| DeepSeek | deepseek-chat, deepseek-reasoner | $ | `DEEPSEEK_API_KEY` |
| Kimi (Moonshot directo) | kimi-k2.5, kimi-k2-thinking | $$ | `MOONSHOT_API_KEY` |
| Z.AI / GLM | glm-5.1, glm-5, glm-4.7 | $$ | `ZAI_CODING_API_KEY` o `ZAI_API_KEY` |
| OpenRouter | 200+ modelos | varía | `OPENROUTER_API_KEY` |

El soporte de Kimi usa la API OpenAI-compatible oficial de Moonshot y hoy es experimental dentro de ForgeGod. Correlalo con tus benchmarks antes de convertirlo en modelo por defecto.
El soporte por suscripción de OpenAI Codex hoy es más fuerte para planner/reviewer/adversary. También puede usarse como superficie de ruteo para código, pero el loop de coder sigue siendo experimental y conviene benchmarkearlo antes de dejarlo como coder remoto por defecto.
OpenRouter sigue funcionando con keys/créditos. Alibaba/Qwen Coding Plan sigue en evaluación porque la documentación oficial actual lo acota a coding tools soportadas, no a loops autónomos genéricos.

Regla practica del harness:

- `forgegod benchmark` mide performance de codigo/modelos sobre tareas scaffold
- `forgegod evals` mide a ForgeGod mismo: UX conversacional, aprobaciones,
  denegaciones por permisos, disciplina del completion gate, comportamiento de
  loop/worktree y manejo de la interfaz strict

## Seguridad

Defensa en profundidad, no teatro de seguridad:

- **Lista de comandos bloqueados** — 13 patrones peligrosos bloqueados (`rm -rf /`, `curl | sh`, `sudo`, fork bombs)
- **Redacción de secretos** — 11 patrones eliminan claves API de la salida de herramientas antes del contexto LLM
- **Detección de inyección de prompts** — Archivos de reglas escaneados por patrones de inyección antes de cargar
- **Límites de presupuesto** — Controles de costo previenen gasto descontrolado de API
- **Killswitch** — Creá `.forgegod/KILLSWITCH` para detener inmediatamente los loops autónomos
- **Protección de archivos sensibles** — `.env`, archivos de credenciales reciben advertencias + redacción automática

> **Advertencia**: ForgeGod ejecuta comandos shell y modifica archivos. Segun la linea base verificada del 2026-04-08, `strict` usa un backend real de sandbox con Docker y se bloquea si faltan Docker o la imagen requerida, mientras que `standard` sigue siendo un flujo local con guardrails. Revisá los cambios en una branch o worktree descartable antes de usar modo autonomo.

## Documentacion Operativa

- [AGENTS.md](AGENTS.md) — instrucciones locales para agentes de codigo
- [docs/OPERATIONS.md](docs/OPERATIONS.md) — sistema de registro actual y comandos verificados
- [docs/AUDIT_2026-04-07.md](docs/AUDIT_2026-04-07.md) — auditoria detallada y orden de remediacion
- [docs/WEB_RESEARCH_2026-04-07.md](docs/WEB_RESEARCH_2026-04-07.md) — investigacion externa usada para estructurar la documentacion

## Contribuir

Damos la bienvenida a contribuciones. Ver [CONTRIBUTING.md](CONTRIBUTING.md) para las guías.

- Reportes de bugs y solicitudes de features: [GitHub Issues](https://github.com/waitdeadai/forgegod/issues)
- Preguntas y discusión: [GitHub Discussions](https://github.com/waitdeadai/forgegod/discussions)

## Colaboradores

ForgeGod acredita públicamente trabajo de código y no-código.

- [Matias Mesa](https://www.linkedin.com/in/matt-mesa/) - `design` - sistema oficial de mascota de ForgeGod
- [WAITDEAD](https://waitdead.com) - `code`, `infra`, `research`, `projectManagement`, `maintenance`

Ver [CONTRIBUTORS.md](CONTRIBUTORS.md) para la lista actual de colaboradores.

## Licencia

Apache 2.0 — ver [LICENSE](LICENSE).

---

<p align="center">
  Construido por <a href="https://waitdead.com">WAITDEAD</a> &bull; Diseño oficial de la mascota por <a href="https://www.linkedin.com/in/matt-mesa/">Matias Mesa</a> &bull; Potenciado por técnicas de OpenClaw, Hermes, e investigación SOTA 2026 de agentes de código.
</p>
