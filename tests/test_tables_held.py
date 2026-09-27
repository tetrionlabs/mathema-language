# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Tables are held out of 0.1: the schema package's public surface is
rows, the table languages live in the internal `_tables` module and
the table vocabulary in the internal `vocabulary._table`, the
public `Ecosystem` protocol has no table methods, and the adaptors
export no table reader."""
import mathema_language.schema as schema
from mathema_language.schema import Ecosystem
from mathema_language.schema.adaptors import django as django_adaptor
from mathema_language.schema.adaptors import sqlalchemy as sqlalchemy_adaptor


def test_the_public_schema_surface_is_rows():
    held = {"frame_of", "FrameLanguage", "TableSchema", "ForeignKey", "TableEcosystem"}
    assert not held & set(schema.__all__)
    assert not any(hasattr(schema, name) for name in ("frame_of", "FrameLanguage"))
    assert "RowLanguage" in schema.__all__


def test_the_ecosystem_protocol_has_no_table_methods():
    table_methods = {"build_frame", "validate_frame", "row_count", "column_names", "cell"}
    assert not table_methods & set(dir(Ecosystem))


def test_the_adaptors_export_no_table_reader():
    for module in (django_adaptor, sqlalchemy_adaptor):
        assert module.__all__ == ["adapt"]


def test_the_held_table_code_is_still_importable_internally():
    from mathema_language.schema._tables import FrameLanguage, TableEcosystem, frame_of
    assert callable(frame_of) and FrameLanguage.kind == "frame"
    assert "_build_frame" in dir(TableEcosystem)


def test_the_table_vocabulary_is_held_and_the_text_and_tree_vocabularies_public():
    import mathema_language.vocabulary as vocabulary
    assert vocabulary.__all__ == ["text", "tree"]
    assert not hasattr(vocabulary, "table")
    from mathema_language.vocabulary import _table, text
    assert callable(_table.frame_eq) and callable(text.nfc)
