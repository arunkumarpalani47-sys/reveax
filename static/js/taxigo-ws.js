/**
 * Rovexa Real-Time WebSocket Client
 * Sprint 1 — Location, Booking, Driver consumers
 *
 * Usage (Customer):
 *   const tracker = new RovexaBookingTracker("booking_id_here");
 *   tracker.onStatusChange = (status, data) => { ... };
 *   tracker.onDriverLocation = (lat, lng, heading) => { ... };
 *
 * Usage (Driver):
 *   const driver = new RovexaDriverWS();
 *   driver.onRideRequest = (data) => { ... };
 *   driver.startLocationStream(); // GPS every 3s
 */

const RovexaWS = (() => {

  const WS_BASE = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}`;

  // ─── Reconnect helper ───────────────────────────────────────────────────────
  class AutoReconnectWS {
    constructor(url, { onMessage, onOpen, onClose, maxRetries = 10 } = {}) {
      this.url        = url;
      this.onMessage  = onMessage  || (() => {});
      this.onOpen     = onOpen     || (() => {});
      this.onClose    = onClose    || (() => {});
      this.maxRetries = maxRetries;
      this._retries   = 0;
      this._ws        = null;
      this._connect();
    }

    _connect() {
      this._ws = new WebSocket(this.url);
      this._ws.onopen    = (e) => { this._retries = 0; this.onOpen(e); };
      this._ws.onmessage = (e) => this.onMessage(JSON.parse(e.data));
      this._ws.onclose   = (e) => {
        this.onClose(e);
        if (this._retries < this.maxRetries) {
          const delay = Math.min(1000 * 2 ** this._retries, 30000);
          this._retries++;
          setTimeout(() => this._connect(), delay);
        }
      };
      this._ws.onerror = () => this._ws.close();
    }

    send(data) {
      if (this._ws && this._ws.readyState === WebSocket.OPEN) {
        this._ws.send(JSON.stringify(data));
        return true;
      }
      return false;
    }

    close() { this._ws && this._ws.close(); }

    get readyState() { return this._ws ? this._ws.readyState : WebSocket.CLOSED; }
  }


  // ─── 1. BOOKING TRACKER — for customers ────────────────────────────────────
  class BookingTracker {
    constructor(bookingId) {
      this.bookingId      = bookingId;
      this.onStatusChange = null;
      this.onDriverLocation = null;

      const url = `${WS_BASE}/ws/booking/${bookingId}/`;

      this._ws = new AutoReconnectWS(url, {
        onOpen:    () => console.log(`[Rovexa] Booking WS connected: ${bookingId}`),
        onMessage: (data) => this._handle(data),
        onClose:   () => console.log(`[Rovexa] Booking WS disconnected`),
      });
    }

    _handle(data) {
      switch (data.type) {
        case "booking_status":
          if (typeof this.onStatusChange === "function") {
            this.onStatusChange(data.status, data);
          }
          this._updateStatusUI(data.status, data);
          break;

        case "driver_location":
          if (typeof this.onDriverLocation === "function") {
            this.onDriverLocation(data.lat, data.lng, data.heading || 0, data);
          }
          break;

        case "driver_arrived":
          this._showToast("🚗 Driver has arrived at your pickup!", "success");
          break;

        case "trip_started":
          this._showToast("🛣️ Trip started! OTP verified successfully.", "info");
          break;

        case "trip_completed":
          this._showToast("✅ Trip completed! Thank you for riding with Rovexa.", "success");
          if (typeof this.onStatusChange === "function") {
            this.onStatusChange("TRIP_COMPLETED", data);
          }
          break;

        case "booking_cancelled":
          this._showToast("❌ Booking cancelled: " + (data.reason || ""), "danger");
          break;
      }
    }

    _updateStatusUI(status, data) {
      const steps = [
        "SEARCHING_DRIVER", "DRIVER_ASSIGNED", "DRIVER_COMING",
        "DRIVER_ARRIVED", "TRIP_STARTED", "TRIP_COMPLETED"
      ];
      const labels = {
        "SEARCHING_DRIVER": "🔍 Searching for Driver...",
        "DRIVER_ASSIGNED":  "✅ Driver Found!",
        "DRIVER_COMING":    "🚗 Driver is on the way",
        "DRIVER_ARRIVED":   "📍 Driver has arrived",
        "TRIP_STARTED":     "🛣️ Trip Started",
        "TRIP_COMPLETED":   "🏁 Trip Completed",
        "NO_DRIVER_FOUND":  "😔 No drivers available",
        "BOOKING_CANCELLED":"❌ Booking Cancelled",
      };

      const el = document.getElementById("booking-status-label");
      if (el) el.textContent = labels[status] || status;

      const idx = steps.indexOf(status);
      steps.forEach((s, i) => {
        const dot = document.getElementById(`step-${s}`);
        if (dot) {
          dot.classList.toggle("active",    i <= idx);
          dot.classList.toggle("completed", i <  idx);
        }
      });

      // Show driver info if assigned
      if (data.driver_id && document.getElementById("driver-info-card")) {
        document.getElementById("driver-info-card").style.display = "block";
      }
    }

    _showToast(message, type = "info") {
      if (!window.showRovexaToast) return;
      window.showRovexaToast(message, type);
    }

    close() { this._ws.close(); }
  }


  // ─── 2. DRIVER LOCATION STREAMER ───────────────────────────────────────────
  class DriverLocationStreamer {
    constructor() {
      this._ws          = null;
      this._gpsInterval = null;
      this.isOnline     = false;
      this.onRideRequest = null;

      const url = `${WS_BASE}/ws/location/`;
      this._ws = new AutoReconnectWS(url, {
        onOpen:    () => console.log("[Rovexa Driver] Location WS connected"),
        onMessage: (data) => this._handle(data),
      });
    }

    _handle(data) {
      if (data.type === "ride_request" && typeof this.onRideRequest === "function") {
        this.onRideRequest(data);
      }
    }

    startGPSStream() {
      if (!navigator.geolocation) {
        console.error("[Rovexa] Geolocation not supported.");
        return;
      }
      this._gpsInterval = setInterval(() => {
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            this._ws.send({
              type:    "gps_update",
              lat:     pos.coords.latitude,
              lng:     pos.coords.longitude,
              heading: pos.coords.heading || 0,
              speed:   pos.coords.speed   || 0,
            });
          },
          (err) => console.warn("[Rovexa GPS]", err.message),
          { enableHighAccuracy: true, timeout: 5000 }
        );
      }, 3000);  // every 3 seconds
    }

    stopGPSStream() {
      if (this._gpsInterval) {
        clearInterval(this._gpsInterval);
        this._gpsInterval = null;
      }
      this._ws.send({ type: "go_offline" });
    }

    goOnline(lat, lng) {
      this.isOnline = true;
      this._ws.send({ type: "go_online", lat, lng });
      this.startGPSStream();
    }

    goOffline() {
      this.isOnline = false;
      this.stopGPSStream();
    }

    close() {
      this.stopGPSStream();
      this._ws && this._ws.close();
    }
  }


  // ─── 3. DRIVER RIDE REQUEST HANDLER ────────────────────────────────────────
  class DriverRideHandler {
    constructor() {
      this._ws = null;
      this.onRideRequest   = null;
      this.onRideTaken     = null;
      this.onRideCancelled = null;
      this._timer          = null;

      const url = `${WS_BASE}/ws/driver/`;
      this._ws = new AutoReconnectWS(url, {
        onOpen:    () => console.log("[Rovexa Driver] Ride request WS connected"),
        onMessage: (data) => this._handle(data),
      });
    }

    _handle(data) {
      switch (data.type) {
        case "ride_request":
          this._startRequestTimer(data);
          if (typeof this.onRideRequest === "function") this.onRideRequest(data);
          break;
        case "ride_accepted":
          this._clearTimer();
          if (typeof this.onRideAccepted === "function") this.onRideAccepted(data);
          break;
        case "ride_taken":
          this._clearTimer();
          if (typeof this.onRideTaken === "function") this.onRideTaken(data);
          break;
        case "ride_cancelled":
          this._clearTimer();
          if (typeof this.onRideCancelled === "function") this.onRideCancelled(data);
          break;
      }
    }

    accept(bookingId) {
      this._clearTimer();
      this._ws.send({ type: "accept_ride", booking_id: bookingId });
    }

    reject(bookingId) {
      this._clearTimer();
      this._ws.send({ type: "reject_ride", booking_id: bookingId });
    }

    _startRequestTimer(data) {
      // Auto-reject after timeout
      const timeout = (data.timeout || 15) * 1000;
      this._timer = setTimeout(() => {
        this.reject(data.booking_id);
        if (typeof this.onRideCancelled === "function") {
          this.onRideCancelled({ reason: "Timeout — no response" });
        }
      }, timeout);
    }

    _clearTimer() {
      if (this._timer) { clearTimeout(this._timer); this._timer = null; }
    }

    close() { this._ws && this._ws.close(); }
  }


  // ─── 4. Toast notification utility ─────────────────────────────────────────
  window.showRovexaToast = function(message, type = "info") {
    const container = document.getElementById("rovexa-toast-container") || (() => {
      const div = document.createElement("div");
      div.id = "rovexa-toast-container";
      div.style.cssText = "position:fixed;top:80px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:10px;";
      document.body.appendChild(div);
      return div;
    })();

    const colors = { success: "#10b981", danger: "#ef4444", info: "#3b82f6", warning: "#f59e0b" };
    const toast  = document.createElement("div");
    toast.style.cssText = `
      background:${colors[type] || "#3b82f6"};color:white;padding:14px 20px;
      border-radius:12px;font-size:14px;font-weight:500;max-width:320px;
      box-shadow:0 8px 30px rgba(0,0,0,.25);animation:slideIn .3s ease;
    `;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
  };

  // Inject toast animation
  const style = document.createElement("style");
  style.textContent = `@keyframes slideIn{from{transform:translateX(120%);opacity:0}to{transform:translateX(0);opacity:1}}`;
  document.head.appendChild(style);


  return { BookingTracker, DriverLocationStreamer, DriverRideHandler };

})();
