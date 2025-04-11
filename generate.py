import secrets

def generate_key():
    key = secrets.token_hex(32)  # Generates a 64-character secure key
    print(f"Generated SECRET_KEY: {key}")

if __name__ == "__main__":
    generate_key()
