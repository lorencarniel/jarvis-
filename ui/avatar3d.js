const JarvisAvatar = {
    scene: null,
    camera: null,
    renderer: null,
    head: null,
    particles: null,
    rings: [],
    speaking: false,
    speakScale: 0,
    time: 0,
    active: true,
    animId: null,

    init() {
        const canvas = document.getElementById('avatar3d');
        if (!canvas || typeof THREE === 'undefined') return;

        this.scene = new THREE.Scene();
        this.camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
        this.camera.position.set(0, 0, 5);

        this.renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
        this.renderer.setSize(300, 300);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.setClearColor(0x000000, 0);

        this._buildHead();
        this._buildRings();
        this._buildParticles();
        this._addLights();
        this._animate();
    },

    _buildHead() {
        const geo = new THREE.SphereGeometry(1, 32, 32);
        const mat = new THREE.MeshPhongMaterial({
            color: 0x00d4ff,
            emissive: 0x003344,
            transparent: true,
            opacity: 0.25,
            wireframe: true,
        });
        this.head = new THREE.Mesh(geo, mat);
        this.scene.add(this.head);

        const innerGeo = new THREE.SphereGeometry(0.95, 24, 24);
        const innerMat = new THREE.MeshPhongMaterial({
            color: 0x00aaff,
            emissive: 0x001133,
            transparent: true,
            opacity: 0.08,
        });
        const inner = new THREE.Mesh(innerGeo, innerMat);
        this.head.add(inner);

        const eyeGeo = new THREE.SphereGeometry(0.08, 16, 16);
        const eyeMat = new THREE.MeshBasicMaterial({ color: 0x00ffff });
        const leftEye = new THREE.Mesh(eyeGeo, eyeMat);
        leftEye.position.set(-0.3, 0.15, 0.85);
        this.head.add(leftEye);
        const rightEye = new THREE.Mesh(eyeGeo, eyeMat);
        rightEye.position.set(0.3, 0.15, 0.85);
        this.head.add(rightEye);
    },

    _buildRings() {
        for (let i = 0; i < 3; i++) {
            const geo = new THREE.TorusGeometry(1.3 + i * 0.25, 0.01, 8, 64);
            const mat = new THREE.MeshBasicMaterial({
                color: 0x00d4ff,
                transparent: true,
                opacity: 0.3 - i * 0.08,
            });
            const ring = new THREE.Mesh(geo, mat);
            ring.rotation.x = Math.PI / 2 + (i - 1) * 0.3;
            this.scene.add(ring);
            this.rings.push(ring);
        }
    },

    _buildParticles() {
        const count = 200;
        const geo = new THREE.BufferGeometry();
        const pos = new Float32Array(count * 3);
        for (let i = 0; i < count; i++) {
            const r = 1.5 + Math.random() * 1.5;
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.random() * Math.PI;
            pos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
            pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
            pos[i * 3 + 2] = r * Math.cos(phi);
        }
        geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
        const mat = new THREE.PointsMaterial({
            color: 0x00d4ff,
            size: 0.03,
            transparent: true,
            opacity: 0.6,
        });
        this.particles = new THREE.Points(geo, mat);
        this.scene.add(this.particles);
    },

    _addLights() {
        const ambient = new THREE.AmbientLight(0x334466, 0.5);
        this.scene.add(ambient);
        const point = new THREE.PointLight(0x00d4ff, 1, 10);
        point.position.set(2, 2, 3);
        this.scene.add(point);
    },

    _animate() {
        if (!this.active) { this.animId = null; return; }
        this.animId = requestAnimationFrame(() => this._animate());
        this.time += 0.016;

        const targetScale = this.speaking ? 1 : 0;
        this.speakScale += (targetScale - this.speakScale) * 0.08;

        if (this.head) {
            this.head.rotation.y = Math.sin(this.time * 0.5) * 0.3;
            this.head.rotation.x = Math.sin(this.time * 0.3) * 0.1;

            const pulse = 1 + this.speakScale * 0.08 * Math.sin(this.time * 8);
            this.head.scale.set(pulse, pulse, pulse);

            this.head.material.emissive.setHex(
                this.speaking ? 0x005566 : 0x003344
            );
            this.head.material.opacity = 0.25 + this.speakScale * 0.1;
        }

        this.rings.forEach((ring, i) => {
            ring.rotation.z = this.time * (0.2 + i * 0.1);
            ring.rotation.x = Math.PI / 2 + (i - 1) * 0.3 + Math.sin(this.time + i) * 0.1;
            const s = 1 + this.speakScale * 0.05 * Math.sin(this.time * 6 + i);
            ring.scale.set(s, s, s);
        });

        if (this.particles) {
            this.particles.rotation.y = this.time * 0.1;
            this.particles.rotation.x = this.time * 0.05;
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
