from pymongo import MongoClient, DESCENDING
from django.conf import settings
_client = None
def db():
    global _client
    if _client is None: _client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=1500)
    return _client[settings.MONGO_DB]
def products():
    try: return list(db().products.find().sort("updated", DESCENDING))
    except Exception: return []
def orders():
    try: return list(db().orders.find().sort("created", DESCENDING).limit(100))
    except Exception: return []
