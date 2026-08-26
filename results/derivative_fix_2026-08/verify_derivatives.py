"""
Independent check of the eight load/PV current derivatives in OPF.ams.

    py -3 verify_derivatives.py

WHAT THIS CHECKS AND WHY IT IS CONCLUSIVE
-----------------------------------------
In MainProject/OPF.ams, section NetworkModel, the four load/PV currents are written
as a first-order Taylor expansion about the flat-start voltage (Vre0, Vim0). For
example Iim_Load reads, literally:

    (P0*Vim0 - Q0*Vre0)/(Vre0^2 + Vim0^2)          <- the base value  f(V0)
      + dIimdVre_Load * (Vre - Vre0)               <- coefficient on dVre
      + dIimdVim_Load * (Vim - Vim0)               <- coefficient on dVim

Because the model is written in that form, the eight `d...` parameters are not free
modelling choices. Each one MUST equal the corresponding partial derivative of its
own base function, or the expansion is not an expansion of that function.

So the check needs no knowledge of power systems and no reference implementation.
It differentiates each base function numerically, and compares against the algebraic
expression the model uses. Anything that disagrees is wrong as a matter of arithmetic.

Both the pre-fix and post-fix expressions are included below, so this script
reproduces the finding as well as confirming the correction.

Everything is standard library. No numpy, no pandas, nothing to install.
"""

import math
import sys

TOL = 1e-6          # relative; central differences land around 1e-9
H   = 1e-7          # finite-difference step


def D(vr, vi):
    """The denominator |V|^2 that appears throughout."""
    return vr * vr + vi * vi


# ---------------------------------------------------------------------------
# The four base functions, transcribed from the Variable definitions in
# OPF.ams -> NetworkModel -> DeclarationSection LoadAndGenVars.
#   P = P0(d,t)      active load        (p.u., Sb = 1 MW)
#   Q = Q0(d,t)      reactive load
#   G = GenP0(d,t)   PV output
# ---------------------------------------------------------------------------
BASE = {
    "Ire_Gen":  lambda vr, vi, P, Q, G: (G * vr) / D(vr, vi),
    "Iim_Gen":  lambda vr, vi, P, Q, G: (G * vi) / D(vr, vi),
    "Ire_Load": lambda vr, vi, P, Q, G: (P * vr + Q * vi) / D(vr, vi),
    "Iim_Load": lambda vr, vi, P, Q, G: (P * vi - Q * vr) / D(vr, vi),
}

# ---------------------------------------------------------------------------
# The eight derivative parameters, from OPF.ams -> NetworkModel ->
# DeclarationSection Linearization. Transcribed as literally as Python allows,
# so they can be diffed against the .ams by eye.
#
# BEFORE = the model as it stood up to 2026-08-24 (commit 8a47dbe and earlier,
#          i.e. since the first commit).
# AFTER  = the model after the fix (commit e5381fb).
# Six of the eight are identical in both columns; two are not.
# ---------------------------------------------------------------------------
BEFORE = {
    ("Ire_Gen",  "vr"): lambda vr, vi, P, Q, G: G * (-vr**2 + vi**2) / D(vr, vi)**2,
    # dIredVim_Gen used P0minGenP = P0 - GenP0 where the function contains only GenP0
    ("Ire_Gen",  "vi"): lambda vr, vi, P, Q, G: (-2 * (P - G) * vr * vi) / D(vr, vi)**2,
    ("Iim_Gen",  "vr"): lambda vr, vi, P, Q, G: (-2 * G * vr * vi) / D(vr, vi)**2,
    ("Iim_Gen",  "vi"): lambda vr, vi, P, Q, G: G * (vr**2 - vi**2) / D(vr, vi)**2,
    ("Ire_Load", "vr"): lambda vr, vi, P, Q, G: (P * (-vr**2 + vi**2) - 2 * Q * vi * vr) / D(vr, vi)**2,
    ("Ire_Load", "vi"): lambda vr, vi, P, Q, G: (Q * (-vi**2 + vr**2) - 2 * P * vr * vi) / D(vr, vi)**2,
    ("Iim_Load", "vr"): lambda vr, vi, P, Q, G: (Q * (vr**2 - vi**2) - 2 * P * vr * vi) / D(vr, vi)**2,
    # dIimdVim_Load closed its bracket one term late, pulling the Q0 term inside
    # the multiplication by P0. Note this is also dimensionally incoherent:
    # (vr^2 - vi^2) is volts^2, while 2*Q*vr*vi is power x volts^2.
    ("Iim_Load", "vi"): lambda vr, vi, P, Q, G: P * (vr**2 - vi**2 + 2 * Q * vr * vi) / D(vr, vi)**2,
}

AFTER = dict(BEFORE)
AFTER[("Ire_Gen",  "vi")] = lambda vr, vi, P, Q, G: (-2 * G * vr * vi) / D(vr, vi)**2
AFTER[("Iim_Load", "vi")] = lambda vr, vi, P, Q, G: (P * (vr**2 - vi**2) + 2 * Q * vr * vi) / D(vr, vi)**2

