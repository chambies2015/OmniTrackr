from fastapi.testclient import TestClient
from app.main import app
import os
import re

client = TestClient(app)

def test_ads_txt():
    print("Testing /ads.txt endpoint...")
    response = client.get("/ads.txt")
    
    if response.status_code == 200:
        print("✅ SUCCESS: Status Code is 200")
        lines = response.text.split('\n')
        found_google = False
        for line in lines:
            if re.search(r'(^|[\s,])google\.com([\s,]|$)', line):
                found_google = True
                break
        if found_google:
            print("✅ SUCCESS: Content contains 'google.com' as a valid domain")
            print("Response text content snippet:", response.text[:50])
        else:
             print("❌ FAILURE: Content does NOT contain 'google.com'")
             print("Response text:", response.text)
    else:
        print(f"❌ FAILURE: Status Code is {response.status_code}")
        print("Response text:", response.text)

if __name__ == "__main__":
    test_ads_txt()
