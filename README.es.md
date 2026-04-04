<p align="center">
  <a href="README.md"><img src="https://img.shields.io/badge/lang-en-blue.svg" alt="English"></a>
  <a href="README.es.md"><img src="https://img.shields.io/badge/lang-es-yellow.svg" alt="Español"></a>
</p>

<p align="center">
  <img src="docs/mascot.png" alt="ForgeGod" width="120" />
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
</p>

<p align="center">
  <code>19 herramientas</code> &bull; <code>5 proveedores LLM</code> &bull; <code>Memoria de 5 niveles</code> &bull; <code>Autónomo 24/7</code> &bull; <code>Modo local $0</code>
</p>

---

ForgeGod orquesta múltiples LLMs (OpenAI, Anthropic, Google Gemini, Ollama, OpenRouter) en un único motor de código autónomo. Enruta tareas al modelo correcto, corre 24/7 desde un PRD, aprende de cada resultado, y mejora su propia estrategia. Ejecutalo localmente por $0 con Ollama, o usá modelos en la nube cuando los necesites.

```bash
pip install forgegod
```

## Inicio Rápido (Sin Saber Programar)

No necesitás ser desarrollador para usar ForgeGod. Si podés describir lo que querés en español, ForgeGod escribe el código.

### Opción A: Modo Local Gratuito ($0)

1. Instalá Ollama: https://ollama.com/download
2. Descargá un modelo: `ollama pull qwen3.5:9b`
3. Instalá ForgeGod: `pip install forgegod`
4. Ejecutá: `forgegod init --lang es` (el asistente te guía)
5. Probalo: `forgegod run "Creá un sitio web simple con un formulario de contacto"`

### Opción B: Modo Nube (más rápido, ~$0.01/tarea)

1. Obtené una clave de OpenAI: https://platform.openai.com/api-keys
2. Instalá ForgeGod: `pip install forgegod`
3. Ejecutá: `forgegod init --lang es` → pegá tu clave cuando te lo pida
4. Probalo: `forgegod run "Construí una API REST con autenticación de usuarios"`

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
| Worktrees git paralelos | subagentes | - | - | - | **sí** |

### La Ventaja: Harness > Modelo

