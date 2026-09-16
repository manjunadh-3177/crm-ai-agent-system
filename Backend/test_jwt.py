import sys
try:
    import jwt
    from jwt import PyJWKClient
    print("PyJWT imported successfully")
except Exception as e:
    print("Error:", e)
