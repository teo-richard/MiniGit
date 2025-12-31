import pickle

def empty():
    empty_dict = {"additions":{}, "removals":[]}
    with open(".minigit/index", "wb") as f:
        pickle.dump(empty_dict, f)