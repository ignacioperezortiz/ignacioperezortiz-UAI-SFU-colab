"""Fifth patch (after add_zx_anchor.py) for model/MainProject/OPF.ams of THIS folder (5 Oct, 15:25).

Bug of the first anchor run (WC_EXPORT anchor, lane L5, 15:10): only the LOWER side of the terminal band was
anchored, E_end >= max(E_now, E_noservice) - delta_E, while the upper side stayed E_end <= E_now + delta_E.
After the first max-export request the battery was at 10 % with the no-service SOC at 40 %, so the band
[35 %, 15 %] was empty and every baseline from step 14 on was Infeasible (EXECFAIL at step 14). The run was
stopped; its info file is kept in runs/archive_anchor_v1/.

Fix: the upper side is anchored the same way, E_end <= max(E_now, E_noservice) + delta_E, so the band is
always [m - delta_E, m + delta_E] with m = max(E_now, E_noservice), as in the paper but centred on m.
Usage: python scripts/add_zx_anchor_fix.py
"""
import hashlib
from pathlib import Path

AMS = Path(__file__).resolve().parents[1] / "model" / "MainProject" / "OPF.ams"
raw = AMS.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n")
s = raw.decode("utf-8").replace("\r\n", "\n")
assert "ZX_AnchorOn" in s, "run add_zx_anchor.py first"
old = ("Definition: sum(t, BattP_Chg(bat,t)*etaChg(bat) - BattP_Dis(bat,t)/etaDis(bat)) <= CyclicSOCBand * BattEcap(bat) / DeltaT;")
assert s.count(old) == 1, s.count(old)
s = s.replace(old, old[:-1] + " + ZX_AnchorOn * max(0, ZX_SOCAnchor(bat) - BattSOCini(bat)) * BattEcap(bat) / DeltaT;")
out = s.replace("\n", "\r\n").encode("utf-8")
AMS.write_bytes(out)
print("patched", AMS, "sha256", hashlib.sha256(out).hexdigest()[:16])
