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
 * COLORS & PALETTE REGISTRY v6.0 (Unified A11y Spectrum)
 * Defines the "Visual Semantics" of the universe.
 * * INTEGRATED: Unified High-Contrast "Turbo" Spectrum for all Risk Metrics.
 */

// --- 1. THE UNIVERSAL RISK SPECTRUM ---
// The master color ramp used for all risk and exposure metrics.
const UNIVERSAL_GRADIENT = "linear-gradient(90deg, #0055ff 0%, #00ffff 25%, #ffff00 50%, #ff8800 75%, #ff0000 100%)";
const UNIVERSAL_COLORS = ["#0055ff", "#00ffff", "#ffff00", "#ff8800", "#ff0000"];

const Colors = {
    // 2. LANGUAGE IDENTITY PALETTE (Spec 2.2.R)
    LANGUAGES: {
        'javascript': 0xF1E05A, 'js': 0xF1E05A,
        'typescript': 0x0099FF, 'ts': 0x0099FF,
        'python': 0x5C95FF, 'py': 0x5C95FF,
        'java': 0xE69F50,
        'c': 0xA8B9CC,
        'c++': 0xFF2E8C, 'cpp': 0xFF2E8C,
        'rust': 0xFF7B00, 'rs': 0xFF7B00,
        'go': 0x00E0FF,
        'c#': 0x49E33B, 'cs': 0x49E33B,
        'php': 0x9B86FF,
        'ruby': 0xFF4040, 'rb': 0xFF4040,
        'swift': 0xFF6A00,
        'kotlin': 0xC792EA, 'kt': 0xC792EA,
        'objective-c': 0x4DA6FF, 'm': 0x4DA6FF,
        'shell': 0x00FF00, 'bash': 0x00FF00, 'sh': 0x00FF00,
        'perl': 0x00C4FF, 'pl': 0x00C4FF,
        'lua': 0x5E80FF,
        'haskell': 0xD0A0FF, 'hs': 0xD0A0FF,
        'sql': 0xFF9900,
        'html': 0xFF5500, 'css': 0xFF5500,
        'fortran': 0x9A72FF, 'f90': 0x9A72FF,
        'assembly': 0xFFD080, 'asm': 0xFFD080,
        'cobol': 0x66AAFF, 'cbl': 0x66AAFF,
        'makefile': 0x00FF00, 
        'json': 0x00FFFF, 'yaml': 0x00FFFF, 'yml': 0x00FFFF, 'xml': 0x00FFFF,
        'markdown': 0xFFFFE0, 'md': 0xFFFFE0, 'txt': 0xFFFFE0, 'csv': 0xFFFFE0,
        'dockerfile': 0x00B0FF, 'docker': 0x00B0FF,
        'bin': 0x505050, 'exe': 0x505050
    },

    // High-Visibility fallback palette for unknown languages
    FALLBACK_PALETTE: [
        0xFF007F, // Neon Pink
        0x00FF00, // Lime Green
        0x00F3FF, // Cyan
        0xFFD700, // Gold
        0xBF00FF, // Magenta
        0xFF5500, // Bright Orange
        0x00FF99, // Spring Green
        0xBFFF00, // Chartreuse
        0xFF00FF, // Fuchsia
        0x0088FF, // Azure
        0xFF4444, // Coral Red
        0x88FF00  // Neon Yellow-Green
    ],

    getLanguageColor: (langString) => {
        if (!langString) return 0xffffff;
        const normalized = langString.toLowerCase().trim();
        
        if (Colors.LANGUAGES[normalized]) return Colors.LANGUAGES[normalized];

        // Deterministic hash to map an unknown language string to a fixed, high-vis color
        let hash = 0;
        for (let i = 0; i < normalized.length; i++) {
            hash = normalized.charCodeAt(i) + ((hash << 5) - hash);
        }
        
        const index = Math.abs(hash) % Colors.FALLBACK_PALETTE.length;
        return Colors.FALLBACK_PALETTE[index];
    },

    // 3. HUD LEGEND CONFIGURATION (Stripped of redundant colors)
    LEGENDS: {
        cognitive_load: { title: "Cognitive Load Exposure", bins: [20, 40, 60, 90], labels: ["VERY LOW", "LOW", "INTERMEDIATE", "HIGH", "VERY HIGH"] },
        safety_score: { title: "Error & Exception Exposure", bins: [10, 40, 60, 80], labels: ["VERY LOW", "LOW", "INTERMEDIATE", "HIGH", "VERY HIGH"] },
        tech_debt: { title: "Tech Debt Exposure", bins: [20, 40, 60, 80], labels: ["VERY LOW", "LOW", "INTERMEDIATE", "HIGH", "VERY HIGH"] },
        verification: { title: "Testing & Verification Exposure", bins: [10, 40, 60, 80], labels: ["IRONCLAD", "LOW", "MODERATE", "HIGH", "VERY HIGH"] },
        api_exposure: { title: "API Exposure", bins: [20, 40, 60, 80], labels: ["VERY LOW", "LOW", "MODERATE", "HIGH", "VERY HIGH"] },
        concurrency: { title: "Concurrency Exposure", bins: [20, 50, 80], labels: ["LOW", "MODERATE", "HIGH", "VERY HIGH"] },
        state_flux: { title: "State Flux Exposure", bins: [20, 40, 60, 80], labels: ["VERY LOW", "LOW", "MODERATE", "HIGH", "VERY HIGH"] },
        graveyard: { title: "Graveyard (Dead Code)", bins: [10, 30, 50, 70], labels: ["CLEAN", "LOW", "INTERMEDIATE", "HIGH", "GRAVEYARD"] },
        dead_code: { title: "Graveyard (Dead Code)", bins: [10, 30, 50, 70], labels: ["CLEAN", "LOW", "INTERMEDIATE", "HIGH", "GRAVEYARD"] },
        spec_match: { title: "Spec Alignment", bins: [20, 40, 60, 90], labels: ["HIGHLY ALIGNED", "ALIGNED", "MODERATE", "LOW", "VERY LOW"] },
        stability: { title: "Stability (Recent Commits)", bins: [20, 40, 60, 80], labels: ["HOT/NEW", "RECENT", "ACTIVE", "ESTABLISHED", "ENDURING"] },
        churn: { title: "Deep Churn", bins: [20, 40, 60, 80], labels: ["STATIC", "SETTLED", "FLUID", "ACTIVE", "HIGHLY ACTIVE"] },
        documentation: { title: "Documentation Risk", bins: [20, 40, 60, 90], labels: ["THOROUGH", "LOW", "MODERATE", "HIGH", "UNDOCUMENTED"] },
        ownership: { title: "Authorship", bins: [20, 40, 60, 80], labels: ["INDIVIDUAL", "SMALL TEAM", "SQUAD", "DEPT", "COMMUNITY"] },
        algorithmic_dos: { title: "Algorithmic DoS Exposure", bins: [10, 40, 60, 80], labels: ["SECURE", "LOW", "MODERATE", "HIGH", "CRITICAL"] },
        obscured_payload: { title: "Obfuscation & Evasion Surface", bins: [10, 40, 60, 80], labels: ["SECURE", "LOW", "MODERATE", "HIGH", "CRITICAL"] },
        logic_bomb: { title: "Logic Bomb Exposure", bins: [10, 40, 60, 80], labels: ["SECURE", "LOW", "MODERATE", "HIGH", "CRITICAL"] },
        injection_surface: { title: "Injection Surface Exposure", bins: [10, 40, 60, 80], labels: ["SECURE", "LOW", "MODERATE", "HIGH", "CRITICAL"] },
        memory_corruption: { title: "Raw Memory Manipulation Exposure", bins: [10, 40, 60, 80], labels: ["SECURE", "LOW", "MODERATE", "HIGH", "CRITICAL"] },
        secrets_risk: { title: "Hardcoded Secrets Exposure", bins: [10, 40, 60, 80], labels: ["SECURE", "LOW", "MODERATE", "HIGH", "CRITICAL"] },

        // Custom Diverging Spectrum (Excluded from Universal Injection)
        civil_war: { 
            title: "Civil War (Tabs vs Spaces)", 
            gradient: "linear-gradient(90deg, #39ff14 0%, #0000ff 50%, #ffff00 100%)", 
            bins: [20, 80], labels: ["TABS", "MIXED", "SPACES"],
            colors: ["#39ff14", "#0000ff", "#ffff00"]
        },
        tabs_vs_spaces: { 
            title: "Civil War (Tabs vs Spaces)", 
            gradient: "linear-gradient(90deg, #39ff14 0%, #0000ff 50%, #ffff00 100%)", 
            bins: [20, 80], labels: ["TABS", "MIXED", "SPACES"],
            colors: ["#39ff14", "#0000ff", "#ffff00"]
        },

        language_identity: {
            title: "Language Identity",
            isCategorical: true,
            isDynamicLanguage: true
        },
        
        file_architecture: {
            title: "File Architecture (Current Research, unvalidated)", 
            isCategorical: true,
            colors: [
                "#FF3B30", "#FF9500", "#FFCC00", "#FFEE58", "#A4E720", 
                "#28CD41", "#00C7BE", "#59C8FA", "#007AFF", "#5856D6", 
                "#AF52DE", "#FF2D55", "#F9A8D4", "#E5E5EA", "#A2845E", 
                "#64748B" // 15: Preprocessor Macros
            ],
            labels: [
                "0: Annotated Service Layer",
                "1: Universal Dependencies",
                "2: Inert Config & Data",
                "3: High-Density Dependency Injection",
                "4: Software Verification & Testing",
                "5: Build, Infra & I/O Automation",
                "6: High-Dependency C Headers",
                "7: Raw Pointer & Memory",
                "8: Test-Driven Annotated Services",
                "9: Functional OOP & Async Logic",
                "10: Object-Oriented Structures",
                "11: Algorithmic & Defensive Logic",
                "12: Documented Core Interfaces",
                "13: Documented Native Headers",
                "14: UI Frameworks & View Layers",
                "15: Preprocessor Macros"
            ]
        }
    },

    // 4. THEME REGISTRY
    THEMES: {
        'ice-crystal': {
            name: "Ice Crystal",
            bg: 0x020205,         
            basalColor: 0xffffff,  
            basalVariance: [0xffffff, 0xadd8e6, 0xffe4e1, 0x87cefa, 0xffd1dc]
        },
        'galactic': {
            name: "Galactic",
            bg: 0x050508,         
            basalColor: 0x00f3ff,  
            basalPalette: [0xbc13fe, 0xffaa00, 0x00f3ff, 0xbfff00, 0xff00ff, 0x00ff00, 0xff0033, 0xffe600, 0x2200ff, 0xffffff]           
        },
        'matrix': {
            name: "The Matrix",
            bg: 0x000000,         
            basalColor: 0x00ff41,  
            basalVariance: [0x00ff41, 0x00dd33, 0x00bb22]
        },
        'high-vis': {
            name: "High-Visibility",
            bg: 0x000000,           
            basalColor: 0xffffff
        }
    },

    // 5. LEGACY FALLBACK (For older UI components requiring a strict hex return)
    getMetricColor: (mode, score) => {
        if (mode === 'none' || mode === 'default') return 0xcccccc;
        if (mode === 'civil_war') return score < 20 ? 0x39ff14 : (score > 80 ? 0xffff00 : 0x0000ff);
        
        // Safely map the 0-100 score to the 5-stop Universal Palette
        const idx = Math.min(4, Math.max(0, Math.floor(score / 20)));
        return parseInt(UNIVERSAL_COLORS[idx].replace('#', '0x'));
    }
};

// --- GLOBAL METRIC COLOR INJECTION ---
// Automatically wires up the UI Legends to the Universal Spectrum
Object.keys(Colors.LEGENDS).forEach(key => {
    // Skip diverging scales AND categorical palettes like File Architecture and Language
    if (key === 'civil_war' || key === 'tabs_vs_spaces' || Colors.LEGENDS[key].isCategorical) return; 

    Colors.LEGENDS[key].gradient = UNIVERSAL_GRADIENT;
    Colors.LEGENDS[key].colors = UNIVERSAL_COLORS.slice(0, Colors.LEGENDS[key].labels.length);
});

window.Colors = Colors;
