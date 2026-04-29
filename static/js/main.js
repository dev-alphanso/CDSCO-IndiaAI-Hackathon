/* ── State ────────────────────────────────────────────────── */
let currentResult = null;

/* ── DOM helpers ─────────────────────────────────────────── */
const $ = id => document.getElementById(id);
const show = id => $(id).hidden = false;
const hide = id => $(id).hidden = true;

/* ── Ollama status ───────────────────────────────────────── */
async function checkStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    const dot   = $('statusDot');
    const label = $('statusLabel');
    const sel   = $('modelSelect');

    if (data.ollama_running) {
      dot.className   = 'status-dot online';
      label.textContent = 'Ollama Online';
      if (data.models && data.models.length) {
        sel.innerHTML = data.models.map(m =>
          `<option value="${m}">${m}</option>`).join('');
      }
    } else {
      dot.className   = 'status-dot offline';
      label.textContent = 'Ollama Offline';
    }
  } catch {
    $('statusDot').className = 'status-dot offline';
    $('statusLabel').textContent = 'Server Error';
  }
}

/* ── File handling ───────────────────────────────────────── */
function setFile(file) {
  if (!file) return;
  const chip = $('fileChip');
  chip.textContent = file.name;
  show('filePreview');
  $('processBtn').disabled = false;
  setStep(2);
}

function clearFile() {
  $('fileInput').value = '';
  hide('filePreview');
  $('processBtn').disabled = true;
  setStep(1);
}

/* ── Workflow steps ──────────────────────────────────────── */
function setStep(n) {
  for (let i = 1; i <= 5; i++) {
    const el = $(`step${i}`);
    el.classList.remove('active', 'done');
    if (i < n)  el.classList.add('done');
    if (i === n) el.classList.add('active');
  }
}

/* ── Mode selection ──────────────────────────────────────── */
document.querySelectorAll('.mode-item').forEach(item => {
  item.addEventListener('click', () => {
    document.querySelectorAll('.mode-item').forEach(m => m.classList.remove('active'));
    item.classList.add('active');
    item.querySelector('input[type=radio]').checked = true;
  });
});

/* ── Drag & drop ─────────────────────────────────────────── */
const dropZone = $('dropZone');
dropZone.addEventListener('click', e => {
  if (!e.target.closest('.file-preview') && !e.target.closest('.btn-outline:not(#clearFile)')) {
    $('fileInput').click();
  }
});
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (f) setFile(f);
});
$('fileInput').addEventListener('change', e => setFile(e.target.files[0]));
$('clearFile').addEventListener('click', e => { e.stopPropagation(); clearFile(); });

/* ── Processing UI helpers ───────────────────────────────── */
const PROC_STEPS = ['procOcr', 'procClean', 'procLlm', 'procOut'];

function setProcessingStep(idx) {
  PROC_STEPS.forEach((id, i) => {
    const el = $(id);
    const dot = el.querySelector('.proc-dot');
    el.classList.remove('active', 'pending');
    dot.classList.remove('spinning', 'done-dot');
    if (i < idx) {
      el.classList.add('done');
      dot.classList.add('done-dot');
    } else if (i === idx) {
      el.classList.add('active');
      dot.classList.add('spinning');
    } else {
      el.classList.add('pending');
    }
  });
  const pct = Math.round((idx / PROC_STEPS.length) * 80) + 10;
  $('progressBar').style.width = pct + '%';
}

function markAllStepsDone() {
  PROC_STEPS.forEach(id => {
    const el = $(id);
    const dot = el.querySelector('.proc-dot');
    el.classList.remove('active', 'pending', 'done');
    dot.classList.remove('spinning');
    el.classList.add('done');
    dot.classList.add('done-dot');
  });
}

function showProcessing() {
  hide('idleState');
  hide('resultsState');
  hide('errorState');
  show('processingState');
  setProcessingStep(0);
  setStep(3);
}

function showResults(data) {
  hide('processingState');
  hide('errorState');
  show('resultsState');
  setStep(5);
  renderResults(data);
}

function showError(msg) {
  hide('processingState');
  hide('resultsState');
  show('errorState');
  $('errorMsg').textContent = msg;
}

