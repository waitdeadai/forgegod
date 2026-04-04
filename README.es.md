<p align="center">
  <a href="README.md"><img src="https://img.shields.io/badge/lang-en-blue.svg" alt="English"></a>
  <a href="README.es.md"><img src="https://img.shields.io/badge/lang-es-yellow.svg" alt="Español"></a>
</p>

<p align="center">
  <img src="docs/mascot.png" alt="ForgeGod" width="120" />
</p>

<h1 align="center">ForgeGod</h1>

<p align="center">
  <strong>El agente de codigo que trabaja 24/7, aprende de sus errores, y cuesta $0 cuando quieras.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/forgegod/"><img src="https://img.shields.io/pypi/v/forgegod?color=00e5ff&style=flat-square" alt="PyPI"></a>
  <a href="https://github.com/waitdeadai/forgegod/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-00e5ff?style=flat-square" alt="Licencia"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11+-00e5ff?style=flat-square" alt="Python 3.11+"></a>
  <a href="https://github.com/waitdeadai/forgegod/actions"><img src="https://img.shields.io/github/actions/workflow/status/waitdeadai/forgegod/ci.yml?style=flat-square&color=00e5ff" alt="CI"></a>
  <a href="https://forgegod.com"><img src="https://img.shields.io/badge/site-forgegod.com-00e5ff?style=flat-square" alt="Website"></a>
</p>

<p align="center">
  <code>16 herramientas</code> &bull; <code>4 proveedores LLM</code> &bull; <code>Memoria de 5 niveles</code> &bull; <code>Autonomo 24/7</code> &bull; <code>Modo local $0</code>
</p>

---

ForgeGod orquesta multiples LLMs (OpenAI, Anthropic, Ollama, OpenRouter) en un unico motor de codigo autonomo. Enruta tareas al modelo correcto, corre 24/7 desde un PRD, aprende de cada resultado, y mejora su propia estrategia. Ejecutalo localmente por $0 con Ollama, o usa modelos en la nube cuando los necesites.

```bash
pip install forgegod
```

## Inicio Rapido (Sin Saber Programar)

No necesitas ser desarrollador para usar ForgeGod. Si puedes describir lo que quieres en espanol, ForgeGod escribe el codigo.

### Opcion A: Modo Local Gratuito ($0)

1. Instala Ollama: https://ollama.com/download
2. Descarga un modelo: `ollama pull qwen3.5:9b`
3. Instala ForgeGod: `pip install forgegod`
4. Ejecuta: `forgegod init --lang es` (el asistente te guia)
5. Probalo: `forgegod run "Crea un sitio web simple con un formulario de contacto"`

### Opcion B: Modo Nube (mas rapido, ~$0.01/tarea)

1. Obtene una clave de OpenAI: https://platform.openai.com/api-keys
2. Instala ForgeGod: `pip install forgegod`
3. Ejecuta: `forgegod init --lang es` → pega tu clave cuando te lo pida
4. Probalo: `forgegod run "Construi una API REST con autenticacion de usuarios"`

### Algo no funciona?

Ejecuta `forgegod doctor` — revisa tu instalacion y te dice exactamente que corregir.

## Por Que ForgeGod es Diferente

Todos los demas CLIs de codigo usan **un modelo a la vez** y **se reinician a cero** cada sesion. ForgeGod no.

| Capacidad | Claude Code | Codex CLI | Aider | Cursor | **ForgeGod** |
|:----------|:----------:|:---------:|:-----:|:------:|:------------:|
| Ruteo multi-modelo automatico | - | - | manual | - | **si** |
| Hibrido local + nube | - | basico | basico | - | **nativo** |
| Loops autonomos 24/7 | - | - | - | - | **si** |
| Memoria entre sesiones | basica | - | - | removida | **5 niveles** |
| Estrategia auto-mejorable | - | - | - | - | **si (SICA)** |
| Modos de presupuesto | - | - | - | - | **si** |
| Generacion Reflexion | - | - | - | - | **3 intentos** |
| Worktrees git paralelos | subagentes | - | - | - | **si** |

