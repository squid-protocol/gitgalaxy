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
 * POSTER GENERATOR (The Gift Shop)
 * v7.0 - True Native High-Res Tiled Rendering Engine
 * Featuring: WebGPU Hardware Bypass, VRAM-Safe SSAA, & Auto-Download
 */

window.abortPosterRender = false;


class PosterGenerator {
    constructor() {
        // ==========================================
        // 🔧 DEVELOPER DIAGNOSTICS
        // Set to TRUE to print grid borders, squash detectors, and math logs.
        // Set to FALSE for the final, clean customer print!
        // ==========================================
        this.DEBUG_MODE = false; 
        
        this.active = false;
        this.isLocked = false;
        this.TILE_SIZE = 2048; 
        this.PAD = 1024;        
    }

    
    
    // --- THE INVINCIBLE CAMERA LOCK ---
    lockCamera() {
        const engine = window.App?.engine;
        if (!engine || this.isLocked) return;
        this.isLocked = true;
        
        engine.isRotating = false;

        Object.defineProperty(engine, 'lastInteractionTime', {
            get: () => Date.now(), 
            set: (val) => {},      
            configurable: true
        });
        
        if (this.DEBUG_MODE) console.log("🔒 Engine Clock Hijacked. Camera is perfectly paralyzed.");
    }

    unlockCamera() {
        const engine = window.App?.engine;
        if (!engine || !this.isLocked) return;
        this.isLocked = false;

        Object.defineProperty(engine, 'lastInteractionTime', {
            value: Date.now(),
            writable: true,
            configurable: true
        });
        
        if (this.DEBUG_MODE) console.log("🔓 Engine Clock Restored.");
    }

    // --- PHASE 1: EXACT SCREEN MATCH (For Free Download & Preview) ---
    async generatePreview() {
        if (this.active) return;
        this.active = true;

        // 1. INSTANT UI FEEDBACK: Grab the button and change it to a loading state
        const triggerBtn = document.querySelector('button[onclick="window.Poster.generatePreview()"]');
        const origBtnText = triggerBtn ? triggerBtn.innerText : "";
        const origBtnBg = triggerBtn ? triggerBtn.style.background : "";
        const origBtnColor = triggerBtn ? triggerBtn.style.color : "";
        
        if (triggerBtn) {
            triggerBtn.innerText = "📸 ALIGNING OPTICS...";
            triggerBtn.style.background = "var(--accent)";
            triggerBtn.style.color = "#000";
        }

        // 2. YIELD THE MAIN THREAD: Force the DOM to paint the button BEFORE the GPU freezes
        await new Promise(resolve => setTimeout(resolve, 50));
        
        this.lockCamera();

        const closeBtn = document.querySelector('#gift-shop-hud .close-btn');
        if (closeBtn) {
            closeBtn.onclick = () => {
                // 👇 NEW: Force the kill switch here so it fires even if the UI is overwritten
                window.abortPosterRender = true; 
                
                this.unlockCamera();
                document.getElementById('gift-shop-hud').style.display = 'none';
                
                // Optional: Reset button text if they cancelled during a render
                const renderBtns = document.querySelectorAll('#print-buttons-container button');
                renderBtns.forEach(btn => {
                    if (btn.innerText.includes('Crunching')) {
                        // Reset the text back to the price (you can refine this if needed)
                        btn.innerHTML = btn.getAttribute('data-original-html') || btn.innerHTML;
                        btn.disabled = false;
                    }
                });
            };
        }

        if (this.DEBUG_MODE) console.log(`🖨️ Generating Screen-Match Preview...`);

        const raw = window.currentRawGalaxyData;
        const engine = window.App.engine;
        
        if (!raw || !engine) {
            // Safety fallback to restore button if data is missing
            if (triggerBtn) {
                triggerBtn.innerText = origBtnText;
                triggerBtn.style.background = origBtnBg;
                triggerBtn.style.color = origBtnColor;
            }
            this.active = false;
            return;
        }

        const labelsWereVisible = engine.labelsVisible;
        if (labelsWereVisible) window.toggleLabels(); 

        const origW = window.innerWidth;
        const origH = window.innerHeight;
        const origAspect = engine.camera.aspect;
        const origPixelRatio = engine.renderer.getPixelRatio();
        
        engine.renderer.setPixelRatio(Math.min(window.devicePixelRatio * 1.5, 3));
        
        // 1. FIX: Use standard render (renderAsync is deprecated and breaks WebGL2 fallback)
        if (engine.composer) engine.composer.render();
        else engine.renderer.render(engine.scene, engine.camera);
        
        
        const canvas = document.createElement('canvas');
        canvas.width = origW * engine.renderer.getPixelRatio();
        canvas.height = origH * engine.renderer.getPixelRatio();
        const ctx = canvas.getContext('2d');

        ctx.fillStyle = "#010103";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(engine.renderer.domElement, 0, 0, canvas.width, canvas.height);
        
        // 3. STAMP TYPOGRAPHY & LEGEND
        this.drawTypography(ctx, canvas.width, canvas.height, raw);
        this.drawLegend(ctx, canvas.width, canvas.height, engine.uMetricMode.value);

        engine.renderer.setPixelRatio(origPixelRatio);
        if (labelsWereVisible) window.toggleLabels(); 

        const targetName = raw.meta?.session?.target || "Unknown_Sector";
        const filename = `GitGalaxy_${targetName.replace(/[^a-zA-Z0-9]/g, '_')}_Digital.png`;
        
        canvas.toBlob((blob) => {
            const url = URL.createObjectURL(blob);
            if (window.showGiftShop) window.showGiftShop(url, filename);
            else this.download(url, filename);
            
            // 4. CLEANUP: Restore the original button state
            if (triggerBtn) {
                triggerBtn.innerText = origBtnText;
                triggerBtn.style.background = origBtnBg;
                triggerBtn.style.color = origBtnColor;
            }
            this.active = false;
        }, 'image/jpeg', 0.95); 
    }


