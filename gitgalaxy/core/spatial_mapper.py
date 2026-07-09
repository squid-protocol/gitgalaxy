# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
import math
import hashlib
import logging
from typing import Dict, List, Any, Optional

# ------------------------------------------------------------------------------
# SPATIAL MAPPER (Phase 7.5: Spatial Positioning Engine)
# ------------------------------------------------------------------------------

class SpatialMapper:
    """
    Transforms a flat list of artifacts into a deterministic 3D Cartesian coordinate map.

    Groups files into Directory Clusters (folders) and positions them relative to the
    highest-impact central node (Critical Node) of each sector while maintaining spatial clearance.

    DEFENSIVE ARCHITECTURE (Angular Spatial Hashing):
    Standard layout engines crash on O(N^2) collision detection loops when placing thousands
    of nodes. This mapper neutralizes that bottleneck by bucketing the map into 360 angular degrees.
    A placement ray only checks the exact degree it points at (and its immediate neighbors), 
    securing O(1) collision avoidance. This guarantees extreme velocity even on massive enterprise monoliths.
    """

    def __init__(self, parent_logger: Optional[logging.Logger] = None):
        # --- TELEMETRY SYNC ---
        if parent_logger:
            self.logger = parent_logger.getChild("spatial_mapper")
            self.logger.setLevel(parent_logger.level)
        else:
            self.logger = logging.getLogger("spatial_mapper")
            self.logger.setLevel(logging.INFO)

        # --- SPATIAL CONSTANTS ---
        # Micro Angle: Nodes within folders follow the classic mathematical Golden Angle
        # for optimal, non-overlapping organic distribution.
        self.MICRO_GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))  # ~2.39996 rad (~137.5 deg)

        # Macro Angle: Directory Clusters follow the user-tuned 92.4 degree step
        self.MACRO_GOLDEN_ANGLE = math.radians(92.4)

        # Base expansion multipliers
        self.MICRO_SPACING = 150.0  # Internal node-to-node density baseline
        self.MACRO_STEP_FACTOR = 1.15  # Inter-cluster step multiplier (Center-to-Center)
        self.MAX_TILT_DEG = 15.0  # Max degrees a cluster can tilt from the horizontal plane
        self.CORE_EXCLUSION_RADIUS = 600.0  # Clear center zone to prevent origin overlapping
        self.JITTER_MAGNITUDE = 45

    def _calculate_spatial_clearance(self, magnitude: float) -> float:
        """Determines the required tight clearance radius for a node based on its structural magnitude."""
        visual_radius = 10 + (math.pow(max(magnitude, 1), 1 / 3) * 2)
        clearance = 40 + (math.log2(max(magnitude, 2)) * 5)

        return min(visual_radius + clearance, 150.0)

    def _hash_jitter(self, seed: str, amplitude: float) -> float:
        """
        Applies a deterministic pseudo-random jitter based on a filename hash.
        This ensures that running the analysis multiple times on the same codebase 
        generates the exact same geometry every time, providing visual stability across audits.
        """
        if not seed:
            return 0.0
        h = int(hashlib.md5(seed.encode("utf-8")).hexdigest()[:8], 16)
        # Map 0-0xffffffff to a normalized range of -1.0 to 1.0
        normalized = (h / 0xFFFFFFFF) * 2.0 - 1.0
        return normalized * amplitude

    def map_repository(self, parsed_files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Injects 3D coordinates using a Ray-Casting Dynamic Mask.
        Ensures ecosystem graphs wrap cleanly around previous turns of the spiral by measuring
        all previously placed obstruction circles.
        """
        if not parsed_files:
            return []

        self.logger.info(f"Spatial Mapper: Executing Ray-Casting Dynamic Mask packing for {len(parsed_files)} nodes...")

        # 1. Sectorization (Directory Grouping)
        sectors: Dict[str, List[Dict[str, Any]]] = {}
        for file_node in parsed_files:
            path_str = file_node.get("path", file_node.get("filename", ""))
            parts = [p for p in path_str.replace("\\", "/").split("/") if p]
            sector_name = "/".join(parts[:-1]) if len(parts) > 1 else "__monolith__"
            file_node["directory_group"] = sector_name  # Saves to RAM for other reports
            if sector_name not in sectors:
                sectors[sector_name] = []
            sectors[sector_name].append(file_node)

        # 2. Hull Calculation
        sector_stats = []
        for name, items in sectors.items():
            items.sort(key=self._get_magnitude, reverse=True)
            central_node_magnitude = self._get_magnitude(items[0])
            central_footprint = self._calculate_spatial_clearance(central_node_magnitude)
            hull_radius = central_footprint + (math.sqrt(len(items)) * self.MICRO_SPACING)
            sector_stats.append({"name": name, "nodes": items, "radius": hull_radius})

        sector_stats.sort(key=lambda x: x["radius"], reverse=True)

        # 3. DYNAMIC MASK PLACEMENT (Spatial Hashed)
        placed_nodes = [[0.0, 0.0, self.CORE_EXCLUSION_RADIUS]]

        # --- THE FIX: ANGULAR SPATIAL HASHING ---
        NUM_BINS = 360
        spatial_grid = [[] for _ in range(NUM_BINS)]

        # Put the origin exclusion zone into all buckets
        for b in range(NUM_BINS):
            spatial_grid[b].append(0)

        current_angle = 0.0
        prev_radius = 0.0
        prev_dist_from_center = self.CORE_EXCLUSION_RADIUS

        for i, sec in enumerate(sector_stats):
            s_name = sec["name"]
            s_nodes = sec["nodes"]
            sec_radius = sec["radius"]

            if i == 0:
                dist = self.CORE_EXCLUSION_RADIUS + sec_radius
                sec_x, sec_z = dist, 0.0
                current_angle = 0.0
                prev_dist_from_center = dist
            else:
                # --- THE FIX: SUNFLOWER SEED MACRO SPIRAL ---
                # Lock the ray rotation to the exact Golden Angle multiplier
                # to prevent decaying rotation (the "comma" shape).
                current_angle = i * self.MACRO_GOLDEN_ANGLE

                cos_th = math.cos(current_angle)
                sin_th = math.sin(current_angle)
                max_r_intersect = self.CORE_EXCLUSION_RADIUS

                # --- FAST O(1) LOOKUP ---
                ray_deg = int(math.degrees(current_angle)) % 360
                bins_to_check = [(ray_deg - 1) % 360, ray_deg, (ray_deg + 1) % 360]

                candidates = set()
                for b in bins_to_check:
                    candidates.update(spatial_grid[b])

                for idx in candidates:
                    px, pz, pr = placed_nodes[idx]

                    b = -2 * (px * cos_th + pz * sin_th)
                    c = (px**2 + pz**2) - (pr * self.MACRO_STEP_FACTOR) ** 2
                    disc = b**2 - 4 * c

                    if disc >= 0:
                        r2 = (-b + math.sqrt(disc)) / 2.0
                        if r2 > max_r_intersect:
                            max_r_intersect = r2

                dist = max_r_intersect + sec_radius
                sec_x = dist * cos_th
                sec_z = dist * sin_th
                prev_dist_from_center = dist

            # Add to memory array
            new_idx = len(placed_nodes)
            placed_nodes.append([sec_x, sec_z, sec_radius])

            # --- REGISTER IN SPATIAL GRID ---
            eff_pr = sec_radius * self.MACRO_STEP_FACTOR
            dist_to_center = math.hypot(sec_x, sec_z)
            center_a = math.atan2(sec_z, sec_x)

            if eff_pr >= dist_to_center:
                for b in range(NUM_BINS):
                    spatial_grid[b].append(new_idx)
            else:
                half_a = math.asin(eff_pr / dist_to_center)
                start_deg = int(math.degrees(center_a - half_a))
                end_deg = int(math.degrees(center_a + half_a))

                for deg in range(start_deg, end_deg + 1):
                    spatial_grid[deg % 360].append(new_idx)

            # Jitter and Tilt logic
            sec_y = self._hash_jitter(s_name, 250.0)
            tilt_mag = math.radians(self._hash_jitter(s_name + "_tilt_mag", self.MAX_TILT_DEG))
            tilt_dir = math.radians((self._hash_jitter(s_name + "_tilt_dir", 0.5) + 0.5) * 360.0)

            central_node_magnitude = self._get_magnitude(s_nodes[0])
            central_footprint = self._calculate_spatial_clearance(central_node_magnitude)

            for j, node in enumerate(s_nodes):
                f_name = node.get("name", node.get("filename", f"node_{j}"))
                if j == 0:
                    lx, ly, lz = 0.0, 0.0, 0.0
                else:
                    p_foot = self._calculate_spatial_clearance(self._get_magnitude(node))
                    local_r = central_footprint + p_foot + (math.sqrt(j) * self.MICRO_SPACING)
                    local_th = j * self.MICRO_GOLDEN_ANGLE

                    bx, bz = local_r * math.cos(local_th), local_r * math.sin(local_th)
                    rot_x = bx * math.cos(tilt_dir) + bz * math.sin(tilt_dir)
                    rot_z = -bx * math.sin(tilt_dir) + bz * math.cos(tilt_dir)
                    tx, ty, tz = (
                        rot_x * math.cos(tilt_mag),
                        rot_x * math.sin(tilt_mag),
                        rot_z,
                    )
                    lx = tx * math.cos(tilt_dir) - tz * math.sin(tilt_dir)
                    lz = tx * math.sin(tilt_dir) + tz * math.cos(tilt_dir)
                    ly = ty

                jit_x = self._hash_jitter(f_name + "_x", self.JITTER_MAGNITUDE)
                jit_y = self._hash_jitter(f_name + "_y", self.JITTER_MAGNITUDE)
                jit_z = self._hash_jitter(f_name + "_z", self.JITTER_MAGNITUDE * 4)

                node["pos_x"] = round(sec_x + lx + jit_x, 2)
                node["pos_y"] = round(sec_y + ly + jit_y, 2)
                node["pos_z"] = round(sec_z + lz + jit_z, 2)

        return parsed_files

    def _get_magnitude(self, node: Dict[str, Any]) -> float:
        """Safely extracts structural magnitude regardless of which JSON version the pipeline is using."""
        if "forensics" in node:
            return float(node["forensics"].get("structural_mass", 0.0))
        return float(node.get("file_impact", node.get("sum_fxn_impact", 0.0)))