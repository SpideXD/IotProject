
(function () {
    "use strict";

    const TOTAL_SEATS = 28;
    const ALERT_LIMIT = 20;
    const HISTORY_POINTS_MAX = 720;

    const STATE_COLORS = {
        empty:     "#22c55e",
        occupied:  "#ef4444",
        suspected: "#eab308",
        ghost:     "#a855f7",
    };

    const ZONE_DEFINITIONS = [
        "Zone A - Window",
        "Zone B - Center",
        "Zone C - Back Wall",
        "Zone D - Study Pods",
        "Zone E - Group Tables",
        "Zone F - Quiet Area",
        "Zone G - Lounge",
        "Zone H - Entrance",
    ];

    let currentTheme = "dark";
    let soundEnabled = true;
    let showAcknowledged = false;
    let currentHistoryMinutes = 60;
    let heatmapMode = false;
    let selectedSeatId = null;
    let analyticsData = null;

    const socket = io({ transports: ["websocket", "polling"] });

    socket.on("connect", () => {
        setConnectionStatus(true);
        console.log("[Dashboard] Connected to server");
        socket.emit("request_history", { minutes: currentHistoryMinutes });
    });

    socket.on("disconnect", () => {
        setConnectionStatus(false);
        console.warn("[Dashboard] Disconnected from server");
    });

    const dom = {
        clock:            document.getElementById("live-clock"),
        connStatus:       document.getElementById("connection-status"),
        sensorIndicators: document.getElementById("sensor-indicators"),
        cameraImg:        {},
        cameraOverlay:    {},
        zoneGrid:         document.getElementById("zone-grid"),
        seatGrid:         document.getElementById("seat-grid"),
        radarList:        document.getElementById("radar-list"),
        alertFeed:        document.getElementById("alert-feed"),
        chartCanvas:      document.getElementById("history-chart"),
        statOccupied:     document.getElementById("stat-occupied"),
        statEmpty:        document.getElementById("stat-empty"),
        statGhost:        document.getElementById("stat-ghost"),
        statScans:        document.getElementById("stat-scans"),
        statUtil:         document.getElementById("stat-util"),
        tooltip:          document.getElementById("seat-tooltip"),
        themeToggle:      document.getElementById("theme-toggle"),
        soundToggle:      document.getElementById("sound-toggle"),
        roomSelect:      document.getElementById("room-select"),
        alertCount:      document.getElementById("alert-count"),
        heatmapLegend:   document.getElementById("heatmap-legend"),
        analyticsSection: document.getElementById("analytics-section"),
    };

    let seats = {};
    let zones = {};
    let alertCount = 0;
    let acknowledgedAlerts = new Set();
    let historyChart = null;

    function init() {
        dom.cameraImg["back_rail"]  = document.getElementById("camera-img-back");
        dom.cameraImg["front_rail"] = document.getElementById("camera-img-front");
        dom.cameraOverlay["back_rail"]  = document.getElementById("camera-overlay-back_rail");
        dom.cameraOverlay["front_rail"] = document.getElementById("camera-overlay-front_rail");

        buildZoneGrid();
        buildSeatGrid();
        buildRadarList();
        initHistoryChart();
        startClock();
        initEventListeners();

        socket.on("telemetry",     handleTelemetry);
        socket.on("camera_frame",  handleCameraFrame);
        socket.on("sensor_status", handleSensorStatus);
        socket.on("ghost_alert",   handleGhostAlert);
        socket.on("stats",         handleStats);
        socket.on("seat_state",    handleSeatState);
        socket.on("history_data",  handleHistoryData);
        socket.on("theme_changed", handleThemeChanged);
        socket.on("room_changed", handleRoomChanged);
        socket.on("alert_acknowledged", handleAlertAcknowledged);
        socket.on("alert_snoozed", handleAlertSnoozed);
        socket.on("alert_resolved", handleAlertResolved);
        socket.on("play_alert_sound", handlePlayAlertSound);

        // Fetch initial state
        fetchInitialState();
    }

    function fetchInitialState() {
        fetch("/api/state")
            .then(r => r.json())
            .then(data => {
                if (data.theme) {
                    currentTheme = data.theme;
                    applyTheme(currentTheme);
                }
                if (data.rooms) {
                    updateRoomSelector(data.rooms, data.current_room);
                }
                if (data.sound_enabled !== undefined) {
                    soundEnabled = data.sound_enabled;
                    updateSoundButton();
                }
            })
            .catch(err => console.error("Failed to fetch initial state:", err));
    }

    function initEventListeners() {
        // Theme toggle
        dom.themeToggle?.addEventListener("click", toggleTheme);

        // Sound toggle
        dom.soundToggle?.addEventListener("click", toggleSound);

        // Room selector
        dom.roomSelect?.addEventListener("change", (e) => {
            selectRoom(e.target.value);
        });

        // Heatmap toggle
        document.getElementById("btn-heatmap")?.addEventListener("click", toggleHeatmap);

        // Export button
        document.getElementById("btn-export")?.addEventListener("click", showExportModal);

        // Show acknowledged toggle
        document.getElementById("btn-show-acked")?.addEventListener("click", toggleShowAcknowledged);

        // History range buttons
        document.getElementById("btn-1h")?.addEventListener("click", () => setHistoryRange(60));
        document.getElementById("btn-6h")?.addEventListener("click", () => setHistoryRange(360));
        document.getElementById("btn-24h")?.addEventListener("click", () => setHistoryRange(1440));

        // Seat modal
        document.getElementById("modal-close")?.addEventListener("click", closeSeatModal);
        document.getElementById("modal-reserve")?.addEventListener("click", handleReserveSeat);

        // Export modal
        document.getElementById("export-modal-close")?.addEventListener("click", closeExportModal);
        document.getElementById("export-cancel")?.addEventListener("click", closeExportModal);
        document.getElementById("export-download")?.addEventListener("click", handleExportDownload);
    }

    function toggleTheme() {
        const newTheme = currentTheme === "dark" ? "light" : "dark";
        fetch("/api/settings/theme", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ theme: newTheme }),
        })
            .then(r => r.json())
            .then(data => {
                if (data.status === "ok") {
                    applyTheme(newTheme);
                }
            })
            .catch(err => console.error("Failed to change theme:", err));
    }

    function applyTheme(theme) {
        currentTheme = theme;
        document.body.classList.toggle("light-theme", theme === "light");
        document.getElementById("theme-icon").textContent = theme === "dark" ? "🌙" : "☀️";
    }

    function handleThemeChanged(data) {
        applyTheme(data.theme);
    }

    function toggleSound() {
        soundEnabled = !soundEnabled;
        fetch("/api/settings/sound", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ enabled: soundEnabled }),
        })
            .then(() => updateSoundButton())
            .catch(err => console.error("Failed to toggle sound:", err));
    }

    function updateSoundButton() {
        document.getElementById("sound-icon").textContent = soundEnabled ? "🔔" : "🔕";
    }

    function selectRoom(roomId) {
        fetch(`/api/rooms/${roomId}/select`, { method: "POST" })
            .then(r => r.json())
            .then(data => {
                if (data.status === "ok") {
                    console.log("Switched to room:", roomId);
                    // Clear current data
                    seats = {};
                    zones = {};
                    buildSeatGrid();
                    buildZoneGrid();
                    socket.emit("request_history", { minutes: currentHistoryMinutes });
                }
            })
            .catch(err => console.error("Failed to switch room:", err));
    }

    function handleRoomChanged(data) {
        console.log("Room changed:", data);
        if (dom.roomSelect) {
            dom.roomSelect.value = data.new_room;
        }
    }

    function updateRoomSelector(rooms, currentRoom) {
        if (!dom.roomSelect) return;
        dom.roomSelect.innerHTML = "";
        Object.entries(rooms).forEach(([id, config]) => {
            const opt = document.createElement("option");
            opt.value = id;
            opt.textContent = config.name;
            if (id === currentRoom) opt.selected = true;
            dom.roomSelect.appendChild(opt);
        });
    }

    function toggleHeatmap() {
        heatmapMode = !heatmapMode;
        document.getElementById("heatmap-legend").style.display = heatmapMode ? "flex" : "none";
        document.getElementById("btn-heatmap").classList.toggle("active", heatmapMode);
        updateHeatmap();
    }

    function updateHeatmap() {
        if (!heatmapMode) return;
        // Update zone cards with heatmap colors
        Object.entries(zones).forEach(([zoneName, zoneData]) => {
            const idx = ZONE_DEFINITIONS.findIndex(
                z => z.toLowerCase() === zoneName.toLowerCase() ||
                     z.toLowerCase().includes(zoneName.toLowerCase())
            );
            if (idx < 0) return;
            const card = document.getElementById("zone-card-" + idx);
            if (!card) return;

            const occupied = zoneData.occupied || 0;
            const total = zoneData.total || 1;
            const pct = (occupied / total) * 100;

            // Heatmap color interpolation
            const hue = (1 - pct / 100) * 120; // Green (120) to Red (0)
            card.style.background = `hsl(${hue}, 60%, 30%)`;
        });
    }

    function toggleShowAcknowledged() {
        showAcknowledged = !showAcknowledged;
        document.getElementById("btn-show-acked").classList.toggle("active", showAcknowledged);
        // Refresh alerts display
        socket.emit("request_history", { minutes: currentHistoryMinutes });
    }

    function setHistoryRange(minutes) {
        currentHistoryMinutes = minutes;
        document.getElementById("history-range").textContent =
            minutes >= 60 ? `Last ${minutes / 60} hour${minutes >= 120 ? "s" : ""}` : `Last ${minutes}m`;
        socket.emit("request_history", { minutes });
    }

    function showExportModal() {
        document.getElementById("export-modal").style.display = "flex";
    }

    function closeExportModal() {
        document.getElementById("export-modal").style.display = "none";
    }

    function handleExportDownload() {
        const type = document.getElementById("export-type").value;
        const time = document.getElementById("export-time").value;
        const format = document.getElementById("export-format").value;

        const url = `/api/export/${type}?minutes=${time}&format=${format}`;
        window.open(url, "_blank");
        closeExportModal();
    }

    function showSeatModal(seatId) {
        selectedSeatId = seatId;
        const seatData = seats[seatId];
        if (!seatData) return;

        document.getElementById("modal-seat-id").textContent = `Seat ${seatId}`;

        const body = document.getElementById("modal-body");
        body.innerHTML = `
            <div class="seat-detail-grid">
                <div class="detail-item">
                    <label>State</label>
                    <span class="state-badge ${seatData.state}">${seatData.state || "unknown"}</span>
                </div>
                <div class="detail-item">
                    <label>Zone</label>
                    <span>${seatData.zone || "N/A"}</span>
                </div>
                <div class="detail-item">
                    <label>Occupancy Score</label>
                    <span>${((seatData.occupancy_score || 0) * 100).toFixed(1)}%</span>
                </div>
                <div class="detail-item">
                    <label>Object Type</label>
                    <span>${seatData.object_type || "empty"}</span>
                </div>
                <div class="detail-item">
                    <label>Confidence</label>
                    <span>${((seatData.confidence || 0) * 100).toFixed(1)}%</span>
                </div>
                <div class="detail-item">
                    <label>Radar Presence</label>
                    <span>${((seatData.radar_presence || 0) * 100).toFixed(1)}%</span>
                </div>
                <div class="detail-item">
                    <label>Has Motion</label>
                    <span>${seatData.has_motion ? "Yes" : "No"}</span>
                </div>
            </div>
        `;

        document.getElementById("seat-modal").style.display = "flex";
    }

    function closeSeatModal() {
        document.getElementById("seat-modal").style.display = "none";
        selectedSeatId = null;
    }

    function handleReserveSeat() {
        if (!selectedSeatId) return;
        const userId = prompt("Enter your user ID:");
        if (!userId) return;

        fetch(`/api/reservation/${selectedSeatId}`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ user_id: userId }),
        })
            .then(r => r.json())
            .then(data => {
                if (data.status === "created" || data.status === "extended") {
                    alert(`Seat ${selectedSeatId} reserved successfully!`);
                    closeSeatModal();
                } else {
                    alert(`Reservation failed: ${data.message}`);
                }
            })
            .catch(err => {
                alert("Reservation failed: " + err);
            });
    }

    function handlePlayAlertSound(data) {
        if (!soundEnabled) return;
        const audio = document.getElementById("alert-sound");
        if (audio) {
            audio.play().catch(() => {});
        }
    }

    function handleAlertAcknowledged(data) {
        acknowledgedAlerts.add(data.alert_id);
        updateAlertCount();
    }

    function handleAlertSnoozed(data) {
        acknowledgedAlerts.add(data.alert_id);
        updateAlertCount();
    }

    function handleAlertResolved(data) {
        acknowledgedAlerts.delete(data.alert_id);
        // Remove alert from feed
        const alertEl = document.querySelector(`[data-alert-id="${data.alert_id}"]`);
        if (alertEl) {
            alertEl.remove();
        }
        updateAlertCount();
    }

    function updateAlertCount() {
        const count = acknowledgedAlerts.size;
        if (dom.alertCount) {
            dom.alertCount.textContent = count;
            dom.alertCount.style.display = count > 0 ? "inline-block" : "none";
        }
    }

    function startClock() {
        function tick() {
            const now = new Date();
            dom.clock.textContent = now.toLocaleTimeString("en-US", {
                hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit",
            });
        }
        tick();
        setInterval(tick, 1000);
    }

    function setConnectionStatus(connected) {
        const el = dom.connStatus;
        if (connected) {
            el.className = "connection-status";
            el.innerHTML = '<span class="dot"></span> LIVE';
        } else {
            el.className = "connection-status disconnected";
            el.innerHTML = '<span class="dot"></span> OFFLINE';
        }
    }

    function handleSensorStatus(data) {
        let el = document.getElementById("sensor-ind-" + data.sensor_id);
        if (!el) {
            el = document.createElement("div");
            el.className = "sensor-indicator";
            el.id = "sensor-ind-" + data.sensor_id;
            el.innerHTML =
                '<span class="sensor-dot"></span><span class="sensor-label"></span>';
            dom.sensorIndicators.appendChild(el);
        }
        const dot = el.querySelector(".sensor-dot");
        const label = el.querySelector(".sensor-label");
        label.textContent = data.sensor_id;

        dot.className = "sensor-dot";
        const status = (data.status || "").toLowerCase();
        if (status === "scanning" || status === "online") {
            dot.classList.add("online");
            if (status === "scanning") dot.classList.add("scanning");
        }

        const camId = data.sensor_id;
        if (dom.cameraOverlay[camId]) {
            const overlay = dom.cameraOverlay[camId];
            const badge = overlay.querySelector(".status-badge");
            const zoneSub = overlay.querySelector(".zone-sub");
            if (badge) {
                badge.className = "status-badge " + status;
                badge.textContent = status.toUpperCase() || "IDLE";
            }
            if (zoneSub) {
                zoneSub.textContent = data.zone ? "Scanning: " + data.zone : "";
            }
        }
    }

    function handleCameraFrame(data) {
        var sid = data.sensor_id || "";
        var key = sid.toLowerCase();
        if (key.includes("back")) key = "back_rail";
        else if (key.includes("front")) key = "front_rail";
        var imgEl = dom.cameraImg[key] || dom.cameraImg[sid];
        if (imgEl && data.image) {
            imgEl.src = "data:image/jpeg;base64," + data.image;
            imgEl.style.display = "block";
            var placeholder = imgEl.parentElement.querySelector(".camera-placeholder");
            if (placeholder) placeholder.style.display = "none";
        }
    }

    function buildZoneGrid() {
        dom.zoneGrid.innerHTML = "";
        ZONE_DEFINITIONS.forEach((name, i) => {
            const card = document.createElement("div");
            card.className = "zone-card state-empty";
            card.id = "zone-card-" + i;
            if (name.includes("Lounge")) card.classList.add("dimmed");
            card.innerHTML = `
                <div class="zone-name">${name}</div>
                <div class="zone-count">0 <span style="font-size:.75rem;font-weight:400;color:var(--text-muted)">/ 0</span></div>
                <div class="zone-total">No data yet</div>
                <div class="zone-bar"><div class="zone-bar-fill" style="width:0%"></div></div>
            `;
            dom.zoneGrid.appendChild(card);
        });
    }

    function updateZoneCard(zoneName, zoneData) {
        const idx = ZONE_DEFINITIONS.findIndex(
            (z) => z.toLowerCase() === zoneName.toLowerCase() ||
                   z.toLowerCase().includes(zoneName.toLowerCase())
        );
        if (idx < 0) return;

        const card = document.getElementById("zone-card-" + idx);
        if (!card) return;

        const occupied = zoneData.occupied || 0;
        const total = zoneData.total || 0;

        let dominantState = "empty";
        if (zoneData.seats) {
            const counts = { empty: 0, occupied: 0, suspected: 0, ghost: 0 };
            const seatValues = typeof zoneData.seats === "object"
                ? Object.values(zoneData.seats) : zoneData.seats;
            seatValues.forEach((s) => {
                const st = s.state || "empty";
                if (counts[st] !== undefined) counts[st]++;
            });
            if (counts.ghost > 0)         dominantState = "ghost";
            else if (counts.suspected > 0) dominantState = "suspected";
            else if (counts.occupied > 0)  dominantState = "occupied";
        } else if (occupied > 0) {
            dominantState = "occupied";
        }

        card.className = "zone-card state-" + dominantState;
        if (ZONE_DEFINITIONS[idx].includes("Lounge")) card.classList.add("dimmed");

        const pct = total > 0 ? Math.round((occupied / total) * 100) : 0;

        card.querySelector(".zone-count").innerHTML =
            `${occupied} <span style="font-size:.75rem;font-weight:400;color:var(--text-muted)">/ ${total}</span>`;
        card.querySelector(".zone-total").textContent =
            `${pct}% occupied`;
        card.querySelector(".zone-bar-fill").style.width = pct + "%";
    }

    function buildSeatGrid() {
        dom.seatGrid.innerHTML = "";
        for (let i = 1; i <= TOTAL_SEATS; i++) {
            const dot = document.createElement("div");
            dot.className = "seat-dot empty";
            dot.id = "seat-" + i;
            dot.dataset.seatId = i;
            dot.textContent = i;

            dot.addEventListener("mouseenter", showTooltip);
            dot.addEventListener("mousemove", moveTooltip);
            dot.addEventListener("mouseleave", hideTooltip);
            dot.addEventListener("click", () => showSeatModal(i));

            dom.seatGrid.appendChild(dot);
        }
    }

    function updateSeatDot(seatId, seatData) {
        const numId = parseInt(String(seatId).replace(/\D/g, ""), 10);
        const dot = document.getElementById("seat-" + numId);
        if (!dot) return;

        const st = seatData.state || "empty";
        dot.className = "seat-dot " + st;
        dot.dataset.state = st;
        dot.dataset.presence = seatData.presence != null ? seatData.presence : "";
        dot.dataset.zone = seatData.zone || "";
    }

    function showTooltip(e) {
        const d = e.currentTarget.dataset;
        const tt = dom.tooltip;
        tt.innerHTML = `
            <div class="tt-id">Seat ${d.seatId}</div>
            <div class="tt-state" style="color:${STATE_COLORS[d.state] || '#94a3b8'}">
                ${(d.state || "unknown")}
            </div>
            <div class="tt-presence">Presence: ${d.presence || "N/A"}%</div>
            ${d.zone ? '<div style="color:var(--text-muted);margin-top:2px">' + d.zone + '</div>' : ""}
        `;
        tt.classList.add("visible");
        moveTooltip(e);
    }

    function moveTooltip(e) {
        dom.tooltip.style.left = (e.clientX + 14) + "px";
        dom.tooltip.style.top  = (e.clientY - 10) + "px";
    }

    function hideTooltip() {
        dom.tooltip.classList.remove("visible");
    }

    function buildRadarList() {
        dom.radarList.innerHTML = "";
        for (let i = 1; i <= TOTAL_SEATS; i++) {
            const row = document.createElement("div");
            row.className = "radar-row";
            row.id = "radar-row-" + i;
            row.innerHTML = `
                <span class="radar-label">S${String(i).padStart(2, "0")}</span>
                <div class="radar-bar-bg">
                    <div class="radar-bar-fill empty" style="width:0%"></div>
                </div>
                <span class="radar-value">0%</span>
            `;
            dom.radarList.appendChild(row);
        }
    }

    function updateRadarBar(seatId, seatData) {
        const numId = parseInt(String(seatId).replace(/\D/g, ""), 10);
        const row = document.getElementById("radar-row-" + numId);
        if (!row) return;

        const presence = parseFloat(seatData.presence) || 0;
        const st = seatData.state || "empty";
        const fill = row.querySelector(".radar-bar-fill");
        const val  = row.querySelector(".radar-value");

        fill.style.width = Math.min(presence, 100) + "%";
        fill.className = "radar-bar-fill " + st;
        val.textContent = Math.round(presence) + "%";
    }

    function handleGhostAlert(data) {
        alertCount++;

        // Check if acknowledged/snoozed
        if (acknowledgedAlerts.has(data.id)) {
            return; // Don't show snoozed alerts
        }

        const emptyMsg = dom.alertFeed.querySelector(".alert-empty");
        if (emptyMsg) emptyMsg.remove();

        const item = document.createElement("div");
        const alertType = data.type || "ghost";
        item.className = "alert-item type-" + alertType;
        item.dataset.alertId = data.id;

        const iconMap = {
            ghost:    "\u{1F47B}",
            ghost_suspected: "\u{1F47B}",
            ghost_confirmed: "\u{1F6A8}",
            warning:  "\u26A0\uFE0F",
            critical: "\u{1F6A8}",
            info:     "\u{2139}\uFE0F",
            person_returned: "\u{1F60A}",
            seat_cleared: "\u{1F60A}",
        };
        const icon = iconMap[alertType] || iconMap.ghost;

        const ts = data.timestamp
            ? new Date(data.timestamp).toLocaleTimeString("en-US", { hour12: false })
            : new Date().toLocaleTimeString("en-US", { hour12: false });

        const countdownHtml = data.countdown
            ? `<span class="alert-countdown" data-countdown="${data.countdown}">${data.countdown}s</span>`
            : "";

        item.innerHTML = `
            <div class="alert-icon">${icon}</div>
            <div class="alert-body">
                <div class="alert-message">${escapeHtml(data.message || "Ghost detected")}</div>
                <div class="alert-meta">
                    <span>${ts}</span>
                    ${data.seat_id ? "<span>Seat " + escapeHtml(String(data.seat_id)) + "</span>" : ""}
                    ${data.zone ? "<span>" + escapeHtml(data.zone) + "</span>" : ""}
                </div>
            </div>
            <div class="alert-actions">
                <button class="btn-ack" title="Acknowledge">&#x2714;</button>
                <button class="btn-snooze" title="Snooze 5min">&#x23F8;</button>
                <button class="btn-resolve" title="Resolve">&#x2716;</button>
            </div>
            ${countdownHtml}
        `;

        // Add event listeners for alert actions
        item.querySelector(".btn-ack")?.addEventListener("click", () => acknowledgeAlert(data.id));
        item.querySelector(".btn-snooze")?.addEventListener("click", () => snoozeAlert(data.id));
        item.querySelector(".btn-resolve")?.addEventListener("click", () => resolveAlert(data.id));

        dom.alertFeed.prepend(item);

        while (dom.alertFeed.children.length > ALERT_LIMIT) {
            dom.alertFeed.removeChild(dom.alertFeed.lastChild);
        }

        if (data.countdown) {
            startCountdown(item.querySelector(".alert-countdown"), data.countdown);
        }

        updateAlertCount();
    }

    function acknowledgeAlert(alertId) {
        fetch(`/api/alerts/${alertId}/acknowledge`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ user_id: "dashboard" }),
        })
            .then(r => r.json())
            .then(data => {
                if (data.status === "acknowledged") {
                    acknowledgedAlerts.add(alertId);
                    const alertEl = document.querySelector(`[data-alert-id="${alertId}"]`);
                    if (alertEl) {
                        alertEl.classList.add("acknowledged");
                    }
                    updateAlertCount();
                }
            })
            .catch(err => console.error("Failed to acknowledge alert:", err));
    }

    function snoozeAlert(alertId) {
        fetch(`/api/alerts/${alertId}/snooze`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ user_id: "dashboard", duration: 300 }),
        })
            .then(r => r.json())
            .then(data => {
                if (data.status === "snoozed") {
                    acknowledgedAlerts.add(alertId);
                    const alertEl = document.querySelector(`[data-alert-id="${alertId}"]`);
                    if (alertEl) {
                        alertEl.classList.add("snoozed");
                    }
                    updateAlertCount();
                }
            })
            .catch(err => console.error("Failed to snooze alert:", err));
    }

    function resolveAlert(alertId) {
        fetch(`/api/alerts/${alertId}/resolve`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ user_id: "dashboard" }),
        })
            .then(r => r.json())
            .then(data => {
                if (data.status === "resolved") {
                    acknowledgedAlerts.delete(alertId);
                    const alertEl = document.querySelector(`[data-alert-id="${alertId}"]`);
                    if (alertEl) {
                        alertEl.remove();
                    }
                    updateAlertCount();
                }
            })
            .catch(err => console.error("Failed to resolve alert:", err));
    }

    function startCountdown(el, seconds) {
        let remaining = seconds;
        const iv = setInterval(() => {
            remaining--;
            if (remaining <= 0) {
                clearInterval(iv);
                el.textContent = "EXPIRED";
                el.style.color = "var(--color-red)";
                return;
            }
            el.textContent = remaining + "s";
        }, 1000);
    }

    function initHistoryChart() {
        const ctx = dom.chartCanvas.getContext("2d");

        historyChart = new Chart(ctx, {
            type: "line",
            data: {
                labels: [],
                datasets: [
                    {
                        label: "Occupied",
                        data: [],
                        borderColor: "#ef4444",
                        backgroundColor: "rgba(239,68,68,.08)",
                        fill: true,
                        tension: 0.35,
                        pointRadius: 0,
                        borderWidth: 2,
                    },
                    {
                        label: "Empty",
                        data: [],
                        borderColor: "#22c55e",
                        backgroundColor: "rgba(34,197,94,.06)",
                        fill: true,
                        tension: 0.35,
                        pointRadius: 0,
                        borderWidth: 2,
                    },
                    {
                        label: "Ghost",
                        data: [],
                        borderColor: "#a855f7",
                        backgroundColor: "rgba(168,85,247,.06)",
                        fill: true,
                        tension: 0.35,
                        pointRadius: 0,
                        borderWidth: 2,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: "index",
                    intersect: false,
                },
                plugins: {
                    legend: {
                        display: true,
                        position: "top",
                        align: "end",
                        labels: {
                            color: "#94a3b8",
                            boxWidth: 10,
                            boxHeight: 10,
                            padding: 16,
                            font: { size: 11, family: "system-ui" },
                        },
                    },
                    tooltip: {
                        backgroundColor: "rgba(17,24,39,.95)",
                        titleColor: "#f1f5f9",
                        bodyColor: "#94a3b8",
                        borderColor: "#374151",
                        borderWidth: 1,
                        padding: 10,
                        cornerRadius: 8,
                        titleFont: { weight: "600" },
                    },
                },
                scales: {
                    x: {
                        grid: { color: "rgba(31,41,55,.5)", drawBorder: false },
                        ticks: {
                            color: "#64748b",
                            maxRotation: 0,
                            font: { size: 10 },
                            maxTicksLimit: 12,
                        },
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: "rgba(31,41,55,.5)", drawBorder: false },
                        ticks: {
                            color: "#64748b",
                            font: { size: 10 },
                            stepSize: 1,
                        },
                    },
                },
                animation: {
                    duration: 400,
                },
            },
        });
    }

    function addHistoryPoint(point) {
        if (!historyChart) return;
        const labels = historyChart.data.labels;
        const ts = new Date(point.ts).toLocaleTimeString("en-US", {
            hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit",
        });

        labels.push(ts);
        historyChart.data.datasets[0].data.push(point.occupied || 0);
        historyChart.data.datasets[1].data.push(point.empty || 0);
        historyChart.data.datasets[2].data.push(point.ghost || 0);

        if (labels.length > HISTORY_POINTS_MAX) {
            labels.shift();
            historyChart.data.datasets.forEach((ds) => ds.data.shift());
        }

        historyChart.update("none");
    }

    function handleHistoryData(data) {
        if (!historyChart || !Array.isArray(data)) return;
        historyChart.data.labels = [];
        historyChart.data.datasets.forEach((ds) => (ds.data = []));

        data.forEach((point) => {
            const ts = new Date(point.ts).toLocaleTimeString("en-US", {
                hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit",
            });
            historyChart.data.labels.push(ts);
            historyChart.data.datasets[0].data.push(point.occupied || 0);
            historyChart.data.datasets[1].data.push(point.empty || 0);
            historyChart.data.datasets[2].data.push(point.ghost || 0);
        });

        historyChart.update();
    }

    function handleTelemetry(data) {
        if (data.zone && data.zone_data) {
            zones[data.zone] = data.zone_data;
            updateZoneCard(data.zone, data.zone_data);
            if (heatmapMode) updateHeatmap();
        }
        if (data.stats) {
            handleStats(data.stats);
        }

        if (data.stats) {
            addHistoryPoint({
                ts: new Date().toISOString(),
                occupied: data.stats.occupied || 0,
                empty: data.stats.empty || 0,
                ghost: data.stats.ghost || 0,
            });
        }
    }

    function handleSeatState(data) {
        if (!data.seats) return;
        seats = data.seats;
        Object.entries(seats).forEach(([id, sdata]) => {
            updateSeatDot(id, sdata);
            updateRadarBar(id, sdata);
        });
    }

    function handleStats(data) {
        if (!data) return;
        animateNumber(dom.statOccupied, data.occupied || 0);
        animateNumber(dom.statEmpty, data.empty || 0);
        animateNumber(dom.statGhost, data.ghost || 0);
        animateNumber(dom.statScans, data.total_scans || 0);
        dom.statUtil.textContent = (data.utilization || 0).toFixed(1) + "%";
    }

    function animateNumber(el, target) {
        const current = parseInt(el.textContent, 10) || 0;
        if (current === target) return;
        el.textContent = target;
        el.style.transform = "scale(1.15)";
        setTimeout(() => { el.style.transform = "scale(1)"; }, 200);
    }

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }

})();
