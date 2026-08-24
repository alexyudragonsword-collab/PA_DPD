"""The one surface Kotlin calls. Everything else stays on this side.

``gui_core/services.py`` is the service layer both desktop GUIs sit on,
and the Android app uses the same one - not a copy. That is the whole
architecture: one contract, three front ends. This module is the adapter
that makes it callable across the language boundary, and it is
deliberately thin. Logic that belongs in services.py must not migrate
here, or the contract forks.

Three problems it solves:

**Live objects.** Several service functions return live Python objects -
a fitted model, a predistorter, a waveform, a scheduler. Those cannot and
should not cross to Kotlin. They are kept in a session registry and
addressed by opaque string handles; Kotlin holds names, never objects.

**Numbers.** Metadata goes as JSON. Arrays go as float32 blobs fetched
separately by key, because a 4096-point PSD as JSON floats is ~80 KB of
text to build, parse and garbage-collect for 16 KB of data.

**Capability.** torch has no Android wheel, so a few entry points cannot
run at all. ``capabilities()`` says so up front, and the UI greys them
out rather than letting them fail at the tap.
"""

from __future__ import annotations

import json
import os
import traceback

import numpy as np

# Functions of gui_core.services that Kotlin may call, by name. An
# allow-list rather than getattr on anything: `call` takes a name from
# outside this process, and the service module also holds private helpers
# and imported symbols that were never meant as entry points.
#
# tests/test_mobile_api.py asserts every name here exists in services.py,
# which is the guard against this table drifting away from the module it
# dispatches to - the most likely long-term failure of this design.
DISPATCH = (
    # sources and data
    "make_waveform",
    "make_synthetic_source",
    "cached_synthetic_source",
    "load_source",
    "source_preview",
    "source_extras_rows",
    "consume_source_extras",
    "eval_source_for",
    "analyze_two_tone_csv",
    "default_opendpd_dir",
    # modelling
    "fit_classical",
    "run_gain_modulation",
    "gain_mod_run_record",
    "identify_gain_mod_from_source",
    "fit_state_spline_from_source",
    "scheduler_from_source",
    "deembedder_from_source",
    # dpd
    "run_dpd_ila",
    "run_adaptive_dpd",
    "adaptive_run_record",
    "run_three_loop_demo",
    "three_loop_run_record",
    "constellation_points",
    # deployment
    "bitwidth_sweep",
    "lut_sweep",
    "export_artifacts",
    "load_saved_model",
    # plotting helpers
    "psd_pair",
    "ccdf_curves",
)

# Service entry points that need torch, which has no Android wheel. Named
# here so `capabilities()` can report them and the UI can grey them out,
# instead of the user tapping a control that throws ImportError.
TORCH_ONLY = ("fit_neural", "run_dpd_dla")

_SESSION: dict[str, object] = {}
_BLOBS: dict[str, np.ndarray] = {}
_counter = [0]

# Values small enough and plain enough to hand back inside the JSON
# result rather than as a handle.
_JSON_SCALARS = (bool, int, float, str, type(None))


def _new_id(prefix: str) -> str:
    _counter[0] += 1
    return f"{prefix}{_counter[0]}"


def boot(data_dir: str, lang: str = "zh") -> str:
    """Prepare the process. Must be called before anything else.

    ``gui_core.prefs`` resolves its path at import time, so PADPD_DATA_DIR
    has to be set before any padpd or gui_core module is imported - which
    is why the host passes the directory in rather than Python discovering
    it. Java cannot portably mutate the process environment, so the
    direction is host -> argument -> os.environ, not the reverse.
    """
    os.environ["PADPD_DATA_DIR"] = data_dir
    # Pin BLAS threading before numpy loads. padpd's own pitfall list
    # records an OpenMP barrier deadlock behind this; on Android the
    # thread limits differ again, so do not leave it to a guess.
    for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ.setdefault(var, "1")
    return capabilities(lang)


def capabilities(lang: str = "zh") -> str:
    """What this build can and cannot do, as JSON."""
    import padpd
    return json.dumps({
        "version": padpd.__version__,
        "lang": lang,
        "torch": False,        # no Android wheel exists
        "onnx": False,         # follows torch
        "rtl_cosim": False,    # needs iverilog/vvp subprocesses
        "unavailable": list(TORCH_ONLY),
        "dispatch": list(DISPATCH),
        "charts": _chart_names(),
    })


def _chart_names() -> list:
    from . import chart_spec
    return sorted(chart_spec.BUILDERS)


def _register(obj) -> str:
    handle = _new_id("h")
    _SESSION[handle] = obj
    return handle


