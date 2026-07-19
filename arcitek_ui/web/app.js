const api = {
  async request(path, options) {
    const response = await fetch(path, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...options?.headers },
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Compute service unavailable');
    return payload;
  },
  metrics() {
    return this.request('/api/metrics');
  },
  jobs() {
    return this.request('/api/jobs');
  },
  submit(workload, size) {
    return this.request('/api/jobs', {
      method: 'POST',
      body: JSON.stringify({ workload, size }),
    });
  },
};

const elements = {
  cpu: document.querySelector('#cpu-value'),
  memory: document.querySelector('#memory-value'),
  memoryProgress: document.querySelector('#memory-progress'),
  memoryFree: document.querySelector('#memory-free'),
  jobs: document.querySelector('#jobs-value'),
  running: document.querySelector('#running-count'),
  queued: document.querySelector('#queued-count'),
  uptime: document.querySelector('#uptime-value'),
  workers: document.querySelector('#worker-count'),
  table: document.querySelector('#jobs-table'),
  dialog: document.querySelector('#job-dialog'),
  form: document.querySelector('#job-form'),
  select: document.querySelector('#workload-select'),
  size: document.querySelector('#workload-size'),
  hint: document.querySelector('#form-hint'),
  toast: document.querySelector('#toast'),
};

const workloadConfig = {
  'prime-scan': { label: 'Prime scan', symbol: '⌗', min: 1000, max: 2000000 },
  'hash-benchmark': { label: 'Hash benchmark', symbol: '✣', min: 1000, max: 1000000 },
  fibonacci: { label: 'Sequence engine', symbol: '∞', min: 100, max: 100000 },
};

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function showToast(message, error = false) {
  elements.toast.textContent = message;
  elements.toast.classList.toggle('error', error);
  elements.toast.classList.add('show');
  window.setTimeout(() => elements.toast.classList.remove('show'), 3000);
}

function formatUptime(seconds) {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

function renderBars() {
  const bars = document.querySelector('#cpu-bars');
  bars.innerHTML = '<i></i>'.repeat(12);
}

async function refreshMetrics() {
  try {
    const metrics = await api.metrics();
    elements.cpu.textContent = metrics.cpuLoad.toFixed(1);
    elements.memory.textContent = metrics.memoryPercent.toFixed(1);
    elements.memoryProgress.style.width = `${metrics.memoryPercent}%`;
    elements.memoryFree.textContent = `${Math.max(0, 100 - metrics.memoryPercent).toFixed(1)}%`;
    elements.jobs.textContent = metrics.runningJobs + metrics.queuedJobs;
    elements.running.textContent = metrics.runningJobs;
    elements.queued.textContent = metrics.queuedJobs;
    elements.uptime.textContent = formatUptime(metrics.uptimeSeconds);
    elements.workers.textContent = `${metrics.workers} active`;
    renderBars();
  } catch {
    showToast('Unable to reach the compute API', true);
  }
}

function renderJobs(jobs) {
  if (!jobs.length) {
    elements.table.innerHTML =
      '<tr class="empty-row"><td colspan="5">No workloads yet. Launch your first compute job.</td></tr>';
    return;
  }
  elements.table.innerHTML = jobs.slice(0, 6).map((job) => {
    const config = workloadConfig[job.workload] || { label: job.workload, symbol: '◇' };
    const created = new Date(job.createdAt * 1000).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    });
    const duration = job.durationMs === null ? '—' : `${job.durationMs.toLocaleString()} ms`;
    return `<tr>
      <td><span class="workload-name"><i class="workload-symbol">${escapeHtml(config.symbol)}</i>${escapeHtml(config.label)}</span></td>
      <td><span class="status-badge ${escapeHtml(job.status)}"><i></i>${escapeHtml(job.status)}</span></td>
      <td>${Number(job.size).toLocaleString()} ops</td>
      <td>${escapeHtml(duration)}</td>
      <td>${escapeHtml(created)}</td>
    </tr>`;
  }).join('');
}

async function refreshJobs() {
  try {
    const { jobs } = await api.jobs();
    renderJobs(jobs);
  } catch {
    showToast('Could not load workload activity', true);
  }
}

function updateLimits() {
  const config = workloadConfig[elements.select.value];
  elements.size.min = config.min;
  elements.size.max = config.max;
  if (+elements.size.value < config.min || +elements.size.value > config.max) {
    elements.size.value = config.min;
  }
  elements.hint.textContent = `Accepted range: ${config.min.toLocaleString()}–${config.max.toLocaleString()}`;
}

function openDialog(workload = 'prime-scan', size = 75000) {
  elements.select.value = workload;
  elements.size.value = size;
  updateLimits();
  elements.dialog.showModal();
}

document.querySelector('#open-job').addEventListener('click', () => openDialog());
document.querySelector('#close-dialog').addEventListener('click', () => elements.dialog.close());
document.querySelector('#cancel-dialog').addEventListener('click', () => elements.dialog.close());
document.querySelector('#refresh-jobs').addEventListener('click', refreshJobs);
document.querySelector('.mobile-menu').addEventListener('click', () => {
  document.querySelector('.sidebar').classList.toggle('open');
});
elements.select.addEventListener('change', updateLimits);
document.querySelectorAll('.action-card').forEach((button) => {
  button.addEventListener('click', () => openDialog(button.dataset.workload, +button.dataset.size));
});
elements.form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const submit = elements.form.querySelector('[type="submit"]');
  submit.disabled = true;
  try {
    await api.submit(elements.select.value, +elements.size.value);
    elements.dialog.close();
    showToast('Workload accepted by the compute node');
    await Promise.all([refreshJobs(), refreshMetrics()]);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    submit.disabled = false;
  }
});

renderBars();
Promise.all([refreshMetrics(), refreshJobs()]);
window.setInterval(() => Promise.all([refreshMetrics(), refreshJobs()]), 5000);
