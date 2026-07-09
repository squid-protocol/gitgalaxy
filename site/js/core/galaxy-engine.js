/**
 * GitGalaxy
 * Copyright (c) 2026 Joe Esquibel
 *
 * This source code is licensed under the PolyForm Noncommercial License 1.0.0.
 * You may not use this file except in compliance with the License.
 * A copy of the license can be found in the LICENSE file in the root directory
 * of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
 */
import * as THREE from 'three';
import { DoubleSide } from 'three';

// 1. The Core Engine & Materials live here
import { 
    WebGPURenderer, 
    RenderPipeline, 
    MeshBasicNodeMaterial, 
    PointsNodeMaterial 
} from 'three/webgpu';

// 2. The Math, Logic, & Post-Processing Nodes live here
import {  
    uniform,  vec3, color,
    time, vec4, select,
    positionLocal, pass,
} from 'three/tsl';

import { bloom } from 'three/addons/tsl/display/BloomNode.js';

// 3. Import the custom shader logic!
import { createPhase6Shaders } from './phase-6-shaders.js';

export class GalaxyEngine {
    constructor() {
        this.viewport = document.getElementById('viewport');
        this.labelContainer = document.getElementById('label-container');
        this.maxInstancesPerGroup = 150000; 
        
        this.activeFiles = [];
        this.cameraRadius = 5000;
        this.cameraPhi = Math.PI / 4;
        this.cameraTheta = Math.PI / 3;
        this.targetPos = new THREE.Vector3(0, 0, 0);
        this.uWarpVelocity = uniform(0);
        this.dustFieldRadialScale = 1.0;
        
        // --- LOD & DETAIL UNIFORMS ---
        this.uMetricMode = uniform(0);
        this.uThemeIndex = uniform(0); 
        this.uSelectedGlobalId = uniform(-1.0);       // Force Float
        this.uSelectedConstellationId = uniform(-1.0); // Force Float
        this.uMoonFadeDist = uniform(5000.0); 
        this.uTime = time;

        this.lastInteractionTime = Date.now();
        this.isRotating = true;
        this.dragDist = 0;
        this.hoveredInfo = { mesh: null, id: -1, scale: { val: 1.0 } };
        
        this.labelsVisible = false;
        
        // --- NEW: DEPENDENCY TRACKERS ---
        this.linesGroup = new THREE.Group(); // Create it here, but DO NOT add it to the scene yet!
        this.linesVisible = false;      
        this.currentSourceId = -1; 
        this.currentTargetIds = [];     
        this.currentOutIds = []; // <--- ADD THIS LINE

        this.init();
    }

    async init() {
        const progress = (p) => {
            const el = document.getElementById('load-progress');
            if (el) el.style.width = p + '%';
        };
        
        this.renderer = new WebGPURenderer({ antialias: true, alpha: true });
        await this.renderer.init();
        // PERFORMANCE FIX: Clamp pixel ratio to 1.5. 
        // Prevents modern phones from trying to render at 3x or 4x native resolution,
        // which completely chokes mobile GPU fill-rates.
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.viewport.appendChild(this.renderer.domElement);

        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1.2;
        
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x010103);
        
        // --- FIX: ADD THE LINES GROUP HERE ---
        this.scene.add(this.linesGroup); 
        
