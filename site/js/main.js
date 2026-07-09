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
 * FILENAME: main.js
 * GitGalaxy Phase 11: Direct JSON Visualization Core
 * Optimized for Spec v6.2 (Pre-analyzed JSONs)
 */

import { GalaxyEngine } from './core/galaxy-engine.js';
import { DataParser } from './core/data-parser.js';
import { createPhase6Shaders } from './core/phase-6-shaders.js';

class AppController {
    constructor() {
        this.engine = new GalaxyEngine();
        this.parser = new DataParser();
        
        this.searchIndex = [];
        this.discoveredGalaxies = []; 
        
        this.METRIC_NAMES = {
            1: "Cognitive Pressure",
            2: "Resilience Factor",
            3: "Structural Debt",
            4: "Verification Density",
            5: "Surface Exposure",
            11: "Seismic Churn"
        };

        this.init();
    }

    async init() {
        console.log("Warp Core Loading");
        
        try {
            // PHASE 11.1: Await Engine Readiness
            // We poll for the materials to ensure the WebGPU init is complete
            await this.waitForEngine();

            // Connect TSL Node Materials once engine is ready
            const shaders = createPhase6Shaders(this.engine);
            this.engine.cachedShaders = shaders; // <-- NEW: Save for theme switching
            if (this.engine.solidMat && this.engine.wireMat) {
                this.engine.solidMat.colorNode = shaders.colorNode;
                this.engine.wireMat.colorNode = shaders.colorNode;
                this.engine.solidMat.opacityNode = shaders.opacityNode;
                this.engine.wireMat.opacityNode = shaders.opacityNode;
                
                // --- THE FIX: Force WebGPU to recompile the materials ---
                this.engine.solidMat.needsUpdate = true;
                this.engine.wireMat.needsUpdate = true;
            }

            window.isWebVisible = false;
            window.toggleDependencyWeb = function(btn) {
                window.isWebVisible = !window.isWebVisible;
                
                // Trigger the 3D Engine
                if (window.App && window.App.toggleLines) {
                    window.App.toggleLines(window.isWebVisible);
                }

                // Update Button Aesthetics
                if (window.isWebVisible) {
                    btn.innerText = "⎈ HIDE LOCAL WEB";
                    btn.style.background = "var(--accent)";
                    btn.style.color = "#000";
                    btn.style.boxShadow = "0 0 15px var(--accent)";
                } else {
                    btn.innerText = "⎈ VISUALIZE LOCAL WEB";
                    btn.style.background = "transparent";
                    btn.style.color = "var(--accent)";
                    btn.style.boxShadow = "none";
                }
            };

            window.App = {
                engine: this.engine,
                setTheme: (val) => this.handleThemeChange(val),
                setMetric: (val) => this.handleMetricChange(val),
                loadMock: (key) => this.fetchGalaxyData(key), 
                resetCamera: () => this.handleResetCamera(),
                hideHUDUI: () => window.hideHUDUI(),
                
                // --- NEW: Expose the toggle to the HTML ---
                toggleLines: (val) => {
                    const raw = window.currentRawGalaxyData;
                    const pScalar = raw?.meta?.scalars?.physics || 10;
                    this.engine.toggleDependencyLines(val, raw?.galaxy, pScalar);
                },

                toggleGlobalWeb: (val) => {
                    const raw = window.currentRawGalaxyData;
                    if (!raw || !raw.galaxy) return;
                    const pScalar = raw.meta?.scalars?.physics || 10;
                    this.engine.toggleGlobalWeb(val, raw.galaxy, pScalar);
                },
                syncSelection: () => this.syncHUDWithSelection()
            };

            // --- ADAPTIVE QUALITY LISTENER ---
            window.addEventListener('galaxy-quality-change', (e) => {
                const newTier = e.detail.tier;
                console.log(`Visualizer: Performance Shift -> ${newTier} Tier Active`);
                
                this.engine.currentQualityTier = newTier;

                // 1. CULL THE DUST FIELD: Hide it entirely if not on TITAN
                if (this.engine.dustField) {
                    this.engine.dustField.visible = (newTier === 'TITAN');
                }

                // 2. AUTO-CULL SATELLITES (Only on severe frame drops)
                const moonMesh = this.engine.meshGroups['moon'];
                if (moonMesh && newTier === 'POTATO') {
                    // Turn them off to save GPU fill-rate
                    moonMesh.visible = false;
                    
                    // Update the UI button so you know the system intervened
                    const btnSats = document.getElementById('btn-toggle-sats');
                    if (btnSats) {
                        btnSats.innerText = "Satellites: OFF (AUTO)";
                        btnSats.style.background = "transparent";
                    }
                }

                // 3. REBUILD THE WEB (If Active)
                if (window.isGlobalWebOn && window.currentRawGalaxyData) {
                    const raw = window.currentRawGalaxyData;
                    const pScalar = raw.meta?.scalars?.physics || 10;
                    
                    if (this.engine.globalWebMesh) {
                        this.engine.scene.remove(this.engine.globalWebMesh);
                        this.engine.globalWebMesh.children.forEach(c => { 
                            c.geometry.dispose(); 
                            c.material.dispose(); 
                        });
                        this.engine.globalWebMesh = null;
                    }
                    this.engine.toggleGlobalWeb(true, raw.galaxy, pScalar);
                }
            });

            // UI Event Listeners
            const searchInput = document.getElementById('warp-search');
            if (searchInput) {
                searchInput.addEventListener('input', (e) => this.performSearch(e.target.value));
            }

            // --- THE LIVE SITE DRAG-AND-DROP LISTENER ---
            window.addEventListener('dragover', (e) => { e.preventDefault(); });
            window.addEventListener('drop', (e) => {
                e.preventDefault();
                const file = e.dataTransfer.files[0];
                if (!file) return;

                // 1. THE .ZIP INTERCEPT
                if (file.name.endsWith('.zip')) {
                    alert("ZIP ingestion feature coming soon!\n\nPlease use 'pip install gitgalaxy' in your terminal in the meantime to process local repositories.");
                    return;
                }
                
                // 2. THE .JSON HANDLER
                if (file.name.endsWith('.json')) {
                    const maxSize = 50 * 1024 * 1024; 
                    if (file.size > maxSize) {
                        const mbSize = (file.size / 1024 / 1024).toFixed(1);
                        const proceed = window.confirm(
                            `⚠️ WARNING: MASSIVE PAYLOAD DETECTED (${mbSize}MB) ⚠️\n\n` +
                            `Files over 50MB require significant RAM to parse into 3D geometry. ` +
                            `Depending on your hardware, this may cause your browser tab to crash (OOM).\n\n` +
                            `This is a hardware limitation. Our data is highly compressed, but 3D arrays are heavy. Proceed at your own risk?`
                        );
                        if (!proceed) return; // Abort if they choose to cancel
                    }

                    const loader = document.getElementById('loading-screen');
                    if (loader) { loader.style.opacity = '1'; loader.style.display = 'flex'; }
                    
                    const reader = new FileReader();
                    reader.onload = (event) => {
                        try {
                            const raw = JSON.parse(event.target.result);
                            
                            // Cache it in RAM and assign the 'isLocal' flag
                            const baseName = file.name.replace('_galaxy.json', '').replace('.json', '');
                            const exists = this.discoveredGalaxies.find(g => g.id === baseName);

                            if (!exists) {
                                this.discoveredGalaxies.push({
                                    id: baseName,
                                    name: baseName.replace(/-/g, ' ').toUpperCase(),
                                    file: file.name,
                                    isLocal: true, // Flags this as a gold-colored manual upload
                                    rawData: raw 
                                });
                                this.renderSystemMenu(); // Re-draw the menu
                            }

                            this.loadGalaxyFromRAM(raw, file.name);
                        } catch (err) {
                            console.error("Live Parse Failure:", err);
                            this.clearLoader();
                            alert("Critical Error: Failed to parse JSON file.");
                        }
                    };
                    reader.readAsText(file);
                }
            });

            // Auto-Discovery: Ask the Librarian what artifacts are available
            await this.discoverGalaxies();

            // 🚨 THE FIX: Search the new object array for Apollo
            let defaultGalaxy = this.discoveredGalaxies[0]; // Fallback to the first item
            
            const apolloMatch = this.discoveredGalaxies.find(g => g.id.toLowerCase().includes('apollo'));
            if (apolloMatch) {
                defaultGalaxy = apolloMatch;
            }
            
            if (defaultGalaxy) {
                await this.fetchGalaxyData(defaultGalaxy);
            } else {
                console.warn("Visualizer: No archives discovered in /data.");
                this.clearLoader();
            }

        } catch (err) {
            console.error("Visualizer: Critical Initialization Error:", err);
            this.clearLoader();
        }
    }

