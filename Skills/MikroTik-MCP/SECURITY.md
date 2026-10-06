# Seguridad - MikroTik MCP Skill

## Principio

El LLM no recibe una consola RouterOS. Solo puede invocar operaciones tipadas y previamente implementadas.

La seguridad no depende de que el modelo "se porte bien"; depende de la superficie que el servidor expone.

## Estado actual

El servidor es **read-only**:

- inventario;
- estado;
- series temporales CPU/interfaz;
- RouterOS Torch;
- gráficos derivados de datos medidos;
- telemetría SSH.

No expone configuración, reboot, upgrade, shell, comandos RouterOS libres ni ejecución SSH arbitraria.

## Esquemas y límites

Los argumentos MCP tienen tipos y límites en el JSON Schema generado por el SDK.

Guardrails principales:

- perfiles: caracteres restringidos;
- interfaces: caracteres restringidos;
- CPU/interface sampling: 5–120 s;
- intervalo: 1–120 s;
- máximo 120 muestras;
- Torch: 1–30 s.

El backend vuelve a validar las operaciones críticas aunque el cliente ya haya validado el schema.

Los samplers no intentan "ponerse al día" ejecutando varias consultas seguidas cuando SSH tarda más que el intervalo. Los slots vencidos se omiten, preservando una observación temporal real en vez de fabricar densidad de muestras.

## Tool annotations

Todas las herramientas públicas declaran:

- `readOnlyHint=true`;
- `destructiveHint=false`;
- `idempotentHint=true`;
- `openWorldHint=false`.

Estas anotaciones informan al cliente MCP, pero no sustituyen las validaciones del backend.

## Credenciales

En Windows, cada contraseña se guarda fuera del repo mediante DPAPI.

Consecuencias:

- el secreto queda ligado al usuario de Windows;
- otro usuario/servicio/contenedor puede no poder descifrarlo;
- la contraseña no aparece como argumento MCP;
- la contraseña descifrada se cachea únicamente en memoria mientras vive el proceso.

## Metadatos de administración

El host/IP, puerto y username del perfil son datos de transporte SSH, no datos model-facing.

`mikrotik_devices` no devuelve host ni username. Los reportes de Torch reciben el nombre lógico del dispositivo desde el orquestador y **no derivan el target desde `client.host`**. Las capturas y respuestas MCP pueden contener IPs de tráfico observadas por Torch porque esas IPs son precisamente evidencia de flujo; esto es distinto de revelar la dirección de administración usada por Paramiko.

## SSH host key

Un perfil puede incluir:

```json
{
  "host_key_sha256": "SHA256:..."
}
```

Cuando hay pin, se verifica durante el intercambio de host key **antes de autenticación**. Un mismatch aborta la conexión.

Sin pin se conserva un modo compatible con laboratorio que carga `known_hosts` y acepta hosts desconocidos. Esto es una compatibilidad de laboratorio, no el objetivo de producción.

### Puerta de producción

Un perfil no debe aprobarse para producción hasta tener un `host_key_sha256` obtenido y verificado fuera de banda. La validación real debe confirmar además que un fingerprint incorrecto produce `SSH_HOST_KEY_MISMATCH` y no cae a autenticación normal.

La telemetría de sesión indica fingerprint observado y si el perfil usa verificación explícita.

## Mínimo privilegio RouterOS

El usuario RouterOS usado por el perfil debe tener únicamente los permisos necesarios para las consultas implementadas. No se debe reutilizar un administrador general si puede definirse un usuario read-only adecuado.

## Auditoría y redacción

Las llamadas MCP se registran en JSONL. Claves sensibles como password, token, secret, private key, PSK, community y credentials se redactan antes de persistir.

Los paths completos de secretos y el contenido de contraseñas no se envían al LLM.

## Evidencia

El servidor incluye notas semánticas para evitar convertir observaciones parciales en afirmaciones de seguridad:

- Torch no prueba que "no exista tráfico malicioso";
- una muestra CPU no prueba estabilidad;
- un contador acumulado no prueba ancho de banda actual;
- una diferencia de firmware no implica causa de inestabilidad.

Cuando falta evidencia, el estado correcto es desconocido.

## Capturas Torch

Torch es una operación diagnóstica temporal. Se limita a ventanas cortas y no se repite automáticamente como "retry" silencioso.

Las capturas raw se conservan para trazabilidad/reprocesamiento, pero el resultado MCP expone solo un identificador/nombre de captura, no rutas locales completas.

## Futuras operaciones de escritura

No deben añadirse como un comando genérico.

Cada write requerirá, como mínimo:

- herramienta dedicada;
- schema estricto;
- clasificación de riesgo;
- preview/plan cuando aplique;
- autorización/aprobación humana;
- snapshot/rollback cuando RouterOS lo permita;
- journal de intento/resultado;
- tratamiento explícito de resultados ambiguos tras timeout/desconexión.

Hasta diseñar esa capa, este MCP seguirá siendo read-only.
