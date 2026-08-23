let sampleRFQsData = {};

document.addEventListener("DOMContentLoaded", () => {
  loadConfig();
  loadSampleRFQs();
  loadCatalog();
  loadCRM();
  loadPendingApprovals();

  document.getElementById("config-form").addEventListener("submit", (e) => {
    e.preventDefault();
    saveConfig();
  });
});

function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

  const activeBtn = Array.from(document.querySelectorAll('.tab-btn')).find(b => b.getAttribute('onclick').includes(tabId));
  if (activeBtn) activeBtn.classList.add('active');

  const activeTab = document.getElementById(`${tabId}-tab`);
  if (activeTab) activeTab.classList.add('active');

  if (tabId === 'crm') loadCRM();
  if (tabId === 'approvals') loadPendingApprovals();
  if (tabId === 'catalog') loadCatalog();
}

async function loadConfig() {
  try {
    const res = await fetch('/api/config');
    const cfg = await res.json();
    document.getElementById("azure_openai_endpoint").value = cfg.azure_openai_endpoint || "https://oai-rfq-automation-01.openai.azure.com/";
    document.getElementById("azure_openai_key").value = cfg.azure_openai_key || "";
    document.getElementById("azure_openai_deployment").value = cfg.azure_openai_deployment || "gpt-5";
    document.getElementById("azure_doc_intel_endpoint").value = cfg.azure_doc_intel_endpoint || "";
  } catch (err) {
    console.error("Error loading config:", err);
  }
}

async function saveConfig() {
  const cfg = {
    azure_openai_endpoint: document.getElementById("azure_openai_endpoint").value,
    azure_openai_key: document.getElementById("azure_openai_key").value,
    azure_openai_deployment: document.getElementById("azure_openai_deployment").value,
    azure_doc_intel_endpoint: document.getElementById("azure_doc_intel_endpoint").value
  };

  try {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cfg)
    });
    const result = await res.json();
    alert(result.message);
  } catch (err) {
    alert("Failed to save config: " + err);
  }
}

async function loadSampleRFQs() {
  try {
    const res = await fetch('/api/sample-rfqs');
    sampleRFQsData = await res.json();

    const select = document.getElementById("sample-rfq-select");
    select.innerHTML = '<option value="">-- Select a Pre-Loaded Sample --</option>';

    for (const [key, sample] of Object.entries(sampleRFQsData)) {
      const opt = document.createElement("option");
      opt.value = key;
      opt.textContent = `${sample.title}`;
      select.appendChild(opt);
    }
  } catch (err) {
    console.error("Error loading samples:", err);
  }
}

function loadSelectedSample() {
  const key = document.getElementById("sample-rfq-select").value;
  if (!key || !sampleRFQsData[key]) return;

  const sample = sampleRFQsData[key];
  document.getElementById("sender_name").value = sample.sender_name;
  document.getElementById("sender_email").value = sample.sender_email;
  document.getElementById("company").value = sample.company;
  document.getElementById("phone").value = sample.phone;
  document.getElementById("subject").value = sample.subject;
  document.getElementById("attachment_name").value = sample.attachment_name;
  document.getElementById("body").value = sample.body;
}

