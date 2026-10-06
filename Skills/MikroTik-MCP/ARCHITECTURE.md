# Arquitectura - MikroTik MCP Skill

## Flujo lógico

```text
Usuario
  -> Hermes / cliente MCP
      -> companion skill (procedimiento y routing)
          -> MCP Server (contrato tipado)
              -> run_skill / orchestrator
                  -> Session Manager
                  -> RouterOS adapter (Paramiko SSH)
                  -> collectors / samplers
                  -> parsers
                  -> analyzers determinísticos
                  -> chart renderer
                  -> audit logger
                      -> RouterOS
```

El LLM decide la intención. Python decide cómo medirla.

## Superficie pública

### mikrotik_devices

Descubre perfiles locales sin revelar host, username o secretos.

### mikrotik_status

Entrada principal para observabilidad:

- health puntual;
- CPU temporal;
- interfaces/contadores puntuales;
- RX/TX temporal de una interfaz;
- red/rutas/connection tracking;
- sesión SSH;
- PNG opcional para series temporales.

### mikrotik_inventory

Inventario completo. Ejecuta todos los collectors y se reserva para solicitudes realmente amplias.

### mikrotik_torch_flows

Captura acotada RouterOS Torch para flujos: origen/destino, protocolo, puerto y tasa observada.

### mikrotik_full

Inventario completo + Torch. Costosa y no recomendada para preguntas normales.

## Frontera de datos

Los datos necesarios para transportar la sesión SSH permanecen dentro del backend:

- host/IP de administración;
- puerto;
- username;
- password DPAPI;
- estado interno de Paramiko.

La superficie MCP trabaja con el nombre lógico del perfil. En particular, los resultados de Torch no derivan `target` desde `client.host`; reciben una etiqueta lógica del orquestador. Esto evita convertir metadatos de transporte en contexto del modelo.

## Colección dirigida

Las vistas compactas no ejecutan inventario completo:

- health: identity + resources + routerboard;
- interfaces: interfaces + interface_stats;
- network: addresses + routes + connection_tracking.

Esto reduce comandos RouterOS, latencia y payload.

## Series temporales

### CPU

`cpu_sampling.py` ejecuta `/system resource print` periódicamente sobre la misma sesión SSH.

Límites:

- 5–120 segundos;
- intervalo 1–120 segundos;
- máximo 120 muestras;
- CPU validada entre 0 y 100.

La primera lectura ocurre al inicio de la ventana. Las siguientes se programan según `interval`. Si una consulta tarda más que el intervalo, no se intentan recuperar muestras vencidas en ráfaga. Si el siguiente slot caería fuera de la ventana, el sampler espera solamente hasta el deadline y termina.

Cada lectura incluye timestamp UTC y tiempo transcurrido. El backend calcula mínimo, máximo, promedio, mediana, primera y última lectura.

### Interfaces

`interface_sampling.py` usa:

```routeros
/interface monitor-traffic <interface> once
```

y repite la medición dentro de una ventana acotada usando la misma política temporal del sampler de CPU.

Esto produce tasas actuales RX/TX en bits por segundo y packet/drop rates. No se confunde con los contadores históricos de bytes/packets. Las estadísticas de la ventana se calculan en Python sobre las mismas lecturas que se devuelven al cliente.

## Torch

Torch permanece separado de monitor-traffic. Sirve para responder **quién/qué** genera tráfico, no para medir CPU ni sustituir una serie RX/TX de interfaz.

Las capturas son acotadas y no se reintentan silenciosamente desde el backend.

## Resultados

El contrato separa:

- `content`: resumen/model-facing compacto;
- `structuredContent`: evidencia completa estructurada;
- `ImageContent`: PNG opcional construido con las mismas lecturas.

El gráfico nunca es la fuente de verdad; la serie estructurada lo es.

## Análisis

Los parsers convierten salida RouterOS a estructuras estables. Los analyzers calculan hechos reproducibles. El LLM queda para explicación contextual.

Ejemplos de semántica explícita:

- CPU puntual = muestra instantánea;
- RX/TX bytes = contador acumulado;
- `link_downs` = contador histórico;
- CPU/interface sample = evidencia de una ventana;
- Torch = evidencia de flujos durante una captura.

## Sesiones

`session_manager.py` mantiene una conexión SSH por perfil:

- reutilización de sesión;
- verificación de transporte antes de reutilizar;
- reconexión antes de una nueva operación cuando la sesión murió;
- cache de secreto DPAPI en memoria;
- telemetría de edad/reuse/fingerprint;
- cierre y limpieza al terminar el proceso.

## Perfiles y secretos

Los perfiles locales contienen:

- nombre lógico;
- host;
- puerto;
- username;
- interfaz predeterminada;
- pin SHA256 opcional de host key.

La contraseña vive separada, protegida por Windows DPAPI.

En laboratorio puede mantenerse compatibilidad sin pin. La puerta de producción exige host-key pinning verificado antes de aprobar despliegue.

## Auditoría

`observability.py` es el choke point de llamadas MCP públicas. Registra JSONL redacted con correlation ID, herramienta, perfil, parámetros, duración, operación backend y resultado.

La estructura queda preparada para un dashboard posterior sin acoplar observabilidad a la lógica RouterOS.

## Portabilidad

El MCP no depende de Hermes para ejecutar. Hermes aporta el companion skill y la experiencia agente.

El proyecto dispone de `pyproject.toml`, por lo que puede instalarse como paquete y reutilizarse desde otros clientes MCP.

## Pruebas

Capas:

1. unitarias puras;
2. contrato MCP;
3. sandbox RouterOS Docker/QEMU;
4. hardware real;
5. comportamiento agente Hermes/Qwen.

El sandbox y el hardware se mantienen separados para que los tests rápidos sigan siendo determinísticos. `VALIDATION.md` define las puertas de aceptación y la evidencia esperada.
