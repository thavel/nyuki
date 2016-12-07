async def index(collection, *args, **kwargs):
    """
    Helper to ensure_index in __init__
    """
    await collection.create_index(*args, **kwargs)
