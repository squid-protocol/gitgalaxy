# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
import os
import logging
import stripe
import requests
from flask import Flask, send_from_directory, jsonify, request
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- 1. SECURE CREDENTIALS LOAD ---
load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
PRINTIFY_TOKEN = os.getenv("PRINTIFY_TOKEN")
PRINTIFY_SHOP_ID = os.getenv("PRINTIFY_SHOP_ID")

# --- 2. PRINTIFY SIZING MAP ---
PRINTIFY_MAP = {
    "5400x3600": {
        "name": "18x12 Poster",
        "product_id": "69bd522e9642b56c490e5fe5",
        "variant_id": 43166,
        "price": 2500,  # $25.00 USD
    },
    "7200x5400": {
        "name": "24x18 Poster",
        "product_id": "69bd522e9642b56c490e5fe5",
        "variant_id": 43172,
        "price": 3500,  # $35.00 USD
    },
    "9000x6000": {
        "name": "30x20 Poster",
        "product_id": "69bd522e9642b56c490e5fe5",
        "variant_id": 43175,
        "price": 4500,  # $45.00 USD
    },
}

# --- 3. CORE CONFIGURATION & FAILSAFE LOGGING ---
app = Flask(__name__, static_folder=".", static_url_path="")

# Standard console logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# DEAD-LETTER LOGGING: Save critical dropped orders to a dedicated file
file_handler = logging.FileHandler("gitgalaxy_dropped_orders.log")
file_handler.setLevel(logging.ERROR)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)
logger.addHandler(file_handler)

# Pull the path from the .env file. Fallback directly to your new museum folder!
BACKEND_DATA_PATH = os.getenv(
    "GALAXY_DATA_PATH", "/srv/storage_16tb/projects/gitgalaxy/museum"
)
os.makedirs(BACKEND_DATA_PATH, exist_ok=True)


# --- 4. ROBUST API SESSION HELPER ---
def get_printify_session():
    """
    Creates an HTTP session that automatically retries failed Printify requests.
    It will try 3 times, waiting 1s, 2s, and 4s between attempts to absorb API hiccups.
    """
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],  # Only retry on actual server crashes
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.headers.update(
        {
            "Authorization": f"Bearer {PRINTIFY_TOKEN}",
            "Content-Type": "application/json",
        }
    )
    return session


# --- 5. EXISTING API & FILE SERVING ---
@app.route("/api/list_galaxies")
def list_galaxies():
    try:
        # 🚨 THE FIX: Read the actual manifest.json instead of globbing the folder
        manifest_path = os.path.join(BACKEND_DATA_PATH, "manifest.json")
        import json

        with open(manifest_path, "r") as f:
            manifest_data = json.load(f)
        return jsonify(manifest_data)
    except Exception as e:
        logger.error(f"Discovery Error (Manifest likely missing): {str(e)}")
        return jsonify([]), 500


@app.route("/")
def serve_index():
    return send_from_directory(".", "index.html")


# 🚨 THE FIX: Add the new /museum/ route to match your manifest
@app.route("/museum/<path:path>")
def serve_museum_data(path):
    return send_from_directory(BACKEND_DATA_PATH, path)


# (Optional) Keep the old backend route just in case anything legacy needs it
@app.route("/backend/<path:path>")
def serve_data(path):
    return send_from_directory(BACKEND_DATA_PATH, path)


@app.route("/<path:path>")
def serve_assets(path):
    return send_from_directory(".", path)


# --- 6. COMMERCE ENDPOINTS ---


