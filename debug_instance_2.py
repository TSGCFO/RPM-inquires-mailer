#!/usr/bin/env python3
"""Debug script for Instance 2 issues"""

import os
import requests
import json

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

def test_graph_token():
    """Test Microsoft Graph token acquisition for Instance 2"""
    tenant_id = os.getenv("TENANT_ID_2")
    client_id = os.getenv("CLIENT_ID_2")
    client_secret = os.getenv("CLIENT_SECRET_2")
    
    print(f"Testing Instance 2 Graph token...")
    print(f"Tenant ID: {tenant_id}")
    print(f"Client ID: {client_id}")
    print(f"Client Secret: {'*' * len(client_secret) if client_secret else 'MISSING'}")
    
    if not all([tenant_id, client_id, client_secret]):
        print("❌ Missing Instance 2 Graph credentials")
        return None
        
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    
    try:
        resp = requests.post(
            token_url,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
            timeout=15,
        )
        
        print(f"Token response status: {resp.status_code}")
        
        if resp.status_code == 200:
            body = resp.json()
            print("✅ Token acquired successfully")
            return body["access_token"]
        else:
            print(f"❌ Token request failed: {resp.text}")
            return None
            
    except Exception as e:
        print(f"❌ Token request exception: {e}")
        return None

def test_send_email(token):
    """Test sending email with Instance 2 configuration"""
    if not token:
        print("❌ No token available for email test")
        return
        
    from_email = os.getenv("FROM_EMAIL_2")
    to_email = os.getenv("TO_EMAIL_2")
    
    print(f"\nTesting email sending...")
    print(f"From: {from_email}")
    print(f"To: {to_email}")
    
    if not all([from_email, to_email]):
        print("❌ Missing Instance 2 email configuration")
        return
        
    sendmail_url = f"https://graph.microsoft.com/v1.0/users/{from_email}/sendMail"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "message": {
            "subject": "🧪 Test Email from Instance 2",
            "body": {
                "contentType": "Text", 
                "content": "This is a test email from Instance 2 debugging script."
            },
            "toRecipients": [{"emailAddress": {"address": to_email}}],
        },
        "saveToSentItems": "false",
    }
    
    try:
        print(f"Sending to Graph URL: {sendmail_url}")
        response = requests.post(sendmail_url, headers=headers, json=payload, timeout=15)
        
        print(f"Email response status: {response.status_code}")
        
        if response.status_code == 202:
            print("✅ Test email sent successfully!")
        else:
            print(f"❌ Email sending failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Email sending exception: {e}")

if __name__ == "__main__":
    print("=== Instance 2 Debug Script ===")
    token = test_graph_token()
    test_send_email(token)