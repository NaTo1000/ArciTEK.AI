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
  dashboard() {
    return this.request('/api/dashboard');
  },
  listProjects() {
    return this.request('/api/projects');
  },
  createProject(payload) {
    return this.request('/api/projects', { method: 'POST', body: JSON.stringify(payload) });
  },
  getFindings(projectId) {
    return this.request(`/api/projects/${encodeURIComponent(projectId)}/findings`);
  },
  approveRevision(projectId, revision, approver, decision) {
    return this.request(`/api/projects/${encodeURIComponent(projectId)}/approvals`, {
      method: 'POST',
      body: JSON.stringify({ revision, approver, decision }),
    });
  },
  listPlans(projectId) {
    return this.request(`/api/projects/${encodeURIComponent(projectId)}/plans`);
  },
  createPlan(projectId, requestedBy) {
    return this.request(`/api/projects/${encodeURIComponent(projectId)}/plans`, {
      method: 'POST',
      body: JSON.stringify({ requested_by: requestedBy }),
    });
  },
  approvePlan(planId, approver, decision) {
    return this.request(`/api/plans/${encodeURIComponent(planId)}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approver, decision }),
    });
  },
  planActivity(planId) {
    return this.request(`/api/plans/${encodeURIComponent(planId)}/activity?limit=20`);
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
  // Engineering control plane
  projectsTable: document.querySelector('#projects-table'),
  findingsTable: document.querySelector('#findings-table'),
  activityTable: document.querySelector('#activity-table'),
  engProjectCount: document.querySelector('#eng-project-count'),
  engPlanCount: document.querySelector('#eng-plan-count'),
  engPlanReleased: document.querySelector('#eng-plan-released'),
  engPlanPending: document.querySelector('#eng-plan-pending'),
  engCriticalCount: document.querySelector('#eng-critical-count'),
  engSelectedProject: document.querySelector('#eng-selected-project'),
  projectDialog: document.querySelector('#project-dialog'),
  projectForm: document.querySelector('#project-form'),
  projectName: document.querySelector('#project-name'),
  projectAuthor: document.querySelector('#project-author'),
  projectDescription: document.querySelector('#project-description'),
  projectRequirements: document.querySelector('#project-requirements'),
  projectParts: document.querySelector('#project-parts'),
  createPlanBtn: document.querySelector('#create-plan-btn'),
  approveRevisionBtn: document.querySelector('#approve-revision-btn'),
  approvePlanBtn: document.querySelector('#approve-plan-btn'),
};

const engineeringState = {
  selectedProjectId: null,
  latestPlanId: null,
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
document.querySelectorAll('#workloads .action-card').forEach((button) => {
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

// -- Engineering control plane (robotics project plans) --------------------

function severityRank(severity) {
  const order = ['critical', 'high', 'medium', 'low', 'info'];
  const index = order.indexOf(severity);
  return index === -1 ? order.length : index;
}

function renderProjects(projects) {
  if (!projects.length) {
    elements.projectsTable.innerHTML =
      '<tr class="empty-row"><td colspan="4">No projects yet. Create one to begin.</td></tr>';
    return;
  }
  elements.projectsTable.innerHTML = projects.map((project) => {
    const selected = project.id === engineeringState.selectedProjectId;
    return `<tr data-project-id="${escapeHtml(project.id)}" class="clickable-row${selected ? ' selected-row' : ''}">
      <td>${escapeHtml(project.name)}</td>
      <td>#${escapeHtml(project.current_revision)}</td>
      <td><span class="status-badge ${escapeHtml(project.approval_status)}"><i></i>${escapeHtml(project.approval_status)}</span></td>
      <td>${escapeHtml(project.findings_summary.total)} (${escapeHtml(project.findings_summary.critical)} critical)</td>
    </tr>`;
  }).join('');
  elements.projectsTable.querySelectorAll('tr[data-project-id]').forEach((row) => {
    row.addEventListener('click', () => selectProject(row.dataset.projectId));
  });
}

function renderFindings(findings) {
  if (!findings || !findings.length) {
    elements.findingsTable.innerHTML =
      '<tr class="empty-row"><td colspan="4">No findings for the selected revision.</td></tr>';
    return;
  }
  const sorted = [...findings].sort((a, b) => severityRank(a.severity) - severityRank(b.severity));
  elements.findingsTable.innerHTML = sorted.slice(0, 10).map((finding) => `<tr>
      <td><span class="status-badge ${escapeHtml(finding.severity)}"><i></i>${escapeHtml(finding.severity)}</span></td>
      <td>${escapeHtml(finding.rule)}</td>
      <td>${escapeHtml(finding.message)}</td>
      <td>${Math.round(finding.confidence * 100)}%</td>
    </tr>`).join('');
}

function renderActivity(activity) {
  if (!activity || !activity.length) {
    elements.activityTable.innerHTML =
      '<tr class="empty-row"><td colspan="2">No plan activity yet.</td></tr>';
    return;
  }
  elements.activityTable.innerHTML = activity.slice(0, 10).map((entry) => {
    const when = new Date(entry.timestamp * 1000).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    });
    return `<tr><td>${escapeHtml(entry.action)}</td><td>${escapeHtml(when)}</td></tr>`;
  }).join('');
}

async function refreshDashboard() {
  try {
    const summary = await api.dashboard();
    elements.engProjectCount.textContent = summary.project_count;
    elements.engPlanCount.textContent = summary.plan_count;
    elements.engPlanReleased.textContent = summary.plans_released;
    elements.engPlanPending.textContent = summary.plans_awaiting_approval;
    elements.engCriticalCount.textContent = summary.severity_totals.critical || 0;
  } catch {
    showToast('Unable to reach the engineering API', true);
  }
}

async function refreshEngineeringProjects() {
  try {
    const { projects } = await api.listProjects();
    renderProjects(projects);
    if (!engineeringState.selectedProjectId && projects.length) {
      await selectProject(projects[0].id);
    }
  } catch {
    showToast('Could not load robotics projects', true);
  }
}

async function refreshProjectActivity(projectId) {
  try {
    const { plans } = await api.listPlans(projectId);
    if (plans.length) {
      engineeringState.latestPlanId = plans[0].id;
      const { activity } = await api.planActivity(plans[0].id);
      renderActivity(activity);
    } else {
      engineeringState.latestPlanId = null;
      renderActivity([]);
    }
  } catch {
    showToast('Could not load agent activity', true);
  }
}

async function selectProject(projectId) {
  engineeringState.selectedProjectId = projectId;
  elements.engSelectedProject.textContent = projectId;
  try {
    const { findings } = await api.getFindings(projectId);
    renderFindings(findings);
  } catch {
    showToast('Could not load findings', true);
  }
  await refreshProjectActivity(projectId);
  const { projects } = await api.listProjects();
  renderProjects(projects);
}

async function refreshEngineering() {
  await Promise.all([refreshDashboard(), refreshEngineeringProjects()]);
}

function openProjectDialog() {
  elements.projectForm.reset();
  elements.projectDialog.showModal();
}

document.querySelector('#refresh-engineering').addEventListener('click', refreshEngineering);
document.querySelector('#open-project').addEventListener('click', openProjectDialog);
document.querySelector('#close-project-dialog').addEventListener('click', () => elements.projectDialog.close());
document.querySelector('#cancel-project-dialog').addEventListener('click', () => elements.projectDialog.close());

elements.projectForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const submit = elements.projectForm.querySelector('[type="submit"]');
  submit.disabled = true;
  try {
    const requirements = elements.projectRequirements.value
      .split(';')
      .map((text) => text.trim())
      .filter(Boolean)
      .map((text) => ({ text }));
    let parts;
    const rawParts = elements.projectParts.value.trim();
    if (rawParts) {
      try {
        parts = JSON.parse(rawParts);
      } catch {
        throw new Error('Parts must be valid JSON');
      }
    }
    const { project } = await api.createProject({
      name: elements.projectName.value,
      author: elements.projectAuthor.value,
      description: elements.projectDescription.value,
      requirements,
      parts,
    });
    elements.projectDialog.close();
    showToast(`Project "${project.name}" created`);
    await refreshDashboard();
    await selectProject(project.id);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    submit.disabled = false;
  }
});

elements.createPlanBtn.addEventListener('click', async () => {
  if (!engineeringState.selectedProjectId) {
    showToast('Select a project first', true);
    return;
  }
  try {
    await api.createPlan(engineeringState.selectedProjectId, 'workspace-operator');
    showToast('Expert plan generated');
    await Promise.all([refreshDashboard(), refreshProjectActivity(engineeringState.selectedProjectId)]);
  } catch (error) {
    showToast(error.message, true);
  }
});

elements.approveRevisionBtn.addEventListener('click', async () => {
  if (!engineeringState.selectedProjectId) {
    showToast('Select a project first', true);
    return;
  }
  try {
    const { projects } = await api.listProjects();
    const project = projects.find((item) => item.id === engineeringState.selectedProjectId);
    if (!project) throw new Error('Project not found');
    await api.approveRevision(project.id, project.current_revision, 'workspace-operator', 'approved');
    showToast(`Revision #${project.current_revision} approved`);
    await refreshEngineeringProjects();
  } catch (error) {
    showToast(error.message, true);
  }
});

elements.approvePlanBtn.addEventListener('click', async () => {
  if (!engineeringState.latestPlanId) {
    showToast('Generate a plan first', true);
    return;
  }
  try {
    await api.approvePlan(engineeringState.latestPlanId, 'workspace-operator', 'approved');
    showToast('Plan approved and released');
    await Promise.all([refreshDashboard(), refreshProjectActivity(engineeringState.selectedProjectId)]);
  } catch (error) {
    showToast(error.message, true);
  }
});

renderBars();
Promise.all([refreshMetrics(), refreshJobs(), refreshEngineering()]);
window.setInterval(() => Promise.all([refreshMetrics(), refreshJobs()]), 5000);
window.setInterval(() => refreshDashboard(), 8000);
