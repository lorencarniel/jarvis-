const JarvisAvatar = {
    scene: null,
    camera: null,
    renderer: null,
    head: null,
    innerSphere: null,
    coreSphere: null,
    particles: null,
    particlesInner: null,
    rings: [],
    hudLines: [],
    speaking: false,
    speakScale: 0,
    time: 0,
    active: true,
    animId: null,

    init() {
        const canvas = document.getElementById('avatar3d');
        if (!canvas || typeof THREE === 'undefined') return;

        const size = Math.min(canvas.parentElement.clientWidth, canvas.parentElement.clientHeight, 500) || 500;

        this.scene = new THREE.Scene();
        this.camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
        this.camera.position.set(0, 0.2, 6);

        this.renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
        this.renderer.setSize(size, size);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.setClearColor(0x000000, 0);

        this._buildHead();
        this._buildRings();
        this._buildHUD();
        this._buildParticles();
        this._addLights();
        this._animate();

        window.addEventListener('resize', () => {
            const s = Math.min(canvas.parentElement.clientWidth, canvas.parentElement.clientHeight, 500) || 500;
            this.renderer.setSize(s, s);
        });
    },

    _buildHead() {
        // Outer wireframe sphere
        const geo = new THREE.IcosahedronGeometry(1.1, 2);
        const mat = new THREE.MeshPhongMaterial({
            color: 0x00d4ff,
            emissive: 0x002233,
            transparent: true,
            opacity: 0.18,
            wireframe: true,
        });
        this.head = new THREE.Mesh(geo, mat);
        this.scene.add(this.head);

        // Inner glowing sphere
        const innerGeo = new THREE.IcosahedronGeometry(1.0, 3);
        const innerMat = new THREE.MeshPhongMaterial({
            color: 0x0088ff,
            emissive: 0x003366,
            transparent: true,
            opacity: 0.06,
        });
        this.innerSphere = new THREE.Mesh(innerGeo, innerMat);
        this.head.add(this.innerSphere);

        // Core energy ball
        const coreGeo = new THREE.SphereGeometry(0.15, 16, 16);
        const coreMat = new THREE.MeshBasicMaterial({
            color: 0x00ffff,
            transparent: true,
            opacity: 0.8,
        });
        this.coreSphere = new THREE.Mesh(coreGeo, coreMat);
        this.head.add(this.coreSphere);

        // Eyes
        const eyeGeo = new THREE.SphereGeometry(0.07, 12, 12);
        const eyeMat = new THREE.MeshBasicMaterial({ color: 0x00ffff });
        const leftEye = new THREE.Mesh(eyeGeo, eyeMat);
        leftEye.position.set(-0.28, 0.18, 0.95);
        this.head.add(leftEye);
        const rightEye = new THREE.Mesh(eyeGeo, eyeMat);
        rightEye.position.set(0.28, 0.18, 0.95);
        this.head.add(rightEye);
        this._eyes = [leftEye, rightEye];

        // Eye glow rings
        const glowGeo = new THREE.RingGeometry(0.09, 0.13, 16);
        const glowMat = new THREE.MeshBasicMaterial({ color: 0x00d4ff, transparent: true, opacity: 0.4, side: THREE.DoubleSide });
        const lGlow = new THREE.Mesh(glowGeo, glowMat);
        lGlow.position.copy(leftEye.position);
        lGlow.position.z += 0.02;
        this.head.add(lGlow);
        const rGlow = new THREE.Mesh(glowGeo, glowMat);
        rGlow.position.copy(rightEye.position);
        rGlow.position.z += 0.02;
        this.head.add(rGlow);
        this._eyeGlows = [lGlow, rGlow];
    },

    _buildRings() {
        const colors = [0x00d4ff, 0x0099ff, 0x00ffcc, 0xff9500, 0x0066ff];
        const radii = [1.4, 1.6, 1.85, 2.1, 2.35];
        const widths = [0.012, 0.008, 0.015, 0.006, 0.01];

        for (let i = 0; i < 5; i++) {
            const geo = new THREE.TorusGeometry(radii[i], widths[i], 8, 128);
            const mat = new THREE.MeshBasicMaterial({
                color: colors[i],
                transparent: true,
                opacity: 0.35 - i * 0.04,
            });
            const ring = new THREE.Mesh(geo, mat);
            ring.rotation.x = Math.PI / 2 + (i - 2) * 0.25;
            ring.rotation.y = i * 0.4;
            this.scene.add(ring);
            this.rings.push(ring);
        }

        // Segmented arc rings (like HUD display)
        for (let i = 0; i < 3; i++) {
            const r = 1.5 + i * 0.3;
            const arcLen = Math.PI * (0.3 + Math.random() * 0.4);
            const startAngle = Math.random() * Math.PI * 2;
            const geo = new THREE.TorusGeometry(r, 0.02, 4, 32, arcLen);
            const mat = new THREE.MeshBasicMaterial({
                color: 0xff9500,
                transparent: true,
                opacity: 0.25,
            });
            const arc = new THREE.Mesh(geo, mat);
            arc.rotation.x = Math.PI / 2;
            arc.rotation.z = startAngle;
            this.scene.add(arc);
            this.rings.push(arc);
        }
    },

    _buildHUD() {
        // Floating data lines around the head
        const lineMat = new THREE.LineBasicMaterial({ color: 0x00d4ff, transparent: true, opacity: 0.2 });

        for (let i = 0; i < 8; i++) {
            const points = [];
            const angle = (i / 8) * Math.PI * 2;
            const r = 1.8 + Math.random() * 0.5;
            const len = 0.3 + Math.random() * 0.5;
            const y = (Math.random() - 0.5) * 2;
            points.push(new THREE.Vector3(Math.cos(angle) * r, y, Math.sin(angle) * r));
            points.push(new THREE.Vector3(Math.cos(angle) * (r + len), y, Math.sin(angle) * (r + len)));
            const geo = new THREE.BufferGeometry().setFromPoints(points);
            const line = new THREE.Line(geo, lineMat.clone());
            this.scene.add(line);
            this.hudLines.push(line);
        }
    },

    _buildParticles() {
        // Outer particles
        const count = 500;
        const geo = new THREE.BufferGeometry();
        const pos = new Float32Array(count * 3);
        const colors = new Float32Array(count * 3);
        for (let i = 0; i < count; i++) {
            const r = 1.3 + Math.random() * 2.2;
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.acos(2 * Math.random() - 1);
            pos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
            pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
            pos[i * 3 + 2] = r * Math.cos(phi);
            // Mix of cyan and orange particles
            if (Math.random() > 0.85) {
                colors[i * 3] = 1; colors[i * 3 + 1] = 0.58; colors[i * 3 + 2] = 0;
            } else {
                colors[i * 3] = 0; colors[i * 3 + 1] = 0.7 + Math.random() * 0.3; colors[i * 3 + 2] = 1;
            }
        }
        geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
        geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        const mat = new THREE.PointsMaterial({
            size: 0.025,
            transparent: true,
            opacity: 0.7,
            vertexColors: true,
        });
        this.particles = new THREE.Points(geo, mat);
        this.scene.add(this.particles);

        // Inner particles (dense, close to sphere)
        const count2 = 300;
        const geo2 = new THREE.BufferGeometry();
        const pos2 = new Float32Array(count2 * 3);
        for (let i = 0; i < count2; i++) {
            const r = 0.8 + Math.random() * 0.5;
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.acos(2 * Math.random() - 1);
            pos2[i * 3] = r * Math.sin(phi) * Math.cos(theta);
            pos2[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
            pos2[i * 3 + 2] = r * Math.cos(phi);
        }
        geo2.setAttribute('position', new THREE.BufferAttribute(pos2, 3));
        const mat2 = new THREE.PointsMaterial({
            color: 0x00aaff,
            size: 0.015,
            transparent: true,
            opacity: 0.4,
        });
        this.particlesInner = new THREE.Points(geo2, mat2);
        this.head.add(this.particlesInner);
    },

    _addLights() {
        this.scene.add(new THREE.AmbientLight(0x223344, 0.6));
        const p1 = new THREE.PointLight(0x00d4ff, 1.2, 12);
        p1.position.set(3, 2, 4);
        this.scene.add(p1);
        const p2 = new THREE.PointLight(0xff9500, 0.3, 10);
        p2.position.set(-3, -1, 2);
        this.scene.add(p2);
    },

    _animate() {
        if (!this.active) { this.animId = null; return; }
        this.animId = requestAnimationFrame(() => this._animate());
        this.time += 0.016;
        const t = this.time;

        const targetScale = this.speaking ? 1 : 0;
        this.speakScale += (targetScale - this.speakScale) * 0.1;
        const sp = this.speakScale;

        if (this.head) {
            this.head.rotation.y = Math.sin(t * 0.4) * 0.25;
            this.head.rotation.x = Math.sin(t * 0.25) * 0.08;

            const pulse = 1 + sp * 0.03 * Math.sin(t * 6);
            this.head.scale.set(pulse, pulse, pulse);

            this.head.material.opacity = 0.18 + sp * 0.12;
            this.head.material.emissive.setHex(this.speaking ? 0x004466 : 0x002233);

            if (this.innerSphere) {
                this.innerSphere.material.opacity = 0.06 + sp * 0.08;
                this.innerSphere.rotation.y = -t * 0.15;
            }

            if (this.coreSphere) {
                const coreScale = 1 + sp * 0.8 * Math.abs(Math.sin(t * 12));
                this.coreSphere.scale.set(coreScale, coreScale, coreScale);
                this.coreSphere.material.opacity = 0.3 + sp * 0.6;
            }

            // Eyes pulse when speaking
            if (this._eyes) {
                const eyeScale = 1 + sp * 0.3 * Math.sin(t * 8);
                this._eyes.forEach(e => e.scale.set(eyeScale, eyeScale, eyeScale));
            }
            if (this._eyeGlows) {
                this._eyeGlows.forEach(g => {
                    g.material.opacity = 0.3 + sp * 0.4 * Math.abs(Math.sin(t * 6));
                });
            }
        }

        // Rings
        this.rings.forEach((ring, i) => {
            if (i < 5) {
                ring.rotation.z = t * (0.15 + i * 0.08) * (i % 2 ? 1 : -1);
                ring.rotation.x += Math.sin(t * 0.5 + i) * 0.001;
                const rs = 1 + sp * 0.02 * Math.sin(t * 5 + i * 1.2);
                ring.scale.set(rs, rs, rs);
                ring.material.opacity = (0.35 - i * 0.04) + sp * 0.15;
            } else {
                ring.rotation.z += 0.008 * (i % 2 ? 1 : -1);
                ring.material.opacity = 0.2 + sp * 0.2 * Math.abs(Math.sin(t * 4 + i));
            }
        });

        // HUD lines flicker
        this.hudLines.forEach((line, i) => {
            line.material.opacity = 0.15 + 0.1 * Math.sin(t * 2 + i * 1.5) + sp * 0.2;
            line.rotation.y = t * 0.05;
        });

        // Particles
        if (this.particles) {
            this.particles.rotation.y = t * 0.08;
            this.particles.rotation.x = t * 0.03;
            this.particles.material.opacity = 0.5 + sp * 0.3;
        }
        if (this.particlesInner) {
            this.particlesInner.rotation.y = -t * 0.2;
            this.particlesInner.material.opacity = 0.3 + sp * 0.4;
        }

        this.renderer.render(this.scene, this.camera);
    },

    setSpeaking(val) {
        this.speaking = !!val;
    },

    stop() {
        this.active = false;
        if (this.animId) cancelAnimationFrame(this.animId);
    },

    start() {
        if (!this.active) {
            this.active = true;
            this._animate();
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => JarvisAvatar.init(), 500);
});