    /**
     * Helper to wait for the async GalaxyEngine.init() to complete
     */
    async waitForEngine() {
        return new Promise((resolve, reject) => {
            let attempts = 0;
            const check = () => {
                attempts++;
                if (this.engine.solidMat) {
                    resolve();
                } else if (attempts > 200) { // 10 second timeout
                    reject("Engine failed to initialize materials within 10s. Check WebGPU support.");
                } else {
                    setTimeout(check, 50);
                }
            };
            check();
        });
    }

    /**
     * Force-clears the loading screen
     */
    clearLoader() {
        const loader = document.getElementById('loading-screen');
        if (loader) {
            loader.style.opacity = '0';
            setTimeout(() => loader.remove(), 1000);
        }
    }

    async discoverGalaxies() {
        try {
            // 🚨 THE FIX: Fetch the static JSON directly from Nginx!
            const response = await fetch('data/manifest.json');
            if (response.ok) {
                this.discoveredGalaxies = await response.json();
                this.renderSystemMenu();
            } else {
                console.error("Visualizer Error: Could not find /data/manifest.json");
            }
        } catch (err) {
            console.error("Discovery Failed:", err);
        }
    }

    /**
     * DYNAMIC UI GENERATOR
     * Reads the JSON schema to populate the Spectral Analysis dropdown
     * and synchronizes the HUD text mapping.
     */
    buildMetricDropdown(riskNames) {
        const select = document.getElementById('metric-select');
        if (!select) return;

        const currentVal = select.value; 
        
        // 1. Reset everything to baseline
        select.innerHTML = '<option value="0">Standard (Basal State)</option>';
        this.METRIC_NAMES = {}; 

        window.RISK_SCHEMA = riskNames;

        // 2. Loop through the JSON schema and build the UI
        riskNames.forEach((rawName, index) => {
            let cleanName = rawName.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
            
            if (window.Colors && window.Colors.LEGENDS && window.Colors.LEGENDS[rawName]) {
                cleanName = window.Colors.LEGENDS[rawName].title;
            }
            
            // THE FIX: Shift the new security lenses (index 13+) to IDs 15-19
            // to preserve ID 14 exclusively for Language Identity.
            const engineId = index >= 13 ? index + 2 : index + 1; 
            
            this.METRIC_NAMES[engineId] = cleanName;

            const option = document.createElement('option');
            option.value = engineId;
            option.innerText = cleanName;
            select.appendChild(option);
        });

        // --- NEW: 3. Inject Language Identity (Mode 14) ---
        const langModeId = 14;
        const langModeName = "Language Identity";
        this.METRIC_NAMES[langModeId] = langModeName;

        const langOption = document.createElement('option');
        langOption.value = langModeId;
        langOption.innerText = langModeName;
        
        // Insert Language Identity right after Civil War (which is the 14th element in the select DOM)
        select.insertBefore(langOption, select.children[14]);

        // --- NEW: Inject File Architecture (Mode 21) ---
        const archModeId = 21;
        const archModeName = "File Architecture";
        this.METRIC_NAMES[archModeId] = archModeName;

        const archOption = document.createElement('option');
        archOption.value = archModeId;
        archOption.innerText = archModeName;
        select.appendChild(archOption); // Adds it to the very bottom of the dropdown

        // 4. Restore previous selection
        if (this.METRIC_NAMES[currentVal]) {
            select.value = currentVal;
            // --- THE FIX: Force the UI to re-evaluate the active data ---
            this.handleMetricChange(currentVal); 
        } else {
            select.value = "0";
            this.handleMetricChange("0");
        }
    }

