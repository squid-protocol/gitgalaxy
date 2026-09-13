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
 * ACCESSIBILITY ENGINE (The Parallel Universe)
 * v6.2 - "The Map IS The Territory"
 * Creates a semantic Shadow DOM (<ul> tree) that mirrors the 3D Galaxy.
 * Translates visual physics (color, shape) into semantic descriptions.
 * Ensures the Museum of Code is accessible to blind engineers.
 */

class A11yEngine {
    constructor() {
        this.active = false;
        this.root = null;
        this.liveRegion = null;
        this.init(); 
    }

    init() {
        // 1. Create the Shadow Container (Off-screen but focusable)
        this.root = document.createElement('div');
        this.root.id = 'a11y-tree';
        this.root.setAttribute('role', 'tree');
        this.root.setAttribute('aria-label', 'Code Galaxy Directory Structure');
        
        Object.assign(this.root.style, {
            position: 'absolute',
            left: '-10000px',
            top: '0',
            width: '1px',
            height: '1px',
            overflow: 'hidden'
        });

        document.body.appendChild(this.root);

        // 2. Create Live Region for Announcements
        this.liveRegion = document.createElement('div');
        this.liveRegion.id = 'a11y-narrator';
        this.liveRegion.setAttribute('aria-live', 'polite');
        this.liveRegion.setAttribute('aria-atomic', 'true');
        Object.assign(this.liveRegion.style, {
            position: 'absolute',
            left: '-10000px'
        });
        
        document.body.appendChild(this.liveRegion);
    }

    announce(message) {
        if (this.liveRegion) {
            this.liveRegion.innerText = message;
        }
    }

    // --- NEW: V6.2 DATA INGESTION ---
    loadGalaxy(activeFiles) {
        this.root.innerHTML = ''; 
        
        if (!activeFiles || activeFiles.length === 0) return;

        const treeStructure = this.buildTree(activeFiles);
        this.renderTree(treeStructure, this.root);

        // Set the first item as focusable so the user can enter the tree
        const firstItem = this.root.querySelector('[role="treeitem"]');
        if (firstItem) firstItem.setAttribute('tabindex', '0');

        this.announce(`System Loaded. Contains ${activeFiles.length} artifacts. Use arrow keys to navigate the directory tree.`);
        this.active = true;
    }

    buildTree(data) {
        const root = { name: 'Root', children: {}, files: [] };
        
        // Loop through the engine's pre-built array
        data.forEach((node, index) => {
            node.id = index; // Store the global ID for the camera hook

            const parts = node.path ? node.path.split('/') : [node.name];
            let current = root;
            
            // Navigate and create folders
            for (let i = 0; i < parts.length - 1; i++) {
                const folder = parts[i];
                if (!current.children[folder]) {
                    current.children[folder] = { name: folder, children: {}, files: [] };
                }
                current = current.children[folder];
            }
            
            current.files.push(node);
        });
        
        return root;
    }

    renderTree(node, container) {
        const ul = document.createElement('ul');
        ul.setAttribute('role', 'group');

        // Render Subfolders
        Object.values(node.children).forEach(folder => {
            const li = document.createElement('li');
            li.setAttribute('role', 'treeitem');
            li.setAttribute('aria-expanded', 'false');
            li.setAttribute('tabindex', '-1');
            li.innerText = `📁 ${folder.name}`;
            
            li.addEventListener('keydown', (e) => this.handleNavigation(e, li));
            
            ul.appendChild(li);
            this.renderTree(folder, li); // Recurse
        });

        // Render Files
        node.files.forEach(file => {
            const li = document.createElement('li');
            li.setAttribute('role', 'treeitem');
            li.setAttribute('tabindex', '-1');
            
            // Translate Visual Truth to Text
            const description = this.generateDescription(file);
            li.setAttribute('aria-label', `${file.name}. ${description}`);
            li.innerText = `📄 ${file.name}`;
            
            // --- NEW: V6.2 CAMERA HOOK ---
            // When a blind user tabs to this element, fly the 3D camera there 
            // so sighted colleagues see exactly what they are inspecting!
            li.addEventListener('focus', () => {
                if (window.App && window.App.engine) {
                    window.App.engine.flyTo(file.pos, file.id);
                    if (typeof window.App.engine.showHUD === 'function') {
                        window.App.engine.showHUD(file.id);
                    }
                }
            });

            li.addEventListener('keydown', (e) => this.handleNavigation(e, li));

            ul.appendChild(li);
        });

        container.appendChild(ul);
    }

