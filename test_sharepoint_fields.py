"""
Diagnostic: Validate AI output fields against SharePoint column requirements.
Simulates exactly what the Logic App does before the Create_SharePoint_RFQ_Item action.
"""
import requests, json

endpoint = 'https://oai-rfq-automation-01.openai.azure.com/openai/deployments/gpt-5/chat/completions?api-version=2024-02-01'
headers = {
    'api-key': 'YOUR_AZURE_OPENAI_KEY_HERE',
    'Content-Type': 'application/json'
}

# ---- Updated prompt (matches arm_template_logic_app.json) ----
prompt = """You are an AI assistant that processes Requests for Quotation (RFQ). Your ONLY output must be a valid JSON object. Do NOT output any plain text, markdown, or explanation outside the JSON.

STEP 1 - CLASSIFY: Determine if the email is a genuine RFQ or spam/newsletter. Set is_rfq accordingly.

STEP 2 - EXTRACT: Extract customer_name, contact_email, confidence_score (0.0 to 1.0), and reasoning. If a value is unknown, use an empty string "" instead of null. Do NOT include newline characters (\\n) in any string values.

STEP 3 - MATCH ITEMS: Use this catalog to match requested items and calculate prices:
- SKU: VALVE-SS-2IN | Industrial Valve 2-inch Stainless | $120.00 | 7 Business Days
- SKU: SENSOR-PRESS-DIG | High-Pressure Digital Sensor | $350.00 | 14 Business Days
- SKU: FLOW-MTR-EM-4IN | Flow Meter Electromagnetic 4-inch | $850.00 | 21 Business Days
- SKU: PUMP-CENT-5HP | Centrifugal Pump 5HP | $1,450.00 | 28 Business Days
- SKU: GSKT-FLG-2IN | Flange Gasket Kit 2-inch | $25.00 | 7 Business Days
For unmatched items: unit_price = 0, lead_time = TBD.

STEP 4 - BUILD HTML EMAIL: Set draft_email_html to a single-line HTML string (no newlines). Fill in the customer name, today's date, line item rows, and grand total.

RETURN this exact JSON structure:
{"is_rfq": boolean, "customer_name": string, "contact_email": string, "confidence_score": number, "reasoning": string, "quote_total": number, "draft_email_html": string, "line_items": [{"sku": string, "name": string, "quantity": integer, "unit_price": number, "line_total": number, "lead_time": string}]}"""

# ---- Realistic vague customer email (no SKUs) ----
email = """
Hi Sales Team,

I hope this email finds you well. We are doing some maintenance on our main water line and 
need to order replacement parts urgently. Could you please send a quote for the following:

- 12x stainless steel 2-inch valves
- 1x 5 horsepower centrifugal pump
- 20x gasket kits (2-inch flanged connections)

Please include your best price and estimated delivery time to Bulawayo.

Thanks,
Michael Banda
Maintenance Supervisor, Delta Manufacturing Ltd.
m.banda@deltamanufacturing.co.zw | +263 77 987 6543
"""

payload = {
    'messages': [
        {'role': 'system', 'content': prompt},
        {'role': 'user', 'content': email}
    ],
    'response_format': {'type': 'json_object'}
}

print("=" * 65)
print("STEP 1: Calling Azure OpenAI GPT-5...")
print("=" * 65)

r = requests.post(endpoint, headers=headers, json=payload)
print(f"HTTP Status: {r.status_code}")
if r.status_code != 200:
    print("ERROR - API call failed:", r.text)
    exit(1)

raw = r.json()['choices'][0]['message']['content']
parsed = json.loads(raw)

print("\nSTEP 2: AI Output Summary")
print("-" * 65)
print(f"  is_rfq          : {parsed.get('is_rfq')}")
print(f"  confidence_score: {parsed.get('confidence_score')}")
print(f"  customer_name   : {repr(parsed.get('customer_name'))}")
print(f"  contact_email   : {repr(parsed.get('contact_email'))}")
print(f"  quote_total     : {parsed.get('quote_total')}")
print(f"  line_items count: {len(parsed.get('line_items', []))}")

