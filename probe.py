import base64
import json
import os
import re
import socket
import time
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from urllib.parse import unquote, urlparse

try:
    import yaml
except Exception:
    yaml = None


def b64decode_loose(s):
    s = s.strip()
    s = re.sub(r"\s+", "", s)
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s.encode()).decode("utf-8", "ignore")


def fetch_subscription(url):
    req = urllib.request.Request(url, headers={"User-Agent": "clash-verge/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read().decode("utf-8", "ignore")
    # Most subscriptions are one base64 blob; some are plain lines / YAML.
    try:
        decoded = b64decode_loose(raw)
        if "://" in decoded or "proxies:" in decoded:
            return decoded
    except Exception:
        pass
    return raw


def parse_clash_yaml(text, source):
    """Parse a Clash / Mihomo YAML subscription (proxies: list).

    Most Chinese airports hand out this format, not raw vmess:// links.
    Returns host/port/name/type per node; TCP latency works for any
    protocol, even ones this script cannot proxy-test (hysteria2, tuic…).
    """
    nodes = []
    if yaml is not None:
        try:
            data = yaml.safe_load(text) or {}
            for p in data.get("proxies") or []:
                if not isinstance(p, dict):
                    continue
                host, port = p.get("server", ""), p.get("port", 0)
                if host and port:
                    nodes.append({"name": str(p.get("name") or f"{host}:{port}"),
                                  "host": str(host), "port": int(port),
                                  "proto": str(p.get("type") or "proxy").lower(),
                                  "source": source})
            return nodes
        except Exception:
            pass
    # Fallback without PyYAML: scan "- name: … / server: … / port: …" blocks.
    for block in re.split(r"(?m)^\s*-\s+name\s*:", text):
        if "server:" not in block:
            continue
        name = block.split("\n", 1)[0].strip().strip('"').strip("'")
        m_host = re.search(r"server\s*:\s*([^\s#]+)", block)
        m_port = re.search(r"port\s*:\s*(\d+)", block)
        m_type = re.search(r"type\s*:\s*([A-Za-z0-9_-]+)", block)
        if m_host and m_port:
            nodes.append({"name": name or f"{m_host.group(1)}:{m_port.group(1)}",
                          "host": m_host.group(1), "port": int(m_port.group(1)),
                          "proto": (m_type.group(1).lower() if m_type else "proxy"),
                          "source": source})
    return nodes


def parse_nodes(text, source):
    # Clash YAML first — the format most airports actually give out.
    if "proxies:" in text:
        nodes = parse_clash_yaml(text, source)
        if nodes:
            return nodes
    nodes = []
    for line in text.splitlines():
        line = line.strip()
        if not line or "://" not in line:
            continue
        try:
            scheme, rest = line.split("://", 1)
            scheme = scheme.lower()
            name = ""
            host = ""
            port = 0
            if "#" in rest:
                rest, name = rest.rsplit("#", 1)
                name = unquote(name)
            if scheme == "vmess":
                data = json.loads(b64decode_loose(rest))
                host, port = data.get("add", ""), int(data.get("port", 0))
                name = name or data.get("ps", "")
            elif scheme in ("vless", "trojan"):
                if "?" in rest:
                    rest = rest.split("?", 1)[0]
                user_host = rest.rsplit("@", 1)[-1]
                host, port_s = user_host.rsplit(":", 1)
                port = int(port_s)
            elif scheme == "ss":
                # ss://base64(method:password@host:port) or ss://base64#name
                if "@" not in rest:
                    rest = b64decode_loose(rest)
                if "@" in rest:
                    creds, hostport = rest.rsplit("@", 1)
                    host, port_s = hostport.rsplit(":", 1)
                    port = int(port_s)
            else:
                continue
            if host and port:
                nodes.append({"name": name or f"{host}:{port}", "host": host,
                              "port": port, "proto": scheme, "source": source})
        except Exception:
            continue
    return nodes


# Nodes that are not real proxies, just account info the airport
# embeds in the subscription (traffic left, expiry, reset date).
# These would leak account info onto the public panel, so skip them.
INFO_KEYWORDS = ("剩余流量", "套餐到期", "距离下次重置", "下次重置",
                 "到期时间", "有效期", "剩余", "套餐", "流量：", "到期：")
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def is_info_node(name, host):
    if str(host).strip().lower() in LOCAL_HOSTS:
        return True
    return any(k in str(name) for k in INFO_KEYWORDS)


def tcp_latency(host, port, timeout=3):
    best = None
    ok = 0
    for _ in range(2):
        try:
            t0 = time.time()
            with socket.create_connection((host, port), timeout=timeout):
                pass
            ms = round((time.time() - t0) * 1000, 1)
            best = ms if best is None else min(best, ms)
            ok += 1
        except Exception:
            pass
    return best, ok


def main():
    # Supports SUB1..SUB10 so adding an airport later is just a new
    # Secret, no code change. Empty slots are skipped.
    subs = [(f"SUB{i}", os.environ.get(f"AIRPORT{i}_NAME") or f"机场{i}")
            for i in range(1, 11)]
    all_nodes = []
    for env_key, label in subs:
        url = os.environ.get(env_key, "").strip()
        if not url:
            print(f"skip {env_key}: not set")
            continue
        try:
            text = fetch_subscription(url)
            nodes = parse_nodes(text, label)
            before = len(nodes)
            nodes = [n for n in nodes if not is_info_node(n["name"], n["host"])]
            if before != len(nodes):
                print(f"{label}: filtered {before - len(nodes)} info nodes")
            print(f"{label}: {len(nodes)} nodes")
            all_nodes.extend(nodes)
        except Exception as e:
            print(f"{label} failed: {e}")

    results = []
    for n in all_nodes:
        ms, ok = tcp_latency(n["host"], n["port"])
        # Do NOT write host/port into results.json: the panel is public,
        # and the user wants server addresses hidden. Protocol is fine.
        results.append({"name": n["name"], "proto": n["proto"],
                        "source": n["source"],
                        "latency_ms": ms, "online": ok > 0,
                        "loss": 0 if ok == 2 else (50 if ok == 1 else 100)})

    results.sort(key=lambda x: (x["latency_ms"] is None, x["latency_ms"] or 99999))
    online = sum(1 for r in results if r["online"])
    out = {
        "updated_at": datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M 北京时间"),
        "total": len(results),
        "online": online,
        "offline": len(results) - online,
        "nodes": results,
    }
    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"done: {online}/{len(results)} online -> results.json")


if __name__ == "__main__":
    main()
