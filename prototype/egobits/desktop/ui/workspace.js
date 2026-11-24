document.addEventListener('DOMContentLoaded', () => {
  const api = window.RekordAI;
  const $ = id => document.getElementById(id);
  let revision = null, offset = 0, query = '', browserRows = [], selected = [], genres = [], searchSequence = 0;
  function text(tag, value, className = '') { const node = document.createElement(tag); node.textContent = value; node.className = className; return node; }
  function go(tab) { document.querySelector(`[data-tab="${tab}"]`).click(); }
  async function read(path) { const response = await api.apiFetch(path); const result = await response.json(); if (!response.ok) throw new Error(result.error || 'No se pudo completar'); return result; }
  let opportunityId=null,opportunityOffset=0,opportunityRevision=null,opportunityRequest=0;
  async function openOpportunity(id,more=false) {
    const sequence=++opportunityRequest;
    try {
      if(!more){const state=await read('/api/status');if(sequence!==opportunityRequest)return;opportunityRevision=state.snapshot_revision;opportunityId=id;opportunityOffset=0;$('opportunity-tracks').replaceChildren();}
      const data=await read(`/api/opportunity?id=${encodeURIComponent(id)}&offset=${opportunityOffset}&revision=${encodeURIComponent(opportunityRevision)}`);
      if(sequence!==opportunityRequest)return;
      $('opportunity-title').textContent=`${data.title} · ${data.total} pistas`;
      $('opportunity-config').textContent=id==='energy'?'Configurar energía':id==='unlisted'?'Preparar un set':'Cargar XML actualizado';
      $('opportunity-description').textContent=data.description;$('opportunity-instructions').textContent=data.instructions;
      for(const track of data.tracks){
        const row=text('div','','insight-card');row.append(text('p',`${track.artist || 'Sin artista'} — ${track.title} · ID ${track.id} · ${track.bpm ?? 'Sin BPM'} · ${track.key || 'Sin tonalidad'}`));
        const details=text('button','Ver detalles de esta pista','btn btn-secondary');details.type='button';
        if(track.in_collection===false){details.disabled=true;details.textContent='Actualizá el XML para invocar esta pista';}
        details.onclick=()=>{$('opportunity-dialog').close();go('tab-chat');$('chat-input').value=`describí pista ${track.id}`;$('chat-input').form.requestSubmit();};
        row.append(details);$('opportunity-tracks').append(row);
      }
      opportunityOffset=data.next_offset;$('opportunity-more').hidden=opportunityOffset==null;
      if(!$('opportunity-dialog').open)$('opportunity-dialog').showModal();
    }catch(error){api.notice(error.message,'error');}
  }
  window.addEventListener('open-opportunity',event=>openOpportunity(event.detail.id));
  $('opportunity-more').onclick=()=>openOpportunity(opportunityId,true);
  $('opportunity-config').onclick=()=>{$('opportunity-dialog').close();go(opportunityId==='unlisted'?'tab-planner':'tab-config');const target=opportunityId==='energy'?'config-energy-path':'library-form';if(opportunityId!=='unlisted')api.openSettings(target);};
  for (const [button, input, kind] of [['browse-library','config-xml-path','library'], ['browse-energies','config-energy-path','energies']]) {
    $(button).addEventListener('click', async () => {
      $(button).disabled = true;
      try { const result = await api.post('/api/dialog', {kind}); if (result.path) $(input).value = result.path; }
      catch (error) { api.notice(error.message, 'error'); }
      finally { $(button).disabled = false; }
    });
  }
  function addTrack(track) {
    if (selected.some(t => t.id === track.id)) return;
    if (selected.length >= 100) { api.notice('La selección admite hasta 100 pistas.'); return; }
    selected.push(track); renderSelection();
  }
  function renderSelection() {
    api.selection = selected.map(t => t.id); $('draft-list').replaceChildren();
    selected.forEach((track, index) => {
      const row = text('div', '', 'selected-track');
      row.append(text('span', `${index + 1}. ${track.artist} — ${track.title}`));
      for (const [label, shift] of [['↑', -1], ['↓', 1], ['×', 0]]) {
        const button = text('button', label, 'btn btn-secondary btn-sm'); button.type = 'button';
        button.setAttribute('aria-label', `${shift ? (shift < 0 ? 'Subir' : 'Bajar') : 'Quitar'} ${track.title}`);
        button.disabled = (shift < 0 && index === 0) || (shift > 0 && index === selected.length - 1);
        button.addEventListener('click', () => {
          if (!shift) selected.splice(index, 1);
          else [selected[index], selected[index + shift]] = [selected[index + shift], selected[index]];
          renderSelection();
        }); row.append(button);
      }
      $('draft-list').append(row);
    });
    if (!selected.length) $('draft-list').append(text('p', 'Todavía no elegiste canciones.', 'hint'));
    $('preview-draft').disabled = !selected.length;
    $('draft-audit').textContent = `${selected.length} pistas. Al revisar se vuelven a comprobar todas las transiciones.`;
  }
  const drop = $('draft-list');
  drop.addEventListener('dragover', e => { if (Array.from(e.dataTransfer.types).includes('application/x-rekord-track')) { e.preventDefault(); drop.classList.add('drag-target'); } });
  drop.addEventListener('dragleave', () => drop.classList.remove('drag-target'));
  drop.addEventListener('drop', e => {
    e.preventDefault(); drop.classList.remove('drag-target');
    const id = e.dataTransfer.getData('application/x-rekord-track');
    const track = browserRows.find(t => t.id === id); if (track) addTrack(track);
  });
  $('clear-draft').addEventListener('click', () => { selected = []; renderSelection(); });
  $('preview-draft').addEventListener('click', async () => {
    try {
      const result = await api.post('/api/draft', {track_ids:selected.map(t => t.id), source_revision:revision});
      api.setPlan(result); $('draft-audit').textContent = result.audit.issues.length ? result.audit.issues.map(i => i.detail).join(' · ') : 'Sin incidencias de metadatos detectadas. Revisá la mezcla de oído.';
      api.notice('Orden manual listo para revisar y exportar.', 'success');
    } catch (error) { api.notice(error.message, 'error'); }
  });
  async function loadTracks(reset = true) {
    const sequence = ++searchSequence;
    if (reset) { offset = 0; browserRows = []; }
    query = $('track-search').value.trim();
    try {
      const data = await read(`/api/tracks?q=${encodeURIComponent(query)}&offset=${offset}`);
      if (sequence !== searchSequence) return;
      if (reset) $('track-browser').replaceChildren();
      browserRows.push(...data.tracks); offset += data.tracks.length;
      for (const track of data.tracks) {
        const row = text('div', '', 'browser-track'); row.draggable = true;
        row.addEventListener('dragstart', e => e.dataTransfer.setData('application/x-rekord-track', track.id));
        const body = text('div', ''); body.append(text('strong', track.title || 'Sin título'), text('p', `${track.artist || 'Sin artista'} · ${track.bpm ?? '—'} BPM · ${track.key || 'Sin tonalidad'} · ${track.genre || 'Sin género'}`, 'hint'));
        const button = text('button', 'Agregar', 'btn btn-secondary btn-sm'); button.type = 'button'; button.setAttribute('aria-label', `Agregar ${track.title}`); button.addEventListener('click', () => addTrack(track));
        const suggest = text('button', 'Sugerir próximas', 'btn btn-secondary btn-sm'); suggest.type='button'; suggest.setAttribute('aria-label', `Sugerir próximas desde ${track.title}`); suggest.addEventListener('click', async () => { await findConnections(track); go('tab-audit'); });
        row.append(body, button, suggest); $('track-browser').append(row);
      }
      $('track-count').textContent = `${offset} de ${data.total} pistas`; $('track-more').disabled = offset >= data.total;
      if (!data.total) $('track-browser').append(text('p', 'No hay coincidencias.', 'hint'));
    } catch (error) { api.notice(error.message, 'error'); }
  }
  $('track-search-button').addEventListener('click', () => loadTracks());
  $('track-search').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); loadTracks(); } });
  $('track-more').addEventListener('click', () => loadTracks(false));
  $('plan-source').addEventListener('change', () => { $('playlist-checkboxes').hidden = $('plan-source').value !== 'playlists'; });
  function chart(id, values, onSelect) {
    const root = $(id); root.replaceChildren(); const entries = Object.entries(values); const total = entries.reduce((sum, [,count]) => sum + count, 0);
    const rows = entries.slice(0, 10); const others = entries.slice(10).reduce((sum, [,count]) => sum + count, 0); if (others) rows.push(['Otros', others]);
    for (const [label, count] of rows) {
      const row = text(onSelect ? 'button' : 'div', '', 'chart-row'); if (onSelect) { row.type='button'; row.addEventListener('click', () => onSelect(label)); }
      const heading = text('div', '', 'chart-label'); heading.append(text('span', label), text('span', `${count} · ${total ? Math.round(count / total * 100) : 0}%`));
      const bar = text('div', '', 'chart-bar'); const fill = text('span', ''); fill.style.width=`${total ? count / total * 100 : 0}%`; bar.append(fill); row.append(heading, bar); root.append(row);
    }
    if (!rows.length) root.append(text('p', 'No hay datos todavía.', 'hint'));
  }
  async function findConnections(track) {
    const root = $('collection-connections'); root.textContent='Buscando canciones compatibles…';
    try {
      const data=await api.post('/api/recommend',{current_track_id:track.id}); root.replaceChildren();
      root.append(text('strong',`Referencia manual: ${track.artist} — ${track.title}`));
      root.append(text('p','Se aplicaron tus filtros guardados. '+data.warning,'hint'));
      for (const candidate of data.recommendations) {
        const row=text('div','','insight-card'); row.append(text('p',`${candidate.artist} — ${candidate.title} · ${candidate.bpm} BPM · ${candidate.key || 'Sin tonalidad'} · ${candidate.genre || 'Sin género'}`));
        const button=text('button','Agregar a mi selección','btn btn-secondary');button.type='button';button.addEventListener('click',()=>{addTrack(candidate);api.notice('Canción agregada a tu selección.','success');});row.append(button);root.append(row);
        if(candidate.match_reasons)row.append(text('p',candidate.match_reasons.join(' · '),'hint'));
        const info=text('button','Ver detalles','btn btn-secondary');info.type='button';info.onclick=()=>{go('tab-chat');$('chat-input').value=`describí pista ${candidate.id}`;$('chat-input').form.requestSubmit();};row.append(info);
      }
      if(!data.recommendations.length) root.append(text('p','No hay canciones que cumplan todos tus filtros. Revisá BPM, tonalidad, género o energía en Configuración.','hint'));
    } catch(error) {root.textContent=error.message;}
  }
  async function loadInsights() {
    try {
      const data = await read('/api/insights');
      $('audit-health').textContent=data.health_score+'%';$('audit-missing-bpm').textContent=data.missing_bpm_count;$('audit-missing-key').textContent=data.missing_key_count;
      genres = Object.keys(data.genres).filter(g => g !== 'Sin género');
      const genreSelect = $('plan-genre'); const old = genreSelect.value; genreSelect.replaceChildren(new Option('Todos los géneros','')); for (const g of genres) genreSelect.append(new Option(g,g)); genreSelect.value = genres.includes(old) ? old : '';
      $('collection-kpis').replaceChildren();
      for (const [label,value] of [['Pistas',data.total_tracks],['Playlists',data.playlists_count],['Artistas',data.artists_count],['Horas de audio',data.hours],['Con energía',data.energy_count],['Sin género',data.missing_genre_count]]) {
        const card = text('div','','metric-card'); card.append(text('span',String(value),'m-val'),text('span',label,'m-lbl')); $('collection-kpis').append(card);
      }
      const chooseGenre = genre => { if (!genres.includes(genre)) return; $('plan-source').value='collection'; $('plan-genre').value=genre; $('plan-source').dispatchEvent(new Event('change')); go('tab-planner'); };
      chart('genre-chart',data.genres,chooseGenre); chart('bpm-chart',data.bpm_distribution); chart('key-chart',data.keys);
      $('collection-suggestions').replaceChildren();
      for (const suggestion of data.suggestions) {
        const item = text('div','','insight-card'); item.append(text('p',suggestion.text));
        const button = text('button',suggestion.action === 'genre' ? 'Preparar este set' : suggestion.action === 'duplicates' ? 'Verificar candidatos' : suggestion.action === 'opportunity' ? 'Revisar pistas' : 'Ver configuración','btn btn-secondary'); button.type='button';
        if(suggestion.action==='opportunity')button.textContent='Ver pistas y solución';
        button.addEventListener('click',() => { if (suggestion.action==='opportunity')openOpportunity(suggestion.opportunity);else if (suggestion.action==='genre') chooseGenre(suggestion.genre); else if(suggestion.action==='duplicates') {go('tab-audit');$('btn-run-duplicates').scrollIntoView({block:'center',behavior:'smooth'});api.notice('Iniciá la verificación cuando quieras; este acceso no lee automáticamente todos tus archivos.');} else go('tab-config'); });
        if(suggestion.description)item.append(text('p',suggestion.description,'hint'));
        item.append(button); $('collection-suggestions').append(item);
      }
      if (!data.suggestions.length) $('collection-suggestions').append(text('p','Metadatos completos para los indicadores analizados.','hint'));
    } catch (error) { $('collection-suggestions').textContent=error.message; }
  }
  $('refresh-insights').addEventListener('click', loadInsights);
  document.querySelector('[data-tab="tab-audit"]').addEventListener('click', loadInsights);
  let recSequence = 0;
  async function loadReferences() {
    const sequence = ++recSequence;
    try {
      const data = await read(`/api/tracks?q=${encodeURIComponent($('rec-search').value)}&offset=0`);
      if(sequence!==recSequence) return;
      const old = $('rec-track').value; $('rec-track').replaceChildren(new Option('Elegí una pista de tu colección',''));
      for (const track of data.tracks) $('rec-track').append(new Option(`${track.artist} — ${track.title} · ${track.bpm ?? '—'} BPM`,track.id));
      if (data.tracks.some(t => t.id===old)) $('rec-track').value=old;
    } catch(error) { api.notice(error.message,'error'); }
  }
  let recTimer; $('rec-search').addEventListener('input',() => { clearTimeout(recTimer); recTimer=setTimeout(loadReferences,300); });
  window.addEventListener('collection-loaded',event => {
    if (revision !== event.detail.snapshot_revision) {
      revision=event.detail.snapshot_revision; selected=[]; $('collection-connections').replaceChildren(); renderSelection(); loadTracks(); loadReferences(); loadInsights();
    }
  });
  window.addEventListener('availability-updated',event => {
    const data=event.detail; const root=$('availability-overview'); root.replaceChildren();
    for (const [name,available,reason] of [
      ['Planificar y exportar XML / M3U8',!!data.snapshot_revision,!data.snapshot_revision ? 'Primero cargá una colección.' : data.demo ? 'Disponible con biblioteca de demostración. Cargá tu colección para trabajar con tu música.' : 'Disponible con tu colección cargada.'],
      ['Recomendar desde una pista elegida',!!data.snapshot_revision,'Elegí una pista de referencia y guardá tus filtros. No requiere escucha automática.'],
      ['Eliminar duplicados verificados',data.native_process_state==='closed' && !!data.snapshot_revision && !data.demo,'Mi colección → Verificar → Elegir porcentaje → Eliminar duplicados. La escritura requiere Rekordbox cerrado, respaldo y confirmación nativa. Metadatos o vínculos distintos quedan protegidos.'],
      ['Popup desde el historial',data.rekordbox_state==='open' && !data.demo && data.tracks_count>0 && data.notifications.enabled && !data.notifications.silenced && data.notifications.history_popup,'Activá el popup del historial y las notificaciones, desactivá silencio y esperá una entrada nueva. Puede tener demora y no confirma el master.'],
      ['Crear una playlist en Rekordbox',data.native_process_state==='closed' && !!data.snapshot_revision && !data.demo,'Configuración → Base y procesos: cargá tu colección real y cerrá Rekordbox y sus agentes. Exige respaldo automático, revisión y acceso exclusivo. Los cambios requieren revisión y confirmación.']
    ]) { const card=text('div','','availability-card'); card.append(text('strong',`${available ? '✓' : '○'} ${name}`),text('span',available ? 'Disponible' : 'Pendiente','availability-state'),text('p',reason)); root.append(card); }
  });
  // Guided configuration builds a reviewable proposal; it never exports automatically.
  let step=0; const wizard={source:'collection',count:10,genre:'',mode:'bpm',harmonic:true,artist:true,allowInsufficient:false,maxStep:3,name:'Mi próximo set'};
  function wizardField(label,type,id,value,options) {
    const group=text('div','','form-group'); const caption=text('label',label); caption.htmlFor=id;
    const field=document.createElement(type==='select' ? 'select' : 'input'); field.id=id;
    if(type==='select') for(const [label,val] of options) field.append(new Option(label,val)); else field.type=type;
    field.value=value; if(type==='number') {field.min='1';if(id!=='wiz-count')field.max='30';}
    group.append(caption,field); $('wizard-content').append(group); return field;
  }
  function renderWizard() {
    $('wizard-content').replaceChildren(); $('wizard-back').disabled=step===0; $('wizard-next').textContent=step===3 ? 'Crear propuesta' : 'Siguiente'; $('wizard-progress').textContent=`${step+1} / 4`;
    if(step===0) {
      $('wizard-title').textContent='¿Con qué música empezamos?';
      wizardField('Origen','select','wiz-source',wizard.source,[['Toda mi colección','collection'],['Playlists marcadas en el formulario','playlists'],['Mi selección manual','selected']]);
      $('wizard-content').append(text('p','Si elegís playlists o selección manual, marcá las canciones en Preparar un set antes de continuar.','hint'));
    } else if(step===1) {
      $('wizard-title').textContent='¿Qué identidad tendrá el set?';
      wizardField('Nombre de la playlist','text','wiz-name',wizard.name);
      wizardField('Género','select','wiz-genre',wizard.genre,[['Todos los géneros',''],...genres.map(g => [g,g])]);
      wizardField('Cantidad de pistas','number','wiz-count',wizard.count);
    } else if(step===2) {
      $('wizard-title').textContent='¿Cómo querés que evolucione?';
      const mode=wizardField('Curva','select','wiz-mode',wizard.mode,[['Subir BPM','bpm'],['Subir energía verificada','energy']]);
      if ($('plan-mode').querySelector('[value="energy"]').disabled) mode.querySelector('[value="energy"]').disabled=true;
      wizardField('Salto máximo entre canciones (BPM)','number','wiz-step',wizard.maxStep);
      for(const [label,id,value] of [['Compatibilidad de tonalidad Camelot','wiz-harmonic',wizard.harmonic],['Evitar artista consecutivo','wiz-artist',wizard.artist],['Permitir crear si los candidatos son insuficientes','wiz-insufficient',wizard.allowInsufficient]]) { const row=text('label',label,'checkbox-item'); const input=document.createElement('input');input.type='checkbox';input.id=id;input.checked=value;row.prepend(input);$('wizard-content').append(row); }
    } else {
      $('wizard-title').textContent='Revisá tu idea antes de crearla';
      $('wizard-content').append(text('p',`${wizard.name} · ${wizard.count} pistas · ${wizard.genre || 'todos los géneros'} · ${wizard.mode === 'bpm' ? 'BPM ascendente' : 'energía creciente'} · salto máximo ${wizard.maxStep} BPM.`));
      $('wizard-content').append(text('p','La propuesta usará pistas de la colección cargada. Si faltan candidatos o canciones compatibles, el modo flexible acomoda las pistas disponibles y reporta los ajustes. Después podrás revisarla y exportarla.','hint'));
    }
  }
  function saveWizard() {
    if(step===0) wizard.source=$('wiz-source').value;
    if(step===1) {wizard.name=$('wiz-name').value.trim();wizard.genre=$('wiz-genre').value;wizard.count=Number($('wiz-count').value);if(!wizard.name || !Number.isInteger(wizard.count) || wizard.count<1) throw new Error('Indicá un nombre y al menos 1 pista.');}
    if(step===2) {wizard.mode=$('wiz-mode').value;wizard.maxStep=Number($('wiz-step').value);wizard.harmonic=$('wiz-harmonic').checked;wizard.artist=$('wiz-artist').checked;wizard.allowInsufficient=$('wiz-insufficient').checked;if(!Number.isFinite(wizard.maxStep) || wizard.maxStep<=0 || wizard.maxStep>30) throw new Error('El salto de BPM debe ser mayor a 0 y no superar 30.');}
  }
  $('open-wizard').addEventListener('click',()=>{step=0;renderWizard();$('wizard-dialog').showModal();});
  $('wizard-back').addEventListener('click',()=>{step--;renderWizard();});
  $('wizard-next').addEventListener('click',async()=>{
    try {saveWizard(); if(step<3) {step++;renderWizard();return;}
      $('wizard-next').disabled=true;
      const playlists=Array.from(document.querySelectorAll('[name="selected_playlist"]:checked')).map(i=>i.value);
      const result=await api.post('/api/plan',{source:wizard.source,playlists,track_ids:selected.map(t=>t.id),genre:wizard.genre,count:wizard.count,mode:wizard.mode,max_bpm_step:wizard.maxStep,harmonic:wizard.harmonic,avoid_adjacent_artist:wizard.artist,allow_insufficient:wizard.allowInsufficient});
      $('plan-source').value=wizard.source; $('plan-count').value=wizard.count; $('plan-mode').value=wizard.mode;
      $('plan-max-step').value=wizard.maxStep; $('plan-harmonic').checked=wizard.harmonic;
      $('plan-avoid-artist').checked=wizard.artist; $('plan-allow-insufficient').checked=wizard.allowInsufficient; $('plan-genre').value=wizard.genre;
      $('plan-source').dispatchEvent(new Event('change'));
      $('plan-out-name').value=wizard.name;api.setPlan(result);$('wizard-dialog').close();api.notice('Propuesta lista. Revisá canciones y transiciones antes de exportar.','success');
    } catch(error) {api.notice(error.message,'error');}
    finally {$('wizard-next').disabled=false;}
  });
  renderSelection();
  $('rec-three-defaults').addEventListener('click',()=>{for(const id of ['rec-match-bpm','rec-genre','rec-harmonic'])$(id).checked=true;api.notice('BPM, género y tonalidad seleccionados. Guardá preferencias para aplicarlos al popup.','info');});
  let historyBusy=false;
  async function startMetadataRecommendations() {
    $('metadata-recommend-start').disabled=true;
    try {const data=await api.post('/api/history/start',{});$('history-monitor').checked=true;$('config-push').checked=true;$('config-silence').checked=false;api.notice(data.display?'Recomendaciones activadas con la última pista registrada. No se captura audio.':data.reason || 'Esperando una referencia del historial.','info');await refreshDelivery();await api.refreshStatus();}
    catch(error){api.notice(error.message,'error');}
    finally{$('metadata-recommend-start').disabled=false;}
  }
  $('metadata-recommend-start').addEventListener('click',startMetadataRecommendations);
  $('live-action').addEventListener('click',()=>{api.openSettings('recommendation-delivery-state');refreshDelivery();});
  let deliveryBusy=false;
  function showDelivery(data) {
    $('recommendation-delivery-state').textContent=data.display ? `Popup disponible · ${data.source==='rekordbox_history'?'referencia del historial':'detección de audio'} · ${data.recommendations.length} sugerencias` : data.reason || 'No hay una referencia identificada.';
  }
  async function refreshDelivery() {
    if(deliveryBusy)return;deliveryBusy=true;
    try {showDelivery(await read('/api/recommendation-popup'));}
    catch(error){$('recommendation-delivery-state').textContent=error.message;}
    finally{deliveryBusy=false;}
  }
  refreshDelivery();
  const pollDelivery=()=>setInterval(()=>{if(!document.hidden)refreshDelivery();},5000);
  if(window.__TAURI__)window.__TAURI__.event.listen('recommendation-delivery-update',event=>showDelivery(event.payload)).catch(()=>pollDelivery());
  else pollDelivery();
  if(window.__TAURI__)window.__TAURI__.event.listen('recommendation-needs-setup',event=>{go('tab-config');api.notice(event.payload.reason || 'Revisá el seguimiento de recomendaciones.','info');api.openSettings('recommendation-delivery-state');}).catch(error=>api.notice(error.message,'error'));
  $('audio-signal').addEventListener('click',async()=>{
    if(!$('audio-device').value || !$('audio-consent').checked){api.notice('Elegí una salida y confirmá el análisis local.','error');return;}
    $('audio-signal').disabled=true;$('audio-signal-state').textContent='Comprobando 3 segundos de señal local…';
    try{const data=await api.post('/api/audio/signal',{device_index:Number($('audio-device').value),accept_loopback:true});$('audio-signal-state').textContent=data.reason;}
    catch(error){$('audio-signal-state').textContent=error.message;}
    finally{$('audio-signal').disabled=false;}
  });
  setInterval(async()=>{
    if (document.hidden || !$('history-monitor').checked || historyBusy) return;
    historyBusy=true;
    try {
      const data=await read('/api/history-suggestion'); const root=$('history-suggestions');root.replaceChildren(text('p',data.reason,'hint'));
      if(data.reference_track) root.append(text('strong',`Referencia registrada: ${data.reference_track.artist} — ${data.reference_track.title}`));
      for(const track of data.recommendations||[]) root.append(text('p',`${track.artist} — ${track.title} · ${track.bpm} BPM · ${track.key||'Sin tonalidad'}`));
    } catch(error) {$('history-suggestions').textContent=error.message;}
    finally {historyBusy=false;}
  },5000);
  $('history-monitor').addEventListener('change',async()=>{
    try {const enabled=$('history-monitor').checked;if(enabled){await startMetadataRecommendations();return;}await api.post('/api/settings',{notifications:{history_popup:false}});
      if(!enabled)$('history-suggestions').replaceChildren();
      else api.notice($('config-push').checked?'Historial habilitado. Esperamos entradas nuevas; puede tener demora y no confirma el master.':'Historial habilitado. Activá también las sugerencias generales para mostrar el popup.','info');
    }catch(error){$('history-monitor').checked=!$('history-monitor').checked;api.notice(error.message,'error');}
  });
  $('audio-watch-start').addEventListener('click',async()=>{
    try {if(!$('audio-device').value)throw new Error('Detectá la salida de audio antes de activar el seguimiento.');const data=await api.post('/api/audio/watch/start',{automatic:true,device_index:Number($('audio-device').value),accept_loopback:$('audio-consent').checked,allow_popup:true});
      await api.post('/api/settings',{notifications:{enabled:true,silenced:false}});$('config-push').checked=true;$('config-silence').checked=false;
      $('audio-watch-state').textContent=data.reason;
    }catch(error){api.notice(error.message,'error');}
  });
  $('audio-watch-stop').addEventListener('click',async()=>{try{const data=await api.post('/api/audio/watch/stop',{});$('audio-watch-state').textContent=data.reason;}catch(error){api.notice(error.message,'error');}});
  let audioWatchBusy=false;
  setInterval(async()=>{if(audioWatchBusy)return;audioWatchBusy=true;try{const data=await read('/api/audio/watch');$('audio-watch-state').textContent=`${data.reason}${data.state==='indexing'?` · ${data.indexed}/${data.total}`:''}`;}catch{}finally{audioWatchBusy=false;}},3000);
  $('audio-devices-refresh').addEventListener('click',async()=>{
    try {const data=await read('/api/audio/devices');$('audio-device').replaceChildren(new Option('Elegí tu salida master',''));
      for(const device of data.devices) $('audio-device').append(new Option(device.name,String(device.index)));
      if(data.suggested_device_index!==null && data.suggested_device_index!==undefined)$('audio-device').value=String(data.suggested_device_index);
      $('audio-signal-state').textContent=data.reason;
      $('audio-result').textContent=data.reason;
    } catch(error) {api.notice(error.message,'error');}
  });
  $('audio-identify').addEventListener('click',async()=>{
    if(!$('audio-device').value || !$('audio-consent').checked) {api.notice('Elegí una salida y confirmá el análisis local.','error');return;}
    $('audio-identify').disabled=true;$('audio-result').textContent='Decodificando pistas y analizando 6 segundos de salida. Puede tardar según la selección…';
    try {const data=await api.post('/api/audio/identify',{automatic:true,device_index:Number($('audio-device').value),accept_loopback:true});
      $('audio-result').textContent=`${data.reason}\nCoincidencia: ${data.similarity??'—'} · margen: ${data.margin??'—'}\n${data.note||''}`;
    } catch(error) {$('audio-result').textContent=error.message;}
    finally {$('audio-identify').disabled=false;}
  });
  $('native-inspect').addEventListener('click',async()=>{
    try {const data=await read('/api/native/status');$('native-result').textContent=`${data.tracks} pistas · ${data.playlists} playlists · integridad ${data.integrity}\n${data.reason}`;}
    catch(error) {$('native-result').textContent=error.message;}
  });
  function approve(title, message, action) {
    return new Promise(resolve=>{
      const dialog=text('dialog','','app-dialog native-dialog'); const content=text('div','','wizard-content');
      content.append(text('h2',title),text('p',message));
      const cancel=text('button','Cancelar','btn btn-secondary'), confirm=text('button',action,'btn btn-primary');
      cancel.type=confirm.type='button';content.append(cancel,confirm);dialog.append(content);document.body.append(dialog);
      let done=false; const finish=value=>{if(done)return;done=true;dialog.close();dialog.remove();resolve(value);};
      cancel.onclick=()=>finish(false);confirm.onclick=()=>finish(true);dialog.addEventListener('cancel',event=>{event.preventDefault();finish(false);});dialog.showModal();
    });
  }
  async function loadBackups() {
    const root=$('native-backups');root.replaceChildren();
    try {const [native,transactions]=await Promise.all([read('/api/native/backups'),read('/api/transactions/backups')]);const data={backups:[...native.backups,...transactions.backups.map(item=>({...item,name:item.name||'Recuperación de transacciones',transaction:true}))]};
      if(!data.backups.length) root.append(text('p','Todavía no hay respaldos. Se creará uno antes de tu primera escritura.','hint'));
      for(const item of data.backups) {
        const states={prepared:'Propuesta pendiente',prepared_restore:'Restauración pendiente',checkpointing:'Recuperación necesaria',restoring:'Recuperación necesaria',publishing:'Recuperación necesaria',recovery_required:'Recuperación necesaria',applied:'Aplicado',rolled_back:'Revertido automáticamente',restored:'Restaurado',invalid:'Recibo ilegible'};
        const card=text('div','','availability-card');card.append(text('strong',item.name),text('p',`${new Date(item.created_at*1000).toLocaleString()} · ${states[item.state]||'Estado desconocido'} · ${item.verified?'SHA-256 verificado':'Verificación fallida'}`));
        const button=text('button','Restaurar este respaldo','btn btn-secondary');button.disabled=!item.verified;button.type='button';
        button.onclick=async()=>{
          if(!await approve('Restaurar colección','Cerrá Rekordbox y sus agentes. Se desharán los cambios posteriores al respaldo elegido. Antes se guardará automáticamente el estado actual.','Crear respaldo y revisar'))return;
          button.disabled=true;
          try {const preview=await api.post(item.transaction?'/api/transactions/restore/prepare':'/api/native/restore/prepare',{operation_id:item.id});
            if(!window.__TAURI__)throw new Error('La restauración requiere la aplicación Windows.');
            const result=await window.__TAURI__.core.invoke('approve_native_operation',{token:preview.token});
            if(result.state==='cancelled')api.notice('Restauración cancelada. No se modificaron la colección ni sus archivos.');
            if(result.state==='applied'||result.state==='restored') {
              api.notice(result.collection_reload_warning || 'Colección y archivos recuperados. Ya podés abrir Rekordbox.',result.collection_reload_warning?'error':'success');await loadBackups();await api.refreshStatus();
            }
          }catch(error){api.notice(error.message,'error');}finally{button.disabled=false;}
        };card.append(button);root.append(card);
      }
    }catch(error){root.append(text('p',error.message));}
  }
  $('native-backups-refresh').addEventListener('click',loadBackups);
  async function recoverTransactions(){
    const button=$('transactions-recover');button.disabled=true;button.textContent='Respaldando y verificando…';
    try {if(!window.__TAURI__)throw new Error('La recuperación requiere la aplicación Windows.');
      const preview=await api.post('/api/transactions/prepare',{});
      const result=await window.__TAURI__.core.invoke('approve_native_operation',{token:preview.token});
      if(result.state==='cancelled')api.notice('Recuperación cancelada. El respaldo se conserva y la colección no cambió.');
      if(result.state==='applied'){api.notice('Transacciones recuperadas y respaldadas. Podés revisar la eliminación de duplicados.','success');await api.refreshStatus();await loadBackups();}
    }catch(error){api.notice(error.message,'error');}finally{button.disabled=false;button.textContent='Respaldar y recuperar transacciones…';}
  }
  api.recoverTransactions=recoverTransactions;$('transactions-recover').onclick=recoverTransactions;
  async function processStatus(){
    const result=await read('/api/rekordbox/processes');$('native-process-status').textContent=result.reason;
    $('rekordbox-force-close').hidden=result.state!=='open'||!api.normalCloseFailed;$('native-close-return').hidden=!(api.pendingDuplicate && result.state==='closed');
    return result;
  }
  $('native-process-refresh').onclick=async()=>{try{await processStatus();await api.refreshStatus();}catch(error){api.notice(error.message,'error');}};
  $('native-close-return').onclick=()=>{go('tab-audit');$('btn-duplicate-delete').scrollIntoView({block:'center',behavior:'smooth'});};
  async function closeRekordbox(mode='normal'){
    if(window.RekordCloseBusy)return;window.RekordCloseBusy=true;$('rekordbox-close').disabled=true;$('rekordbox-force-close').disabled=true;
    try {
      api.openSettings('native-process-status');
      const proposal=await api.post('/api/rekordbox/close/prepare',{mode});
      if(!proposal.processes.length){const state=await processStatus();$('rekordbox-close-result').textContent=state.reason;return;}
      const names=[...new Set(proposal.processes.map(p=>p.name))].join(', ');const force=mode==='force';
      const warning=force?`Se finalizarán ${proposal.processes.length} procesos verificados (${names}). Podés perder cambios sin guardar y dejar transacciones que requieran recuperación. El respaldo de la eliminación todavía NO está preparado. Continuá sólo si ya guardaste tu sesión.`:`Se solicitará el cierre normal de ${proposal.processes.length} procesos (${names}), primero Rekordbox y luego sus agentes. Terminá tu mezcla y guardá los cambios. Respondé las confirmaciones de guardado en su ventana.`;
      if(!await approve(force?'Finalizar procesos de Rekordbox':'Cerrar tu sesión de Rekordbox',warning,force?'Entiendo el riesgo · finalizar':'Solicitar cierre seguro'))return;
      $('rekordbox-close-result').textContent=force?'Finalizando procesos confirmados…':'Solicitando cierre… revisá si Rekordbox pide guardar. Esperamos hasta 15 segundos.';
      const result=await api.post('/api/rekordbox/close/apply',{token:proposal.token,confirmed:true});
      api.normalCloseFailed=mode==='normal'&&result.state==='open';$('rekordbox-close-result').textContent=result.reason;await processStatus();
      api.notice(result.reason,result.state==='closed'?'success':'info',result.state==='open'?{label:'Finalizar procesos…',run:()=>closeRekordbox('force')}:api.pendingDuplicate?{label:'Volver a eliminar duplicados',run:()=>$('native-close-return').click()}:null);
    }catch(error){$('rekordbox-close-result').textContent=error.message;api.notice(error.message,'error');}
    finally{window.RekordCloseBusy=false;$('rekordbox-force-close').disabled=false;await api.refreshStatus().catch(()=>{});}
  }
  api.closeRekordbox=closeRekordbox;
  $('rekordbox-close').onclick=()=>closeRekordbox('normal');$('rekordbox-force-close').onclick=()=>closeRekordbox('force');
  $('native-prepare').addEventListener('click',async()=>{
    if(!await approve('Respaldo obligatorio antes de escribir','Cerrá Rekordbox y sus agentes de sincronización. Crearemos automáticamente un respaldo verificado de la colección y prepararemos la playlist en una copia para que la revises.','Crear respaldo y revisar'))return;
    $('native-prepare').disabled=true;
    $('native-result').textContent='Creando el respaldo y verificando la propuesta… esperá antes de salir o actualizar Rekord AI.';
    try {const data=await api.post('/api/native/prepare',{track_ids:api.selection,name:$('plan-out-name').value,source_revision:revision});
      $('native-result').textContent=`Propuesta: ${data.playlist_name} · ${data.tracks} pistas · integridad ${data.integrity}\nRespaldo: ${data.backup_directory}`;
      if(!window.__TAURI__)throw new Error('La escritura requiere la aplicación Windows.');
      const result=await window.__TAURI__.core.invoke('approve_native_operation',{token:data.token,sourceRevision:revision});
      if(result.state==='applied'||result.state==='restored') {
        api.notice('Playlist creada con respaldo. Ya podés abrir Rekordbox.','success');$('native-result').textContent+='\nPlaylist aplicada. Respaldo disponible abajo.';
      }
      await loadBackups();
    } catch(error) {$('native-result').textContent=error.message;}
    finally {await api.refreshStatus().catch(()=>{});}
  });
});
