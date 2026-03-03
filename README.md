# Imperium Radar

Overlay en tiempo real para **Imperium Classic 1.20** que detecta NPCs y Jugadores mediante captura de pantalla y visión por computadora.

## Funcionalidades

- Detección de NPCs (amarillo) y Jugadores (cyan) en tiempo real
- Overlay transparente con marcadores minimalistas (puntos + etiquetas)
- Redirección automática de clicks hacia el centro del personaje detectado
- Movimiento suave del mouse con velocidad configurable
- Cooldown anti-spam entre clicks
- Panel de controles colapsable
- Configuración persistente en JSON

## Requisitos

- **Python 3.x** — [Descargar](https://www.python.org/downloads/windows/) (marcar "Add Python to PATH" al instalar)
- **Windows** (usa la API Win32 para control del mouse)

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

1. Abre **Imperium Classic 1.20**
2. Ejecuta el radar:
   ```bash
   python overlay.py
   ```

## Controles

| Control | Descripción |
|---------|-------------|
| **START/STOP** | Activa o desactiva el escaneo |
| **Visuales** | Muestra u oculta los marcadores sobre los personajes |
| **Click Redir** | Redirige clicks al centro del personaje detectado |
| **Dimensiones** | Ajusta el área de detección (Izq, Der, Arr, Aba) |
| **Hitbox** | Expande el área clickeable alrededor del personaje |
| **Punt X / Y** | Ajuste fino de la puntería (offset en pixels) |
| **Velocidad** | Suavidad del movimiento del mouse (1 = instantáneo, 20 = muy suave) |
| **Cooldown** | Tiempo mínimo entre clicks (0-1000 ms) |
| **▲/▼** | Colapsa o expande el panel de controles |
| **Escape** | Cierra la aplicación |

## Configuración

Los ajustes se guardan en `radar_config.json` al presionar **GUARDAR** y se cargan automáticamente al iniciar.

## Notas

- El juego debe estar en resolución estándar con los nombres de personajes visibles
- El radar busca la ventana con el título exacto "Imperium Classic 1.20"
