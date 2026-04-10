<p align="center">
  <a href="README.md"><img src="https://img.shields.io/badge/lang-en-blue.svg" alt="English"></a>
  <a href="README.es.md"><img src="https://img.shields.io/badge/lang-es-yellow.svg" alt="EspaÃ±ol"></a>
</p>

<p align="center">
  <img src="docs/mascot.png" alt="Mascota oficial de ForgeGod" width="120" />
</p>

<p align="center">
  <sub>DiseÃ±o oficial de la mascota por <a href="https://www.linkedin.com/in/matt-mesa/">Matias Mesa</a>.</sub>
</p>

<h1 align="center">ForgeGod</h1>

<p align="center">
  <strong>El agente de cÃ³digo que trabaja 24/7, aprende de sus errores, y cuesta $0 cuando quieras.</strong>
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
  <code>23 herramientas</code> &bull; <code>8 proveedores LLM</code> &bull; <code>Memoria de 5 niveles</code> &bull; <code>AutÃ³nomo 24/7</code> &bull; <code>Modo local $0</code>
</p>

---

ForgeGod orquesta mÃºltiples LLMs (OpenAI, Anthropic, Google Gemini, Ollama, OpenRouter, DeepSeek, Kimi via Moonshot y Z.AI GLM) en un Ãºnico motor de cÃ³digo autÃ³nomo. Enruta tareas al modelo correcto, corre 24/7 desde un PRD, aprende de cada resultado, y mejora su propia estrategia. Ejecutalo localmente por $0 con Ollama, usÃ¡ API keys cuando haga falta, o conectÃ¡ autenticaciÃ³n nativa de OpenAI Codex y Z.AI Coding Plan dentro del CLI de ForgeGod.

```bash
pip install forgegod
```

> Nota de auditoria (re-verificada 2026-04-10): la baseline verificada ahora incluye `23` herramientas registradas, `8` familias de proveedores, `9` superficies de ruteo, `537` tests recolectados, `452` tests no-stress pasando por defecto, `84/84` stress tests pasando, lint en verde y build en verde. El camino de integracion strict con Docker sigue siendo opt-in y solo corre cuando el daemon local realmente esta listo. La entrada principal para personas ahora es el modo conversacional `forgegod`; auto-crea config local en el primer uso y ahora respeta los mismos overrides de runtime que las superficies para scripts, incluyendo `--terse`, overrides de modelo y flags de permisos/aprobacion. `forgegod run` queda como superficie explicita para scripts, `forgegod evals` como superficie deterministica de regresion del harness, y `forgegod loop` ya no auto-commitea ni hace auto-push por defecto. Lee [docs/AUDIT_2026-04-07.md](docs/AUDIT_2026-04-07.md), [docs/OPERATIONS.md](docs/OPERATIONS.md) y [docs/WEB_RESEARCH_2026-04-07.md](docs/WEB_RESEARCH_2026-04-07.md) antes de tocar comportamiento de runtime.

### Harness Experimental Recomendado: GLM-5.1 + Codex

Para la configuraciÃ³n por suscripciÃ³n mÃ¡s fuerte hoy dentro de ForgeGod, usÃ¡
`glm-5.1` para `planner` / `researcher` / `coder` y `openai-codex:gpt-5.4`
para `reviewer` / `sentinel` / `escalation`.

MirÃ¡ [docs/GLM_CODEX_HARNESS_2026-04-08.md](docs/GLM_CODEX_HARNESS_2026-04-08.md),
[docs/examples/glm_codex_coding_plan.toml](docs/examples/glm_codex_coding_plan.toml),
y corrÃ© `python scripts/smoke_glm_codex_harness.py` antes de usarlo en tareas crÃ­ticas.
El camino con `ZAI_CODING_API_KEY` funciona hoy en ForgeGod, pero sigue siendo
experimental hasta que Z.AI reconozca explÃ­citamente a ForgeGod como coding
tool soportada.

