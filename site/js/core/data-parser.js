/**
 * GitGalaxy
 * Copyright (c) 2026 Joe Esquibel
 *
 * This source code is licensed under the PolyForm Noncommercial License 1.0.0.
 * You may not use this file except in compliance with the License.
 * A copy of the license can be found in the LICENSE file in the root directory
 * of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
 */
/**
 * FILENAME: data-parser.js
 * GitGalaxy Data Ingestion & Transformation Layer
 *: Deep Refraction Update (Fibonacci Physics + Complexity Depth)
 * Handles Satellite Impact Scoring, 3D Phyllotaxis, and DNA Inheritance.
 */

export class DataParser {
    constructor() {
        // Schema mappings from the engine spec
        this.RISK_INDICES = {
            COGNITIVE: 0, SAFETY: 1, TECH_DEBT: 2, VERIFICATION: 3, API: 4,
            CONCURRENCY: 5, FLUX: 6, GRAVEYARD: 7, SPEC: 8, STABILITY: 9,
            CHURN: 10, DOCS: 11, CIVIL_WAR: 12
        };

        // Standardized Hit indices for structural logic
        this.HIT_INDICES = {
            BRANCH: 0,
            SAFETY: 9,
            DOCS: 12,
            IMPORTS: 23,
            FUNC_START: 3,
            CLASS_START: 4
        };
        
        // The 10-Point SAT_SCHEMA from the GPU Recorder
        this.SAT_INDICES = {
            NAME_ID: 0,
            LOC: 1,
            BRANCH: 2,
            ANGLE_X10: 3,
            ARGS: 4,
            TYPE_ID: 5,
            RATIO_X1000: 6,
            MAG_X10: 7,
            START_LINE: 8,
            END_LINE: 9
        };
    }

    /**
     * Translates raw JSON into a structured Galaxy payload.
     * @param {Object} raw - The raw JSON from the scanner.
     * @returns {Object} Structured data for the Engine.
     */
    parse(raw) {
        if (!raw || !raw.galaxy) return null;

        const galaxy = raw.galaxy;
        const count = galaxy.names.length;
        const stride = raw.meta?.schemas?.risk_vector_x1000?.length || 19;
        const processed = {
            entities: [],
            groups: this.createEmptyGroups()
        };

        for (let i = 0; i < count; i++) {
            const entity = this.transformEntity(galaxy, i, stride);
            processed.entities.push(entity);
            
            // 1. Add Star to geometry group
            if (processed.groups[entity.visualType]) {
                this.addToGroup(processed.groups[entity.visualType], entity);
            }

            // 2. --- 2.1.D & 2.1.F SATELLITE REFRACTION ---
            if (entity.satellites && entity.satellites.length > 0) {
                
                // Calculate File-Level Composite Complexity (2.1.F.3)
                const hits = galaxy.hits ? galaxy.hits[i] : [];
                const structural = hits[this.HIT_INDICES.BRANCH] || 0;
                const defensive = (hits[this.HIT_INDICES.SAFETY] || 0) * 0.5;
                const compositeScore = structural + defensive;

                // Determine Fractal Depth (Step Function 2.1.F.4)
                let maxMoons = 0;
                if (compositeScore > 25) maxMoons = 12;      // "The Jungle"
                else if (compositeScore > 15) maxMoons = 8;  // "The Thicket"
                else if (compositeScore > 8) maxMoons = 4;   // "The Tree"
                else if (compositeScore > 2) maxMoons = 2;   // "The Fork"
                else maxMoons = 1;                           // "The Bamboo"

                // 2.1.D.4 Calculate Impact Scores and take the heaviest tools
                const scoredSats = entity.satellites.map(s => ({
                    raw: s,
                    impact: ((s[this.SAT_INDICES.BRANCH] + 1) * (s[this.SAT_INDICES.ARGS] + 1) + (0.05 * s[this.SAT_INDICES.LOC])) * 10
                }));
                
                // Filter by Impact and then Limit by Fractal Depth (Capped at 12)
                const topSats = scoredSats
                    .sort((a, b) => b.impact - a.impact)
                    .slice(0, Math.min(maxMoons, 12));

                topSats.forEach((satObj, sIdx) => {
                    const satEntity = this.transformSatellite(satObj.raw, entity, sIdx, topSats.length, raw.meta.lookups);
                    this.addToGroup(processed.groups.moon, satEntity);
                });
            }

            // 3. Handle Dependency Rings
            if (entity.importHits > 5) {
                const ringEntity = this.transformRing(entity);
                this.addToGroup(processed.groups.ring, ringEntity);
            }
        }

        return processed;
    }

    transformEntity(galaxy, i, stride = 19) {
        const loc = galaxy.locs[i];
        const m_loc = galaxy.m_locs[i];
        const mass = galaxy.mass[i];
        const hits = galaxy.hits ? galaxy.hits[i] : [];
        
        const logicRatio = (loc > 0) ? (m_loc / loc) : 0;
        
        // 2.1.C: Higher Fidelity Thresholds
        let type = 'sphere';
        if (mass < 200) type = 'dot';
        else if (logicRatio >= 0.975) type = 'tetra';   // Pure Logic
        else if (logicRatio >= 0.90) type = 'octa';     // Algorithmic
        else if (logicRatio >= 0.85) type = 'dodeca';   // Business Logic
        else if (logicRatio >= 0.75) type = 'icosa';    // Declarative
        else type = 'sphere';                           // Data/Config

        const realPopularity = (galaxy.popularity && galaxy.popularity[i]) || 
                               (galaxy.telemetry && galaxy.telemetry[i] ? galaxy.telemetry[i].popularity : 0) || 0;

        let r = Array(stride).fill(-10);
        if (galaxy.risks_flat) {
            r = galaxy.risks_flat.slice(i * stride, (i + 1) * stride);
        } else if (galaxy.risks && galaxy.risks[i]) {
            r = galaxy.risks[i];
        }

        return {
            id: i,
            name: galaxy.names[i],
            path: galaxy.paths[i],
            loc: loc,
            mass: mass,
            visualType: type,
            logicRatio: logicRatio,
            pos: { x: galaxy.pos_x[i] / 10.0, y: galaxy.pos_y[i] / 10.0, z: galaxy.pos_z[i] / 10.0 },
            risks: r,
            satellites: galaxy.satellites ? galaxy.satellites[i] : [],
            popularity: realPopularity,    // <--- Store the real value
            importHits: realPopularity     // <--- Wire rings to actual popularity, not regex hits!
        };
    }

