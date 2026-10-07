/* Native file transfer; never turn a browser URL into an arbitrary file path. */
(async()=>{
  const source=document.getElementById('source'), root=document.getElementById('suggestions'), help=document.getElementById('drag-help');
  let sequence='', busy=false;
  if (!window.__TAURI__) { source.textContent='El arrastre al deck requiere la aplicación Windows.';return; }
  const {port,token}=await window.__TAURI__.core.invoke('backend_info');
  function render(data) {
    if(!data.display){root.replaceChildren();sequence='';source.textContent=data.reason||'Esperando pista de referencia';return;}
    source.textContent=data.source==='verified_telemetry'?'Pista audible confirmada':data.source==='audio_pilot'?'Coincidencia de audio · revisar referencia':'Referencia del historial · puede tener demora; master sin confirmar';
    if(data.source==='rekordbox_history' && data.reference_track)source.textContent=`Referencia: ${data.reference_track.artist} — ${data.reference_track.title} · última registrada, no escucha del master`;
    const signature=JSON.stringify([data.source_revision,data.recommendations]);
    if(signature===sequence)return;
    sequence=signature;root.replaceChildren();
    for(const track of data.recommendations||[]) {
      const card=document.createElement('button');card.type='button';card.className='live-track';
      const title=document.createElement('strong');title.textContent=`${track.artist} — ${track.title}`;
      const meta=document.createElement('span');meta.textContent=`${track.bpm??'—'} BPM · ${track.key||'Sin tonalidad'} · ${track.genre||'Sin género'}`;
      const why=document.createElement('span');why.textContent=(track.compatibility_score!=null?`Compatibilidad ${track.compatibility_score}/100 · `:'')+(track.match_reasons||[]).join(' · ');card.append(title,meta,why);card.setAttribute('aria-label',`${title.textContent}. Arrastrar al deck de Rekordbox.`);
      let origin=null, dragging=false;
      card.addEventListener('pointerdown',event=>{if(event.button===0){origin=[event.clientX,event.clientY];dragging=false;}});
      card.addEventListener('pointerup',()=>{origin=null;});
      card.addEventListener('pointerleave',event=>{if(!(event.buttons&1))origin=null;});
      card.addEventListener('pointermove',async event=>{
        if(!origin || !(event.buttons&1) || dragging || Math.hypot(event.clientX-origin[0],event.clientY-origin[1])<5)return;
        dragging=true;origin=null;
        try { await window.__TAURI__.core.invoke('drag_collection_track',{trackId:track.id,sourceRevision:data.source_revision}); }
        catch(error){help.textContent=String(error);}
      });
      card.addEventListener('click',()=>{help.textContent=`Seleccionada: ${title.textContent}. Mantené el botón del mouse y arrastrá al deck.`;});
      root.append(card);
    }
  }
  await window.__TAURI__.event.listen('recommendation-update',event=>render(event.payload));
  await window.__TAURI__.event.listen('track-drag-error',event=>{help.textContent=event.payload;});
  await window.__TAURI__.event.listen('track-drag-result',event=>{help.textContent=event.payload.accepted?'El destino aceptó el archivo. Verificá que la pista se haya cargado en el deck.':'Arrastre cancelado o archivo no aceptado por el destino.';});
  document.getElementById('dismiss').onclick=()=>window.__TAURI__.core.invoke('hide_recommendation_popup');
  async function refresh(){if(busy)return;busy=true;try{
    const response=await fetch(`http://127.0.0.1:${port}/api/recommendation-popup`,{headers:{'X-EgoBits-Token':token}});
    if(response.ok){const data=await response.json();if(data.display)render(data);else {root.replaceChildren();sequence='';source.textContent=data.reason||'Esperando pista de referencia';}}
  }catch{source.textContent='Servicio local no disponible';root.replaceChildren();sequence='';}finally{busy=false;}}
  await refresh();
})();