async function processRFQ() {
  const payload = {
    sender_name: document.getElementById("sender_name").value,
    sender_email: document.getElementById("sender_email").value,
    company: document.getElementById("company").value,
    phone: document.getElementById("phone").value,
    subject: document.getElementById("subject").value,
    attachment_name: document.getElementById("attachment_name").value,
    body: document.getElementById("body").value
  };

  const spinner = document.getElementById("processing-spinner");
  const output = document.getElementById("processing-output");

  spinner.style.display = "block";
  output.innerHTML = "";

  try {
    const res = await fetch('/api/process-rfq', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    spinner.style.display = "none";
    const data = await res.json();

    if (!res.ok) {
      output.innerHTML = `
        <div style="background: rgba(239,68,68,0.15); border: 1px solid var(--danger); padding: 1rem; border-radius: 8px; color: var(--danger);">
          <h4><i class="fa-solid fa-triangle-exclamation"></i> ${data.error_code || 'Error'}</h4>
          <p>${data.message}</p>
          <p><strong>Action Taken:</strong> ${data.action_taken}</p>
        </div>`;
      return;
    }

    const rfq = data.rfq_record;
    const isApproval = rfq.requires_approval;

    let itemsHtml = rfq.items.map(item => `
      <tr>
        <td><strong>${item.name}</strong><br><small style="color:var(--text-muted);">${item.sku}</small></td>
        <td>${item.qty}</td>
        <td>$${item.unit_price.toFixed(2)}</td>
        <td><strong>$${item.line_total.toFixed(2)}</strong></td>
        <td>${item.lead_time}</td>
      </tr>
    `).join('');

    output.innerHTML = `
      <div style="margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center;">
        <div>
          <h3 style="color: var(--accent-cyan);">${rfq.rfq_id} (${rfq.customer_name})</h3>
          <span style="font-size: 0.8rem; color: var(--text-muted);">AI Extraction Confidence: ${(rfq.confidence_score * 100).toFixed(0)}%</span>
        </div>
        <span class="badge ${isApproval ? 'badge-pending' : 'badge-sent'}">${rfq.status}</span>
      </div>

      ${isApproval ? `
        <div style="background: rgba(245,158,11,0.15); border: 1px solid var(--warning); padding: 12px; border-radius: 8px; margin-bottom: 1rem; color: var(--warning); font-size: 0.85rem;">
          <i class="fa-solid fa-circle-exclamation"></i> <strong>Approval Required:</strong> ${rfq.approval_reasons.join(', ')}
        </div>
      ` : ''}

      <h4>Itemized Pricing Lookup:</h4>
      <table>
        <thead>
          <tr><th>Item & SKU</th><th>Qty</th><th>Unit Price</th><th>Total</th><th>Lead Time</th></tr>
        </thead>
        <tbody>${itemsHtml}</tbody>
      </table>

      <div style="text-align: right; margin: 1rem 0; font-size: 1.2rem; font-weight: bold; color: var(--accent-cyan);">
        Total Quoted: $${rfq.quote_total.toLocaleString('en-US', {minimumFractionDigits: 2})} USD
      </div>

      <h4>Customer Email Draft Preview:</h4>
      <div style="background: rgba(11,15,25,0.9); padding: 1rem; border-radius: 8px; border: 1px solid var(--border-color); margin-top: 0.5rem; max-height: 250px; overflow-y: auto;">
        ${rfq.draft_email_html}
      </div>

      ${isApproval ? `
        <div style="margin-top: 1rem; display: flex; gap: 10px;">
          <button class="btn btn-success" onclick="approveQuoteDirect('${rfq.rfq_id}')"><i class="fa-solid fa-check"></i> Approve & Send Email</button>
        </div>
      ` : ''}
    `;

    loadCRM();
    loadPendingApprovals();
  } catch (err) {
    spinner.style.display = "none";
    output.innerHTML = `<p style="color: var(--danger);">Failed to process RFQ: ${err}</p>`;
  }
}

async function approveQuoteDirect(rfqId) {
  try {
    const res = await fetch('/api/approve-quote', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rfq_id: rfqId, action: 'approve' })
    });
    const data = await res.json();
    alert(`RFQ ${rfqId} has been approved and quote email dispatched to customer!`);
    loadPendingApprovals();
    loadCRM();
  } catch (err) {
    alert("Approval error: " + err);
  }
}