    renderSystemMenu() {
        const container = document.getElementById('galaxy-list'); 
        if (!container) return;
        container.innerHTML = ''; 

        this.discoveredGalaxies.forEach(galaxyObj => {
            const btn = document.createElement('button');
            btn.className = "warp-btn"; 
            
            // Apply gold styling to user-uploaded files
            if (galaxyObj.isLocal) {
                btn.classList.add('local-warp-btn');
            }

            btn.innerHTML = `${galaxyObj.name.toUpperCase()} <span>WARP</span>`;
            btn.onclick = () => this.fetchGalaxyData(galaxyObj);
            container.appendChild(btn);
        });
    }

    /**
     * FETCH GALAXY DATA (Network vs RAM Routing)
     */
    async fetchGalaxyData(galaxyObj) {
        if (typeof galaxyObj === 'string') {
            galaxyObj = this.discoveredGalaxies.find(g => g.id === galaxyObj) || { id: galaxyObj, name: galaxyObj, file: `/museum/${galaxyObj}_galaxy.json` };
        }
        
        const key = galaxyObj.id;
        console.log(`Visualizer: Fetching ${key}...`);

        // --- MOBILE MENU AUTO-CLOSE ---
        // If on a mobile device, automatically slide the main menu away so the user can see the hyperspace jump
        if (window.innerWidth <= 768 && window.isMainUIOpen) {
            window.toggleMainUI();
        }

        const searchInput = document.getElementById('warp-search');
        if (searchInput) searchInput.value = '';
        if (window.renderSearchResults) window.renderSearchResults([], null);

        const progress = document.getElementById('load-progress');
        if (progress) { progress.style.transition = 'none'; progress.style.width = '30%'; }

        try {
            // --- RAM BYPASS: If it's a dragged-in file, load instantly ---
            if (galaxyObj.isLocal) {
                console.log(`Visualizer: Restoring [${key}] directly from RAM Cache...`);
                // Null out payloads since it's a manual upload
                galaxyObj.rawData._injectedAuditUrl = null;
                galaxyObj.rawData._injectedLlmUrl = null;
                this.loadGalaxyFromRAM(galaxyObj.rawData, galaxyObj.file);
                return;
            }

            // --- STANDARD: Fetch from your live Nginx server ---
            const targetUrl = galaxyObj.file || `/museum/${key}_galaxy.json`;
            const response = await fetch(targetUrl);
            
            if (!response.ok) throw new Error(`Artifact [${key}] Load Error: ${response.status}`);
            
            const raw = await response.json();

            // Inject URLs so the load function knows they exist
            raw._injectedAuditUrl = galaxyObj.auditUrl;
            raw._injectedLlmUrl = galaxyObj.llmUrl;

            this.loadGalaxyFromRAM(raw, galaxyObj.name.split(' ')[0]);

        } catch (err) {
            console.warn("Visualizer: Data load failed for", key, err);
            if (this.engine.loadMock) this.engine.loadMock(key);
            this.clearLoader();
        }
    }