Si querÃƒÂ©s una configuraciÃƒÂ³n mÃƒÂ¡s simple, ForgeGod tambiÃƒÂ©n soporta `single-model`
durante `forgegod init` y `forgegod auth sync --profile single-model`. Eso
fuerza todos los roles a un solo modelo detectado en lugar del split
adversarial recomendado.

`forgegod` ahora es la entrada principal conversacional para personas y
auto-crea config local en el primer uso. UsÃ¡ `forgegod init` si querÃ©s el
wizard guiado, y `forgegod run "..."` cuando necesites una superficie no
interactiva y reproducible para scripts, CI o automatizaciÃ³n. Esa misma
entrada raÃ­z tambiÃ©n acepta overrides de sesiÃ³n como `--terse`, `--model`,
`--review/--no-review`, `--permission-mode`, `--approval-mode` y
`--allow-tool`.

## Inicio RÃ¡pido (Sin Saber Programar)

No necesitÃ¡s ser desarrollador para usar ForgeGod. Si podÃ©s describir lo que querÃ©s en espaÃ±ol, ForgeGod escribe el cÃ³digo.

### OpciÃ³n A: Modo Local Gratuito ($0)

1. InstalÃ¡ Ollama: https://ollama.com/download
2. DescargÃ¡ un modelo: `ollama pull qwen3.5:9b`
3. InstalÃ¡ ForgeGod: `pip install forgegod`
4. IniciÃ¡ la sesiÃ³n: `forgegod`
5. Pedile algo en lenguaje natural, por ejemplo: `CreÃ¡ un sitio web simple con un formulario de contacto`
6. Si querÃ©s el wizard guiado, corrÃ©: `forgegod init --lang es`


### OpciÃ³n B: Modo SuscripciÃ³n OpenAI Nativa

1. InstalÃ¡ ForgeGod: `pip install forgegod`
2. EjecutÃ¡: `forgegod auth login openai-codex`
3. EjecutÃ¡: `forgegod auth sync --profile adversarial`
4. IniciÃ¡ la sesiÃ³n: `forgegod`
5. Pedile algo en lenguaje natural, por ejemplo: `ConstruÃ­ una API REST con autenticaciÃ³n de usuarios`

### OpciÃ³n C: Modo Z.AI Coding Plan

1. ExportÃ¡ `ZAI_CODING_API_KEY=...`
2. InstalÃ¡ ForgeGod: `pip install forgegod`
3. EjecutÃ¡: `forgegod auth sync --profile adversarial`
4. IniciÃ¡ la sesiÃ³n: `forgegod`
5. Pedile algo en lenguaje natural, por ejemplo: `ConstruÃ­ una API REST con autenticaciÃ³n de usuarios`

### Â¿Algo no funciona?

EjecutÃ¡ `forgegod doctor` â€” revisa tu instalaciÃ³n y te dice exactamente quÃ© corregir.

## Por QuÃ© ForgeGod es Diferente

Todos los demÃ¡s CLIs de cÃ³digo usan **un modelo a la vez** y **se reinician a cero** cada sesiÃ³n. ForgeGod no.

| Capacidad | Claude Code | Codex CLI | Aider | Cursor | **ForgeGod** |
|:----------|:----------:|:---------:|:-----:|:------:|:------------:|
| Ruteo multi-modelo automÃ¡tico | - | - | manual | - | **sÃ­** |
| HÃ­brido local + nube | - | bÃ¡sico | bÃ¡sico | - | **nativo** |
| Loops autÃ³nomos 24/7 | - | - | - | - | **sÃ­** |
| Memoria entre sesiones | bÃ¡sica | - | - | removida | **5 niveles** |
| Estrategia auto-mejorable | - | - | - | - | **sÃ­ (SICA)** |
| Modos de presupuesto | - | - | - | - | **sÃ­** |
| GeneraciÃ³n ReflexiÃ³n | - | - | - | - | **3 intentos** |
| Worktrees git paralelos | subagentes | - | - | - | **experimental** |
| Probado bajo estrÃ©s + benchmarks | - | - | - | - | **[linea base auditada](docs/AUDIT_2026-04-07.md)** |

### La Ventaja: Harness > Modelo

