# Seguridad - MikroTik MCP Skill

## Principio

El LLM no recibe acceso SSH genérico. La superficie expuesta se limita a herramientas concretas y validadas.

## Permitido

- Inventario.
- Análisis de tráfico.
- Inventario + tráfico.
- Selección de perfiles locales existentes.
- Duración de captura dentro de límites del backend.

## No expuesto

No se publica ninguna herramienta de shell, ejecución SSH arbitraria ni comandos RouterOS libres. Tampoco se pasan contraseñas o secretos como argumentos MCP.

## Credenciales

En Windows, las contraseñas se almacenan localmente con DPAPI. El secreto queda ligado al usuario de Windows y no debe añadirse al repositorio.

## RouterOS

La implementación actual es de solo lectura/análisis: no modifica configuración, no crea usuarios, no cambia firewall, no reinicia el router y no actualiza RouterOS.

## SSH

La implementación actual usa Paramiko. Antes de una adopción de producción más amplia debe endurecerse la validación de host keys y reemplazar políticas permisivas por verificación explícita de hosts conocidos.

## Futuras operaciones de escritura

Deben implementarse como herramientas específicas con validación de parámetros, alcance limitado, aprobación cuando corresponda y registro del resultado. No deben aceptar comandos RouterOS libres generados por el LLM.