    // --- PHASE 2: TRUE NATIVE HIGH-RES TILED RENDERER ---
    async _renderTiledPrintCanvas(targetW, targetH, buttonElement) {
        const raw = window.currentRawGalaxyData;
        const engine = window.App.engine;
        
        const labelsWereVisible = engine.labelsVisible;
        if (labelsWereVisible) window.toggleLabels(); 

        const artWidth = targetW;
        const artHeight = targetH;
        
        const canvas = document.createElement('canvas');
        canvas.width = targetW;
        canvas.height = targetH;
        const ctx = canvas.getContext('2d', { willReadFrequently: true }); 
        
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = 'high';

        ctx.fillStyle = "#010103";
        ctx.fillRect(0, 0, targetW, targetH);

        const origW = window.innerWidth;
        const origH = window.innerHeight;
        const origAspect = engine.camera.aspect;
        const origPixelRatio = engine.renderer.getPixelRatio();

        // Safely extract the camera target, whether it's stored in targetPos or OrbitControls
        const lockPhi = engine.cameraPhi;
        const lockTheta = engine.cameraTheta;
        let lockTarget = null;
        if (engine.targetPos && typeof engine.targetPos.clone === 'function') {
            lockTarget = engine.targetPos.clone();
        } else if (engine.controls && engine.controls.target && typeof engine.controls.target.clone === 'function') {
            lockTarget = engine.controls.target.clone();
        }
        const lockRadius = engine.cameraRadius;

        const SSAA = 2;
        
        // 1. Ask the GPU for its absolute limit
        const gl = document.createElement('canvas').getContext('webgl');
        const maxTexture = gl ? gl.getParameter(gl.MAX_TEXTURE_SIZE) : 4096;
        
        if (this.DEBUG_MODE) console.log(`💻 GPU Max Texture Limit: ${maxTexture}px`);

        // 2. The padding is critical for hiding bloom seams. 
        // You know 1000 works, so we set that as our baseline.
        const PAD = 1000;

        // 3. THE FIX: The VRAM Safety Buffer
        // A post-processing stack uses multiple screen-sized buffers at once.
        // By multiplying by 0.45, we reserve over half the GPU's memory strictly for the bloom math.
        const safeLimit = maxTexture * 0.45; 
        
        // Algebra to solve for TILE_SIZE: TILE = (safeLimit / SSAA) - (PAD * 2)
        let calculatedTile = Math.floor((safeLimit / SSAA) - (PAD * 2));

        // 4. Set highly conservative boundaries. 
        // If the math yields a tiny number on weak GPUs, default to a safe micro-tile (128).
        // Cap it at 600 (your known good limit) so it never pushes your specific machine too hard.
        const TILE_SIZE = Math.max(128, Math.min(600, calculatedTile));
        
        if (this.DEBUG_MODE) console.log(`📐 Dynamically selected TILE_SIZE: ${TILE_SIZE}px`);
        
        const cols = Math.ceil(artWidth / TILE_SIZE);
        const rows = Math.ceil(artHeight / TILE_SIZE);
        const totalTiles = cols * rows;
        let currentTile = 0;

        const viewW = (TILE_SIZE + (PAD * 2)) * SSAA;
        const viewH = (TILE_SIZE + (PAD * 2)) * SSAA;
        
        engine.renderer.setPixelRatio(1);
        engine.renderer.setSize(viewW, viewH, false);
        if (engine.composer && typeof engine.composer.setSize === 'function') {
            engine.composer.setSize(viewW, viewH);
        }

        const virtualArtW = artWidth * SSAA;
        const virtualArtH = artHeight * SSAA;
        engine.camera.aspect = artWidth / artHeight;
        engine.camera.updateProjectionMatrix();

        // ==========================================
        // 🎛️ PRINT-FIDELITY CALIBRATION
        // ==========================================
        const printScale = targetH / window.innerHeight;
        
        // 1. ALPHA BUG FIX: Hardcode the background opaque to save stars. 
        const origClearColor = 0x010103; 
        let origClearAlpha = 1;
        
        if (engine.renderer.getClearAlpha) {
            origClearAlpha = engine.renderer.getClearAlpha();
        }
        engine.renderer.setClearColor(0x010103, 1.0);

        // 2. SUB-PIXEL FIX: Find ALL star systems, scale them up, max opacity, and force HDR
        const originalPointMats = new Map();
        engine.scene.traverse((child) => {
            if (child.isPoints && child.material) {
                const mats = Array.isArray(child.material) ? child.material : [child.material];
                mats.forEach(mat => {
                    if (!originalPointMats.has(mat)) {
                        // Save original size, opacity, and color hex
                        originalPointMats.set(mat, {
                            size: mat.size,
                            opacity: mat.opacity,
                            origHex: mat.color ? mat.color.getHex() : null
                        });
                        
                        // LEVER 1: Bump size multiplier up a bit more (1.5 -> 2.0)
                        mat.size = mat.size * Math.max(1, printScale * 2.0) * SSAA;
                        
                        // LEVER 2: Force maximum opacity
                        if (mat.transparent) mat.opacity = 1.0; 
                        
                        // LEVER 3: Multiply the color to force it over the bloom threshold!
                        if (mat.color) {
                            // Multiply by 3 or 4 to make them burn bright white/hot
                            mat.color.multiplyScalar(6.5); 
                        }
                        
                        mat.needsUpdate = true;
                    }
                });
            }
        });
        
        // 3. Save original bloom & exposure states
        const originalExposure = engine.renderer.toneMappingExposure || 1.2;
        const origBloomRadius = engine.uBloomRadius ? engine.uBloomRadius.value : 0.4;
        const origBloomStrength = engine.uBloomStrength ? engine.uBloomStrength.value : 0.8;

        // 4. SCALE THE BLOOM FOR HIGH-RES
        if (engine.uBloomRadius) engine.uBloomRadius.value = origBloomRadius * (printScale * 0.25);
        
        // LEVER 3: Crank the bloom strength (bumped from 1.1 to 1.8)
        if (engine.uBloomStrength) engine.uBloomStrength.value = origBloomStrength * 1.8; 
        
        engine.renderer.toneMappingExposure = originalExposure * 1.5;

        // ==========================================
        // 🕸️ NETWORK LINE CALIBRATION & THE CABLE FIX
        // ==========================================
        const originalLineMats = new Map();
        const cableClones = []; // Track our faked lines so we can delete them after printing

        const boostNetwork = (group) => {
            if (!group) return;
            group.children.forEach(child => {
                if (child.material && child.material.opacity !== undefined) {
                    // Save original state
                    originalLineMats.set(child.material, {
                        opacity: child.material.opacity,
                        blending: child.material.blending,
                        origHex: child.material.color ? child.material.color.getHex() : null
                    });
                    
                    // 1. Drop opacity to 0.15 because 9 stacked lines will multiply the brightness!
                    child.material.opacity = 0.15; 
                    child.material.blending = 2; // Additive Blending
                    if (child.material.color) child.material.color.multiplyScalar(1.0); // No HDR needed
                    child.material.needsUpdate = true;

                    // 2. THE CABLE GENERATOR: Clone the line 8 times to fake physical thickness
                    const spread = printScale * 0.4; // The physical thickness of the cable
                    const offsets = [
                        [1,0,0], [-1,0,0], [0,1,0], [0,-1,0],
                        [0.7,0.7,0], [-0.7,-0.7,0], [-0.7,0.7,0], [0.7,-0.7,0]
                    ];

                    offsets.forEach(dir => {
                        const clone = child.clone();
                        // Shift the clone slightly in 3D space to widen the core
                        clone.position.x += dir[0] * spread;
                        clone.position.y += dir[1] * spread;
                        clone.position.z += dir[2] * spread;
                        
                        cableClones.push(clone);
                        engine.scene.add(clone);
                    });
                }
            });
        };

        boostNetwork(engine.linesGroup);
        if (engine.globalWebMesh) boostNetwork(engine.globalWebMesh);

        if (this.DEBUG_MODE) {
            console.log(`\n========================================`);
            console.log(`🖨️ INITIATING PRINT SEQUENCE`);
            console.log(`📏 Print Scale: ${printScale.toFixed(1)}x`);
            console.log(`🕸️ Network Lines Boosted to 100% Opacity`);
            console.log(`========================================\n`);
        }

        // ==========================================
        // 👻 STEALTH MODE: HIDE LIVE UI & 3D HUDS
        // ==========================================
        // 1. Hide HTML DOM Legends to prevent massive browser compositing lag
        // (Add your exact HTML legend ID to this list if it's not caught!)
        const uiElementsToHide = document.querySelectorAll('.legend, #legend, #metric-legend, .hud-overlay');
        const originalDisplays = new Map();
        
        uiElementsToHide.forEach(el => {
            originalDisplays.set(el, el.style.display);
            el.style.display = 'none';
        });

        // 2. Hide any 3D WebGL Legends inside the scene
        const hidden3DObjects = [];
        engine.scene.traverse(child => {
            if (child.name && (child.name.toLowerCase().includes('legend') || child.name.toLowerCase().includes('hud')) && child.visible) {
                child.visible = false;
                hidden3DObjects.push(child);
            }
        });

        // 👇 NEW: Setup the local abort tracker and reset the global switch
        let isAborted = false;
        window.abortPosterRender = false;

        for (let y = 0; y < rows; y++) {
            if (isAborted) break; // Kills the outer row loop

            for (let x = 0; x < cols; x++) {
                
                // 👇 THE KILL SWITCH INTERCEPT
                if (window.abortPosterRender) {
                    console.warn("User aborted render. Initiating GPU cleanup...");
                    isAborted = true;
                    break; // Kills the inner column loop
                }

                currentTile++;
                
                const progress = Math.round((currentTile / totalTiles) * 100);
                if (buttonElement) buttonElement.innerText = `Crunching HD Art: ${progress}% (Keep Tab Open) ⏳`;

                // Safely restore the camera variables only if they exist
                if (lockPhi !== undefined) engine.cameraPhi = lockPhi;
                if (lockTheta !== undefined) engine.cameraTheta = lockTheta;
                if (lockRadius !== undefined) engine.cameraRadius = lockRadius;
                
                if (lockTarget) {
                    if (engine.targetPos && typeof engine.targetPos.copy === 'function') {
                        engine.targetPos.copy(lockTarget);
                    } else if (engine.controls && engine.controls.target && typeof engine.controls.target.copy === 'function') {
                        engine.controls.target.copy(lockTarget);
                    }
                }

                const coreX = x * TILE_SIZE;
                const coreY = y * TILE_SIZE;
                const coreW = Math.min(TILE_SIZE, artWidth - coreX);
                const coreH = Math.min(TILE_SIZE, artHeight - coreY);

                const vViewX = (coreX - PAD) * SSAA;
                const vViewY = (coreY - PAD) * SSAA;

                engine.camera.setViewOffset(virtualArtW, virtualArtH, vViewX, vViewY, viewW, viewH);

                // FIX: Use standard render (renderAsync is deprecated)
                if (engine.composer) engine.composer.render();
                else engine.renderer.render(engine.scene, engine.camera);

                await new Promise(resolve => requestAnimationFrame(resolve));
                await new Promise(resolve => requestAnimationFrame(resolve));

                // ==========================================
                // 🛑 WEBGPU HARDWARE ACCELERATION BYPASS
                // ==========================================
                const tempCanvas = document.createElement('canvas');
                tempCanvas.width = coreW * SSAA;
                tempCanvas.height = coreH * SSAA;
                const tempCtx = tempCanvas.getContext('2d');

                // 1. EXTRACTION: Crop the padding and pull from the WebGPU engine
                tempCtx.drawImage(
                    engine.renderer.domElement, 
                    PAD * SSAA, PAD * SSAA, coreW * SSAA, coreH * SSAA,   
                    0, 0, coreW * SSAA, coreH * SSAA                            
                );

                // 2. GRADING & STAMPING: Stamp it onto the Master Print Canvas
                ctx.filter = 'saturate(1.1)'; // Slight punch, engine handles exposure
                ctx.drawImage(
                    tempCanvas,
                    0, 0, coreW * SSAA, coreH * SSAA,
                    coreX, coreY, coreW, coreH
                );

                // --- DEBUG BORDERS ---
                if (this.DEBUG_MODE) {
                    ctx.strokeStyle = "rgba(255, 0, 0, 0.8)";
                    ctx.lineWidth = 10;
                    ctx.strokeRect(coreX, coreY, coreW, coreH);
                }

                await new Promise(resolve => setTimeout(resolve, 30));
            }
        }

        if (this.DEBUG_MODE && !isAborted) console.log(`\n✅ Grid assembly complete. Restoring system state...`);
        // ------------------------------------------

        // ==========================================
        // 🧹 RESTORE ORIGINAL STATE
        // ==========================================
        // 1. Restore the background transparency
        engine.renderer.setClearColor(origClearColor, origClearAlpha);
        
        // 2. Shrink ALL the stars, restore their original dimness, and restore color
        originalPointMats.forEach((orig, mat) => {
            mat.size = orig.size;
            if (orig.opacity !== undefined) mat.opacity = orig.opacity;
            if (orig.origHex !== null && mat.color) mat.color.setHex(orig.origHex);
            mat.needsUpdate = true;
        });

        engine.renderer.toneMappingExposure = originalExposure;
        
        if (engine.uBloomRadius) engine.uBloomRadius.value = origBloomRadius;
        if (engine.uBloomStrength) engine.uBloomStrength.value = origBloomStrength;

        cableClones.forEach(clone => engine.scene.remove(clone));
        cableClones.length = 0; // Empty the trash

        // 👻 DEACTIVATE STEALTH MODE: Restore UI & HUDS
        uiElementsToHide.forEach(el => el.style.display = originalDisplays.get(el));
        hidden3DObjects.forEach(obj => obj.visible = true);

        originalLineMats.forEach((origState, material) => {
            material.opacity = origState.opacity;
            material.blending = origState.blending;
            if (material.color && origState.origHex !== null) material.color.setHex(origState.origHex);
            material.needsUpdate = true;
        });

        engine.camera.clearViewOffset();
        engine.renderer.setSize(origW, origH, false);
        engine.renderer.setPixelRatio(origPixelRatio);
        if (engine.composer && typeof engine.composer.setSize === 'function') {
            engine.composer.setSize(origW, origH);
        }
        engine.camera.aspect = origAspect;
        engine.camera.updateProjectionMatrix();
        
        if (labelsWereVisible) window.toggleLabels(); 

        // 👇 NEW: The graceful exit. 
        // We wait until AFTER the scene is cleaned up to throw the error and stop Stripe.
        if (isAborted) {
            throw new Error("Render cancelled by user.");
        }

        // ==========================================
        // 🛡️ THE FAILSAFE CHECK (BEFORE TYPOGRAPHY!)
        // ==========================================
        if (!this._verifyRenderIntegrity(canvas)) {
            
            // 🛑 VISUAL ERROR: Stop the pipeline and alert the user
            throw new Error(
                "Hardware Resource Mismatch\n\n" +
                "Your current device's GPU memory (VRAM) is insufficient to process the extreme resolution required for this high-fidelity print.\n\n" +
                "To resolve this, please select a smaller print size, or access GitGalaxy from a machine with a dedicated graphics card."
            );
        }

        // ✅ THE STAMP: Draw text & legend ONCE at the very end!
        this.drawTypography(ctx, targetW, targetH, raw);
        this.drawLegend(ctx, targetW, targetH, engine.uMetricMode.value);

        // Snap the live 3D canvas back to the current window size just in case they resized!
        window.dispatchEvent(new Event('resize'));

        return canvas;
    }

