"""WP3 — blind injection validation (proposal §5.8, Authorization C).

A HARNESS around the frozen WP2 pipeline (`wp2-frozen-v1`) — never new analysis.
Three code-separated roles run strictly in order:

  controller  (sealed seed) -> hidden mixture + sealed labels + commitment
  evaluate    (blind)        -> frozen-pipeline scores + commitment
  unblind     (after both)   -> efficiency vs predicted + FP vs targets -> gate

`foundation` sets up the disjoint blind-round pools and asserts the freeze
contract; `predict` generates the predetermined full-criterion efficiency surface
on the DEV split (the prediction G1 is judged against).
"""
