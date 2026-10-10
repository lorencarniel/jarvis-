const API = 'http://localhost:8080/api/browser';
let mediaInfo = {};

// Enviar logs al servidor para diagnostico
async function logToServer(msg, data) {
  try {
    await fetch(`${API}/log`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ msg, data })
    });
  } catch(e) {}
}

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

    } else if (cmd.action === 'whatsapp_send') {
      await handleWhatsAppSend(cmd.phone, cmd.message);

    } else if (cmd.action === 'whatsapp_read') {
      await handleWhatsAppRead(cmd.count || 5);

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

// WhatsApp read messages handler
async function handleWhatsAppRead(count) {
  await logToServer('whatsapp_read_start', { count });

  const tabs = await chrome.tabs.query({});
  let waTab = tabs.find(t => t.url && t.url.includes('web.whatsapp.com'));

  if (!waTab) {
    waTab = await chrome.tabs.create({ url: 'https://web.whatsapp.com' });
    await new Promise(r => setTimeout(r, 10000));
  } else {
    await chrome.tabs.update(waTab.id, { active: true });
    await chrome.windows.update(waTab.windowId, { focused: true });
  }

  const tabId = waTab.id;

  const readMessages = async (attempt) => {
    if (attempt > 10) {
      await logToServer('whatsapp_read_timeout', {});
      return;
    }

    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId },
        func: (maxCount) => {
          const messages = [];

          // Find unread chat indicators
          const unreadBadges = document.querySelectorAll('[data-testid="icon-unread-count"], span[aria-label*="no le"]');

          // Read messages from the currently open chat
          const msgContainers = document.querySelectorAll('[data-testid="msg-container"]');
          const recent = [...msgContainers].slice(-maxCount);

          for (const container of recent) {
            const incoming = container.querySelector('[data-testid="msg-text"]') || container.querySelector('.message-in .copyable-text');
            if (!incoming) continue;

            const textEl = container.querySelector('[data-testid="msg-text"] span, .selectable-text span');
            const text = textEl ? textEl.textContent : '';
            if (!text) continue;

            const metaEl = container.querySelector('[data-testid="msg-meta"]') || container.querySelector('.message-time');
            const time = metaEl ? metaEl.textContent : '';

            const isIncoming = !!container.querySelector('.message-in');
            const prefix = isIncoming ? 'Recibido' : 'Enviado';

            messages.push(`[${time}] ${prefix}: ${text}`);
          }

          // Get chat name
          const chatHeader = document.querySelector('header [data-testid="conversation-info-header-chat-title"] span, header span[dir="auto"][title]');
          const chatName = chatHeader ? (chatHeader.getAttribute('title') || chatHeader.textContent) : 'Chat actual';

          // Get list of chats with unread messages
          const unreadChats = [];
          const chatListItems = document.querySelectorAll('[data-testid="cell-frame-container"]');
          for (const item of chatListItems) {
            const badge = item.querySelector('[data-testid="icon-unread-count"]');
            if (!badge) continue;
            const nameEl = item.querySelector('span[dir="auto"][title]') || item.querySelector('span[dir="auto"]');
            const name = nameEl ? (nameEl.getAttribute('title') || nameEl.textContent) : '?';
            const countText = badge.textContent || '1';
            unreadChats.push(`${name} (${countText} nuevos)`);
          }

          return { messages, chatName, unreadChats };
        },
        args: [count]
      });

      const data = results?.[0]?.result;
      await logToServer('whatsapp_read_result', { chatName: data?.chatName, msgCount: data?.messages?.length, unreadChats: data?.unreadChats?.length });

      if (data) {
        const allMessages = [];
        if (data.unreadChats && data.unreadChats.length > 0) {
          allMessages.push('Chats con mensajes sin leer: ' + data.unreadChats.join(', '));
        }
        if (data.messages && data.messages.length > 0) {
          allMessages.push(`Chat abierto (${data.chatName}):`);
          allMessages.push(...data.messages);
        }

        if (allMessages.length > 0) {
          try {
            await fetch('http://localhost:8080/api/browser/whatsapp-messages', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ messages: allMessages })
            });
          } catch(e) {}
        }
      }
    } catch(e) {
      await logToServer('whatsapp_read_error', { attempt, error: e.message });
      setTimeout(() => readMessages(attempt + 1), 2000);
    }
  };

  setTimeout(() => readMessages(0), 3000);
}