    // --- PHASE 3: CHECKOUT PIPELINE (PHYSICAL PRINTS DISABLED) ---
    async initiateCheckout(sizeString, buttonElement) {
        if (this.active) return;
        this.active = true;

        const originalText = buttonElement.innerText;
        buttonElement.disabled = true;

        try {
            if (this.DEBUG_MODE) console.log(`\n🛒 Initiating pipeline for: ${sizeString}...`);
            const [targetW, targetH] = sizeString.split('x').map(Number);
            
            buttonElement.innerText = "Please Keep Tab Open... ⚙️";
            await new Promise(resolve => setTimeout(resolve, 50));

            // 1. Render the massive canvas
            const canvas = await this._renderTiledPrintCanvas(targetW, targetH, buttonElement);

            // 2. Extract the data URL
            const imageDataUrl = canvas.toDataURL('image/jpeg', 0.95);

            // ==========================================
            // 🎁 THE "FREE GIFT" AUTO-DOWNLOAD
            // ==========================================
            buttonElement.innerText = "Downloading Master File... 💾";
            const raw = window.currentRawGalaxyData;
            const targetName = raw?.meta?.session?.target || "Unknown_Sector";
            const filename = `GitGalaxy_${targetName.replace(/[^a-zA-Z0-9]/g, '_')}_${sizeString}_Master.jpg`;
            
            this.download(imageDataUrl, filename);
            
            // Wait half a second to ensure the browser registers the download
            await new Promise(resolve => setTimeout(resolve, 500)); 

            // ==========================================
            // 🛑 THE CHECKOUT INTERCEPT
            // ==========================================
            buttonElement.innerText = "Render Complete! ✨";
            
            // Hide the Gift Shop HUD so it doesn't clutter the screen
            document.getElementById('gift-shop-hud').style.display = 'none';

            // Calculate exact specs
            const megapixels = ((targetW * targetH) / 1000000).toFixed(1);
            const inchW = targetW / 300;
            const inchH = targetH / 300;

            // Populate the list in the modal
            document.getElementById('render-specs-list').innerHTML = `
                <li><span style="color: #fff;">Physical Dimensions:</span> ${inchW}" x ${inchH}"</li>
                <li><span style="color: #fff;">Resolution:</span> ${targetW} x ${targetH} Pixels</li>
                <li><span style="color: #fff;">Pixel Density:</span> 300 DPI (Print-Ready)</li>
                <li><span style="color: #fff;">Raw Size:</span> ${megapixels} Megapixels</li>
            `;

            const promptHud = document.getElementById('checkout-prompt-hud');
            const btnDecline = document.getElementById('btn-decline-print');
            const btnAccept = document.getElementById('btn-accept-print');

            // Reset buttons in case they previously clicked it
            btnAccept.innerHTML = `YES, SHIP ME THE POSTER <span>→</span>`;
            btnAccept.style.background = "var(--accent)";
            btnAccept.style.color = "#000";
            btnDecline.style.display = 'block';

            promptHud.style.display = 'flex';

            // Wait for the user's decision using a Promise
            const userDecision = await new Promise((resolve) => {
                const handleDecline = () => { cleanup(); resolve(false); };
                const handleAccept = () => { cleanup(); resolve(true); };
                
                const cleanup = () => {
                    btnDecline.removeEventListener('click', handleDecline);
                    btnAccept.removeEventListener('click', handleAccept);
                };

                btnDecline.addEventListener('click', handleDecline);
                btnAccept.addEventListener('click', handleAccept);
            });

            if (!userDecision) {
                // User clicked "No Thanks"
                promptHud.style.display = 'none';
                buttonElement.innerText = originalText;
                buttonElement.disabled = false;
                this.active = false;
                this.unlockCamera();
                return; // Stop the pipeline here!
            }

            // ==========================================
            // 🛑 COMING SOON INTERCEPT (Stripe Disabled)
            // ==========================================
            // If they click YES, show the coming soon message
            btnAccept.innerHTML = "PHYSICAL PRINTS COMING SOON! 🚀";
            btnAccept.style.background = "transparent";
            btnAccept.style.color = "var(--accent)";
            btnAccept.style.cursor = "default";
            
            btnDecline.style.display = 'none'; // Hide the 'no' button to focus attention

            // Give them 3.5 seconds to read the message, then automatically close the HUD
            await new Promise(resolve => setTimeout(resolve, 3500));
            
            // Clean up and restore everything to normal
            promptHud.style.display = 'none';
            buttonElement.innerText = originalText;
            buttonElement.disabled = false;
            this.active = false;
            this.unlockCamera(); 

        } catch (error) {
            console.error("❌ Checkout Pipeline Error:", error);
            
            if (error.message !== "Render cancelled by user.") {
                alert(error.message);
            }
            
            document.getElementById('checkout-prompt-hud').style.display = 'none';
            buttonElement.innerText = originalText;
            buttonElement.disabled = false;
            this.active = false;
            this.unlockCamera(); 
        }
    }

