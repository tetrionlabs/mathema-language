# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""An OpenAPI operation is the language of the requests it accepts: a
record of its path, query, header and cookie parameters and its JSON
body, as one JSON Schema. References inline and a self-reference is
refused, OpenAPI 3.0's `nullable` admits null, a path parameter is always
required, and the method says whether the operation only reads, is
idempotent or destroys. Over two versions of a specification, widening
a bound is proven to keep every request valid, and a new required field
or a narrower bound is falsified with the request that breaks; the
encoding of a request never admits less than its language as the older
side or more as the newer."""
import copy
import random

import pytest

pytest.importorskip("jsonschema")

from mathema_language import openapi  # noqa: E402

V1 = {
    "openapi": "3.0.3",
    "info": {"title": "orders", "version": "1"},
    "components": {"schemas": {
        "NewOrder": {"type": "object", "required": ["sku", "quantity"],
                     "properties": {"sku": {"type": "string", "minLength": 1, "maxLength": 12,
                                            "example": "ABC-1"},
                                    "quantity": {"type": "integer", "minimum": 1, "maximum": 10},
                                    "note": {"type": "string", "nullable": True}}}}},
    "paths": {
        "/orders": {
            "post": {"operationId": "createOrder",
                     "requestBody": {"required": True, "content": {"application/json": {
                         "schema": {"$ref": "#/components/schemas/NewOrder"}}}}},
            "get": {"operationId": "listOrders",
                    "parameters": [
                        {"name": "limit", "in": "query",
                         "schema": {"type": "integer", "minimum": 1, "maximum": 100}},
                        {"name": "export", "in": "query", "schema": {"type": "string"}}]}},
        "/orders/{id}": {
            "parameters": [{"name": "id", "in": "path", "required": True,
                            "schema": {"type": "integer", "minimum": 1}}],
            "delete": {"operationId": "cancelOrder"}}},
}

WIDER = copy.deepcopy(V1)
WIDER["components"]["schemas"]["NewOrder"]["properties"]["quantity"]["maximum"] = 100
WIDER["paths"]["/orders"]["get"]["parameters"][0]["schema"]["maximum"] = 500

BREAKING = copy.deepcopy(V1)
BREAKING["components"]["schemas"]["NewOrder"]["required"].append("currency")
BREAKING["components"]["schemas"]["NewOrder"]["properties"]["currency"] = {
    "type": "string", "enum": ["EUR", "USD"]}
BREAKING["paths"]["/orders"]["get"]["parameters"][0]["schema"]["maximum"] = 50


def test_every_operation_is_found_with_what_its_method_says():
    assert openapi.operation_ids(V1) == ["listOrders", "createOrder", "cancelOrder"]
    listing, cancel = openapi.operation(V1, "listOrders"), openapi.operation(V1, "cancelOrder")
    assert (listing.method, listing.read_only, listing.destructive) == ("get", True, False)
    assert (cancel.method, cancel.idempotent, cancel.destructive) == ("delete", True, True)
    assert not openapi.operation(V1, "createOrder").idempotent


def test_a_request_is_a_record_of_its_parameters_by_place_and_its_body():
    schema = openapi.request_schema(V1, "cancelOrder")
    assert schema["required"] == ["path"] and schema["properties"]["path"]["required"] == ["id"]
    body = openapi.request_schema(V1, "createOrder")["properties"]["body"]
    assert body["properties"]["note"]["type"] == ["string", "null"]
    language = openapi.operation(V1, "createOrder").language
    assert language.contains({"body": {"sku": "A", "quantity": 3, "note": None}})
    assert not language.contains({"body": {"sku": "A", "quantity": 11}})
    assert not language.contains({})
    rng = random.Random(0)
    assert all(language.contains(language.sample(rng)) for _ in range(30))


def test_a_reference_to_itself_or_outside_is_refused():
    looping = copy.deepcopy(V1)
    looping["components"]["schemas"]["NewOrder"]["properties"]["parent"] = {
        "$ref": "#/components/schemas/NewOrder"}
    with pytest.raises(ValueError, match="refers to itself"):
        openapi.request_schema(looping, "createOrder")
    with pytest.raises(KeyError):
        openapi.request_schema(V1, "noSuchOperation")


@pytest.mark.parametrize("op_id, newer, verdict", [
    ("createOrder", WIDER, "proven"),
    ("listOrders", WIDER, "proven"),
    ("cancelOrder", BREAKING, "proven"),
    ("createOrder", BREAKING, "falsified"),
    ("listOrders", BREAKING, "falsified"),
])
def test_a_new_version_keeps_every_request_or_names_the_one_it_breaks(op_id, newer, verdict):
    pytest.importorskip("z3")
    from mathema_language import smt
    older_language = openapi.operation(V1, op_id).language
    newer_language = openapi.operation(newer, op_id).language
    result = smt._schema_inclusion(older_language, newer_language)
    assert result.verdict == verdict, str(result)
    if verdict == "falsified":
        assert older_language.contains(result.witness)
        assert not newer_language.contains(result.witness)


def test_a_query_parameter_is_held_to_a_path_language():
    pytest.importorskip("z3")
    from mathema_language import smt
    from mathema_language.text.path_language import path_within
    result = smt._field_in(openapi.operation(V1, "listOrders").language, "query.export",
                           path_within("/exports"))
    assert result.verdict == "falsified"
    assert not path_within("/exports").contains(result.witness["query"]["export"])


@pytest.mark.parametrize("op_id", ["createOrder", "listOrders", "cancelOrder"])
def test_the_encoding_of_a_request_never_admits_less_than_older_or_more_than_newer(op_id):
    z3 = pytest.importorskip("z3")
    from mathema_language import smt
    language = openapi.operation(V1, op_id).language
    names = smt._names(language)

    def flat(request, prefix=""):
        out = {}
        for key, value in request.items():
            out[prefix + key] = True if isinstance(value, dict) else value
            if isinstance(value, dict):
                out.update(flat(value, prefix + key + "."))
        return out

    def satisfies(request, side):
        values = flat(request)
        enc = smt.MembershipEncoding(z3)
        solver = z3.Solver()
        solver.add(enc.language(language, list(dict.fromkeys([*names, *values])), side))
        for name in dict.fromkeys([*names, *values]):
            solver.add(enc.var(name) == (enc.const(values[name]) if name in values else enc.V.absent))
        return solver.check() == z3.sat

    def past_z3(request):
        return any(isinstance(v, str) and any(ord(c) > smt._Z3_MAX_CHAR for c in v)
                   for v in flat(request).values())

    rng = random.Random(5)
    for _ in range(60):
        request = language.sample(rng)
        if not past_z3(request):
            assert satisfies(request, "older"), request
    for _ in range(60):
        request = language.outside(rng)
        if request is None or not isinstance(request, dict) or past_z3(request):
            continue
        try:
            newer = satisfies(request, "newer")
        except smt.Untranslated:
            continue
        if newer:
            assert language.contains(request), request
