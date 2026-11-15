"""
在 sandbox 容器「裡面」執行的外連測試。
每一項「應該失敗」的連線如果成功了，就代表有洩漏路徑。

只用 Python 標準函式庫，不需要 curl / ping / nslookup。
用法（由 verify.sh 自動呼叫）：python3 egress_test.py [--llm-url URL]
"""
import socket
import sys
import urllib.request

TIMEOUT = 4
results = []  # (ok, 說明)


def record(ok, msg):
    results.append((ok, msg))
    print(("  ✅ PASS  " if ok else "  ❌ FAIL  ") + msg, flush=True)


def tcp(host, port, family=socket.AF_INET):
    """回傳 'open' / 'refused' / 'blocked'"""
    try:
        with socket.socket(family, socket.SOCK_STREAM) as s:
            s.settimeout(TIMEOUT)
            s.connect((host, port))
            return "open"
    except ConnectionRefusedError:
        return "refused"
    except OSError:
        return "blocked"


def main():
    llm_url = "http://llm:11434/api/tags"
    if "--llm-url" in sys.argv:
        llm_url = sys.argv[sys.argv.index("--llm-url") + 1]

    print("\n[1] DNS 查詢外部網域（應該失敗；DNS 本身也能被拿來偷傳資料）")
    for name in ["example.com", "github.com", "api.openai.com"]:
        try:
            socket.getaddrinfo(name, 443)
            record(False, f"{name} 竟然查得到 IP")
        except OSError:
            record(True, f"{name} 查不到")

    print("\n[2] 直接用 IP 連外部（應該失敗；這就是 NAT 出口）")
    for ip, port in [("1.1.1.1", 443), ("8.8.8.8", 53), ("140.82.112.3", 443)]:
        r = tcp(ip, port)
        record(r == "blocked", f"TCP {ip}:{port} → {r}")

    print("\n[3] 直接送 UDP DNS 封包給 8.8.8.8（應該收不到回應）")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(TIMEOUT)
            query = bytes.fromhex("abcd01000001000000000000076578616d706c6503636f6d0000010001")
            s.sendto(query, ("8.8.8.8", 53))
            s.recvfrom(512)
            record(False, "UDP 8.8.8.8:53 有回應")
    except OSError:
        record(True, "UDP 8.8.8.8:53 沒有回應")

    print("\n[4] IPv6 對外連線（應該失敗）")
    r = tcp("2606:4700:4700::1111", 443, socket.AF_INET6)
    record(r == "blocked", f"TCP [2606:4700:4700::1111]:443 → {r}")

    print("\n[5] 連到主機本身（172.30.0.1）上的服務（應該失敗；主機上的 proxy 也能當跳板）")
    for port in [22, 53, 80, 443, 3128, 8080, 11434]:
        r = tcp("172.30.0.1", port)
        # refused 代表封包有到達主機（只是那個 port 沒開），也算碰得到主機
        record(r == "blocked", f"TCP 172.30.0.1:{port} → {r}")

    print("\n[6] 連到 sandbox 裡的模型伺服器（應該成功，不然 Hermes 不能用）")
    try:
        with urllib.request.urlopen(llm_url, timeout=10) as resp:
            record(resp.status == 200, f"{llm_url} → HTTP {resp.status}")
    except Exception as e:  # noqa: BLE001
        record(False, f"{llm_url} 連不到：{e}")

    failed = [m for ok, m in results if not ok]
    print()
    if failed:
        print(f"結果：{len(failed)} 項失敗 ❌")
        sys.exit(1)
    print(f"結果：全部 {len(results)} 項通過 ✅")


if __name__ == "__main__":
    main()
