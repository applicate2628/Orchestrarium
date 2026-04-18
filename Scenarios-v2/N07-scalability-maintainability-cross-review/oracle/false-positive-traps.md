# False-Positive Traps

The following details are intentionally present and should not be raised as findings by themselves:

- the lane labels in `lane_catalog.py` are harmless presentation data; the problem is duplicating
  lane membership, not having labels
- returning `"unassigned"` from `resolve_lane` is not itself the issue here
- small local tuple or list literals are acceptable when they are not competing maintained owners