/* ── Process button ──────────────────────────────────────── */
$('processBtn').addEventListener('click', async () => {
  const fileInput = $('fileInput');
  const file = fileInput.files[0];
  if (!file) return;

  const mode  = document.querySelector('input[name="mode"]:checked').value;
  const model = $('modelSelect').value;

  console.log(`[MedDoc] LLM process starting — model: ${model}, mode: ${mode}, file: ${file.name}`);

  const fd = new FormData();
  fd.append('file', file);
  fd.append('mode', mode);
  fd.append('model', model);

  showProcessing();
  $('processBtn').disabled = true;

  // Simulate step progress while waiting
  let stepIdx = 0;
  const timer = setInterval(() => {
    if (stepIdx < 2) { stepIdx++; setProcessingStep(stepIdx); }
  }, 3000);

  try {
    const res = await fetch('/api/process', { method: 'POST', body: fd });
    clearInterval(timer);

    // Advance to "Generating Output" step (active/spinning)
    setProcessingStep(3);
    $('progressBar').style.width = '95%';

    const data = await res.json();
    if (!res.ok || data.error) {
      showError(data.error || 'An unknown error occurred.');
    } else {
      // Mark ALL steps done, fill bar, then transition after a short pause
      markAllStepsDone();
      $('progressBar').style.width = '100%';
      setTimeout(() => { currentResult = data; showResults(data); loadHistory(); }, 700);
    }
  } catch (err) {
    clearInterval(timer);
    showError('Network error — is the Flask server running?');
  } finally {
    $('processBtn').disabled = false;
  }
});

/* ── Render results ──────────────────────────────────────── */
function renderResults(data) {
  // Meta bar
  const ts = new Date(data.timestamp).toLocaleString();
  $('resultsMeta').innerHTML = `
    <span><strong>${data.filename}</strong></span>
    <span>Mode: <strong>${data.mode}</strong></span>
    <span>${ts}</span>`;

  // Reset tabs
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => { t.hidden = true; t.classList.remove('active'); });
  document.querySelector('.tab[data-tab="output"]').classList.add('active');
  $('tabOutput').hidden = false; $('tabOutput').classList.add('active');

  // Hide all output views
  hide('summaryView'); hide('maskView'); hide('reportView');

  const { type, content } = data.output;

  if (type === 'summary') {
    $('summaryContent').innerHTML = markdownToHtml(content);
    show('summaryView');
  } else if (type === 'mask') {
    $('maskContent').innerHTML = highlightMasked(escapeHtml(content));
    show('maskView');
  } else if (type === 'report') {
    renderReportGrid(content);
    show('reportView');
  }

  // Raw OCR
  $('rawContent').textContent = data.raw_text || '(no text)';

  // Entities
  renderEntities(data.entities || {});
}

function markdownToHtml(md) {
  return md
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>[\s\S]*?<\/li>)+/g, m => `<ul>${m}</ul>`)
    .replace(/\n{2,}/g, '<br/><br/>');
}

function escapeHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function highlightMasked(s) {
  return s.replace(/\[(PATIENT_NAME|DOCTOR_NAME|FACILITY_NAME|PHONE|EMAIL|ADDRESS|DOB|ID_NUMBER|REDACTED|AADHAR|PAN)\]/g,
    '<span class="masked-token">[$1]</span>');
}

