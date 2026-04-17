# Model-View Brief

The table view constructs one visible projection from source rows. The model/view seam owns:

- filtering out rows marked `visible: false`
- ordering visible rows by descending priority and then `id`
- synchronizing the detail pane with the final visible selection

It does not own widget rendering, visualization semantics, or scoring.