    drawTypography(ctx, w, h, raw) {
        const margin = w * 0.05;
        const scale = w / 3600; 

        const targetName = (raw.meta?.session?.target || "GIT_ARCHIVE").toUpperCase(); 

        ctx.shadowColor = "rgba(0, 0, 0, 0.8)";
        ctx.shadowBlur = 20 * scale;
        ctx.shadowOffsetX = 0;
        ctx.shadowOffsetY = 5 * scale;

        ctx.fillStyle = "#ffffff";
        ctx.textAlign = "left";
        ctx.textBaseline = "top"; 
        ctx.font = `900 ${140 * scale}px 'Space Grotesk', sans-serif`;
        ctx.fillText(targetName, margin, margin); 

        ctx.fillStyle = "#00f3ff"; 
        ctx.textAlign = "right";
        ctx.textBaseline = "bottom";
        ctx.font = `700 ${50 * scale}px 'Space Mono', monospace`; 
        ctx.fillText("gitgalaxy.io", w - margin, h - margin); 
        
        ctx.shadowColor = "transparent";
        ctx.shadowBlur = 0;
    }

    drawLegend(ctx, w, h, metricMode) {
        // 1. Abort if we are in Standard (0) or Language Identity (14) modes
        if (!metricMode || metricMode === 0 || metricMode === 14) return;

        // 2. Map the engine's numeric uniform to the Colors.js schema key
        const metricMap = {
            1: 'cognitive_load', 2: 'safety_score', 3: 'tech_debt',
            4: 'verification', 5: 'api_exposure', 6: 'concurrency',
            7: 'state_flux', 8: 'graveyard', 9: 'spec_match',
            10: 'stability', 11: 'churn', 12: 'documentation',
            13: 'civil_war'
        };

        const metricKey = metricMap[metricMode];
        if (!metricKey || !window.Colors || !window.Colors.LEGENDS[metricKey]) return;

        const legend = window.Colors.LEGENDS[metricKey];
        const scale = w / 3600; 
        const margin = w * 0.05;
        
        // 3. Define the HUD Box Dimensions
        const boxW = 800 * scale;
        const boxH = 180 * scale;
        const boxX = w - margin - boxW;
        const boxY = margin;

        // ==========================================
        // 🚀 OPTIMIZATION: OFFSCREEN CANVAS CACHING
        // ==========================================
        // We draw the complex vectors on a tiny canvas to avoid lagging the 54MP main canvas
        const legCanvas = document.createElement('canvas');
        legCanvas.width = boxW;
        legCanvas.height = boxH;
        const lCtx = legCanvas.getContext('2d');

        // 4. Draw the semi-transparent HUD Background (at 0,0 on the mini canvas)
        lCtx.fillStyle = "rgba(0, 0, 0, 0.85)";
        lCtx.strokeStyle = "rgba(51, 51, 51, 0.8)"; 
        lCtx.lineWidth = 2 * scale;
        
        lCtx.beginPath();
        if (lCtx.roundRect) {
            lCtx.roundRect(0, 0, boxW, boxH, 12 * scale);
        } else {
            lCtx.rect(0, 0, boxW, boxH); 
        }
        lCtx.fill();
        lCtx.stroke();

        const pad = 40 * scale;

        // 5. Draw the Header Text
        lCtx.fillStyle = "#00f3ff"; 
        lCtx.textAlign = "left";
        lCtx.textBaseline = "top";
        lCtx.font = `700 ${36 * scale}px 'Space Grotesk', sans-serif`;
        lCtx.fillText(`SYSTEM ANALYSIS: ${legend.title.toUpperCase()}`, pad, pad);

        // 6. Build the Gradient Color Bar
        const barX = pad;
        const barY = pad + 60 * scale;
        const barW = boxW - (pad * 2);
        const barH = 16 * scale;

        const gradient = lCtx.createLinearGradient(barX, 0, barX + barW, 0);
        
        if (legend.colors && legend.colors.length > 0) {
            const step = 1 / (legend.colors.length - 1);
            legend.colors.forEach((col, idx) => gradient.addColorStop(idx * step, col));
        } else {
            gradient.addColorStop(0, "#ffffff"); 
            gradient.addColorStop(1, "#ff0000");
        }

        lCtx.fillStyle = gradient;
        lCtx.fillRect(barX, barY, barW, barH);
        
        lCtx.strokeStyle = "rgba(255, 255, 255, 0.3)";
        lCtx.lineWidth = 1 * scale;
        lCtx.strokeRect(barX, barY, barW, barH);

        // 7. Draw the Min/Max Labels
        lCtx.fillStyle = "rgba(255, 255, 255, 0.9)";
        lCtx.font = `700 ${24 * scale}px 'Space Mono', monospace`;
        lCtx.textBaseline = "top";
        
        lCtx.textAlign = "left";
        lCtx.fillText(legend.labels[0], barX, barY + barH + 12 * scale);
        
        lCtx.textAlign = "right";
        lCtx.fillText(legend.labels[legend.labels.length - 1], barX + barW, barY + barH + 12 * scale);

        // ==========================================
        // 💥 THE STAMP
        // ==========================================
        // Stamp the fully rendered mini-canvas onto the giant canvas instantly
        ctx.drawImage(legCanvas, boxX, boxY);
    }

    download(url, filename) {
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    // --- SAFETY FAILSAFE: Scans the final canvas to ensure it didn't crash to black ---
    _verifyRenderIntegrity(canvas) {
        // To save CPU time on a massive 54MP canvas, we shrink it to 50x50 pixels 
        // to average out the colors, then check the data.
        const inspector = document.createElement('canvas');
        inspector.width = 50;
        inspector.height = 50;
        const ctx = inspector.getContext('2d');
        ctx.drawImage(canvas, 0, 0, 50, 50);

        const imgData = ctx.getImageData(0, 0, 50, 50).data;
        let isBlank = true;

        // Loop through the pixels. If we find anything significantly brighter 
        // than your background color (#010103), the render was successful.
        for (let i = 0; i < imgData.length; i += 4) {
            const r = imgData[i];
            const g = imgData[i + 1];
            const b = imgData[i + 2];

            // Background is roughly rgb(1, 1, 3). If any channel is over 10, we have stars!
            if (r > 10 || g > 10 || b > 10) {
                isBlank = false;
                break;
            }
        }

        return !isBlank; // Returns true if safe, false if it crashed
    }
}



window.Poster = new PosterGenerator();