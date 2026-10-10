const API = 'http://localhost:8080/api/browser';
let mediaInfo = {};

// Recibir info de media de los content scripts
chrome.runtime.onMessage.addListener((msg, sender) => {
  if (msg.type === 'media_update' && sender.tab) {
    mediaInfo[sender.tab.id] = {
      ...msg.data,
      tabId: sender.tab.id,
      url: sender.tab.url,
      tabTitle: sender.tab.title
    };
  }
});

chrome.tabs.onRemoved.addListener((tabId) => {
  delete mediaInfo[tabId];
});

// Sitios de media conocidos
const MEDIA_SITES = ['youtube.com', 'music.youtube.com', 'open.spotify.com', 'twitch.tv', 'netflix.com'];

function isMediaUrl(url) {
  return url && MEDIA_SITES.some(s => url.includes(s));
}

// Reportar estado al servidor
async function reportState() {
  try {
    const tabs = await chrome.tabs.query({});
    const tabList = tabs.map(t => ({
      id: t.id, url: t.url, title: t.title, active: t.active, audible: t.audible
    }));
    const allMedia = Object.values(mediaInfo);
    const activeMedia = allMedia.filter(m => m.playing);
    await fetch(`${API}/state`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tabs: tabList, media: allMedia, activeMedia })
    });
  } catch (e) {}
}

// Pedir comandos al servidor
async function pollCommands() {
  try {
    const res = await fetch(`${API}/commands`);
    const data = await res.json();
    if (data.commands && data.commands.length > 0) {
      for (const cmd of data.commands) {
        await executeCommand(cmd);
      }
    }
  } catch (e) {}
}

// Encontrar pestañas de media
async function findMediaTab() {
  const all = await chrome.tabs.query({});
  const audible = all.filter(t => t.audible && isMediaUrl(t.url));
  if (audible.length > 0) return audible;
  return all.filter(t => isMediaUrl(t.url));
}

// Ejecutar un comando
async function executeCommand(cmd) {
  try {
    if (cmd.action === 'open_or_switch') {
      const tabs = await chrome.tabs.query({});
      let existing = null;
      if (cmd.urlPattern) {
        existing = tabs.find(t => t.url && t.url.includes(cmd.urlPattern));
      }
      if (!existing && cmd.url) {
        try {
          const domain = new URL(cmd.url).hostname.replace('www.', '');
          existing = tabs.find(t => {
            if (!t.url) return false;
            try { return new URL(t.url).hostname.replace('www.', '') === domain; } catch(e) { return false; }
          });
        } catch(e) {}
      }
      if (existing) {
        await chrome.tabs.update(existing.id, { active: true });
        await chrome.windows.update(existing.windowId, { focused: true });
        if (cmd.url && cmd.url !== existing.url) {
          await chrome.scripting.executeScript({
            target: { tabId: existing.id },
            func: (url) => { window.location.href = url; },
            args: [cmd.url]
          });
        }
      } else if (cmd.url) {
        await chrome.tabs.create({ url: cmd.url });
      }

    } else if (cmd.action === 'navigate_tab') {
      const tabs = await chrome.tabs.query({});
      const existing = tabs.find(t => t.url && t.url.includes(cmd.urlPattern));
      if (existing) {
        await chrome.tabs.update(existing.id, { active: true, url: cmd.url });
        await chrome.windows.update(existing.windowId, { focused: true });
      } else {
        await chrome.tabs.create({ url: cmd.url });
      }

    } else if (cmd.action === 'switch_tab') {
      const tabs = await chrome.tabs.query({});
      const target = tabs.find(t => t.url && t.url.includes(cmd.urlPattern));
      if (target) {
        await chrome.tabs.update(target.id, { active: true });
        await chrome.windows.update(target.windowId, { focused: true });
      }

    } else if (cmd.action === 'media_control') {
      await handleMediaControl(cmd.command, cmd.tabId);

    } else if (cmd.action === 'whatsapp_call') {
      await handleWhatsAppCall(cmd.phone, cmd.callType || 'audio');

    } else if (cmd.action === 'close_tab') {
      const tabs = await chrome.tabs.query({});
      const target = tabs.find(t => t.url && t.url.includes(cmd.urlPattern));
      if (target) chrome.tabs.remove(target.id);
    }
  } catch (e) {
    console.error('[JARVIS] Command error:', e);
  }
}

