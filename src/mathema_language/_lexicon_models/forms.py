# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A signup form as a pydantic model."""
from pydantic import BaseModel, Field


class SignupForm(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    age: int = Field(ge=13, le=120)