@app.route("/api/create-checkout-session", methods=["POST"])
def create_checkout_session():
    try:
        data = request.json
        poster_size = data.get("size", "5400x3600")
        mapped_item = PRINTIFY_MAP.get(poster_size, PRINTIFY_MAP["5400x3600"])

        image_data_url = data.get("image")
        if not image_data_url:
            return jsonify(error="No image data provided from frontend"), 400

        if "," in image_data_url:
            base64_str = image_data_url.split(",")[1]
        else:
            base64_str = image_data_url

        logger.info(
            "Uploading custom high-res image to Printify. This may take a few seconds..."
        )

        # Use our robust session to upload the image!
        printify = get_printify_session()
        upload_url = "https://api.printify.com/v1/uploads/images.json"
        upload_payload = {
            "file_name": f"gitgalaxy_custom_{poster_size}.jpg",
            "contents": base64_str,
        }

        # If Printify glitches during checkout, it will auto-retry up to 3 times
        upload_res = printify.post(upload_url, json=upload_payload, timeout=25)
        upload_res.raise_for_status()

        image_id = upload_res.json().get("id")
        logger.info(f"Image successfully uploaded! Printify Image ID: {image_id}")

        # Generate Stripe Session
        # Generate Stripe Session
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": f"GitGalaxy Custom Print ({mapped_item['name']})"
                        },
                        "unit_amount": mapped_item["price"],
                    },
                    "quantity": 1,  # 👈 This is the default starting amount
                    # 👇 NEW: Let Stripe handle the quantity UI!
                    "adjustable_quantity": {
                        "enabled": True,
                        "minimum": 1,
                        "maximum": 50,  # Cap it so someone doesn't accidentally buy 9,000 posters
                    },
                }
            ],
            mode="payment",
            shipping_address_collection={"allowed_countries": ["US", "CA", "GB"]},
            success_url=request.host_url + "?order=success",
            cancel_url=request.host_url,
            metadata={"poster_size": poster_size, "image_id": image_id},
            custom_text={
                "submit": {
                    "message": "**Order Policies:**\n• **Returns:** Custom prints are final sale. However, if your poster arrives damaged or misprinted, we will issue a free replacement.\n• **Privacy:** Your repository data is rendered locally and never stored on our servers. We only share your shipping address and your image with our print partner for your order."
                }
            },
        )
        return jsonify({"id": session.id, "url": session.url})

    except requests.exceptions.RequestException as e:
        logger.error(f"Printify Upload Failed: {str(e)}")
        return jsonify(error="Image upload failed. Please try again."), 500
    except Exception as e:
        # Keep the raw error in YOUR logs, but give the user a sanitized message
        logger.error(f"Stripe Session Error: {str(e)}")
        return (
            jsonify(
                error="An internal payment processing error occurred. Please contact support."
            ),
            500,
        )