El scaffolding agrega [~11 puntos en SWE-bench](https://arxiv.org/abs/2410.06992) — la ingeniería del harness importa tanto como el modelo. ForgeGod es el harness:

- **Ralph Loop** — Código 24/7 desde un PRD. El progreso vive en git, no en el contexto del LLM. Agente fresco por historia. Sin degradación de contexto.
- **Memoria de 5 Niveles** — Episódica (qué pasó) + Semántica (qué sé) + Procedimental (cómo lo hago) + Grafo (cómo se conectan las cosas) + Errores-Soluciones (qué arregla qué). Las memorias decaen, se consolidan y se refuerzan automáticamente.
- **Coder Reflexión** — 3 intentos de generación de código con modelos escalonados: local (gratis) → nube (barato) → frontier (cuando importa). Validación AST en cada paso.
- **SICA** — Agente de Código Auto-Mejorable. Modifica sus propios prompts, ruteo de modelos y estrategia basado en resultados. 6 capas de seguridad previenen la desviación.
- **Modos de Presupuesto** — `normal` → `throttle` → `local-only` → `halt`. Activados automáticamente por gasto. Corre para siempre en Ollama por $0.

## Inicio Rápido

```bash
# Instalar
pip install forgegod

# Inicializar un proyecto
forgegod init --lang es

# Tarea única
forgegod run "Agregá un endpoint /health a server.py con uptime e info de versión"

# Planificar un proyecto → genera PRD
forgegod plan "Construí una API REST para una app de tareas con auth, CRUD y tests"

# Loop autónomo 24/7 desde PRD
forgegod loop --prd .forgegod/prd.json

# Modo cavernícola — 50-75% ahorro de tokens con prompts ultra-concisos
forgegod run --terse "Agregá un endpoint /health"

# Ver qué aprendió
forgegod memory

# Ver desglose de costos
forgegod cost

# Benchmark de modelos
forgegod benchmark

# Chequeo de salud
forgegod doctor
```

## Cómo Funciona el Ralph Loop

```
┌─────────────────────────────────────────────────┐
│                  RALPH LOOP                      │
│                                                  │
│  ┌──────┐   ┌───────┐   ┌─────────┐   ┌─────┐ │
│  │ LEER │──▶│CREAR  │──▶│EJECUTAR │──▶│VALI-│ │
│  │ PRD  │   │AGENTE │   │HISTORIA │   │ DAR │ │
│  └──────┘   └───────┘   └─────────┘   └──┬──┘ │
│      ▲                                    │     │
│      │         ┌────────┐    ┌────────┐   │     │
│      └─────────│ROTAR   │◀───│COMMIT  │◀──┘     │
│                │CONTEXTO│    │O RETRY │   ok    │
│                └────────┘    └────────┘          │
│                                                  │
│  El progreso está en GIT, no en contexto LLM.   │
│  Agente fresco por historia. Sin degradación.    │
│  Creá .forgegod/KILLSWITCH para detener.         │
└─────────────────────────────────────────────────┘
```

1. **Leer PRD** — Elegir la historia TODO de mayor prioridad
2. **Crear agente** — Contexto fresco (el progreso está en git, no en memoria)
3. **Ejecutar** — El agente usa 19 herramientas para implementar la historia
4. **Validar** — Tests, lint, sintaxis, revisión frontier
5. **Commit o retry** — Pasa: commit + marcar hecho. Falla: reintentar hasta 3x con escalamiento de modelo
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

```toml
# .forgegod/config.toml

[models]
planner = "openai:gpt-4o-mini"        # Planificación barata
coder = "ollama:qwen3-coder-next"     # Código local gratis
reviewer = "openai:o4-mini"           # Puerta de calidad
sentinel = "openai:gpt-4o"            # Muestreo frontier
escalation = "openai:gpt-4o"          # Fallback para problemas difíciles

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
export ANTHROPIC_API_KEY="sk-ant-..."     # Opcional
export OPENROUTER_API_KEY="sk-or-..."     # Opcional
export GOOGLE_API_KEY="AIza..."           # Opcional (Gemini)
```

O usá el archivo `.forgegod/.env` — `forgegod init` lo crea automáticamente.

## Modelos Soportados

| Proveedor | Modelos | Costo | Setup |
|:----------|:--------|:------|:------|
| **Ollama** | qwen3-coder-next, devstral, cualquiera | **$0** | `ollama serve` |
| OpenAI | gpt-4o, gpt-4o-mini, o3, o4-mini | $$ | `OPENAI_API_KEY` |
| Anthropic | claude-sonnet-4-6, claude-opus-4-6 | $$$ | `ANTHROPIC_API_KEY` |
| Google Gemini | gemini-2.5-pro, gemini-3-flash | $$ | `GOOGLE_API_KEY` |
| OpenRouter | 200+ modelos | varía | `OPENROUTER_API_KEY` |

## Seguridad

Defensa en profundidad, no teatro de seguridad:

- **Lista de comandos bloqueados** — 13 patrones peligrosos bloqueados (`rm -rf /`, `curl | sh`, `sudo`, fork bombs)
- **Redacción de secretos** — 11 patrones eliminan claves API de la salida de herramientas antes del contexto LLM
- **Detección de inyección de prompts** — Archivos de reglas escaneados por patrones de inyección antes de cargar
- **Límites de presupuesto** — Controles de costo previenen gasto descontrolado de API
- **Killswitch** — Creá `.forgegod/KILLSWITCH` para detener inmediatamente los loops autónomos
- **Protección de archivos sensibles** — `.env`, archivos de credenciales reciben advertencias + redacción automática

> **Advertencia**: ForgeGod ejecuta comandos shell y modifica archivos. Revisá los cambios antes de hacer commit. Iniciá el modo autónomo con `--max 5` para verificar el comportamiento.

## Contribuir

Damos la bienvenida a contribuciones. Ver [CONTRIBUTING.md](CONTRIBUTING.md) para las guías.

- Reportes de bugs y solicitudes de features: [GitHub Issues](https://github.com/waitdeadai/forgegod/issues)
- Preguntas y discusión: [GitHub Discussions](https://github.com/waitdeadai/forgegod/discussions)

## Licencia

Apache 2.0 — ver [LICENSE](LICENSE).

---

<p align="center">
  Construido por <a href="https://waitdead.com">WAITDEAD</a> &bull; Potenciado por técnicas de OpenClaw, Hermes, e investigación SOTA 2026 de agentes de código.
</p>
