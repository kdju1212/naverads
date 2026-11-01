import copy

import pytest

from app.naver import NaverApiError, RealNaverClient


def client_with(monkeypatch, handler):
    client = RealNaverClient("api-key", "secret", "123")
    calls = []

    def request(method, path, **kwargs):
        calls.append((method, path, copy.deepcopy(kwargs)))
        return handler(method, path, kwargs)

    monkeypatch.setattr(client, "_req", request)
    return client, calls


def test_shopping_create_uses_list_api_and_returns_created_item(monkeypatch):
    client, calls = client_with(monkeypatch, lambda *_: [{"nccAdId": "nad-new"}])
    result = client.create_ad("grp-1", "SHOPPING_PRODUCT_AD", {}, None,
                              referenceKey="123456", adAttr={"bidAmt": 300, "useGroupBidAmt": False})
    assert result == {"nccAdId": "nad-new"}
    method, path, request = calls[0]
    assert (method, path, request["params"]) == ("POST", "/ncc/ads", {"isList": "true"})
    assert request["json"] == [{"nccAdgroupId": "grp-1", "type": "SHOPPING_PRODUCT_AD", "ad": {},
                                "userLock": True, "referenceKey": "123456",
                                "adAttr": {"bidAmt": 300, "useGroupBidAmt": False}}]


@pytest.mark.parametrize("response", [[], [{}], [{"resultStatus": {"code": 3830, "message": "invalid"}}],
                                      {"nccAdId": "unexpected"}, [{"nccAdId": "a"}, {"nccAdId": "b"}]])
def test_shopping_create_does_not_report_item_failure_as_success(monkeypatch, response):
    client, calls = client_with(monkeypatch, lambda *_: response)
    with pytest.raises(NaverApiError):
        client.create_ad("grp-1", "SHOPPING_PRODUCT_AD", {}, None, referenceKey="123456")
    assert len(calls) == 1  # 불확실한 쓰기를 자동으로 재시도하지 않는다.


def test_other_ad_creation_still_uses_single_object(monkeypatch):
    client, calls = client_with(monkeypatch, lambda *_: {"nccAdId": "nad-text"})
    client.create_ad("grp-1", "TEXT_45", {"headline": "제목"}, None)
    assert "params" not in calls[0][2]
    assert isinstance(calls[0][2]["json"], dict)


def test_shopping_bid_update_uses_official_fields_and_verifies_response(monkeypatch):
    ad = {"nccAdId": "nad-1", "type": "SHOPPING_PRODUCT_AD", "adAttr": {"bidAmt": 100, "useGroupBidAmt": False}}

    def handler(method, path, request):
        return copy.deepcopy(ad) if method == "GET" else {"adAttr": {"bidAmt": 500, "useGroupBidAmt": False}}

    client, calls = client_with(monkeypatch, handler)
    client.update("ad", "nad-1", "bid_amt", "500", expect="100")
    assert calls[1] == ("PUT", "/ncc/ads/nad-1", {"params": {"fields": "adAttr"},
                           "json": {"nccAdId": "nad-1", "type": "SHOPPING_PRODUCT_AD",
                                    "adAttr": {"bidAmt": 500, "useGroupBidAmt": False}}})


def test_bid_uses_readback_if_response_omits_adattr(monkeypatch):
    responses = iter([{"type": "SHOPPING_PRODUCT_AD", "adAttr": {"bidAmt": 100, "useGroupBidAmt": False}},
                      {"nccAdId": "nad-1"}, {"adAttr": {"bidAmt": 500, "useGroupBidAmt": False}}])
    client, calls = client_with(monkeypatch, lambda *_: next(responses))
    client.update("ad", "nad-1", "bid_amt", "500")
    assert [c[0] for c in calls] == ["GET", "PUT", "GET"]


def test_bid_rejects_other_ad_type_and_stale_scheduled_value(monkeypatch):
    for ad, expected in [({"type": "TEXT_45"}, None),
                         ({"type": "SHOPPING_PRODUCT_AD", "adAttr": {"bidAmt": 200, "useGroupBidAmt": False}}, "100")]:
        client, calls = client_with(monkeypatch, lambda *_, ad=ad: copy.deepcopy(ad))
        with pytest.raises(NaverApiError):
            client.update("ad", "nad-1", "bid_amt", "500", expect=expected)
        assert [c[0] for c in calls] == ["GET"]


def test_bid_refuses_unconfirmed_response_without_retrying_write(monkeypatch):
    old = {"type": "SHOPPING_PRODUCT_AD", "adAttr": {"bidAmt": 100, "useGroupBidAmt": False}}
    responses = iter([old, {"adAttr": {"bidAmt": 100, "useGroupBidAmt": False}}, copy.deepcopy(old)])  # 응답·재조회 모두 이전 값
    client, calls = client_with(monkeypatch, lambda *_: next(responses))
    with pytest.raises(NaverApiError, match="확인"):
        client.update("ad", "nad-1", "bid_amt", "500")
    assert [c[0] for c in calls] == ["GET", "PUT", "GET"]  # PUT은 한 번뿐


def test_bid_stale_response_but_readback_confirms(monkeypatch):
    responses = iter([{"type": "SHOPPING_PRODUCT_AD", "adAttr": '{"bidAmt": 100, "useGroupBidAmt": false}'},
                      {"adAttr": {"bidAmt": 100}}, {"adAttr": '{"bidAmt": "500", "useGroupBidAmt": false}'}])
    client, calls = client_with(monkeypatch, lambda *_: next(responses))
    client.update("ad", "nad-1", "bid_amt", "500", expect="100")  # adAttr가 JSON 문자열이어도 예약 비교·확인
    assert [c[0] for c in calls] == ["GET", "PUT", "GET"]


def test_scheduled_bid_skips_compare_when_ad_uses_group_bid(monkeypatch):
    responses = iter([{"type": "SHOPPING_PRODUCT_AD", "adAttr": {"useGroupBidAmt": True}},
                      {"adAttr": {"bidAmt": 500, "useGroupBidAmt": False}}])
    client, _ = client_with(monkeypatch, lambda *_: next(responses))
    client.update("ad", "nad-1", "bid_amt", "500", expect="300")


def test_shopping_create_network_error_is_reported_as_unknown(monkeypatch):
    def fail(*_):
        raise NaverApiError("네트워크 오류: timeout")
    client, calls = client_with(monkeypatch, fail)
    with pytest.raises(NaverApiError, match="알 수 없습니다"):
        client.create_ad("grp-1", "SHOPPING_PRODUCT_AD", {}, None, referenceKey="123456")
    assert len(calls) == 1
