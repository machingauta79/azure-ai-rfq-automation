"""
Test script to send sample RFQ requests and verify Quotation Retrieval.
Run while app.py is running or standalone.
"""
import requests
import json

SERVER_URL = "http://localhost:5000/api/process-rfq"

# Sample Request 1: Standard Catalog Items
sample_request_1 = {
    "sender_name": "Tinashe Moyo",
    "sender_email": "tinashe.moyo@vsozim.co.zw",
    "company": "VSO Zimbabwe Engineering Services",
    "phone": "+263 77 123 4567",
    "subject": "Urgent RFQ - Flow Meters and Centrifugal Pumps for VSO Zimbabwe Project",
    "attachment_name": "None",
    "body": """Dear Sales Team,

Please send us a formal quotation for the following items for our upcoming water infrastructure project in Harare:

1. 4 units of Flow Meter Electromagnetic 4-inch (SKU: FLOW-MTR-EM-4IN)
2. 2 units of Centrifugal Pump 5HP (SKU: PUMP-CENT-5HP)
3. 15 units of Flange Gasket Kit 2-inch (SKU: GSKT-FLG-2IN)

Please include delivery lead times and payment terms in the quotation.

Kind regards,

Tinashe Moyo
Procurement Specialist
VSO Zimbabwe Engineering Services"""
}

# Sample Request 2: Industrial Valves & Digital Sensors
sample_request_2 = {
    "sender_name": "Kudzai Chiwenga",
    "sender_email": "k.chiwenga@industrial.co.zw",
    "company": "Chiwenga Industrial Supplies",
    "phone": "+263 71 987 6543",
    "subject": "Quotation Request: Industrial Valves and Pressure Sensors",
    "attachment_name": "None",
    "body": """Hi Commercial Sales Team,

Could you please quote on the following equipment:

- 6x Industrial Valve 2-inch Stainless (SKU: VALVE-SS-2IN)
- 4x High-Pressure Digital Sensor (SKU: SENSOR-PRESS-DIG)

We need these delivered within 30 days if possible. Please send through the pricing and estimated lead times.

Thanks & Regards,

Kudzai Chiwenga
Operations Manager"""
}

def send_rfq_http(payload):
    print("=" * 60)
    print("Sending RFQ Request:", payload['subject'])
    print("From:", payload['sender_name'], f"<{payload['sender_email']}>")
    print("=" * 60)
    try:
        response = requests.post(
            SERVER_URL,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=10
        )
        print(f"Status Code: {response.status_code}")
        data = response.json()
        display_results(data)
    except requests.exceptions.ConnectionError:
        print("Flask server is not currently running on http://localhost:5000.")
        print("Falling back to internal Flask test client to evaluate request...\n")
        import app
        with app.app.test_client() as client:
            res = client.post('/api/process-rfq', json=payload)
            print(f"Internal Test Client Status: {res.status_code}")
            display_results(res.get_json())

def display_results(data):
    if data.get("status") == "success":
        rfq = data["rfq_record"]
        print(f"\n QUOTE RETRIEVED SUCCESSFULLY!")
        print(f"   RFQ Tracking ID  : {rfq['rfq_id']}")
        print(f"   Customer         : {rfq['customer_name']} ({rfq['contact_person']})")
        print(f"   Confidence Score : {rfq['confidence_score'] * 100:.0f}%")
        print(f"   Status           : {rfq['status']}")
        print(f"   Requires Approval: {rfq['requires_approval']}")
        if rfq.get('approval_reasons'):
            print(f"   Approval Reasons : {', '.join(rfq['approval_reasons'])}")
        print("\n--- Line Items Retrieved from Catalog ---")
        for item in rfq["items"]:
            match_icon = "[OK]" if item["matched"] else "[--]"
            print(f"   {match_icon} {item['sku']} | {item['name']:<35} | Qty: {item['qty']:<3} | Unit: ${item['unit_price']:>7.2f} | Total: ${item['line_total']:>8.2f} | Lead Time: {item['lead_time']}")
        print("-" * 60)
        print(f"   GRAND TOTAL QUOTE : ${rfq['quote_total']:,.2f} USD")
        print("=" * 60)
    else:
        print("Error retrieving quote:", json.dumps(data, indent=2))

if __name__ == "__main__":
    send_rfq_http(sample_request_1)
    print("\n\n")
    send_rfq_http(sample_request_2)
