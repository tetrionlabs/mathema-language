# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The one module that imports from mathema.

Everything this package needs from mathema is on the extension surface,
`mathema.interfaces.extension`, and is re-exported here under the same
name; no other module names mathema at all. The import-contract test
enforces both halves, so a rename inside mathema is found here, by the
surface's own version policy, never as a traceback somewhere else.
"""
from mathema.interfaces.extension import EXTENSION_API_VERSION as EXTENSION_API_VERSION
from mathema.interfaces.extension import HAZARD_KINDS as HAZARD_KINDS
from mathema.interfaces.extension import KINDS as KINDS
from mathema.interfaces.extension import LEVELS as LEVELS
from mathema.interfaces.extension import STRING_HAZARDS as STRING_HAZARDS
from mathema.interfaces.extension import HazardValue as HazardValue
from mathema.interfaces.extension import Language as Language
from mathema.interfaces.extension import LanguageRef as LanguageRef
from mathema.interfaces.extension import OutputPredicateFamily as OutputPredicateFamily
from mathema.interfaces.extension import Problem as Problem
from mathema.interfaces.extension import ProofResult as ProofResult
from mathema.interfaces.extension import SafetyFamily as SafetyFamily
from mathema.interfaces.extension import StringLanguage as StringLanguage
from mathema.interfaces.extension import UnknownLanguage as UnknownLanguage
from mathema.interfaces.extension import call_with_target as call_with_target
from mathema.interfaces.extension import describe_language as describe_language
from mathema.interfaces.extension import (
    domain_bound_from_json as domain_bound_from_json,
)
from mathema.interfaces.extension import format_point as format_point
from mathema.interfaces.extension import language_adaptors as language_adaptors
from mathema.interfaces.extension import language_problems as language_problems
from mathema.interfaces.extension import language_vocabulary as language_vocabulary
from mathema.interfaces.extension import lexicon_problems as lexicon_problems
from mathema.interfaces.extension import lexicon_source as lexicon_source
from mathema.interfaces.extension import pinned_float_env as pinned_float_env
from mathema.interfaces.extension import probe_trials as probe_trials
from mathema.interfaces.extension import register_language as register_language
from mathema.interfaces.extension import resolve_language as resolve_language
from mathema.interfaces.extension import sample_bound as sample_bound
from mathema.interfaces.extension import shrink as shrink
from mathema.interfaces.extension import synth_other_params as synth_other_params
from mathema.interfaces.extension import unregister_language as unregister_language
from mathema.interfaces.extension import write_lexicon_golden as write_lexicon_golden