LABEL = {
    ("Ire_Gen",  "vr"): "dIredVre_Gen",
    ("Ire_Gen",  "vi"): "dIredVim_Gen",
    ("Iim_Gen",  "vr"): "dIimdVre_Gen",
    ("Iim_Gen",  "vi"): "dIimdVim_Gen",
    ("Ire_Load", "vr"): "dIredVre_Load",
    ("Ire_Load", "vi"): "dIredVim_Load",
    ("Iim_Load", "vr"): "dIimdVre_Load",
    ("Iim_Load", "vi"): "dIimdVim_Load",
}

# ---------------------------------------------------------------------------
# Operating points. The voltages are the ones Load_data_reset actually seeds:
# LV nodes carry the 30 deg Dy1 rotation scaled by VmultLV = 1.037; MV nodes sit
# at the balanced unit vectors. Load and PV span midday, evening and night.
# ---------------------------------------------------------------------------
VOLTAGES = [
    ("LV phase 1", 0.866 * 1.037, -0.5 * 1.037),
    ("LV phase 2", -0.866 * 1.037, -0.5 * 1.037),
    ("LV phase 3", 0.0 * 1.037, 1.0 * 1.037),
    ("MV phase 1", 1.0, 0.0),
    ("MV phase 2", -0.5, -0.866),
    ("MV phase 3", -0.5, 0.866),
]
CONDITIONS = [
    ("midday, PV 3 kW", 0.0010, 0.00030, 0.0030),
    ("evening, no PV", 0.0025, 0.00080, 0.0000),
    ("dawn, PV 0.5 kW", 0.0010, 0.00030, 0.0005),
    ("high PV, low load", 0.0005, -0.00020, 0.0040),
]


def numeric_partial(fn, vr, vi, P, Q, G, wrt):
    """Central finite difference of fn with respect to vr or vi."""
    if wrt == "vr":
        return (fn(vr + H, vi, P, Q, G) - fn(vr - H, vi, P, Q, G)) / (2 * H)
    return (fn(vr, vi + H, P, Q, G) - fn(vr, vi - H, P, Q, G)) / (2 * H)


def worst_error(table, key):
    """Largest disagreement with the numerical derivative, and where it occurs.

    Reported as a relative error, except where the true derivative is zero and the
    expression is not: there a ratio is meaningless, so the case is named instead.
    """
    base, wrt = key
    fn, expr = BASE[base], table[key]
    worst_rel, worst_abs, where, flipped, from_zero = 0.0, 0.0, None, False, False
    scale = 0.0
    for vname, vr, vi in VOLTAGES:
        for cname, P, Q, G in CONDITIONS:
            truth = numeric_partial(fn, vr, vi, P, Q, G, wrt)
            got = expr(vr, vi, P, Q, G)
            scale = max(scale, abs(truth))
            adiff = abs(got - truth)
            # normalise against the largest true value this derivative takes, so a
            # point where the truth happens to vanish cannot manufacture a huge ratio
            rel = adiff / max(abs(truth), 1e-12)
            if adiff > worst_abs:
                worst_abs, where = adiff, f"{vname}, {cname}"
                flipped = (got * truth < 0)
                from_zero = (abs(truth) < 1e-15 and adiff > 1e-15)
            worst_rel = max(worst_rel, rel)
    # a scale-relative figure that stays meaningful even at a zero crossing
    rel_to_scale = worst_abs / max(scale, 1e-12)
    return worst_rel, rel_to_scale, where, flipped, from_zero


def report(title, table):
    print(f"\n{title}")
    print("-" * len(title))
    bad = []
    for key in LABEL:
        rel, rel_scale, where, flipped, from_zero = worst_error(table, key)
        ok = rel < TOL
        mark = "ok  " if ok else "WRONG"
        if ok:
            print(f"  [{mark}] {LABEL[key]:16s} max error {rel:10.3e}")
        else:
            detail = f"{rel_scale * 100:.1f}% of this derivative's own scale"
            print(f"  [{mark}] {LABEL[key]:16s} max error {detail}")
            print(f"{'':9s}{'':16s} worst at {where}")
            if flipped:
                print(f"{'':9s}{'':16s} -> the expression has the OPPOSITE SIGN to the truth")
            if from_zero:
                print(f"{'':9s}{'':16s} -> at some points the true derivative is exactly 0 "
                      "and the expression is not")
            bad.append(LABEL[key])
    return bad


def main():
    n = len(VOLTAGES) * len(CONDITIONS)
    print(__doc__.strip().split("\n")[0])
    print(f"\n8 derivatives x {n} operating points, central differences, tolerance {TOL:g}")

    bad_before = report("BEFORE the fix  (OPF.ams up to commit 8a47dbe)", BEFORE)
    bad_after = report("AFTER the fix   (OPF.ams from commit e5381fb)", AFTER)

    print("\n" + "=" * 68)
    if bad_before and not bad_after:
        print(f"CONFIRMED. {len(bad_before)} of 8 derivatives were wrong before the fix:")
        for b in bad_before:
            print(f"    - {b}")
        print(f"All 8 agree with the numerical derivative after the fix.")
        print("\nThe remaining 6 were correct all along and were not modified.")
        return 0
    if not bad_before and not bad_after:
        print("No discrepancy found before the fix - this does not reproduce the finding.")
        return 1
    print("Unexpected: some derivatives still disagree AFTER the fix:")
    for b in bad_after:
        print(f"    - {b}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
