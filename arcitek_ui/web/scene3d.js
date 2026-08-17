// ArciTEK 3D desktop layer: canvas scene, startup splash, and panel depth.
(() => {
  'use strict';

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const finePointer = window.matchMedia('(pointer: fine)');

  // -- Startup splash -------------------------------------------------------
  const splash = document.querySelector('#splash');
  const splashBar = document.querySelector('#boot-progress-bar');
  const splashStatus = document.querySelector('#boot-status');
  const BOOT_STEPS = [
    'Calibrating quantum cores',
    'Linking compute fabric',
    'Syncing robotics plans',
    'Compositing 3D workspace',
  ];
  const SPLASH_MIN_MS = reduceMotion.matches ? 200 : 1200;
  const SPLASH_MAX_MS = 8000;
  const splashShownAt = Date.now();
  let splashDone = false;
  let bootStep = 0;
  let bootProgress = 0;

  function setBootStatus(text) {
    if (splashStatus) splashStatus.textContent = text;
  }

  function setBootProgress(value) {
    bootProgress = Math.max(bootProgress, Math.min(100, value));
    if (splashBar) splashBar.style.width = `${bootProgress}%`;
  }

  const bootTicker = window.setInterval(() => {
    if (splashDone) return;
    if (bootStep < BOOT_STEPS.length) setBootStatus(BOOT_STEPS[bootStep]);
    bootStep += 1;
    setBootProgress(Math.min(90, bootProgress + 18 + Math.random() * 8));
  }, 420);

  function hideSplash() {
    if (splashDone || !splash) return;
    splashDone = true;
    window.clearInterval(bootTicker);
    setBootProgress(100);
    setBootStatus('Workspace ready');
    const elapsed = Date.now() - splashShownAt;
    window.setTimeout(() => {
      splash.classList.add('splash-hidden');
      splash.setAttribute('aria-hidden', 'true');
      window.setTimeout(() => {
        splash.hidden = true;
      }, 700);
    }, Math.max(0, SPLASH_MIN_MS - elapsed) + 250);
  }

  const splashFailsafe = window.setTimeout(hideSplash, SPLASH_MAX_MS);

  window.ArciTEKDesktop = {
    bootComplete() {
      window.clearTimeout(splashFailsafe);
      hideSplash();
    },
  };

  // -- 3D scene: starfield, grid floor, and wireframe core ------------------
  function initScene(canvas, ctx) {
    const FOV = 420;
    const STAR_COUNT = 150;
    const STAR_DEPTH = 1600;
    const camera = { x: 0, y: 0, targetX: 0, targetY: 0 };
    let width = 0;
    let height = 0;
    let dpr = 1;
    let gridScroll = 0;
    let coreAngle = 0;
    let rafId = 0;
    let lastTime = 0;

    const stars = Array.from({ length: STAR_COUNT }, () => ({
      x: (Math.random() - 0.5) * 2400,
      y: (Math.random() - 0.5) * 1400,
      z: Math.random() * STAR_DEPTH,
      speed: 30 + Math.random() * 90,
    }));

    // Icosahedron vertices/edges for the rotating wireframe core.
    const phi = (1 + Math.sqrt(5)) / 2;
    const coreVerts = [
      [-1, phi, 0], [1, phi, 0], [-1, -phi, 0], [1, -phi, 0],
      [0, -1, phi], [0, 1, phi], [0, -1, -phi], [0, 1, -phi],
      [phi, 0, -1], [phi, 0, 1], [-phi, 0, -1], [-phi, 0, 1],
    ];
    const coreEdges = [];
    for (let a = 0; a < coreVerts.length; a += 1) {
      for (let b = a + 1; b < coreVerts.length; b += 1) {
        const dx = coreVerts[a][0] - coreVerts[b][0];
        const dy = coreVerts[a][1] - coreVerts[b][1];
        const dz = coreVerts[a][2] - coreVerts[b][2];
        if (Math.abs(Math.hypot(dx, dy, dz) - 2) < 0.01) coreEdges.push([a, b]);
      }
    }

    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function project(x, y, z) {
      const scale = FOV / (FOV + z);
      return {
        x: width / 2 + (x - camera.x * (1 - z / (STAR_DEPTH + FOV))) * scale,
        y: height / 2 + (y - camera.y * (1 - z / (STAR_DEPTH + FOV))) * scale,
        scale,
      };
    }

    function drawStars(dt) {
      for (const star of stars) {
        star.z -= star.speed * dt;
        if (star.z < 1) {
          star.z = STAR_DEPTH;
          star.x = (Math.random() - 0.5) * 2400;
          star.y = (Math.random() - 0.5) * 1400;
        }
        const point = project(star.x, star.y, star.z);
        const alpha = Math.min(0.5, (1 - star.z / STAR_DEPTH) * 0.55 + 0.05);
        const size = Math.max(0.4, point.scale * 2.1);
        ctx.fillStyle = `rgba(167, 143, 255, ${alpha.toFixed(3)})`;
        ctx.fillRect(point.x, point.y, size, size);
      }
    }

    function drawGrid(dt) {
      gridScroll = (gridScroll + 55 * dt) % 120;
      const gridY = 330;
      ctx.lineWidth = 1;
      for (let z = 120 - gridScroll; z < STAR_DEPTH; z += 120) {
        const alpha = 0.14 * (1 - z / STAR_DEPTH);
        if (alpha <= 0.004) continue;
        const left = project(-2200, gridY, z);
        const right = project(2200, gridY, z);
        ctx.strokeStyle = `rgba(66, 216, 209, ${alpha.toFixed(3)})`;
        ctx.beginPath();
        ctx.moveTo(left.x, left.y);
        ctx.lineTo(right.x, right.y);
        ctx.stroke();
      }
      for (let x = -2200; x <= 2200; x += 220) {
        const near = project(x, gridY, 40);
        const far = project(x, gridY, STAR_DEPTH);
        ctx.strokeStyle = 'rgba(135, 104, 255, 0.05)';
        ctx.beginPath();
        ctx.moveTo(near.x, near.y);
        ctx.lineTo(far.x, far.y);
        ctx.stroke();
      }
    }

    function drawCore(dt) {
      coreAngle += dt * 0.32;
      const cosY = Math.cos(coreAngle);
      const sinY = Math.sin(coreAngle);
      const cosX = Math.cos(coreAngle * 0.6);
      const sinX = Math.sin(coreAngle * 0.6);
      const radius = Math.min(width, height) * 0.16;
      const offsetX = width * 0.31;
      const offsetY = -height * 0.08;
      const projected = coreVerts.map(([vx, vy, vz]) => {
        const rx = vx * cosY - vz * sinY;
        const rz = vx * sinY + vz * cosY;
        const ry = vy * cosX - rz * sinX;
        const fz = vy * sinX + rz * cosX;
        return project(rx * radius + offsetX, ry * radius + offsetY, fz * radius + 620);
      });
      ctx.lineWidth = 1;
      for (const [a, b] of coreEdges) {
        const depth = (projected[a].scale + projected[b].scale) / 2;
        ctx.strokeStyle = `rgba(135, 104, 255, ${(depth * 0.34).toFixed(3)})`;
        ctx.beginPath();
        ctx.moveTo(projected[a].x, projected[a].y);
        ctx.lineTo(projected[b].x, projected[b].y);
        ctx.stroke();
      }
      for (const point of projected) {
        ctx.fillStyle = `rgba(203, 189, 255, ${(point.scale * 0.5).toFixed(3)})`;
        ctx.fillRect(point.x - 1, point.y - 1, 2, 2);
      }
    }

    function renderFrame(dt) {
      ctx.clearRect(0, 0, width, height);
      camera.x += (camera.targetX - camera.x) * Math.min(1, dt * 3);
      camera.y += (camera.targetY - camera.y) * Math.min(1, dt * 3);
      drawStars(dt);
      drawGrid(dt);
      drawCore(dt);
    }

    function loop(time) {
      const dt = Math.min(0.05, (time - lastTime) / 1000 || 0.016);
      lastTime = time;
      renderFrame(dt);
      rafId = window.requestAnimationFrame(loop);
    }

    function start() {
      if (rafId) return;
      lastTime = performance.now();
      rafId = window.requestAnimationFrame(loop);
    }

    function stop() {
      if (!rafId) return;
      window.cancelAnimationFrame(rafId);
      rafId = 0;
    }

    resize();
    window.addEventListener('resize', () => {
      resize();
      if (reduceMotion.matches) renderFrame(0);
    });
    document.addEventListener('visibilitychange', () => {
      if (document.hidden || reduceMotion.matches) stop();
      else start();
    });
    window.addEventListener('pointermove', (event) => {
      camera.targetX = (event.clientX / width - 0.5) * 60;
      camera.targetY = (event.clientY / height - 0.5) * 40;
    });

    if (reduceMotion.matches) {
      renderFrame(0);
    } else {
      start();
    }
    reduceMotion.addEventListener('change', () => {
      if (reduceMotion.matches) {
        stop();
        renderFrame(0);
      } else {
        start();
      }
    });
  }

  const sceneCanvas = document.querySelector('#scene3d');
  let sceneCtx = null;
  try {
    sceneCtx = sceneCanvas ? sceneCanvas.getContext('2d') : null;
  } catch {
    sceneCtx = null;
  }
  if (sceneCanvas && sceneCtx) initScene(sceneCanvas, sceneCtx);

  // -- Pointer-driven 3D tilt for desktop panels ----------------------------
  if (finePointer.matches && !reduceMotion.matches) {
    const MAX_TILT = 3.2;
    document.querySelectorAll('.metric-card, .action-card, .panel').forEach((card) => {
      card.addEventListener('pointermove', (event) => {
        const rect = card.getBoundingClientRect();
        const ratioX = (event.clientX - rect.left) / rect.width - 0.5;
        const ratioY = (event.clientY - rect.top) / rect.height - 0.5;
        card.style.setProperty('--tilt-x', `${(-ratioY * MAX_TILT).toFixed(2)}deg`);
        card.style.setProperty('--tilt-y', `${(ratioX * MAX_TILT).toFixed(2)}deg`);
        card.style.setProperty('--lift', '6px');
      });
      card.addEventListener('pointerleave', () => {
        card.style.setProperty('--tilt-x', '0deg');
        card.style.setProperty('--tilt-y', '0deg');
        card.style.setProperty('--lift', '0px');
      });
    });
  }
})();
