// Universal Media Downloader Pro - app.js (v2.0.0)

document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const urlInput = document.getElementById('urlInput');
  const pasteClipboardBtn = document.getElementById('pasteClipboardBtn');
  const analyzeBtn = document.getElementById('analyzeBtn');
  const alertBanner = document.getElementById('alertBanner');
  
  const mediaSection = document.getElementById('mediaSection');
  const videoThumbnail = document.getElementById('videoThumbnail');
  const videoTitle = document.getElementById('videoTitle');
  const videoUploader = document.getElementById('videoUploader');
  const videoDuration = document.getElementById('videoDuration');
  const videoViews = document.getElementById('videoViews');
  const platformPill = document.getElementById('platformPill');

  const tabVideo = document.getElementById('tabVideo');
  const tabAudio = document.getElementById('tabAudio');
  const tabImage = document.getElementById('tabImage');
  const typeBtns = document.querySelectorAll('.type-btn');

  const videoGrid = document.getElementById('videoGrid');
  const audioGrid = document.getElementById('audioGrid');
  const imageGrid = document.getElementById('imageGrid');
  const qualityItems = document.querySelectorAll('.quality-item');

  const startDownloadBtn = document.getElementById('startDownloadBtn');
  const downloadBtnLabel = document.getElementById('downloadBtnLabel');
  const progressBox = document.getElementById('progressBox');
  const progressStatus = document.getElementById('progressStatus');
  const progressPercent = document.getElementById('progressPercent');
  const progressBarFill = document.getElementById('progressBarFill');
  const progressSpeed = document.getElementById('progressSpeed');
  const progressEta = document.getElementById('progressEta');
  
  const successCard = document.getElementById('successCard');
  const saveFileBtn = document.getElementById('saveFileBtn');
  const openSuccessFolderBtn = document.getElementById('openSuccessFolderBtn');
  const openFolderBtn = document.getElementById('openFolderBtn');
  const historyList = document.getElementById('historyList');

  // State
  let currentVideoUrl = '';
  let currentVideoData = null;
  let activeFormatType = 'video'; // 'video' | 'audio' | 'image'
  let activeQuality = '1080';
  let activePollInterval = null;
  let lastCompletedTaskId = null;

  // 1. Initial Load History
  loadHistory();

  // Event Listeners
  pasteClipboardBtn.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        urlInput.value = text.trim();
        analyzeVideo();
      }
    } catch (err) {
      showAlert('Could not read clipboard. Please paste manually.', 'error');
    }
  });

  analyzeBtn.addEventListener('click', analyzeVideo);

  urlInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') analyzeVideo();
  });

  // Type Switcher (Video vs Audio vs Photo)
  typeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      typeBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      activeFormatType = btn.dataset.type;
      
      videoGrid.classList.add('hidden');
      audioGrid.classList.add('hidden');
      imageGrid.classList.add('hidden');

      if (activeFormatType === 'video') {
        videoGrid.classList.remove('hidden');
        const selected = videoGrid.querySelector('.quality-item.selected') || videoGrid.querySelector('.quality-item');
        if (selected) selectQuality(selected);
      } else if (activeFormatType === 'audio') {
        audioGrid.classList.remove('hidden');
        const selected = audioGrid.querySelector('.quality-item.selected') || audioGrid.querySelector('.quality-item');
        if (selected) selectQuality(selected);
      } else if (activeFormatType === 'image') {
        imageGrid.classList.remove('hidden');
        const selected = imageGrid.querySelector('.quality-item.selected') || imageGrid.querySelector('.quality-item');
        if (selected) selectQuality(selected);
      }
    });
  });

  // Quality Item Selection
  qualityItems.forEach(item => {
    item.addEventListener('click', () => {
      selectQuality(item);
    });
  });

  function selectQuality(item) {
    const parent = item.parentElement;
    parent.querySelectorAll('.quality-item').forEach(i => i.classList.remove('selected'));
    item.classList.add('selected');
    activeQuality = item.dataset.quality;
    updateDownloadBtnLabel();
  }

  function updateDownloadBtnLabel() {
    const platformName = currentVideoData?.platform?.name || 'Media';
    
    if (activeFormatType === 'image') {
      downloadBtnLabel.textContent = `Download High-Res ${platformName} Photo`;
    } else if (activeFormatType === 'video') {
      const label = activeQuality === '4k' ? '4K Ultra' : (activeQuality === '1080' ? '1080p HD' : `${activeQuality}p`);
      downloadBtnLabel.textContent = `Download ${platformName} Video (${label})`;
    } else {
      const q = activeQuality.toUpperCase().replace('-', ' ');
      downloadBtnLabel.textContent = `Download Audio (${q})`;
    }
  }

  // Open Downloads Folder
  openFolderBtn.addEventListener('click', openDownloadsFolder);
  openSuccessFolderBtn.addEventListener('click', openDownloadsFolder);

  async function openDownloadsFolder() {
    try {
      await fetch('/api/open-downloads', { method: 'POST' });
    } catch (e) {
      console.error(e);
    }
  }

  // Trigger Save File to Browser
  saveFileBtn.addEventListener('click', () => {
    if (lastCompletedTaskId) {
      triggerBrowserDownload(lastCompletedTaskId);
    }
  });

  function triggerBrowserDownload(taskId) {
    const downloadUrl = `/api/get-file/${taskId}`;
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.setAttribute('download', '');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  // Analyze Video / Media Function
  async function analyzeVideo() {
    const url = urlInput.value.trim();
    if (!url) {
      showAlert('Please enter a YouTube, Facebook, Instagram or TikTok link.', 'error');
      return;
    }

    hideAlert();
    setAnalyzingState(true);
    mediaSection.classList.add('hidden');
    successCard.classList.add('hidden');
    progressBox.classList.add('hidden');

    try {
      const res = await fetch('/api/info', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Failed to extract media details. Make sure the post is public.');
      }

      currentVideoUrl = url;
      currentVideoData = data;

      videoTitle.textContent = data.title;
      videoUploader.textContent = data.uploader;
      videoDuration.textContent = data.duration;
      videoViews.textContent = data.views;
      videoThumbnail.src = data.thumbnail || 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=800';

      // Platform badge
      platformPill.textContent = data.platform.name;
      platformPill.style.backgroundColor = data.platform.color || '#ff0033';

      // Show/Hide Image tab based on media type
      if (data.media_type === 'image') {
        tabImage.classList.remove('hidden');
        tabImage.click(); // Activate photo tab
      } else {
        tabImage.classList.add('hidden');
        tabVideo.click(); // Activate video tab
      }

      // Format resolution availability
      const resolutions = data.resolutions || {};
      toggleQualityVisibility('4k', resolutions['4k']);
      toggleQualityVisibility('1080', resolutions['1080']);
      toggleQualityVisibility('720', resolutions['720']);
      toggleQualityVisibility('480', resolutions['480']);

      const targetRes = resolutions['1080'] ? '1080' : (resolutions['720'] ? '720' : '480');
      const targetItem = videoGrid.querySelector(`[data-quality="${targetRes}"]`);
      if (targetItem && data.media_type !== 'image') selectQuality(targetItem);

      mediaSection.classList.remove('hidden');
    } catch (err) {
      showAlert(err.message, 'error');
    } finally {
      setAnalyzingState(false);
    }
  }

  function toggleQualityVisibility(quality, isAvailable) {
    const item = videoGrid.querySelector(`[data-quality="${quality}"]`);
    if (item) {
      if (isAvailable === false) {
        item.style.opacity = '0.35';
        item.style.pointerEvents = 'none';
      } else {
        item.style.opacity = '1';
        item.style.pointerEvents = 'auto';
      }
    }
  }

  // Start Download
  startDownloadBtn.addEventListener('click', async () => {
    if (!currentVideoUrl) return;

    if (activePollInterval) clearInterval(activePollInterval);

    startDownloadBtn.disabled = true;
    startDownloadBtn.classList.add('loading');
    progressBox.classList.remove('hidden');
    successCard.classList.add('hidden');
    
    progressStatus.textContent = activeFormatType === 'image' ? 'Downloading high-resolution photo...' : 'Fetching & converting media stream...';
    progressPercent.textContent = '0%';
    progressBarFill.style.width = '0%';
    progressSpeed.textContent = 'Speed: Initializing...';
    progressEta.textContent = 'ETA: --';

    try {
      const res = await fetch('/api/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: currentVideoUrl,
          format_type: activeFormatType,
          quality: activeQuality
        })
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Download start failed');

      const taskId = data.task_id;
      pollProgress(taskId);

    } catch (err) {
      showAlert(err.message, 'error');
      startDownloadBtn.disabled = false;
      startDownloadBtn.classList.remove('loading');
      progressBox.classList.add('hidden');
    }
  });

  // Poll Progress
  function pollProgress(taskId) {
    activePollInterval = setInterval(async () => {
      try {
        const res = await fetch(`/api/progress/${taskId}`);
        const data = await res.json();

        if (data.status === 'downloading') {
          progressStatus.textContent = `Downloading ${activeQuality.toUpperCase()} stream...`;
          progressPercent.textContent = `${data.percent}%`;
          progressBarFill.style.width = `${data.percent}%`;
          progressSpeed.textContent = `Speed: ${data.speed}`;
          progressEta.textContent = `ETA: ${data.eta}`;
        } else if (data.status === 'processing') {
          progressStatus.textContent = 'Merging video & audio (FFmpeg)...';
          progressPercent.textContent = '100%';
          progressBarFill.style.width = '100%';
          progressSpeed.textContent = 'Finalizing';
          progressEta.textContent = 'Almost ready...';
        } else if (data.status === 'completed') {
          clearInterval(activePollInterval);
          lastCompletedTaskId = taskId;
          progressBox.classList.add('hidden');
          successCard.classList.remove('hidden');
          startDownloadBtn.disabled = false;
          startDownloadBtn.classList.remove('loading');
          
          // Auto trigger browser download
          triggerBrowserDownload(taskId);
          loadHistory();
        } else if (data.status === 'error') {
          clearInterval(activePollInterval);
          progressBox.classList.add('hidden');
          startDownloadBtn.disabled = false;
          startDownloadBtn.classList.remove('loading');
          showAlert(`Download failed: ${data.error}`, 'error');
        }
      } catch (err) {
        console.error('Poll error:', err);
      }
    }, 400);
  }

  // Load History
  async function loadHistory() {
    try {
      const res = await fetch('/api/history');
      const history = await res.json();
      
      if (!history || history.length === 0) {
        historyList.innerHTML = `
          <div class="empty-history">
            <p>No downloads yet in this session. Paste a YouTube, Facebook, Instagram or TikTok link above to start!</p>
          </div>
        `;
        return;
      }

      historyList.innerHTML = history.map(item => `
        <div class="history-item">
          <div class="history-item-left">
            <span class="history-badge">${item.quality}</span>
            <span class="history-title">${escapeHtml(item.title)}</span>
          </div>
          <div class="history-item-right">
            <span class="history-time">${item.time}</span>
            ${item.id ? `<button class="btn-mini-download" onclick="window.location.href='/api/get-file/${item.id}'" title="Save file to PC again">⬇ Save</button>` : ''}
          </div>
        </div>
      `).join('');

    } catch (e) {
      console.error(e);
    }
  }

  function showAlert(msg, type = 'error') {
    alertBanner.textContent = msg;
    alertBanner.className = `alert-banner ${type}`;
    alertBanner.classList.remove('hidden');
  }

  function hideAlert() {
    alertBanner.classList.add('hidden');
  }

  function setAnalyzingState(isAnalyzing) {
    if (isAnalyzing) {
      analyzeBtn.classList.add('loading');
      analyzeBtn.disabled = true;
    } else {
      analyzeBtn.classList.remove('loading');
      analyzeBtn.disabled = false;
    }
  }

  function escapeHtml(str) {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
  }
});
