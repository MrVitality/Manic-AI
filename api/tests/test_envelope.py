"""Tests for the ApiResponse envelope helpers in api.schemas.envelope."""

from api.schemas.envelope import ApiResponse, ok, fail


class TestOkHelper:
    def test_basic_ok(self):
        result = ok({"key": "value"})
        assert result["success"] is True
        assert result["data"] == {"key": "value"}
        assert result["error"] is None
        assert result["meta"] is None

    def test_ok_with_meta(self):
        result = ok([1, 2, 3], meta={"total": 3, "page": 1})
        assert result["success"] is True
        assert result["data"] == [1, 2, 3]
        assert result["meta"]["total"] == 3

    def test_ok_no_data(self):
        result = ok()
        assert result["success"] is True
        assert result["data"] is None

    def test_ok_with_none_data(self):
        result = ok(None)
        assert result["success"] is True
        assert result["data"] is None


class TestFailHelper:
    def test_basic_fail(self):
        result = fail("Something went wrong")
        assert result["success"] is False
        assert result["data"] is None
        assert result["error"] == "Something went wrong"
        assert result["meta"] is None

    def test_fail_with_meta(self):
        result = fail("bad request", meta={"code": 400})
        assert result["success"] is False
        assert result["error"] == "bad request"
        assert result["meta"]["code"] == 400


class TestApiResponseModel:
    def test_success_model(self):
        resp = ApiResponse(success=True, data={"items": []})
        assert resp.success is True
        assert resp.data == {"items": []}
        assert resp.error is None

    def test_error_model(self):
        resp = ApiResponse(success=False, error="not found")
        assert resp.success is False
        assert resp.data is None
        assert resp.error == "not found"

    def test_serialization_roundtrip(self):
        resp = ApiResponse(success=True, data="hello", meta={"v": 1})
        d = resp.model_dump()
        assert d["success"] is True
        assert d["data"] == "hello"
        assert d["meta"] == {"v": 1}
