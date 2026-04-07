const App = {
    currentScreen: "welcome",
    selectedServices: [],
    serviceQueue: [],
    serviceIndex: 0,
    state: {},
    assistantStatus: null,
    assistantInstallChoice: "",
    browserStatus: null,
    localAIStatus: null,
    localAIHardware: null,
    slackTeamId: "",
    slackUserId: "",
    googleFiles: { private: null, personal: null },
    initialLoadServices: [],

    async init() {
        try {
            this.state = await this.api("GET", "/api/status");
        } catch (_) {}
        await this.refreshAssistantStatus();
        await this.refreshBrowserStatus();
        await this.refreshLocalAIStatus();
        this.initGoogleUpload();
        this.renderProgress();
    },

    async api(method, path, body) {
        const opts = { method, headers: { "Content-Type": "application/json" } };
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

    goTo(screenId) {
        const cur = document.getElementById("screen-" + this.currentScreen);
        const nxt = document.getElementById("screen-" + screenId);
        if (cur) cur.hidden = true;
        if (nxt) nxt.hidden = false;
        this.currentScreen = screenId;
        this.renderProgress();
        if (screenId === "local-ai") {
            this.prepareLocalAIScreen();
        }
        window.scrollTo({ top: 0, behavior: "smooth" });
    },

    async goToNextService() {
        this.serviceIndex += 1;
        if (this.serviceIndex < this.serviceQueue.length) {
            this.goTo(this.serviceQueue[this.serviceIndex]);
            return;
        }
        await this.refreshWizardState();
        if (this.shouldOfferInitialLoad()) {
            this.prepareInitialLoadScreen();
            this.goTo("initial-load");
        } else {
            this.goTo("summary");
            this.loadSummary();
        }
    },

    confirmServices() {
        if (this.assistantStatus && this.assistantStatus.supported && !this.assistantStatus.installed_any) {
            return;
        }
        const checks = document.querySelectorAll('input[name="service"]:checked');
        this.selectedServices = Array.from(checks).map(function (c) { return c.value; });
        this.serviceQueue = this.selectedServices.filter(function (item) { return item !== "local-ai"; });
        if (this.selectedServices.indexOf("local-ai") !== -1) {
            this.serviceQueue.push("local-ai");
        }
        this.serviceIndex = 0;
        if (this.serviceQueue.length > 0) {
            this.goTo(this.serviceQueue[0]);
        } else {
            this.goTo("summary");
            this.loadSummary();
        }
    },

    async refreshAssistantStatus() {
        try {
            this.assistantStatus = await this.api("GET", "/api/assistant/status");
        } catch (_) {
            this.assistantStatus = null;
        }
        this.renderAssistantStatus();
    },

    async refreshBrowserStatus() {
        try {
            this.browserStatus = await this.api("GET", "/api/browser/status");
        } catch (_) {
            this.browserStatus = null;
        }
    },

    async refreshLocalAIStatus() {
        try {
            this.localAIStatus = await this.api("GET", "/api/local-ai/status");
        } catch (_) {
            this.localAIStatus = null;
        }
    },

    async refreshWizardState() {
        try {
            this.state = await this.api("GET", "/api/status");
        } catch (_) {}
    },

    initialLoadCapabilities() {
        var googleAccounts = this.state.google_accounts && this.state.google_accounts.length ? this.state.google_accounts : [];
        var meetingsReady = googleAccounts.some((account) => !!this.state["gcal_" + account + "_authed"]);
        var emailsReady = googleAccounts.some((account) => !!this.state["gmail_" + account + "_authed"]);
        return {
            meetings: meetingsReady,
            emails: emailsReady,
            messages: !!this.state.slack_connected,
            tasks: !!this.state.todoist_connected,
        };
    },

    renderAssistantStatus(message, isError) {
        var box = document.getElementById("assistant-setup");
        var statusEl = document.getElementById("assistant-status");
        var resultEl = document.getElementById("assistant-install-result");
        var installBtn = document.getElementById("assistant-install-btn");
        var startBtn = document.getElementById("welcome-start-btn");
        var choiceList = document.getElementById("assistant-choice-list");
        var choiceHelp = document.getElementById("assistant-choice-help");
        if (!box || !statusEl || !resultEl || !installBtn || !startBtn || !choiceList || !choiceHelp) return;

        if (!this.assistantStatus || !this.assistantStatus.supported) {
            box.hidden = true;
            startBtn.disabled = false;
            return;
        }

        box.hidden = false;
        var assistants = this.assistantStatus.assistants || [];
        var installed = assistants.filter(function (item) { return item.installed; });
        if (installed.length) {
            statusEl.innerHTML = "<strong>Coding assistant ready.</strong> " + installed.map(function (item) { return item.label; }).join(" / ") + " is installed on this machine.";
            choiceList.hidden = true;
            choiceHelp.hidden = true;
            installBtn.hidden = true;
            installBtn.disabled = true;
            startBtn.disabled = false;
            this.assistantInstallChoice = this.assistantStatus.preferred || installed[0].key;
        } else {
            statusEl.innerHTML = "<strong>Choose a coding assistant.</strong> None of OpenAI Codex, Claude Code, Gemini CLI, or OpenCode is installed yet.";
            if (!this.assistantInstallChoice || !assistants.some((item) => item.key === this.assistantInstallChoice)) {
                this.assistantInstallChoice = "";
            }
            this.renderAssistantChoices();
            choiceList.hidden = false;
            choiceHelp.hidden = false;
            installBtn.hidden = false;
            installBtn.disabled = !this.assistantInstallChoice;
            startBtn.disabled = true;
        }

        if (message) {
            resultEl.textContent = message;
            resultEl.className = "result-message " + (isError ? "error" : "success");
        } else if (!installed.length) {
            resultEl.textContent = "";
            resultEl.className = "result-message";
        }
    },

    renderAssistantChoices() {
        var choiceList = document.getElementById("assistant-choice-list");
        var installBtn = document.getElementById("assistant-install-btn");
        if (!choiceList || !this.assistantStatus) return;
        var assistants = this.assistantStatus.assistants || [];
        choiceList.innerHTML = assistants.map((item) => {
            var selected = this.assistantInstallChoice === item.key;
            return '<label class="assistant-option ' + (selected ? 'selected' : '') + '">' +
                '<div class="assistant-option-header">' +
                '<input type="radio" name="assistant-choice" value="' + item.key + '" ' + (selected ? 'checked' : '') + ' onchange="App.selectAssistantChoice(\'' + item.key + '\')">' +
                '<span>' + item.label + '</span>' +
                '</div>' +
                '<div class="assistant-option-body">' +
                '<span><strong>Minimum access:</strong> ' + item.minimum_access + '</span>' +
                '<span><strong>After install:</strong> ' + item.login_hint + '</span>' +
                '<span><a href="' + item.purchase_url + '" target="_blank" rel="noopener noreferrer">Where to get access: ' + item.purchase_label + '</a></span>' +
                '</div>' +
                '</label>';
        }).join('');
        if (installBtn) {
            installBtn.disabled = !this.assistantInstallChoice;
        }
    },

    selectAssistantChoice(key) {
        this.assistantInstallChoice = key;
        this.renderAssistantChoices();
    },

    async installAssistant() {
        var installBtn = document.getElementById("assistant-install-btn");
        var selected = this.assistantInstallChoice;
        if (!selected) {
            this.renderAssistantStatus("Select which coding assistant you want to install first.", true);
            return;
        }
        var selectedLabel = selected;
        if (this.assistantStatus && this.assistantStatus.assistants) {
            var meta = this.assistantStatus.assistants.find(function (item) { return item.key === selected; });
            if (meta) selectedLabel = meta.label;
        }
        if (installBtn) {
            installBtn.disabled = true;
            installBtn.textContent = "Installing...";
        }
        this.renderAssistantStatus("Installing " + selectedLabel + ". This can take a minute.", false);
        try {
            var resp = await this.api("POST", "/api/assistant/install", { assistant: selected });
            this.assistantStatus = resp.status || (await this.api("GET", "/api/assistant/status"));
            this.renderAssistantStatus(resp.message, !resp.ok);
        } catch (err) {
            this.renderAssistantStatus(err.message, true);
        } finally {
            if (installBtn) {
                installBtn.disabled = false;
                installBtn.textContent = "Install Selected Assistant";
            }
        }
    },

    async installBrowserPlugin() {
        var installBtn = document.getElementById("browser-install-btn");
        var resultEl = document.getElementById("browser-install-result");
        resultEl.textContent = "";
        resultEl.className = "result-message";
        if (installBtn) {
            installBtn.disabled = true;
            installBtn.textContent = "Installing...";
        }
        resultEl.textContent = "Installing Playwright Browser plugin and Chromium. This can take a few minutes.";
        try {
            var resp = await this.api("POST", "/api/browser/install", {});
            this.browserStatus = resp.status || (await this.api("GET", "/api/browser/status"));
            resultEl.textContent = resp.message;
            resultEl.classList.add(resp.ok ? "success" : "error");
            if (resp.ok) {
                await this.refreshWizardState();
                setTimeout(() => this.goToNextService(), 1500);
            }
        } catch (err) {
            resultEl.textContent = err.message;
            resultEl.classList.add("error");
        } finally {
            if (installBtn) {
                installBtn.disabled = false;
                installBtn.textContent = "Install Playwright Browser";
            }
        }
    },

    async prepareLocalAIScreen() {
        await this.refreshLocalAIStatus();
        this.renderLocalAIStatus();
        if (this.localAIHardware) {
            this.renderLocalAIHardware(this.localAIHardware);
        } else if (this.localAIStatus && this.localAIStatus.recommendation) {
            var recommendationBox = document.getElementById("local-ai-recommendation");
            var recommendation = this.localAIStatus.recommendation;
            if (recommendationBox) {
                recommendationBox.innerHTML = '<div class="recommendation-badge ' + recommendation.tier + '">' + recommendation.headline + '</div>' +
                    '<p>' + recommendation.details + '</p>' +
                    '<p><strong>Suggested starting model:</strong> ' + recommendation.recommended_model + '</p>';
            }
            var chosenModelInput = document.getElementById("local-ai-chosen-model-label");
            if (chosenModelInput && !chosenModelInput.dataset.userEdited) {
                chosenModelInput.value = recommendation.recommended_model || "Gemma Local";
            }
        }
    },

    localAIRecommendationFromHardware(hardware) {
        return hardware && hardware.recommendation ? hardware.recommendation : (this.localAIStatus ? this.localAIStatus.recommendation : null);
    },

    renderLocalAIStatus(message, isError) {
        var opencodeStatus = document.getElementById("local-ai-opencode-status");
        var configStatus = document.getElementById("local-ai-config-status");
        var paths = document.getElementById("local-ai-config-paths");
        var installBtn = document.getElementById("local-ai-opencode-install-btn");
        if (opencodeStatus && this.localAIStatus && this.localAIStatus.opencode) {
            if (this.localAIStatus.opencode.installed) {
                opencodeStatus.textContent = "OpenCode is already installed on this machine.";
                opencodeStatus.className = "result-message success";
                if (installBtn) installBtn.disabled = true;
            } else {
                opencodeStatus.textContent = "OpenCode is not installed yet.";
                opencodeStatus.className = "result-message";
                if (installBtn) installBtn.disabled = false;
            }
        }
        if (configStatus && this.localAIStatus) {
            if (this.localAIStatus.opencode_configured) {
                configStatus.textContent = "An LM Studio provider config was detected for OpenCode.";
                configStatus.className = "result-message success";
            } else {
                configStatus.textContent = "";
                configStatus.className = "result-message";
            }
        }
        if (paths && this.localAIStatus && this.localAIStatus.config_paths) {
            paths.textContent = "Global: " + this.localAIStatus.config_paths.global + "\nProject: " + this.localAIStatus.config_paths.project;
        }
        if (message) {
            var resultEl = document.getElementById("local-ai-general-result");
            if (resultEl) {
                resultEl.textContent = message;
                resultEl.className = "result-message " + (isError ? "error" : "success");
            }
        }
    },

    renderLocalAIHardware(hardware) {
        var box = document.getElementById("local-ai-hardware-result");
        var recommendationBox = document.getElementById("local-ai-recommendation");
        var recommendation = this.localAIRecommendationFromHardware(hardware);
        if (box) {
            var gpuText = (hardware.gpus || []).length ? hardware.gpus.map(function (gpu) {
                var suffix = gpu.vram_gb ? " (" + gpu.vram_gb + " GB VRAM)" : "";
                return gpu.name + suffix;
            }).join(", ") : "No dedicated GPU details detected";
            var details = [
                "OS: " + hardware.os,
                "Architecture: " + hardware.arch,
                "Memory: " + (hardware.memory_gb ? hardware.memory_gb + " GB" : "Unknown"),
                "GPU: " + gpuText,
            ];
            if (hardware.os === "windows") {
                details.push("WSL available: " + (hardware.wsl_available ? "Yes" : "No"));
            }
            if (hardware.detection_warning) {
                details.push("Note: " + hardware.detection_warning);
            }
            box.textContent = details.join("\n");
            box.className = "result-message success";
        }
        if (recommendationBox && recommendation) {
            recommendationBox.innerHTML = '<div class="recommendation-badge ' + recommendation.tier + '">' + recommendation.headline + '</div>' +
                '<p>' + recommendation.details + '</p>' +
                '<p><strong>Suggested starting model:</strong> ' + recommendation.recommended_model + '</p>' +
                ((recommendation.warnings || []).length ? '<p class="muted">' + recommendation.warnings.join(" ") + '</p>' : '');
        }
        var chosenModelInput = document.getElementById("local-ai-chosen-model-label");
        if (chosenModelInput && recommendation && !chosenModelInput.dataset.userEdited) {
            chosenModelInput.value = recommendation.recommended_model || "Gemma Local";
        }
    },

    async scanLocalAIHardware() {
        var btn = document.getElementById("local-ai-scan-btn");
        if (btn) {
            btn.disabled = true;
            btn.textContent = "Scanning...";
        }
        try {
            this.localAIHardware = await this.api("GET", "/api/local-ai/hardware");
            await this.refreshWizardState();
            await this.refreshLocalAIStatus();
            this.renderLocalAIHardware(this.localAIHardware);
            this.renderLocalAIStatus();
        } catch (err) {
            this.renderLocalAIStatus(err.message, true);
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = "Scan My Hardware";
            }
        }
    },

    async installLocalAIOpenCode() {
        var btn = document.getElementById("local-ai-opencode-install-btn");
        if (btn) {
            btn.disabled = true;
            btn.textContent = "Installing...";
        }
        try {
            var resp = await this.api("POST", "/api/local-ai/opencode/install", {});
            this.localAIStatus = await this.api("GET", "/api/local-ai/status");
            this.renderLocalAIStatus(resp.message, !resp.ok);
        } catch (err) {
            this.renderLocalAIStatus(err.message, true);
        } finally {
            if (btn) {
                btn.textContent = "Install OpenCode";
            }
        }
    },

    async checkLocalAIServer() {
        var btn = document.getElementById("local-ai-server-check-btn");
        var resultEl = document.getElementById("local-ai-server-result");
        var modelsEl = document.getElementById("local-ai-server-models");
        if (btn) {
            btn.disabled = true;
            btn.textContent = "Checking...";
        }
        resultEl.textContent = "";
        resultEl.className = "result-message";
        try {
            var resp = await this.api("GET", "/api/local-ai/lmstudio/status");
            await this.refreshWizardState();
            await this.refreshLocalAIStatus();
            resultEl.textContent = resp.message;
            resultEl.classList.add(resp.ok ? "success" : "error");
            if (modelsEl) {
                if (resp.models && resp.models.length) {
                    modelsEl.textContent = "Loaded models:\n" + resp.models.map(function (item) { return "- " + item.id; }).join("\n");
                    modelsEl.className = "result-message success";
                } else {
                    modelsEl.textContent = "";
                    modelsEl.className = "result-message";
                }
            }
        } catch (err) {
            resultEl.textContent = err.message;
            resultEl.classList.add("error");
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = "Check LM Studio Server";
            }
        }
    },

    async writeLocalAIConfig() {
        var scope = document.querySelector('input[name="local-ai-config-scope"]:checked');
        var modelAlias = document.getElementById("local-ai-model-alias").value || "gemma-local";
        var chosenModelLabel = document.getElementById("local-ai-chosen-model-label").value || "Gemma Local";
        var apiKey = document.getElementById("local-ai-api-key").value || "lm-studio";
        var baseURL = document.getElementById("local-ai-base-url").value || "http://127.0.0.1:1234/v1";
        var resultEl = document.getElementById("local-ai-config-write-result");
        resultEl.textContent = "";
        resultEl.className = "result-message";
        try {
            var resp = await this.api("POST", "/api/local-ai/config/write", {
                scope: scope ? scope.value : "global",
                model_alias: modelAlias,
                chosen_model_label: chosenModelLabel,
                api_key: apiKey,
                base_url: baseURL
            });
            await this.refreshWizardState();
            await this.refreshLocalAIStatus();
            this.renderLocalAIStatus();
            resultEl.textContent = resp.message;
            resultEl.classList.add(resp.ok ? "success" : "error");
        } catch (err) {
            resultEl.textContent = err.message;
            resultEl.classList.add("error");
        }
    },

    async verifyLocalAISetup() {
        var resultEl = document.getElementById("local-ai-verify-result");
        var checksEl = document.getElementById("local-ai-verify-checks");
        resultEl.textContent = "";
        resultEl.className = "result-message";
        checksEl.textContent = "";
        checksEl.className = "result-message";
        try {
            var resp = await this.api("POST", "/api/local-ai/verify", {});
            await this.refreshWizardState();
            await this.refreshLocalAIStatus();
            resultEl.textContent = resp.message;
            resultEl.classList.add(resp.ok ? "success" : "error");
            if (resp.checks && resp.checks.length) {
                checksEl.textContent = resp.checks.map(function (item) {
                    return (item.ok ? "PASS: " : "TODO: ") + item.label;
                }).join("\n");
                checksEl.classList.add(resp.ok ? "success" : "error");
            }
        } catch (err) {
            resultEl.textContent = err.message;
            resultEl.classList.add("error");
        }
    },

    markLocalAIModelEdited() {
        var input = document.getElementById("local-ai-chosen-model-label");
        if (input) {
            input.dataset.userEdited = "true";
        }
    },

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
            var resp = await this.api("POST", "/api/todoist/save-token", { token: token });
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

    async verifyTelegramToken() {
        var token = document.getElementById("telegram-token").value;
        var errorEl = document.getElementById("telegram-token-error");
        errorEl.textContent = "";
        if (!token.trim()) {
            errorEl.textContent = "Please paste your bot token.";
            return;
        }
        try {
            var resp = await this.api("POST", "/api/telegram/verify-token", { bot_token: token });
            if (resp.valid) {
                document.getElementById("telegram-verified").hidden = false;
                document.getElementById("telegram-bot-info").textContent = resp.message;
                document.getElementById("telegram-bot-info").className = "result-message success";
                document.getElementById("telegram-next-steps").hidden = false;
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
            var resp = await this.api("POST", "/api/telegram/detect-ids", { bot_token: token });
            if (resp.found) {
                document.getElementById("telegram-ids").hidden = false;
                document.getElementById("telegram-user-id").textContent = resp.user_id;
                document.getElementById("telegram-chat-id").textContent = resp.chat_id;
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
            var resp = await this.api("POST", "/api/telegram/save-config", { bot_token: token, user_id: userId, chat_id: chatId });
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

    googleStep(n) {
        for (var i = 1; i <= 7; i++) {
            var el = document.getElementById("google-step-" + i);
            if (el) el.hidden = i !== n;
        }
        if (n === 6) {
            this.renderGoogleUploadLayout();
        }
        if (n === 7) {
            this.renderGoogleSignInButtons();
        }
    },

    googleAccountCount() {
        var radios = document.querySelectorAll('input[name="google-accounts"]');
        var count = 1;
        radios.forEach(function (r) {
            if (r.checked) count = parseInt(r.value, 10);
        });
        return count;
    },

    googleAccounts() {
        return this.googleAccountCount() === 1 ? ["private"] : ["private", "personal"];
    },

    renderGoogleUploadLayout() {
        var wrap = document.getElementById("google-personal-upload-wrap");
        if (wrap) {
            wrap.hidden = this.googleAccountCount() !== 2;
        }
    },

    initGoogleUpload() {
        this.initGoogleUploadZone("private");
        this.initGoogleUploadZone("personal");
        var radios = document.querySelectorAll('input[name="google-accounts"]');
        radios.forEach((radio) => {
            radio.addEventListener("change", () => this.renderGoogleUploadLayout());
        });
    },

    initGoogleUploadZone(account) {
        var zone = document.getElementById("google-upload-zone-" + account);
        var input = document.getElementById("google-file-input-" + account);
        if (!zone || !input) return;
        zone.addEventListener("click", function () { input.click(); });
        zone.addEventListener("dragover", function (e) { e.preventDefault(); zone.classList.add("dragover"); });
        zone.addEventListener("dragleave", function () { zone.classList.remove("dragover"); });
        zone.addEventListener("drop", (e) => {
            e.preventDefault();
            zone.classList.remove("dragover");
            if (e.dataTransfer.files.length) {
                this.handleGoogleFile(account, e.dataTransfer.files[0]);
            }
        });
        input.addEventListener("change", () => {
            if (input.files.length) {
                this.handleGoogleFile(account, input.files[0]);
            }
        });
    },

    handleGoogleFile(account, file) {
        var reader = new FileReader();
        reader.onload = (e) => {
            this.googleFiles[account] = { name: file.name, content: e.target.result };
            var status = document.getElementById("google-upload-status-" + account);
            status.innerHTML = '<div class="result-message success">Loaded ' + file.name + ' for ' + account + '.</div>';
        };
        reader.readAsText(file);
    },

    async saveGoogleCredentials() {
        var result = document.getElementById("google-upload-status");
        result.textContent = "";
        result.className = "result-message";
        var accounts = this.googleAccounts();
        var payload = [];
        for (var i = 0; i < accounts.length; i++) {
            var account = accounts[i];
            if (!this.googleFiles[account]) {
                result.textContent = "Load a JSON file for the " + account + " account.";
                result.classList.add("error");
                return;
            }
            payload.push({ account: account, client_json: this.googleFiles[account].content });
        }
        try {
            var resp = await this.api("POST", "/api/google/upload-credentials", { credentials: payload });
            if (resp.valid) {
                result.textContent = resp.message;
                result.classList.add("success");
                await this.refreshWizardState();
                setTimeout(() => this.googleStep(7), 800);
            } else {
                result.textContent = resp.message;
                result.classList.add("error");
            }
        } catch (err) {
            result.textContent = err.message;
            result.classList.add("error");
        }
    },

    renderGoogleSignInButtons() {
        var container = document.getElementById("google-signin-buttons");
        if (!container) return;
        var accounts = this.googleAccounts();
        var services = [
            { key: "gcal", label: "Google Calendar" },
            { key: "gmail", label: "Gmail" },
            { key: "gdrive", label: "Google Workspace / Drive" },
        ];
        var html = "";
        for (var s = 0; s < services.length; s++) {
            for (var a = 0; a < accounts.length; a++) {
                var svc = services[s];
                var acct = accounts[a];
                var key = svc.key + "_" + acct + "_authed";
                var connected = !!this.state[key];
                html += '<button class="' + (connected ? "btn-secondary" : "btn-primary") + '" ' + (connected ? "disabled" : "") + ' onclick="App.startGoogleAuth(\'' + svc.key + '\', \'' + acct + '\')">' + (connected ? "Connected: " : "Sign in: ") + svc.label + (accounts.length > 1 ? " (" + acct + ")" : "") + "</button> ";
            }
            html += "<br>";
        }
        container.innerHTML = html;
    },

    async startGoogleAuth(service, account) {
        var resultEl = document.getElementById("google-auth-result");
        resultEl.textContent = "";
        resultEl.className = "result-message";
        try {
            var resp = await this.api("POST", "/api/google/start-auth", { service: service, account: account });
            if (resp.success) {
                this.state = await this.api("GET", "/api/status");
                this.renderGoogleSignInButtons();
                resultEl.textContent = "Connected " + service + " for " + account + ".";
                resultEl.classList.add("success");
            } else {
                resultEl.textContent = resp.error || "Google auth failed.";
                resultEl.classList.add("error");
            }
        } catch (err) {
            resultEl.textContent = err.message;
            resultEl.classList.add("error");
        }
    },

    shouldOfferInitialLoad() {
        var caps = this.initialLoadCapabilities();
        return caps.meetings || caps.emails || caps.messages || caps.tasks;
    },

    prepareInitialLoadScreen() {
        var caps = this.initialLoadCapabilities();
        var options = [];
        if (caps.meetings) {
            options.push({ key: "meetings", label: "Meetings", description: "Create meeting notes from the last N days" });
        }
        if (caps.emails) {
            options.push({ key: "emails", label: "Emails", description: "Export important emails and sent-thread snapshots" });
        }
        if (caps.messages) {
            options.push({ key: "messages", label: "Slack Messages", description: "Export Slack summaries and thread snapshots" });
        }
        if (caps.tasks) {
            options.push({ key: "tasks", label: "Todoist Tasks", description: "Sync upcoming tasks into daily briefs" });
        }
        this.initialLoadServices = options.map(function (item) { return item.key; });
        var container = document.getElementById("initial-load-options");
        if (!container) return;
        container.innerHTML = options.map(function (item) {
            return '<label class="service-option">' +
                '<input type="checkbox" name="initial-load-service" value="' + item.key + '" checked>' +
                '<div class="service-info">' +
                '<span class="service-name">' + item.label + '</span>' +
                '<span class="service-desc">' + item.description + '</span>' +
                '</div></label>';
        }).join("");
    },

    selectedInitialLoadServices() {
        return Array.from(document.querySelectorAll('input[name="initial-load-service"]:checked')).map(function (item) {
            return item.value;
        });
    },

    async runInitialLoad() {
        var services = this.selectedInitialLoadServices();
        var resultEl = document.getElementById("initial-load-result");
        var detailsEl = document.getElementById("initial-load-details");
        var runBtn = document.getElementById("initial-load-run-btn");
        resultEl.textContent = "";
        resultEl.className = "result-message";
        detailsEl.textContent = "";
        detailsEl.className = "result-message";

        if (!services.length) {
            resultEl.textContent = "Select at least one initial load option or skip this step.";
            resultEl.classList.add("error");
            return;
        }

        var daysBack = parseInt(document.getElementById("initial-load-days-back").value || "7", 10);
        var daysAhead = parseInt(document.getElementById("initial-load-days-ahead").value || "14", 10);
        if (Number.isNaN(daysBack) || daysBack < 1) {
            resultEl.textContent = "Days back must be at least 1.";
            resultEl.classList.add("error");
            return;
        }
        if (Number.isNaN(daysAhead) || daysAhead < 0) {
            resultEl.textContent = "Todoist days ahead must be 0 or greater.";
            resultEl.classList.add("error");
            return;
        }

        runBtn.disabled = true;
        runBtn.textContent = "Running...";
        resultEl.textContent = "Running initial load. This can take a few minutes.";
        try {
            var resp = await this.api("POST", "/api/initial-load/run", {
                services: services,
                days_back: daysBack,
                todoist_days_ahead: daysAhead,
            });
            resultEl.textContent = resp.message;
            resultEl.classList.add(resp.ok ? "success" : "error");
            if (resp.results && resp.results.length) {
                detailsEl.textContent = resp.results.map(function (item) {
                    var tail = item.ok ? (item.stdout || "Done") : (item.stderr || item.stdout || ("Failed with exit code " + item.returncode));
                    return item.label + ": " + tail;
                }).join("\n\n");
                detailsEl.classList.add(resp.ok ? "success" : "error");
            }
            if (resp.ok) {
                setTimeout(() => {
                    this.goTo("summary");
                    this.loadSummary();
                }, 1200);
            }
        } catch (err) {
            resultEl.textContent = err.message;
            resultEl.classList.add("error");
        } finally {
            runBtn.disabled = false;
            runBtn.textContent = "Run Initial Load";
        }
    },

    skipInitialLoad() {
        this.goTo("summary");
        this.loadSummary();
    },

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
            var resp = await this.api("POST", "/api/fireflies/save-key", { key: key });
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
            var resp = await this.api("POST", "/api/clockify/save-key", { key: key });
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
            var resp = await this.api("POST", "/api/slack/save-token", { token: token, alias: alias });
            if (resp.valid) {
                resultEl.textContent = resp.message;
                resultEl.classList.add("success");
                this.slackTeamId = resp.team_id || "";
                this.slackUserId = resp.user_id || "";
                await this.refreshWizardState();
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
                container.innerHTML = '<div class="result-message error">Could not load channels: ' + (resp.error || "unknown") + "</div>";
            }
        } catch (err) {
            container.innerHTML = '<div class="result-message error">' + err.message + "</div>";
        }
    },

    renderSlackChannels(channels) {
        var container = document.getElementById("slack-channel-list");
        if (!channels.length) {
            container.innerHTML = '<p class="muted">No channels found. Make sure the bot is added to at least one channel.</p>';
            return;
        }
        container.innerHTML = channels.map(function (ch) {
            return '<label class="service-option">' +
                '<input type="checkbox" name="slack-channel" value="' + ch.id + '" data-name="' + ch.name + '" data-type="' + ch.type + '">' +
                '<div class="service-info">' +
                '<span class="service-name">#' + ch.name + "</span>" +
                '<span class="service-desc">' + ch.type + "</span>" +
                "</div></label>";
        }).join("");
    },

    async saveSlackConfig() {
        var alias = document.getElementById("slack-alias").value;
        var checks = document.querySelectorAll('input[name="slack-channel"]:checked');
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
                    token_file: "90_System/secrets/slack_token_" + alias + ".txt",
                    jan_user_ids: this.slackUserId ? [this.slackUserId] : [],
                    download: {
                        enabled: false,
                        max_bytes: 26214400,
                        allowed_extensions: [".csv", ".docx", ".jpg", ".md", ".pdf", ".png", ".pptx", ".txt", ".xlsx"],
                    },
                    allow_conversations: conversations,
                },
            ],
        };
        var resultEl = document.getElementById("slack-config-result");
        resultEl.textContent = "";
        resultEl.className = "result-message";
        try {
            var resp = await this.api("POST", "/api/slack/save-config", { config: config });
            if (resp.saved) {
                resultEl.textContent = "Slack configuration saved.";
                resultEl.classList.add("success");
                await this.refreshWizardState();
                setTimeout(() => this.goToNextService(), 1500);
            }
        } catch (err) {
            resultEl.textContent = err.message;
            resultEl.classList.add("error");
        }
    },

    googleConnected(resp) {
        var accounts = resp.google_accounts && resp.google_accounts.length ? resp.google_accounts : ["private"];
        for (var i = 0; i < accounts.length; i++) {
            var acct = accounts[i];
            if (!(resp["gcal_" + acct + "_authed"] && resp["gmail_" + acct + "_authed"] && resp["gdrive_" + acct + "_authed"])) {
                return false;
            }
        }
        return !!resp.google_credentials_uploaded;
    },

    async loadSummary() {
        try {
            var resp = await this.api("GET", "/api/status");
            var prereqs = await this.api("GET", "/api/prerequisites");
            var browser = await this.api("GET", "/api/browser/status");
            this.state = resp;
            this.assistantStatus = prereqs.assistant || this.assistantStatus;
            this.browserStatus = browser || this.browserStatus;
            var grid = document.getElementById("status-grid");
            var services = [
                { key: "__assistant__", name: "Coding Assistant" },
                { key: "__google__", name: "Google Workspace" },
                { key: "todoist_connected", name: "Todoist" },
                { key: "telegram_connected", name: "Telegram Bridge" },
                { key: "fireflies_connected", name: "Fireflies" },
                { key: "clockify_connected", name: "Clockify" },
                { key: "slack_connected", name: "Slack" },
                { key: "browser_playwright_installed", name: "Playwright Browser", serviceKey: "browser" },
                { key: "local_ai_completed", name: "Local AI Setup", serviceKey: "local-ai" },
            ];
            var selected = this.selectedServices;
            grid.innerHTML = services.map((s) => {
                var connected = false;
                if (s.key === "__assistant__") {
                    connected = prereqs.assistant && prereqs.assistant.installed_any;
                } else if (s.key === "__google__") {
                    connected = this.googleConnected(resp);
                } else if (s.key === "browser_playwright_installed") {
                    connected = browser && browser.installed;
                } else if (s.key === "local_ai_completed") {
                    connected = !!resp[s.key];
                } else {
                    connected = !!resp[s.key];
                }
                var svcKey = s.key === "__assistant__" ? "__assistant__" : (s.key === "__google__" ? "google" : (s.serviceKey || s.name.toLowerCase().split(" ")[0]));
                var isSelected = s.key === "__assistant__" ? true : selected.indexOf(svcKey) !== -1;
                var badge = "Not Set Up";
                var cls = "not-connected";
                if (connected) {
                    if (s.key === "__assistant__" && prereqs.assistant) {
                        var names = prereqs.assistant.assistants.filter(function (item) { return item.installed; }).map(function (item) { return item.label; });
                        badge = names.join(" / ") || "Connected";
                    } else if (s.key === "__google__") {
                        badge = "Calendar + Gmail + Drive ready";
                    } else {
                        badge = "Connected";
                    }
                    cls = "connected";
                } else if (!isSelected) {
                    badge = "Skipped";
                    cls = "skipped";
                }
                return '<div class="status-row"><span>' + s.name + '</span><span class="status-badge ' + cls + '">' + badge + "</span></div>";
            }).join("");
            document.getElementById("vault-path").textContent = prereqs.repo_root;
            this.renderTryAssistant();
        } catch (_) {}
    },

    renderTryAssistant(message, isError) {
        var wrap = document.getElementById("assistant-try");
        var buttons = document.getElementById("assistant-launch-buttons");
        var result = document.getElementById("assistant-launch-result");
        if (!wrap || !buttons || !result) return;
        if (!this.assistantStatus || !this.assistantStatus.supported) {
            wrap.hidden = true;
            return;
        }
        var installed = (this.assistantStatus.assistants || []).filter(function (item) { return item.installed; });
        wrap.hidden = !installed.length;
        if (!installed.length) return;
        buttons.innerHTML = installed.map(function (item) {
            return '<button class="btn-primary" onclick="App.launchAssistant(\'' + item.key + '\')">Try ' + item.label + "</button>";
        }).join(" ");
        if (message) {
            result.textContent = message;
            result.className = "result-message " + (isError ? "error" : "success");
        } else {
            result.textContent = "";
            result.className = "result-message";
        }
    },

    async launchAssistant(key) {
        this.renderTryAssistant("Starting assistant session...", false);
        try {
            var resp = await this.api("POST", "/api/assistant/launch", { assistant: key });
            this.renderTryAssistant(resp.message, !resp.ok);
        } catch (err) {
            this.renderTryAssistant(err.message, true);
        }
    },

    async shutdown() {
        try {
            await this.api("POST", "/api/shutdown");
        } catch (_) {}
        document.body.innerHTML = '<div style="text-align:center;padding:80px"><h2>Setup wizard closed.</h2><p>You can close this tab.</p></div>';
    },

    copyManifest() {
        var code = document.getElementById("slack-manifest-code").textContent;
        if (navigator.clipboard) {
            navigator.clipboard.writeText(code);
        }
    },
};

document.addEventListener("DOMContentLoaded", function () {
    App.init();
});