def _deref(value):
    """Replace handle strings with the objects they name.

    Handles are recognised by being present in the registry, so an
    ordinary string argument that happens to look like one is only
    substituted if it actually names a live object.
    """
    if isinstance(value, str) and value in _SESSION:
        return _SESSION[value]
    if isinstance(value, dict) and "__handle__" in value:
        # An encoded live object being passed back in place.
        return _SESSION.get(value["__handle__"])
    if isinstance(value, list):
        return [_deref(v) for v in value]
    if isinstance(value, dict):
        return {k: _deref(v) for k, v in value.items()}
    return value


def _encode(value):
    """Turn a service return value into something JSON can carry.

    Arrays become blob keys, live objects become handles, containers
    recurse. The shape of the result mirrors the shape of the original,
    so the Kotlin side reads the same field names the desktop GUIs do.
    """
    if isinstance(value, _JSON_SCALARS):
        return value
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        if np.iscomplexobj(value):
            # Complex arrays go as two blobs: nothing downstream plots a
            # complex number directly, and splitting here keeps the blob
            # format a single flat float32 buffer.
            return {"__complex__": True,
                    "re": _put_blob(value.real), "im": _put_blob(value.imag),
                    "n": int(value.size)}
        return {"__blob__": _put_blob(value), "n": int(value.size)}
    if isinstance(value, complex):
        return {"__complex_scalar__": True, "re": value.real,
                "im": value.imag}
    if isinstance(value, dict):
        return {str(k): _encode(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_encode(v) for v in value]
    # Anything else is a live object - a model, a predistorter, a
    # waveform. Keep it here and hand out a name.
    return {"__handle__": _register(value),
            "type": type(value).__name__}


def _put_blob(arr) -> str:
    key = _new_id("b")
    _BLOBS[key] = np.ascontiguousarray(
        np.asarray(arr, dtype=np.float64).ravel(), dtype=np.float32)
    return key


def call(fn: str, args_json: str = "{}") -> str:
    """Invoke one allow-listed service function.

    ``args_json`` is ``{"args": [...], "kwargs": {...}}``; either may be
    omitted. Returns ``{"ok": true, "result": ...}`` or
    ``{"ok": false, "error": ..., "traceback": ...}`` - errors come back
    as data rather than as a Java exception, so the UI can show what
    failed without the app dying on a bad parameter.
    """
    if fn not in DISPATCH:
        hint = (" (needs torch, which has no Android build)"
                if fn in TORCH_ONLY else "")
        return json.dumps({"ok": False,
                           "error": f"{fn} is not callable here{hint}"})
    try:
        payload = json.loads(args_json) if args_json else {}
        args = _deref(payload.get("args", []))
        kwargs = _deref(payload.get("kwargs", {}))
        import gui_core.services as services
        result = getattr(services, fn)(*args, **kwargs)
        # Register the raw result too, and return its handle alongside the
        # encoded view. Service functions routinely return a dict mixing
        # arrays with live objects - a source, say, carries x/y arrays AND
        # a PA instance - and the caller almost always wants to hand that
        # whole thing to the next call. Without a handle for the container
        # itself, Kotlin would have to reassemble it field by field.
        return json.dumps({"ok": True,
                           "handle": _register(result),
                           "result": _encode(result)})
    except Exception as e:                       # noqa: BLE001
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}",
                           "traceback": traceback.format_exc(limit=8)})


def _build_chart(name: str, args, kwargs) -> dict:
    from . import chart_spec
    lang = kwargs.pop("lang", "zh")
    spec, blobs = chart_spec.build(name, *args, lang=lang, **kwargs)
    # chart_spec numbers its own keys from zero per chart; namespace them
    # so two charts alive at once cannot collide.
    prefix = _new_id("c")
    remap = {k: f"{prefix}_{k}" for k in blobs}
    _BLOBS.update({remap[k]: v for k, v in blobs.items()})
    return _rekey(spec, remap)


def chart(name: str, args_json: str = "{}") -> str:
    """Build a chart spec. Same calling convention as ``call``.

    Returns ``{"ok": true, "spec": {...}}`` with the spec's numeric
    arrays already registered as blobs, fetchable with ``blob``.
    """
    try:
        payload = json.loads(args_json) if args_json else {}
        args = _deref(payload.get("args", []))
        kwargs = _deref(payload.get("kwargs", {}))
        return json.dumps({"ok": True, "spec": _build_chart(name, args, kwargs)})
    except Exception as e:                       # noqa: BLE001
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}",
                           "traceback": traceback.format_exc(limit=8)})


