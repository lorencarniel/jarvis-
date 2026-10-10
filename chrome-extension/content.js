let lastState = '';

function getMediaInfo() {
  const video = document.querySelector('video');
  if (!video) return null;

  const host = location.hostname;
  let title = '', artist = '', thumbnail = '';

  if (host.includes('youtube.com')) {
    const titleEl = document.querySelector('h1.ytd-watch-metadata yt-formatted-string, h1.title');
    title = titleEl?.textContent?.trim() || document.title.replace(' - YouTube', '').trim();
    const channelEl = document.querySelector('#owner #channel-name a, .ytd-channel-name a');
    artist = channelEl?.textContent?.trim() || '';
    const thumbEl = document.querySelector('link[rel="image_src"]');
    thumbnail = thumbEl?.href || '';
  } else if (host.includes('spotify.com')) {
    const titleEl = document.querySelector('[data-testid="context-item-info-title"], [data-testid="nowplaying-track-link"]');
    title = titleEl?.textContent?.trim() || document.title.replace(' | Spotify', '').trim();
    const artistEl = document.querySelector('[data-testid="context-item-info-artist"], [data-testid="context-item-info-show"]');
    artist = artistEl?.textContent?.trim() || '';
  }

  return {
    title,
    artist,
    playing: !video.paused,
    currentTime: Math.round(video.currentTime),
    duration: Math.round(video.duration) || 0,
    site: host.includes('youtube') ? 'YouTube' : host.includes('spotify') ? 'Spotify' : host,
    url: location.href,
    thumbnail
  };
}

function reportMedia() {
  const info = getMediaInfo();
  if (!info) return;
  try {
    chrome.runtime.sendMessage({ type: 'media_update', data: info });
  } catch(e) {}
}

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === 'media_command') {
    const video = document.querySelector('video');
    if (!video) return;
    const command = msg.command;
    const shouldPlay = command === 'play' || (command === 'toggle' && video.paused);
    const shouldPause = command === 'pause' || (command === 'toggle' && !video.paused);

    if (shouldPlay) {
      video.play().catch(() => {
        // Si play() falla por autoplay policy, intentar click en botón de YouTube
        const ytBtn = document.querySelector('.ytp-play-button');
        if (ytBtn) ytBtn.click();
      });
    } else if (shouldPause) {
      video.pause();
    } else if (command === 'mute') video.muted = true;
    else if (command === 'unmute') video.muted = false;
  }
});

setInterval(reportMedia, 1500);
reportMedia();
