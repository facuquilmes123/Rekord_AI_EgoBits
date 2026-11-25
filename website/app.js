/**
 * REKORD AI - Interactive Experience Engine
 * Handles: Ambient Particles, Waveform Canvas, Camelot Harmonics, Before/After Slider, Smooth Scroll
 */

document.addEventListener('DOMContentLoaded', () => {
  initAmbientParticles();
  initWaveformVisualizer();
  initCamelotWheel();
  initBeforeAfterSlider();
  initSmoothScroll();
});

/* ==========================================================================
   1. BACKGROUND AMBIENT PARTICLES (CLUB LIGHTING SIMULATOR)
   ========================================================================== */
function initAmbientParticles() {
  const canvas = document.getElementById('ambient-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  let width = (canvas.width = window.innerWidth);
  let height = (canvas.height = window.innerHeight);

  window.addEventListener('resize', () => {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  });

  const particles = [];
  const particleCount = 45;

  for (let i = 0; i < particleCount; i++) {
    particles.push({
      x: Math.random() * width,
      y: Math.random() * height,
      radius: Math.random() * 2 + 1,
      vx: (Math.random() - 0.5) * 0.4,
      vy: (Math.random() - 0.5) * 0.4,
      color: Math.random() > 0.5 ? 'rgba(0, 242, 255,' : 'rgba(143, 0, 255,',
      alpha: Math.random() * 0.5 + 0.1
    });
  }

  function render() {
    ctx.clearRect(0, 0, width, height);

    for (let p of particles) {
      p.x += p.vx;
      p.y += p.vy;

      if (p.x < 0) p.x = width;
      if (p.x > width) p.x = 0;
      if (p.y < 0) p.y = height;
      if (p.y > height) p.y = 0;

      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
      ctx.fillStyle = `${p.color} ${p.alpha})`;
      ctx.fill();
    }

    // Connect close particles with subtle energy laser lines
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 120) {
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.strokeStyle = `rgba(0, 242, 255, ${0.08 * (1 - dist / 120)})`;
          ctx.lineWidth = 0.6;
          ctx.stroke();
        }
      }
    }

    requestAnimationFrame(render);
  }

  render();
}

/* ==========================================================================
   2. PIONEER CDJ-3000 STYLE MULTI-BAND WAVEFORM VISUALIZER
   ========================================================================== */