def page(name: str, args_json: str = "{}") -> str:
    """Assemble one screen. Same calling convention as ``call``.

    Returns ``{"ok": true, "handle": ..., "metrics": [...],
    "charts": {slot: spec}}``. One crossing per screen rather than one
    per value: the alternative is Kotlin issuing a service call, several
    attribute reads and four chart builds, each taking the GIL, to draw
    a single view.
    """
    try:
        payload = json.loads(args_json) if args_json else {}
        args = _deref(payload.get("args", []))
        kwargs = _deref(payload.get("kwargs", {}))
        from . import pages
        built = pages.build(name, *args, **kwargs)
        lang = built.get("lang", "zh")
        charts = {slot: _build_chart(spec_name, spec_args,
                                     dict(spec_kwargs, lang=lang))
                  for slot, (spec_name, spec_args, spec_kwargs)
                  in built["charts"].items()}
        return json.dumps({"ok": True,
                           "handle": _register(built["result"]),
                           "metrics": built["metrics"],
                           # Sentences the screen wants shown verbatim -
                           # the gain-modulation verdict, for one, whose
                           # wording depends on what was measured.
                           "notes": built.get("notes", []),
                           # Tabular screens (Compare) return rows rather
                           # than metric cards.
                           "rows": built.get("rows", []),
                           # Choices the screen offers, when they are
                           # discovered at runtime rather than fixed -
                           # models fitted this session, for one.
                           "options": built.get("options", []),
                           "charts": charts})
    except Exception as e:                       # noqa: BLE001
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}",
                           "traceback": traceback.format_exc(limit=8)})


def delete_runs(ids_json: str) -> str:
    """Delete runs from the store. Returns how many remain.

    Separate from ``page`` on purpose: page assembles a view and must
    stay safe to call, while this destroys records.
    """
    try:
        from . import pages
        remaining = pages.delete_runs(json.loads(ids_json))
        return json.dumps({"ok": True, "remaining": remaining})
    except Exception as e:                       # noqa: BLE001
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}",
                           "traceback": traceback.format_exc(limit=8)})


def i18n_map(lang: str = "en") -> str:
    """The whole Chinese-to-English table, sent once at boot.

    Kotlin sources carry the Chinese strings verbatim, exactly as the Qt
    sources do, and translate by looking them up in this map. The
    alternative - generating res/values/strings.xml - forces every string
    to acquire a generated identifier, since Android resource names
    cannot be Chinese, and Kotlin then reads
    `stringResource(R.string.s_9f2a41)` where the desktop reads the
    sentence. Resource files earn that cost by following the system
    locale; this app does not, because the language is a control in the
    UI on every front end.

    Empty for ``zh``: the keys are already Chinese, so the lookup is the
    identity and there is nothing to carry.
    """
    if lang == "zh":
        return json.dumps({})
    from gui_core import i18n
    return json.dumps({k: i18n.tr(k, lang) for k in i18n._EN})


def gallery_list() -> str:
    """Index of the chart gallery. Metadata only - nothing is computed
    until an entry is asked for."""
    from . import gallery
    return json.dumps({"ok": True, "entries": gallery.listing()})


def gallery_chart(entry_id: str, lang: str = "zh") -> str:
    """Build one gallery entry, running whatever computation it needs.

    Separate from ``chart`` because the gallery supplies its own inputs:
    some entries run a real service path, others carry a fixture because
    their real producer is minutes of compute or needs torch. Which is
    which is in ``gallery.listing()`` and shown in the UI - a plausible
    chart is otherwise easy to mistake for a working pipeline.
    """
    try:
        from . import gallery
        name, args, kwargs = gallery.chart_args(entry_id)
        kwargs = dict(kwargs, lang=lang)
        return json.dumps({"ok": True, "id": entry_id,
                           "spec": _build_chart(name, args, kwargs)})
    except Exception as e:                       # noqa: BLE001
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}",
                           "traceback": traceback.format_exc(limit=8)})


def _rekey(spec: dict, remap: dict) -> dict:
    for panel in spec["panels"]:
        for s in panel["series"]:
            s["x"] = remap[s["x"]]
            s["y"] = remap[s["y"]]
    return spec


def blob(key: str) -> bytes:
    """Fetch one array as little-endian float32 bytes.

    Chaquopy maps Python ``bytes`` straight to a Kotlin ``ByteArray``;
    decode with ``ByteBuffer.order(LITTLE_ENDIAN).asFloatBuffer()``.
    Returns empty bytes for an unknown key rather than raising, so a
    stale key in the UI degrades to an empty curve.
    """
    arr = _BLOBS.get(key)
    if arr is None:
        return b""
    return arr.astype("<f4", copy=False).tobytes()


def release(*keys: str) -> None:
    """Drop handles and blobs by name.

    Worth calling: a fitted GMP holds its basis matrix, and a few
    forgotten sources will outweigh everything else the app keeps.
    """
    for k in keys:
        _SESSION.pop(k, None)
        _BLOBS.pop(k, None)


def reset() -> None:
    """Drop everything. The registry is process-global, and an Activity
    restart would otherwise inherit the previous session's objects."""
    _SESSION.clear()
    _BLOBS.clear()


def stats() -> str:
    """Handle and blob counts plus blob bytes - for a debug readout, and
    for tests asserting that release actually releases."""
    return json.dumps({
        "handles": len(_SESSION),
        "blobs": len(_BLOBS),
        "blob_bytes": int(sum(a.nbytes for a in _BLOBS.values())),
    })
