# Rekord AI — Open Source Web Experience

Sitio web local de **Rekord AI**, diseñado con estética de cabina profesional (*Obsidian Kinetic Glass*).

## Características Implementadas

1. **Visualizador de Forma de Onda Tri-Banda (CDJ-3000 Style)**: renderizado en `<canvas>` HTML5 interactivo.
2. **Simulador de Rueda Armónica Camelot**: 12 tonalidades activas (1A a 12A / 1B a 12B) y compatibilidad instantánea.
3. **Slider Comparativo Antes / Después**: evolución visual de la interfaz original hacia el cockpit oscuro Obsidian.
4. **Catálogo de Motores IA Locales**: selección transparente según la RAM/GPU del equipo (`Lite 0.8B`, `Compact 2B`, `Balanced 4B`, `Pro 9B` o `Deterministic 0 MB`).
5. **Comunidad & Cafecito**: 100% gratuito y Open Source con enlace de apoyo en [cafecito.app/digitalmenteseguro](https://cafecito.app/digitalmenteseguro).

## Cómo Probarlo en Local

```powershell
python -m http.server 8080 --directory website
# http://localhost:8080
```
