# plataforma de diagnóstico de aplicaciones.
tu proyecto ya no sería simplemente un agente que ejecuta comandos Linux, sino una plataforma de diagnóstico de aplicaciones


Yo separaría la arquitectura en tres responsabilidades:
- Diagnostic Service: obtiene información técnica de forma segura.
- Skills: enseñan al agente cómo investigar problemas concretos.
- CMDB / Topology Service: identifica qué servidores, servicios y dependencias pertenecen a cada aplicación.

Y utilizaría LangGraph para orquestarlo todo.

# 1. Ejemplo de un servicio de diagnóstico dedicado
Imagina una aplicación ficticia llamada LAB-PORTAL, compuesta por tres servidores:

| Servidor | Función | Servicio |
|---|---|---|
| `web01` | Frontend | nginx |
| `app01` | Backend | tomcat |
| `db01` | Base de datos | PostgreSQL |

Zabbix detecta que app01 tiene la CPU al 97 %.
En lugar de que el agente pueda ejecutar cualquier comando SSH, tendríamos un servicio llamado Linux Diagnostic API.

[Diagrama](img/07_graph.png)

El agente podría llamar a una herramienta MCP:

````python
linux_get_top_processes(
    server_id="app01"
)
````

El MCP Server traduciría esa solicitud en una llamada HTTPS a la Diagnostic API:

````json
POST /v1/diagnostics/processes
Authorization: Bearer <token>

{
  "server_id": "app01",
  "limit": 5
}
````

La API validaría que el cliente tiene permiso para consultar app01, aplicaría los límites de tiempo y recursos y devolvería:

````json
{
  "server_id": "app01",
  "status": "success",
  "processes": [
    {"pid": 1234, "name": "java", "cpu_percent": 92},
    {"pid": 2345, "name": "systemd", "cpu_percent": 1}
  ]
}
````

En un diseño real también incluiría la hora de medición y el tipo de muestra, para evitar interpretar datos antiguos o comparar métricas incompatibles.

**¿Cómo implementaría el servicio?**
Podrías hacerlo con **FastAPI + Python + systemd**, pero no necesitas instalar FastAPI en todos los servidores.
Mi preferencia inicial sería una API centralizada que utilice SSH con comandos restringidos contra los servidores destino.
Por ejemplo, el backend tendría un catálogo interno de operaciones autorizadas:

````python
DIAGNOSTICS = {
    "cpu": get_cpu_usage,
    "memory": get_memory_usage,
    "processes": get_top_processes,
    "service_status": get_service_status,
    "journal": get_journal_logs,
}
````
La API no ofrecería run_command(command: str).
Y la autorización no se basaría en el server_id proporcionado por el LLM, sino en la identidad del solicitante y una política de permisos independiente.
Para producción añadiría mTLS u OAuth2 con Entra ID, una identidad distinta para cada servicio, límites de concurrencia y resultados, permisos Linux mínimos, controles de red y auditoría centralizada.


**Una consideración:** no es obligatorio tener una Diagnostic API separada desde el primer momento. El propio MCP Server puede implementar esta lógica si solo existe un consumidor. La separaría cuando varias aplicaciones necesiten reutilizar los diagnósticos o cuando convenga administrar la ejecución y sus permisos independientemente del agente.

---

# 2. ¿Qué son exactamente las Skills?

Aquí aparece un concepto diferente de Tool y MCP.

Una ``Skill`` es un paquete reutilizable de instrucciones, procedimientos y recursos que enseña al agente cómo resolver una clase determinada de problemas.
Normalmente incluye un archivo SKILL.md y opcionalmente referencias, scripts o plantillas.
No es un proceso que se ejecuta permanentemente, ni es automáticamente una Tool, ni es un modelo entrenado.
Las Skills se pueden cargar bajo demanda, de manera que el agente no tenga que recibir de golpe todos los procedimientos existentes. Este mecanismo suele llamarse progressive disclosure.

Ejemplo: Skill para diagnosticar CPU elevada
Crearíamos este directorio:

````bash
skills/
└── linux-high-cpu/
    ├── SKILL.md
    └── references/
        └── cpu-diagnostics.md
````

Y su archivo SKILL.md podría ser:

````

---
name: linux-high-cpu
description: Diagnostica alertas de CPU elevada en Linux.
---

# Linux High CPU Diagnosis