El scaffolding agrega [~11 puntos en SWE-bench](https://arxiv.org/abs/2410.06992) â€” la ingenierÃ­a del harness importa tanto como el modelo. ForgeGod es el harness:

- **Ralph Loop** â€” CÃ³digo 24/7 desde un PRD. El progreso vive en git, no en el contexto del LLM. Agente fresco por historia. Sin degradaciÃ³n de contexto.
- **Memoria de 5 Niveles** â€” EpisÃ³dica (quÃ© pasÃ³) + SemÃ¡ntica (quÃ© sÃ©) + Procedimental (cÃ³mo lo hago) + Grafo (cÃ³mo se conectan las cosas) + Errores-Soluciones (quÃ© arregla quÃ©). Las memorias decaen, se consolidan y se refuerzan automÃ¡ticamente.
- **Coder ReflexiÃ³n** â€” 3 intentos de generaciÃ³n de cÃ³digo con modelos escalonados: local (gratis) â†’ nube (barato) â†’ frontier (cuando importa). El repo ya conecta scoping de workspace, auditorÃ­a de comandos, rutas bloqueadas y advertencias de cÃ³digo generado en runtime, mientras la auditorÃ­a sigue marcando los gaps de hardening que quedan.
- **DESIGN.md Nativo** â€” ImportÃ¡s un preset, dejÃ¡s `DESIGN.md` en la raÃ­z, y las tareas frontend heredan ese lenguaje visual automÃ¡ticamente.
- **Modo ContribuciÃ³n** â€” Lee `CONTRIBUTING.md`, inspecciona el repo, detecta issues abordables, y planifica o ejecuta cambios chicos respetando reglas del proyecto.
- **SICA** â€” Agente de CÃ³digo Auto-Mejorable. Modifica sus propios prompts, ruteo de modelos y estrategia basado en resultados. 6 capas de seguridad previenen la desviaciÃ³n.
- **Modos de Presupuesto** â€” `normal` â†’ `throttle` â†’ `local-only` â†’ `halt`. Activados automÃ¡ticamente por gasto. Corre para siempre en Ollama por $0.

## Inicio RÃ¡pido

```bash
# Instalar
pip install forgegod

# Camino mÃ¡s rÃ¡pido: hablar con ForgeGod directo
forgegod

# Setup guiado opcional
forgegod init --lang es

# O forzar un estilo de harness explÃ­citamente
forgegod init --lang es --profile adversarial
forgegod init --lang es --profile single-model

# Ver superficies de auth nativas
forgegod auth status

# Vincular la suscripciÃ³n de OpenAI Codex y sincronizar defaults
forgegod auth login openai-codex
forgegod auth sync --profile adversarial

# Hablar con ForgeGod en lenguaje natural
forgegod

# Superficie explÃ­cita para scripts
forgegod run "AgregÃ¡ un endpoint /health a server.py con uptime e info de versiÃ³n"

# Evals deterministicas del harness
forgegod evals
forgegod evals --case chat_natural_language_roundtrip

# Planificar un proyecto â†’ genera PRD
forgegod plan "ConstruÃ­ una API REST para una app de tareas con auth, CRUD y tests"

# Loop autÃ³nomo 24/7 desde PRD
# Valores por defecto del loop: sin auto-commit ni auto-push salvo que lo actives explÃ­citamente
# Los workers paralelos requieren un repo git con al menos un commit porque ForgeGod usa worktrees aislados
forgegod loop --prd .forgegod/prd.json

# Modo cavernÃ­cola â€” 50-75% ahorro de tokens con prompts ultra-concisos
forgegod --terse

# Ver quÃ© aprendiÃ³
forgegod memory

# Ver desglose de costos
forgegod cost

# Benchmark de modelos
forgegod benchmark

# Evals del harness
forgegod evals

# Instalar un preset DESIGN.md para trabajo frontend
forgegod design pull claude

# Planear una contribuciÃ³n sobre otro repo
forgegod contribute https://github.com/owner/repo --goal "Mejorar tests"

# Chequeo de salud
forgegod doctor
```

## CÃ³mo Funciona el Ralph Loop

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                  RALPH LOOP                      â”‚
â”‚                                                  â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”   â”Œâ”€â”€â”€â”€â”€â”€â”€â”   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”   â”Œâ”€â”€â”€â”€â”€â” â”‚
â”‚  â”‚ LEER â”‚â”€â”€â–¶â”‚CREAR  â”‚â”€â”€â–¶â”‚EJECUTAR â”‚â”€â”€â–¶â”‚VALI-â”‚ â”‚
â”‚  â”‚ PRD  â”‚   â”‚AGENTE â”‚   â”‚HISTORIA â”‚   â”‚ DAR â”‚ â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”˜   â””â”€â”€â”€â”€â”€â”€â”€â”˜   â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜   â””â”€â”€â”¬â”€â”€â”˜ â”‚
â”‚      â–²                                    â”‚     â”‚
â”‚      â”‚         â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”   â”‚     â”‚
â”‚      â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”‚ROTAR   â”‚â—€â”€â”€â”€â”‚COMMIT  â”‚â—€â”€â”€â”˜     â”‚
â”‚                â”‚CONTEXTOâ”‚    â”‚O RETRY â”‚   ok    â”‚
â”‚                â””â”€â”€â”€â”€â”€â”€â”€â”€â”˜    â””â”€â”€â”€â”€â”€â”€â”€â”€â”˜          â”‚
â”‚                                                  â”‚
â”‚  El progreso estÃ¡ en GIT, no en contexto LLM.   â”‚
â”‚  Agente fresco por historia. Sin degradaciÃ³n.    â”‚
â”‚  CreÃ¡ .forgegod/KILLSWITCH para detener.         â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

1. **Leer PRD** â€” Elegir la historia TODO de mayor prioridad
2. **Crear agente** â€” Contexto fresco (el progreso estÃ¡ en git, no en memoria)
3. **Ejecutar** â€” El agente usa 23 herramientas para implementar la historia
4. **Validar** â€” Tests, lint, sintaxis, revisiÃ³n frontier
5. **Finalizar o retry** â€” Pasa: revisar diff + marcar hecho. Falla: reintentar hasta 3x con escalamiento de modelo
6. **Rotar** â€” Siguiente historia. El contexto siempre es fresco.

## Sistema de Memoria de 5 Niveles

ForgeGod tiene el sistema de memoria mÃ¡s avanzado de cualquier agente de cÃ³digo open-source:

| Nivel | QuÃ© | CÃ³mo | RetenciÃ³n |
|:------|:----|:-----|:----------|
| **EpisÃ³dica** | QuÃ© pasÃ³ por tarea | Registros completos de resultado | 90 dÃ­as |
| **SemÃ¡ntica** | Principios extraÃ­dos | Confianza + decaimiento + refuerzo | Indefinido |
| **Procedimental** | Patrones de cÃ³digo y recetas | Seguimiento de tasa de Ã©xito | Indefinido |
| **Grafo** | Relaciones + aristas causales | Auto-extraÃ­do de resultados | Indefinido |
| **Errores-Soluciones** | PatrÃ³n de error â†’ soluciÃ³n | BÃºsqueda fuzzy | Indefinido |

Las memorias **decaen** sin refuerzo (vida media de 30 dÃ­as), se **consolidan** automÃ¡ticamente (fusionan similares, podan dÃ©biles), y se **inyectan** en cada prompt como un Memory Spine ranqueado por relevancia + recencia + importancia.

## Modos de Presupuesto

| Modo | Comportamiento | Disparador |
|:-----|:---------------|:-----------|
| `normal` | Usa todos los modelos configurados | Por defecto |
| `throttle` | Preferir local, nube solo para revisiÃ³n | 80% del lÃ­mite diario |
| `local-only` | Solo Ollama, **operaciÃ³n $0** | Manual o 95% del lÃ­mite |
| `halt` | Detener todas las llamadas LLM | 100% del lÃ­mite diario |

## Modo CavernÃ­cola (`--terse`)

Prompts ultra-concisos que reducen el uso de tokens 50-75% sin pÃ©rdida de precisiÃ³n para tareas de cÃ³digo. Respaldado por investigaciÃ³n 2026:

- [Mini-SWE-Agent](https://github.com/SWE-agent/mini-swe-agent) â€” 100 lÃ­neas, >74% SWE-bench Verified
- [Chain of Draft](https://arxiv.org/abs/2502.18600) â€” 7.6% tokens, misma precisiÃ³n
- [CCoT](https://arxiv.org/abs/2401.05618) â€” 48.7% mÃ¡s corto, impacto insignificante

```bash
# AgregÃ¡ --terse a cualquier comando
forgegod --terse
forgegod run --terse "ConstruÃ­ una API REST"
forgegod loop --terse --prd .forgegod/prd.json

# O habilitalo globalmente en config
# [terse]
# enabled = true
```

## Leaderboard de Modelos

EjecutÃ¡ el tuyo: `forgegod benchmark`

| Modelo | Compuesto | Correctitud | Calidad | Velocidad | Costo | Auto-ReparaciÃ³n |
|:-------|:---------:|:-----------:|:-------:|:---------:|:-----:|:---------------:|
| openai:gpt-4o-mini | 81.5 | 10/12 | 7.4 | 12s prom | $0.08 | 4/4 |
| ollama:qwen3.5:9b | 72.3 | 8/12 | 6.8 | 45s prom | $0.00 | 3/4 |

*EjecutÃ¡ `forgegod benchmark --update-readme` para actualizar con tus propios resultados.*

## ConfiguraciÃ³n

ForgeGod usa config TOML con prioridad de 3 niveles: variables de entorno > proyecto > global.

`forgegod` auto-crea `.forgegod/config.toml` en la primera sesiÃ³n conversacional con defaults sensibles a la auth detectada cuando puede. `forgegod init` y `forgegod auth sync` tambiÃ©n escriben esos defaults y guardan `harness.profile` como `adversarial` o `single-model`. El ejemplo de abajo muestra la forma del archivo, no la Ãºnica combinaciÃ³n recomendada.

```toml
# .forgegod/config.toml

[models]
planner = "openai:gpt-4o-mini"        # PlanificaciÃ³n barata
coder = "ollama:qwen3-coder-next"     # CÃ³digo local gratis
reviewer = "openai:o4-mini"           # Puerta de calidad
sentinel = "openai:gpt-4o"            # Muestreo frontier
escalation = "openai:gpt-4o"          # Fallback para problemas difÃ­ciles

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

O usÃ¡ el archivo `.forgegod/.env` â€” `forgegod init` lo crea automÃ¡ticamente.

## Modelos Soportados

| Proveedor | Modelos | Costo | Setup |
|:----------|:--------|:------|:------|
| **Ollama** | qwen3-coder-next, devstral, cualquiera | **$0** | `ollama serve` |
| OpenAI API | gpt-4o, gpt-4o-mini, o3, o4-mini | $$ | `OPENAI_API_KEY` |
| SuscripciÃ³n OpenAI Codex | gpt-5.4 vÃ­a superficie Codex | Incluida en planes ChatGPT soportados | `forgegod auth login openai-codex` |
| Anthropic | claude-sonnet-4-6, claude-opus-4-6 | $$$ | `ANTHROPIC_API_KEY` |
| Google Gemini | gemini-2.5-pro, gemini-3-flash | $$ | `GOOGLE_API_KEY` |
| DeepSeek | deepseek-chat, deepseek-reasoner | $ | `DEEPSEEK_API_KEY` |
| Kimi (Moonshot directo) | kimi-k2.5, kimi-k2-thinking | $$ | `MOONSHOT_API_KEY` |
| Z.AI / GLM | glm-5.1, glm-5, glm-4.7 | $$ | `ZAI_CODING_API_KEY` o `ZAI_API_KEY` |
| OpenRouter | 200+ modelos | varÃ­a | `OPENROUTER_API_KEY` |

El soporte de Kimi usa la API OpenAI-compatible oficial de Moonshot y hoy es experimental dentro de ForgeGod. Correlalo con tus benchmarks antes de convertirlo en modelo por defecto.
El soporte por suscripciÃ³n de OpenAI Codex hoy es mÃ¡s fuerte para planner/reviewer/adversary. TambiÃ©n puede usarse como superficie de ruteo para cÃ³digo, pero el loop de coder sigue siendo experimental y conviene benchmarkearlo antes de dejarlo como coder remoto por defecto.
OpenRouter sigue funcionando con keys/crÃ©ditos. Alibaba/Qwen Coding Plan sigue en evaluaciÃ³n porque la documentaciÃ³n oficial actual lo acota a coding tools soportadas, no a loops autÃ³nomos genÃ©ricos.

Regla practica del harness:

- `forgegod benchmark` mide performance de codigo/modelos sobre tareas scaffold
- `forgegod evals` mide a ForgeGod mismo: UX conversacional, aprobaciones,
  denegaciones por permisos y disciplina del completion gate

## Seguridad

Defensa en profundidad, no teatro de seguridad:

- **Lista de comandos bloqueados** â€” 13 patrones peligrosos bloqueados (`rm -rf /`, `curl | sh`, `sudo`, fork bombs)
- **RedacciÃ³n de secretos** â€” 11 patrones eliminan claves API de la salida de herramientas antes del contexto LLM
- **DetecciÃ³n de inyecciÃ³n de prompts** â€” Archivos de reglas escaneados por patrones de inyecciÃ³n antes de cargar
- **LÃ­mites de presupuesto** â€” Controles de costo previenen gasto descontrolado de API
- **Killswitch** â€” CreÃ¡ `.forgegod/KILLSWITCH` para detener inmediatamente los loops autÃ³nomos
- **ProtecciÃ³n de archivos sensibles** â€” `.env`, archivos de credenciales reciben advertencias + redacciÃ³n automÃ¡tica

> **Advertencia**: ForgeGod ejecuta comandos shell y modifica archivos. Segun la linea base verificada del 2026-04-08, `strict` usa un backend real de sandbox con Docker y se bloquea si faltan Docker o la imagen requerida, mientras que `standard` sigue siendo un flujo local con guardrails. RevisÃ¡ los cambios en una branch o worktree descartable antes de usar modo autonomo.

## Documentacion Operativa

- [AGENTS.md](AGENTS.md) â€” instrucciones locales para agentes de codigo
- [docs/OPERATIONS.md](docs/OPERATIONS.md) â€” sistema de registro actual y comandos verificados
- [docs/AUDIT_2026-04-07.md](docs/AUDIT_2026-04-07.md) â€” auditoria detallada y orden de remediacion
- [docs/WEB_RESEARCH_2026-04-07.md](docs/WEB_RESEARCH_2026-04-07.md) â€” investigacion externa usada para estructurar la documentacion

## Contribuir

Damos la bienvenida a contribuciones. Ver [CONTRIBUTING.md](CONTRIBUTING.md) para las guÃ­as.

- Reportes de bugs y solicitudes de features: [GitHub Issues](https://github.com/waitdeadai/forgegod/issues)
- Preguntas y discusiÃ³n: [GitHub Discussions](https://github.com/waitdeadai/forgegod/discussions)

## Colaboradores

ForgeGod acredita pÃºblicamente trabajo de cÃ³digo y no-cÃ³digo.

- [Matias Mesa](https://www.linkedin.com/in/matt-mesa/) - `design` - sistema oficial de mascota de ForgeGod
- [WAITDEAD](https://waitdead.com) - `code`, `infra`, `research`, `projectManagement`, `maintenance`

Ver [CONTRIBUTORS.md](CONTRIBUTORS.md) para la lista actual de colaboradores.

## Licencia

Apache 2.0 â€” ver [LICENSE](LICENSE).

---

<p align="center">
  Construido por <a href="https://waitdead.com">WAITDEAD</a> &bull; DiseÃ±o oficial de la mascota por <a href="https://www.linkedin.com/in/matt-mesa/">Matias Mesa</a> &bull; Potenciado por tÃ©cnicas de OpenClaw, Hermes, e investigaciÃ³n SOTA 2026 de agentes de cÃ³digo.
</p>


