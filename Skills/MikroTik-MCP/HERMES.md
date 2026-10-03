# Integración con Hermes Agent

## Requisitos validados

- Hermes Agent v0.21.3.
- MCP Python SDK 2.3.0.
- Servidor MCP local por stdio.
- Python del entorno virtual del proyecto.

## Herramientas descubiertas

- mikrotik_inventory
- mikrotik_traffic
- mikrotik_full

El servidor se verifica con hermes mcp test mikrotik y se lista con hermes mcp list.

## Registro por stdio

Hermes inicia el Python del entorno virtual con el módulo mikrotik_skill.mcp_server.

Durante las pruebas se detectó que, sin instalar el módulo como paquete, la GUI podía fallar con MCPError: Connection closed porque el proceso se iniciaba desde un directorio distinto y Python no encontraba mikrotik_skill.

## Solución temporal validada

Registrar el MCP con PYTHONPATH apuntando a la raíz del proyecto. Después se valida con hermes mcp test mikrotik y se reinicia el gateway.

Esto permitió usar el MCP tanto desde CLI como desde la GUI de Hermes.

## Pruebas realizadas

Inventario: el agente consultó el perfil laboratorio sin recibir IP, contraseña ni comandos SSH.

Tráfico: el agente solicitó una captura Torch de 5 segundos y presentó protocolos, flujos, orígenes, destinos, puertos y tasa observada.

## Mejora pendiente

Crear pyproject.toml e instalar mikrotik_skill en el entorno virtual para eliminar PYTHONPATH y facilitar su reutilización desde otros clientes MCP.