## Objetivo
Identificar procesos responsables de una alerta
de CPU elevada y proponer comprobaciones adicionales.

## Procedimiento

1. Consultar el porcentaje actual de CPU.
2. Consultar los procesos con mayor uso de CPU.
3. Comparar el resultado con la alerta de Zabbix.
4. Identificar la aplicación propietaria del proceso.
5. Seleccionar el procedimiento específico:
   - Oracle: comprobar sesiones y SQL.
   - Java: comprobar JVM, threads y GC.
   - PostgreSQL: comprobar sesiones y queries.
6. Generar un diagnóstico con evidencias.

## Reglas

- No reiniciar procesos.
- No modificar configuraciones.
- No ejecutar comandos arbitrarios.
- Separar hechos, hipótesis y recomendaciones.
- Indicar las comprobaciones que faltan.
````


Eso sería una Skill inicial perfectamente válida como procedimiento. Todavía tendríamos que implementar cómo nuestro agente descubre y carga estos archivos.

### Skill frente a Tool

| Concepto | Pregunta que responde | Ejemplo |
|---|---|---|
| **Tool** | ¿Qué operación puedo ejecutar? | `linux_processes()` |
| **MCP** | ¿Cómo accedo a esa herramienta? | MCP Server Linux |
| **Skill** | ¿Cómo debo investigar el problema? | `linux-high-cpu` |
| **LangGraph** | ¿Cómo coordino la investigación? | Nodos, rutas y loop |
| **LLM** | ¿Qué hacer a continuación? | Decidir consultar procesos |

Por ejemplo, la Skill le indica al agente que, ante CPU elevada en un proceso Oracle, considere investigar sesiones SQL.

La Tool `oracle_sessions()` obtiene los datos reales.

El LLM interpreta la información.

LangGraph mantiene el estado y la ejecución.

## ¿Cómo debería seleccionar y cargar las Skills?

No cargaría 100 Skills completas en el prompt inicial.

Utilizaría un catálogo de metadatos y una herramienta de carga:

```python
load_skill(name="linux-high-cpu")
```

Cuando el agente recibe una alerta, el catálogo permite identificar Skills relacionadas y cargar solamente las que necesita.

La implementación puede apoyarse en un middleware de Skills, como el que ofrece el ecosistema Deep Agents, o en un mecanismo propio de LangGraph. No necesitas adoptar Deep Agents para utilizar el patrón. <Cite ref="turn632748search8"/>

Una forma sencilla de empezar sería:

```python
SKILLS = {
    "linux-high-cpu": "skills/linux-high-cpu/SKILL.md",
    "oracle-slow-sql": "skills/oracle-slow-sql/SKILL.md",
    "nginx-502": "skills/nginx-502/SKILL.md",
}
```

Con una Tool `load_skill()` que lea un archivo autorizado del catálogo y lo devuelva como contexto al agente.

**La Skill debe orientar el diagnóstico, no conceder privilegios.** Si una Skill recomienda reiniciar un proceso, eso no significa que exista una herramienta autorizada para hacerlo.

---

# 3. Muchas aplicaciones y servidores: ¿cómo sabe el agente dónde investigar?

Aquí creo que has identificado una de las partes más importantes de tu arquitectura.

**Sí, el agente necesita conocer qué componentes forman cada aplicación, dónde se ejecutan y cómo se relacionan.**

Pero no le pasaría el inventario completo de la empresa en el prompt.

Imagina que tienes 500 aplicaciones, 3.000 servidores y 8.000 servicios. Incluir toda esa información en cada llamada al LLM sería caro, difícil de mantener y generaría mucho ruido.

En su lugar crearía un **Application Topology Service**, conectado a una fuente de inventario autorizada.

## 3.1. Ejemplo de una aplicación

Supongamos que la aplicación ficticia `LAB-PORTAL` utiliza esta arquitectura:

<box border radius="xl" padding={3} gap={2}>
  <svg viewBox="0 0 340 295" width="100%">
    <rect x="105" y="4" width="130" height="33" rx="8" stroke="#64748b" fill="#64748b" fillOpacity=".10"/>
    <text x="170" y="25" fill="currentColor" fontSize="12" fontWeight="600" textAnchor="middle">LAB-PORTAL</text>
    <path d="M170 37V57" stroke="currentColor" strokeOpacity=".6" strokeWidth="1.5"/>
    <rect x="91" y="58" width="158" height="45" rx="8" stroke="#2563eb" fill="#2563eb" fillOpacity=".1"/>
    <text x="170" y="75" fill="currentColor" fontSize="12" fontWeight="600" textAnchor="middle">web01 / nginx</text>
    <text x="170" y="91" fill="currentColor" fontSize="10" textAnchor="middle">Frontend</text>
    <path d="M170 103V126" stroke="currentColor" strokeOpacity=".6" strokeWidth="1.5"/>
    <path d="M165 120L170 126L175 120" stroke="currentColor" fill="none"/>
    <rect x="91" y="127" width="158" height="45" rx="8" stroke="#2563eb" fill="#2563eb" fillOpacity=".1"/>
    <text x="170" y="144" fill="currentColor" fontSize="12" fontWeight="600" textAnchor="middle">app01 / tomcat</text>
    <text x="170" y="160" fill="currentColor" fontSize="10" textAnchor="middle">Backend Java</text>
    <path d="M170 172V194" stroke="currentColor" strokeOpacity=".6" strokeWidth="1.5"/>
    <path d="M165 188L170 194L175 188" stroke="currentColor" fill="none"/>
    <rect x="91" y="195" width="158" height="45" rx="8" stroke="#16a34a" fill="#16a34a" fillOpacity=".1"/>
    <text x="170" y="212" fill="currentColor" fontSize="12" fontWeight="600" textAnchor="middle">db01 / PostgreSQL</text>
    <text x="170" y="228" fill="currentColor" fontSize="10" textAnchor="middle">Base de datos</text>
    <text x="170" y="269" fill="currentColor" fontSize="11" textAnchor="middle" opacity=".7">Dependencias declaradas de la aplicación</text>
  </svg>
</box>

Cuando llega una alerta de Zabbix:

```text
Host: app01
Trigger: High CPU usage
Severity: High
```

El agente debe descubrir:

- A qué aplicación pertenece `app01`.
- Qué servicio se ejecuta en ese servidor.
- Qué otros componentes están relacionados.
- Qué herramientas puede utilizar.
- Qué Skills de diagnóstico son aplicables.

Pero **el inventario de infraestructura debería ser una fuente de datos estructurados, no conocimiento que el LLM tenga que adivinar**.

## 3.2. ¿Esto sería RAG?

Depende de cómo obtengas la información.

RAG (*Retrieval-Augmented Generation*) consiste, en términos generales, en recuperar información externa relevante para utilizarla como contexto al generar una respuesta.

Sin embargo, no todas las consultas externas necesitan implementarse como un RAG con embeddings y una base vectorial.

| Necesidad | Solución que utilizaría |
|---|---|
| Saber a qué aplicación pertenece `app01` | CMDB / inventario estructurado |
| Obtener los servidores de una aplicación | API o consulta SQL |
| Saber qué servicios ejecuta un host | Inventario y descubrimiento |
| Encontrar un procedimiento de diagnóstico | Catálogo de Skills |
| Buscar un incidente similar del pasado | RAG documental o búsqueda híbrida |
| Buscar documentación técnica de una aplicación | RAG documental |
| Obtener CPU en tiempo real | Tool de observabilidad |

Por tanto, **sí utilizaría RAG en tu sistema, pero no para todo**.

Para consultar relaciones entre aplicaciones, servidores y servicios, empezaría con SQL o una API de topología.

Para buscar documentos, runbooks e incidencias anteriores, utilizaría recuperación semántica o híbrida, incluyendo búsqueda por palabras clave.

## 3.3. Modelo de inventario recomendado

Como mínimo necesitas representar estas entidades:

```text
Application
    │
    ├── Environment
    │      │
    │      ├── Component
    │      │       │
    │      │       ├── Server
    │      │       └── Service
    │      │
    │      └── Dependencies
    │
    └── Owners / Support Groups
```

Podrías empezar con un esquema relacional sencillo:

```sql
CREATE TABLE applications (
    id BIGINT PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

CREATE TABLE servers (
    id BIGINT PRIMARY KEY,
    hostname VARCHAR(255) NOT NULL
);

CREATE TABLE components (
    id BIGINT PRIMARY KEY,
    application_id BIGINT NOT NULL,
    name VARCHAR(100) NOT NULL,
    component_type VARCHAR(50) NOT NULL
);

CREATE TABLE component_servers (
    component_id BIGINT NOT NULL,
    server_id BIGINT NOT NULL,
    PRIMARY KEY (component_id, server_id)
);
```