@app.route("/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return "Invalid payload", 400
    except stripe.error.SignatureVerificationError:
        return "Invalid signature", 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        logger.info(
            "Webhook caught checkout.session.completed! Processing Printify order..."
        )

        # Safely extract data
        shipping = (
            session.get("shipping_details") or session.get("customer_details") or {}
        )
        address = shipping.get("address") or {}
        metadata = session.get("metadata") or {}

        poster_size = metadata.get("poster_size", "5400x3600")
        image_id = metadata.get("image_id")

        first_name = (
            shipping.get("name", "Valued").split()[0]
            if shipping.get("name")
            else "Valued"
        )
        last_name = (
            " ".join(shipping.get("name", "Customer").split()[1:])
            if len(shipping.get("name", " ").split()) > 1
            else "Customer"
        )

        line1 = address.get("line1") or "123 Test Street"
        city = address.get("city") or "San Francisco"
        state = address.get("state") or "CA"
        country = address.get("country") or "US"
        zip_code = address.get("postal_code") or "94105"

        # 👇 NEW: Ask Stripe exactly how many posters they ended up buying
        line_items = stripe.checkout.Session.list_line_items(session.get("id"))
        final_quantity = line_items.data[0].quantity if line_items.data else 1

        printify_item = PRINTIFY_MAP.get(poster_size, PRINTIFY_MAP["5400x3600"])
        master_product_id = printify_item["product_id"]
        target_variant_id = printify_item["variant_id"]

        printify = get_printify_session()

        try:
            # --- PHASE 1: FETCH MASTER BLUEPRINT DNA ---
            get_url = f"https://api.printify.com/v1/shops/{PRINTIFY_SHOP_ID}/products/{master_product_id}.json"
            master_res = printify.get(get_url, timeout=15)
            master_res.raise_for_status()  # If this fails, it jumps straight to the except block

            master_data = master_res.json()

            # --- PHASE 2: CLONE A CUSTOM PRODUCT ---
            new_product_payload = {
                "title": f"GitGalaxy Custom Print - {first_name} {last_name}",
                "description": "Custom GitGalaxy Visualization",
                "blueprint_id": master_data.get("blueprint_id"),
                "print_provider_id": master_data.get("print_provider_id"),
                "variants": [
                    {
                        "id": target_variant_id,
                        "price": printify_item["price"],
                        "is_enabled": True,
                    }
                ],  # 👈 DYNAMIC PRICE APPLIED HERE
                "print_areas": [
                    {
                        "variant_ids": [target_variant_id],
                        "placeholders": [
                            {
                                "position": "front",
                                "images": [
                                    {
                                        "id": image_id,
                                        "x": 0.5,
                                        "y": 0.5,
                                        "scale": 1,
                                        "angle": 0,
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }

            create_url = (
                f"https://api.printify.com/v1/shops/{PRINTIFY_SHOP_ID}/products.json"
            )
            create_res = printify.post(create_url, json=new_product_payload, timeout=20)
            create_res.raise_for_status()

            new_product_id = create_res.json().get("id")
            logger.info(f"Successfully generated custom Product ID: {new_product_id}")

            # --- PHASE 3: PLACE THE ORDER ---
            printify_order_url = (
                f"https://api.printify.com/v1/shops/{PRINTIFY_SHOP_ID}/orders.json"
            )
            order_data = {
                "external_id": session.get("id", "test_id"),
                # 👇 NEW: Pass the dynamic quantity to the printer!
                "line_items": [
                    {
                        "product_id": new_product_id,
                        "variant_id": target_variant_id,
                        "quantity": final_quantity,
                    }
                ],
                "shipping_method": 1,
                "send_shipping_notification": False,
                "address_to": {
                    "first_name": first_name,
                    "last_name": last_name,
                    "address1": line1,
                    "city": city,
                    "country": country,
                    "region": state,
                    "zip": zip_code,
                },
            }

            response = printify.post(printify_order_url, json=order_data, timeout=20)
            response.raise_for_status()

            logger.info(
                f"SUCCESS! Printify order created for Product {new_product_id} with Quantity {final_quantity}!"
            )

        except (requests.exceptions.RequestException, ValueError, Exception) as e:
            # ==========================================
            # 🚨 THE ULTIMATE FAILSAFE (DEAD-LETTER)
            # ==========================================
            # Printify is down, returned invalid JSON, or crashed. The customer paid, but the order failed.
            error_msg = f"CRITICAL DROP: Printify failed to process Stripe Session {session.get('id')}. Error: {str(e)}"

            # Logs to the special 'gitgalaxy_dropped_orders.log' file
            logger.error(error_msg)

            # TODO: Add Discord/Slack ping here (e.g., requests.post('DISCORD_WEBHOOK_URL', json={'content': error_msg}))

    # 4. ALWAYS return 200 to Stripe at the very end so it doesn't pause your webhook
    return jsonify({"status": "success"}), 200


# --- 5.5 ENTERPRISE LEAD CAPTURE (THE BUSINESS TRAP) ---
@app.route("/api/enterprise-lead", methods=["POST"])
def capture_enterprise_lead():
    try:
        data = request.json
        email = data.get("email", "").lower()
        company = data.get("company", "Unknown")
        use_case = data.get("use_case", "Unknown")
        codebase_size = data.get("codebase_size", "Unknown")

        # The Filter: Reject generic emails to ensure high-signal enterprise leads
        generic_domains = ["@gmail.com", "@yahoo.com", "@hotmail.com", "@outlook.com"]
        if any(domain in email for domain in generic_domains):
            return (
                jsonify(
                    error="Please provide a valid corporate email address for commercial licensing."
                ),
                400,
            )

        # SANITIZATION: Prevent CRLF Log Injection and Memory Exhaustion (Cap at 500 chars)
        safe_company = str(company)[:500].replace("\n", " ").replace("\r", "")
        safe_size = str(codebase_size)[:500].replace("\n", " ").replace("\r", "")
        safe_case = str(use_case)[:500].replace("\n", " ").replace("\r", "")
        safe_email = str(email)[:500].replace("\n", " ").replace("\r", "")

        # Log the massive lead safely
        lead_msg = f"🚨 ENTERPRISE LEAD CAPTURED: {safe_company} | Size: {safe_size} | Case: {safe_case} | Contact: {safe_email}"
        logger.critical(lead_msg)

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Lead captured. Our architecture team will be in touch shortly.",
                }
            ),
            200,
        )

    except Exception as e:
        safe_error = str(e).replace("\n", " ")
        logger.error(f"Lead Capture Error: {safe_error}")
        return (
            jsonify(
                error="Failed to submit inquiry. Please email commercial@gitgalaxy.io directly."
            ),
            500,
        )


if __name__ == "__main__":
    print("\n" + "═" * 50)
    print(" 🌌 GITGALAXY VISUALIZER: COMMAND CENTER ACTIVE")
    print(f" Source: {BACKEND_DATA_PATH}")
    print(" Access: http://localhost:5000")
    print("═" * 50 + "\n")

    # Securely load debug state from environment variables
    is_debug = os.getenv("FLASK_ENV", "production").lower() == "development"
    host = os.getenv("FLASK_HOST", "0.0.0.0" if is_debug else "127.0.0.1")
    app.run(debug=is_debug, host=host, port=5000, threaded=True)
