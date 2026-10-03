# MikroTik MCP Skill

Skill de consulta y análisis seguro para dispositivos MikroTik RouterOS, expuesto mediante Model Context Protocol (MCP).

## Estado validado

- Windows + PowerShell
- Python 3.14
- Paramiko 5.x
- MCP Python SDK 2.3.0
- Hermes Agent v0.21.3
- Qwen3 Coder 30B mediante endpoint OpenAI-compatible
- RouterOS 7.24.4
- MikroTik CRS112-8P-4S

## Objetivo

Permitir que agentes compatibles con MCP consulten y analicen equipos MikroTik sin entregar al modelo acceso SSH arbitrario, credenciales ni una consola RouterOS genérica.

## Herramientas MCP

- mikrotik_inventory(device): inventario y análisis determinístico.
- mikrotik_traffic(device, duration=5): captura y análisis mediante RouterOS Torch.
- mikrotik_full(device, duration=5): inventario + tráfico.

No se expone execute_command, shell, ssh_command ni routeros_command.

## Arquitectura

Agente/LLM -> MCP stdio -> mikrotik_skill -> perfil + DPAPI -> Paramiko/SSH -> RouterOS

El modelo selecciona una operación y un nombre lógico de dispositivo. La IP, usuario, interfaz predeterminada y contraseña no necesitan formar parte del prompt.

## Seguridad

La versión actual es de solo lectura/análisis. No modifica configuración, no reinicia dispositivos y no expone comandos RouterOS arbitrarios.

Consulta SECURITY.md, ARCHITECTURE.md y HERMES.md para los detalles técnicos.

## Próximos pasos

1. Instrumentar tiempos de DPAPI, SSH, Torch y procesamiento.
2. Empaquetar el proyecto con pyproject.toml para eliminar la dependencia temporal de PYTHONPATH.
3. Añadir perfiles para más dispositivos.
4. Mantener futuras operaciones de escritura como herramientas separadas, validadas y con aprobación.