### La Ventaja: Harness > Modelo

Un [salto de 22 puntos en SWE-bench](https://www.cognition.ai/blog/swe-bench-devin) viene de la ingenieria del harness, no de upgrades de modelo. ForgeGod es el harness:

- **Ralph Loop** — Codigo 24/7 desde un PRD. El progreso vive en git, no en el contexto del LLM. Agente fresco por historia. Sin degradacion de contexto.
- **Memoria de 5 Niveles** — Episodica (que paso) + Semantica (que se) + Procedimental (como lo hago) + Grafo (como se conectan las cosas) + Errores-Soluciones (que arregla que). Las memorias decaen, se consolidan y se refuerzan automaticamente.
- **Coder Reflexion** — 3 intentos de generacion de codigo con modelos escalonados: local (gratis) → nube (barato) → frontier (cuando importa). Validacion AST en cada paso.
- **SICA** — Agente de Codigo Auto-Mejorable. Modifica sus propios prompts, ruteo de modelos y estrategia basado en resultados. 6 capas de seguridad previenen la desviacion.
- **Modos de Presupuesto** — `normal` → `throttle` → `local-only` → `halt`. Activados automaticamente por gasto. Corre para siempre en Ollama por $0.

## Inicio Rapido

```bash
# Instalar
pip install forgegod

# Inicializar un proyecto
forgegod init --lang es

# Tarea unica
forgegod run "Agrega un endpoint /health a server.py con uptime e info de version"

# Planificar un proyecto → genera PRD
forgegod plan "Construi una API REST para una app de tareas con auth, CRUD y tests"

# Loop autonomo 24/7 desde PRD
forgegod loop --prd .forgegod/prd.json

# Ver que aprendio
forgegod memory

# Ver desglose de costos
forgegod cost

# Benchmark de modelos
forgegod benchmark

# Chequeo de salud
forgegod doctor
```

## Como Funciona el Ralph Loop

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
│  El progreso esta en GIT, no en contexto LLM.   │
│  Agente fresco por historia. Sin degradacion.    │
│  Crea .forgegod/KILLSWITCH para detener.        │
└─────────────────────────────────────────────────┘
```

1. **Leer PRD** — Elegir la historia TODO de mayor prioridad
2. **Crear agente** — Contexto fresco (el progreso esta en git, no en memoria)
3. **Ejecutar** — El agente usa 16 herramientas para implementar la historia
4. **Validar** — Tests, lint, sintaxis, revision frontier
5. **Commit o retry** — Pasa: commit + marcar hecho. Falla: reintentar hasta 3x con escalamiento de modelo
6. **Rotar** — Siguiente historia. El contexto siempre es fresco.

## Sistema de Memoria de 5 Niveles

ForgeGod tiene el sistema de memoria mas avanzado de cualquier agente de codigo open-source:

| Nivel | Que | Como | Retencion |
|:------|:----|:-----|:----------|
| **Episodica** | Que paso por tarea | Registros completos de resultado | 90 dias |
| **Semantica** | Principios extraidos | Confianza + decaimiento + refuerzo | Indefinido |
| **Procedimental** | Patrones de codigo y recetas | Seguimiento de tasa de exito | Indefinido |
| **Grafo** | Relaciones + aristas causales | Auto-extraido de resultados | Indefinido |
| **Errores-Soluciones** | Patron de error → solucion | Busqueda fuzzy | Indefinido |

Las memorias **decaen** sin refuerzo (vida media de 30 dias), se **consolidan** automaticamente (fusionan similares, podan debiles), y se **inyectan** en cada prompt como un Memory Spine ranqueado por relevancia + recencia + importancia.

## Modos de Presupuesto

| Modo | Comportamiento | Disparador |
|:-----|:---------------|:-----------|
| `normal` | Usa todos los modelos configurados | Por defecto |
| `throttle` | Preferir local, nube solo para revision | 80% del limite diario |
| `local-only` | Solo Ollama, **operacion $0** | Manual o 95% del limite |
| `halt` | Detener todas las llamadas LLM | 100% del limite diario |

## Leaderboard de Modelos

Ejecuta el tuyo: `forgegod benchmark`

| Modelo | Compuesto | Correctitud | Calidad | Velocidad | Costo | Auto-Reparacion |
|:-------|:---------:|:-----------:|:-------:|:---------:|:-----:|:---------------:|
| openai:gpt-4o-mini | 81.5 | 10/12 | 7.4 | 12s prom | $0.08 | 4/4 |
| ollama:qwen3.5:9b | 72.3 | 8/12 | 6.8 | 45s prom | $0.00 | 3/4 |

*Ejecuta `forgegod benchmark --update-readme` para actualizar con tus propios resultados.*

## Configuracion

ForgeGod usa config TOML con prioridad de 3 niveles: variables de entorno > proyecto > global.

```toml
# .forgegod/config.toml

[models]
planner = "openai:gpt-4o-mini"        # Planificacion barata
coder = "ollama:qwen3-coder-next"     # Codigo local gratis
reviewer = "openai:o4-mini"           # Puerta de calidad
sentinel = "openai:gpt-4o"            # Muestreo frontier
escalation = "openai:gpt-4o"          # Fallback para problemas dificiles

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
```

O usa el archivo `.forgegod/.env` — `forgegod init` lo crea automaticamente.

## Modelos Soportados

| Proveedor | Modelos | Costo | Setup |
|:----------|:--------|:------|:------|
| **Ollama** | qwen3-coder-next, devstral, cualquiera | **$0** | `ollama serve` |
| OpenAI | gpt-4o, gpt-4o-mini, o3, o4-mini | $$ | `OPENAI_API_KEY` |
| Anthropic | claude-sonnet-4-6, claude-opus-4-6 | $$$ | `ANTHROPIC_API_KEY` |
| OpenRouter | 200+ modelos | varia | `OPENROUTER_API_KEY` |

## Seguridad

Defensa en profundidad, no teatro de seguridad:

- **Lista de comandos bloqueados** — 13 patrones peligrosos bloqueados (`rm -rf /`, `curl | sh`, `sudo`, fork bombs)
- **Redaccion de secretos** — 11 patrones eliminan claves API de la salida de herramientas antes del contexto LLM
- **Deteccion de inyeccion de prompts** — Archivos de reglas escaneados por patrones de inyeccion antes de cargar
- **Limites de presupuesto** — Controles de costo previenen gasto descontrolado de API
- **Killswitch** — Crea `.forgegod/KILLSWITCH` para detener inmediatamente los loops autonomos
- **Proteccion de archivos sensibles** — `.env`, archivos de credenciales reciben advertencias + redaccion automatica

> **Advertencia**: ForgeGod ejecuta comandos shell y modifica archivos. Revisa los cambios antes de hacer commit. Inicia el modo autonomo con `--max 5` para verificar el comportamiento.

## Contribuir

Damos la bienvenida a contribuciones. Ver [CONTRIBUTING.md](CONTRIBUTING.md) para las guias.

- Reportes de bugs y solicitudes de features: [GitHub Issues](https://github.com/waitdeadai/forgegod/issues)
- Preguntas y discusion: [GitHub Discussions](https://github.com/waitdeadai/forgegod/discussions)

## Licencia

Apache 2.0 — ver [LICENSE](LICENSE).

---

<p align="center">
  Construido por <a href="https://waitdead.com">WAITDEAD</a> &bull; Potenciado por tecnicas de OpenClaw, Hermes, e investigacion SOTA 2026 de agentes de codigo.
</p>