function renderReportGrid(data) {
  const grid = $('reportGrid');
  if (data.parse_error) {
    grid.innerHTML = `<div class="report-field field-wide">
      <label>Raw Output</label><pre class="field-val">${escapeHtml(data.raw || '')}</pre></div>`;
    return;
  }

  const SCALAR_FIELDS = [
    ['patient_name','Patient Name'], ['patient_age','Age'], ['patient_gender','Gender'],
    ['visit_date','Visit Date'], ['doctor_name','Doctor'], ['facility_name','Facility'],
    ['chief_complaint','Chief Complaint'], ['doctor_notes','Doctor Notes'],
    ['follow_up','Follow-Up'], ['document_type','Document Type'],
  ];
  const LIST_FIELDS = [['diagnosis','Diagnoses']];
  const MEDS_FIELD  = 'medications';

  let html = '';
  SCALAR_FIELDS.forEach(([key, label]) => {
    const val = data[key] || '';
    html += `<div class="report-field">
      <label>${label}</label>
      <div class="field-val ${val ? '' : 'empty'}">${escapeHtml(val) || '—'}</div>
    </div>`;
  });

  LIST_FIELDS.forEach(([key, label]) => {
    const arr = Array.isArray(data[key]) ? data[key] : [];
    html += `<div class="report-field">
      <label>${label}</label>
      ${arr.length
        ? `<ul class="field-list">${arr.map(v => `<li>${escapeHtml(typeof v === 'object' ? (v.name || v.test_name || JSON.stringify(v)) : String(v))}</li>`).join('')}</ul>`
        : '<div class="field-val empty">—</div>'}
    </div>`;
  });

  // Lab Tests — dedicated table (items may be objects or strings)
  const labs = Array.isArray(data.lab_tests) ? data.lab_tests : [];
  if (labs.length) {
    const labsAreObjects = labs.some(l => typeof l === 'object' && l !== null);
    if (labsAreObjects) {
      function _labRow(l, indent) {
        if (typeof l === 'string') return `<tr><td colspan="5" style="padding-left:${indent?18:8}px;color:#64748b">${escapeHtml(l)}</td></tr>`;
        const name   = escapeHtml(l.test_name || l.name || l.test || '—');
        const value  = escapeHtml(String(l.value ?? l.observed_value ?? l.result ?? '—'));
        const unit   = escapeHtml(l.unit || l.units || '');
        const range  = escapeHtml(l.reference_range || l.normal_range || l.reference_interval || l.range || '');
        const status = l.status || l.flag || '';
        const sc = /abnormal|high|low|positive/i.test(status) ? 'lab-status-abnormal'
                 : /normal|negative/i.test(status)            ? 'lab-status-normal' : '';
        return `<tr>
          <td style="padding-left:${indent?18:8}px">${name}</td>
          <td class="lab-val">${value}</td>
          <td>${unit}</td>
          <td>${range}</td>
          <td><span class="lab-status ${sc}">${escapeHtml(status)}</span></td>
        </tr>`;
      }
      const rows = labs.flatMap(l => {
        if (typeof l === 'string') return [_labRow(l, false)];
        const subItems = Array.isArray(l.sub_tests) ? l.sub_tests
                       : Array.isArray(l.results)   ? l.results : [];
        if (subItems.length) {
          const hdr = `<tr><td colspan="5" style="font-weight:600;padding:5px 8px;background:#f8fafc;color:#334155">${escapeHtml(l.test_name||l.name||l.test||'')}</td></tr>`;
          return [hdr, ...subItems.map(s => _labRow(s, true))];
        }
        return [_labRow(l, false)];
      }).join('');
      html += `<div class="report-field field-wide lab-tests-card">
        <label>Lab Tests</label>
        <div class="lab-table-wrap">
          <table class="lab-table">
            <thead><tr>
              <th>Test Name</th><th>Value</th><th>Unit</th><th>Reference Range</th><th>Status</th>
            </tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </div>`;
    } else {
      html += `<div class="report-field field-wide"><label>Lab Tests</label>
        <ul class="field-list">${labs.map(v => `<li>${escapeHtml(String(v))}</li>`).join('')}</ul>
      </div>`;
    }
  }

  // Medications
  const meds = Array.isArray(data[MEDS_FIELD]) ? data[MEDS_FIELD] : [];
  if (meds.length) {
    html += `<div class="report-field field-wide"><label>Medications</label>
      <ul class="field-list">${meds.map(m =>
        `<li><strong>${escapeHtml(m.name||'')}</strong>${m.dosage ? ' · ' + escapeHtml(m.dosage) : ''}${m.frequency ? ' · ' + escapeHtml(m.frequency) : ''}${m.duration ? ' · ' + escapeHtml(m.duration) : ''}</li>`
      ).join('')}</ul></div>`;
  }

  // Vitals
  if (data.vitals && typeof data.vitals === 'object' && Object.keys(data.vitals).length) {
    const vEntries = Object.entries(data.vitals).map(([k,v]) => `<li><strong>${escapeHtml(k)}</strong>: ${escapeHtml(String(v))}</li>`).join('');
    html += `<div class="report-field field-wide"><label>Vitals</label><ul class="field-list">${vEntries}</ul></div>`;
  }

  grid.innerHTML = html;
}

function renderEntities(entities) {
  const grid = $('entitiesGrid');
  const keys = Object.keys(entities);
  if (!keys.length) {
    grid.innerHTML = '<div class="entities-empty">No PII entities detected by rule-based scanner.</div>';
    return;
  }
  grid.innerHTML = keys.map(key => `
    <div class="entity-card">
      <h4>${key}</h4>
      <div class="entity-tags">
        ${entities[key].map(v => `<span class="entity-tag">${escapeHtml(String(v))}</span>`).join('')}
      </div>
    </div>`).join('');
}