// WhatsApp send message handler
async function handleWhatsAppSend(phone, message) {
  const cleanPhone = phone.replace(/[\s\-\(\)]/g, '');
  const encodedMsg = encodeURIComponent(message);
  const waUrl = `https://web.whatsapp.com/send?phone=${cleanPhone}&text=${encodedMsg}`;

  await logToServer('whatsapp_send_start', { phone: cleanPhone, messageLen: message.length });

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
  const initialWait = needsFullLoad ? 12000 : 8000;
  let attempts = 0;

  const findAndClickSend = async () => {
    attempts++;
    if (attempts > 25) {
      await logToServer('whatsapp_send_timeout', { attempts });
      return;
    }

    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId },
        func: () => {
          // Check if message box has content and send button is available
          const sendBtn = document.querySelector('[data-testid="send"], [aria-label="Enviar"], [aria-label="Send"]');
          if (sendBtn) {
            sendBtn.click();
            return { ok: true, method: 'send-button' };
          }

          // Try finding send button by data-icon
          const sendIcon = document.querySelector('[data-icon="send"]');
          if (sendIcon) {
            const btn = sendIcon.closest('button') || sendIcon.closest('[role="button"]') || sendIcon.parentElement;
            if (btn) { btn.click(); return { ok: true, method: 'send-icon' }; }
          }

          // Check if the compose box has text (means page loaded the message)
          const composeBox = document.querySelector('[data-testid="conversation-compose-box-input"], div[contenteditable="true"][data-tab="10"]');
          if (composeBox && composeBox.textContent && composeBox.textContent.trim().length > 0) {
            // Text is there but no send button found yet
            return { ok: false, hasText: true, textLen: composeBox.textContent.length };
          }

          return { ok: false, hasText: false };
        }
      });

      const r = results?.[0]?.result;
      await logToServer('whatsapp_send_click', { attempt: attempts, result: r });

      if (r?.ok) {
        await logToServer('whatsapp_send_success', { attempts });
      } else {
        setTimeout(findAndClickSend, 2000);
      }
    } catch(e) {
      await logToServer('whatsapp_send_error', { attempt: attempts, error: e.message });
      setTimeout(findAndClickSend, 3000);
    }
  };

  setTimeout(findAndClickSend, initialWait);
}