    // --- NEW: V6.2 PHYSICS TRANSLATOR ---
    generateDescription(file) {
        // 1. Determine Shape
        let shape = "Sphere (Data or Config)";
        if (file.mass < 200) shape = "Small Dot";
        else if (file.logicRatio >= 0.975) shape = "Tetrahedron (Pure Logic)";
        else if (file.logicRatio >= 0.90) shape = "Octahedron (Algorithmic)";
        else if (file.logicRatio >= 0.85) shape = "Dodecahedron (Business Logic)";
        else if (file.logicRatio >= 0.75) shape = "Icosahedron (Declarative)";

        let desc = `Shape: ${shape}. Mass: ${Math.round(file.mass)}. `;

        // 2. Determine Satellites (Moons)
        if (file.sats_count && file.sats_count > 0) {
            desc += `Orbiting ${file.sats_count} satellite functions. `;
        }

        // 3. Determine Popularity (Rings)
        if (file.importCount && file.importCount > 5) {
            desc += `Surrounded by a dense dependency ring (Popularity score: ${file.importCount}). `;
        }

        // 4. Determine Risks
        // Engine normalizes vectors to 1000. 500 = 50% surface presence.
        // Structural Surface Profile (formerly "risk exposure") -- gitgalaxy#2991.
        const risks = file.risks || [];
        const highRisks = [];
        if ((risks[0] || 0) > 500) highRisks.push("Complexity Load");
        if ((risks[1] || 0) > 500) highRisks.push("Guard Balance");
        if ((risks[2] || 0) > 500) highRisks.push("Debt Markers");
        if ((risks[10] || 0) > 500) highRisks.push("Seismic Churn (Historical Churn, predictive layer pending #2987)");

        if (highRisks.length > 0) {
            desc += `Warning: high structural surface in ${highRisks.join(', ')}.`;
        } else {
            desc += "System stable.";
        }

        return desc;
    }

    handleNavigation(e, element) {
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            this.focusNext(element);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            this.focusPrev(element);
        } else if (e.key === 'ArrowRight') {
            e.preventDefault();
            if (element.getAttribute('aria-expanded') === 'false') {
                element.setAttribute('aria-expanded', 'true');
            } else {
                const firstChild = element.querySelector('ul > li');
                if (firstChild) {
                    element.setAttribute('tabindex', '-1');
                    firstChild.setAttribute('tabindex', '0');
                    firstChild.focus();
                }
            }
        } else if (e.key === 'ArrowLeft') {
            e.preventDefault();
            if (element.getAttribute('aria-expanded') === 'true') {
                element.setAttribute('aria-expanded', 'false');
            } else {
                const parentLi = element.parentElement.closest('li[role="treeitem"]');
                if (parentLi) {
                    element.setAttribute('tabindex', '-1');
                    parentLi.setAttribute('tabindex', '0');
                    parentLi.focus();
                }
            }
        }
    }

    focusNext(element) {
        const focusable = this.getVisibleNodes();
        const index = focusable.indexOf(element);
        if (index > -1 && index < focusable.length - 1) {
            element.setAttribute('tabindex', '-1');
            focusable[index + 1].setAttribute('tabindex', '0');
            focusable[index + 1].focus();
        }
    }

    focusPrev(element) {
        const focusable = this.getVisibleNodes();
        const index = focusable.indexOf(element);
        if (index > 0) {
            element.setAttribute('tabindex', '-1');
            focusable[index - 1].setAttribute('tabindex', '0');
            focusable[index - 1].focus();
        }
    }

    getVisibleNodes() {
        // Only return nodes where all parent folders are currently expanded
        return Array.from(this.root.querySelectorAll('li[role="treeitem"]')).filter(el => {
            let parent = el.parentElement.closest('li[role="treeitem"]');
            while (parent) {
                if (parent.getAttribute('aria-expanded') !== 'true') return false;
                parent = parent.parentElement.closest('li[role="treeitem"]');
            }
            return true;
        });
    }
}

// Auto-Instantiate globally
window.Ally = new A11yEngine();