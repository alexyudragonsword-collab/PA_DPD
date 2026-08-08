from .adaptive import AdaptiveDPD
from .ila import ILAPredistorter


def __getattr__(name):
    # torch-dependent direct-learning entry points load lazily so the
    # slim (no-torch) install keeps importing padpd.dpd
    if name in ("direct_learn_spline_dpd", "torch_spline_basis"):
        from . import direct
        return getattr(direct, name)
    raise AttributeError(f"module 'padpd.dpd' has no attribute {name!r}")


__all__ = ["ILAPredistorter", "AdaptiveDPD", "direct_learn_spline_dpd",
           "torch_spline_basis"]
