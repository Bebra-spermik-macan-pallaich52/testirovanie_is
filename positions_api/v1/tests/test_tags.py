from http import HTTPStatus

def test_get_tags_list(api_client):
    resp = api_client.get("/Tags")
    assert resp.status_code == HTTPStatus.OK
    assert isinstance(resp.json(), list)
