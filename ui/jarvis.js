const API = 'http://localhost:8080/api';

const JARVIS = {
    isListening: false,
    recognition: null,
    synth: window.speechSynthesis,
    selectedVoice: null,
    waveAnimId: null,
    dom: {},

    useEdgeTTS: true,

    wakeWordActive: false,
    wakeWordRecog: null,
    commandListening: false,
    isSpeaking: false,
    wakeWordRetryTimer: null,
    wakeWordLastEvent: 0,
    wakeWordRestartCount: 0,
    lastStateChange: 0,
    processingVideo: false,
    conversationMode: false,
    conversationTimer: null,
    conversationSilenceMs: 5000,
    systemActive: true,

    init() {
        this.cacheDom();
        this.setupClock();
        this.setupVoice();
        this.setupWaveform();
        this.initReactor();
        this.setupTabs();
        this.bindEvents();
        this.loadConfig();
        this.loadHistory();
        this.startWakeWord();
        setInterval(() => {
            if (!this.systemActive) return;
            const now = Date.now();
            if (this.commandListening && this.lastStateChange && (now - this.lastStateChange > 20000)) {
                console.log('[Watchdog] commandListening trabado, reseteando...');
                this.commandListening = false;
            }
            if (this.isSpeaking && this.lastStateChange && (now - this.lastStateChange > 30000)) {
                console.log('[Watchdog] isSpeaking trabado, reseteando...');
                this.isSpeaking = false;
                this.reactorState = 'idle';
                this.dom.arcReactor.classList.remove('speaking');
                this.setWaveAmplitude(0);
            }
            if (this.commandListening) return;
            if (this.isSpeaking) return;
            const stale = this.wakeWordActive && (Date.now() - this.wakeWordLastEvent > 6000);
            if (!this.wakeWordActive || stale) {
                console.log('[Watchdog] Reiniciando wake word...');
                this.wakeWordActive = false;
                this.startWakeWord();
            }
        }, 3000);
        this.startProactivePolling();
    },

    cacheDom() {
        this.dom = {
            clock: document.getElementById('clock'),
            sysTime: document.getElementById('sys-time'),
            statusText: document.getElementById('status-text'),
            voiceStatus: document.getElementById('voice-status'),
            aiStatus: document.getElementById('ai-status'),
            memCount: document.getElementById('mem-count'),
            chatArea: document.getElementById('chat-area'),
            textInput: document.getElementById('text-input'),
            micBtn: document.getElementById('mic-btn'),
            sendBtn: document.getElementById('send-btn'),
            arcReactor: document.getElementById('arc-reactor'),
            waveCanvas: document.getElementById('waveCanvas'),
            apiKeyInput: document.getElementById('api-key'),
            saveKeyBtn: document.getElementById('save-key-btn'),
            keyStatus: document.getElementById('key-status'),
            gmailStatus: document.getElementById('gmail-status'),
            gmailAuthBtn: document.getElementById('gmail-auth-btn'),
            memoryList: document.getElementById('memory-list'),
            taskList: document.getElementById('task-list'),
            addTaskBtn: document.getElementById('add-task-btn'),
            powerBtn: document.getElementById('power-btn'),
            statusDot: document.getElementById('status-dot'),
        };
    },

    // Clock
    setupClock() {
        const tick = () => {
            const now = new Date();
            const t = now.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            this.dom.clock.textContent = t;
            this.dom.sysTime.textContent = t;
        };
        tick();
        setInterval(tick, 1000);
    },

    // Tabs
    setupTabs() {
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                btn.classList.add('active');
                document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
                if (btn.dataset.tab === 'memory') this.loadMemories();
                if (btn.dataset.tab === 'tasks') this.loadTasks();
                if (btn.dataset.tab === 'connections') this.loadConnections();
            });
        });

        document.querySelectorAll('#tab-memory .filter-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('#tab-memory .filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.loadMemories(btn.dataset.cat === 'all' ? null : btn.dataset.cat);
            });
        });

        document.querySelectorAll('#tab-tasks .filter-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('#tab-tasks .filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.loadTasks(btn.dataset.status);
            });
        });
    },

    // Voice
    setupVoice() {
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) {
            this.dom.voiceStatus.textContent = 'No soportado';
            this.dom.voiceStatus.className = 'val-error';
            return;
        }

        this.recognition = new SR();
        this.recognition.lang = 'es-AR';
        this.recognition.continuous = false;
        this.recognition.interimResults = false;

        this.recognition.onresult = (e) => {
            const text = e.results[0][0].transcript;
            this.processInput(text);
        };

        this.recognition.onstart = () => {
            this.isListening = true;
            this.dom.micBtn.classList.add('active');
            this.reactorState = 'listening'; this.dom.arcReactor.classList.add('listening');
            this.dom.voiceStatus.textContent = 'Escuchando...';
            this.dom.voiceStatus.className = 'val-active';
            this.dom.statusText.textContent = 'ESCUCHANDO';
            this.setWaveAmplitude(0.4);
        };

        this.recognition.onend = () => {
            this.isListening = false;
            this.dom.micBtn.classList.remove('active');
            this.reactorState = 'idle'; this.dom.arcReactor.classList.remove('listening');
            this.dom.voiceStatus.textContent = 'Listo';
            this.dom.voiceStatus.className = 'val-active';
            if (!this.processingVideo) this.dom.statusText.textContent = 'SISTEMA ACTIVO';
            this.setWaveAmplitude(0);
        };

        this.recognition.onerror = () => {
            this.dom.micBtn.classList.remove('active');
            this.reactorState = 'idle'; this.dom.arcReactor.classList.remove('listening');
        };

        this.dom.voiceStatus.textContent = 'Listo';
        this.dom.voiceStatus.className = 'val-active';

        const loadVoices = () => {
            const voices = this.synth.getVoices();
            this.selectedVoice =
                voices.find(v => v.lang.startsWith('es') && v.name.includes('Google')) ||
                voices.find(v => v.lang.startsWith('es')) ||
                voices[0];
        };
        loadVoices();
        this.synth.onvoiceschanged = loadVoices;
    },

    // Waveform
    setupWaveform() {
        const canvas = this.dom.waveCanvas;
        const ctx = canvas.getContext('2d');
        const w = canvas.width, h = canvas.height;
        let phase = 0, amplitude = 0, targetAmplitude = 0;

        const draw = () => {
            requestAnimationFrame(draw);
            ctx.clearRect(0, 0, w, h);
            amplitude += (targetAmplitude - amplitude) * 0.1;

            const speaking = this.dom.arcReactor.classList.contains('speaking');
            ctx.beginPath();
            ctx.strokeStyle = speaking ? 'rgba(0,255,136,0.5)' : 'rgba(255,149,0,0.3)';
            ctx.lineWidth = 2;

            for (let x = 0; x < w; x++) {
                const y = h / 2 + (
                    Math.sin((x / w) * 4 * Math.PI + phase) +
                    Math.sin((x / w) * 6 * Math.PI + phase * 1.5) * 0.5 +
                    Math.sin((x / w) * 10 * Math.PI + phase * 0.7) * 0.3
                ) * amplitude * (h / 4);
                x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
            }
            ctx.stroke();
            phase += 0.03;
        };

        this.setWaveAmplitude = (val) => { targetAmplitude = val; };
        draw();
    },

    reactorState: 'idle',

    initReactor() {
        const canvas = document.getElementById('reactorCanvas');
        if (!canvas) return;
        this.rCtx = canvas.getContext('2d');
        this.rW = canvas.width;
        this.rH = canvas.height;
        this.rCx = this.rW / 2;
        this.rCy = this.rH / 2;
        this.rScale = this.rW / 520;
        this.rTime = 0;
        this.rParticles = [];
        this.rSparks = [];
        this.rEnergy = [];

        const s = this.rScale;
        for (let i = 0; i < 350; i++) {
            const ring = Math.floor(Math.random() * 7);
            const baseR = (40 + ring * 30) * s;
            this.rParticles.push({
                radius: baseR + (Math.random() - 0.5) * 16 * s,
                angle: Math.random() * Math.PI * 2,
                speed: (0.15 + Math.random() * 0.35) * (ring % 2 ? 1 : -1),
                size: (0.8 + Math.random() * 2.5) * s,
                glow: 0.2 + Math.random() * 0.8,
                ring
            });
        }

        for (let i = 0; i < 60; i++) {
            this.rSparks.push(this._newSpark());
        }

        for (let i = 0; i < 8; i++) {
            this.rEnergy.push({
                angle: (Math.PI * 2 * i) / 8,
                wobble: Math.random() * Math.PI * 2
            });
        }

        this.animateReactor();
    },

    _newSpark() {
        const a = Math.random() * Math.PI * 2;
        const s = this.rScale || 1;
        return { angle: a, radius: (20 + Math.random() * 30) * s, speed: (0.5 + Math.random() * 2) * s, life: 0, maxLife: 40 + Math.random() * 80, size: (0.5 + Math.random() * 2.5) * s };
    },

    animateReactor() {
        const ctx = this.rCtx;
        const cx = this.rCx, cy = this.rCy, w = this.rW, h = this.rH;
        ctx.clearRect(0, 0, w, h);
        this.rTime++;

        const isListening = this.reactorState === 'listening';
        const isSpeaking = this.reactorState === 'speaking';
        const isThinking = this.reactorState === 'thinking';
        const intensity = isListening ? 1.6 : isThinking ? 1.3 : isSpeaking ? 1.1 : 1.0;
        const speedMul = isThinking ? 2.0 : isListening ? 1.5 : 1.0;

        const r1 = isSpeaking ? 50 : 180;
        const g1 = isSpeaking ? 255 : 150;
        const b1 = isSpeaking ? 100 : 30;

        const s = this.rScale;
        const outerGlow = ctx.createRadialGradient(cx, cy, 0, cx, cy, 300 * s);
        outerGlow.addColorStop(0, `rgba(${r1}, ${g1}, ${b1}, ${0.12 * intensity})`);
        outerGlow.addColorStop(0.4, `rgba(${r1}, ${Math.floor(g1*0.7)}, ${b1}, ${0.04 * intensity})`);
        outerGlow.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = outerGlow;
        ctx.fillRect(0, 0, w, h);

        const coreSize = (40 + Math.sin(this.rTime * 0.04 * speedMul) * 8 * intensity) * s;
        const coreGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreSize * 2);
        coreGrad.addColorStop(0, `rgba(255, ${isSpeaking ? 255 : 220}, ${isSpeaking ? 180 : 120}, ${0.95 * intensity})`);
        coreGrad.addColorStop(0.2, `rgba(${r1+50}, ${g1}, ${b1+20}, ${0.7 * intensity})`);
        coreGrad.addColorStop(0.5, `rgba(${r1}, ${Math.floor(g1*0.6)}, 0, ${0.25 * intensity})`);
        coreGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = coreGrad;
        ctx.beginPath();
        ctx.arc(cx, cy, coreSize * 2, 0, Math.PI * 2);
        ctx.fill();

        for (const e of this.rEnergy) {
            e.wobble += 0.02 * speedMul;
            const len = (140 + Math.sin(e.wobble) * 60) * s;
            const spread = 0.08 + Math.sin(this.rTime * 0.01 + e.angle) * 0.03;
            ctx.save();
            ctx.translate(cx, cy);
            ctx.rotate(e.angle + Math.sin(this.rTime * 0.005) * 0.1);
            const grad = ctx.createLinearGradient(0, 0, len, 0);
            grad.addColorStop(0, `rgba(${r1+50}, ${g1}, ${b1}, ${0.4 * intensity})`);
            grad.addColorStop(0.5, `rgba(${r1}, ${Math.floor(g1*0.6)}, 0, ${0.15 * intensity})`);
            grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
            ctx.fillStyle = grad;
            ctx.beginPath();
            ctx.moveTo(15 * s, 0);
            ctx.lineTo(len, -len * spread);
            ctx.lineTo(len, len * spread);
            ctx.closePath();
            ctx.fill();
            ctx.restore();
        }

        for (const p of this.rParticles) {
            p.angle += p.speed * 0.015 * speedMul;
            const wobble = Math.sin(this.rTime * 0.025 * speedMul + p.angle * 3) * 8 * s;
            const r = p.radius + wobble;
            const x = cx + Math.cos(p.angle) * r;
            const y = cy + Math.sin(p.angle) * r;
            const bright = p.glow * (0.5 + 0.5 * Math.sin(this.rTime * 0.04 + p.angle)) * intensity;

            ctx.beginPath();
            ctx.arc(x, y, p.size * Math.min(bright + 0.3, 1.5), 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${Math.floor(200 + bright * 55)}, ${Math.floor(100 + bright * 80)}, ${Math.floor(bright * 40)}, ${bright})`;
            ctx.fill();

            if (bright > 0.7) {
                ctx.beginPath();
                ctx.arc(x, y, p.size * 3, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(255, ${Math.floor(g1)}, ${b1}, ${(bright - 0.7) * 0.3})`;
                ctx.fill();
            }
        }

        for (const s of this.rSparks) {
            s.radius += s.speed * speedMul;
            s.life++;
            if (s.life > s.maxLife) Object.assign(s, this._newSpark());
            const alpha = Math.max(0, 1 - s.life / s.maxLife) * intensity;
            const x = cx + Math.cos(s.angle) * s.radius;
            const y = cy + Math.sin(s.angle) * s.radius;
            ctx.beginPath();
            ctx.arc(x, y, s.size * alpha, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(255, ${Math.floor(150 + alpha * 80)}, ${Math.floor(alpha * 50)}, ${alpha * 0.7})`;
            ctx.fill();
        }

        ctx.strokeStyle = `rgba(${r1}, ${Math.floor(g1*0.5)}, 0, ${0.06 * intensity})`;
        ctx.lineWidth = 0.5;
        for (let i = 1; i <= 7; i++) {
            ctx.beginPath();
            ctx.arc(cx, cy, (40 + i * 30) * s, 0, Math.PI * 2);
            ctx.stroke();
        }

        requestAnimationFrame(() => this.animateReactor());
    },

    // Events
    bindEvents() {
        this.dom.micBtn.addEventListener('click', () => {
            if (!this.recognition) return;
            this.isListening ? this.recognition.stop() : this.recognition.start();
        });

        this.dom.sendBtn.addEventListener('click', () => this.sendTextInput());
        this.dom.textInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') this.sendTextInput();
        });

        this.dom.saveKeyBtn.addEventListener('click', () => this.saveApiKey());
        document.getElementById('change-key-btn').addEventListener('click', () => {
            const provider = this.currentProvider || 'anthropic';
            if (provider === 'openrouter') {
                document.getElementById('api-key-openrouter').value = '';
                document.getElementById('api-key-openrouter').focus();
            } else {
                this.dom.apiKeyInput.value = '';
                this.dom.apiKeyInput.type = 'text';
                this.dom.apiKeyInput.focus();
            }
            this.dom.keyStatus.innerHTML = '<div class="status-err">Pega la key nueva y dale Guardar</div>';
        });
        document.querySelectorAll('.provider-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.provider-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const provider = btn.dataset.provider;
                this.currentProvider = provider;
                document.getElementById('provider-anthropic-info').style.display = provider === 'anthropic' ? '' : 'none';
                document.getElementById('provider-openrouter-info').style.display = provider === 'openrouter' ? '' : 'none';
            });
        });
        this.dom.powerBtn.addEventListener('click', () => this.toggleSystem());
        this.dom.gmailAuthBtn.addEventListener('click', () => this.connectGmail());
        document.getElementById('save-together-btn').addEventListener('click', () => this.saveTogetherKey());
        this.dom.addTaskBtn.addEventListener('click', () => this.addTaskFromForm());

        document.getElementById('video-btn').addEventListener('click', () => {
            document.getElementById('video-input').click();
        });
        document.getElementById('video-input').addEventListener('change', (e) => {
            if (e.target.files.length) this.showFormatSelector(e.target.files[0]);
            e.target.value = '';
        });
        document.getElementById('video-results-btn').addEventListener('click', () => {
            this.reopenVideoResults();
        });
        document.getElementById('doc-btn').addEventListener('click', () => {
            document.getElementById('doc-input').click();
        });
        document.getElementById('doc-input').addEventListener('change', (e) => {
            if (e.target.files.length) this.uploadDocument(e.target.files[0]);
            e.target.value = '';
        });

        try {
            if (localStorage.getItem('jarvis_last_video')) {
                document.getElementById('video-results-btn').style.display = '';
            }
        } catch(e) {}
    },

    sendTextInput() {
        const text = this.dom.textInput.value.trim();
        if (!text) return;
        this.dom.textInput.value = '';
        this.processInput(text);
    },

    // Config
    async loadConfig() {
        try {
            const res = await fetch(`${API}/config`);
            const data = await res.json();
            const provider = data.ai_provider || 'anthropic';
            this.currentProvider = provider;
            const provLabel = provider === 'openrouter' ? 'OpenRouter' : 'Claude AI';
            this.dom.aiStatus.textContent = data.has_api_key ? provLabel : 'Sin config';
            this.dom.aiStatus.className = data.has_api_key ? 'val-active' : 'val-error';
            this.dom.memCount.textContent = data.memory_count;

            document.querySelectorAll('.provider-btn').forEach(b => {
                b.classList.toggle('active', b.dataset.provider === provider);
            });
            document.getElementById('provider-anthropic-info').style.display = provider === 'anthropic' ? '' : 'none';
            document.getElementById('provider-openrouter-info').style.display = provider === 'openrouter' ? '' : 'none';

            if (data.has_api_key) {
                if (provider === 'openrouter') {
                    document.getElementById('api-key-openrouter').value = '••••••••••••';
                    if (data.ai_model) {
                        document.getElementById('openrouter-model').value = data.ai_model;
                    }
                } else {
                    this.dom.apiKeyInput.value = '••••••••••••';
                }
                this.dom.keyStatus.innerHTML = `<div class="status-ok">API Key configurada (${provLabel})</div>`;
            }

            this.dom.gmailStatus.innerHTML = data.gmail_configured
                ? (data.gmail_authenticated
                    ? '<div class="status-ok">Gmail conectado</div>'
                    : '<div class="status-err">Gmail configurado pero no autenticado</div>')
                : '<div class="status-err">Gmail no configurado</div>';

            const togetherStatus = document.getElementById('together-status');
            if (togetherStatus) {
                togetherStatus.innerHTML = data.together_configured
                    ? '<div class="status-ok">Together AI configurado (FLUX)</div>'
                    : '<div class="status-err">No configurado (usando Pollinations)</div>';
                if (data.together_configured) {
                    document.getElementById('together-key').value = '••••••••••••';
                }
            }
        } catch (e) {
            this.dom.aiStatus.textContent = 'Error';
            this.dom.aiStatus.className = 'val-error';
        }
    },

    async saveApiKey() {
        const provider = this.currentProvider || 'anthropic';
        let key;
        if (provider === 'openrouter') {
            key = document.getElementById('api-key-openrouter').value.trim().replace(/\s+/g, '');
        } else {
            key = this.dom.apiKeyInput.value.trim().replace(/\s+/g, '');
        }
        if (!key || key === '••••••••••••' || key.length < 10) {
            this.dom.keyStatus.innerHTML = '<div class="status-err">La key es muy corta</div>';
            return;
        }

        const body = { key, provider };
        if (provider === 'openrouter') {
            const model = document.getElementById('openrouter-model').value;
            if (model) body.model = model;
        }

        try {
            const res = await fetch(`${API}/config/api-key`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            const data = await res.json();
            if (data.success) {
                const provName = provider === 'openrouter' ? 'OpenRouter' : 'Anthropic';
                this.dom.keyStatus.innerHTML = `<div class="status-ok">API Key de ${provName} guardada. Probando conexion...</div>`;
                if (provider === 'openrouter') {
                    document.getElementById('api-key-openrouter').value = '••••••••••••';
                } else {
                    this.dom.apiKeyInput.value = '••••••••••••';
                }
                this.loadConfig();
                this.processInput('Hola Jarvis, confirma que estas funcionando');
            } else {
                this.dom.keyStatus.innerHTML = `<div class="status-err">${data.error}</div>`;
            }
        } catch (e) {
            this.dom.keyStatus.innerHTML = '<div class="status-err">Error de conexion con el servidor</div>';
        }
    },

    async saveTogetherKey() {
        const key = document.getElementById('together-key').value.trim();
        const status = document.getElementById('together-status');
        if (!key || key === '••••••••••••' || key.length < 10) {
            status.innerHTML = '<div class="status-err">La key es muy corta</div>';
            return;
        }
        try {
            const res = await fetch(`${API}/config/together-key`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key })
            });
            const data = await res.json();
            if (data.success) {
                status.innerHTML = '<div class="status-ok">Together AI configurado (FLUX)</div>';
                document.getElementById('together-key').value = '••••••••••••';
            } else {
                status.innerHTML = `<div class="status-err">${data.error}</div>`;
            }
        } catch (e) {
            status.innerHTML = '<div class="status-err">Error de conexion</div>';
        }
    },

    async connectGmail() {
        const addr = document.getElementById('gmail-address').value.trim();
        const pwd = document.getElementById('gmail-app-pwd').value.trim();
        if (!addr || !pwd) {
            this.dom.gmailStatus.innerHTML = '<div class="status-err">Completa email y App Password</div>';
            return;
        }
        this.dom.gmailStatus.innerHTML = '<div class="status-ok">Conectando...</div>';
        try {
            const res = await fetch(`${API}/gmail/setup`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ address: addr, app_password: pwd })
            });
            const data = await res.json();
            if (data.success) {
                this.dom.gmailStatus.innerHTML = '<div class="status-ok">Gmail conectado exitosamente</div>';
                document.getElementById('gmail-app-pwd').value = '';
            } else {
                this.dom.gmailStatus.innerHTML = `<div class="status-err">${data.error}</div>`;
            }
        } catch (e) {
            this.dom.gmailStatus.innerHTML = '<div class="status-err">Error conectando Gmail</div>';
        }
    },

    // Memory
    async loadMemories(category = null) {
        try {
            const url = category ? `${API}/memories?category=${category}` : `${API}/memories`;
            const res = await fetch(url);
            const data = await res.json();
            this.renderMemories(data);
        } catch (e) {
            this.dom.memoryList.innerHTML = '<div class="config-hint">Error cargando memorias</div>';
        }
    },

    renderMemories(memories) {
        if (!memories.length) {
            this.dom.memoryList.innerHTML = '<div class="config-hint" style="text-align:center;padding:20px;">Jarvis aun no tiene memorias. Hablale y contale cosas sobre vos.</div>';
            return;
        }
        this.dom.memoryList.innerHTML = memories.map(m => `
            <div class="memory-item">
                <div class="memory-item-content">
                    <span class="memory-category">${m.category.toUpperCase()}</span>
                    <div class="memory-text">${this.esc(m.content)}</div>
                    <div class="memory-date">${new Date(m.created_at).toLocaleString('es-AR')}</div>
                </div>
                <button class="delete-btn" onclick="JARVIS.deleteMemory(${m.id})">Borrar</button>
            </div>
        `).join('');
    },

    async deleteMemory(id) {
        await fetch(`${API}/memories/${id}`, { method: 'DELETE' });
        this.loadMemories();
    },

    // Tasks
    async loadTasks(status = 'pending') {
        try {
            const res = await fetch(`${API}/tasks?status=${status}`);
            const data = await res.json();
            this.renderTasks(data, status);
        } catch (e) {
            this.dom.taskList.innerHTML = '<div class="config-hint">Error cargando tareas</div>';
        }
    },

    renderTasks(tasks, currentStatus) {
        if (!tasks.length) {
            this.dom.taskList.innerHTML = `<div class="config-hint" style="text-align:center;padding:20px;">No hay tareas ${currentStatus === 'pending' ? 'pendientes' : ''}.</div>`;
            return;
        }
        this.dom.taskList.innerHTML = tasks.map(t => {
            const due = t.due_date ? `${t.due_date}${t.due_time ? ' ' + t.due_time : ''}` : '';
            return `
            <div class="task-item">
                <div class="task-info">
                    <div class="task-title ${t.status === 'completed' ? 'completed' : ''}">${this.esc(t.title)}</div>
                    ${due ? `<div class="task-due">${due}</div>` : ''}
                </div>
                <div class="task-actions">
                    ${t.status === 'pending' ? `<button class="complete-btn" onclick="JARVIS.completeTask(${t.id})">Completar</button>` : ''}
                    <button class="delete-btn" onclick="JARVIS.deleteTask(${t.id})">Borrar</button>
                </div>
            </div>`;
        }).join('');
    },

    async addTaskFromForm() {
        const title = document.getElementById('new-task-title').value.trim();
        if (!title) return;
        const date = document.getElementById('new-task-date').value || null;
        const time = document.getElementById('new-task-time').value || null;

        await fetch(`${API}/tasks`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, due_date: date, due_time: time })
        });
        document.getElementById('new-task-title').value = '';
        this.loadTasks();
    },

    async completeTask(id) {
        await fetch(`${API}/tasks/${id}/complete`, { method: 'POST' });
        this.loadTasks();
    },

    async deleteTask(id) {
        await fetch(`${API}/tasks/${id}`, { method: 'DELETE' });
        this.loadTasks();
    },

    // Chat
    addMessage(sender, text, actions) {
        const div = document.createElement('div');
        div.className = `message ${sender === 'jarvis' ? 'jarvis-msg' : 'user-msg'}`;
        let actionsHtml = '';
        let imageHtml = '';
        if (actions && actions.length) {
            const imageAction = actions.find(a => a.action === 'show_image');
            if (imageAction) {
                imageHtml = `<div class="generated-image-container"><img src="${imageAction.image_url}" class="generated-image" onclick="window.open('${imageAction.image_url}','_blank')"></div>`;
                this.showImageOverlay(imageAction.image_url);
            }
            const analysisAction = actions.find(a => a.action === 'show_analysis');
            if (analysisAction) {
                this.showAnalysisOverlay(
                    'Documento analizado',
                    analysisAction.analysis,
                    analysisAction.focus || 'general',
                    analysisAction.chars || text.length
                );
            }
            const otherActions = actions.filter(a => a.action !== 'show_image' && a.action !== 'show_analysis');
            if (otherActions.length) {
                actionsHtml = otherActions.map(a => `<span class="msg-action">${a.action}: ${a.url || a.app_name || a.title || ''}</span>`).join(' ');
            }
        }
        div.innerHTML = `
            <span class="msg-label">${sender === 'jarvis' ? 'JARVIS' : 'USUARIO'}</span>
            <span class="msg-text">${this.formatMsg(text)}</span>
            ${imageHtml}
            ${actionsHtml}
        `;
        this.dom.chatArea.appendChild(div);
        this.dom.chatArea.scrollTop = this.dom.chatArea.scrollHeight;
    },

    showImageOverlay(imageUrl) {
        const existing = document.getElementById('image-overlay');
        if (existing) existing.remove();
        const overlay = document.createElement('div');
        overlay.id = 'image-overlay';
        overlay.innerHTML = `
            <div class="image-overlay-backdrop">
                <div class="image-overlay-content">
                    <img src="${imageUrl}" class="image-overlay-img">
                    <div class="image-overlay-actions">
                        <button class="image-overlay-btn" onclick="window.open('${imageUrl}','_blank')">ABRIR</button>
                        <button class="image-overlay-btn" onclick="document.getElementById('image-overlay').remove()">CERRAR</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);
        overlay.querySelector('.image-overlay-backdrop').addEventListener('click', (e) => {
            if (e.target === e.currentTarget) overlay.remove();
        });
    },

    async uploadDocument(file) {
        console.log('[DOC] uploadDocument llamado:', file.name, file.size);
        const sizeMB = (file.size / 1024 / 1024).toFixed(1);

        this.reactorState = 'thinking';
        this.dom.arcReactor.classList.add('thinking');

        let elapsed = 0;
        const steps = ['EXTRAYENDO TEXTO...', 'ANALIZANDO CONTENIDO...', 'PROCESANDO SECCIONES...', 'GENERANDO ANALISIS COMPLETO...'];
        this.showDocProgress(file.name, sizeMB);
        const progressTimer = setInterval(() => {
            elapsed += 5;
            const step = steps[Math.floor(elapsed / 20) % steps.length];
            this.dom.statusText.textContent = `${step} (${elapsed}s)`;
            const progEl = document.getElementById('doc-progress-step');
            if (progEl) progEl.textContent = `${step} (${elapsed}s)`;
        }, 5000);

        const formData = new FormData();
        formData.append('file', file);

        try {
            console.log('[DOC] Enviando fetch a /api/analyze/upload...');
            const res = await fetch(`${API}/analyze/upload`, {
                method: 'POST',
                body: formData
            });
            console.log('[DOC] Respuesta recibida, status:', res.status);
            clearInterval(progressTimer);
            this.reactorState = 'idle';
            this.dom.arcReactor.classList.remove('thinking');
            this.dom.statusText.textContent = 'SISTEMA ACTIVO';

            const progressOverlay = document.getElementById('doc-progress-overlay');
            if (progressOverlay) progressOverlay.remove();

            const data = await res.json();
            console.log('[DOC] Data parseada, keys:', Object.keys(data));
            if (data.error) {
                this.addMessage('jarvis', data.error);
                this.speak(data.error);
            } else {
                console.log('[DOC] Mostrando overlay de analisis...');
                this.showAnalysisOverlay(data.filename, data.analysis, data.focus, data.chars);
                this.speak(`Listo señor, terminé el análisis de ${data.filename}. Puede verlo en pantalla.`);
            }
        } catch (e) {
            console.error('[DOC] Error en upload:', e);
            clearInterval(progressTimer);
            this.reactorState = 'idle';
            this.dom.arcReactor.classList.remove('thinking');
            this.dom.statusText.textContent = 'SISTEMA ACTIVO';

            const progressOverlay = document.getElementById('doc-progress-overlay');
            if (progressOverlay) progressOverlay.remove();

            this.addMessage('jarvis', 'Error analizando el documento. Puede que el servidor esté ocupado.');
            this.speak('Error analizando el documento.');
        }
    },

    showDocProgress(filename, sizeMB) {
        const existing = document.getElementById('doc-progress-overlay');
        if (existing) existing.remove();

        const overlay = document.createElement('div');
        overlay.id = 'doc-progress-overlay';
        overlay.innerHTML = `
            <div class="analysis-backdrop">
                <div class="analysis-panel" style="text-align:center;max-width:500px;">
                    <div class="analysis-header" style="justify-content:center;border-bottom:none;">
                        <div>
                            <h2 class="analysis-title">ANALIZANDO DOCUMENTO</h2>
                            <span class="analysis-meta">${this.esc(filename)} (${sizeMB}MB)</span>
                        </div>
                    </div>
                    <div class="analysis-body" style="text-align:center;padding:30px 24px;">
                        <div class="typing-indicator" style="justify-content:center;margin-bottom:20px;">
                            <span></span><span></span><span></span>
                        </div>
                        <p id="doc-progress-step" style="font-size:0.85rem;color:var(--warning);margin:12px 0;">EXTRAYENDO TEXTO... (0s)</p>
                        <p style="font-size:0.75rem;color:var(--text-dim);margin-top:16px;">
                            El analisis exhaustivo puede tardar 1-3 minutos.<br>
                            Se estan procesando TODAS las secciones del documento.
                        </p>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);
    },

    showAnalysisOverlay(filename, analysis, focus, chars) {
        const existing = document.getElementById('analysis-overlay');
        if (existing) existing.remove();

        const focusLabels = { legal: 'LEGAL', academico: 'ACADEMICO', cientifico: 'CIENTIFICO', noticioso: 'NOTICIOSO', general: 'GENERAL' };
        const focusLabel = focusLabels[focus] || 'GENERAL';
        const charsNum = typeof chars === 'number' ? chars : parseInt(chars) || 0;

        let formatted = this.esc(analysis);
        formatted = formatted.replace(/\n/g, '<br>');
        formatted = formatted.replace(/\*\*([^*]+?)\*\*/g, '<strong>$1</strong>');
        formatted = formatted.replace(/(▸\s*)(.+?)(<br>)/g, '<div class="analysis-section-title">$2</div>');

        const overlay = document.createElement('div');
        overlay.id = 'analysis-overlay';
        overlay.innerHTML = `
            <div class="analysis-backdrop">
                <div class="analysis-panel">
                    <div class="analysis-header">
                        <div>
                            <h2 class="analysis-title">${this.esc(filename)}</h2>
                            <span class="analysis-meta">${charsNum.toLocaleString()} caracteres · Enfoque: ${focusLabel}</span>
                        </div>
                        <button class="analysis-close-btn" onclick="document.getElementById('analysis-overlay').remove()">✕</button>
                    </div>
                    <div class="analysis-body">${formatted}</div>
                    <div class="analysis-footer">
                        <button class="analysis-action-btn" id="analysis-copy-btn">COPIAR ANALISIS</button>
                        <button class="analysis-action-btn" onclick="document.getElementById('analysis-overlay').remove()">CERRAR</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);

        overlay.querySelector('.analysis-backdrop').addEventListener('click', (e) => {
            if (e.target === e.currentTarget) overlay.remove();
        });

        document.getElementById('analysis-copy-btn').addEventListener('click', () => {
            navigator.clipboard.writeText(analysis).then(() => {
                document.getElementById('analysis-copy-btn').textContent = 'COPIADO!';
                setTimeout(() => { document.getElementById('analysis-copy-btn').textContent = 'COPIAR ANALISIS'; }, 2000);
            });
        });
    },

    addTyping() {
        const div = document.createElement('div');
        div.className = 'message jarvis-msg';
        div.id = 'typing';
        div.innerHTML = `<span class="msg-label">JARVIS</span><div class="typing-indicator"><span></span><span></span><span></span></div>`;
        this.dom.chatArea.appendChild(div);
        this.dom.chatArea.scrollTop = this.dom.chatArea.scrollHeight;
    },

    removeTyping() {
        const el = document.getElementById('typing');
        if (el) el.remove();
    },

    speak(text) {
        if (this.useEdgeTTS) {
            this.speakEdgeTTS(text);
        } else {
            this.speakBrowser(text);
        }
    },

    stopSpeaking() {
        this.synth.cancel();
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio.currentTime = 0;
            this.currentAudio = null;
        }
        this.ttsAborted = true;
        this.isSpeaking = false;
        if (!this.processingVideo) {
            this.reactorState = 'idle'; this.dom.arcReactor.classList.remove('speaking');
        }
        this.setWaveAmplitude(0);
    },

    speakBrowser(text) {
        this.synth.cancel();
        this.isSpeaking = true;
        this.ttsAborted = false;
        this.lastStateChange = Date.now();
        const u = new SpeechSynthesisUtterance(text);
        u.lang = 'es-AR';
        u.rate = 1;
        u.pitch = 0.9;
        if (this.selectedVoice) u.voice = this.selectedVoice;

        u.onstart = () => {
            if (!this.processingVideo) {
                this.reactorState = 'speaking'; this.dom.arcReactor.classList.add('speaking');
                this.dom.statusText.textContent = 'HABLANDO';
            }
            this.setWaveAmplitude(0.7);
        };
        u.onend = () => {
            if (!this.processingVideo) {
                this.reactorState = 'idle'; this.dom.arcReactor.classList.remove('speaking');
            }
            this.setWaveAmplitude(0);
            this.isSpeaking = false;
            this.finishSpeaking();
        };
        this.synth.speak(u);
    },

    ttsQueue: [],
    ttsPlaying: false,

    async speakEdgeTTS(text) {
        this.isSpeaking = true;
        this.ttsAborted = false;
        this.lastStateChange = Date.now();
        const sentences = text.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [text];
        const chunks = [];
        let current = '';
        for (const s of sentences) {
            if ((current + s).length > 300) {
                if (current) chunks.push(current.trim());
                current = s;
            } else {
                current += s;
            }
        }
        if (current.trim()) chunks.push(current.trim());

        if (!this.processingVideo) {
            this.reactorState = 'speaking'; this.dom.arcReactor.classList.add('speaking');
            this.dom.statusText.textContent = 'HABLANDO';
        }
        this.setWaveAmplitude(0.7);

        for (let i = 0; i < chunks.length; i++) {
            if (this.ttsAborted) break;
            try {
                const res = await fetch(`${API}/tts`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: chunks[i] })
                });
                if (!res.ok) { this.speakBrowser(chunks.slice(i).join(' ')); return; }

                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                await new Promise((resolve, reject) => {
                    const audio = new Audio(url);
                    this.currentAudio = audio;
                    audio.onended = () => { URL.revokeObjectURL(url); this.currentAudio = null; resolve(); };
                    audio.onerror = () => { URL.revokeObjectURL(url); this.currentAudio = null; reject(); };
                    audio.play();
                });
            } catch (e) {
                if (this.ttsAborted) break;
                this.speakBrowser(chunks.slice(i).join(' '));
                return;
            }
        }

        if (!this.ttsAborted) {
            if (!this.processingVideo) {
                this.reactorState = 'idle'; this.dom.arcReactor.classList.remove('speaking');
            }
            this.setWaveAmplitude(0);
            this.isSpeaking = false;
            this.finishSpeaking();
        }
    },

    finishSpeaking() {
        this.isSpeaking = false;
        this.commandListening = false;
        if (!this.processingVideo) {
            this.reactorState = 'idle';
            this.dom.arcReactor.classList.remove('speaking');
        }
        this.setWaveAmplitude(0);
        if (this.wakeWordRecog) {
            try { this.wakeWordRecog.abort(); } catch(e) {}
            this.wakeWordRecog = null;
        }
        this.wakeWordActive = false;

        if (this.conversationMode) {
            if (this._followUpRecog) {
                try { this._followUpRecog.abort(); } catch(e) {}
                this._followUpRecog = null;
            }
            setTimeout(() => {
                console.log('[Voice] Modo conversacion: escuchando siguiente comando');
                this.listenForFollowUp();
            }, 400);
        } else {
            if (!this.processingVideo) {
                this.dom.statusText.textContent = 'REINICIANDO MIC...';
            }
            setTimeout(() => {
                console.log('[Voice] Reiniciando wake word post-habla');
                this.startWakeWord();
            }, 500);
        }
    },

    startConversationMode() {
        this.conversationMode = true;
        if (this.conversationTimer) clearTimeout(this.conversationTimer);
        console.log('[Conversation] Modo conversacion activado');
    },

    endConversationMode() {
        this.conversationMode = false;
        if (this.conversationTimer) {
            clearTimeout(this.conversationTimer);
            this.conversationTimer = null;
        }
        console.log('[Conversation] Modo conversacion desactivado');
        this.commandListening = false;
        this.reactorState = 'idle';
        this.dom.arcReactor.classList.remove('listening');
        this.setWaveAmplitude(0);
        this.dom.statusText.textContent = 'ESCUCHANDO "HEY JARVIS"';
        this.playBeep();
        setTimeout(() => this.startWakeWord(), 500);
    },

    toggleSystem() {
        this.systemActive = !this.systemActive;
        const btn = this.dom.powerBtn;
        if (this.systemActive) {
            btn.classList.remove('off');
            btn.classList.add('on');
            document.querySelector('.hud-container').classList.remove('system-off');
            this.dom.statusText.textContent = 'SISTEMA ACTIVO';
            this.addMessage('jarvis', 'Sistema reactivado. Estoy a su disposicion, señor.');
            this.speak('Sistema reactivado.');
            setTimeout(() => this.startWakeWord(), 1000);
        } else {
            btn.classList.remove('on');
            btn.classList.add('off');
            document.querySelector('.hud-container').classList.add('system-off');
            this.stopSpeaking();
            if (this.conversationMode) {
                this.conversationMode = false;
                if (this.conversationTimer) { clearTimeout(this.conversationTimer); this.conversationTimer = null; }
            }
            if (this._followUpRecog) { try { this._followUpRecog.abort(); } catch(e) {} this._followUpRecog = null; }
            if (this.wakeWordRecog) { try { this.wakeWordRecog.abort(); } catch(e) {} this.wakeWordRecog = null; }
            this.wakeWordActive = false;
            this.commandListening = false;
            if (this.wakeWordRetryTimer) { clearTimeout(this.wakeWordRetryTimer); this.wakeWordRetryTimer = null; }
            this.reactorState = 'idle';
            this.dom.arcReactor.classList.remove('speaking', 'listening', 'thinking');
            this.setWaveAmplitude(0);
            this.dom.statusText.textContent = 'SISTEMA APAGADO';
        }
    },

    listenForFollowUp() {
        if (!this.conversationMode) return;
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) return;

        this.commandListening = true;
        this.lastStateChange = Date.now();
        this.reactorState = 'listening';
        this.dom.arcReactor.classList.add('listening');
        this.dom.statusText.textContent = 'CONVERSANDO...';
        this.setWaveAmplitude(0.4);

        this._resetSilenceTimer();

        const followUpRecog = new SR();
        followUpRecog.continuous = true;
        followUpRecog.interimResults = true;
        followUpRecog.lang = 'es-AR';
        this._followUpRecog = followUpRecog;

        followUpRecog.onresult = (e) => {
            this._resetSilenceTimer();

            for (let i = e.resultIndex; i < e.results.length; i++) {
                if (!e.results[i].isFinal) continue;

                let text = e.results[i][0].transcript;
                text = text.replace(/^(hey\s+)?(jarvis|yarvis|jarbis|jarves|charvis|garvis|jervis|tarvis)\s*/i, '').trim();
                console.log('[Conversation] Recibido:', text);
                if (!text) continue;

                if (this.conversationTimer) { clearTimeout(this.conversationTimer); this.conversationTimer = null; }
                try { followUpRecog.abort(); } catch(ex) {}
                this._followUpRecog = null;

                const endPhrases = ['gracias jarvis', 'gracias yarvis', 'gracias jarbis', 'listo jarvis', 'nada mas', 'nada más', 'eso es todo', 'chau jarvis', 'chau', 'anda a dormir', 'andá a dormir', 'andate a dormir'];
                const lower = text.toLowerCase().trim();
                if (endPhrases.some(p => lower.includes(p))) {
                    console.log('[Conversation] Frase de cierre detectada');
                    this.processInput(text);
                    setTimeout(() => this.endConversationMode(), 1000);
                    return;
                }

                this.processInput(text);
                return;
            }
        };

        followUpRecog.onend = () => {
            if (this.conversationMode && !this.isSpeaking) {
                console.log('[Conversation] Recognition ended, reiniciando...');
                setTimeout(() => {
                    if (this.conversationMode && !this.isSpeaking) {
                        this.listenForFollowUp();
                    }
                }, 300);
            }
        };

        followUpRecog.onerror = (e) => {
            if (e.error === 'no-speech') {
                console.log('[Conversation] No speech detectado');
                return;
            }
            if (e.error === 'aborted') return;
            console.log('[Conversation] Error:', e.error);
        };

        try {
            followUpRecog.start();
        } catch(e) {
            console.log('[Conversation] No se pudo iniciar mic:', e);
            this.endConversationMode();
        }
    },

    _resetSilenceTimer() {
        if (this.conversationTimer) clearTimeout(this.conversationTimer);
        this.conversationTimer = setTimeout(() => {
            console.log('[Conversation] Silencio de 5s, terminando conversacion');
            if (this._followUpRecog) {
                try { this._followUpRecog.abort(); } catch(e) {}
                this._followUpRecog = null;
            }
            this.endConversationMode();
        }, this.conversationSilenceMs);
    },

    speakDirect(text) {
        this.synth.cancel();
        const u = new SpeechSynthesisUtterance(text);
        u.lang = 'es-AR';
        u.rate = 1;
        u.pitch = 0.9;
        if (this.selectedVoice) u.voice = this.selectedVoice;
        this.synth.speak(u);
    },

    showFormatSelector(file) {
        const existing = document.querySelector('.video-results-overlay');
        if (existing) existing.remove();

        const sizeMB = (file.size / 1024 / 1024).toFixed(1);
        const overlay = document.createElement('div');
        overlay.className = 'video-results-overlay';
        overlay.innerHTML = `
            <div class="video-results-panel format-selector-panel">
                <h2>FORMATO DE CLIPS</h2>
                <p style="font-size:0.78rem;color:var(--text-dim);margin-bottom:16px;">
                    ${this.esc(file.name)} (${sizeMB}MB) — Elegí el formato para los clips:
                </p>
                <div class="format-options">
                    <div class="format-option selected" data-format="horizontal">
                        <div class="format-preview format-preview-h"><svg viewBox="0 0 64 36"><rect x="2" y="2" width="60" height="32" rx="3" fill="none" stroke="currentColor" stroke-width="2"/><polygon points="24,10 24,26 42,18" fill="currentColor" opacity="0.6"/></svg></div>
                        <div class="format-label">HORIZONTAL</div>
                        <div class="format-ratio">16:9</div>
                    </div>
                    <div class="format-option" data-format="vertical">
                        <div class="format-preview format-preview-v"><svg viewBox="0 0 36 64"><rect x="2" y="2" width="32" height="60" rx="3" fill="none" stroke="currentColor" stroke-width="2"/><polygon points="12,24 12,40 24,32" fill="currentColor" opacity="0.6"/></svg></div>
                        <div class="format-label">VERTICAL</div>
                        <div class="format-ratio">9:16</div>
                    </div>
                    <div class="format-option" data-format="square">
                        <div class="format-preview format-preview-sq"><svg viewBox="0 0 48 48"><rect x="2" y="2" width="44" height="44" rx="3" fill="none" stroke="currentColor" stroke-width="2"/><polygon points="18,14 18,34 34,24" fill="currentColor" opacity="0.6"/></svg></div>
                        <div class="format-label">CUADRADO</div>
                        <div class="format-ratio">1:1</div>
                    </div>
                </div>
                <div style="display:flex;gap:8px;margin-top:20px;">
                    <button class="video-close-btn format-start-btn" style="flex:2;">PROCESAR VIDEO</button>
                    <button class="video-close-btn format-cancel-btn" style="flex:1;border-color:var(--text-dim);color:var(--text-dim);">CANCELAR</button>
                </div>
            </div>`;

        let selectedFormat = 'horizontal';
        overlay.querySelectorAll('.format-option').forEach(opt => {
            opt.addEventListener('click', () => {
                overlay.querySelectorAll('.format-option').forEach(o => o.classList.remove('selected'));
                opt.classList.add('selected');
                selectedFormat = opt.dataset.format;
            });
        });
        overlay.querySelector('.format-start-btn').addEventListener('click', () => {
            overlay.remove();
            this.uploadVideo(file, selectedFormat);
        });
        overlay.querySelector('.format-cancel-btn').addEventListener('click', () => overlay.remove());
        overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
        document.body.appendChild(overlay);
    },

    async uploadVideo(file, clipFormat = 'horizontal') {
        const sizeMB = (file.size / 1024 / 1024).toFixed(1);
        this.processingVideo = true;
        this.reactorState = 'thinking'; this.dom.arcReactor.classList.add('thinking');
        this.dom.statusText.textContent = 'PROCESANDO VIDEO...';

        this.speakDirect(`Recibido. Estoy procesando el video. Esto puede tardar unos minutos.`);

        this.showVideoProgress(file.name, sizeMB);

        const steps = ['EXTRAYENDO AUDIO...', 'TRANSCRIBIENDO...', 'ANALIZANDO CLIPS...', 'PROCESANDO VIDEO...'];
        let stepIdx = 0;
        let elapsed = 0;
        const progressInterval = setInterval(() => {
            stepIdx = (stepIdx + 1) % steps.length;
            elapsed += 8;
            this.dom.statusText.textContent = steps[stepIdx];
            const progEl = document.getElementById('video-progress-step');
            if (progEl) progEl.textContent = `${steps[stepIdx]} (${elapsed}s)`;
        }, 8000);

        const formData = new FormData();
        formData.append('video', file);
        formData.append('clips', 'true');
        formData.append('format', clipFormat);

        try {
            const res = await fetch(`${API}/video/upload`, {
                method: 'POST',
                body: formData
            });
            clearInterval(progressInterval);
            this.processingVideo = false;
            this.reactorState = 'idle'; this.dom.arcReactor.classList.remove('thinking');
            this.dom.statusText.textContent = 'SISTEMA ACTIVO';

            const overlay = document.querySelector('.video-results-overlay');
            if (overlay) overlay.remove();

            const data = await res.json();
            if (data.error) {
                this.dom.statusText.textContent = 'ERROR EN VIDEO';
                this.speakDirect('Hubo un error procesando el video.');
                setTimeout(() => { this.dom.statusText.textContent = 'SISTEMA ACTIVO'; }, 5000);
                return;
            }

            this.showVideoResults(file.name, data);
            this.speakDirect(`Listo. Transcribí el video de ${Math.round(data.duration)} segundos. ${data.clips?.length ? `Encontré ${data.clips.length} clips interesantes.` : ''}`);

            this.lastVideoResult = data;
            this.lastVideoFilename = file.name;
            document.getElementById('video-results-btn').style.display = '';
            try {
                await fetch(`${API}/chat`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: `[SISTEMA] El usuario subió el video "${file.name}" (${sizeMB}MB). Transcripción: "${data.full_text.substring(0, 500)}${data.full_text.length > 500 ? '...' : ''}". ${data.clips?.length ? `Se generaron ${data.clips.length} clips.` : 'No se generaron clips.'} Los clips están en jarvis/clips/. Ya le mostré los resultados al usuario.` })
                });
            } catch(e) {}

        } catch (e) {
            clearInterval(progressInterval);
            this.processingVideo = false;
            this.reactorState = 'idle'; this.dom.arcReactor.classList.remove('thinking');
            this.dom.statusText.textContent = 'SISTEMA ACTIVO';
            const overlay = document.querySelector('.video-results-overlay');
            if (overlay) overlay.remove();
            this.speakDirect('Error de conexión procesando el video.');
            console.error('[Video] Upload error:', e);
        }
    },

    showVideoProgress(filename, sizeMB) {
        const existing = document.querySelector('.video-results-overlay');
        if (existing) existing.remove();

        const overlay = document.createElement('div');
        overlay.className = 'video-results-overlay';
        overlay.innerHTML = `
            <div class="video-results-panel" style="text-align:center;">
                <h2>PROCESANDO VIDEO</h2>
                <p style="font-size:0.82rem;color:var(--text);margin:12px 0;">${this.esc(filename)} (${sizeMB}MB)</p>
                <div style="margin:24px 0;">
                    <div class="typing-indicator" style="justify-content:center;">
                        <span></span><span></span><span></span>
                    </div>
                </div>
                <p id="video-progress-step" style="font-size:0.78rem;color:var(--warning);margin:12px 0;">PROCESANDO VIDEO... (0s)</p>
                <p style="font-size:0.72rem;color:var(--text-dim);margin-top:16px;">Esto puede tardar varios minutos.<br>No cierres esta ventana.</p>
            </div>`;
        document.body.appendChild(overlay);
    },

    showVideoResults(filename, data) {
        const existing = document.querySelector('.video-results-overlay');
        if (existing) existing.remove();

        const overlay = document.createElement('div');
        overlay.className = 'video-results-overlay';
        const fmtTime = (s) => { const m = Math.floor(s/60); const sec = Math.floor(s%60); return `${m}:${sec.toString().padStart(2,'0')}`; };
        const cf = data.clip_format || 'horizontal';
        const formatLabels = { horizontal: 'HORIZONTAL 16:9', vertical: 'VERTICAL 9:16', square: 'CUADRADO 1:1' };
        const previewClass = cf === 'vertical' ? 'clip-preview-vertical' : cf === 'square' ? 'clip-preview-square' : '';

        let clipsHtml = '';
        if (data.clips && data.clips.length > 0) {
            clipsHtml = `<h3>CLIPS GENERADOS (${data.clips.length}) — ${formatLabels[cf] || cf.toUpperCase()}</h3>
                <div class="video-clips-grid ${cf === 'vertical' ? 'clips-grid-vertical' : ''}">`;
            for (let i = 0; i < data.clips.length; i++) {
                const clip = data.clips[i];
                const clipUrl = clip.filename ? `${API.replace('/api','')}/api/video/clips/${encodeURIComponent(clip.filename)}` : '';
                clipsHtml += `
                    <div class="video-clip-card">
                        <div class="video-clip-preview ${previewClass}" data-clip-idx="${i}">
                            ${clipUrl ? `<video class="clip-video" src="${clipUrl}" preload="metadata"></video>` : ''}
                            <div class="clip-play-btn">&#9654;</div>
                        </div>
                        <div class="video-clip-info">
                            <div class="video-clip-title">${this.esc(clip.title || 'Clip ' + (i+1))}</div>
                            <div class="video-clip-time">${fmtTime(clip.start)} - ${fmtTime(clip.end)}</div>
                            <div class="video-clip-reason">${this.esc(clip.reason || '')}</div>
                            ${clipUrl ? `<a href="${clipUrl}" download class="clip-download-btn">DESCARGAR</a>` : ''}
                        </div>
                    </div>`;
            }
            clipsHtml += `</div>
                <p style="font-size:0.72rem;color:var(--text-dim);margin-top:8px;">Clips guardados en: jarvis/clips/</p>`;
        }

        overlay.innerHTML = `
            <div class="video-results-panel">
                <h2>VIDEO PROCESADO: ${this.esc(filename)}</h2>
                <p style="font-size:0.78rem;color:var(--text-dim);margin-bottom:12px;">Duración: ${fmtTime(data.duration)} (${Math.round(data.duration)}s)</p>
                <h3>TRANSCRIPCIÓN</h3>
                <div class="video-transcript">${this.esc(data.full_text)}</div>
                ${clipsHtml}
                <div style="display:flex;gap:8px;margin-top:16px;">
                    <button class="video-close-btn video-copy-btn" style="flex:1;">COPIAR TRANSCRIPCIÓN</button>
                    <button class="video-close-btn video-close-final" style="flex:1;">CERRAR</button>
                </div>
            </div>`;

        overlay.querySelectorAll('.video-clip-preview').forEach(prev => {
            prev.addEventListener('click', () => {
                const video = prev.querySelector('.clip-video');
                const btn = prev.querySelector('.clip-play-btn');
                if (!video) return;
                if (video.paused) {
                    overlay.querySelectorAll('.clip-video').forEach(v => {
                        v.pause();
                        v.removeAttribute('controls');
                        v.closest('.video-clip-preview').querySelector('.clip-play-btn').style.display = '';
                    });
                    video.setAttribute('controls', '');
                    btn.style.display = 'none';
                    video.play();
                } else {
                    video.pause();
                    video.removeAttribute('controls');
                    btn.style.display = '';
                }
            });
        });
        overlay.querySelectorAll('.clip-video').forEach(v => {
            v.addEventListener('ended', () => {
                v.removeAttribute('controls');
                v.closest('.video-clip-preview').querySelector('.clip-play-btn').style.display = '';
            });
        });
        overlay.querySelector('.video-copy-btn').addEventListener('click', () => {
            navigator.clipboard.writeText(data.full_text).then(() => {
                const btn = overlay.querySelector('.video-copy-btn');
                btn.textContent = 'COPIADO!';
                setTimeout(() => { btn.textContent = 'COPIAR TRANSCRIPCIÓN'; }, 2000);
            });
        });
        overlay.querySelector('.video-close-final').addEventListener('click', () => overlay.remove());
        overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
        document.body.appendChild(overlay);

        try { localStorage.setItem('jarvis_last_video', JSON.stringify({ filename, data })); } catch(e) {}
    },

    reopenVideoResults() {
        if (this.lastVideoResult && this.lastVideoFilename) {
            this.showVideoResults(this.lastVideoFilename, this.lastVideoResult);
            return;
        }
        try {
            const saved = JSON.parse(localStorage.getItem('jarvis_last_video'));
            if (saved) {
                this.showVideoResults(saved.filename, saved.data);
                return;
            }
        } catch(e) {}
        this.speakDirect('No hay resultados de video para mostrar.');
    },

    async processInput(text) {
        // Comando directo para setear API key desde el chat
        if (text.startsWith('/key ')) {
            const key = text.replace('/key ', '').trim();
            this.addMessage('user', '/key ••••••••');
            try {
                const res = await fetch(`${API}/config/api-key`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ key })
                });
                const data = await res.json();
                if (data.success) {
                    this.addMessage('jarvis', 'API Key guardada. Probando conexion...');
                    const test = await fetch(`${API}/config/test-key`, { method: 'POST' });
                    const testData = await test.json();
                    if (testData.working_model) {
                        this.addMessage('jarvis', `Conexion exitosa con modelo ${testData.working_model}. Estoy listo, señor.`);
                        this.speak('Conexión exitosa. Estoy listo, señor.');
                    } else {
                        const errors = testData.results.map(r => `${r.model}: ${r.status}`).join('\n');
                        this.addMessage('jarvis', `La key se guardo pero ningun modelo responde. Resultados:\n${errors}`);
                    }
                    this.loadConfig();
                } else {
                    this.addMessage('jarvis', `Error: ${data.error}`);
                }
            } catch (e) {
                this.addMessage('jarvis', 'Error guardando la key.');
            }
            return;
        }

        // Comando para configurar Gmail con App Password
        if (text.startsWith('/gmail ')) {
            const parts = text.replace('/gmail ', '').trim().split(/\s+/);
            if (parts.length < 2) {
                this.addMessage('user', '/gmail ...');
                this.addMessage('jarvis', 'Uso: /gmail tu@gmail.com tu-app-password\nEl App Password lo generas en myaccount.google.com/apppasswords');
                return;
            }
            const address = parts[0];
            const app_password = parts.slice(1).join(' ');
            this.addMessage('user', `/gmail ${address} ••••••••`);
            this.addMessage('jarvis', 'Configurando Gmail...');
            try {
                const res = await fetch(`${API}/gmail/setup`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ address, app_password })
                });
                const data = await res.json();
                if (data.success) {
                    this.addMessage('jarvis', 'Gmail conectado exitosamente, señor. Ya puedo leer y enviar emails.');
                    this.speak('Gmail conectado exitosamente.');
                } else {
                    this.addMessage('jarvis', `Error conectando Gmail: ${data.error}`);
                }
                this.loadConfig();
            } catch (e) {
                this.addMessage('jarvis', 'Error de conexion con el servidor.');
            }
            return;
        }

        // Comando para configurar WhatsApp (Green API)
        if (text.startsWith('/whatsapp ')) {
            const parts = text.replace('/whatsapp ', '').trim().split(/\s+/);
            if (parts.length < 2) {
                this.addMessage('user', '/whatsapp ...');
                this.addMessage('jarvis', 'Uso: /whatsapp ID_INSTANCE API_TOKEN [API_URL]\nEjemplo: /whatsapp 710722758026 abc123token https://7107.api.greenapi.com\nObtené estos datos en green-api.com');
                return;
            }
            const instanceId = parts[0];
            const apiToken = parts[1];
            const apiUrl = parts[2] || '';
            this.addMessage('user', '/whatsapp ••••••••');
            try {
                const res = await fetch(`${API}/config/whatsapp`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ instance_id: instanceId, token: apiToken, api_url: apiUrl })
                });
                const data = await res.json();
                if (data.success) {
                    this.addMessage('jarvis', 'WhatsApp conectado exitosamente, señor. Ya puedo enviar y leer mensajes.');
                    this.speak('WhatsApp conectado exitosamente.');
                } else {
                    this.addMessage('jarvis', `Error: ${data.error}`);
                }
                this.loadConfig();
            } catch (e) {
                this.addMessage('jarvis', 'Error de conexion con el servidor.');
            }
            return;
        }

        // Comando para configurar Google Calendar
        if (text.startsWith('/calendar ')) {
            const calUrl = text.replace('/calendar ', '').trim();
            this.addMessage('user', '/calendar ••••••••');
            try {
                const res = await fetch(`${API}/config/calendar`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: calUrl })
                });
                const data = await res.json();
                if (data.success) {
                    this.addMessage('jarvis', 'Google Calendar configurado, señor. Ya puedo ver sus eventos.');
                    this.speak('Google Calendar configurado exitosamente.');
                } else {
                    this.addMessage('jarvis', `Error: ${data.error}`);
                }
            } catch (e) {
                this.addMessage('jarvis', 'Error configurando calendario.');
            }
            return;
        }

        const endPhrases = ['gracias jarvis', 'gracias yarvis', 'gracias jarbis', 'gracias', 'listo jarvis', 'nada mas', 'nada más', 'eso es todo', 'chau jarvis', 'chau', 'anda a dormir', 'andá a dormir', 'andate a dormir'];
        const lowerText = text.toLowerCase().trim();
        const isEndPhrase = this.conversationMode && endPhrases.some(p => lowerText.includes(p));

        this.addMessage('user', text);
        this.addTyping();
        this.reactorState = 'thinking'; this.dom.arcReactor.classList.add('thinking');
        this.setWaveAmplitude(0.3);
        this.dom.statusText.textContent = 'PROCESANDO';

        try {
            const res = await fetch(`${API}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text })
            });

            this.removeTyping();
            this.reactorState = 'idle'; this.dom.arcReactor.classList.remove('thinking');

            const data = await res.json();

            if (data.error) {
                this.addMessage('jarvis', data.error);
                this.speak(data.error);
            } else {
                this.addMessage('jarvis', data.text, data.actions);
                if (isEndPhrase) {
                    this.conversationMode = false;
                    if (this.conversationTimer) { clearTimeout(this.conversationTimer); this.conversationTimer = null; }
                }
                this.speak(data.text);
                this.loadConfig();
            }
        } catch (e) {
            this.removeTyping();
            this.reactorState = 'idle'; this.dom.arcReactor.classList.remove('thinking');
            this.setWaveAmplitude(0);
            this.dom.statusText.textContent = 'SISTEMA ACTIVO';
            this.addMessage('jarvis', 'Error de conexion. Asegurate que el servidor esta corriendo (python server.py)');
        }
    },

    async loadHistory() {
        try {
            const res = await fetch(`${API}/history?limit=30`);
            const messages = await res.json();
            if (messages && messages.length > 0) {
                this.dom.chatArea.innerHTML = '';
                messages.forEach(m => {
                    this.addMessage(m.role === 'assistant' ? 'jarvis' : 'user', m.content);
                });
                this.checkDailyBriefing(messages);
            } else {
                this.requestBriefing();
            }
        } catch (e) {
            // Si falla, se queda con el mensaje default
        }
    },

    checkDailyBriefing(messages) {
        const today = new Date().toLocaleDateString('es-AR');
        const lastBriefing = localStorage.getItem('jarvis_last_briefing');
        if (lastBriefing !== today) {
            this.requestBriefing();
        }
    },

    async requestBriefing() {
        const today = new Date().toLocaleDateString('es-AR');
        try { localStorage.setItem('jarvis_last_briefing', today); } catch(e) {}
        const h = new Date().getHours();
        const saludo = h < 6 ? 'buenas noches' : h < 12 ? 'buenos dias' : h < 19 ? 'buenas tardes' : 'buenas noches';
        this.processInput(`Dame un briefing rapido: decime ${saludo}, el clima actual, una noticia importante de hoy, mis tareas pendientes, y si tengo emails nuevos. Se breve y conciso.`);
    },

    updateGreeting() {
        const h = new Date().getHours();
        let g = h < 6 ? 'Buenas noches' : h < 12 ? 'Buenos dias' : h < 19 ? 'Buenas tardes' : 'Buenas noches';
        const first = this.dom.chatArea.querySelector('.jarvis-msg .msg-text');
        if (first) first.textContent = `Sistema inicializado. ${g}, señor. ¿En qué puedo ayudarle?`;
    },

    // Wake Word: "Hey Jarvis"
    startWakeWord() {
        if (!this.systemActive) return;
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR || this.commandListening) return;

        if (this.wakeWordRetryTimer) {
            clearTimeout(this.wakeWordRetryTimer);
            this.wakeWordRetryTimer = null;
        }

        if (this.wakeWordRecog) {
            try { this.wakeWordRecog.abort(); } catch(e) {}
            this.wakeWordRecog = null;
        }

        this.wakeWordRestartCount++;
        const delay = Math.min(this.wakeWordRestartCount * 200, 3000);

        const recog = new SR();
        recog.continuous = true;
        recog.interimResults = true;
        recog.lang = 'es-AR';

        recog.onresult = (e) => {
            this.wakeWordLastEvent = Date.now();
            this.wakeWordRestartCount = 0;
            for (let i = e.resultIndex; i < e.results.length; i++) {
                const t = e.results[i][0].transcript.toLowerCase().trim();
                const wakeWords = ['jarvis', 'yarvis', 'jarvi', 'jarbis', 'jarby', 'jarbi', 'charvis', 'jarves', 'jarvas', 'yarbis', 'jarvys', 'har vis', 'jar vis', 'jervis', 'tarvis', 'jarbus', 'jarbes', 'jarbi', 'jarbys', 'javis', 'garvis', 'arvis', 'arviz', 'jarbiz'];
                if (wakeWords.some(w => t.includes(w)) && !this.commandListening) {
                    console.log('[WakeWord] Detectado:', t);
                    if (this.isSpeaking) {
                        this.stopSpeaking();
                    }
                    this.activateCommand();
                    return;
                }
            }
        };

        recog.onend = () => {
            this.wakeWordActive = false;
            this.wakeWordLastEvent = Date.now();
            if (!this.commandListening && !this.isSpeaking) {
                const retryDelay = Math.min(500 + this.wakeWordRestartCount * 300, 3000);
                this.wakeWordRetryTimer = setTimeout(() => this.startWakeWord(), retryDelay);
            }
        };

        recog.onerror = (e) => {
            this.wakeWordActive = false;
            this.wakeWordLastEvent = Date.now();
            if (e.error === 'not-allowed') {
                console.log('[WakeWord] Microfono bloqueado, reintentando en 10s...');
                this.dom.statusText.textContent = 'MIC BLOQUEADO - Permitir microfono';
                this.wakeWordActive = true;
                this.wakeWordLastEvent = Date.now();
                this.wakeWordRetryTimer = setTimeout(() => {
                    this.wakeWordActive = false;
                    this.startWakeWord();
                }, 10000);
                return;
            }
            if (e.error !== 'no-speech' && e.error !== 'aborted') {
                console.log('[WakeWord] error:', e.error);
            }
        };

        this.wakeWordRecog = recog;

        try {
            recog.start();
            this.wakeWordActive = true;
            this.wakeWordLastEvent = Date.now();
            if (!this.processingVideo) this.dom.statusText.textContent = 'ESCUCHANDO "HEY JARVIS"';
        } catch(e) {
            console.log('[WakeWord] start failed, retrying...', e);
            this.wakeWordActive = false;
            this.wakeWordRetryTimer = setTimeout(() => this.startWakeWord(), delay);
        }
    },

    activateCommand() {
        this.commandListening = true;
        this.lastStateChange = Date.now();
        if (this.wakeWordRetryTimer) {
            clearTimeout(this.wakeWordRetryTimer);
            this.wakeWordRetryTimer = null;
        }
        if (this.wakeWordRecog) {
            try { this.wakeWordRecog.abort(); } catch(e) {}
        }
        this.wakeWordActive = false;

        this.startConversationMode();

        this.reactorState = 'listening'; this.dom.arcReactor.classList.add('listening');
        this.dom.statusText.textContent = 'ESCUCHANDO COMANDO...';
        this.setWaveAmplitude(0.5);
        this.playBeep();

        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        const cmd = new SR();
        cmd.continuous = false;
        cmd.interimResults = false;
        cmd.lang = 'es-AR';

        cmd.onresult = (e) => {
            let text = e.results[0][0].transcript;
            text = text.replace(/^(hey\s+)?(jarvis|yarvis|jarbis|jarves|charvis|garvis|jervis|tarvis)\s*/i, '').trim();
            if (text) {
                this.processInput(text);
            }
        };

        cmd.onend = () => {
            this.commandListening = false;
            this.reactorState = 'idle'; this.dom.arcReactor.classList.remove('listening');
            this.setWaveAmplitude(0);
            if (!this.isSpeaking && !this.conversationMode) {
                if (!this.processingVideo) this.dom.statusText.textContent = 'ESCUCHANDO "HEY JARVIS"';
                setTimeout(() => this.startWakeWord(), 500);
            }
        };

        cmd.onerror = () => {
            this.commandListening = false;
            this.reactorState = 'idle'; this.dom.arcReactor.classList.remove('listening');
            this.setWaveAmplitude(0);
            if (!this.isSpeaking && !this.conversationMode) {
                if (!this.processingVideo) this.dom.statusText.textContent = 'ESCUCHANDO "HEY JARVIS"';
                setTimeout(() => this.startWakeWord(), 500);
            }
        };

        cmd.start();
    },

    startProactivePolling() {
        setInterval(async () => {
            try {
                const res = await fetch(`${API}/proactive`);
                const data = await res.json();
                if (data.messages && data.messages.length > 0) {
                    for (const msg of data.messages) {
                        this.addMessage('jarvis', msg.text);
                        this.speak(msg.text);
                    }
                }
            } catch(e) {}
        }, 30000);
    },

    playBeep() {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.frequency.value = 880;
            gain.gain.value = 0.2;
            osc.start();
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2);
            osc.stop(ctx.currentTime + 0.2);
        } catch(e) {}
    },

    esc(str) {
        const d = document.createElement('div');
        d.textContent = str;
        return d.innerHTML;
    },

    formatMsg(str) {
        let escaped = this.esc(str);
        escaped = escaped.replace(/\n/g, '<br>');
        escaped = escaped.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        return escaped;
    },

    connectionIcons: {
        claude: `<svg viewBox="0 0 24 24" fill="none"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 15l-1.5-1.5L13 12l-3.5-3.5L11 7l5 5-5 5z" fill="#D97706"/></svg>`,
        chrome: `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="none" stroke="#4285F4" stroke-width="1.5"/><circle cx="12" cy="12" r="4" fill="none" stroke="#4285F4" stroke-width="1.5"/><path d="M12 8L20 8" stroke="#EA4335" stroke-width="1.5"/><path d="M8 16L4 9" stroke="#34A853" stroke-width="1.5"/><path d="M16 16L8 16" stroke="#FBBC05" stroke-width="1.5"/></svg>`,
        windows: `<svg viewBox="0 0 24 24"><path d="M3 5.5l7.5-1v7H3V5.5zm0 13l7.5 1v-7H3v6zm8.5 1.2L21.5 21V12.5H11.5v7.2zm0-15.4v7.2h10V3l-10 1.3z" fill="#00A4EF"/></svg>`,
        whatsapp: `<svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12c0 1.77.46 3.43 1.27 4.88L2 22l5.23-1.23A9.96 9.96 0 0012 22c5.52 0 10-4.48 10-10S17.52 2 12 2zm.01 18c-1.61 0-3.13-.43-4.45-1.18l-.32-.17-3.1.73.78-2.97-.2-.33A7.96 7.96 0 014 12c0-4.41 3.59-8 8-8s8 3.59 8 8-3.59 8-8 8zm4.36-5.95c-.24-.12-1.42-.7-1.64-.78-.22-.08-.38-.12-.54.12-.16.24-.62.78-.76.94-.14.16-.28.18-.52.06-.24-.12-1.01-.37-1.93-1.18-.71-.63-1.19-1.41-1.33-1.65-.14-.24-.02-.37.1-.49.11-.11.24-.28.36-.42.12-.14.16-.24.24-.4.08-.16.04-.3-.02-.42-.06-.12-.54-1.3-.74-1.78-.2-.47-.4-.41-.54-.41h-.46c-.16 0-.42.06-.64.3-.22.24-.84.82-.84 2s.86 2.32.98 2.48c.12.16 1.7 2.6 4.12 3.64.58.25 1.03.4 1.38.51.58.18 1.1.16 1.52.1.46-.07 1.42-.58 1.62-1.14.2-.56.2-1.04.14-1.14-.06-.1-.22-.16-.46-.28z" fill="#25D366"/></svg>`,
        youtube: `<svg viewBox="0 0 24 24"><path d="M21.58 7.19a2.51 2.51 0 00-1.77-1.77C18.25 5 12 5 12 5s-6.25 0-7.81.42A2.51 2.51 0 002.42 7.19 26.37 26.37 0 002 12a26.37 26.37 0 00.42 4.81 2.51 2.51 0 001.77 1.77C5.75 19 12 19 12 19s6.25 0 7.81-.42a2.51 2.51 0 001.77-1.77A26.37 26.37 0 0022 12a26.37 26.37 0 00-.42-4.81zM10 15V9l5.2 3-5.2 3z" fill="#FF0000"/></svg>`,
        spotify: `<svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.56 14.46a.62.62 0 01-.86.21c-2.34-1.43-5.29-1.76-8.77-.96a.62.62 0 11-.28-1.21c3.81-.87 7.08-.5 9.7 1.1a.63.63 0 01.21.86zm1.22-2.73a.78.78 0 01-1.07.26c-2.68-1.65-6.76-2.13-9.93-1.16a.78.78 0 11-.45-1.5c3.62-1.1 8.12-.57 11.19 1.33a.78.78 0 01.26 1.07zm.1-2.84C14.74 8.87 9.16 8.7 5.97 9.66a.94.94 0 11-.54-1.8C9.02 6.8 15.17 7 18.76 9.26a.94.94 0 01-.88 1.63z" fill="#1DB954"/></svg>`,
        gmail: `<svg viewBox="0 0 24 24"><path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z" fill="#EA4335"/></svg>`,
        together: `<svg viewBox="0 0 24 24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" fill="#6366F1"/></svg>`,
        calendar: `<svg viewBox="0 0 24 24"><path d="M19 3h-1V1h-2v2H8V1H6v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V8h14v11z" fill="#4285F4"/><path d="M7 10h5v5H7z" fill="#4285F4" opacity="0.4"/></svg>`,
        telegram: `<svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69.01-.03.01-.14-.07-.2-.08-.06-.19-.04-.27-.02-.12.03-1.97 1.25-5.56 3.69-.53.36-1 .54-1.42.53-.47-.01-1.37-.26-2.03-.48-.82-.27-1.47-.42-1.42-.88.03-.24.37-.49 1.02-.74 3.98-1.73 6.63-2.87 7.97-3.44 3.8-1.58 4.58-1.85 5.09-1.86.11 0 .37.03.54.17.14.12.18.28.2.46-.01.06.01.24 0 .38z" fill="#229ED9"/></svg>`,
        notion: `<svg viewBox="0 0 24 24"><path d="M4 4.5A2.5 2.5 0 016.5 2h8.84a2.5 2.5 0 011.77.73l2.66 2.66a2.5 2.5 0 01.73 1.77V19.5a2.5 2.5 0 01-2.5 2.5h-12A2.5 2.5 0 014 19.5v-15z" fill="none" stroke="#999" stroke-width="1.5"/><path d="M8 7h8M8 11h8M8 15h5" stroke="#999" stroke-width="1.5" stroke-linecap="round"/></svg>`,
        drive: `<svg viewBox="0 0 24 24"><path d="M7.71 3.5L1.15 15l3.43 5.93h6.56L4.58 9.43 7.71 3.5zm1.72 0l6.56 11.5H22l-3.43-5.93L12.01 3.5H9.43zm5.15 12.5H8.02L4.58 21.93h13.13L21.15 16h-6.57z" fill="#FBBC05"/><path d="M7.71 3.5L1.15 15l3.43 5.93 6.56-11.5L7.71 3.5z" fill="#0066DA"/><path d="M15.86 3.5L9.43 3.5l6.57 12.5h6.15l-3.43-5.93L15.86 3.5z" fill="#00AC47"/></svg>`,
        discord: `<svg viewBox="0 0 24 24"><path d="M20.32 4.37a19.8 19.8 0 00-4.93-1.52.07.07 0 00-.08.04c-.21.38-.45.87-.61 1.26a18.27 18.27 0 00-5.41 0 12.6 12.6 0 00-.62-1.26.08.08 0 00-.08-.04 19.74 19.74 0 00-4.93 1.52.07.07 0 00-.03.03C1.16 8.55.5 12.58.87 16.56a.08.08 0 00.03.06 19.9 19.9 0 005.99 3.03.08.08 0 00.08-.03c.46-.63.87-1.3 1.22-2a.08.08 0 00-.04-.11 13.1 13.1 0 01-1.87-.9.08.08 0 01-.01-.13c.13-.09.25-.19.37-.29a.07.07 0 01.08-.01c3.93 1.8 8.18 1.8 12.07 0a.07.07 0 01.08.01c.12.1.25.2.37.29a.08.08 0 01-.01.13c-.6.35-1.22.65-1.87.9a.08.08 0 00-.04.11c.36.7.77 1.37 1.22 2a.08.08 0 00.08.03 19.83 19.83 0 006-3.03.08.08 0 00.03-.06c.44-4.54-.73-8.53-3.1-12.16a.06.06 0 00-.03-.03zM8.02 14.09c-1.05 0-1.92-.97-1.92-2.16s.85-2.16 1.92-2.16c1.08 0 1.93.98 1.92 2.16 0 1.19-.85 2.16-1.92 2.16zm7.1 0c-1.06 0-1.92-.97-1.92-2.16s.85-2.16 1.92-2.16c1.08 0 1.93.98 1.92 2.16 0 1.19-.84 2.16-1.92 2.16z" fill="#5865F2"/></svg>`,
        slack: `<svg viewBox="0 0 24 24"><path d="M5.04 15.16a2.12 2.12 0 01-2.12 2.13 2.12 2.12 0 01-2.13-2.13 2.12 2.12 0 012.13-2.12h2.12v2.12zm1.07 0a2.12 2.12 0 012.12-2.12 2.12 2.12 0 012.13 2.12v5.31a2.12 2.12 0 01-2.13 2.13 2.12 2.12 0 01-2.12-2.13v-5.3z" fill="#E01E5A"/><path d="M8.23 5.04a2.12 2.12 0 01-2.12-2.13A2.12 2.12 0 018.23.79a2.12 2.12 0 012.13 2.12v2.13H8.23zm0 1.08a2.12 2.12 0 012.13 2.12 2.12 2.12 0 01-2.13 2.13H2.92A2.12 2.12 0 01.79 8.24a2.12 2.12 0 012.13-2.12h5.3z" fill="#36C5F0"/><path d="M18.17 8.24a2.12 2.12 0 012.12-2.12 2.12 2.12 0 012.13 2.12 2.12 2.12 0 01-2.13 2.13h-2.12V8.24zm-1.07 0a2.12 2.12 0 01-2.12 2.13 2.12 2.12 0 01-2.13-2.13V2.92A2.12 2.12 0 0114.98.79a2.12 2.12 0 012.12 2.13v5.32z" fill="#2EB67D"/><path d="M14.98 18.17a2.12 2.12 0 012.12 2.12 2.12 2.12 0 01-2.12 2.13 2.12 2.12 0 01-2.13-2.13v-2.12h2.13zm0-1.07a2.12 2.12 0 01-2.13-2.12 2.12 2.12 0 012.13-2.13h5.3a2.12 2.12 0 012.13 2.13 2.12 2.12 0 01-2.12 2.12h-5.31z" fill="#ECB22E"/></svg>`,
        github: `<svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12c0 4.42 2.87 8.17 6.84 9.5.5.08.66-.23.66-.5v-1.69c-2.77.6-3.36-1.34-3.36-1.34-.46-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.87 1.52 2.34 1.07 2.91.83.09-.65.35-1.09.63-1.34-2.22-.25-4.55-1.11-4.55-4.92 0-1.11.38-2 1.03-2.71-.1-.25-.45-1.29.1-2.64 0 0 .84-.27 2.75 1.02.79-.22 1.65-.33 2.5-.33.85 0 1.71.11 2.5.33 1.91-1.29 2.75-1.02 2.75-1.02.55 1.35.2 2.39.1 2.64.65.71 1.03 1.6 1.03 2.71 0 3.82-2.34 4.66-4.57 4.91.36.31.69.92.69 1.85V21c0 .27.16.59.67.5C19.14 20.16 22 16.42 22 12c0-5.52-4.48-10-10-10z" fill="#ccc"/></svg>`,
        trello: `<svg viewBox="0 0 24 24"><rect x="2" y="2" width="20" height="20" rx="3" fill="#0079BF"/><rect x="4.5" y="4.5" width="6" height="13" rx="1.5" fill="#fff"/><rect x="13.5" y="4.5" width="6" height="8" rx="1.5" fill="#fff"/></svg>`,
        todoist: `<svg viewBox="0 0 24 24"><path d="M21 4.5H3c-.55 0-1 .45-1 1v13c0 .55.45 1 1 1h18c.55 0 1-.45 1-1v-13c0-.55-.45-1-1-1zm-13 11l-2-2 1.41-1.41L8 13.67l3.59-3.59L13 11.5l-5 4zm10-1H14v-2h4v2zm0-4H14v-2h4v2z" fill="#E44332"/></svg>`,
        twitter: `<svg viewBox="0 0 24 24"><path d="M18.24 3h3.15l-6.87 7.85L22.5 21h-6.34l-4.96-6.49L5.66 21H2.5l7.35-8.4L2.18 3h6.5l4.48 5.93L18.24 3zm-1.1 16.17h1.75L7.08 4.78H5.21l11.93 14.39z" fill="#ccc"/></svg>`,
        instagram: `<svg viewBox="0 0 24 24"><rect x="2" y="2" width="20" height="20" rx="5" fill="none" stroke="#E4405F" stroke-width="1.5"/><circle cx="12" cy="12" r="5" fill="none" stroke="#E4405F" stroke-width="1.5"/><circle cx="17.5" cy="6.5" r="1.2" fill="#E4405F"/></svg>`,
        twitch: `<svg viewBox="0 0 24 24"><path d="M4.27 2L2 6.63v12.74h5.09V22h3.18l2.81-2.63h4.36L22 14.82V2H4.27zm15.27 11.73l-3.18 2.98h-4.36l-2.81 2.63v-2.63H5.54V3.81h14v9.92z" fill="#9146FF"/><path d="M15.36 6.8h-1.82v5.36h1.82V6.8zm-5 0H8.55v5.36h1.82V6.8z" fill="#9146FF"/></svg>`,
        netflix: `<svg viewBox="0 0 24 24"><path d="M5.4 2h4.4l4.5 12.5V2H19v20c-1.6-.4-3.5-.8-4.8-1L9.4 8.5V22c-1.4-.3-2.8-.6-4-.9V2z" fill="#E50914"/></svg>`,
        teams: `<svg viewBox="0 0 24 24"><path d="M20.63 8.26h-4.38v7.13c0 2.07-1.68 3.75-3.75 3.75-.36 0-.7-.05-1.03-.15A5.63 5.63 0 0017 21.5c3.11 0 5.63-2.52 5.63-5.63V10.26a2 2 0 00-2-2z" fill="#5059C9"/><circle cx="19" cy="5" r="2.5" fill="#5059C9"/><path d="M14.5 7H4.5A1.5 1.5 0 003 8.5v7A4.5 4.5 0 007.5 20h2A4.5 4.5 0 0014 15.5v-7A1.5 1.5 0 0012.5 7h2z" fill="#7B83EB"/><circle cx="9.5" cy="4" r="3" fill="#7B83EB"/></svg>`,
        sheets: `<svg viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2z" fill="#0F9D58"/><path d="M7 7h10v2H7zm0 4h10v2H7zm0 4h7v2H7z" fill="#fff" opacity="0.8"/></svg>`,
        obsidian: `<svg viewBox="0 0 24 24"><path d="M12 2L6 7v10l6 5 6-5V7l-6-5zm0 2.5L16 8v8l-4 3.3L8 16V8l4-3.5z" fill="#7C3AED"/><path d="M12 4.5L8 8v8l4 3.3V4.5z" fill="#A855F7" opacity="0.6"/></svg>`,
        openai: `<svg viewBox="0 0 24 24"><path d="M22.28 9.37a5.93 5.93 0 00-.51-4.89A6.01 6.01 0 0015.3 1.5a5.97 5.97 0 00-4.52 2.07A5.93 5.93 0 006.34 2.3 6.01 6.01 0 002.6 6.59a5.97 5.97 0 00.73 4.96 5.93 5.93 0 00.51 4.89 6.01 6.01 0 006.47 2.98 5.97 5.97 0 004.52-2.07 5.93 5.93 0 004.44 1.27 6.01 6.01 0 003.74-4.29 5.97 5.97 0 00-.73-4.96zM12 16.5a4.5 4.5 0 110-9 4.5 4.5 0 010 9z" fill="#10A37F"/></svg>`,
        homeassistant: `<svg viewBox="0 0 24 24"><path d="M12 3L2 12h3v8h6v-6h2v6h6v-8h3L12 3zm0 2.7L18 11v8h-3v-6H9v6H6v-8l6-5.3z" fill="#41BDF5"/></svg>`,
        elevenlabs: `<svg viewBox="0 0 24 24"><rect x="8" y="3" width="3" height="18" rx="1.5" fill="#ccc"/><rect x="13" y="3" width="3" height="18" rx="1.5" fill="#ccc"/></svg>`,
        dropbox: `<svg viewBox="0 0 24 24"><path d="M7.1 3L1.5 6.7l5.6 3.7-5.6 3.7L7.1 18l5.6-3.7L18.3 18l5.6-3.9-5.6-3.7 5.6-3.7L18.3 3l-5.6 3.7L7.1 3zm.1 2.3l3.5 2.3-3.5 2.4-3.6-2.4 3.6-2.3zm11 0l3.6 2.3-3.6 2.4-3.5-2.4 3.5-2.3zm-5.5 3.7l3.5 2.3-3.5 2.4-3.6-2.4 3.6-2.3z" fill="#0061FF"/></svg>`
    },

    async loadConnections() {
        try {
            const res = await fetch(`${API}/connections`);
            const data = await res.json();
            const conns = data.connections;

            const active = conns.filter(c => c.category === 'active');
            const passive = conns.filter(c => c.category === 'passive');
            const available = conns.filter(c => c.category === 'available');

            document.getElementById('conn-active').innerHTML = active.map(c => this.renderConnectionCard(c)).join('');
            document.getElementById('conn-passive').innerHTML = passive.map(c => this.renderConnectionCard(c)).join('');
            document.getElementById('conn-available').innerHTML = available.map(c => this.renderConnectionCard(c)).join('');
        } catch(e) {
            console.error('Error cargando conexiones:', e);
        }
    },

    connectionSetup: {
        claude: { tab: 'config', msg: 'Configurar API Key de Claude' },
        chrome: { steps: ['Abrir chrome://extensions en Chrome', 'Activar "Modo desarrollador"', 'Click en "Cargar descomprimida"', 'Seleccionar la carpeta chrome-extension/ del proyecto'] },
        gmail: { tab: 'config', msg: 'Configurar Gmail con App Password' },
        together: { tab: 'config', msg: 'Configurar API Key de Together AI' },
        calendar: { type: 'api_key', key: 'google_calendar_url', label: 'URL del calendario (iCal)', placeholder: 'https://calendar.google.com/calendar/ical/...', steps: ['Ir a Google Calendar > Configuracion', 'Click en tu calendario > "Integracion del calendario"', 'Copiar la "Direccion secreta en formato iCal"'] },
        telegram: { type: 'api_key', key: 'telegram_bot_token', label: 'Bot Token', placeholder: '123456789:ABCdefGhIjKlMnOpQrStUvWxYz', steps: ['Abri Telegram en tu celu y busca @BotFather', 'Mandá /newbot y ponele un nombre (ej: "Mi Jarvis")', 'Ponele un username (ej: "mi_jarvis_bot")', 'Copiá el token que te da y pegalo acá', 'Después abrí tu bot y mandá /start'] },
        discord: { type: 'api_key', key: 'discord_bot_token', label: 'Bot Token', placeholder: 'Tu token de bot de Discord', steps: ['Ir a discord.com/developers/applications', 'Crear una aplicacion > Bot > Reset Token', 'Copiar el token', 'En OAuth2 > URL Generator: seleccionar bot con permisos Send Messages y Read Message History', 'Abrir la URL generada para invitar el bot a tu servidor'] },
        slack: { type: 'api_key', key: 'slack_webhook_url', label: 'Webhook URL', placeholder: 'https://hooks.slack.com/services/...', steps: ['Ir a api.slack.com/apps > Create App', 'Activar Incoming Webhooks', 'Copiar la Webhook URL'] },
        github: { type: 'api_key', key: 'github_token', label: 'Personal Access Token', placeholder: 'ghp_xxxxxxxxxxxx', steps: ['Ir a github.com > Settings > Developer settings', 'Personal access tokens > Generate new token', 'Seleccionar permisos (repo, notifications)', 'Copiar el token'] },
        trello: { type: 'api_key', key: 'trello_api_key', label: 'API Key', placeholder: 'Tu API key de Trello', steps: ['Ir a trello.com/app-key', 'Copiar tu API Key', 'Generar un Token de acceso'] },
        todoist: { type: 'api_key', key: 'todoist_api_token', label: 'API Token', placeholder: 'Tu token de Todoist', steps: ['Abrir Todoist > Configuracion > Integraciones', 'Copiar el "Token de la API"'] },
        twitter: { type: 'coming_soon' },
        instagram: { type: 'coming_soon' },
        teams: { type: 'coming_soon' },
        sheets: { type: 'coming_soon' },
        obsidian: { steps: ['Instalar el plugin "Local REST API" en Obsidian', 'Activar el plugin y configurar el puerto', 'JARVIS se conecta automaticamente'] },
        openai: { type: 'api_key', key: 'openai_api_key', label: 'API Key', placeholder: 'sk-...', steps: ['Ir a platform.openai.com/api-keys', 'Crear una nueva API Key', 'Copiar el token'] },
        homeassistant: { type: 'api_key', key: 'homeassistant_url', label: 'URL + Token', placeholder: 'http://homeassistant.local:8123', steps: ['Abrir Home Assistant > Perfil > Tokens de larga duracion', 'Crear un token nuevo', 'Copiar URL y token'] },
        elevenlabs: { type: 'api_key', key: 'elevenlabs_api_key', label: 'API Key', placeholder: 'Tu API key de ElevenLabs', steps: ['Ir a elevenlabs.io > Profile + API Key', 'Copiar tu API Key'] },
        dropbox: { type: 'coming_soon' },
    },

    renderConnectionCard(conn) {
        const icon = this.connectionIcons[conn.icon] || '';
        const statusClass = conn.category === 'available'
            ? (conn.connected ? 'online' : 'available-tag')
            : (conn.connected ? 'online' : 'offline');
        const statusText = conn.category === 'available'
            ? (conn.connected ? 'ACTIVO' : 'DISPONIBLE')
            : (conn.connected ? 'ONLINE' : 'OFFLINE');
        const cardClass = conn.connected ? 'connected' : 'disconnected';
        const hasSetup = this.connectionSetup[conn.id];
        const clickable = hasSetup ? 'clickable' : '';
        const onclick = hasSetup ? `onclick="JARVIS.openConnectionSetup('${conn.id}')"` : '';

        return `<div class="connection-card ${cardClass} ${clickable}" ${onclick}>
            <div class="connection-icon">${icon}</div>
            <div class="connection-info">
                <div class="connection-name">${this.esc(conn.name)}</div>
                <div class="connection-desc">${this.esc(conn.description)}</div>
            </div>
            <div class="connection-status ${statusClass}">${statusText}</div>
        </div>`;
    },

    openConnectionSetup(connId) {
        const setup = this.connectionSetup[connId];
        if (!setup) return;

        if (setup.tab) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            const tabBtn = document.querySelector(`.tab-btn[data-tab="${setup.tab}"]`);
            if (tabBtn) tabBtn.classList.add('active');
            document.getElementById(`tab-${setup.tab}`).classList.add('active');
            return;
        }

        const icon = this.connectionIcons[connId] || '';
        const allConns = document.querySelectorAll('.connection-card');
        let connName = connId;
        allConns.forEach(c => {
            if (c.onclick && c.onclick.toString().includes(connId)) {
                connName = c.querySelector('.connection-name')?.textContent || connId;
            }
        });

        const names = {
            calendar: 'Google Calendar', telegram: 'Telegram', discord: 'Discord',
            slack: 'Slack', github: 'GitHub', trello: 'Trello', todoist: 'Todoist',
            twitter: 'X / Twitter', instagram: 'Instagram', teams: 'Microsoft Teams',
            sheets: 'Google Sheets', obsidian: 'Obsidian', openai: 'OpenAI',
            homeassistant: 'Home Assistant', elevenlabs: 'ElevenLabs', dropbox: 'Dropbox',
            chrome: 'Chrome Extension'
        };

        let bodyHTML = '';

        if (setup.type === 'coming_soon') {
            bodyHTML = `
                <div class="setup-coming-soon">
                    <div class="setup-icon">${icon}</div>
                    <p>La integracion con <strong>${this.esc(names[connId] || connId)}</strong> estara disponible proximamente.</p>
                    <p class="config-hint">Mientras tanto, podes pedirle a JARVIS que abra ${this.esc(names[connId] || connId)} en el navegador.</p>
                </div>`;
        } else if (setup.type === 'api_key') {
            const stepsHTML = setup.steps ? setup.steps.map((s, i) =>
                `<li>${this.esc(s)}</li>`).join('') : '';
            bodyHTML = `
                <div class="setup-form">
                    <div class="setup-icon">${icon}</div>
                    ${stepsHTML ? `<ol class="config-steps">${stepsHTML}</ol>` : ''}
                    <label>${this.esc(setup.label)}</label>
                    <input type="text" id="setup-key-input" placeholder="${this.esc(setup.placeholder || '')}" autocomplete="off">
                    <button class="config-btn" onclick="JARVIS.saveConnectionKey('${connId}')">Conectar</button>
                    <div id="setup-status"></div>
                </div>`;
        } else if (setup.steps) {
            const stepsHTML = setup.steps.map((s, i) =>
                `<li>${this.esc(s)}</li>`).join('');
            bodyHTML = `
                <div class="setup-form">
                    <div class="setup-icon">${icon}</div>
                    <ol class="config-steps">${stepsHTML}</ol>
                </div>`;
        }

        document.querySelector('.setup-overlay')?.remove();
        const overlay = document.createElement('div');
        overlay.className = 'setup-overlay';
        overlay.innerHTML = `
            <div class="setup-panel">
                <div class="setup-header">
                    <h3>Conectar ${this.esc(names[connId] || connId)}</h3>
                    <button class="analysis-close-btn" onclick="this.closest('.setup-overlay').remove()">&times;</button>
                </div>
                <div class="setup-body">${bodyHTML}</div>
            </div>`;
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) overlay.remove();
        });
        document.body.appendChild(overlay);
    },

    async saveConnectionKey(connId) {
        const setup = this.connectionSetup[connId];
        const input = document.getElementById('setup-key-input');
        const status = document.getElementById('setup-status');
        if (!input || !setup) return;
        const val = input.value.trim();
        if (!val) {
            status.innerHTML = '<span class="status-err">Ingresa un valor</span>';
            return;
        }
        try {
            const res = await fetch(`${API}/config/connection`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key: setup.key, value: val })
            });
            const data = await res.json();
            if (data.success) {
                status.innerHTML = '<span class="status-ok">Conectado correctamente</span>';
                setTimeout(() => {
                    document.querySelector('.setup-overlay')?.remove();
                    this.loadConnections();
                }, 1500);
            } else {
                status.innerHTML = `<span class="status-err">${this.esc(data.error || 'Error')}</span>`;
            }
        } catch(e) {
            status.innerHTML = '<span class="status-err">Error de conexion</span>';
        }
    }
};

document.addEventListener('DOMContentLoaded', () => JARVIS.init());
