# Liquid Glass (efecto cristal de iPhone)

Efecto de cristal para un recuadro, al estilo de iOS. Incluye la refracción de los bordes, la aberración cromática, el brillo especular y el desenfoque del fondo.

![preview](preview.png)

## Uso

```html
<link rel="stylesheet" href="liquid-glass.css">

<div class="glass" id="box">Contenido</div>

<script src="liquid-glass.js"></script>
<script>
  new LiquidGlass(document.getElementById("box"), {
    refraction: 70,  // intensidad de la curvatura del fondo (px)
    bezel: 28,       // ancho del borde que refracta (px)
    aberration: 6,   // separación de colores en el borde (px)
    blur: 2.5,       // desenfoque del fondo (px)
    saturation: 1.6, // saturación del fondo
  });
  // o para todos: LiquidGlass.attachAll(".glass");
</script>
```

Variables CSS personalizables: `--glass-radius`, `--glass-tint`, `--glass-blur` y `--glass-saturate`.

## Cómo funciona

- **CSS (`liquid-glass.css`)**: tinte translúcido, sombras internas, borde especular con degradado enmascarado y brillo superior. Por sí solo da el "frosted glass" clásico de iOS.
- **JS (`liquid-glass.js`)**: calcula la forma del recuadro (rectángulo redondeado) y genera un *mapa de desplazamiento*. Lo aplica con un filtro SVG (`feDisplacementMap`) dentro de `backdrop-filter`, de modo que el fondo se curva en los bordes como una lente. El mapa se regenera si el recuadro cambia de tamaño.

## Compatibilidad

| Navegador | Resultado |
|---|---|
| Chrome / Edge / Opera / Android | Refracción completa |
| Safari / Firefox / iOS | Respaldo: desenfoque + brillo (sin refracción) |

Se respetan `prefers-reduced-transparency` y `prefers-reduced-motion`.

Abre `index.html` para ver la demo, con un recuadro arrastrable y controles en vivo.
