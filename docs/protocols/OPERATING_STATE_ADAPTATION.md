# Operating-state adaptation

Phase 11.4 deterministically combines battery, charging, thermal, foreground-load, and idle observations. Low unplugged battery caps experts at economical and disables speculation. Thermal protection caps at micro. High foreground load disables prefetch. Background adaptation is enabled only after five idle minutes with no protective reason.

Every restriction has a reason code and user preferences cannot override it.