    /**
     * LOAD GALAXY (The Core Engine Injector)
     */
    loadGalaxyFromRAM(raw, displayName) {
        const progress = document.getElementById('load-progress');
        
        try {
            // --- REVERSE-ENGINEER OUTBOUND EDGES ---
            if (raw.galaxy && raw.galaxy.edges && !raw.galaxy.outbound_edges) {
                raw.galaxy.outbound_edges = Array.from({length: raw.galaxy.names.length}, () => []);
                raw.galaxy.edges.forEach((importedByArray, targetId) => {
                    if (importedByArray) {
                        importedByArray.forEach(sourceId => {
                            raw.galaxy.outbound_edges[sourceId].push(targetId);
                        });
                    }
                });
            }

            window.currentRawGalaxyData = raw; 
            
            // --- INJECT STORY DATA ---
            if (window.populateStoryHUD) {
                window.populateStoryHUD(raw.story, displayName);
            }

            // Update the Download Payload Buttons
            if (window.updatePayloadButtons) {
                window.updatePayloadButtons(raw._injectedAuditUrl, raw._injectedLlmUrl);
            }
            
            if (raw.meta && raw.meta.schemas && raw.meta.schemas.risk_vector_x1000) {
                this.buildMetricDropdown(raw.meta.schemas.risk_vector_x1000);
            }

            if (progress) {
                progress.style.transition = 'width 0.5s ease';
                progress.style.width = '70%';
            }

            if (this.engine && typeof this.engine.hyperspaceJump === 'function') {
                this.engine.hyperspaceJump(() => {
                    this.engine.loadSector(raw);
                    this.buildSearchIndex(raw);
                    if (progress) progress.style.width = '100%';
                    this.clearLoader();
                });
            } else {
                this.engine.loadSector(raw);
                this.buildSearchIndex(raw);
                if (progress) progress.style.width = '100%';
                this.clearLoader();
            }

            const brand = document.getElementById('brand-title');
            if (brand) brand.innerText = displayName.toUpperCase();

            // --- THE FIX: Update the Floating Canvas Title ---
            const floatingTitle = document.getElementById('floating-title');
            if (floatingTitle) floatingTitle.innerText = displayName.toUpperCase();

        } catch (err) {
            console.warn("Visualizer: RAM load failed", err);
            this.clearLoader();
        }
    }