// WhatsApp call handler
async function handleWhatsAppCall(phone, callType) {
  const cleanPhone = phone.replace(/[\s\-\(\)]/g, '');
  const waUrl = `https://web.whatsapp.com/send?phone=${cleanPhone}`;

  await logToServer('whatsapp_call_start', { phone: cleanPhone, callType, url: waUrl });

  const tabs = await chrome.tabs.query({});
  let waTab = tabs.find(t => t.url && t.url.includes('web.whatsapp.com'));
  let needsFullLoad = false;

  if (waTab) {
    await logToServer('whatsapp_tab_found', { tabId: waTab.id, url: waTab.url });
    await chrome.tabs.update(waTab.id, { active: true });
    await chrome.windows.update(waTab.windowId, { focused: true });
    await chrome.scripting.executeScript({
      target: { tabId: waTab.id },
      func: (url) => { window.location.href = url; },
      args: [waUrl]
    });
  } else {
    await logToServer('whatsapp_new_tab', {});
    waTab = await chrome.tabs.create({ url: waUrl });
    needsFullLoad = true;
  }

  const tabId = waTab.id;
  const initialWait = needsFullLoad ? 10000 : 6000;
  let attempts = 0;

  const findAndClickCallButton = async () => {
    attempts++;
    if (attempts > 20) {
      await logToServer('whatsapp_timeout', { attempts });
      return;
    }

    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId },
        func: () => {
          // Recoger TODO el diagnostico posible
          const allDataIcons = [...document.querySelectorAll('[data-icon]')].map(el => ({
            icon: el.getAttribute('data-icon'),
            tag: el.tagName,
            parentTag: el.parentElement?.tagName,
            inHeader: !!el.closest('header'),
            inFooter: !!el.closest('footer'),
            ariaLabel: el.closest('button')?.getAttribute('aria-label') || el.closest('[role="button"]')?.getAttribute('aria-label') || ''
          }));

          // Info de headers
          const headers = document.querySelectorAll('header');
          const headerInfo = [...headers].map((h, i) => ({
            idx: i,
            childButtons: h.querySelectorAll('button, [role="button"]').length,
            dataIcons: [...h.querySelectorAll('[data-icon]')].map(e => e.getAttribute('data-icon')),
            ariaLabels: [...h.querySelectorAll('[aria-label]')].map(e => ({
              label: e.getAttribute('aria-label'),
              tag: e.tagName,
              icon: e.querySelector('[data-icon]')?.getAttribute('data-icon') || null
            }))
          }));

          // Buscar testids relevantes
          const testIds = [...document.querySelectorAll('[data-testid]')]
            .map(e => e.getAttribute('data-testid'))
            .filter(t => t.includes('call') || t.includes('phone') || t.includes('audio') || t.includes('header'));

          return {
            allIcons: allDataIcons,
            headers: headerInfo,
            testIds,
            title: document.title,
            url: window.location.href
          };
        }
      });

      const diag = results?.[0]?.result;
      await logToServer('whatsapp_diag', {
        attempt: attempts,
        title: diag?.title,
        url: diag?.url,
        headerCount: diag?.headers?.length,
        headers: diag?.headers,
        testIds: diag?.testIds,
        iconCount: diag?.allIcons?.length,
        headerIcons: diag?.allIcons?.filter(i => i.inHeader),
        callRelated: diag?.allIcons?.filter(i =>
          i.icon?.includes('call') || i.icon?.includes('phone') ||
          i.icon?.includes('audio') || i.icon?.includes('video') ||
          i.ariaLabel?.toLowerCase().includes('call') || i.ariaLabel?.toLowerCase().includes('llamad')
        )
      });

      // Ahora intentar clickear
      const clickResult = await chrome.scripting.executeScript({
        target: { tabId },
        func: (callType) => {
          const isVideo = callType === 'video';

          // 1) Buscar en headers por data-icon
          const headers = document.querySelectorAll('header');
          for (const header of headers) {
            const icons = header.querySelectorAll('[data-icon]');
            for (const icon of icons) {
              const name = icon.getAttribute('data-icon');
              if (isVideo && (name === 'video-call' || name === 'videocam')) {
                const btn = icon.closest('button') || icon.closest('[role="button"]') || icon.parentElement;
                if (btn) { btn.click(); return { ok: true, method: 'header-data-icon', icon: name }; }
              }
              if (!isVideo && (name === 'audio-call' || name === 'call' || name === 'phone')) {
                const btn = icon.closest('button') || icon.closest('[role="button"]') || icon.parentElement;
                if (btn) { btn.click(); return { ok: true, method: 'header-data-icon', icon: name }; }
              }
            }
          }

          // 2) Buscar en headers por aria-label
          for (const header of headers) {
            const btns = header.querySelectorAll('button, [role="button"], span[title]');
            for (const btn of btns) {
              const label = (btn.getAttribute('aria-label') || btn.getAttribute('title') || '').toLowerCase().trim();
              if (isVideo && (label === 'videollamada' || label === 'video call' || (label.includes('video') && label.includes('llamada')))) {
                btn.click();
                return { ok: true, method: 'header-aria', label };
              }
              if (!isVideo && (label === 'llamada' || label === 'llamar' || label === 'call' || label === 'voice call' || label === 'audio call' || label.includes('llamada de voz'))) {
                btn.click();
                return { ok: true, method: 'header-aria', label };
              }
            }
          }

          // 3) Buscar globalmente (excluyendo footer/compose)
          const allIcons = document.querySelectorAll('[data-icon]');
          for (const icon of allIcons) {
            if (icon.closest('footer')) continue;
            if (icon.closest('[data-testid="conversation-compose-box"]')) continue;
            if (icon.closest('[data-testid="msg-container"]')) continue;
            const name = icon.getAttribute('data-icon');
            if (!isVideo && (name === 'audio-call' || name === 'call' || name === 'phone')) {
              const btn = icon.closest('button') || icon.closest('[role="button"]') || icon.parentElement;
              if (btn) { btn.click(); return { ok: true, method: 'global-data-icon', icon: name }; }
            }
            if (isVideo && (name === 'video-call' || name === 'videocam')) {
              const btn = icon.closest('button') || icon.closest('[role="button"]') || icon.parentElement;
              if (btn) { btn.click(); return { ok: true, method: 'global-data-icon', icon: name }; }
            }
          }

          return { ok: false };
        },
        args: [callType]
      });

      const r = clickResult?.[0]?.result;
      await logToServer('whatsapp_click', { attempt: attempts, result: r });

      if (r?.ok) {
        setTimeout(() => confirmCall(tabId, callType, 0), 2000);
      } else {
        setTimeout(findAndClickCallButton, 2000);
      }
    } catch(e) {
      await logToServer('whatsapp_error', { attempt: attempts, error: e.message });
      setTimeout(findAndClickCallButton, 3000);
    }
  };

  const confirmCall = async (tabId, callType, n) => {
    if (n > 10) {
      await logToServer('whatsapp_confirm_timeout', { n });
      return;
    }
    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId },
        func: () => {
          if (document.querySelector('[data-icon="end-call"], [data-testid="end-call"]')) {
            return { confirmed: true, reason: 'call-active' };
          }
          const dialogs = document.querySelectorAll('[role="dialog"], [data-animate-modal-popup="true"]');
          for (const d of dialogs) {
            const btns = d.querySelectorAll('button, [role="button"]');
            for (const btn of btns) {
              const text = (btn.textContent || '').toLowerCase().trim();
              const icon = btn.querySelector('[data-icon]');
              const iconName = icon ? icon.getAttribute('data-icon') : '';
              if (['audio-call', 'video-call', 'call', 'phone'].includes(iconName) ||
                  text.includes('llamar') || text === 'call' || text.includes('voice call')) {
                btn.click();
                return { confirmed: true, reason: 'dialog-btn', text };
              }
            }
          }
          const allDialogInfo = [...document.querySelectorAll('[role="dialog"]')].map(d => ({
            text: d.textContent?.substring(0, 200),
            buttons: [...d.querySelectorAll('button')].map(b => b.textContent?.trim())
          }));
          return { confirmed: false, dialogs: allDialogInfo };
        }
      });
      const r = results?.[0]?.result;
      await logToServer('whatsapp_confirm', { n, result: r });
      if (!r?.confirmed) {
        setTimeout(() => confirmCall(tabId, callType, n + 1), 1500);
      }
    } catch(e) {
      await logToServer('whatsapp_confirm_error', { n, error: e.message });
    }
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