function initWaveformVisualizer() {
  const canvas = document.getElementById('hero-waveform');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  let width = (canvas.width = canvas.offsetWidth);
  let height = (canvas.height = canvas.offsetHeight);

  window.addEventListener('resize', () => {
    if (!canvas) return;
    width = canvas.width = canvas.offsetWidth;
    height = canvas.height = canvas.offsetHeight;
  });

  let playhead = 0.35; // 35% into the track
  let isPlaying = true;
  let bpm = 126.0;
  let time = 0;

  // Toggle play/pause on click
  canvas.addEventListener('click', () => {
    isPlaying = !isPlaying;
    const playStatusEl = document.getElementById('waveform-play-state');
    if (playStatusEl) {
      playStatusEl.textContent = isPlaying ? 'PLAYING (126.00 BPM)' : 'PAUSED (SCRUB READY)';
      playStatusEl.className = isPlaying ? 'text-emerald-400 font-mono text-xs' : 'text-amber-400 font-mono text-xs';
    }
  });

  // Track scrubber on mousemove when holding click
  canvas.addEventListener('mousemove', (e) => {
    if (e.buttons === 1) {
      const rect = canvas.getBoundingClientRect();
      playhead = Math.max(0, Math.min(1, (e.clientX - rect.left) / width));
    }
  });

  function draw() {
    ctx.clearRect(0, 0, width, height);
    time += 0.03;

    if (isPlaying) {
      playhead += 0.0008;
      if (playhead > 1) playhead = 0;
    }

    const centerY = height / 2;
    const barWidth = 3;
    const gap = 2;
    const totalBars = Math.floor(width / (barWidth + gap));

    for (let i = 0; i < totalBars; i++) {
      const x = i * (barWidth + gap);
      const normX = i / totalBars;

      // Pioneer 3-band energy simulation:
      // Low (Bass/Kick): Deep Blue / Cyan
      // Mid (Synths/Vocals): Amber / Orange
      // High (Hi-hats): Bright White
      const bassFreq = Math.sin(normX * 35 + time * 2) * Math.cos(normX * 12);
      const midFreq = Math.sin(normX * 60 - time) * 0.7;
      const beatPulse = (i % 8 === 0) ? 1.5 : 0.8;

      const baseAmp = (Math.sin(normX * Math.PI) * 0.5 + 0.3) * beatPulse;
      const combinedAmp = Math.max(0.1, (baseAmp + bassFreq * 0.3 + midFreq * 0.2));
      const barHeight = Math.min(height * 0.85, combinedAmp * (height * 0.75));

      // Color coding before and after playhead
      const isPast = normX <= playhead;
      
      // Draw 3-band layered bars
      // Bass layer
      ctx.fillStyle = isPast ? '#00E5FF' : 'rgba(0, 229, 255, 0.35)';
      ctx.fillRect(x, centerY - barHeight / 2, barWidth, barHeight);

      // Mid layer (central core)
      ctx.fillStyle = isPast ? '#FFAA00' : 'rgba(255, 170, 0, 0.4)';
      ctx.fillRect(x, centerY - barHeight * 0.3, barWidth, barHeight * 0.6);

      // High layer (bright spine)
      ctx.fillStyle = isPast ? '#FFFFFF' : 'rgba(255, 255, 255, 0.5)';
      ctx.fillRect(x, centerY - barHeight * 0.1, barWidth, barHeight * 0.2);
    }

    // Draw CDJ-3000 Glowing Red/White Playhead Needle
    const needleX = playhead * width;
    ctx.strokeStyle = '#FFFFFF';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(needleX, 0);
    ctx.lineTo(needleX, height);
    ctx.stroke();

    // Needle glow halo
    ctx.fillStyle = 'rgba(0, 242, 255, 0.4)';
    ctx.fillRect(needleX - 2, 0, 4, height);

    // Cue point markers
    const cueA = 0.22 * width;
    const cueB = 0.65 * width;
    ctx.fillStyle = '#10B981'; // Green Hot Cue A
    ctx.beginPath();
    ctx.moveTo(cueA - 5, 0);
    ctx.lineTo(cueA + 5, 0);
    ctx.lineTo(cueA, 8);
    ctx.closePath();
    ctx.fill();

    ctx.fillStyle = '#8F00FF'; // Purple Hot Cue B
    ctx.beginPath();
    ctx.moveTo(cueB - 5, 0);
    ctx.lineTo(cueB + 5, 0);
    ctx.lineTo(cueB, 8);
    ctx.closePath();
    ctx.fill();

    requestAnimationFrame(draw);
  }

  draw();
}

/* ==========================================================================
   3. INTERACTIVE CAMELOT HARMONIC WHEEL ENGINE
   ========================================================================== */
function initCamelotWheel() {
  const container = document.getElementById('camelot-nodes-container');
  if (!container) return;

  const keys = [
    { code: '8A', name: 'A minor', energy: 'Standard' },
    { code: '9A', name: 'E minor', energy: 'Energy Lift (+1)' },
    { code: '10A', name: 'B minor', energy: 'High Tension (+2)' },
    { code: '11A', name: 'F# minor', energy: 'Peak Surge (+3)' },
    { code: '12A', name: 'Db minor', energy: 'Extreme Transition' },
    { code: '1A', name: 'Ab minor', energy: 'Moody Shift' },
    { code: '2A', name: 'Eb minor', energy: 'Deep Groove' },
    { code: '3A', name: 'Bb minor', energy: 'Dark Lift' },
    { code: '4A', name: 'F minor', energy: 'Raw Emotion' },
    { code: '5A', name: 'C minor', energy: 'Club Classic' },
    { code: '6A', name: 'G minor', energy: 'Warm Dynamic' },
    { code: '7A', name: 'D minor', energy: 'Smooth Drop (-1)' }
  ];

  const radius = 120;
  const centerX = 160;
  const centerY = 160;

  container.innerHTML = '';

  keys.forEach((k, idx) => {
    const angle = (idx / 12) * Math.PI * 2 - Math.PI / 2;
    const x = centerX + radius * Math.cos(angle);
    const y = centerY + radius * Math.sin(angle);

    const node = document.createElement('div');
    node.className = `camelot-node ${k.code === '8A' ? 'active' : ''}`;
    node.style.left = `${x}px`;
    node.style.top = `${y}px`;
    node.textContent = k.code;
    node.dataset.code = k.code;
    node.dataset.name = k.name;
    node.dataset.energy = k.energy;

    node.addEventListener('click', () => selectCamelotKey(k.code, keys));
    container.appendChild(node);
  });

  // Default selection
  selectCamelotKey('8A', keys);
}

