import pandas as pd
from collections import defaultdict
from typing import Dict, Set
from typing import List, Tuple

#The add_fan_in_out function computes transaction-level graph degree features 
# by counting how many upstream and downstream transactions are directly connected to each transaction, 
# capturing aggregation and distribution behavior relevant to Bitcoin AML typologies.

def add_fan_in_out(df: pd.DataFrame, edges: pd.DataFrame) -> pd.DataFrame:
    out_deg = edges["txId1"].value_counts().rename("fan_out_1hop")
    in_deg  = edges["txId2"].value_counts().rename("fan_in_1hop")

    out = df.copy()
    out = out.merge(out_deg, left_on="txId", right_index=True, how="left")
    out = out.merge(in_deg,  left_on="txId", right_index=True, how="left")

    out["fan_out_1hop"] = out["fan_out_1hop"].fillna(0).astype(int)
    out["fan_in_1hop"]  = out["fan_in_1hop"].fillna(0).astype(int)
    return out


#_build_undirected_adj() constructs an undirected transaction graph where each transaction is mapped 
# to its immediate neighbors, enabling proximity-based AML risk features such as illicit neighborhood 
# exposure and layering detection.
def _build_undirected_adj(edges: pd.DataFrame) -> Dict[int, Set[int]]: 
    adj: Dict[int, Set[int]] = defaultdict(set)
    for a, b in zip(edges["txId1"].values, edges["txId2"].values):
        a = int(a); b = int(b)
        adj[a].add(b)
        adj[b].add(a)
    return adj


# add_illicit_exposure() computes graph-based AML exposure features that quantify 
# how strongly a transaction is connected to known illicit activity at one-hop and two-hop distances, 
# supporting typologies like layering and risk propagation.

def add_illicit_exposure(
    df: pd.DataFrame,
    edges: pd.DataFrame,
    class_col: str = "class_name",
    txid_col: str = "txId",
    compute_2hop: bool = True,
) -> pd.DataFrame:
    out = df.copy()

    # Only "illicit" is illicit
    illicit_set = set(out.loc[out[class_col] == "illicit", txid_col].astype(int).values)

    adj = _build_undirected_adj(edges)
    txids = out[txid_col].astype(int).values

    nbr_count_1 = []
    illicit_count_1 = []

    for t in txids:
        nbrs = adj.get(int(t), set())
        nbr_count_1.append(len(nbrs))
        illicit_count_1.append(sum((n in illicit_set) for n in nbrs))

    out["nbr_count_1hop"] = nbr_count_1
    out["illicit_nbr_count_1hop"] = illicit_count_1

    # IMPORTANT: keep NaN when denom=0 (not computable != 0 exposure)
    out["illicit_nbr_ratio_1hop"] = (
        out["illicit_nbr_count_1hop"] / out["nbr_count_1hop"].replace(0, pd.NA)
    ).astype("float")

    if not compute_2hop:
        return out

    nbr_count_2 = []
    illicit_count_2 = []

    for t in txids:
        t = int(t)
        nbrs1 = adj.get(t, set())
        nbrs2 = set()
        for n1 in nbrs1:
            nbrs2.update(adj.get(n1, set()))

        # strict 2-hop: exclude self + direct neighbors
        nbrs2.discard(t)
        nbrs2.difference_update(nbrs1)

        nbr_count_2.append(len(nbrs2))
        illicit_count_2.append(sum((n in illicit_set) for n in nbrs2))

    out["nbr_count_2hop_strict"] = nbr_count_2
    out["illicit_nbr_count_2hop_strict"] = illicit_count_2

    # IMPORTANT: keep NaN when denom=0 (not computable != 0 exposure)
    out["illicit_nbr_ratio_2hop_strict"] = (
        out["illicit_nbr_count_2hop_strict"] / out["nbr_count_2hop_strict"].replace(0, pd.NA)
    ).astype("float")

    return out


def get_top_illicit_neighbors_for_tx(
    txid: int,
    edges: pd.DataFrame,
    illicit_set: set,
    k: int = 5,
) -> Dict[str, List[int]]:
    """
    Returns top illicit neighbor IDs for:
      - 1-hop undirected neighbors
      - strict 2-hop undirected neighbors (exclude self and 1-hop)
    Note: "top" is currently by presence only (IDs), since Elliptic edges are unweighted.
    """
    adj = _build_undirected_adj(edges)

    txid = int(txid)
    nbrs1 = adj.get(txid, set())

    illicit_1hop = sorted([n for n in nbrs1 if n in illicit_set])[:k]

    # strict 2-hop
    nbrs2 = set()
    for n1 in nbrs1:
        nbrs2.update(adj.get(n1, set()))
    nbrs2.discard(txid)
    nbrs2.difference_update(nbrs1)

    illicit_2hop = sorted([n for n in nbrs2 if n in illicit_set])[:k]

    return {
        "top_illicit_neighbors_1hop": illicit_1hop,
        "top_illicit_neighbors_2hop_strict": illicit_2hop,
    }


def build_illicit_set(df: pd.DataFrame, txid_col: str = "txId", class_col: str = "class_name") -> set:
    """Convenience helper: txIds labeled illicit in Elliptic."""
    return set(df.loc[df[class_col] == "illicit", txid_col].astype(int).values)
