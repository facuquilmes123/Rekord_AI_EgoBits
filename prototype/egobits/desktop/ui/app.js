// Rekord AI - Cliente Desktop Frontend
document.addEventListener('DOMContentLoaded', () => {
  let lastPlanResult = null;
  let backend = null;
  let chatBusy = false;
  let chatReference = null;
  let chatHistory = [];

  async function apiFetch(path, options = {}) {
    if (!window.__TAURI__) return fetch(path, options);
    if (!backend) backend = await window.__TAURI__.core.invoke('backend_info');
    const headers = new Headers(options.headers || {});
    headers.set('X-EgoBits-Token', backend.token);
    const url = `http://127.0.0.1:${backend.port}${path}`;
    let lastError;
    for (let attempt = 0; attempt < 80; attempt++) {
      try { return await fetch(url, { ...options, headers }); }
      catch (error) {
        lastError = error;
        if (options.method === 'POST') break;
        await new Promise(resolve => setTimeout(resolve, 250));
      }
    }
    throw lastError;
  }

  function notice(text, kind = 'info', action = null) {
    if (kind === 'info' && /error|no se pudo|rechazad|inválid/i.test(String(text))) kind = 'error';
    const stack = document.getElementById('notice-stack');
    for(const old of [...stack.children])if(old.dataset.message===String(text))old.remove();
    while(stack.children.length>=3)stack.firstElementChild.remove();
    const item = document.createElement('div');item.dataset.message=String(text); item.className = `app-notice notice-${kind}`;
    const symbol = document.createElement('span'); symbol.className = 'notice-symbol'; symbol.textContent = kind === 'error' ? '!' : '✓';
    const body = document.createElement('div'); const title = document.createElement('strong'); title.textContent = 'Rekord AI';
    const message = document.createElement('p'); message.textContent = String(text); body.append(title, message);
    if(action){const link=document.createElement('button');link.type='button';link.className='notice-action';link.textContent=action.label;link.onclick=()=>{item.remove();action.run();};body.append(link);}
    const close = document.createElement('button'); close.type = 'button'; close.setAttribute('aria-label', 'Cerrar aviso'); close.textContent = '×'; close.addEventListener('click', () => item.remove());
    item.append(symbol, body, close); stack.append(item);
    if (kind !== 'error') setTimeout(() => item.remove(), 8000);
  }
  window.RekordAI = {apiFetch, post, notice, async refreshStatus() { const r=await apiFetch('/api/status'); if(r.ok) {const data=await r.json();showStatus(data);document.getElementById('lib-tracks-count').textContent=`${data.tracks_count} tracks`;document.getElementById('config-xml-path').value=data.demo?'':data.source_path || '';window.dispatchEvent(new CustomEvent('collection-loaded',{detail:data}));} }, setPlan(result) { lastPlanResult = result; renderPlanResults(result); }};

  // Tabs Switching
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabPanes = document.querySelectorAll('.tab-pane');

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => { b.classList.remove('active'); b.removeAttribute('aria-current'); });
      tabPanes.forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      btn.setAttribute('aria-current', 'page');
      const targetId = btn.getAttribute('data-tab');
      document.getElementById(targetId)?.classList.add('active');
      if (targetId === 'tab-chat') updateLiveCockpit();
    });
  });

  const urlParams = new URLSearchParams(window.location.search);
  const requestedTab = urlParams.get('tab') || (window.location.hash ? window.location.hash.slice(1) : null);
  if (requestedTab) {
    const matchingBtn = document.querySelector(`.tab-btn[data-tab="${requestedTab}"]`);
    if (matchingBtn) matchingBtn.click();
  }

  // Carga inicial de estado y playlists
  async function loadInitialData() {
    try {
      const resp = await apiFetch('/api/status');
      if (resp.ok) {
        const data = await resp.json();
        const rbStateEl = document.getElementById('rb-state');
        const badgeEl = document.getElementById('rekordbox-badge');
        const tracksCountEl = document.getElementById('lib-tracks-count');

        if (rbStateEl) rbStateEl.textContent = data.rekordbox_state.toUpperCase();
        if (tracksCountEl) tracksCountEl.textContent = `${data.tracks_count} tracks`;
        const xmlPathEl = document.getElementById('config-xml-path');
        if (xmlPathEl && !xmlPathEl.value) xmlPathEl.value = data.demo ? '' : (data.source_path || '');
        showStatus(data);
        window.dispatchEvent(new CustomEvent('collection-loaded', {detail:data}));

        const dot = badgeEl?.querySelector('.dot');
        if (dot) {
          dot.className = 'dot ' + (data.rekordbox_state === 'open' ? 'dot-green' : data.rekordbox_state === 'closed' ? 'dot-orange' : 'dot-unknown');
        }
      }
    } catch (err) {
      document.getElementById('runtime-status').textContent = 'Servicio local no disponible: ' + err.message;
    }

    try {
      const resp = await apiFetch('/api/playlists');
      if (resp.ok) {
        const data = await resp.json();
        renderPlaylists(data.playlists || []);
      }
    } catch (err) {
      console.warn('Error al cargar playlists', err);
    }
  }

  function renderPlaylists(playlists) {
    const container = document.getElementById('playlist-checkboxes');
    if (!container) return;
    if (playlists.length === 0) {
      container.innerHTML = '<span class="hint">No se encontraron playlists en la colección.</span>';
      return;
    }

    container.innerHTML = '';
    playlists.forEach((p, idx) => {
      const label = document.createElement('label');
      label.className = 'checkbox-item';
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.name = 'selected_playlist';
      input.value = p.path;
      input.checked = false;
      const span = document.createElement('span');
      span.textContent = `${p.path} `;
      const small = document.createElement('small');
      small.style.color = 'var(--text-secondary)';
      small.textContent = `(${p.count} tracks)`;
      span.appendChild(small);
      label.append(input, span);
      container.appendChild(label);
    });
  }

  // Enviar formulario de planificación
  const planForm = document.getElementById('plan-form');
  planForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const checkedBoxes = Array.from(document.querySelectorAll('input[name="selected_playlist"]:checked'));
    const selectedPaths = checkedBoxes.map(cb => cb.value);

    if (document.getElementById('plan-source').value === 'playlists' && selectedPaths.length === 0) {
      notice('Por favor seleccioná al menos una playlist de origen.');
      return;
    }

    const countVal = document.getElementById('plan-count').value.trim();
    const parsedCount = countVal ? parseInt(countVal, 10) : null;
    if (parsedCount !== null && (Number.isNaN(parsedCount) || parsedCount < 1)) {
      notice('Indicá una cantidad de pistas válida (al menos 1) o dejala en blanco para incluir todas.', 'error');
      return;
    }

    const payload = {
      playlists: selectedPaths,
      source: document.getElementById('plan-source').value,
      track_ids: window.RekordAI.selection || [],
      genre: document.getElementById('plan-genre').value,
      mode: document.getElementById('plan-mode').value,
      count: parsedCount,
      max_bpm_step: parseFloat(document.getElementById('plan-max-step').value),
      harmonic: document.getElementById('plan-harmonic').checked,
      avoid_adjacent_artist: document.getElementById('plan-avoid-artist').checked,
      same_genre: document.getElementById('plan-same-genre').checked,
      allow_insufficient: document.getElementById('plan-allow-insufficient').checked,
      name: document.getElementById('plan-out-name').value
    };

    const submitBtn = document.getElementById('btn-calculate-plan');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Calculando...';

    try {
      const resp = await apiFetch('/api/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const result = await resp.json();
      if (!resp.ok) {
        let errorMsg = result.error || 'No se pudo generar';
        if (/candidatos.*insuficientes/i.test(errorMsg) && !payload.allow_insufficient) {
          notice('Candidatos insuficientes. Podés tildar «Permitir crear si los candidatos son insuficientes» para armar el set con las pistas disponibles.', 'error');
        } else {
          notice('Error en planificación: ' + errorMsg);
        }
        return;
      }

      lastPlanResult = result;
      renderPlanResults(result);
      if (result.adjustments && result.adjustments.length > 0) {
        notice(`Propuesta calculada: ${result.track_ids.length} pistas acomodadas con ajustes flexibles para cumplir el set.`, 'info');
      } else {
        notice(`Propuesta calculada: ${result.track_ids.length} pistas ordenadas exitosamente.`, 'success');
      }
    } catch (err) {
      notice('Error de conexión con el backend: ' + err.message);
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Calcular propuesta';
    }
  });

  function renderPlanResults(result) {
    document.getElementById('plan-empty-state').style.display = 'none';
    document.getElementById('plan-metrics').style.display = 'grid';
    document.getElementById('plan-table-container').style.display = 'block';
    document.getElementById('btn-export-xml').disabled = false;

    // Métricas
    document.getElementById('metric-tracks').textContent = result.track_ids.length;
    const durSec = result.duration_sum_seconds;
    if (durSec) {
      const mins = Math.floor(durSec / 60);
      const secs = Math.floor(durSec % 60);
      document.getElementById('metric-duration').textContent = `${mins}:${secs < 10 ? '0' : ''}${secs}`;
    } else {
      document.getElementById('metric-duration').textContent = 'N/D';
    }

    const bpms = result.tracks.map(t => t.bpm).filter(b => b != null);
    if (bpms.length > 0) {
      document.getElementById('metric-bpm-range').textContent = `${Math.min(...bpms)} - ${Math.max(...bpms)}`;
    }
    const plannedBpms = result.tracks.map(t => Number(t.bpm)).filter(b => Number.isFinite(b) && b > 0);
    const cbStart = document.getElementById('cabin-bpm-start');
    if (cbStart) cbStart.textContent = plannedBpms.length ? plannedBpms[0].toFixed(2) : '—';
    const cbEnd = document.getElementById('cabin-bpm-end');
    if (cbEnd) cbEnd.textContent = plannedBpms.length > 1 ? plannedBpms[plannedBpms.length - 1].toFixed(2) : '—';
    document.getElementById('metric-score').textContent = result.score;

    // Ajustes aplicados
    const adjCard = document.getElementById('plan-adjustments-card');
    const adjList = document.getElementById('adjustments-list');
    if (adjCard && adjList) {
      const adjustments = result.adjustments || [];
      if (adjustments.length > 0) {
        adjCard.style.display = 'block';
        adjList.innerHTML = adjustments.map(a => `<li>${escapeHtml(String(a))}</li>`).join('');
      } else {
        adjCard.style.display = 'none';
      }
    }

    // Exclusiones
    const exclCard = document.getElementById('plan-exclusions-card');
    const exclList = document.getElementById('exclusions-list');
    const exclEntries = Object.entries(result.excluded || {});
    if (exclEntries.length > 0) {
      exclCard.style.display = 'block';
      exclList.innerHTML = exclEntries.map(([id, reason]) => `<li><strong>Track ID ${escapeHtml(String(id))}:</strong> ${escapeHtml(String(reason))}</li>`).join('');
    } else {
      exclCard.style.display = 'none';
    }

    // Tabla
    const tbody = document.getElementById('plan-tbody');
    tbody.innerHTML = '';
    result.tracks.forEach((t, i) => {
      const tr = document.createElement('tr');
      const isCamelotB = t.key && t.key.endsWith('B');
      const trans = result.transitions[i - 1];
      let transBadge = '<span class="delta-neutral">-</span>';

      if (trans) {
        const deltaClass = trans.bpm_delta != null && trans.bpm_delta >= 0 ? 'delta-positive' : 'delta-neutral';
        const hsLabel = trans.harmonic === 1.0 ? 'Misma tonalidad' : (trans.harmonic ? `${trans.harmonic * 100}%` : 'salto');
        transBadge = `<span class="delta-badge ${deltaClass}">${trans.bpm_delta == null ? 'BPM sin dato' : (trans.bpm_delta >= 0 ? '+' : '') + trans.bpm_delta + ' BPM'} · ${hsLabel}</span>`;
      }

      tr.innerHTML = `
        <td><strong>${i + 1}</strong></td>
        <td>${escapeHtml(t.title)}</td>
        <td style="color:var(--text-secondary)">${escapeHtml(t.artist)}</td>
        <td><strong>${t.bpm || '-'}</strong></td>
        <td>${t.key ? `<span class="tag-camelot ${isCamelotB ? 'tag-camelot-b' : ''}">${escapeHtml(t.key)}</span>` : '-'}</td>
        <td>${t.energy != null ? `${t.energy}/10` : '<span class="hint">N/D</span>'}</td>
        <td>${transBadge}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  // Exportar XML
  document.getElementById('btn-export-xml')?.addEventListener('click', async () => {
    if (!lastPlanResult) return;
    const defaultName = document.getElementById('plan-out-name').value || 'Rekord AI - Selección';
    const format = document.getElementById('export-format').value;
    let targetFile;
    try {
      const selection = await post('/api/dialog', {kind:'export_' + format, suggested:defaultName.replace(/[<>:"/\\|?*]/g, '_') + '.' + format});
      targetFile = selection.path;
    } catch (error) { notice(error.message, 'error'); return; }
    if (!targetFile) return;

    try {
      const resp = await apiFetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          result: lastPlanResult,
          name: defaultName,
          target_path: targetFile, format
        })
      });

      const data = await resp.json();
      if (!resp.ok) {
        notice('Error al exportar: ' + (data.error || 'Fallo de exportación'));
        return;
      }

      const banner = document.getElementById('export-success-banner');
      banner.querySelector('span').textContent = `${format.toUpperCase()} creado: ${data.exported_file}. ${format === 'xml' ? 'Importalo mediante XML Bridge.' : 'Importalo como playlist en Rekordbox. Los cues y beatgrids permanecen en tu colección.'}`;
      banner.style.display = 'block';
      notice('Playlist exportada: ' + data.exported_file, 'success');
      setTimeout(() => banner.style.display = 'none', 6000);
    } catch (err) {
      notice('Error en exportación: ' + err.message);
    }
  });

  // Chat Asistente
  const chatForm = document.getElementById('chat-form');
  const chatInput = document.getElementById('chat-input');
  const chatMessages = document.getElementById('chat-messages');

  function addChatMessage(role, text, cardHtml = '', suggestions = []) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role === 'user' ? 'msg-user' : 'msg-assistant'}`;
    msgDiv.innerHTML = `
      <div class="msg-avatar">${role === 'user' ? 'DJ' : '<img src="rekord-ia.png" alt="Rekord AI" width="32" height="32">'}</div>
      <div class="msg-body">
        <p>${escapeHtml(text)}</p>
        ${cardHtml}
      </div>
    `;
    if (role !== 'user') {
      const actions = document.createElement('div'); actions.className='chat-followups';
      for (const action of suggestions.slice(0,6)) {
        const button = document.createElement('button'); button.type='button'; button.className='chip'; button.textContent=action.label;
        button.addEventListener('click', () => {
          if (action.query && !chatBusy) { chatInput.value=action.query; chatForm.requestSubmit(); }
          else if(action.opportunity)window.dispatchEvent(new CustomEvent('open-opportunity',{detail:{id:action.opportunity}}));
          else if (['tab-planner','tab-config','tab-audit'].includes(action.tab)) {document.querySelector(`[data-tab="${action.tab}"]`)?.click();if(action.tab==='tab-config' && action.target)window.RekordAI.openSettings(action.target);else if(action.target)document.getElementById(action.target)?.scrollIntoView({block:'center',behavior:'smooth'});}
        }); actions.append(button);
      }
      msgDiv.querySelector('.msg-body').append(actions);
    }
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  const mentionOptions = document.getElementById('mention-options');
  let mentionTimer = null, mentionGeneration = 0, mentionSelection = -1;
  function hideMentions() {
    mentionGeneration++; mentionOptions.hidden=true; mentionOptions.replaceChildren();
    chatInput.setAttribute('aria-expanded','false'); chatInput.removeAttribute('aria-activedescendant'); mentionSelection=-1;
  }
  function activeMention() {
    const prefix = chatInput.value.slice(0,chatInput.selectionStart);
    const match = /(?:^|\s)@([^@\n;]{0,160})$/.exec(prefix);
    if (!match || match[1].includes('"') || match[1].includes("'")) return null;
    return {start:prefix.length-match[1].length-1, end:prefix.length, query:match[1]};
  }
  chatInput.addEventListener('input', () => {
    if (mentionTimer) clearTimeout(mentionTimer);
    hideMentions(); const mention=activeMention(); if (!mention) return;
    const generation=mentionGeneration;
    mentionTimer=setTimeout(async () => {
      try {
        const response=await apiFetch('/api/mentions?q='+encodeURIComponent(mention.query)); const data=await response.json();
        if (!response.ok || generation!==mentionGeneration || !data.tracks.length) return;
        mentionOptions.replaceChildren();
        for (const [index,track] of data.tracks.entries()) {
          const option=document.createElement('button'); option.type='button'; option.role='option'; option.id=`mention-option-${index}`;
          option.setAttribute('aria-selected','false');
          option.textContent=`${track.artist} — ${track.title} · ${track.bpm ?? '—'} BPM · ${track.key || 'sin tonalidad'} · ID ${track.id}`;
          option.addEventListener('click', () => {
            const current=activeMention(); if (!current || generation!==mentionGeneration) return;
            const value=`@id:${track.id} `;
            chatInput.setRangeText(value,current.start,current.end,'end');
            chatReference={track_id:track.id,source_revision:data.source_revision}; hideMentions(); chatInput.focus();
          }); mentionOptions.append(option);
        }
        mentionOptions.hidden=false; chatInput.setAttribute('aria-expanded','true');
      } catch { hideMentions(); }
    },250);
  });
  chatInput.addEventListener('keydown', e => {
    const options=Array.from(mentionOptions.querySelectorAll('button'));
    if (!mentionOptions.hidden && options.length) {
      if (e.key==='Escape') { e.preventDefault(); hideMentions(); return; }
      if (e.key==='ArrowDown' || e.key==='ArrowUp') {
        e.preventDefault(); mentionSelection=(mentionSelection+(e.key==='ArrowDown'?1:-1)+options.length)%options.length;
        options.forEach((option,index)=>option.setAttribute('aria-selected',String(index===mentionSelection)));
        chatInput.setAttribute('aria-activedescendant',options[mentionSelection].id); options[mentionSelection].scrollIntoView({block:'nearest'}); return;
      }
      if ((e.key==='Enter' || e.key==='Tab') && mentionSelection>=0) { e.preventDefault(); options[mentionSelection].click(); return; }
    }
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); chatForm.requestSubmit(); }
  });

  chatForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (chatBusy) return;
    const text = chatInput.value.trim();
    if (!text) return;
    hideMentions();
    chatInput.value = '';
    document.querySelector('.chat-heading').hidden = true;
    addChatMessage('user', text);
    chatBusy=true;
    const send=chatForm.querySelector('button[type=submit]');
    send.disabled=true; send.textContent='Procesando…';
    const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),300000);

    try {
      const resp = await apiFetch('/api/chat', {
        method: 'POST',
        signal:controller.signal,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: text, context_reference:chatReference, history:chatHistory.slice(-4) })
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || 'Consulta rechazada');
      chatHistory.push({role:'user',text:text.slice(0,500)},{role:'assistant',text:(data.response || '').slice(0,500)});
      chatHistory=chatHistory.slice(-4);
      if (data.needs_selection || data.results || (data.references && data.references.length!==1) || (data.tracks && !data.references && !data.context_reference)) chatReference=null;
      else if (data.context_reference) chatReference=data.context_reference;
      let card = '';
      if (data.plan_result) {
        lastPlanResult = data.plan_result;
        document.getElementById('plan-out-name').value = data.intent?.out_name || 'Rekord AI - Selección';
        renderPlanResults(data.plan_result);
        card = `
          <div style="margin-top:0.75rem; padding:0.5rem; background:var(--bg-panel-alt); border-radius:6px;">
            <strong>Propuesta generada (${data.plan_result.track_ids.length} pistas):</strong>
            <ul style="font-size:0.8rem; margin:0.4rem 0 0.4rem 1.2rem;">
              ${data.plan_result.tracks.map(t => `<li>${escapeHtml(t.artist)} - ${escapeHtml(t.title)} (${t.bpm} BPM, ${escapeHtml(t.key || 's/k')})</li>`).join('')}
            </ul>
            <button class="btn btn-accent btn-sm view-plan">Ver en Planificador</button>
          </div>
        `;
      }
      addChatMessage('assistant', data.response || 'Orden procesada.', card, data.suggestions || []);
    } catch (err) {
      addChatMessage('assistant', err.name==='AbortError'?'La IA local superó el tiempo de espera. Podés seguir usando las consultas directas de colección o revisar el estado de IA en Configuración.':'Error procesando solicitud: ' + err.message, '', [{label:'Ver conexión y permisos',tab:'tab-config'},{label:'Revisar colección',query:'auditar colección'}]);
    } finally {
      clearTimeout(timeout);chatBusy=false; send.disabled=false; send.textContent='Enviar';
    }
  });

  // Chips de chat
  document.querySelectorAll('.chat-prompt-chips .chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const prompt = chip.getAttribute('data-prompt');
      if (prompt && chatInput) {
        chatInput.value = prompt;
        chatInput.focus();
      }
    });
  });

  // Auditoría
  document.getElementById('btn-run-audit')?.addEventListener('click', async () => {
    const btn = document.getElementById('btn-run-audit');
    btn.disabled = true;
    btn.textContent = 'Auditando...';
    try {
      const resp = await apiFetch('/api/audit');
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error);
      document.getElementById('audit-health').textContent = `${data.health_score}%`;
      document.getElementById('audit-missing-bpm').textContent = data.missing_bpm_count;
      document.getElementById('audit-missing-key').textContent = data.missing_key_count;

      const details = document.getElementById('audit-details');
      details.innerHTML = `
        <p>Total de tracks analizados: <strong>${data.total_tracks}</strong></p>
        <p>Tracks sin duración: <strong>${data.missing_duration_count}</strong></p>
        <p>Rutas no locales o atípicas: <strong>${data.invalid_location_count}</strong></p>
      `;
    } catch (err) {
      notice('Error ejecutando auditoría: ' + err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Ejecutar Auditoría Completa';
    }
  });

  // Verificación completa de duplicados, en segundo plano y cancelable.
  let duplicateScanId = null;
  let duplicatePollBusy = false;
  let duplicateTimer = null;
  const duplicateButton = document.getElementById('btn-run-duplicates');
  const duplicateCancel = document.getElementById('btn-cancel-duplicates');
  const duplicateProgress = document.getElementById('duplicate-progress');
  function renderDuplicateScan(data) {
    if (data.state === 'idle') return;
    duplicateScanId = data.scan_id;
    const running = data.state === 'running';
    duplicateButton.disabled = running;
    duplicateButton.textContent = running ? 'Verificando…' : 'Verificar toda la colección';
    duplicateCancel.hidden = !running;
    duplicateCancel.disabled = false;
    const labels = {running:'Leyendo archivos', complete:'Análisis terminado', cancelled:'Análisis cancelado', stale:'Análisis desactualizado', failed:'Error de análisis'};
    duplicateProgress.textContent = `${labels[data.state] || data.state}: ${data.phase || "Comparando"} · ${data.processed}/${data.total} referencias · ${data.skipped_unique_size || 0} archivos con tamaño único · ${data.hashed_files} archivos leídos completos · ${(data.bytes_read / 1024**3).toFixed(2)} GiB · ${data.unavailable.length} no verificables. ${data.error || ''}`;
    document.getElementById('duplicate-rule').hidden = data.state !== 'complete';
    if (running) return;
    if (duplicateTimer) { clearTimeout(duplicateTimer); duplicateTimer = null; }
    const list = document.getElementById('duplicates-list'); list.replaceChildren();
    if (data.state !== 'complete') {
      const warning = document.createElement('p'); warning.textContent = 'La regla requiere un análisis completo de la colección actual.'; list.append(warning); return;
    }
    const groups = data.groups || [];
    if (!groups.length) { const message = document.createElement('p'); message.textContent = 'No se encontraron grupos de coincidencias. Archivos distintos por SHA-256 aún pueden contener la misma grabación con otras etiquetas o codificación.'; list.append(message); }
    // Paginar evita bloquear la ventana con colecciones muy grandes.
    let offset = 0;
    const more = document.createElement('button'); more.className = 'btn btn-secondary'; more.type = 'button';
    const appendPage = () => {
      for (const group of groups.slice(offset, offset + 50)) {
        const card = document.createElement('div'); card.className = 'duplicate-card';
        const title = document.createElement('strong'); title.textContent = `${group.score}% · ${group.classification} · ${group.tracks.length} referencias`;
        const reason = document.createElement('p'); reason.className = 'hint'; reason.textContent = group.reason;
        const paths = document.createElement('details');
        const summary = document.createElement('summary'); summary.textContent = 'Ver canciones y rutas'; paths.append(summary);
        for (const row of group.tracks) { const line = document.createElement('p'); line.className = 'hint'; line.textContent = `${row.artist} — ${row.title} · ID ${row.id} · ${row.path || row.error || 'Sin ruta disponible'}`; paths.append(line); }
        card.append(title, reason, paths); list.append(card);
      }
      offset += 50; more.remove();
      if (offset < groups.length) { more.textContent = `Mostrar más (${groups.length - offset} grupos)`; list.append(more); }
    };
    more.addEventListener('click', appendPage); appendPage();
    if (data.unavailable.length) {
      const details = document.createElement('details'); const title = document.createElement('summary'); title.textContent = `${data.unavailable.length} referencias que no se pudieron verificar`; details.append(title);
      for (const row of data.unavailable) { const line = document.createElement('p'); line.textContent = `ID ${row.id}: ${row.reason}`; details.append(line); } list.append(details);
    }
  }
  async function pollDuplicateScan() {
    if (duplicatePollBusy) return;
    duplicatePollBusy = true;
    try {
      const response = await apiFetch('/api/duplicates/scan'); const data = await response.json();
      if (!response.ok) throw new Error(data.error);
      renderDuplicateScan(data);
      if (data.state === 'running') duplicateTimer = setTimeout(pollDuplicateScan, 1500);
    } catch (error) {
      duplicateProgress.textContent = 'No se pudo consultar el análisis: ' + error.message;
      duplicateButton.disabled = false;
    } finally { duplicatePollBusy = false; }
  }
  duplicateButton?.addEventListener('click', async () => {
    duplicateButton.disabled = true;
    document.getElementById('duplicate-rule').hidden = true;
    document.getElementById('duplicate-rule-preview').replaceChildren();
    try {
      const response = await apiFetch('/api/playlists'); const library = await response.json();
      if (!response.ok) throw new Error(library.error);
      renderDuplicateScan(await post('/api/duplicates/scan/start', {source_revision:library.revision}));
      if (duplicateTimer) clearTimeout(duplicateTimer);
      duplicateTimer = setTimeout(pollDuplicateScan, 300);
    } catch (error) { notice(error.message); duplicateButton.disabled = false; }
  });
  duplicateCancel?.addEventListener('click', async () => {
    duplicateCancel.disabled = true;
    try { await post('/api/duplicates/scan/cancel', {scan_id:duplicateScanId}); duplicateProgress.textContent = 'Cancelando al terminar el bloque actual…'; }
    catch (error) { notice(error.message); duplicateCancel.disabled = false; }
  });
  document.getElementById('btn-duplicate-rule')?.addEventListener('click', async () => {
    const button = document.getElementById('btn-duplicate-rule'); button.disabled = true;
    try {
      const input = document.getElementById('duplicate-threshold');
      if (!input.value.trim() || !input.checkValidity()) throw new Error('Ingresá un porcentaje entre 0 y 100.');
      const rule = await post('/api/duplicates/rule', {scan_id:duplicateScanId, threshold:Number(input.value)});
      const output = document.getElementById('duplicate-rule-preview'); output.replaceChildren();
      const summary = document.createElement('p'); summary.textContent = `Referencias candidatas: ${rule.references} · Archivos candidatos: ${rule.files} · Grupos protegidos: ${rule.protected.length}.`; output.append(summary);
      const details = document.createElement('details'); const heading = document.createElement('summary'); heading.textContent = 'Revisar selección y pistas conservadas'; details.append(heading);
      for (const row of rule.selected) { const line = document.createElement('p'); line.className='hint'; line.textContent = `Retirar ID ${row.id} · ${row.path}. Conservar ID ${row.keeper_id} · ${row.keeper_path}${row.remove_file ? '' : ' · El archivo compartido se conserva.'}`; details.append(line); }
      output.append(details);
      if (rule.protected.length) {
        const protectedRows = document.createElement('details'); const heading = document.createElement('summary'); heading.textContent = 'Por qué se protegieron estos grupos'; protectedRows.append(heading);
        for (const group of rule.protected) { const line = document.createElement('p'); line.className='hint'; line.textContent = `${group.score}% · IDs ${group.track_ids.join(', ')} · ${group.reason}`; protectedRows.append(line); }
        output.append(protectedRows);
      }
      const warning = document.createElement('p'); warning.className='hint'; warning.textContent=rule.delete_reason; output.append(warning);
      notice('Regla revisada. No se eliminó ningún archivo.');
    } catch (error) { notice(error.message); }
    finally { button.disabled = false; }
  });
  // Al volver a abrir la interfaz se recupera el estado del trabajo del backend.
  document.getElementById('btn-duplicate-delete')?.addEventListener('click',async()=>{
    const button=document.getElementById('btn-duplicate-delete');const status=document.getElementById('duplicate-delete-state');
    button.disabled=true;
    try {
      if(!window.__TAURI__)throw new Error('Esta operación requiere la aplicación Windows y su confirmación nativa.');
      const input=document.getElementById('duplicate-threshold');
      if(!input.value.trim() || !input.checkValidity())throw new Error('Elegí un porcentaje entre 0 y 100.');
      const state=await (await apiFetch('/api/status')).json();
      const processes=await (await apiFetch('/api/rekordbox/processes')).json();
      if(processes.state!=='closed'){
        window.RekordAI.pendingDuplicate=true;status.textContent=processes.reason;
        notice(processes.reason,'info',{label:processes.state==='open'?'Cerrar desde acá…':'Comprobar procesos',run:()=>{window.RekordAI.openSettings('native-process-status');if(processes.state==='open')window.RekordAI.closeRekordbox('normal');}});return;
      }
      window.RekordAI.pendingDuplicate=false;
      status.textContent='Preparando y verificando respaldo, correspondencia nativa y archivos…';
      const preview=await post('/api/duplicates/prepare',{scan_id:duplicateScanId,threshold:Number(input.value)});
      status.textContent=`Propuesta: ${preview.references} referencias, ${preview.files} archivos retirables, ${preview.protected.length} referencias protegidas por conflictos nativos. Respaldo: ${preview.backup_directory}`;
      const result=await window.__TAURI__.core.invoke('approve_native_operation',{token:preview.token,sourceRevision:state.snapshot_revision});
      if(result.state==='cancelled'){status.textContent='Cancelado. La colección y los archivos originales siguen intactos.';return;}
      status.textContent='Duplicados consolidados. Playlists enlazadas a las pistas conservadas. Podés recuperar colección y música desde Configuración → Respaldos.';
      notice(result.collection_reload_warning || 'Consolidación completada y respaldada. Se conserva el XML original.',result.collection_reload_warning?'error':'success');
      duplicateScanId=null;document.getElementById('duplicate-rule').hidden=true;
      await window.RekordAI.refreshStatus();
    }catch(error){status.textContent=error.message;const pending=/transacciones pendientes/.test(error.message);if(pending)window.RekordAI.pendingDuplicate=true;notice(error.message,'error',pending?{label:'Respaldar y recuperar…',run:()=>{window.RekordAI.openSettings('transactions-recover');window.RekordAI.recoverTransactions();}}:null);}
    finally{button.disabled=false;}
  });
  pollDuplicateScan();

  function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  async function post(path, payload) {
    const resp = await apiFetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    const result = await resp.json();
    if (!resp.ok) throw new Error(result.error || 'Solicitud rechazada');
    return result;
  }
  function showStatus(data) {
    const needsSetup = data.demo || !!data.library_error;
    document.getElementById('setup-notice').hidden = !needsSetup;
    document.getElementById('open-setup').classList.toggle('needs-attention', needsSetup);
    document.querySelector('[data-tab="tab-config"]').classList.toggle('needs-attention', needsSetup);
    window.dispatchEvent(new CustomEvent('availability-updated', {detail:data}));
    const banner = document.getElementById('runtime-status');
    const llmLabel = {not_started:'disponible bajo demanda',loading:'cargando',ready:'lista',degraded:'no disponible; formulario activo',not_configured:'sin configurar'}[data.llm.state] || data.llm.state;
    banner.textContent = `${data.demo ? 'DEMOSTRACIÓN · ' : ''}${data.library_error || `${data.tracks_count} pistas de la colección cargada`} · IA: ${llmLabel}`;
    if (data.settings_error) banner.textContent += ' · ' + data.settings_error;
    if (data.native_operation_active) banner.textContent += ' · Operación sobre la colección en curso: esperá antes de salir o actualizar.';
    document.getElementById('rb-state').textContent = {open:'Abierto',closed:'Cerrado',unknown:'Desconocido'}[data.rekordbox_state] || 'Desconocido';
    if(window.RekordAI.pendingDuplicate && data.native_process_state==='closed'){document.getElementById('duplicate-delete-state').textContent='Rekordbox está cerrado. Podés volver a preparar el respaldo y revisar la eliminación.';document.getElementById('native-close-return').hidden=false;}
    document.getElementById('native-reason').textContent = 'Crear playlists requiere cerrar Rekordbox y sus agentes, respaldo automático y confirmación. Usá el botón de arriba. Restaurá desde Respaldos y recuperación.';
    document.getElementById('native-prepare').disabled = data.native_process_state !== 'closed' || data.native_operation_active || data.demo || !data.snapshot_revision;
    document.getElementById('rekordbox-close').disabled = data.native_process_state !== 'open' || data.native_operation_active || window.RekordCloseBusy === true;
    document.getElementById('live-reason').textContent = 'Las recomendaciones sin audio usan una referencia del historial y los filtros guardados de tu colección. Consultá el estado del popup arriba; no se requiere certificar el master para este modo.';
    document.getElementById('live-action').disabled = false;
    const energy = document.querySelector('#plan-mode option[value="energy"]');
    energy.disabled = !data.energy_available;
    energy.title = data.energy_available ? '' : 'Cargá energías con procedencia para esta colección';
    if (energy.disabled && document.getElementById('plan-mode').value === 'energy') document.getElementById('plan-mode').value = 'bpm';
  }
  async function loadSettings() {
    const response = await apiFetch('/api/settings');
    if (!response.ok) throw new Error('No se pudieron leer las preferencias');
    const s = await response.json();
    document.getElementById('config-energy-path').value = s.energies_json;
    for (const [id,value] of Object.entries({'config-llm':s.llm_enabled,'config-push':s.notifications.enabled,'history-monitor':s.notifications.history_popup,'config-silence':s.notifications.silenced,'rec-match-bpm':s.recommendation.match_bpm,'rec-harmonic':s.recommendation.harmonic,'rec-genre':s.recommendation.same_genre,'rec-artist':s.recommendation.avoid_same_artist})) document.getElementById(id).checked=value;
    for (const [id,value] of Object.entries({'config-frequency':s.notifications.min_frequency_seconds,'rec-duration':s.recommendation.min_duration_seconds==null?'':s.recommendation.min_duration_seconds/60,'rec-key-mode':s.recommendation.key_mode,'rec-count':s.recommendation.count,'rec-bpm':s.recommendation.max_bpm_delta,'rec-energy':s.recommendation.max_energy_delta ?? ''})) document.getElementById(id).value=value;
  }
  document.getElementById('library-form').addEventListener('submit', async e => {
    e.preventDefault();
    try {
      await post('/api/library', {path:document.getElementById('config-xml-path').value,energies_path:document.getElementById('config-energy-path').value});
      chatReference=null;
      chatHistory=[];
      hideMentions();
      lastPlanResult=null;
      document.getElementById('btn-export-xml').disabled=true;
      document.getElementById('plan-table-container').style.display='none';
      document.getElementById('plan-metrics').style.display='none';
      document.getElementById('plan-exclusions-card').style.display='none';
      const adjCard = document.getElementById('plan-adjustments-card'); if (adjCard) adjCard.style.display = 'none';
      document.getElementById('plan-empty-state').style.display='block';
      await loadInitialData();
      notice('Colección cargada correctamente.', 'success');
    } catch(error) { notice(error.message); }
  });
  document.getElementById('settings-form').addEventListener('submit', async e => {
    e.preventDefault();
    const checked=id=>document.getElementById(id).checked;
    const number=id=>Number(document.getElementById(id).value);
    try {
      await post('/api/settings',{llm_enabled:checked('config-llm'),notifications:{enabled:checked('config-push'),history_popup:checked('history-monitor'),silenced:checked('config-silence'),min_frequency_seconds:number('config-frequency')},recommendation:{match_bpm:checked('rec-match-bpm'),key_mode:document.getElementById('rec-key-mode').value,min_duration_seconds:document.getElementById('rec-duration').value===''?null:number('rec-duration')*60,count:number('rec-count'),max_bpm_delta:number('rec-bpm'),max_energy_delta:document.getElementById('rec-energy').value === '' ? null : number('rec-energy'),harmonic:checked('rec-harmonic'),same_genre:checked('rec-genre'),avoid_same_artist:checked('rec-artist')}});
      notice('Preferencias guardadas.', 'success');
      await loadSettings();
    } catch(error) { notice(error.message); }
  });
  document.getElementById('recommend-form').addEventListener('submit', async e => {
    e.preventDefault();
    const output=document.getElementById('recommend-result');
    try {
      const data=await post('/api/recommend',{current_track_id:document.getElementById('rec-track').value.trim()});
      output.textContent=data.recommendations.map(t=>`ID ${t.id}: ${t.artist} — ${t.title} · ${t.bpm} BPM`).join('\n') || 'No hay candidatas con los filtros guardados.';
    } catch(error) { output.textContent=error.message; }
  });
  chatMessages.addEventListener('click', e => {
    if(e.target.closest('.view-plan')) document.querySelector('[data-tab="tab-planner"]').click();
  });
  document.getElementById('live-action').addEventListener('click', async () => {
    try { const response=await apiFetch('/api/live-suggestion'); const result=await response.json(); notice(result.body || result.reason); } catch(error) { notice(error.message); }
  });
  async function detectInstallation() {
    const label = document.getElementById('discovery-status');
    label.textContent = 'Buscando instalaciones y configuraciones…';
    try {
      const response = await apiFetch('/api/discovery');
      if (!response.ok) throw new Error('No se pudo completar la detección');
      const data = await response.json();
      label.textContent = data.installations.length ? `Rekordbox detectado · ${data.installations.length} instalación(es)` : 'No encontramos una instalación en las ubicaciones conocidas.';
      const list = document.getElementById('discovery-results');
      list.replaceChildren();
      for (const text of [...data.installations.map(i => `${i.version} · ${i.path}`), ...data.databases.map(p => `Colección localizada: ${p}`), ...data.warnings]) {
        const li = document.createElement('li'); li.textContent = text; list.append(li);
      }
      document.getElementById('discovery-next').textContent = data.next_step;
      for (const path of data.export_candidates) {
        const button = document.createElement('button'); button.type = 'button'; button.className = 'btn btn-secondary';
        button.textContent = `Usar exportación detectada: ${path}`;
        button.addEventListener('click', () => { document.getElementById('config-xml-path').value = path; document.getElementById('library-form').requestSubmit(); });
        const li = document.createElement('li'); li.append(button); list.append(li);
      }
    } catch (error) { label.textContent = error.message; }
  }
  document.getElementById('rescan').addEventListener('click', detectInstallation);
  document.getElementById('open-setup').addEventListener('click', () => document.querySelector('[data-tab="tab-config"]').click());
  detectInstallation();
  loadInitialData();
  loadSettings().catch(error=>console.warn(error.message));
  async function updateLiveCockpit() {
    const cockpit = document.getElementById('live-cockpit');
    if (!cockpit) return;
    try {
      const response = await apiFetch('/api/history-suggestion');
      if (!response.ok) return;
      const data = await response.json();

      const pulse = document.getElementById('cockpit-pulse');
      const statusTitle = document.getElementById('cockpit-status-title');
      const statusText = document.getElementById('cockpit-status-text');
      const trackInfo = document.getElementById('cockpit-track-info');
      const emptyBox = document.getElementById('cockpit-empty');
      const emptyMsg = document.getElementById('cockpit-empty-msg');
      const btnRec = document.getElementById('btn-cockpit-rec');

      if (!data.connected) {
        if (pulse) pulse.className = 'status-pulse pulse-off';
        if (statusTitle) statusTitle.textContent = 'Modo offline';
        if (statusText) statusText.textContent = data.reason || 'Rekordbox cerrado';
        if (trackInfo) trackInfo.style.display = 'none';
        if (emptyBox) emptyBox.style.display = 'block';
        if (emptyMsg) emptyMsg.textContent = 'Rekordbox cerrado. Abrí Rekordbox para activar telemetría en tiempo real, o usá el asistente para planificar tu colección.';
        if (btnRec) btnRec.style.display = 'none';
        return;
      }

      if (data.reference_track) {
        const t = data.reference_track;
        if (pulse) pulse.className = 'status-pulse pulse-on';
        if (statusTitle) statusTitle.textContent = 'En vivo · Rekordbox';
        if (statusText) statusText.textContent = 'Pista activa en historial';
        if (trackInfo) trackInfo.style.display = 'flex';
        if (emptyBox) emptyBox.style.display = 'none';

        const titleEl = document.getElementById('cockpit-title');
        const artistEl = document.getElementById('cockpit-artist');
        const bpmEl = document.getElementById('cockpit-bpm');
        const keyEl = document.getElementById('cockpit-key');
        const genreEl = document.getElementById('cockpit-genre');

        if (titleEl) titleEl.textContent = t.title || 'Sin título';
        if (artistEl) artistEl.textContent = t.artist || 'Sin artista';
        if (bpmEl) bpmEl.textContent = t.bpm != null ? `${Number(t.bpm).toFixed(1)} BPM` : '—';
        if (keyEl) keyEl.textContent = t.key || '—';
        if (genreEl) genreEl.textContent = t.genre || 'Sin género';

        if (btnRec) {
          btnRec.style.display = 'inline-flex';
          btnRec.onclick = () => {
            const chatInput = document.getElementById('chat-input');
            if (chatInput) {
              chatInput.value = `¿Qué pistas de mi colección combinan bien con ${t.artist} - ${t.title}?`;
              chatInput.focus();
              chatInput.form.requestSubmit();
            }
          };
        }
      } else {
        if (pulse) pulse.className = 'status-pulse pulse-waiting';
        if (statusTitle) statusTitle.textContent = 'Rekordbox detectado';
        if (statusText) statusText.textContent = 'Esperando reproducción';
        if (trackInfo) trackInfo.style.display = 'none';
        if (emptyBox) emptyBox.style.display = 'block';
        if (emptyMsg) emptyMsg.textContent = data.reason || 'Reproducí una pista en Rekordbox (se sincroniza automáticamente tras ~30s de reproducción).';
        if (btnRec) btnRec.style.display = 'none';
      }
    } catch (_) {}
  }

  let refreshing=false;
  function pollStatus() {
    setInterval(async()=>{
      if(refreshing || document.hidden)return;
      refreshing=true;
      try {
        const response=await apiFetch('/api/status');
        if(response.ok)showStatus(await response.json());
        await updateLiveCockpit();
      }
      catch(error){document.getElementById('runtime-status').textContent='Servicio local no disponible';}
      finally{refreshing=false;}
    },5000);
  }
  if(window.__TAURI__) {
    window.__TAURI__.event.listen('backend-status',event=>{
      showStatus(event.payload);
      updateLiveCockpit();
    }).catch(()=>pollStatus());
    updateLiveCockpit();
  } else {
    pollStatus();
    updateLiveCockpit();
  }
});
