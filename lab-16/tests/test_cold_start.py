import pytest
from reco.cold_start import scenario_new_doc, top_k_with_new_slot, tuned_params
from reco.data import load
from reco.recommender import Recommender


@pytest.fixture(scope="module")
def ds():
    return load()


def test_new_slot_puts_new_doc_in_top_k(ds):
    g, h = tuned_params()
    rec = Recommender(ds, g, None, h); new = set(ds.split["new_items"])
    u = sorted(ds.split["warm_eval_users"])[0]
    top = top_k_with_new_slot(rec, u, 5, "hybrid", ds.end[:10], new, 1)
    assert len(top) == 5 and len(set(top)) == 5 and set(top) & new


def test_new_doc_scenario_shape(ds):
    g, h = tuned_params()
    res = scenario_new_doc(ds, g, h)
    assert res["pop"]["exposure5"] == 0.0            # без взаємодій популярність не бачить нових документів
    assert res["hybrid+слот"]["exposure5"] == 1.0    # слот гарантує показ
    assert res["hybrid+слот"]["new_doc_recall5"] >= res["hybrid"]["new_doc_recall5"]


def test_cold_users_have_no_train_history(ds):
    train_users = {e["user_id"] for e in ds.train}
    assert not set(ds.split["cold_users"]) & train_users
