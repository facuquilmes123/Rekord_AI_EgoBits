document.addEventListener('DOMContentLoaded',()=>{
  const buttons=[...document.querySelectorAll('[data-settings]')];
  function select(key,focus=false){
    for(const button of buttons){const active=button.dataset.settings===key;button.setAttribute('aria-selected',String(active));button.tabIndex=active?0:-1;document.getElementById(button.getAttribute('aria-controls')).hidden=!active;if(active&&focus)button.focus();}
  }
  for(const [index,button] of buttons.entries()){
    button.onclick=()=>select(button.dataset.settings);
    button.onkeydown=event=>{let next;if(event.key==='ArrowRight')next=(index+1)%buttons.length;else if(event.key==='ArrowLeft')next=(index+buttons.length-1)%buttons.length;else if(event.key==='Home')next=0;else if(event.key==='End')next=buttons.length-1;else return;event.preventDefault();select(buttons[next].dataset.settings,true);};
  }
  window.RekordAI.openSettings=target=>{
    document.querySelector('[data-tab="tab-config"]').click();const node=document.getElementById(target);const pane=node?.closest('.settings-pane');
    if(pane)select(pane.id.replace('settings-',''));node?.scrollIntoView({block:'center',behavior:'smooth'});
  };
});