// Control de media
async function handleMediaControl(command, specificTabId) {
  const targets = [];
  if (specificTabId) targets.push(specificTabId);

  const infoEntries = Object.values(mediaInfo);
  const fromInfo = infoEntries.find(m => m.playing) || infoEntries[0];
  if (fromInfo && !targets.includes(fromInfo.tabId)) targets.push(fromInfo.tabId);

  const mediaTabs = await findMediaTab();
  for (const t of mediaTabs) {
    if (!targets.includes(t.id)) targets.push(t.id);
  }

  if (targets.length === 0) {
    console.log('[JARVIS] No hay tabs de media');
    return;
  }

  for (const tabId of targets) {
    try {
      const tab = await chrome.tabs.get(tabId);
      await chrome.tabs.update(tabId, { active: true });
      await chrome.windows.update(tab.windowId, { focused: true });
      await new Promise(r => setTimeout(r, 300));

      const results = await chrome.scripting.executeScript({
        target: { tabId },
        func: (cmd) => {
          const v = document.querySelector('video');
          if (!v) return 'no-video';
          if (cmd === 'toggle') {
            const ytBtn = document.querySelector('.ytp-play-button');
            if (ytBtn) { ytBtn.click(); return v.paused ? 'now-playing' : 'now-paused'; }
            if (v.paused) v.play(); else v.pause();
          } else if (cmd === 'play') {
            const ytBtn = document.querySelector('.ytp-play-button');
            if (v.paused && ytBtn) { ytBtn.click(); return 'now-playing'; }
            if (v.paused) v.play();
          } else if (cmd === 'pause') {
            const ytBtn = document.querySelector('.ytp-play-button');
            if (!v.paused && ytBtn) { ytBtn.click(); return 'now-paused'; }
            if (!v.paused) v.pause();
          }
          return v.paused ? 'paused' : 'playing';
        },
        args: [command]
      });
      console.log('[JARVIS] executeScript resultado:', results?.[0]?.result, 'en tab', tabId);
      if (results?.[0]?.result && results[0].result !== 'no-video') return;
    } catch(e) {
      console.log('[JARVIS] executeScript fallo en tab', tabId, ':', e.message);
      try {
        await chrome.tabs.sendMessage(tabId, { type: 'media_command', command });
        return;
      } catch(e2) {}
    }
  }
}