    transformSatellite(sat, parent, sIdx, totalSats, lookups) {
        const sLoc = sat[this.SAT_INDICES.LOC];
        const sArgs = sat[this.SAT_INDICES.ARGS];
        const sLogicRatio = sat[this.SAT_INDICES.RATIO_X1000] / 1000.0;
        
        const nameStr = lookups && lookups.strings ? lookups.strings[sat[this.SAT_INDICES.NAME_ID]] : "Unknown";

        // 2.1.E Orbital Reach (Logarithmic)
        const dist = 60 + (Math.log2(Math.max(sLoc, 1)) * 30);
        
        // 2.1.G Logic Warp (Thinking vs Speaking)
        const sa = 22.5 + (1.0 - sLogicRatio) * 67.5;
        const spreadMultiplier = (sa / 90.0); // Normalizing angle to a scale factor

        // 3D Fibonacci Distribution (Phyllotaxis)
        const goldenAngle = 2.3999632; 
        const phi = Math.acos(1 - (2 * sIdx + 1) / totalSats); 
        const theta = goldenAngle * sIdx;

        return {
            parentId: parent.id,
            name: nameStr,
            magnitude: sat[this.SAT_INDICES.MAG_X10] / 10.0,
            loc: sLoc,
            branches: sat[this.SAT_INDICES.BRANCH],
            startLine: sat[this.SAT_INDICES.START_LINE],
            endLine: sat[this.SAT_INDICES.END_LINE],
            pos: {
                x: parent.pos.x + dist * Math.sin(phi * spreadMultiplier) * Math.cos(theta),
                y: parent.pos.y + dist * Math.cos(phi * spreadMultiplier),
                z: parent.pos.z + dist * Math.sin(phi * spreadMultiplier) * Math.sin(theta)
            },
            // 2.1.H Node Size (Logarithmic Args)
            scale: 1.0 + (Math.log2(Math.max(sArgs, 1)) * 0.2),
            risks: parent.risks // 1.1 DNA Inheritance: Inherit Parent Risk Vector
        };
    }

    transformRing(parent) {
        return {
            parentId: parent.id,
            pos: parent.pos,
            scale: 1.0 + (parent.importHits * 0.05),
            risks: parent.risks,
            rotation: { x: Math.PI / 2 + (parent.id * 0.1), y: (parent.id * 0.2), z: 0 }
        };
    }

    createEmptyGroups() {
        const keys = ['sphere', 'icosa', 'dodeca', 'octa', 'tetra', 'dot', 'moon', 'ring'];
        const groups = {};
        keys.forEach(k => {
            groups[k] = {
                positions: [], scales: [], rotations: [], satData: [], 
                attrs: { pack1: [], pack2: [], pack3: [], pack4: [], pack5: [], meta: [] },
                riskAttributes: this.createEmptyRiskAttributes()
            };
        });
        
        return groups;
    }

    createEmptyRiskAttributes() {
        return {
            cognitive: [], safety: [], debt: [], verification: [], api: [],
            concurrency: [], flux: [], graveyard: [], spec: [],
            stability: [], churn: [], doc: [], civil: [],
            popularity: [], globalId: []
        };
    }

    addToGroup(group, entity) {
        group.positions.push(entity.pos);
        group.scales.push(entity.scale || (1.0 + (Math.log2(Math.max(entity.mass, 1)) * 0.15)));
        group.rotations.push(entity.rotation || { x: Math.random(), y: Math.random(), z: 0 });
        
        if (entity.startLine !== undefined) {
            group.satData.push({
                name: entity.name,
                magnitude: entity.magnitude,
                loc: entity.loc,
                branches: entity.branches,
                startLine: entity.startLine,
                endLine: entity.endLine
            });
        }
        
        const r = entity.risks;
        const es = 1000.0;
        
        group.riskAttributes.cognitive.push((r[0] || 0) / es);
        group.riskAttributes.safety.push((r[1] || 0) / es);
        group.riskAttributes.debt.push((r[2] || 0) / es);
        group.riskAttributes.verification.push((r[3] || 0) / es);
        group.riskAttributes.api.push((r[4] || 0) / es);
        group.riskAttributes.concurrency.push((r[5] || 0) / es);
        group.riskAttributes.flux.push((r[6] || 0) / es);
        group.riskAttributes.graveyard.push((r[7] || 0) / es);
        group.riskAttributes.spec.push((r[8] || 0) / es);
        group.riskAttributes.stability.push((r[9] || 0) / es);
        group.riskAttributes.churn.push((r[10] || 0) / es);
        group.riskAttributes.doc.push((r[11] || 0) / es);
        group.riskAttributes.civil.push((r[12] || 0) / es);
        
        group.riskAttributes.popularity.push(entity.popularity);

        // Use Global ID for both stars and moons so the selection shader works correctly
        group.riskAttributes.globalId.push(entity.id !== undefined ? entity.id : entity.parentId);
    }
}