print("\nSTEP 3: Line Items Extracted")
print("-" * 65)
for i, item in enumerate(parsed.get('line_items', []), 1):
    print(f"  Item {i}: {item.get('name')} | SKU: {item.get('sku')} | Qty: {item.get('quantity')} | Unit: ${item.get('unit_price')} | Total: ${item.get('line_total')} | Lead: {item.get('lead_time')}")

# ---- SHAREPOINT FIELD VALIDATION ----
print("\nSTEP 4: SharePoint Field Validation")
print("-" * 65)

CONFIDENCE_THRESHOLD = 0.85
is_rfq = parsed.get('is_rfq', False)
confidence = parsed.get('confidence_score', 0)

print(f"  is_rfq = {is_rfq}, confidence = {confidence}")
print(f"  Condition (is_rfq=True AND confidence >= {CONFIDENCE_THRESHOLD}): ", end="")

if is_rfq and confidence >= CONFIDENCE_THRESHOLD:
    print("✅ PASSES — SharePoint write will be attempted")
else:
    print("❌ FAILS — Logic App goes to ELSE branch (sends alert email, skips SharePoint)")
    if not is_rfq:
        print("  REASON: AI classified this as NOT an RFQ")
    if confidence < CONFIDENCE_THRESHOLD:
        print(f"  REASON: confidence_score {confidence} is below threshold {CONFIDENCE_THRESHOLD}")
    exit(0)

print("\nSTEP 5: Validating each SharePoint field per line item")
print("-" * 65)
errors = []
for i, item in enumerate(parsed.get('line_items', []), 1):
    title = item.get('name', '')
    customer_name = parsed.get('customer_name', '')
    contact_email = parsed.get('contact_email', '')
    confidence_val = parsed.get('confidence_score', 0)
    quote_total = parsed.get('quote_total', 0)

    item_errors = []

    # SharePoint "Title" (Single line of text): max 255 chars, no newlines
    if not title:
        item_errors.append("Title (name) is EMPTY — SharePoint will reject (required field)")
    elif len(title) > 255:
        item_errors.append(f"Title too long: {len(title)} chars (max 255)")
    elif '\n' in title or '\r' in title:
        item_errors.append(f"Title contains newline characters — SharePoint will reject")

    # CustomerName (Single line of text)
    if customer_name is None:
        item_errors.append("CustomerName is NULL — may cause SP write failure if column is required")

    # ContactEmail
    if contact_email is None:
        item_errors.append("ContactEmail is NULL")

    # AIConfidenceScore (Number column)
    if not isinstance(confidence_val, (int, float)):
        item_errors.append(f"AIConfidenceScore is type {type(confidence_val).__name__}, expected number")

    # QuoteTotal (Number column)
    if not isinstance(quote_total, (int, float)):
        item_errors.append(f"QuoteTotal is type {type(quote_total).__name__}, expected number")

    status = "✅ OK" if not item_errors else "❌ ERRORS"
    print(f"\n  Item {i}: {repr(title)} — {status}")
    for e in item_errors:
        print(f"    ⚠️  {e}")
        errors.append(e)

print("\n" + "=" * 65)
if errors:
    print(f"❌ VALIDATION FAILED — {len(errors)} error(s) found. SharePoint write would fail.")
else:
    print("✅ ALL FIELDS VALID — Logic App should write to SharePoint successfully.")
    print("\nSimulated SharePoint payload per line item:")
    for i, item in enumerate(parsed.get('line_items', []), 1):
        sp_payload = {
            "Title": item.get('name'),
            "CustomerName": parsed.get('customer_name'),
            "ContactEmail": parsed.get('contact_email'),
            "AIConfidenceScore": parsed.get('confidence_score'),
            "QuoteTotal": parsed.get('quote_total')
        }
        print(f"  Row {i}: {json.dumps(sp_payload)}")
print("=" * 65)
