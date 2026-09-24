import threading
import time
import logging
import urllib.request

logger = logging.getLogger("django")

_ping_thread_started = False
_lock = threading.Lock()

def start_self_ping_worker():
    """
    Spawns a background daemon thread that pings https://rovexa.onrender.com/healthz
    every 4 minutes (240s) to keep Render free tier alive 24/7 without sleeping.
    """
    global _ping_thread_started
    with _lock:
        if _ping_thread_started:
            return
        _ping_thread_started = True

    def ping_loop():
        # Initial delay to ensure server startup complete
        time.sleep(15)
        logger.info("🟢 24/7 Render Self-Ping Keep-Alive Worker Active!")

        while True:
            try:
                req = urllib.request.Request(
                    "https://rovexa.onrender.com/healthz",
                    headers={"User-Agent": "Rovexa-247-SelfPing-Worker"}
                )
                with urllib.request.urlopen(req, timeout=12) as resp:
                    pass
            except Exception as e:
                logger.debug(f"Self-ping heartbeat status: {e}")

            # Sleep 4 minutes (240 seconds) — well within Render's 15-minute idle limit
            time.sleep(240)

    thread = threading.Thread(target=ping_loop, daemon=True, name="RenderKeepAliveWorker")
    thread.start()