    /**
     * SEARCH INDEXER
     * Maps the 'galaxy' object for the Warp Search.
     */
    buildSearchIndex(raw) {
        this.searchIndex = [];
        const gal = raw.galaxy;
        if (!gal || !gal.names) return;

        // --- THE FIX: Grab the physics scalar from the JSON meta ---
        const pScalar = raw.meta?.scalars?.physics || 10;

        for (let i = 0; i < gal.names.length; i++) {
            const star = {
                id: i,
                name: gal.names[i],
                type: 'FILE',
                loc: gal.locs[i],
                // --- THE FIX: Divide the raw integers to match the true 3D world ---
                pos: { 
                    x: gal.pos_x[i] / pScalar, 
                    y: gal.pos_y[i] / pScalar, 
                    z: gal.pos_z[i] / pScalar 
                }
            };
            this.searchIndex.push(star);

            if (gal.satellites && gal.satellites[i]) {
                gal.satellites[i].forEach(sat => {
                    this.searchIndex.push({
                        id: i,
                        name: sat[0], 
                        type: 'SATELLITE',
                        loc: sat[1],
                        pos: star.pos // Satellites correctly inherit the scaled parent position
                    });
                });
            }
        }
    }

    performSearch(query) {
        if (!query || query.length < 2) { window.renderSearchResults([], null); return; }
        const q = query.toLowerCase();
        const matches = this.searchIndex.filter(item => item.name.toLowerCase().includes(q)).slice(0, 8);
        window.renderSearchResults(matches, (selected) => {
            this.engine.flyTo(selected.pos, selected.id);
            this.syncHUDWithSelection();
        });
    }

    syncHUDWithSelection() {
        const sid = this.engine.uSelectedGlobalId.value;
        if (sid === -1) {
            this.engine.clearDependencyLines(); 
            return; 
        }
        
        const fileData = this.engine.activeFiles[sid];
        const raw = window.currentRawGalaxyData;
        
        let inEdges = [];
        let inNames = [];
        let outEdges = [];
        let outNames = [];

        if (raw && raw.galaxy) {
            // 1. Get Inbound (Imported By)
            if (raw.galaxy.edges) {
                inEdges = raw.galaxy.edges[sid] || [];
                inNames = inEdges.map(id => raw.galaxy.names[id]); 
            }
            // 2. Get Outbound (Imports)
            if (raw.galaxy.outbound_edges) {
                outEdges = raw.galaxy.outbound_edges[sid] || [];
                outNames = outEdges.map(id => raw.galaxy.names[id]);
            }
        }

        // Draw the 3D Lines
        const pScalar = raw?.meta?.scalars?.physics || 10;
        this.engine.drawDependencyLines(sid, inEdges, outEdges, raw.galaxy, pScalar);

        // Pass BOTH arrays to the HTML HUD
        if (fileData && window.updateHUD) {
            const mode = this.engine.uMetricMode.value;
            window.updateHUD(fileData, mode, this.METRIC_NAMES[mode], inNames, inEdges.length, outNames, outEdges.length);
        }
    }