// WhatsApp call handler
async function handleWhatsAppCall(phone, callType) {
  const cleanPhone = phone.replace(/[\s\-\(\)]/g, '');
  const waUrl = `https://web.whatsapp.com/send?phone=${cleanPhone}`;

  const tabs = await chrome.tabs.query({});
  let waTab = tabs.find(t => t.url && t.url.includes('web.whatsapp.com'));
  let needsFullLoad = false;

  if (waTab) {
    await chrome.tabs.update(waTab.id, { active: true });
    await chrome.windows.update(waTab.windowId, { focused: true });
    await chrome.scripting.executeScript({
      target: { tabId: waTab.id },
      func: (url) => { window.location.href = url; },
      args: [waUrl]
    });
  } else {
    waTab = await chrome.tabs.create({ url: waUrl });
    needsFullLoad = true;
  }

  const tabId = waTab.id;
  const initialWait = needsFullLoad ? 8000 : 5000;
  let attempts = 0;

  const findAndClickCallButton = async () => {
    attempts++;
    if (attempts > 30) {
      console.log('[JARVIS] WhatsApp call: timeout');
      return;
    }

    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId },
        func: (callType) => {
          // DIAGNOSTICO: logear todos los data-icon de la pagina
          const allDataIcons = [...document.querySelectorAll('[data-icon]')].map(el => el.getAttribute('data-icon'));
          console.log('[JARVIS-DIAG] data-icons en pagina:', JSON.stringify(allDataIcons));

          // Nombres de icono que WhatsApp usa para llamadas
          const callIconNames = callType === 'video'
            ? ['video-call', 'videocam']
            : ['audio-call', 'call', 'phone'];

          // EXCLUIR estos: son botones de nota de voz / grabar audio (NO llamada)
          const excludeIcons = ['ptt', 'audio-ptt', 'microphone', 'mic', 'ptt-recording'];

          // Buscar en headers (panel superior del chat)
          const headers = document.querySelectorAll('header, [data-testid="conversation-header"], [data-testid="chat-header"]');
          for (const header of headers) {
            for (const iconName of callIconNames) {
              const icon = header.querySelector(`[data-icon="${iconName}"]`);
              if (icon) {
                const btn = icon.closest('button') || icon.closest('[role="button"]') || icon.parentElement;
                if (btn) {
                  btn.click();
                  return { ok: true, method: 'header-icon', icon: iconName };
                }
              }
            }
            // Buscar por data-testid
            for (const iconName of callIconNames) {
              const el = header.querySelector(`[data-testid="${iconName}"]`);
              if (el) {
                (el.closest('button') || el).click();
                return { ok: true, method: 'header-testid', icon: iconName };
              }
            }
          }

          // Buscar globalmente pero EXCLUIR footer/compose/mensajes
          for (const iconName of callIconNames) {
            const icons = document.querySelectorAll(`[data-icon="${iconName}"]`);
            for (const icon of icons) {
              if (icon.closest('footer')) continue;
              if (icon.closest('[data-testid="conversation-compose-box"]')) continue;
              if (icon.closest('[data-testid="msg-container"]')) continue;
              if (icon.closest('[data-testid="chat-input"]')) continue;
              const btn = icon.closest('button') || icon.closest('[role="button"]') || icon.parentElement;
              if (btn) {
                btn.click();
                return { ok: true, method: 'global-filtered', icon: iconName };
              }
            }
          }

          // Buscar por aria-label SOLO con texto muy especifico de llamada
          const allBtns = document.querySelectorAll('header button, header [role="button"]');
          for (const btn of allBtns) {
            const label = ((btn.getAttribute('aria-label') || '') + ' ' + (btn.getAttribute('title') || '')).toLowerCase();
            if (callType === 'video' && label.includes('video') && (label.includes('call') || label.includes('llamada'))) {
              btn.click();
              return { ok: true, method: 'aria-label', label };
            }
            if (callType !== 'video' && (label.includes('llamada de voz') || label.includes('voice call') || label === 'llamar' || label === 'call')) {
              btn.click();
              return { ok: true, method: 'aria-label', label };
            }
          }

          return { ok: false, icons: allDataIcons.filter(i => i.includes('call') || i.includes('audio') || i.includes('phone') || i.includes('ptt')) };
        },
        args: [callType]
      });

      const r = results?.[0]?.result;
      console.log('[JARVIS] WhatsApp call attempt', attempts, ':', JSON.stringify(r));

      if (r?.ok) {
        setTimeout(() => confirmCall(tabId, callType, 0), 2000);
      } else {
        setTimeout(findAndClickCallButton, 2000);
      }
    } catch(e) {
      console.log('[JARVIS] WhatsApp call error:', e.message);
      setTimeout(findAndClickCallButton, 3000);
    }
  };

  const confirmCall = async (tabId, callType, n) => {
    if (n > 10) return;
    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId },
        func: () => {
          // Ya empezo la llamada?
          if (document.querySelector('[data-icon="end-call"], [data-testid="end-call"]')) {
            return { confirmed: true, reason: 'call-active' };
          }
          // Buscar dialogo de confirmacion
          const dialogs = document.querySelectorAll('[role="dialog"]');
          for (const d of dialogs) {
            const btns = d.querySelectorAll('button, [role="button"]');
            for (const btn of btns) {
              const text = (btn.textContent || '').toLowerCase().trim();
              const icon = btn.querySelector('[data-icon]');
              const iconName = icon ? icon.getAttribute('data-icon') : '';
              if (['audio-call', 'video-call', 'call', 'phone'].includes(iconName) ||
                  text.includes('llamar') || text === 'call' || text.includes('voice call')) {
                btn.click();
                return { confirmed: true, reason: 'dialog-btn' };
              }
            }
          }
          return { confirmed: false };
        }
      });
      const r = results?.[0]?.result;
      console.log('[JARVIS] WhatsApp confirm', n, ':', JSON.stringify(r));
      if (!r?.confirmed) {
        setTimeout(() => confirmCall(tabId, callType, n + 1), 1500);
      }
    } catch(e) {}
  };

  setTimeout(findAndClickCallButton, initialWait);
}

// --- Polling ---
setInterval(reportState, 3000);
setInterval(pollCommands, 2000);
reportState();
pollCommands();

chrome.alarms.create('jarvis_poll', { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener(() => {
  reportState();
  pollCommands();
});
