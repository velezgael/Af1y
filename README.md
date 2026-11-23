# AF1 x GTA VI — Monitor de stock

Vigila las páginas de producto de los Air Force 1 de GTA VI y te avisa **al instante**
cuando hay stock en tu talla: Discord, Telegram, pitido y apertura automática del
navegador en el producto. **La compra la completas tú**, con tu cuenta, así no te
cancelan el pedido ni te banean por usar bots.

## Cactus Jack (shop.travisscott.com)

`config.example.yaml` ya trae los 3 AF1 '07 RS x GTA VI (Black, Gradient Camo, White).
Solo cambia `sizes` por tus tallas (US hombre).

## Instalación

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml   # edita productos, tallas y notificaciones
```

## Uso

```bash
python monitor.py                 # vigilar en bucle
python monitor.py --once          # una sola comprobación
python monitor.py --test-notify   # probar Discord/Telegram
```

## Tipos de producto

| tipo      | cómo funciona |
|-----------|---------------|
| `shopify` | Lee el JSON público del producto (`/products/<handle>.json`); si la tienda lo bloquea (como Cactus Jack), usa los datos que vienen en la propia página. Filtra por `sizes`. |
| `page`    | Descarga la página y busca palabras clave de "en stock" / "agotado". Sirve para la mayoría de tiendas. |

> Nike SNKRS suele lanzar mediante sorteo (Draw): ahí no hay stock que vigilar, apúntate
> manualmente en la app. Este monitor es útil para restocks y tiendas/resellers.

## Consejos para conseguirlos

- Ten la sesión iniciada y la dirección y el pago guardados en la tienda antes del drop.
- Activa las notificaciones del móvil para Discord/Telegram.
- No bajes de 30 s de intervalo: si vas más rápido, la tienda puede bloquearte la IP.