        this.camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 10, 1000000);
        
        this.composer = new RenderPipeline(this.renderer); 
        const scenePass = pass(this.scene, this.camera);
        
        // --- NEW: DYNAMIC RESOLUTION SCALING ---
        const canvasHeight = this.renderer.domElement.height;
        const resScale = canvasHeight / 1080.0;

        // Make these class-level uniforms so the Poster generator can control them!
        this.uBloomRadius = uniform(0.1 * resScale);
        this.uBloomStrength = uniform(0.6 * Math.pow(resScale, 0.5));
        const staticThreshold = 0.4;

        // 🚨 THE FIX: Make the threshold a uniform so we can mathematically starve the bloom
        this.uBloomThreshold = uniform(0.4);
        const bloomNode = bloom(scenePass, this.uBloomStrength, this.uBloomRadius, this.uBloomThreshold);
        
        // 1. Combine the scene and the bloom into a single output
        // RESTORED: No select() branch, preserving your MSAA and high resolution!
        const composite = scenePass.add(bloomNode);
        
        // 2. Extract RGB directly and pass to the Tone Mapper
        this.composer.outputNode = vec4(vec3(composite), 1.0);

        // --- CRITICAL RESTORE: The Initialization Sequence ---
        this.initMaterials();
        this.initMeshes();
        this.setupEvents();
        
        setTimeout(() => {
            const loader = document.getElementById('loading-screen');
            if (loader) loader.style.opacity = '0';
            this.animate(); 
        }, 500);
    }

    initMaterials() {
        // Fetch the calculated nodes directly from the external shader file
        const { colorNode, opacityNode, moonOpacityNode } = createPhase6Shaders(this);

        // Assign the materials (THIS is where they legally belong)
        this.solidMat = new MeshBasicNodeMaterial({ transparent: true, colorNode, opacityNode, depthWrite: false });
        this.wireMat = new MeshBasicNodeMaterial({ transparent: true, colorNode, wireframe: true, opacityNode, depthWrite: false });
        this.moonMat = new MeshBasicNodeMaterial({ transparent: true, colorNode, opacityNode: moonOpacityNode, depthWrite: false });

        this.dustNodeMat = new PointsNodeMaterial({
            transparent: true,
            opacity: 0.7,
            size: 8,
            color: new THREE.Color(0x888888),
            blending: THREE.AdditiveBlending,
            depthWrite: false
        });

        const dustPos = positionLocal;
        const travel = this.uTime.mul(this.uWarpVelocity).mul(200000.0); 
        const wrappedZ = dustPos.z.add(travel).add(100000.0).mod(200000.0).sub(100000.0);
        this.dustNodeMat.positionNode = vec3(dustPos.x, dustPos.y, wrappedZ);
    }

    initMeshes() {
        this.geos = {
            sphere: new THREE.SphereGeometry(1, 16, 16),
            icosa: new THREE.IcosahedronGeometry(1, 0),
            dodeca: new THREE.DodecahedronGeometry(1, 0),
            octa: new THREE.OctahedronGeometry(1, 0),
            tetra: new THREE.TetrahedronGeometry(1, 0),
            dot: new THREE.SphereGeometry(1, 4, 4),
            moon: new THREE.SphereGeometry(3, 4, 4), // <-- Bump this from 1 to 2
            ring: new THREE.TorusGeometry(2, 0.05, 8, 32)
        };

        this.meshGroups = {};
        
        // FIX: Respect size parameter for packed memory alignment
        const createEmptyAttr = (size = 1) => new THREE.InstancedBufferAttribute(new Float32Array(this.maxInstancesPerGroup * size), size);

        Object.keys(this.geos).forEach(key => {
            const geo = this.geos[key];
            // =================================================================
            // [LLM CONTEXT: MOBILE GPU VERTEX ATTRIBUTE LIMITS]
            // Mobile WebGL2/WebGPU enforces a strict HARD LIMIT of 16 vertex attributes (slots).
            // - Three.js Base overhead: 3 slots (Position, Normal, UV)
            // - InstancedMesh Matrix: 4 slots (4x4 transform matrix)
            // - Available Custom Slots: 9 slots
            // - Currently Used Below: 6 slots
            // - REMAINING BUDGET: 3 slots (12 floats total).
            // IF EXCEEDED: The mobile GPU compiler will silently crash and nothing will render.
            // DO NOT add new attributes if the limit is reached; use bit-packing instead.
            // =================================================================
            // =================================================================
            // THE 8-BUFFER LIMIT FIX
            // Delete unused generated attributes (Normals/UVs) to free up 2 slots.
            // =================================================================
            geo.deleteAttribute('normal');
            geo.deleteAttribute('uv');

            geo.setAttribute('aRiskPack1', createEmptyAttr(4));
            geo.setAttribute('aRiskPack2', createEmptyAttr(4));
            geo.setAttribute('aRiskPack3', createEmptyAttr(4));
            geo.setAttribute('aRiskPack4', createEmptyAttr(4)); 
            geo.setAttribute('aRiskPack5', createEmptyAttr(4)); 
            geo.setAttribute('aMetaPack1', createEmptyAttr(4));
            // =================================================================
            // 🚨 [LLM CONTEXT: MOBILE GPU BUFFER LIMITS] 🚨
            // Future AI Agents: Do NOT add an `aMetaPack2` or any 7th custom attribute here.
            // Mobile GPUs have a hardcap of 8 Vertex Buffer Bindings.
            // Three.js uses 2 (Position + Matrix). We are using 6 custom attributes here.
            // Total = 8. Adding one more will cause a silent WebGL crash.
            // To add more data, compress it mathematically into existing floats (see pushAttrs).
            // =================================================================


            const isHighTier = ['icosa', 'dodeca', 'octa', 'tetra'].includes(key);
            let mat = isHighTier ? this.wireMat : this.solidMat;
            if (key === 'moon') mat = this.moonMat; // Use dedicated moon material

            const m = new THREE.InstancedMesh(geo, mat, this.maxInstancesPerGroup);
            m.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
            m.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, 0, 0), 99999999);
            m.frustumCulled = false;
            this.scene.add(m);
            this.meshGroups[key] = m;
            m.count = 0; 
        });

        // --- NEW: Spherical Dust Field Generation ---
        const dustCount = 10000;
        const dustGeo = new THREE.BufferGeometry();
        const dustPosArray = new Float32Array(dustCount * 3);
        const dRadius = 100000; // Radius of the star sphere
        
        for(let i = 0; i < dustCount; i++) {
            // Uniform spherical distribution
            const r = dRadius * Math.cbrt(Math.random()); 
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.acos(2 * Math.random() - 1);
            
            dustPosArray[i*3] = r * Math.sin(phi) * Math.cos(theta);
            dustPosArray[i*3+1] = r * Math.sin(phi) * Math.sin(theta);
            dustPosArray[i*3+2] = r * Math.cos(phi);
        }
        
        dustGeo.setAttribute('position', new THREE.BufferAttribute(dustPosArray, 3));
        this.dustField = new THREE.Points(dustGeo, this.dustNodeMat);        
        this.scene.add(this.dustField);

        // --- Black Hole / Singularity ---
        this.singularityGroup = new THREE.Group();
        const bhGeo = new THREE.SphereGeometry(1.5, 32, 32);
        const bhMat = new MeshBasicNodeMaterial({ colorNode: color(0x000000) });
        this.blackHoleMesh = new THREE.Mesh(bhGeo, bhMat);
        this.singularityGroup.add(this.blackHoleMesh);
        
        const diskGeo = new THREE.TorusGeometry(1.6, 0.15, 16, 100);
        const diskMat = new MeshBasicNodeMaterial({ colorNode: color(0xffffff).mul(4.0), transparent: true, opacity: 0.8, side: DoubleSide });
        this.accretionDisk = new THREE.Mesh(diskGeo, diskMat);
        this.accretionDisk.rotation.x = Math.PI / 2.5;
        this.singularityGroup.add(this.accretionDisk);
        
        this.scene.add(this.singularityGroup);
    }

    setupEvents() {
        this.mouse = new THREE.Vector2();
        this.raycaster = new THREE.Raycaster();
        const canvas = this.renderer.domElement;

        // Prevent the default browser context menu from appearing on right-click
        canvas.addEventListener('contextmenu', e => e.preventDefault());

        canvas.addEventListener('mousedown', (e) => {
            // Track left (0) and right (2) clicks separately
            if (e.button === 0) this.isLeftMouseDown = true;
            if (e.button === 2) this.isRightMouseDown = true;
            
            this.dragDist = 0;
            this.prevMouseX = e.clientX;
            this.prevMouseY = e.clientY;
        });

        window.addEventListener('mouseup', (e) => {
            if (e.button === 0) this.isLeftMouseDown = false;
            if (e.button === 2) this.isRightMouseDown = false;
        });

        canvas.addEventListener('mousemove', (e) => {
            this.lastInteractionTime = Date.now();
            this.isRotating = false;
            this.needsRaycast = true; // <--- ADD THIS LINE

            const rect = canvas.getBoundingClientRect();
            this.mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
            this.mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

            const dx = e.clientX - this.prevMouseX;
            const dy = e.clientY - this.prevMouseY;

            if (this.isLeftMouseDown || this.isRightMouseDown) {
                this.dragDist += Math.abs(dx) + Math.abs(dy);
            }

            if (this.isLeftMouseDown) {
                // LEFT CLICK: Pan the target across the galaxy
                this.pan(dx, dy);
            } else if (this.isRightMouseDown) {
                // RIGHT CLICK: Orbit the current target
                this.cameraPhi -= dx * 0.005;
                this.cameraTheta = THREE.MathUtils.clamp(this.cameraTheta - dy * 0.005, 0.1, Math.PI - 0.1);
            }

            if (this.isLeftMouseDown || this.isRightMouseDown) {
                this.prevMouseX = e.clientX;
                this.prevMouseY = e.clientY;
            }
        });

        canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            // Increased multiplier from 0.8 to 5.0 for much faster zooming
            this.cameraRadius = Math.max(100, Math.min(60000, this.cameraRadius + e.deltaY * 5.0));
        }, { passive: false });

        canvas.addEventListener('click', (e) => {
            // Only trigger star selection on a clean LEFT click
            if (e.button === 0 && this.dragDist < 10) {
                this.handleInteraction();
            }
        });

        window.addEventListener('resize', () => {
            // 🛑 THE FIX: Ignore resize events if the Gift Shop is rendering a poster!
            if (window.Poster && window.Poster.active) return; 

            this.camera.aspect = window.innerWidth / window.innerHeight;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(window.innerWidth, window.innerHeight);
        });

        // ==========================================
        // 📱 MOBILE TOUCH CONTROLS
        // ==========================================
        let prevTouchDist = 0;
        let prevTouchX = 0;
        let prevTouchY = 0;

        canvas.addEventListener('touchstart', (e) => {
            // Prevent the browser from pulling-to-refresh or zooming the whole webpage
            if (e.touches.length > 0) e.preventDefault();
            this.dragDist = 0;

            if (e.touches.length === 1) {
                prevTouchX = e.touches[0].clientX;
                prevTouchY = e.touches[0].clientY;
            } else if (e.touches.length === 2) {
                const dx = e.touches[0].clientX - e.touches[1].clientX;
                const dy = e.touches[0].clientY - e.touches[1].clientY;
                prevTouchDist = Math.hypot(dx, dy);
                prevTouchX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
                prevTouchY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
            }
        }, { passive: false });

        canvas.addEventListener('touchmove', (e) => {
            e.preventDefault();
            this.lastInteractionTime = Date.now();
            this.isRotating = false; // Stop idle rotation when user grabs it
            this.needsRaycast = true; // <--- ADD THIS LINE

            if (e.touches.length === 1) {
                // --- 1 FINGER: ORBIT ---
                const touch = e.touches[0];
                const dx = touch.clientX - prevTouchX;
                const dy = touch.clientY - prevTouchY;

                this.dragDist += Math.abs(dx) + Math.abs(dy);

                // Use the exact same math from your right-click orbit
                this.cameraPhi -= dx * 0.005;
                this.cameraTheta = THREE.MathUtils.clamp(this.cameraTheta - dy * 0.005, 0.1, Math.PI - 0.1);

                prevTouchX = touch.clientX;
                prevTouchY = touch.clientY;

            } else if (e.touches.length === 2) {
                // --- 2 FINGERS: PINCH ZOOM & PAN ---
                const touch1 = e.touches[0];
                const touch2 = e.touches[1];

                // 1. Pinch Zoom Math
                const dx = touch1.clientX - touch2.clientX;
                const dy = touch1.clientY - touch2.clientY;
                const dist = Math.hypot(dx, dy);
                const distDelta = prevTouchDist - dist;
                
                // Multiply by 15.0 to make the pinch feel responsive
                this.cameraRadius = Math.max(100, Math.min(60000, this.cameraRadius + distDelta * 15.0));
                prevTouchDist = dist;

                // 2. Pan Math (Moving two fingers together)
                const midX = (touch1.clientX + touch2.clientX) / 2;
                const midY = (touch1.clientY + touch2.clientY) / 2;
                const panDx = midX - prevTouchX;
                const panDy = midY - prevTouchY;

                this.dragDist += Math.abs(panDx) + Math.abs(panDy);

                // Use your existing left-click pan helper
                this.pan(panDx, panDy);

                prevTouchX = midX;
                prevTouchY = midY;
            }
        }, { passive: false });

        canvas.addEventListener('touchend', (e) => {
            // --- TAP TO SELECT ---
            // If it was a quick single tap (low drag distance), trigger the raycaster
            if (e.changedTouches.length === 1 && this.dragDist < 15) {
                const touch = e.changedTouches[0];
                const rect = canvas.getBoundingClientRect();
                
                // Update the global mouse vector for the raycaster
                this.mouse.x = ((touch.clientX - rect.left) / rect.width) * 2 - 1;
                this.mouse.y = -((touch.clientY - rect.top) / rect.height) * 2 + 1;

                this.handleInteraction();
            }
        });
    }
    
    checkHover() {
        this.raycaster.setFromCamera(this.mouse, this.camera);
        let currentHit = null;
        let hoveringBlackHole = false;

        // 1. Check if hovering the Black Hole OR the Accretion Disk
        if (this.singularityGroup.visible) {
            // The 'true' flag checks the whole group
            const bhHit = this.raycaster.intersectObject(this.singularityGroup, true);
            if (bhHit.length > 0) {
                hoveringBlackHole = true;
            }
        }

        // 2. Check if hovering any Stars
        const targets = ['sphere','icosa','dodeca','octa','tetra','dot'];
        for (let key of targets) {
            const hits = this.raycaster.intersectObject(this.meshGroups[key]);
            if (hits.length > 0) {
                currentHit = { mesh: this.meshGroups[key], id: hits[0].instanceId };
                break;
            }
        }

        // 3. Resolve Cursor and Hover Animations
        if (hoveringBlackHole) {
            // Un-scale any previously hovered star
            if (this.hoveredInfo.id !== -1) {
                this.animateScale(this.hoveredInfo, 1.0);
                this.hoveredInfo = { mesh: null, id: -1, scale: { val: 1.0 } };
            }
            document.body.style.cursor = 'pointer'; // Show hand pointer
            
        } else if (currentHit && (currentHit.mesh !== this.hoveredInfo.mesh || currentHit.id !== this.hoveredInfo.id)) {
            // Hovering a NEW star
            if (this.hoveredInfo.id !== -1) this.animateScale(this.hoveredInfo, 1.0);
            
            this.hoveredInfo = { mesh: currentHit.mesh, id: currentHit.id, scale: { val: 1.0 } };
            this.animateScale(this.hoveredInfo, 1.2);
            document.body.style.cursor = 'pointer'; // Show hand pointer
            
        } else if (!currentHit) {
            // Pointing at empty space - CLEAN UP
            if (this.hoveredInfo.id !== -1) {
                this.animateScale(this.hoveredInfo, 1.0);
                this.hoveredInfo = { mesh: null, id: -1, scale: { val: 1.0 } };
            }
            document.body.style.cursor = 'default'; // Reset to standard arrow
        }
    }

    animateScale(info, target) {
        new TWEEN.Tween(info.scale)
            .to({ val: target }, 200)
            .easing(TWEEN.Easing.Back.Out)
            .start();
    }

    handleInteraction() {
        this.raycaster.setFromCamera(this.mouse, this.camera);
        
        // 1. --- Check if we clicked the Black Hole OR the Accretion Disk ---
        if (this.singularityGroup.visible) {
            // The 'true' flag forces it to check all child meshes inside the group
            const bhHit = this.raycaster.intersectObject(this.singularityGroup, true); 
            if (bhHit.length > 0) {
                this.flyTo(new THREE.Vector3(0, 0, 0), -2); // -2 is our special ID for the Singularity
                this.showSingularityHUD();
                return; // Stop execution so it doesn't process stars or hide the HUD
            }
        }

        // 2. --- Original Star Check ---
        let hit = null;
        const targetGroups = ['sphere', 'icosa', 'dodeca', 'octa', 'tetra', 'dot'];
        for (let key of targetGroups) {
            const intersects = this.raycaster.intersectObject(this.meshGroups[key]);
            if (intersects.length > 0) {
                hit = { mesh: this.meshGroups[key], id: intersects[0].instanceId };
                break;
            }
        }

        // 3. --- Handle Star Click or Miss ---
        if (hit) {
            // 🚨 THE MOBILE FIX: Open the new suitcase to find the ID 
            const metaPackAttr = hit.mesh.geometry.getAttribute('aMetaPack1');
            if (!metaPackAttr) return;
            
            // Extract the 'Z' compartment where we packed the Global ID
            const globalId = Math.round(metaPackAttr.getZ(hit.id)); 
            
            const matrix = new THREE.Matrix4();
            hit.mesh.getMatrixAt(hit.id, matrix);
            const worldPos = new THREE.Vector3().setFromMatrixPosition(matrix);
            
            this.flyTo(worldPos, globalId);
            this.showHUD(globalId);
        } else {
            // If we clicked empty space (and didn't click the black hole above)
            this.hideHUD();
        }
    }

    showHUD(globalId) {
        this.uSelectedGlobalId.value = globalId;
        const raw = window.currentRawGalaxyData;
        
        if (window.selectionMode === 'constellation' && raw) {
            const cId = raw.galaxy.c_ids ? raw.galaxy.c_ids[globalId] : -1;
            this.uSelectedConstellationId.value = cId; 
            
            if (cId !== -1) {
                const cName = raw.meta.schemas.lookups.constellations[cId];
                // Clone stats to avoid mutating the original JSON object
                const stats = JSON.parse(JSON.stringify(raw.global_summary.constellations[cName] || {}));
                const files = [];
                
                // --- THE FIX: Dynamically recalculate averages, explicitly excluding unscanned (-10) files ---
                const riskTotals = {};
                const riskCounts = {};
                const RISK_LENGTH = raw.meta?.schemas?.risk_vector_x1000?.length || 18;
                const riskSchema = raw.meta?.schemas?.risk_vector_x1000 || [];

                for (let i = 0; i < raw.galaxy.names.length; i++) {
                    if (raw.galaxy.c_ids[i] === cId) {
                        const langStr = raw.meta.schemas.lookups.languages[raw.galaxy.lang_ids[i]] || "UNKNOWN";
                        files.push({ name: raw.galaxy.names[i], lang: langStr });

                        // Aggregate risks strictly for this constellation
                        const rStart = i * RISK_LENGTH;
                        const fileRisks = raw.galaxy.risks_flat ? raw.galaxy.risks_flat.slice(rStart, rStart + RISK_LENGTH) : [];
                        
                        for (let j = 0; j < fileRisks.length; j++) {
                            const val = fileRisks[j];
                            if (val >= 0) { // Exclude -10 (Unscanned) values
                                const key = riskSchema[j];
                                if (!riskTotals[key]) {
                                    riskTotals[key] = 0;
                                    riskCounts[key] = 0;
                                }
                                riskTotals[key] += (val / 10.0); // Convert back to 0-100 scale
                                riskCounts[key]++;
                            }
                        }
                    }
                }

                // Apply the true averages
                stats.avg_exposures = {};
                for (let k = 0; k < riskSchema.length; k++) {
                    const key = riskSchema[k];
                    stats.avg_exposures[key] = riskCounts[key] > 0 ? (riskTotals[key] / riskCounts[key]) : -1.0;
                }
                
                if (window.updateConstellationHUD) {
                    window.updateConstellationHUD(cName, stats, files);
                    return;
                }
            }
        } else {
            this.uSelectedConstellationId.value = -1;
        }

        if (window.App && window.App.syncSelection) {
            window.App.syncSelection();
        }
    }


    showSingularityHUD() {
        console.log("Engine: Singularity clicked. Data payload:", this.singularityData);
        
        if (!this.singularityData) {
            console.warn("Engine: Aborting HUD. No singularity data found in memory.");
            return;
        }
        
        if (window.updateSingularityHUD) {
            console.log("Engine: Triggering UI overlay...");
            window.updateSingularityHUD(this.singularityData);
        } else {
            console.error("Engine Error: window.updateSingularityHUD is not defined in the DOM!");
        }
    }

    hideHUD() {
        // UNIFIED LOGIC: Trigger the global hide animation
        if (window.hideHUDUI) window.hideHUDUI();
        this.uSelectedGlobalId.value = -1;
        this.uSelectedConstellationId.value = -1; // <--- ADD THIS LINE
    }

    flyTo(pos, globalId) {
        this.uSelectedGlobalId.value = globalId;

        // Smoothly pan the target position to the star
        new TWEEN.Tween(this.targetPos)
            .to({ x: pos.x, y: pos.y, z: pos.z }, 2300)
            .easing(TWEEN.Easing.Quartic.InOut)
            .start();
            
        // Smoothly zoom the camera in
        new TWEEN.Tween(this)
            .to({ cameraRadius: 1500 }, 2300)
            .easing(TWEEN.Easing.Quartic.InOut)
            .start();
    }

    hyperspaceJump(onMidpoint) {
        this.hideHUD();

        // --- NEW: Purge network artifacts before warp ---
        this.clearDependencyLines();
        this.linesVisible = false;
        
        if (this.globalWebMesh) {
            this.scene.remove(this.globalWebMesh);
            this.globalWebMesh.children.forEach(child => {
                child.geometry.dispose();
                child.material.dispose();
            });
            this.globalWebMesh = null;
        }
        
        // THE FIX: Master timing variables (in milliseconds)
        const diveTime = 2500; 
        const voidPause = 50;
        const emergenceTime = 2000;

        // --- PHASE 1: THE EVENT HORIZON DIVE ---
        new TWEEN.Tween(this.targetPos)
            .to({ x: 0, y: 0, z: 0 }, diveTime)
            .easing(TWEEN.Easing.Cubic.InOut)
            .start();

        new TWEEN.Tween(this)
            .to({ cameraRadius: 1.6 }, diveTime) // Dive into the singularity
            .easing(TWEEN.Easing.Cubic.In)
            .start();

        new TWEEN.Tween(this.uWarpVelocity)
            .to({ value: 4.0 }, diveTime)
            .easing(TWEEN.Easing.Quartic.In)
            .start();

        new TWEEN.Tween(this.camera)
            .to({ fov: 160 }, diveTime)
            .easing(TWEEN.Easing.Quartic.In)
            .onUpdate(() => this.camera.updateProjectionMatrix())
            .start();

        // --- PHASE 2 & 3: THE WHITE HOLE EMERGENCE ---
        // Dynamically waits for the dive to finish, plus the void pause
        setTimeout(() => {
            // EXECUTING THE CALLBACK: Swap the old galaxy for the new one!
            if (onMidpoint) onMidpoint();

            // 1. Lock the gaze dead-center on the black hole
            this.targetPos.set(0, 0, 0);

            // 2. Set a beautiful, cinematic off-axis angle
            this.cameraPhi = Math.PI / 4; 
            this.cameraTheta = Math.PI / 3;

            this.dustFieldRadialScale = 1.0;

            // 3. THE REVEAL: Pull the camera backward
            new TWEEN.Tween(this)
                .to({ cameraRadius: 6000 }, emergenceTime) 
                .easing(TWEEN.Easing.Cubic.Out)
                .start();

            new TWEEN.Tween(this.uWarpVelocity)
                .to({ value: 0 }, emergenceTime)
                .easing(TWEEN.Easing.Quartic.Out)
                .start();
                
            new TWEEN.Tween(this.camera)
                .to({ fov: 60 }, emergenceTime)
                .easing(TWEEN.Easing.Quartic.Out)
                .onUpdate(() => this.camera.updateProjectionMatrix())
                .start();

        }, diveTime + voidPause); 
    }

    loadSector(raw) {
        Object.values(this.meshGroups).forEach(m => m.count = 0);
        this.labelContainer.innerHTML = '';
        
        const names = raw.galaxy.names || [];
        const count = names.length;

        // --- PHASE 1 & 3: LOD DENSITY SCALING ---
        const maxDist = 2500 + 7500 * Math.exp(-count / 5000);
        this.uMoonFadeDist.value = maxDist;

        // Handle Singularity
        const sigData = raw.singularity; // Grab directly from the root
        const ambigCount = sigData?.paths?.length || 0; // Count is the length of the columnar array

        if (sigData && ambigCount > 0) {
            this.singularityData = sigData;
            // Inject the count back so the HTML HUD can read it
            this.singularityData.ambig_file_count = ambigCount;
            this.singularityData.visible_percent = raw.global_summary?.summary?.Percent_Visible || 0; 
            this.singularityGroup.visible = true;
            
            // Calculate scale based on the array length
            const bhScale = 20 + Math.pow(ambigCount, 0.5) * 5; 
            this.singularityGroup.scale.setScalar(bhScale);
        } else {
            this.singularityGroup.visible = false;
        }

        this.activeFiles = [];
        const dummy = new THREE.Object3D();
        const groupData = {};

        // 1. Restore standard vec4 arrays
        Object.keys(this.meshGroups).forEach(key => {
            groupData[key] = { 
                matrices: [], 
                attrs: { pack1: [], pack2: [], pack3: [], pack4: [], pack5: [], meta: [], meta2: [] } 
            };
        });

        const languages = raw.meta?.schemas?.lookups?.languages || [];
        const pScalar = raw.meta?.scalars?.physics || 10;



        // How many elements are in each flattened vector per star?
        const RISK_LENGTH = raw.meta?.schemas?.risk_vector_x1000?.length || 18;
        const HIT_LENGTH = raw.meta?.schemas?.hit_vector?.length || 60;

        for (let i = 0; i < count; i++) {
            const loc = raw.galaxy.locs[i];
            const mass = raw.galaxy.mass[i];
            
            // --- NEW: Slice the flattened risk array for this specific star ---
            const rStart = i * RISK_LENGTH;
            const risks = raw.galaxy.risks_flat ? raw.galaxy.risks_flat.slice(rStart, rStart + RISK_LENGTH) : Array(RISK_LENGTH).fill(-10);
            
            const m_loc = raw.galaxy.m_locs ? raw.galaxy.m_locs[i] : 0;
            const logicRatio = (loc > 0) ? (m_loc / loc) : 0;
            const langString = languages[raw.galaxy.lang_ids[i]] || "UNKNOWN";
            const langHex = window.Colors ? window.Colors.getLanguageColor(langString) : 0xffffff;
            const rVal = ((langHex >> 16) & 255) / 255;
            const gVal = ((langHex >> 8) & 255) / 255;
            const bVal = (langHex & 255) / 255;
            
            // 1. STAR INSTANTIATION
            let type = 'sphere';
            if (mass < 200) type = 'dot';
            else if (logicRatio >= 0.975) type = 'tetra';
            else if (logicRatio >= 0.90) type = 'octa';
            else if (logicRatio >= 0.85) type = 'dodeca';
            else if (logicRatio >= 0.75) type = 'icosa';

            const starGroup = groupData[type];
            const x = raw.galaxy.pos_x[i] / pScalar;
            const y = raw.galaxy.pos_y[i] / pScalar;
            const z = raw.galaxy.pos_z[i] / pScalar;
            
            dummy.position.set(x, y, z);
            const scale = 10 + Math.pow(mass, 1/3) * 2.1;
            dummy.scale.setScalar(type === 'dot' ? scale * 0.5 : scale);
            dummy.rotation.set(Math.random(), Math.random(), 0);
            dummy.updateMatrix();
            
            starGroup.matrices.push({ matrix: dummy.matrix.clone(), baseScale: dummy.scale.x, pos: new THREE.Vector3(x,y,z), rot: dummy.rotation.clone() });
            
            // --- NEW: Slice the flattened hit array for this specific star ---
            const hStart = i * HIT_LENGTH;
            const hits = raw.galaxy.hits_flat ? raw.galaxy.hits_flat.slice(hStart, hStart + HIT_LENGTH) : Array(HIT_LENGTH).fill(0);
            
            const importCount = hits[23] || 0; 
            const popScore = Math.min(Math.log2(Math.max(importCount, 1)) / 6.0, 1.0);
            
            const labelEl = document.createElement('div');
            labelEl.className = 'star-label'; 
            labelEl.textContent = names[i];
            labelEl.style.display = 'none';
            this.labelContainer.appendChild(labelEl);

            const doc_loc = raw.galaxy.d_locs ? raw.galaxy.d_locs[i] : 0;
            const tel = raw.galaxy.telemetry ? raw.galaxy.telemetry[i] : {};
            const popRank = tel.pop || 0;
            const sats = raw.galaxy.satellites ? raw.galaxy.satellites[i] : [];

            this.activeFiles.push({ 
                name: names[i], path: raw.galaxy.paths[i] || "UNKNOWN", lang: langString, 
                loc: loc, m_loc: m_loc, d_loc: doc_loc, mass: mass,
                risks: risks, sats_count: sats.length, sats_data: sats, popRank: popRank,
                logicRatio: logicRatio, importCount: importCount, pos: new THREE.Vector3(x, y, z),
                el: labelEl, baseScale: dummy.scale.x     
            });



            // 2. Push attributes back into standard 4-float vectors
            const pushAttrs = (g, targetGid, targetCid) => { 
                const es = 1000.0;
                
                // --- THE FIX: Handle array of arrays AND correct the lookup path ---
                const clusterData = raw.galaxy.a_ids ? raw.galaxy.a_ids[i] : 0;
                let clusterId = Array.isArray(clusterData) ? clusterData[0] : clusterData;
                
                // =================================================================
                // 🚨 DATA COMPRESSION: BUFFER OVERFLOW PREVENTION 🚨
                // We pack `clusterId` (integer) and `popScore` (decimal) into ONE float.
                // e.g., clusterId 12 + popScore 0.85 = 12.85.
                // This eliminates the need for an extra buffer, keeping us strictly under
                // the mobile GPU 8-buffer limit. Unpacked in the shader via floor/fract.
                // =================================================================
                
                // Try to get the string from the lookups table (where it actually lives!)
                const archetypesList = raw.meta?.schemas?.lookups?.archetypes || [];
                const archString = archetypesList[clusterId] || "";
                
                let absoluteClusterId = 15; // Default to 15 (Slate Gray)
                
                // If the string exists, regex it. If not, maybe clusterId IS the absolute ID (legacy support)
                const match = archString.match(/Cluster (\d+)/);
                if (match) {
                    absoluteClusterId = parseInt(match[1], 10);
                } else if (typeof clusterId === 'number' && clusterId >= 0 && clusterId <= 15) {
                    absoluteClusterId = clusterId; // Legacy fallback for older JSONs
                }



                // Now pack the absolute ID into your metadata float
                const safePopScore = Math.min(popScore, 0.999);
                const packedMeta = absoluteClusterId + safePopScore;

                g.attrs.pack1.push((risks[0]||0)/es, (risks[1]||0)/es, (risks[2]||0)/es, (risks[3]||0)/es);
                g.attrs.pack2.push((risks[4]||0)/es, (risks[5]||0)/es, (risks[6]||0)/es, (risks[7]||0)/es);
                g.attrs.pack3.push((risks[8]||0)/es, (risks[9]||0)/es, (risks[10]||0)/es, (risks[11]||0)/es);
                g.attrs.pack4.push((risks[13]||0)/es, (risks[14]||0)/es, (risks[15]||0)/es, (risks[16]||0)/es);
                g.attrs.pack5.push((risks[17]||0)/es, rVal, gVal, bVal); 
                g.attrs.meta.push((risks[12]||0)/es, packedMeta, targetGid, targetCid);
            };

            const cId = raw.galaxy.c_ids ? raw.galaxy.c_ids[i] : -1; // <-- Grab it from JSON
            pushAttrs(starGroup, i, cId); // <-- Pass it in for the star

            // 2. SATELLITE (MOON) REFRACTION
            // --- NEW: Hard-cull satellites for massive galaxies to save geometry ---
            const moonGroup = groupData['moon'];

            // Calculate Composite Score for fractal depth
            const structural = hits[0] || 0; 
            const defensive = (hits[9] || 0) * 0.5;
            const compositeScore = structural + defensive;

            // --- NEW: Reconstruct the Satellite array from the flattened data ---
            let moonData = sats; // Fallback to the original array if flat map isn't available
            
            if (raw.galaxy.satellite_data_flat && raw.galaxy.satellite_offsets) {
                moonData = []; // clear and build from flat data
                const startOffset = i === 0 ? 0 : raw.galaxy.satellite_offsets[i - 1];
                const endOffset = raw.galaxy.satellite_offsets[i];
                
                // Each satellite has exactly 10 properties in the flat array
                for (let j = startOffset; j < endOffset; j++) {
                    const sIdx = j * 10;
                    moonData.push([
                        raw.galaxy.satellite_data_flat[sIdx],      // name
                        raw.galaxy.satellite_data_flat[sIdx + 1],  // loc
                        raw.galaxy.satellite_data_flat[sIdx + 2],  // branch
                        raw.galaxy.satellite_data_flat[sIdx + 3],  // angle
                        raw.galaxy.satellite_data_flat[sIdx + 4],  // args
                        raw.galaxy.satellite_data_flat[sIdx + 5],  // texture
                        raw.galaxy.satellite_data_flat[sIdx + 6],  // cfr
                        raw.galaxy.satellite_data_flat[sIdx + 7],  // impact
                        raw.galaxy.satellite_data_flat[sIdx + 8],  // start_line
                        raw.galaxy.satellite_data_flat[sIdx + 9]   // end_line
                    ]);
                }
            }

            let maxMoons = 1; // Level 0: The Bamboo
            if (compositeScore > 25) maxMoons = 12;      // Level 4: The Jungle
            else if (compositeScore > 15) maxMoons = 8;  // Level 3: The Thicket
            else if (compositeScore > 8) maxMoons = 4;   // Level 2: The Tree
            else if (compositeScore > 2) maxMoons = 2;   // Level 1: The Fork
            
            // --- 2. IMPACT SCORING & FILTERING ---
            const scoredSats = moonData.map(s => ({
                    raw: s,
                    impact: ((s[2] + 1) * (s[4] + 1) + (0.05 * s[1])) * 10
                })).sort((a, b) => b.impact - a.impact).slice(0, Math.min(maxMoons, 12));

                const totalMoons = scoredSats.length;
                const goldenAngle = 2.3999632; 

                scoredSats.forEach((satObj, sIdx) => {
                    const s = satObj.raw;
                    const sLoc = s[1];
                    const sArgs = s[4];
                    
                    const dist = 60 + (Math.log2(Math.max(sLoc, 1)) * 30);
                    
                    // Standard 3D Fibonacci distribution
                    const phi = Math.acos(1 - (2 * sIdx + 1) / totalMoons); 
                    const theta = goldenAngle * sIdx;
                    
                    // THE FIX: Removed 'spreadMultiplier' to allow full 360-degree orbits
                    const mX = x + dist * Math.sin(phi) * Math.cos(theta);
                    const mY = y + dist * Math.cos(phi);
                    const mZ = z + dist * Math.sin(phi) * Math.sin(theta);
                    
                    dummy.position.set(mX, mY, mZ);
                    const mScale = 1.0 + (Math.log2(Math.max(sArgs, 1)) * 0.2);
                    dummy.scale.setScalar(mScale);
                    
                    // Point the moon's rotation vaguely toward its parent star
                    dummy.rotation.set(Math.random(), Math.random(), 0);
                    dummy.updateMatrix();
                    
                    moonGroup.matrices.push({ matrix: dummy.matrix.clone(), baseScale: mScale, pos: new THREE.Vector3(mX, mY, mZ), rot: dummy.rotation.clone() });
                    pushAttrs(moonGroup, i, cId); // Inherit Star GID and DNA
                });
            }

        Object.keys(groupData).forEach(key => {
            const g = groupData[key];
            const mesh = this.meshGroups[key];
            mesh.count = g.matrices.length;
            mesh.userData.instanceData = g.matrices; 
            if (mesh.count === 0) return;
            
            g.matrices.forEach((m, idx) => mesh.setMatrixAt(idx, m.matrix));
            mesh.instanceMatrix.needsUpdate = true;
            
            const setAttr = (n, d, size) => mesh.geometry.setAttribute(n, new THREE.InstancedBufferAttribute(new Float32Array(d), size));
            
            setAttr('aRiskPack1', g.attrs.pack1, 4); 
            setAttr('aRiskPack2', g.attrs.pack2, 4); 
            setAttr('aRiskPack3', g.attrs.pack3, 4);
            setAttr('aRiskPack4', g.attrs.pack4, 4); 
            setAttr('aRiskPack5', g.attrs.pack5, 4); 
            setAttr('aMetaPack1', g.attrs.meta, 4);
        });

        const statNodesEl = document.getElementById('stat-nodes');
        if (statNodesEl) statNodesEl.innerText = count.toLocaleString();
    }

    animate() {
        if (window.GalaxyScope) window.GalaxyScope.update(this.renderer);
        requestAnimationFrame(() => this.animate());
        TWEEN.update();

        // 1. REAL-TIME IDLE CHECK (Strictly 5 seconds)
        if (Date.now() - this.lastInteractionTime > 5000) {
            this.isRotating = true;
            this.cameraPhi += 0.0005;
        }

        // PERFORMANCE FIX: Only calculate hover intersections if the mouse actually moved
        if (this.needsRaycast) {
            this.checkHover();
            this.needsRaycast = false;
        }

        if (this.hoveredInfo.id !== -1) {
            const mesh = this.hoveredInfo.mesh;
            const idx = this.hoveredInfo.id;
            const data = mesh.userData.instanceData[idx];
            const dummy = new THREE.Object3D();
            dummy.position.copy(data.pos);
            dummy.rotation.copy(data.rot);
            dummy.scale.setScalar(data.baseScale * this.hoveredInfo.scale.val);
            dummy.updateMatrix();
            mesh.setMatrixAt(idx, dummy.matrix);
            mesh.instanceMatrix.needsUpdate = true;
        }

        // Calculate the spherical coordinates and offset them by the current pan target
        const x = this.targetPos.x + this.cameraRadius * Math.sin(this.cameraTheta) * Math.cos(this.cameraPhi);
        const y = this.targetPos.y + this.cameraRadius * Math.cos(this.cameraTheta);
        const z = this.targetPos.z + this.cameraRadius * Math.sin(this.cameraTheta) * Math.sin(this.cameraPhi);

        // APPLY THE MATH TO THE CAMERA
        this.camera.position.set(x, y, z);
        this.camera.lookAt(this.targetPos);

        // --- NEW: WARP EFFECT ALIGNMENT ---
        if (this.uWarpVelocity.value > 0.05) {
            // During warp, lock orientation to the camera so the streaks fly perfectly past the lens
            this.dustField.quaternion.copy(this.camera.quaternion);
        } else {
            // THE FIX: We removed rotateX and rotateY here!
            // When idle, the dust field now stays completely stationary.
            // True parallax is achieved entirely by the camera moving through the space.
        }
        
        // Stretch the dust container into streaks based on warp velocity
        const warpStretch = 1.0 + (this.uWarpVelocity.value * 50.0);
        this.dustField.scale.set(this.dustFieldRadialScale, this.dustFieldRadialScale, warpStretch);

        // --- 3D TO 2D LABEL PROJECTION ---
        if (this.labelsVisible) {
            const camPos = this.camera.position;
            const halfW = window.innerWidth / 2;
            const halfH = window.innerHeight / 2;
            
            // LOD Settings: Taper off labels that are too far away
            // 🚨 TIGHTENED: You now must be significantly closer to see the text
            const maxDist = 1200;  // Slashed from 3500
            const fadeStart = 500; // Slashed from 1500

            this.activeFiles.forEach(f => {
                if (!f.el) return;
                
                const dist = f.pos.distanceTo(camPos);
                
                if (dist < maxDist) {
                    // Spatial Offset: Lift the label above the star's geometry
                    const v = f.pos.clone();
                    v.y += (f.baseScale || 10) + 15; 

                    v.project(this.camera);

                    // Frustum check: z > 1 means it's behind the camera
                    if (v.z > 1 || v.x < -1 || v.x > 1 || v.y < -1 || v.y > 1) {
                        // PERFORMANCE FIX: Only touch the DOM if we actually need to change the state
                        if (f.el.style.display !== 'none') f.el.style.display = 'none';
                    } else {
                        if (f.el.style.display !== 'block') f.el.style.display = 'block';
                        
                        const x = (v.x * halfW) + halfW;
                        const y = -(v.y * halfH) + halfH;
                        
                        f.el.style.transform = `translate(-50%, -50%) translate(${x}px, ${y}px)`;
                        
                        // Opacity Taper: Gracefully fade out distant labels
                        let opacity = 1.0;
                        if (dist > fadeStart) {
                            opacity = 1.0 - ((dist - fadeStart) / (maxDist - fadeStart));
                        }
                        f.el.style.opacity = opacity.toFixed(2);
                    }
                } else {
                    f.el.style.display = 'none';
                }
            });
        }
        
        // --- CLEAN BACKGROUND FIX ---
        // Hide the space dust entirely in High-Vis mode to keep the canvas stark and clean
        if (this.dustField) {
            this.dustField.visible = (this.uThemeIndex.value !== 4);
        }
        
        // Render via the post-processing stack instead of the renderer
        this.composer.render();    
    }

    pan(deltaX, deltaY) {
        // Scale the panning speed based on how far zoomed out you are.
        // This ensures panning feels consistent whether you are close to a star or viewing the whole galaxy.
        const panSpeed = this.cameraRadius * 0.001;
        
        const offset = new THREE.Vector3();
        const vRight = new THREE.Vector3();
        const vUp = new THREE.Vector3();

        // Extract the camera's local X (Right) and Y (Up) axes
        this.camera.matrixWorld.extractBasis(vRight, vUp, new THREE.Vector3());

        // Move the target negatively along the right vector for horizontal mouse movement
        vRight.multiplyScalar(-deltaX * panSpeed);
        
        // Move the target positively along the up vector for vertical mouse movement
        vUp.multiplyScalar(deltaY * panSpeed);

        offset.add(vRight).add(vUp);
        this.targetPos.add(offset);
    }

    clearDependencyLines() {
    while(this.linesGroup.children.length > 0) { 
        const child = this.linesGroup.children[0];
        this.linesGroup.remove(child); 
        child.geometry.dispose();
        child.material.dispose();
    }
    }

    drawDependencyLines(sourceId, inIds, outIds, positions, pScalar) {
        this.currentSourceId = sourceId;
        this.currentTargetIds = inIds;
        this.currentOutIds = outIds; // Store the outbound targets
        this.clearDependencyLines();

        // Abort if the toggle is off or there are absolutely no connections
        if (!this.linesVisible || (!inIds.length && !outIds.length)) return;

        const sx = positions.pos_x[sourceId] / pScalar;
        const sy = positions.pos_y[sourceId] / pScalar;
        const sz = positions.pos_z[sourceId] / pScalar;
        const startPoint = new THREE.Vector3(sx, sy, sz);

        // --- 1. DRAW INBOUND (GOLD) ---
        if (inIds && inIds.length > 0) {
            const inMat = new THREE.LineBasicMaterial({ 
                color: 0xffcc00, transparent: true, opacity: 0.25, blending: THREE.NormalBlending 
            });

            inIds.forEach(tId => {
                const tx = positions.pos_x[tId] / pScalar;
                const ty = positions.pos_y[tId] / pScalar;
                const tz = positions.pos_z[tId] / pScalar;
                const endPoint = new THREE.Vector3(tx, ty, tz);

                const distance = startPoint.distanceTo(endPoint);
                const midPoint = new THREE.Vector3().addVectors(startPoint, endPoint).multiplyScalar(0.5);
                midPoint.y += distance * 0.3; // Gold arcs UPWARD

                const curve = new THREE.QuadraticBezierCurve3(startPoint, midPoint, endPoint);
                const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(curve.getPoints(50)), inMat);
                this.linesGroup.add(line);
            });
        }

        // --- 2. DRAW OUTBOUND (MAGENTA/PINK) ---
        if (outIds && outIds.length > 0) {
            const outMat = new THREE.LineBasicMaterial({ 
                color: 0xff007f, transparent: true, opacity: 0.25, blending: THREE.NormalBlending 
            });

            outIds.forEach(tId => {
                const tx = positions.pos_x[tId] / pScalar;
                const ty = positions.pos_y[tId] / pScalar;
                const tz = positions.pos_z[tId] / pScalar;
                const endPoint = new THREE.Vector3(tx, ty, tz);

                const distance = startPoint.distanceTo(endPoint);
                const midPoint = new THREE.Vector3().addVectors(startPoint, endPoint).multiplyScalar(0.5);
                midPoint.y -= distance * 0.2; // Magenta arcs DOWNWARD

                const curve = new THREE.QuadraticBezierCurve3(startPoint, midPoint, endPoint);
                const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(curve.getPoints(50)), outMat);
                this.linesGroup.add(line);
            });
        }
    }

    toggleDependencyLines(visible, positions, pScalar) {
        this.linesVisible = visible;
        if (visible) {
            this.drawDependencyLines(this.currentSourceId, this.currentTargetIds, this.currentOutIds, positions, pScalar);
        } else {
            this.clearDependencyLines();
        }
    }

    toggleGlobalWeb(visible, rawGalaxy, pScalar) {
        if (!visible) {
            if (this.globalWebMesh) this.globalWebMesh.visible = false;
            return;
        }

        // If we already built the giant mesh, just unhide it
        if (this.globalWebMesh) {
            this.globalWebMesh.visible = true;
            return;
        }

        // Otherwise, calculate the massive dual-layered global web
        this.globalWebMesh = new THREE.Group();
        
        const inPoints = [];
        const outPoints = [];
        const edges = rawGalaxy.edges;

        if (!edges) {
            console.warn("GalaxyEngine: No dependency edges found in this dataset.");
            return;
        }
        
        // --- ADAPTIVE PERFORMANCE LIMITER ---
        const isMassiveGalaxy = rawGalaxy.names.length > 20000;
        let orchestratorThreshold = 2; // Default (TITAN)

        // Stiffen the limits based on the active telemetry tier
        if (this.currentQualityTier === 'STANDARD') {
            orchestratorThreshold = isMassiveGalaxy ? 15 : 5;
        } else if (this.currentQualityTier === 'POTATO') {
            orchestratorThreshold = isMassiveGalaxy ? 50 : 15;
        }
        
        for (let i = 0; i < edges.length; i++) {
            const targets = edges[i];
            
            // CULLING: Skip drawing lines for files below the threshold
            if (!targets || targets.length < orchestratorThreshold) continue; 
            
            const sx = rawGalaxy.pos_x[i] / pScalar;
            const sy = rawGalaxy.pos_y[i] / pScalar;
            const sz = rawGalaxy.pos_z[i] / pScalar;
            const startPoint = new THREE.Vector3(sx, sy, sz);
            
            targets.forEach(tId => {
                const tx = rawGalaxy.pos_x[tId] / pScalar;
                const ty = rawGalaxy.pos_y[tId] / pScalar;
                const tz = rawGalaxy.pos_z[tId] / pScalar;
                const endPoint = new THREE.Vector3(tx, ty, tz);
                
                const distance = startPoint.distanceTo(endPoint);
                const midBase = new THREE.Vector3().addVectors(startPoint, endPoint).multiplyScalar(0.5);
                
                // 1. Gold Arcs UP (Inbound)
                const midUp = midBase.clone();
                midUp.y += distance * 0.3; // Matches local view height
                const curveUp = new THREE.QuadraticBezierCurve3(startPoint, midUp, endPoint);
                const ptsUp = curveUp.getPoints(10); // Low-poly for extreme performance
                
                for (let j = 0; j < ptsUp.length - 1; j++) {
                    inPoints.push(ptsUp[j], ptsUp[j+1]);
                }

                // 2. Magenta Arcs DOWN (Outbound)
                const midDown = midBase.clone();
                midDown.y -= distance * 0.2; // Matches local view depth
                const curveDown = new THREE.QuadraticBezierCurve3(startPoint, midDown, endPoint);
                const ptsDown = curveDown.getPoints(10); 
                
                for (let j = 0; j < ptsDown.length - 1; j++) {
                    outPoints.push(ptsDown[j], ptsDown[j+1]);
                }
            });
        }
        
        // Compile Inbound (Gold) Layer
        const inGeo = new THREE.BufferGeometry().setFromPoints(inPoints);
        const inMat = new THREE.LineBasicMaterial({ 
            color: 0xffcc00, 
            transparent: true, 
            opacity: 0.15, 
            blending: THREE.NormalBlending // Switched for better performance
        });
        const inMesh = new THREE.LineSegments(inGeo, inMat);
        
        // Compile Outbound (Magenta) Layer
        const outGeo = new THREE.BufferGeometry().setFromPoints(outPoints);
        const outMat = new THREE.LineBasicMaterial({ 
            color: 0xff007f, 
            transparent: true, 
            opacity: 0.15, 
            blending: THREE.NormalBlending // Switched for better performance
        });
        const outMesh = new THREE.LineSegments(outGeo, outMat);
        
        // Add both to the parent group and inject into the scene
        this.globalWebMesh.add(inMesh);
        this.globalWebMesh.add(outMesh);
        this.scene.add(this.globalWebMesh);
    }
}