# Arquitectura - MikroTik MCP Skill

## Flujo

Usuario -> Agente -> LLM -> MCP Server (stdio) -> run_skill() -> MikroTikClient/Paramiko -> SSH -> RouterOS

## Operaciones

- inventory: captura, normalización y análisis determinístico del inventario.
- traffic: captura RouterOS Torch, parser y agregación.
- full: inventario + tráfico.

## Perfiles y secretos

Cada equipo usa un nombre lógico de perfil. El perfil contiene host, puerto SSH, usuario e interfaz predeterminada. La contraseña se almacena localmente mediante Windows DPAPI y no se entrega al LLM.

DPAPI queda ligado al usuario de Windows que creó el secreto. Si el MCP se ejecuta con otro usuario, servicio, contenedor, WSL o equipo, el secreto puede no descifrarse.

## Inventario

La tubería es: RouterOS -> captura -> parser -> estructura normalizada -> analyzer -> hallazgos.

La CPU es una muestra instantánea y no debe presentarse como carga sostenida. link_downs es un contador acumulativo.

## Tráfico

Torch usa la interfaz predeterminada del perfil. Durante las pruebas no se usa as-value porque esa variante no devolvió la salida esperada.

El análisis agrega filas, flujos únicos, protocolos, clasificación, principales orígenes/destinos, puertos y tasa observada. La tasa corresponde a la ventana de captura, no a utilización histórica.

## Portabilidad

El diseño separa MCP de Hermes. Cualquier cliente MCP compatible puede reutilizar el servidor. Temporalmente se usa PYTHONPATH para que el módulo sea importable desde cualquier directorio; el objetivo es instalarlo como paquete Python.