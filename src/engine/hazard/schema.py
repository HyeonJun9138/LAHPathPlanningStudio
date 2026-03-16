"""Pydantic v2 models for the hazard subsystem.

Defines the configuration schema for hazard sources, restricted zones,
observation boxes, altitude bands, and the top-level hazard config that
drives the :class:`HazardBuildPipeline`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AltitudeBand(BaseModel):
    """A named altitude layer used to slice risk computation."""

    name: str
    agl_m: float


class HazardSource(BaseModel):
    """A single point-source of risk (threat emitter, terrain obstacle, etc.).

    Attributes:
        id: Unique identifier.
        name: Human-readable label.
        type: Free-form category string (e.g. ``"sam"``, ``"aaa"``).
        x, y, z: Position in the project coordinate system (metres).
        influence_radius_m: Maximum effective range.
        altitude_weight_profile: Mapping of altitude-band name to a
            multiplicative weight in ``[0, 1]``.  Bands not listed default
            to 1.0 inside the pipeline.
        visibility_sensitive: When *True* the pipeline will attenuate
            this source's risk by the LoS visible-ratio.
        range_falloff_type: One of ``exp``, ``linear``, ``inverse``.
        range_falloff_scale: Characteristic distance for ``exp`` and
            ``inverse`` falloff modes.
        sector_azimuth_deg: Centre bearing of the active sector
            (degrees, north-up clockwise).
        sector_width_deg: Total angular width of the active sector.
            360 means omnidirectional.
        enabled: Toggle the source on/off without removing it.
    """

    id: str
    name: str
    type: str
    x: float
    y: float
    z: float
    influence_radius_m: float
    altitude_weight_profile: dict[str, float] = Field(default_factory=dict)
    visibility_sensitive: bool = True
    range_falloff_type: Literal["exp", "linear", "inverse"] = "exp"
    range_falloff_scale: float = 1200.0
    sector_azimuth_deg: float = 0.0
    sector_width_deg: float = 360.0
    enabled: bool = True


class RestrictedZone(BaseModel):
    """A polygonal no-fly / penalty zone.

    Attributes:
        id: Unique identifier.
        polygon: List of ``[x, y]`` vertices (closed automatically).
        min_altitude_m: Lower altitude bound of the zone.
        max_altitude_m: Upper altitude bound.
        penalty_type: ``"hard"`` means infinite cost; ``"soft"`` adds
            *penalty_value* to the cost.
        penalty_value: Cost added when ``penalty_type`` is ``"soft"``.
    """

    id: str
    polygon: list[list[float]]
    min_altitude_m: float = 0.0
    max_altitude_m: float = 9999.0
    penalty_type: Literal["hard", "soft"] = "hard"
    penalty_value: float = 1.0


class ObserveBox(BaseModel):
    """An observation-objective volume.

    Attributes:
        id: Unique identifier.
        center_xyz: Centre of the box ``[x, y, z]``.
        size_xyz: Dimensions ``[dx, dy, dz]``.
        required_los_ratio: Minimum fraction of the box that must be
            visible from a candidate observation position.
        preferred_heading: Ideal approach heading (degrees).
        observation_duration_sec: Time the vehicle must loiter.
    """

    id: str
    center_xyz: list[float]
    size_xyz: list[float]
    required_los_ratio: float = 0.7
    preferred_heading: float = 0.0
    observation_duration_sec: float = 10.0


class HazardConfig(BaseModel):
    """Top-level configuration consumed by :class:`HazardBuildPipeline`.

    Attributes:
        fusion_mode: How per-source risk layers are combined.
        clearance_margin_m: Minimum terrain clearance for LoS checks.
        altitude_bands: The altitude slices to evaluate.
        sources: Point-source threats.
        restricted_zones: Polygon zones with cost penalties.
        observe_boxes: Observation objectives.
    """

    fusion_mode: Literal["probabilistic_union", "sum_clip", "max"] = (
        "probabilistic_union"
    )
    clearance_margin_m: float = 20.0
    altitude_bands: list[AltitudeBand]
    sources: list[HazardSource] = Field(default_factory=list)
    restricted_zones: list[RestrictedZone] = Field(default_factory=list)
    observe_boxes: list[ObserveBox] = Field(default_factory=list)