Es un punto de partida: faltaría relacionar servicios, entornos, dependencias, permisos y procedencia de los datos.

A medio plazo, convendría modelar explícitamente las dependencias, porque saber que dos servidores pertenecen a una aplicación no explica si uno depende del otro.

### ¿Necesitas una base de datos de grafos?

No necesariamente.

Aunque estemos usando LangGraph, eso **no implica que necesites Neo4j ni otra base de datos de grafos**.

LangGraph organiza el flujo de ejecución de tu agente; una base de datos de grafos almacenaría relaciones entre aplicaciones y componentes. Son conceptos diferentes.

Empezaría con la CMDB existente o una base de datos relacional y solo consideraría una base de grafos si las consultas de dependencias se vuelven complejas.

En Azure, <Link url="https://learn.microsoft.com/en-us/azure/azure-monitor/app/app-map" title="Application Insights Application Map"/> puede ayudarte a descubrir dependencias entre componentes instrumentados, aunque no sustituye una CMDB completa. <Cite ref="turn632748search5"/>

# 4. Arquitectura que propondría para tu agente

Yo añadiría a LangGraph una primera fase obligatoria para resolver el contexto de la aplicación antes de empezar a investigar.

<box border radius="xl" padding={3} gap={2}>
  <svg viewBox="0 0 340 535" width="100%">
    {#each [{y:5,t:"Alerta Zabbix",sub:"Host · Trigger · Severidad",c:"#64748b"},{y:73,t:"Resolver aplicación",sub:"CMDB / Application Topology",c:"#2563eb"},{y:141,t:"Seleccionar Skills",sub:"Procedimientos aplicables",c:"#d97706"},{y:209,t:"Agente LangGraph + LLM",sub:"Planifica la investigación",c:"#16a34a"}] as item}
      <rect x="47" y={item.y} width="246" height="51" rx="9" stroke={item.c} fill={item.c} fillOpacity=".10" strokeWidth="1.4"/>
      <text x="170" y={item.y+21} textAnchor="middle" fontSize="12" fontWeight="600" fill="currentColor">{item.t}</text>
      <text x="170" y={item.y+38} textAnchor="middle" fontSize="10" fill="currentColor">{item.sub}</text>
      <path d={`M170 ${item.y+51}V${item.y+68}`} stroke="currentColor" strokeOpacity=".65" strokeWidth="1.5"/>
    {/each}
    <path d="M170 260V282M55 282H285M55 282V298M170 282V298M285 282V298" stroke="currentColor" strokeOpacity=".65" strokeWidth="1.5" fill="none"/>
    {#each [{x:5,t:"MCP Linux",sub:"CPU · Logs"},{x:117,t:"MCP Oracle",sub:"SQL · Waits"},{x:229,t:"MCP Windows",sub:"Events"}] as item}
      <rect x={item.x} y="298" width="106" height="50" rx="8" stroke="#2563eb" fill="#2563eb" fillOpacity=".08"/>
      <text x={item.x+53} y="318" textAnchor="middle" fontSize="11" fontWeight="600" fill="currentColor">{item.t}</text>
      <text x={item.x+53} y="334" textAnchor="middle" fontSize="10" fill="currentColor">{item.sub}</text>
    {/each}
    <path d="M55 348V376H170M170 348V376M285 348V376H170M170 376V393" stroke="currentColor" strokeOpacity=".65" strokeWidth="1.5" fill="none"/>
    <rect x="47" y="394" width="246" height="48" rx="9" stroke="#d97706" fill="#d97706" fillOpacity=".10"/>
    <text x="170" y="414" textAnchor="middle" fontSize="12" fontWeight="600" fill="currentColor">Evidencias + RAG</text>
    <text x="170" y="430" textAnchor="middle" fontSize="10" fill="currentColor">Logs · Incidentes · Runbooks</text>
    <path d="M170 442V459" stroke="currentColor" strokeOpacity=".65" strokeWidth="1.5"/>
    <rect x="80" y="460" width="180" height="49" rx="9" stroke="#16a34a" fill="#16a34a" fillOpacity=".10"/>
    <text x="170" y="480" textAnchor="middle" fontSize="12" fontWeight="600" fill="currentColor">Diagnóstico final</text>
    <text x="170" y="496" textAnchor="middle" fontSize="10" fill="currentColor">Hallazgos y recomendaciones</text>
  </svg>
</box>

La clave es que **no dejaría al LLM inventar la topología o los permisos**. El agente primero recuperaría esa información de una fuente autorizada.

## Ejemplo del flujo completo

Imagina esta alerta:

```json
{
  "source": "zabbix",
  "host": "app01",
  "trigger": "High CPU usage",
  "severity": "high"
}
```

El primer nodo LangGraph, `resolve_application_context`, ejecutaría una consulta determinista a la CMDB y obtendría:

```json
{
  "application": "LAB-PORTAL",
  "environment": "production",
  "affected_server": "app01",
  "affected_service": "tomcat",
  "components": [
    {"server": "web01", "service": "nginx"},
    {"server": "app01", "service": "tomcat"},
    {"server": "db01", "service": "postgresql"}
  ],
  "dependencies": [
    {"from": "web01", "to": "app01"},
    {"from": "app01", "to": "db01"}
  ]
}
```

Ahora el agente dispone del contexto necesario.

A continuación seleccionaría la Skill `linux-high-cpu`. Al comprobar que el proceso problemático es Java, podría cargar `java-high-cpu` y utilizar herramientas adicionales como `java_thread_dump`, si están implementadas y autorizadas.

Finalmente buscaría, mediante RAG, si existe un incidente anterior similar con la misma aplicación y síntomas.

El diagnóstico podría indicar:

> El servidor app01 presenta CPU elevada. Las métricas apuntan a un proceso Java, pero todavía no está determinada la causa raíz. La aplicación depende de PostgreSQL en db01. Se recomienda analizar hilos JVM y comprobar posibles esperas hacia la base de datos.

Este es un ejemplo hipotético, no un diagnóstico real.

## 5. Qué datos debería almacenar el sistema

Para que el agente no termine dependiendo de información desactualizada, cada dato importante debería tener una fuente identificada.

| Información | Fuente recomendada |
|---|---|
| Aplicaciones y entornos | CMDB corporativa |
| Servidores asociados | CMDB, inventario o descubrimiento |
| Servicios instalados | Ansible / descubrimiento / monitorización |
| Dependencias reales | CMDB + telemetría observada |
| Estado actual | Zabbix, Grafana, Azure Monitor |
| Procedimientos | Skills versionadas en Git |
| Documentación de aplicación | Repositorio documental con RAG |
| Incidentes anteriores | ITSM con búsqueda híbrida |

También distinguiría las relaciones **declaradas** de las **observadas**: una CMDB puede decir que una aplicación depende de una base de datos, mientras que la telemetría puede descubrir dependencias adicionales. En vez de sobrescribir una fuente con la otra, conservaría ambas y registraría su procedencia.

## 6. Mi propuesta de implementación por fases

No desarrollaría todos estos componentes simultáneamente.

| Fase | Implementación | Resultado |
|---|---|---|
| 1 | MCP Linux + SSH restringido | Diagnóstico técnico de un servidor |
| 2 | Application Topology Service | Identificación de aplicación, servidores y servicios |
| 3 | Skills Linux, Java, Oracle y Windows | Procedimientos especializados |
| 4 | RAG de runbooks e incidencias | Contexto documental e histórico |
| 5 | Auditoría, autorización y observabilidad centralizadas | Preparación para operación empresarial |

**Mi prioridad sería la fase 2 antes que el RAG.** Un inventario de aplicaciones y dependencias fiable es más importante para el diagnóstico inicial que disponer de miles de documentos indexados.

La pieza que más valor puede aportar al proyecto no es otro modelo LLM, sino una fuente fiable que responda:

> «Para esta alerta, ¿qué aplicación está afectada, qué componentes tiene, cómo se relacionan y qué diagnósticos estoy autorizado a ejecutar?»

Una vez resuelta esa pregunta, LangGraph, las Skills, MCP y RAG encajan de manera bastante natural.

Y con esto también queda clara la distinción conceptual: **la CMDB le dice al agente dónde investigar; la Skill le explica cómo hacerlo; MCP le proporciona las herramientas; RAG le aporta conocimiento adicional; y LangGraph coordina el proceso.**
