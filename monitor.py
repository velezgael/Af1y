#!/usr/bin/env python3
"""Monitor de stock para los AF1 x GTA VI.

Vigila páginas de producto y avisa (Discord, Telegram, pitido, navegador)
en cuanto hay stock. La compra la completas tú manualmente.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

import requests
import yaml

USER_AGENT = "AF1-Stock-Monitor/1.0 (+uso personal)"
MIN_INTERVAL = 30


@dataclass
class Result:
    in_stock: bool
    detail: str = ""


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


# ---------------------------------------------------------------- checkers

def check_shopify(session: requests.Session, product: dict) -> Result:
    parts = urlsplit(product["url"])
    path = parts.path.rstrip("/")
    if path.endswith(".json"):
        path = path[:-5]
    json_url = urlunsplit((parts.scheme, parts.netloc, path + ".json", "", ""))
    r = session.get(json_url, timeout=15)
    if r.ok:
        variants = r.json()["product"]["variants"]
    else:
        # Algunas tiendas (p. ej. Cactus Jack) bloquean el .json; usamos los
        # datos del producto que vienen incrustados en la propia página.
        page_url = urlunsplit((parts.scheme, parts.netloc, path, "", ""))
        r = session.get(page_url, timeout=15)
        r.raise_for_status()
        variants = extract_variants_from_html(r.text)

    wanted = {str(s).strip().lower() for s in product.get("sizes", []) or []}
    available = []
    for v in variants:
        if not v.get("available"):
            continue
        label = " / ".join(str(v.get(k) or "") for k in ("option1", "option2", "option3")).strip(" /")
        opts = {str(v.get(k) or "").strip().lower() for k in ("option1", "option2", "option3")}
        if wanted and not (wanted & opts):
            continue
        available.append(label or v.get("title", "?"))

    if available:
        return Result(True, "Tallas: " + ", ".join(available))
    return Result(False, "sin tallas disponibles" + (" (de las que buscas)" if wanted else ""))


_PRODUCT_JSON_RE = re.compile(
    r"<script[^>]*type=['\"]application/json['\"][^>]*class=['\"]js-product-json['\"][^>]*>(.*?)</script>",
    re.S | re.I,
)


def extract_variants_from_html(html: str) -> list[dict]:
    m = _PRODUCT_JSON_RE.search(html)
    if not m:
        raise ValueError("no se encontraron los datos del producto en la página")
    data = json.loads(m.group(1))
    return (data.get("product") or data)["variants"]


def check_page(session: requests.Session, product: dict) -> Result:
    r = session.get(product["url"], timeout=15)
    r.raise_for_status()
    html = r.text.lower()
    oos = [k for k in product.get("out_of_stock_keywords", []) if k.lower() in html]
    ins = [k for k in product.get("in_stock_keywords", []) if k.lower() in html]
    if ins and not oos:
        return Result(True, f"encontrado: {ins[0]!r}")
    if oos:
        return Result(False, f"encontrado: {oos[0]!r}")
    return Result(False, "sin palabras clave reconocidas")


CHECKERS = {"shopify": check_shopify, "page": check_page}


# ----------------------------------------------------------- notifications

def notify(cfg: dict, session: requests.Session, product: dict, result: Result) -> None:
    text = f"🔥 ¡STOCK! {product['name']}\n{result.detail}\n{product['url']}"
    n = cfg.get("notifications", {}) or {}

    if hook := n.get("discord_webhook_url"):
        try:
            session.post(hook, json={"content": text}, timeout=10).raise_for_status()
        except requests.RequestException as e:
            log(f"Error enviando a Discord: {e}")

    token, chat = n.get("telegram_bot_token"), n.get("telegram_chat_id")
    if token and chat:
        try:
            session.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat, "text": text},
                timeout=10,
            ).raise_for_status()
        except requests.RequestException as e:
            log(f"Error enviando a Telegram: {e}")

    if cfg.get("beep", True):
        sys.stdout.write("\a" * 3)
        sys.stdout.flush()

    if cfg.get("open_browser", True):
        webbrowser.open(product["url"])


# -------------------------------------------------------------------- main

def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    if not cfg.get("products"):
        sys.exit("config: no hay productos en 'products'.")
    for p in cfg["products"]:
        if p.get("type") not in CHECKERS:
            sys.exit(f"config: tipo desconocido {p.get('type')!r} en {p.get('name')!r} (usa: {', '.join(CHECKERS)})")
        if not p.get("url"):
            sys.exit(f"config: falta 'url' en {p.get('name')!r}")
    return cfg


def main() -> None:
    ap = argparse.ArgumentParser(description="Monitor de stock AF1 x GTA VI")
    ap.add_argument("-c", "--config", default="config.yaml")
    ap.add_argument("--once", action="store_true", help="comprobar una vez y salir")
    ap.add_argument("--test-notify", action="store_true", help="enviar una alerta de prueba y salir")
    args = ap.parse_args()

    cfg = load_config(args.config)
    interval = max(MIN_INTERVAL, int(cfg.get("interval_seconds", 60)))

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    if args.test_notify:
        notify(cfg, session, cfg["products"][0], Result(True, "Esto es una prueba"))
        log("Alerta de prueba enviada.")
        return

    was_in_stock: dict[str, bool] = {}
    log(f"Vigilando {len(cfg['products'])} producto(s) cada {interval}s. Ctrl+C para salir.")
    try:
        while True:
            for p in cfg["products"]:
                try:
                    res = CHECKERS[p["type"]](session, p)
                except (requests.RequestException, ValueError, KeyError, json.JSONDecodeError) as e:
                    log(f"{p['name']}: error al comprobar ({e})")
                    continue
                state = "EN STOCK" if res.in_stock else "agotado"
                log(f"{p['name']}: {state} — {res.detail}")
                # Avisar solo al pasar de agotado -> en stock.
                if res.in_stock and not was_in_stock.get(p["url"]):
                    notify(cfg, session, p, res)
                was_in_stock[p["url"]] = res.in_stock
            if args.once:
                break
            time.sleep(interval)
    except KeyboardInterrupt:
        log("Detenido.")


if __name__ == "__main__":
    main()