    handleThemeChange(val) { 
        const index = parseInt(val);
        this.engine.uThemeIndex.value = index; 

        // --- THE FIX: DYNAMIC UI COLORS ---
        // This updates the global --accent variable so the entire HTML UI
        // (including buttons, titles, and borders) matches the 3D WebGPU scene!
        const root = document.documentElement;
        if (index === 3) {
            root.style.setProperty('--accent', '#00ff41'); // Matrix Green
        } else if (index === 4) {
            root.style.setProperty('--accent', '#ffffff'); // High-Vis White
        } else if (index === 2) {
            root.style.setProperty('--accent', '#bc13fe'); // Galactic Purple
        } else {
            root.style.setProperty('--accent', '#00f3ff'); // Crystalline Teal
        }

        // Cache the default bloom strength the first time we switch themes
        if (this.engine.defaultBloomStrength === undefined && this.engine.uBloomStrength) {
            this.engine.defaultBloomStrength = this.engine.uBloomStrength.value;
        }

        // 1. Handle Background Environments & Post-Processing
        if (index === 4) { // High-Vis
            this.engine.scene.background.setHex(0x000000); // Pure Black
            if (this.engine.uBloomStrength) this.engine.uBloomStrength.value = 0.0;
            if (this.engine.uBloomThreshold) this.engine.uBloomThreshold.value = 2.0;
            
            // Force the Opaque Render Queue to prevent back-to-front rendering bleed
            if (this.engine.solidMat) {
                this.engine.solidMat.transparent = false;
                this.engine.solidMat.depthWrite = true;
                this.engine.moonMat.transparent = false;
                this.engine.moonMat.depthWrite = true;
                this.engine.wireMat.transparent = false;
                this.engine.wireMat.depthWrite = true;
            }
        } else {
            // Restore standard space backgrounds and Bloom for all other themes
            if (index === 3) this.engine.scene.background.setHex(0x000000); // Matrix
            else if (index === 1) this.engine.scene.background.setHex(0x020205); // Ice Crystal
            else this.engine.scene.background.setHex(0x050508); // Galactic
            
            if (this.engine.uBloomStrength) this.engine.uBloomStrength.value = this.engine.defaultBloomStrength;
            if (this.engine.uBloomThreshold) this.engine.uBloomThreshold.value = 0.4; // Restore standard glow
            
            // Restore Transparent Render Queue
            if (this.engine.solidMat) {
                this.engine.solidMat.transparent = true;
                this.engine.solidMat.depthWrite = false;
                this.engine.moonMat.transparent = true;
                this.engine.moonMat.depthWrite = false;
                this.engine.wireMat.transparent = true;
                this.engine.wireMat.depthWrite = false;
            }
        }

        // 2. Handle Wireframe Overrides
        const forceWireframe = (index === 3);
        if (this.engine.solidMat) {
            this.engine.solidMat.wireframe = forceWireframe;
            this.engine.solidMat.needsUpdate = true;
        }
        
        // 3. Handle DOM Label Colors
        const labelContainer = document.getElementById('label-container');
        if (labelContainer) {
            labelContainer.className = ''; 
            if (index === 2) labelContainer.classList.add('theme-galactic');
            else if (index === 3) labelContainer.classList.add('theme-matrix');
            else if (index === 4) labelContainer.classList.add('theme-high-vis');
        }

        // 4. Force the Legend & HUD to refresh their colors
        if (this.engine.uMetricMode) {
            this.handleMetricChange(this.engine.uMetricMode.value);
        }
    }


    handleMetricChange(val) { 
        const mode = parseInt(val);
        this.engine.uMetricMode.value = mode; 
        
        if (window.updateLegend) {
            let schemaKey = null;
            if (mode === 14) schemaKey = 'language_identity'; 
            else if (mode === 21) schemaKey = 'file_architecture'; // <-- SHIFT TO 21
            else if (mode >= 15) schemaKey = window.RISK_SCHEMA[mode - 2]; 
            else if (mode > 0) schemaKey = window.RISK_SCHEMA[mode - 1]; 
            
            window.updateLegend(mode, schemaKey);
        }
        this.syncHUDWithSelection(); 
    }


    handleResetCamera() {
        this.engine.hideHUD();
        new TWEEN.Tween(this.engine.targetPos).to({ x: 0, y: 0, z: 0 }, 1500).easing(TWEEN.Easing.Cubic.Out).start();
        new TWEEN.Tween(this.engine).to({ cameraRadius: 5000 }, 1500).easing(TWEEN.Easing.Cubic.Out).start();
    }

    

}



new AppController();