/* ── Tabs ────────────────────────────────────────────────── */
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    const target = tab.dataset.tab;
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => { t.hidden = true; t.classList.remove('active'); });
    tab.classList.add('active');
    $('tab' + target.charAt(0).toUpperCase() + target.slice(1)).hidden = false;
    $('tab' + target.charAt(0).toUpperCase() + target.slice(1)).classList.add('active');
  });
});

/* ── Copy ────────────────────────────────────────────────── */
$('copyBtn').addEventListener('click', () => {
  if (!currentResult) return;
  const { type, content } = currentResult.output;
  const text = type === 'report' ? JSON.stringify(content, null, 2) : content;
  navigator.clipboard.writeText(text).then(() => {
    $('copyBtn').textContent = 'Copied!';
    setTimeout(() => $('copyBtn').textContent = 'Copy', 1800);
  });
});

/* ── Download dropdown ───────────────────────────────────── */
const dlDropdown = $('dlDropdown');

$('dlToggle').addEventListener('click', (e) => {
  e.stopPropagation();
  dlDropdown.classList.toggle('open');
});

document.addEventListener('click', () => dlDropdown.classList.remove('open'));

document.querySelectorAll('.dl-item').forEach(btn => {
  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    dlDropdown.classList.remove('open');
    if (!currentResult) return;
    const fmt = btn.dataset.fmt;
    if (fmt === 'json') {
      window.location = `/api/download/${currentResult.job_id}`;
    } else {
      window.location = `/api/export/${currentResult.job_id}/${fmt}`;
    }
  });
});

/* ── New job ─────────────────────────────────────────────── */
$('newJobBtn').addEventListener('click', () => {
  clearFile();
  hide('resultsState');
  show('idleState');
  currentResult = null;
});

/* ── Retry ───────────────────────────────────────────────── */
$('retryBtn').addEventListener('click', () => {
  hide('errorState');
  show('idleState');
  setStep(1);
});

/* ── History ─────────────────────────────────────────────── */
async function loadHistory() {
  try {
    const res  = await fetch('/api/history');
    const data = await res.json();
    const list = $('historyList');
    if (!data.length) {
      list.innerHTML = '<li class="history-empty">No jobs yet</li>';
      return;
    }
    list.innerHTML = data.map(j => `
      <li>
        <div class="history-item">
          <div class="hist-main" onclick="loadJob('${j.job_id}')">
            <strong>${j.filename}</strong>
            <span>${new Date(j.timestamp).toLocaleString()}</span>
            <div class="hist-badges">
              <span class="hist-tag hist-${j.mode}">${j.mode}</span>
            </div>
          </div>
          <button class="hist-del-btn" title="Delete job" onclick="deleteJob('${j.job_id}', this)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/>
            </svg>
          </button>
        </div>
      </li>`).join('');
  } catch { /* silently ignore */ }
}

async function deleteJob(jobId, btn) {
  btn.disabled = true;
  btn.classList.add('deleting');
  try {
    const res = await fetch(`/api/jobs/${jobId}`, { method: 'DELETE' });
    if (res.ok) {
      const li = btn.closest('li');
      li.classList.add('hist-fade-out');
      li.addEventListener('animationend', () => {
        li.remove();
        // Show "no jobs" placeholder if list is now empty
        const list = $('historyList');
        if (!list.querySelector('.history-item')) {
          list.innerHTML = '<li class="history-empty">No jobs yet</li>';
        }
      }, { once: true });
      // If the deleted job is currently displayed, reset to idle
      if (currentResult && currentResult.job_id === jobId) {
        currentResult = null;
        hide('resultsState');
        show('idleState');
        setStep(1);
      }
    }
  } catch { btn.disabled = false; btn.classList.remove('deleting'); }
}

async function loadJob(jobId) {
  try {
    const res  = await fetch(`/api/download/${jobId}`);
    const data = await res.json();
    currentResult = data;
    hide('idleState');
    hide('processingState');
    show('resultsState');
    renderResults(data);
    setStep(5);
  } catch (e) {
    alert('Could not load job: ' + e.message);
  }
}

$('refreshHistory').addEventListener('click', loadHistory);

/* ── Init ────────────────────────────────────────────────── */
checkStatus();
loadHistory();
