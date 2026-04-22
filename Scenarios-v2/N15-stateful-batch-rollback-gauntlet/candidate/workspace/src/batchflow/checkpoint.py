def get_checkpoint(store, batch_id):
    return store.checkpoints.get("last", 0)


def set_checkpoint(store, batch_id, index):
    store.checkpoints["last"] = index