async function loadPendingApprovals() {
  const container = document.getElementById("pending-approvals-list");
  try {
    const res = await fetch('/api/tracking');
    const records = await res.json();
    const pending = records.filter(r => r.status === "Pending Approval");

    if (pending.length === 0) {
      container.innerHTML = `<p style="color: var(--success);"><i class="fa-solid fa-circle-check"></i> No quotes currently pending approval. All active RFQs are auto-approved!</p>`;
      return;
    }

    container.innerHTML = pending.map(rfq => `
      <div class="card" style="background: rgba(11,15,25,0.8); border: 1px solid var(--warning); margin-bottom: 1.5rem;">
        <h4 style="color: var(--warning); margin-bottom: 8px;">⚠️ High-Value / Exception Approval Required (${rfq.rfq_id})</h4>
        <p style="font-size: 0.9rem; margin-bottom: 6px;">Customer: <strong>${rfq.customer_name}</strong> (${rfq.contact_person})</p>
        <p style="font-size: 0.9rem; margin-bottom: 6px;">Quoted Amount: <strong style="color: var(--accent-cyan);">$${rfq.quote_total.toLocaleString('en-US', {minimumFractionDigits: 2})}</strong></p>
        <p style="font-size: 0.85rem; color: #ffca28; margin-bottom: 15px;">Reasons: ${rfq.approval_reasons.join(', ')}</p>

        <div style="display: flex; gap: 10px;">
          <button class="btn btn-success" onclick="approveQuoteDirect('${rfq.rfq_id}')"><i class="fa-solid fa-check"></i> Approve & Send Email</button>
        </div>
      </div>
    `).join('');
  } catch (err) {
    container.innerHTML = `<p style="color: var(--danger);">Failed to load approvals: ${err}</p>`;
  }
}

async function loadCRM() {
  const tbody = document.querySelector("#crm-table tbody");
  try {
    const res = await fetch('/api/tracking');
    const records = await res.json();

    tbody.innerHTML = records.map(rfq => {
      let badgeClass = 'badge-sent';
      if (rfq.status === 'Pending Approval') badgeClass = 'badge-pending';
      if (rfq.status === 'Awaiting Sales Call') badgeClass = 'badge-call';

      const sentDate = rfq.sent_date ? rfq.sent_date.split('T')[0] : 'N/A';

      return `
        <tr>
          <td><strong>${rfq.rfq_id}</strong></td>
          <td>${rfq.customer_name}<br><small style="color: var(--text-muted);">${rfq.contact_email}</small></td>
          <td><strong>$${rfq.quote_total.toLocaleString('en-US', {minimumFractionDigits: 2})}</strong></td>
          <td><span class="badge ${badgeClass}">${rfq.status}</span></td>
          <td>${sentDate}</td>
          <td>${rfq.next_followup_date || 'N/A'}</td>
          <td>${rfq.followup_count || 0} / 3</td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error("Error loading CRM:", err);
  }
}

async function runFollowUpEngine() {
  try {
    const res = await fetch('/api/run-followups', { method: 'POST' });
    const data = await res.json();
    alert(`Automated Follow-up Scan Complete!\nProcessed: ${data.processed_count} quotes.`);
    loadCRM();
  } catch (err) {
    alert("Follow-up error: " + err);
  }
}

async function loadCatalog() {
  const tbody = document.querySelector("#catalog-table tbody");
  try {
    const res = await fetch('/api/catalog');
    const catalog = await res.json();

    tbody.innerHTML = catalog.map(item => `
      <tr>
        <td><code>${item.sku}</code></td>
        <td><strong>${item.name}</strong><br><small style="color: var(--text-muted);">${item.description}</small></td>
        <td>${item.category}</td>
        <td><strong>$${item.price.toFixed(2)}</strong></td>
        <td>${item.stock} units</td>
        <td>${item.lead_time_days} days</td>
      </tr>
    `).join('');
  } catch (err) {
    console.error("Error loading catalog:", err);
  }
}

async function triggerErrorTest(type) {
  const output = document.getElementById("error-test-output");
  try {
    const res = await fetch('/api/trigger-error', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ error_type: type })
    });
    const data = await res.json();

    const steps = data.recovery_steps.map(s => `<li>${s}</li>`).join('');

    output.innerHTML = `
      <div style="background: rgba(11,15,25,0.9); border: 1px solid var(--accent-cyan); padding: 1.25rem; border-radius: 8px;">
        <h4 style="color: var(--accent-cyan); margin-bottom: 6px;"><i class="fa-solid fa-shield-halved"></i> ${data.title}</h4>
        <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 10px;"><strong>Mechanism:</strong> ${data.mechanism}</p>
        <p style="font-size: 0.85rem; font-weight: bold; margin-bottom: 6px;">Automated Recovery Steps Log:</p>
        <ul style="padding-left: 20px; font-size: 0.85rem; color: var(--success);">${steps}</ul>
      </div>
    `;
  } catch (err) {
    output.innerHTML = `<p style="color: var(--danger);">Test failed: ${err}</p>`;
  }
}
