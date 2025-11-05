import sqlite3
import requests
import json

def check_db():
    print("Checking database...")
    try:
        conn = sqlite3.connect('emotions.db')
        c = conn.cursor()
        c.execute('SELECT name FROM sqlite_master WHERE type="table"')
        tables = c.fetchall()
        print(f"Tables: {tables}")
        for table in tables:
            table_name = table[0]
            c.execute(f'SELECT COUNT(*) FROM {table_name}')
            count = c.fetchone()[0]
            print(f"Records in {table_name} table: {count}")
            if count > 0:
                c.execute(f'SELECT * FROM {table_name} ORDER BY id DESC LIMIT 5')
                rows = c.fetchall()
                print(f"Sample records from {table_name} (latest 5):")
                for row in rows:
                    print(row)
            else:
                print(f"No records in {table_name} table.")
        conn.close()
    except Exception as e:
        print(f"Error checking DB: {e}")

def check_api():
    print("\nChecking API...")
    try:
        response = requests.get('http://localhost:5000/api/emotions', timeout=5)
        print(f"API Status: {response.status_code}")
        print(f"Server: {response.headers.get('Server')}")
        if response.status_code == 200:
            data = response.json()
            print(f"API Response: {data}")
        else:
            print(f"API Error: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"API Request failed: {e}")

def check_root():
    print("\nChecking root endpoint...")
    try:
        response = requests.get('http://localhost:5000/', timeout=5)
        print(f"Root Status: {response.status_code}")
        print(f"Server: {response.headers.get('Server')}")
        if response.status_code == 200:
            print("Root is working.")
        else:
            print(f"Root Error: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Root Request failed: {e}")

if __name__ == "__main__":
    check_db()
    check_root()
    check_api()
