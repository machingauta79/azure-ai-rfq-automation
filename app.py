import os
import json
import time
import datetime
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, static_folder='static', template_folder='templates')

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
CATALOG_PATH = os.path.join(DATA_DIR, 'catalog.json')
DATABASE_PATH = os.path.join(DATA_DIR, 'rfq_database.json')
CONFIG_PATH = os.path.join(DATA_DIR, 'config.json')

def load_json(filepath, default):
    if not os.path.exists(filepath):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(default, f, indent=2)
        return default
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception:
        return default

def save_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

# --- Sample Pre-loaded RFQs ---
SAMPLE_RFQS = {
    "sample_1": {
        "title": "Standard RFQ - Industrial Valves & Sensors",
        "sender_name": "Sarah Lin",
        "sender_email": "slin@apexengineering.com",
        "company": "Apex Engineering Corp",
        "phone": "+1-555-402-1188",
        "subject": "Request for Quotation - Project Alpha Valves & Transmitters",
        "body": """Hi Sales Team,

Could you please provide a quotation for the following items required for our plant expansion:

1. 10 units of 2-Inch Stainless Steel Ball Valve (SKU: VALVE-SS-2IN)
2. 5 units of Digital Pressure Transmitter 0-100 PSI (SKU: SENSOR-PRESS-100PSI)
3. 2 units of 4-Inch Carbon Steel Flanged Gate Valve (SKU: VALVE-CS-4IN)

We require delivery by September 15th. Please let us know standard lead times and pricing.

Best regards,
Sarah Lin
Procurement Manager | Apex Engineering Corp""",
        "attachment_name": "None (Email Body)"
    },
    "sample_2": {
        "title": "High-Value Order (Requires Approval >$10k)",
        "sender_name": "David Miller",
        "sender_email": "d.miller@horizonrefinery.io",
        "company": "Horizon Refinery Ltd",
        "phone": "+1-555-901-4433",
        "subject": "URGENT RFQ: Bulk Order for Piping Replacement",
        "body": """Dear Quotations Department,

We are submitting an RFQ for our upcoming maintenance shutdown.

Requested Quantities:
- 100 units of 2-Inch Stainless Steel Ball Valve (VALVE-SS-2IN)
- 50 units of 4-Inch Carbon Steel Flanged Gate Valve (VALVE-CS-4IN)
- 30 units of 2-Inch Seamless SS316 Pipe (10ft Length) (PIPE-SS316-2IN-10FT)

Please send formal quote ASAP.

Thanks,
David Miller
Horizon Refinery Ltd""",
        "attachment_name": "RFQ_B449_Horizon.pdf"
    },
    "sample_3": {
        "title": "Unlisted / Fuzzy SKU Match Scenario",
        "sender_name": "Marcus Vance",
        "sender_email": "marcus@vancetech.org",
        "company": "Vance Technical Solutions",
        "phone": "+1-555-883-9900",
        "subject": "Price Inquiry for Emergency Stop Switches and Valves",
        "body": """Hello Team,

Please quote us for:
- 15 pcs of Red Mushroom Push Button Emergency Stop 22mm
- 8 pcs of 3-inch Butterfly Valves Lug Type

Regards,
Marcus Vance""",
        "attachment_name": "None"
    },
    "sample_4": {
        "title": "Corrupt Attachment / Error Test Scenario",
        "sender_name": "Unknown Client",
        "sender_email": "unknown@corruptdomain.xyz",
        "company": "Unknown Entity",
        "phone": "N/A",
        "subject": "RFQ Document Attached",
        "body": "Please see attached encrypted file.",
        "attachment_name": "RFQ_Encrypted_Protected.pdf (CORRUPT)"
    }
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    if request.method == 'POST':
        cfg = request.json
        save_json(CONFIG_PATH, cfg)
        return jsonify({"status": "success", "message": "Configuration saved."})
    else:
        cfg = load_json(CONFIG_PATH, {
            "azure_openai_endpoint": "https://oai-rfq-automation-01.openai.azure.com/",
            "azure_openai_key": "YOUR_AZURE_OPENAI_KEY_HERE",
            "azure_openai_deployment": "gpt-5",
            "azure_doc_intel_endpoint": "",
            "azure_doc_intel_key": ""
        })
        return jsonify(cfg)

@app.route('/api/sample-rfqs', methods=['GET'])
def get_sample_rfqs():
    return jsonify(SAMPLE_RFQS)

@app.route('/api/catalog', methods=['GET', 'POST'])
def handle_catalog():
    if request.method == 'POST':
        new_catalog = request.json
        save_json(CATALOG_PATH, new_catalog)
        return jsonify({"status": "success", "message": "Catalog updated."})
    else:
        catalog = load_json(CATALOG_PATH, [])
        return jsonify(catalog)

@app.route('/api/process-rfq', methods=['POST'])
def process_rfq():
    data = request.json
    email_body = data.get("body", "")
    sender_name = data.get("sender_name", "Customer")
    sender_email = data.get("sender_email", "customer@example.com")
    company = data.get("company", "Client Corp")
    phone = data.get("phone", "N/A")
    attachment_name = data.get("attachment_name", "")

    # Check for corrupt attachment error scenario
    if "CORRUPT" in attachment_name.upper():
        return jsonify({
            "status": "error",
            "error_code": "CORRUPT_ATTACHMENT",
            "message": "File processing failed: Attached document is encrypted or unreadable.",
            "action_taken": "Routed to 'RFQ_Needs_Manual_Review' Outlook folder & alerted Sales team."
        }), 400

    catalog = load_json(CATALOG_PATH, [])
    config = load_json(CONFIG_PATH, {})

    extracted_items = []
    confidence_score = 0.98

    use_live_azure = bool(config.get("azure_openai_endpoint") and config.get("azure_openai_key"))

    if use_live_azure:
        try:
            endpoint = config["azure_openai_endpoint"].rstrip('/')
            key = config["azure_openai_key"]
            deployment = config.get("azure_openai_deployment", "gpt-5")
            
            headers = {
                "Content-Type": "application/json",
                "api-key": key
            }
            prompt = f"""Extract RFQ items from this email body into a JSON array of objects with keys: search_term, requested_sku, quantity.
Email Body:
{email_body}

Respond ONLY with valid JSON."""

            url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version=2024-02-01"
            payload = {
                "messages": [
                    {"role": "system", "content": "You are an AI assistant that extracts purchase quotation requests into JSON format."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "response_format": {"type": "json_object"}
            }
            res = requests.post(url, headers=headers, json=payload, timeout=15)
            if res.status_code == 200:
                result_json = res.json()["choices"][0]["message"]["content"]
                parsed_res = json.loads(result_json)
                extracted_items = parsed_res.get("items", parsed_res.get("line_items", []))
        except Exception as e:
            print("Azure OpenAI Live call failed, falling back to smart rules:", e)
            use_live_azure = False

    if not use_live_azure or not extracted_items:
        # Smart rule-based mock extractor
        text_lower = email_body.lower()
        for cat_item in catalog:
            sku = cat_item.get("sku") or cat_item.get("SKU") or ""
            name = cat_item.get("name") or cat_item.get("Title") or ""
            name_lower = name.lower()
            if sku.lower() in text_lower or any(word in text_lower for word in name_lower.split() if len(word) > 4):
                qty = 1
                for word in text_lower.split():
                    if word.isdigit():
                        q_val = int(word)
                        if 1 <= q_val <= 500:
                            qty = q_val
                            break
                extracted_items.append({
                    "requested_sku": sku,
                    "search_term": name,
                    "quantity": qty
                })
        
        seen_skus = set()
        clean_extracted = []
        for item in extracted_items:
            if item["requested_sku"] not in seen_skus:
                seen_skus.add(item["requested_sku"])
                clean_extracted.append(item)
        extracted_items = clean_extracted

    matched_items = []
    total_amount = 0.0
    unmatched_count = 0

    for ext_item in extracted_items:
        req_sku = ext_item.get("requested_sku", "").upper()
        search_term = ext_item.get("search_term", "").lower()
        qty = int(ext_item.get("quantity", 1))

        catalog_match = next((item for item in catalog if (item.get("sku") or item.get("SKU", "")).upper() == req_sku), None)

        if not catalog_match:
            catalog_match = next((item for item in catalog if any(w in (item.get("name") or item.get("Title", "")).lower() for w in search_term.split() if len(w) > 3)), None)

        if catalog_match:
            item_sku = catalog_match.get("sku") or catalog_match.get("SKU", "")
            item_name = catalog_match.get("name") or catalog_match.get("Title", "")
            unit_price = float(catalog_match.get("price") or catalog_match.get("UnitPrice", 0.0))
            lead_time = catalog_match.get("lead_time_days")
            if lead_time is not None:
                lead_str = f"{lead_time} Business Days"
            elif catalog_match.get("LeadTimeWeeks") is not None:
                lead_str = f"{catalog_match.get('LeadTimeWeeks')} Week(s)"
            else:
                lead_str = "Standard Delivery"

            line_total = round(unit_price * qty, 2)
            total_amount += line_total
            matched_items.append({
                "sku": item_sku,
                "name": item_name,
                "qty": qty,
                "unit_price": unit_price,
                "line_total": line_total,
                "matched": True,
                "lead_time": lead_str
            })
        else:
            unmatched_count += 1
            confidence_score = 0.75
            matched_items.append({
                "sku": req_sku or "UNLISTED-ITEM",
                "name": ext_item.get("search_term", "Custom Item Request"),
                "qty": qty,
                "unit_price": 0.0,
                "line_total": 0.0,
                "matched": False,
                "lead_time": "TBD"
            })

    total_amount = round(total_amount, 2)

    requires_approval = False
    approval_reasons = []

    if total_amount >= 10000.0:
        requires_approval = True
        approval_reasons.append("High Quote Value (>= $10,000.00)")
    if unmatched_count > 0:
        requires_approval = True
        approval_reasons.append(f"{unmatched_count} Unlisted/Unmatched SKU(s)")
    if confidence_score < 0.90:
        requires_approval = True
        approval_reasons.append("Low AI Extraction Confidence (< 90%)")

    status = "Pending Approval" if requires_approval else "Quote Sent"
    rfq_id = f"RFQ-2026-{int(time.time()) % 10000:04d}"

    item_rows = "".join([
        f"<tr><td>{item['name']} ({item['sku']})</td><td>{item['qty']}</td><td>${item['unit_price']:.2f}</td><td>${item['line_total']:.2f}</td><td>{item['lead_time']}</td></tr>"
        for item in matched_items
    ])

    draft_email_html = f"""<div style="font-family: Arial, sans-serif; padding: 15px; border: 1px solid #ddd; border-radius: 8px;">
<p>Dear {sender_name},</p>
<p>Thank you for reaching out to us regarding your request for quotation. Below is our formal pricing proposal for <strong>{company}</strong>:</p>
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
  <thead>
    <tr style="background: #0056b3; color: white;">
      <th>Item & SKU</th><th>Qty</th><th>Unit Price</th><th>Total Price</th><th>Lead Time</th>
    </tr>
  </thead>
  <tbody>
    {item_rows}
  </tbody>
</table>
<h3 style="text-align: right; color: #0056b3;">Total Quoted Amount: ${total_amount:,.2f} USD</h3>
<p>This quotation is valid for 30 days. Please reply directly to confirm your purchase order.</p>
<p>Best regards,<br><strong>Automated Quotations Team</strong></p>
</div>"""

    rfq_record = {
        "rfq_id": rfq_id,
        "customer_name": company,
        "contact_person": sender_name,
        "contact_email": sender_email,
        "contact_phone": phone,
        "quote_total": total_amount,
        "status": status,
        "sent_date": datetime.datetime.now().isoformat(),
        "next_followup_date": (datetime.datetime.now() + datetime.timedelta(days=3)).strftime("%Y-%m-%d"),
        "followup_count": 0,
        "confidence_score": confidence_score,
        "requires_approval": requires_approval,
        "approval_reasons": approval_reasons,
        "items": matched_items,
        "draft_email_html": draft_email_html
    }

    db = load_json(DATABASE_PATH, [])
    db.insert(0, rfq_record)
    save_json(DATABASE_PATH, db)

    return jsonify({
        "status": "success",
        "rfq_record": rfq_record,
        "used_live_azure": use_live_azure
    })

@app.route('/api/approve-quote', methods=['POST'])
def approve_quote():
    data = request.json
    rfq_id = data.get("rfq_id")
    action = data.get("action", "approve")

    db = load_json(DATABASE_PATH, [])
    record = next((r for r in db if r["rfq_id"] == rfq_id), None)

    if not record:
        return jsonify({"status": "error", "message": "RFQ Record not found"}), 404

    if action == "approve":
        record["status"] = "Quote Sent"
        record["approval_notes"] = "Approved by Sales Manager via Outlook / SharePoint"
    else:
        record["status"] = "Rejected"
        record["approval_notes"] = "Rejected by Sales Representative"

    save_json(DATABASE_PATH, db)
    return jsonify({"status": "success", "record": record})

@app.route('/api/tracking', methods=['GET'])
def get_tracking():
    db = load_json(DATABASE_PATH, [])
    return jsonify(db)

@app.route('/api/run-followups', methods=['POST'])
def run_followups():
    db = load_json(DATABASE_PATH, [])
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")

    processed_count = 0
    followup_logs = []

    for record in db:
        if record["status"] == "Quote Sent" and record.get("next_followup_date", "9999-12-31") <= today_str:
            record["followup_count"] = record.get("followup_count", 0) + 1
            new_next_date = (datetime.datetime.now() + datetime.timedelta(days=3)).strftime("%Y-%m-%d")
            record["next_followup_date"] = new_next_date

            if record["followup_count"] >= 3:
                record["status"] = "Awaiting Sales Call"
                note = f"Max 3 email follow-ups completed. Assigned phone call task to Sales Rep."
            else:
                note = f"Follow-up #{record['followup_count']} email sent to {record['contact_email']}."

            processed_count += 1
            followup_logs.append({
                "rfq_id": record["rfq_id"],
                "customer": record["customer_name"],
                "followup_num": record["followup_count"],
                "next_date": new_next_date,
                "note": note
            })

    save_json(DATABASE_PATH, db)
    return jsonify({
        "status": "success",
        "processed_count": processed_count,
        "logs": followup_logs
    })

@app.route('/api/trigger-error', methods=['POST'])
def trigger_error():
    error_type = request.json.get("error_type", "rate_limit")
    if error_type == "rate_limit":
        return jsonify({
            "status": "simulated_error",
            "error_code": 429,
            "title": "Azure OpenAI Rate Limit Exceeded (HTTP 429)",
            "mechanism": "Logic App Exponential Backoff Policy triggered.",
            "recovery_steps": [
                "Retrying Attempt #1 in 5 seconds...",
                "Retrying Attempt #2 in 15 seconds...",
                "Retrying Attempt #3 in 45 seconds... [SUCCESS]"
            ]
        })
    elif error_type == "bounce_back":
        return jsonify({
            "status": "simulated_error",
            "error_code": "NDR_BOUNCE",
            "title": "Exchange NDR Bounce-Back Received",
            "mechanism": "Outlook Exchange Non-Delivery Report Event",
            "recovery_steps": [
                "Updated CRM record status to 'Delivery Failed'",
                "Alerted Account Owner via Email: 'Please verify email address for Customer X'"
            ]
        })
    else:
        return jsonify({"status": "unknown_error"})

if __name__ == '__main__':
    print("Starting Azure AI RFQ Automation Server on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
