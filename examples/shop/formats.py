# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The shop's identifiers and formats: order numbers, order ids, dates,
addresses, tokens, colours, attribute names and shell commands."""
import base64
import datetime as dt
import shlex
import uuid


def render_quantity(n: int) -> str:
    """A quantity as it is printed on the invoice."""
    return str(n)


def parse_order_id(text: str) -> uuid.UUID:
    """The order id in a URL, or a ValueError when it is not one."""
    return uuid.UUID(text)


def normalise_order_id(text: str) -> str:
    """The order id as the database stores it."""
    return str(uuid.UUID(text))


def normalise_date(text: str) -> str:
    """A delivery date as the shop stores it."""
    return dt.date.fromisoformat(text).isoformat()


def normalise_timestamp(text: str) -> str:
    """An event time as the shop stores it."""
    return dt.datetime.fromisoformat(text).isoformat()


def anonymise_ip(address: str) -> str:
    """A visitor's address with the last part zeroed, for analytics."""
    return ".".join(address.split(".")[:3] + ["0"])


def reencode_token(token: str) -> str:
    """An API token as the gateway passes it on."""
    return base64.b64encode(base64.b64decode(token)).decode("ascii")


def normalise_colour(text: str) -> str:
    """A colour's hex bytes as the theme file stores them."""
    return bytes.fromhex(text).hex()


def attribute_name(label: str) -> str:
    """A form label turned into the attribute name the template uses."""
    return label.strip().replace(" ", "_").lower()


def delete_command(filename: str) -> list:
    """The command that deletes an uploaded file, split into arguments
    the way the shell will."""
    return shlex.split(f"rm {filename}")


def delete_command_quoted(filename: str) -> list:
    """The same command with the filename quoted."""
    return shlex.split(f"rm {shlex.quote(filename)}")
