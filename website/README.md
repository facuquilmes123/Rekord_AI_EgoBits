# Rekord AI — Official Web Experience (Local)

Sitio web oficial local de **Rekord AI**, diseñado con estética de cabina profesional y animación cinética de alta fidelidad (*Obsidian Kinetic Glass* & After Effects Motion Engine).

## Características Implementadas

1. **Visualizador de Forma de Onda Tri-Banda (CDJ-3000 Style)**:
   - Renderizado en `<canvas>` HTML5 interactivo.
   - Espectro separado: Bajas (Azul/Cian), Medias (Ámbar/Naranja) y Altas (Blanco).
   - Playhead dinámico a 126 BPM con Hot Cues verde y violeta.
   - Clickeable para pausar/reproducir y arrastrable (scrubber manual).

2. **Simulador de Rueda Armónica Camelot**:
   - 12 tonalidades activas (1A a 12A / 1B a 12B).
   - Detección instantánea de compatibilidad armónica (+1 / -1 / cambio modal relativo).
   - Cálculo del score de mezcla (hasta 99.4% de precisión).

3. **Slider Comparativo Interactivo Antes / Después**:
   - Compara la captura real inicial (modo claro básico) frente al nuevo rediseño en modo oscuro de cabina DJ (*Obsidian Kinetic*).
   - Control deslizante manual por arrastre de ratón o toque táctil.

4. **Matriz de Precios con Anuncio de Prueba Gratuita de 10 Días**:
   - Selector interactivo Mensual / Anual (con cálculo de ahorro de 2 meses).
   - 3 Niveles: Club Starter ($19/m), Pro Touring ($29/m - Destacado) y Lifetime Tour ($199 único).
   - **Prueba gratuita de 10 días anunciada en cabecera, hero y tarjetas de precio sin requerir tarjeta de crédito**.

5. **Modal de Activación Inmediata de Licencia de Prueba**:
   - Genera un token offline aleatorio (ej. `RKRDAI-VIP-8A9A-XXXX-10DAYS`).
   - Botón de copiado con un clic.
   - Enlace directo a la descarga del instalador oficial Windows x64.

6. **Galería Visual Ultra-Premium**:
   - `assets/images/rekord_ui_pro.jpg`: Mockup rediseñado de la interfaz en cabina.
   - `assets/images/rekord_booth_live.jpg`: Foto cinematográfica del software corriendo junto a Pioneer CDJ-3000s y DJM-A9 en escenario de festival.
   - `assets/images/rekord_harmonic_flow.jpg`: Visualización holográfica de energía armónica y curva de pista LUFS.

---

## Cómo Probarlo en Local

Podés abrir directamente `index.html` en tu navegador, o iniciar un servidor local ultra-rápido con Python o Node:

```powershell
# Opción 1: Servidor nativo de Python (recomendado)
python -m http.server 8080 --directory website

# Luego abrí en tu navegador:
# http://localhost:8080
```
