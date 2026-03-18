/* ================================================================
   Agentic Vault Setup Wizard -- Frontend Logic
   ================================================================ */

const App = {
    currentScreen: "welcome",
    selectedServices: [],
    serviceQueue: [],
    serviceIndex: 0,
    state: {},

    slackTeamId: "",
    slackUserId: "",

    /* ----------------------------------------------------------------
       Initialization
       ---------------------------------------------------------------- */

    async init() {
        try {
            const resp = await this.api("GET", "/api/status");
            this.state = resp;
        } catch (_) {
            /* server may not be ready yet */
        }
        this.renderProgress();
    },

    /* ----------------------------------------------------------------
       API helper
       ---------------------------------------------------------------- */

    async api(method, path, body) {
        const opts = {
            method,
            headers: { "Content-Type": "application/json" },
        };
        if (body !== undefined && body !== null) {
            opts.body = JSON.stringify(body);
        }
        const resp = await fetch(path, opts);
        const data = await resp.json();
        if (!resp.ok && data.error) {
            throw new Error(data.error);
        }
        return data;
    },

    /* ----------------------------------------------------------------
       Screen navigation
       ---------------------------------------------------------------- */

    goTo(screenId) {
        const cur = document.getElementById("screen-" + this.currentScreen);
        const nxt = document.getElementById("screen-" + screenId);
        if (cur) cur.hidden = true;
        if (nxt) nxt.hidden = false;
        this.currentScreen = screenId;
        this.renderProgress();
        window.scrollTo({ top: 0, behavior: "smooth" });
    },

    goToNextService() {
        this.serviceIndex++;
        if (this.serviceIndex < this.serviceQueue.length) {
            this.goTo(this.serviceQueue[this.serviceIndex]);
        } else {
            this.goTo("summary");
            this.loadSummary();
        }
    },

    /* ----------------------------------------------------------------
       Service picker
       ---------------------------------------------------------------- */

    confirmServices() {
        const checks = document.querySelectorAll(
            'input[name="service"]:checked'
        );
        this.selectedServices = Array.from(checks).map(function (c) {
            return c.value;
        });
        this.serviceQueue = this.selectedServices.slice();
        this.serviceIndex = 0;
        if (this.serviceQueue.length > 0) {
            this.goTo(this.serviceQueue[0]);
        } else {
            this.goTo("summary");
            this.loadSummary();
        }
    },

    /* ----------------------------------------------------------------
       Progress bar
       ---------------------------------------------------------------- */

    renderProgress() {
        var bar = document.getElementById("progress-bar");
        var total = 2 + this.serviceQueue.length + 1;
        var currentIdx = 0;

        if (this.currentScreen === "welcome") {
            currentIdx = 0;
        } else if (this.currentScreen === "service-picker") {
            currentIdx = 1;
        } else if (this.currentScreen === "summary") {
            currentIdx = total - 1;
        } else {
            currentIdx = 2 + this.serviceIndex;
        }

        bar.innerHTML = "";
        for (var i = 0; i < total; i++) {
            var step = document.createElement("div");
            step.className = "progress-step";
            if (i < currentIdx) step.classList.add("completed");
            if (i === currentIdx) step.classList.add("current");
            bar.appendChild(step);
        }
    },

    /* ----------------------------------------------------------------
       Todoist
       ---------------------------------------------------------------- */

    async saveTodoist() {
        var token = document.getElementById("todoist-token").value;
        var errorEl = document.getElementById("todoist-error");
        var resultEl = document.getElementById("todoist-result");
        errorEl.textContent = "";
        resultEl.textContent = "";
        resultEl.className = "result-message";

        if (!token.trim()) {
            errorEl.textContent = "Please paste your token.";
            return;
        }

        try {
            var resp = await this.api("POST", "/api/todoist/save-token", {
                token: token,
            });
            if (resp.valid) {
                resultEl.textContent = resp.message;
                resultEl.classList.add("success");
                document.getElementById("todoist-token").classList.remove("error");
                setTimeout(() => this.goToNextService(), 1500);
            } else {
                errorEl.textContent = resp.message;
                document.getElementById("todoist-token").classList.add("error");
            }
        } catch (err) {
            errorEl.textContent = err.message;
        }
    },

    /* ----------------------------------------------------------------
       Telegram
       ---------------------------------------------------------------- */

    async verifyTelegramToken() {
        var token = document.getElementById("telegram-token").value;
        var errorEl = document.getElementById("telegram-token-error");
        errorEl.textContent = "";

        if (!token.trim()) {
            errorEl.textContent = "Please paste your bot token.";
            return;
        }

        try {
            var resp = await this.api("POST", "/api/telegram/verify-token", {
                bot_token: token,
            });
            if (resp.valid) {
                document.getElementById("telegram-verified").hidden = false;
                document.getElementById("telegram-bot-info").textContent =
                    resp.message;
                document.getElementById("telegram-bot-info").className =
                    "result-message success";
            } else {
                errorEl.textContent = resp.message;
            }
        } catch (err) {
            errorEl.textContent = err.message;
        }
    },

    async detectTelegramIds() {
        var token = document.getElementById("telegram-token").value;
        var resultEl = document.getElementById("telegram-result");
        resultEl.textContent = "";
        resultEl.className = "result-message";

        try {
            var resp = await this.api("POST", "/api/telegram/detect-ids", {
                bot_token: token,
            });
            if (resp.found) {
                document.getElementById("telegram-ids").hidden = false;
                document.getElementById("telegram-user-id").textContent =
                    resp.user_id;
                document.getElementById("telegram-chat-id").textContent =
                    resp.chat_id;
            } else {
                resultEl.textContent = resp.message;
                resultEl.classList.add("error");
            }
        } catch (err) {
            resultEl.textContent = err.message;
            resultEl.classList.add("error");
        }
    },

    async saveTelegram() {
        var token = document.getElementById("telegram-token").value;
        var userId = document.getElementById("telegram-user-id").textContent;
        var chatId = document.getElementById("telegram-chat-id").textContent;
        var resultEl = document.getElementById("telegram-result");
        resultEl.textContent = "";
        resultEl.className = "result-message";

        try {
            var resp = await this.api("POST", "/api/telegram/save-config", {
                bot_token: token,
                user_id: userId,
                chat_id: chatId,
            });
            if (resp.valid) {
                resultEl.textContent = resp.message;
                resultEl.classList.add("success");
                setTimeout(() => this.goToNextService(), 1500);
            } else {
                resultEl.textContent = resp.message;
                resultEl.classList.add("error");
            }
        } catch (err) {
            resultEl.textContent = err.message;
            resultEl.classList.add("error");
        }
    },

    /* ----------------------------------------------------------------
       Google (6-step flow)
       ---------------------------------------------------------------- */

    googleStep(n) {
        for (var i = 1; i <= 6; i++) {
            var el = document.getElementById("google-step-" + i);
            if (el) el.hidden = i !== n;
        }
    },

    initGoogleUpload() {
        var zone = document.getElementById("google-upload-zone");
        var input = document.getElementById("google-file-input");
        if (!zone || !input) return;

        zone.addEventListener("click", function () {
            input.click();
        });
        zone.addEventListener("dragover", function (e) {
            e.preventDefault();
            zone.classList.add("dragover");
        });
        zone.addEventListener("dragleave", function () {
            zone.classList.remove("dragover");
        });
        zone.addEventListener("drop", (e) => {
            e.preventDefault();
            zone.classList.remove("dragover");
            if (e.dataTransfer.files.length) {
                this.handleGoogleFile(e.dataTransfer.files[0]);
            }
        });
        input.addEventListener("change", () => {
            if (input.files.length) {
                this.handleGoogleFile(input.files[0]);
            }
        });
    },

    handleGoogleFile(file) {
        var reader = new FileReader();
        reader.onload = async (e) => {
            var content = e.target.result;
            var status = document.getElementById("google-upload-status");
            try {
                var resp = await this.api(
                    "POST",
                    "/api/google/upload-credentials",
                    { client_json: content, accounts: ["private"] }
                );
                if (resp.valid) {
                    status.innerHTML =
                        '<div class="result-message success">' +
                        resp.message +
                        "</div>";
                    document.getElementById(
                        "google-accounts-section"
                    ).hidden = false;
                    this.renderGoogleSignInButtons();
                } else {
                    status.innerHTML =
                        '<div class="result-message error">' +
                        resp.message +
                        "</div>";
                }
            } catch (err) {
                status.innerHTML =
                    '<div class="result-message error">' +
                    err.message +
                    "</div>";
            }
        };
        reader.readAsText(file);
    },

    renderGoogleSignInButtons() {
        var container = document.getElementById("google-signin-buttons");
        var radios = document.querySelectorAll(
            'input[name="google-accounts"]'
        );

        var render = () => {
            var count = 1;
            radios.forEach(function (r) {
                if (r.checked) count = parseInt(r.value, 10);
            });

            var accounts =
                count === 1 ? ["private"] : ["private", "personal"];
            var services = ["gcal", "gmail"];
            var labels = { gcal: "Google Calendar", gmail: "Gmail" };

            var html = "";
            for (var s = 0; s < services.length; s++) {
                for (var a = 0; a < accounts.length; a++) {
                    var svc = services[s];
                    var acct = accounts[a];
                    var label =
                        labels[svc] +
                        (accounts.length > 1
                            ? " (" + acct + ")"
                            : "");
                    html +=
                        '<button class="btn-secondary" style="margin-right:8px" ' +
                        'onclick="App.startGoogleAuth(\'' +
                        svc +
                        "', '" +
                        acct +
                        "')\">" +
                        "Sign in: " +
                        label +
                        "</button>";
                }
            }
            html +=
                '<br><button class="btn-primary" style="margin-top:16px" ' +
                'onclick="App.goToNextService()">Continue</button>';
            container.innerHTML = html;
        };

        radios.forEach(function (r) {
            r.addEventListener("change", render);
        });
        render();
    },

    async startGoogleAuth(service, account) {
        try {
            var resp = await this.api("POST", "/api/google/start-auth", {
                service: service,
                account: account,
            });
            if (resp.success) {
                var btn = event.target;
                btn.textContent = "Connected";
                btn.disabled = true;
                btn.style.opacity = "0.6";
            } else {
                alert("Google auth error: " + (resp.error || "Unknown error"));
            }
        } catch (err) {
            alert("Google auth error: " + err.message);
        }
    },

    /* ----------------------------------------------------------------
       Fireflies
       ---------------------------------------------------------------- */

    async saveFireflies() {
        var key = document.getElementById("fireflies-key").value;
        var errorEl = document.getElementById("fireflies-error");
        var resultEl = document.getElementById("fireflies-result");
        errorEl.textContent = "";
        resultEl.textContent = "";
        resultEl.className = "result-message";

        if (!key.trim()) {
            errorEl.textContent = "Please paste your API key.";
            return;
        }

        try {
            var resp = await this.api("POST", "/api/fireflies/save-key", {
                key: key,
            });
            if (resp.valid) {
                resultEl.textContent = resp.message;
                resultEl.classList.add("success");
                setTimeout(() => this.goToNextService(), 1500);
            } else {
                errorEl.textContent = resp.message;
            }
        } catch (err) {
            errorEl.textContent = err.message;
        }
    },

    /* ----------------------------------------------------------------
       Clockify
       ---------------------------------------------------------------- */

    async saveClockify() {
        var key = document.getElementById("clockify-key").value;
        var errorEl = document.getElementById("clockify-error");
        var resultEl = document.getElementById("clockify-result");
        errorEl.textContent = "";
        resultEl.textContent = "";
        resultEl.className = "result-message";

        if (!key.trim()) {
            errorEl.textContent = "Please paste your API key.";
            return;
        }

        try {
            var resp = await this.api("POST", "/api/clockify/save-key", {
                key: key,
            });
            if (resp.valid) {
                resultEl.textContent = resp.message;
                resultEl.classList.add("success");
                setTimeout(() => this.goToNextService(), 1500);
            } else {
                errorEl.textContent = resp.message;
            }
        } catch (err) {
            errorEl.textContent = err.message;
        }
    },

    /* ----------------------------------------------------------------
       Slack
       ---------------------------------------------------------------- */

    slackStep(n) {
        for (var i = 1; i <= 4; i++) {
            var el = document.getElementById("slack-step-" + i);
            if (el) el.hidden = i !== n;
        }
    },

    async testSlack() {
        var token = document.getElementById("slack-token").value;
        var alias = document.getElementById("slack-alias").value;
        var errorEl = document.getElementById("slack-token-error");
        var resultEl = document.getElementById("slack-test-result");
        errorEl.textContent = "";
        resultEl.textContent = "";
        resultEl.className = "result-message";

        if (!token.trim()) {
            errorEl.textContent = "Please paste your bot token.";
            return;
        }

        try {
            var resp = await this.api("POST", "/api/slack/save-token", {
                token: token,
                alias: alias,
            });
            if (resp.valid) {
                resultEl.textContent = resp.message;
                resultEl.classList.add("success");
                this.slackTeamId = resp.team_id || "";
                this.slackUserId = resp.user_id || "";
                setTimeout(() => this.slackStep(4), 1000);
            } else {
                resultEl.textContent = resp.message;
                resultEl.classList.add("error");
            }
        } catch (err) {
            resultEl.textContent = err.message;
            resultEl.classList.add("error");
        }
    },

    async loadSlackChannels() {
        var container = document.getElementById("slack-channel-list");
        container.innerHTML = '<span class="spinner"></span> Loading channels...';

        try {
            var resp = await this.api("GET", "/api/slack/list-conversations");
            if (resp.ok) {
                this.renderSlackChannels(resp.channels);
            } else {
                container.innerHTML =
                    '<div class="result-message error">Could not load channels: ' +
                    (resp.error || "unknown") +
                    "</div>";
            }
        } catch (err) {
            container.innerHTML =
                '<div class="result-message error">' +
                err.message +
                "</div>";
        }
    },

    renderSlackChannels(channels) {
        var container = document.getElementById("slack-channel-list");
        if (!channels.length) {
            container.innerHTML =
                '<p class="muted">No channels found. Make sure the bot is added to at least one channel.</p>';
            return;
        }
        container.innerHTML = channels
            .map(function (ch) {
                return (
                    '<label class="service-option">' +
                    '<input type="checkbox" name="slack-channel" value="' +
                    ch.id +
                    '" data-name="' +
                    ch.name +
                    '" data-type="' +
                    ch.type +
                    '">' +
                    '<div class="service-info">' +
                    '<span class="service-name">#' +
                    ch.name +
                    "</span>" +
                    '<span class="service-desc">' +
                    ch.type +
                    "</span>" +
                    "</div></label>"
                );
            })
            .join("");
    },

    async saveSlackConfig() {
        var alias = document.getElementById("slack-alias").value;
        var checks = document.querySelectorAll(
            'input[name="slack-channel"]:checked'
        );
        var conversations = Array.from(checks).map(function (c) {
            return {
                id: c.value,
                name: c.dataset.name,
                type: c.dataset.type,
                retention_class: "work",
                allow_file_download: false,
            };
        });

        var config = {
            workspaces: [
                {
                    alias: alias,
                    team_id: this.slackTeamId,
                    token_file:
                        "90_System/secrets/slack_token_" + alias + ".txt",
                    jan_user_ids: this.slackUserId
                        ? [this.slackUserId]
                        : [],
                    download: {
                        enabled: false,
                        max_bytes: 26214400,
                        allowed_extensions: [
                            ".csv", ".docx", ".jpg", ".md", ".pdf",
                            ".png", ".pptx", ".txt", ".xlsx",
                        ],
                    },
                    allow_conversations: conversations,
                },
            ],
        };

        var resultEl = document.getElementById("slack-config-result");
        resultEl.textContent = "";
        resultEl.className = "result-message";

        try {
            var resp = await this.api("POST", "/api/slack/save-config", {
                config: config,
            });
            if (resp.saved) {
                resultEl.textContent = "Slack configuration saved.";
                resultEl.classList.add("success");
                setTimeout(() => this.goToNextService(), 1500);
            }
        } catch (err) {
            resultEl.textContent = err.message;
            resultEl.classList.add("error");
        }
    },

    /* ----------------------------------------------------------------
       Summary / Dashboard
       ---------------------------------------------------------------- */

    async loadSummary() {
        try {
            var resp = await this.api("GET", "/api/status");
            var prereqs = await this.api("GET", "/api/prerequisites");
            this.state = resp;

            var grid = document.getElementById("status-grid");
            var services = [
                { key: "gcal_private_authed", name: "Google Calendar" },
                { key: "gmail_private_authed", name: "Gmail" },
                { key: "todoist_connected", name: "Todoist" },
                { key: "telegram_connected", name: "Telegram Bridge" },
                { key: "fireflies_connected", name: "Fireflies" },
                { key: "clockify_connected", name: "Clockify" },
                { key: "slack_connected", name: "Slack" },
            ];

            var selected = this.selectedServices;
            grid.innerHTML = services
                .map(function (s) {
                    var connected = resp[s.key];
                    var svcKey = s.name.toLowerCase().split(" ")[0];
                    var isSelected = selected.indexOf(svcKey) !== -1;
                    var badge, cls;
                    if (connected) {
                        badge = "Connected";
                        cls = "connected";
                    } else if (!isSelected) {
                        badge = "Skipped";
                        cls = "skipped";
                    } else {
                        badge = "Not Set Up";
                        cls = "not-connected";
                    }
                    return (
                        '<div class="status-row">' +
                        "<span>" + s.name + "</span>" +
                        '<span class="status-badge ' + cls + '">' +
                        badge +
                        "</span></div>"
                    );
                })
                .join("");

            document.getElementById("vault-path").textContent =
                prereqs.repo_root;
        } catch (_) {
            /* best-effort */
        }
    },

    /* ----------------------------------------------------------------
       Shutdown
       ---------------------------------------------------------------- */

    async shutdown() {
        try {
            await this.api("POST", "/api/shutdown");
        } catch (_) {
            /* expected: server shuts down */
        }
        document.body.innerHTML =
            '<div style="text-align:center;padding:80px">' +
            "<h2>Setup wizard closed.</h2>" +
            "<p>You can close this tab.</p></div>";
    },

    /* ----------------------------------------------------------------
       Clipboard helper
       ---------------------------------------------------------------- */

    copyManifest() {
        var code = document.getElementById("slack-manifest-code").textContent;
        if (navigator.clipboard) {
            navigator.clipboard.writeText(code);
        }
    },
};

/* ----------------------------------------------------------------
   Boot
   ---------------------------------------------------------------- */

document.addEventListener("DOMContentLoaded", function () {
    App.init();
    App.initGoogleUpload();
});