function selectCamelotKey(selectedCode, keys) {
  const nodes = document.querySelectorAll('.camelot-node');
  const selIndex = keys.findIndex(k => k.code === selectedCode);
  if (selIndex === -1) return;

  const current = keys[selIndex];
  const nextKey = keys[(selIndex + 1) % 12];
  const prevKey = keys[(selIndex + 11) % 12];
  const relativeMajor = selectedCode.replace('A', 'B');

  nodes.forEach(node => {
    node.classList.remove('active', 'compatible');
    if (node.dataset.code === selectedCode) {
      node.classList.add('active');
    } else if (node.dataset.code === nextKey.code || node.dataset.code === prevKey.code) {
      node.classList.add('compatible');
    }
  });

  // Update UI displays
  const keyDisplay = document.getElementById('camelot-active-key');
  const keyNameDisplay = document.getElementById('camelot-active-name');
  const transitionDisplay = document.getElementById('camelot-transition-recommendation');
  const matchScoreDisplay = document.getElementById('camelot-match-score');

  if (keyDisplay) keyDisplay.textContent = current.code;
  if (keyNameDisplay) keyNameDisplay.textContent = current.name;
  if (transitionDisplay) {
    transitionDisplay.innerHTML = `
      <div class="flex items-center gap-2 mb-1">
        <span class="text-cyan-400 font-bold font-mono">Recomendación Armónica:</span>
        <span class="text-emerald-400 font-bold">${current.code} &rarr; ${nextKey.code}</span>
      </div>
      <p class="text-xs text-gray-400">Transición armónica con <strong>${nextKey.energy}</strong> hacia ${nextKey.name} o cambio modal a <strong>${relativeMajor}</strong>.</p>
    `;
  }
  if (matchScoreDisplay) {
    matchScoreDisplay.textContent = '99.4%';
  }
}

/* ==========================================================================
   4. BEFORE & AFTER INTERACTIVE SPLIT COMPARISON SLIDER
   ========================================================================== */
function initBeforeAfterSlider() {
  const container = document.getElementById('comparison-slider-container');
  const beforeWrap = document.getElementById('comparison-before-wrap');
  const handle = document.getElementById('comparison-slider-handle');

  if (!container || !beforeWrap || !handle) return;

  let isDragging = false;

  function updateSlider(clientX) {
    const rect = container.getBoundingClientRect();
    let x = clientX - rect.left;
    x = Math.max(0, Math.min(x, rect.width));
    const percent = (x / rect.width) * 100;

    beforeWrap.style.width = `${percent}%`;
    handle.style.left = `${percent}%`;
  }

  handle.addEventListener('mousedown', () => (isDragging = true));
  window.addEventListener('mouseup', () => (isDragging = false));
  container.addEventListener('mousemove', (e) => {
    if (isDragging) updateSlider(e.clientX);
  });

  // Touch Support
  handle.addEventListener('touchstart', () => (isDragging = true));
  window.addEventListener('touchend', () => (isDragging = false));
  container.addEventListener('touchmove', (e) => {
    if (isDragging && e.touches[0]) updateSlider(e.touches[0].clientX);
  });

  // Click anywhere on container to move slider
  container.addEventListener('click', (e) => {
    updateSlider(e.clientX);
  });
}

/* ==========================================================================
   5. SMOOTH SCROLLING FOR NAVIGATION
   ========================================================================== */
function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      const targetId = this.getAttribute('href');
      if (targetId === '#' || targetId === '#login') return;
      
      const targetEl = document.querySelector(targetId);
      if (targetEl) {
        e.preventDefault();
        targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });
}
