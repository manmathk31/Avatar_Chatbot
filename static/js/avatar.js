import * as THREE from 'https://unpkg.com/three@0.160.0/build/three.module.js';
import { FBXLoader } from 'https://unpkg.com/three@0.160.0/examples/jsm/loaders/FBXLoader.js';

let scene, camera, renderer;
let avatar, mixer;
let avatarHeadMesh = null;

// Shape Key Indices
let mouthKeyIndex = null;
let blinkKeyIndex = null;

// State Flags
let isTalking = false;

// Speech Logic Variables
let speechTarget = 0;
let lastSpeechUpdate = 0;
let speechSpeed = 150; // How fast she changes syllables (ms)

// Blink Logic Variables
let isBlinking = false;
let blinkTarget = 0;
let lastBlinkTime = 0;
let nextBlinkInterval = 3000;

window.addEventListener('DOMContentLoaded', () => {
    console.log("🚀 SCRIPT STARTED: Procedural Animation Mode");
    initAvatar();
    // Controls removed - auto-sync enabled
});

function initAvatar() {
    const container = document.getElementById('avatar-canvas');
    if (!container) return;

    // 1. SCENE
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x333333);

    // 2. CAMERA
    camera = new THREE.PerspectiveCamera(35, container.clientWidth / container.clientHeight, 0.1, 1000);
    camera.position.set(0, 0.55, 1.1);

    // 3. RENDERER
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(renderer.domElement);

    // 4. LIGHTS
    const ambientLight = new THREE.AmbientLight(0xffffff, 1.2);
    scene.add(ambientLight);
    const mainLight = new THREE.DirectionalLight(0xffffff, 2.0);
    mainLight.position.set(2, 2, 5);
    scene.add(mainLight);

    // 5. LOAD AVATAR
    const loader = new FBXLoader();
    loader.load('/static/models/Catwalk Idle.fbx', (object) => {
        avatar = object;
        scene.add(avatar);

        // Scale & Position
        const box = new THREE.Box3().setFromObject(avatar);
        const size = box.getSize(new THREE.Vector3());
        if (size.y > 0) {
            const scaleFactor = 1.6 / size.y;
            avatar.scale.multiplyScalar(scaleFactor);
        }

        const newBox = new THREE.Box3().setFromObject(avatar);
        const center = newBox.getCenter(new THREE.Vector3());
        avatar.position.x = -center.x;
        avatar.position.z = -center.z;
        avatar.position.y = -0.8;

        camera.lookAt(0, 0.5, 0);

        // Texture Fix
        avatar.traverse((child) => {
            if (child.isMesh) {
                const oldMap = child.material ? child.material.map : null;
                const color = oldMap ? 0xffffff : 0xcccccc;
                child.material = new THREE.MeshStandardMaterial({
                    color: color,
                    map: oldMap,
                    roughness: 0.5,
                    metalness: 0.1,
                    side: THREE.DoubleSide
                });
            }
        });

        setupMusclesAndAnimation(object);
        animate();

    }, undefined, (e) => console.error(e));
}

function setupMusclesAndAnimation(object) {
    // 1. Find the Head
    avatarHeadMesh = avatar.getObjectByName('AvatarHead');
    if (!avatarHeadMesh) {
        avatar.traverse((child) => {
            if (child.isMesh && child.morphTargetDictionary && !avatarHeadMesh) {
                if (!child.name.includes("Eyelash") && !child.name.includes("Teeth")) avatarHeadMesh = child;
            }
        });
    }

    if (avatarHeadMesh && avatarHeadMesh.morphTargetDictionary) {
        const keys = Object.keys(avatarHeadMesh.morphTargetDictionary);
        console.log("🧠 Available Muscles:", keys); // Check console to see all available muscles!

        // 2. Find Mouth (Talking)
        const mouthKeyName = keys.find(k => k.toLowerCase() === 'jawopen') ||
            keys.find(k => k.toLowerCase() === 'mouthopen') ||
            keys.find(k => k.toLowerCase() === 'viseme_aa');
        if (mouthKeyName) {
            mouthKeyIndex = avatarHeadMesh.morphTargetDictionary[mouthKeyName];
            console.log(`🗣️ Mouth Linked to: ${mouthKeyName}`);
        }

        // 3. Find Eyes (Blinking)
        const blinkKeyName = keys.find(k => k.toLowerCase().includes('blink') ||
            k.toLowerCase().includes('eyeclose'));
        if (blinkKeyName) {
            blinkKeyIndex = avatarHeadMesh.morphTargetDictionary[blinkKeyName];
            console.log(`👁️ Blinking Linked to: ${blinkKeyName}`);
        }
    }

    // 4. Body Animation
    if (object.animations && object.animations.length > 0) {
        mixer = new THREE.AnimationMixer(avatar);
        const action = mixer.clipAction(object.animations[0]);
        action.play();
    }
}

function animate() {
    requestAnimationFrame(animate);
    const now = Date.now();

    // Update Body Animation
    if (mixer) mixer.update(0.016);

    if (avatarHeadMesh) {
        // --- 🗣️ PROCEDURAL TALKING ---
        if (mouthKeyIndex !== null) {
            if (isTalking) {
                // Change target every 150ms (simulating syllables)
                if (now - lastSpeechUpdate > speechSpeed) {
                    // Random number between 0.0 (closed) and 0.7 (open)
                    // We don't go to 1.0 often because real people don't scream constantly
                    speechTarget = Math.random() * 0.7;

                    // 20% chance to pause completely (end of word)
                    if (Math.random() > 0.8) speechTarget = 0;

                    lastSpeechUpdate = now;
                    // Randomize speed slightly for realism
                    speechSpeed = 100 + Math.random() * 150;
                }
            } else {
                speechTarget = 0; // Close mouth if not talking
            }

            // Smoothly move jaw to target
            const currentMouth = avatarHeadMesh.morphTargetInfluences[mouthKeyIndex];
            avatarHeadMesh.morphTargetInfluences[mouthKeyIndex] = THREE.MathUtils.lerp(currentMouth, speechTarget, 0.2);
        }

        // --- 👁️ PROCEDURAL BLINKING ---
        if (blinkKeyIndex !== null) {
            // Check if it's time to blink
            if (!isBlinking && now - lastBlinkTime > nextBlinkInterval) {
                isBlinking = true;
                blinkTarget = 1; // Close eyes
            }

            // If blinking, handle the close/open cycle
            if (isBlinking) {
                const currentBlink = avatarHeadMesh.morphTargetInfluences[blinkKeyIndex];

                // Move towards target (Snap shut fast, open slow)
                avatarHeadMesh.morphTargetInfluences[blinkKeyIndex] = THREE.MathUtils.lerp(currentBlink, blinkTarget, 0.3);

                // If eyes are fully closed, switch target to Open
                if (blinkTarget === 1 && currentBlink > 0.9) {
                    blinkTarget = 0;
                }
                // If eyes are back to open, reset timer
                if (blinkTarget === 0 && currentBlink < 0.1) {
                    isBlinking = false;
                    lastBlinkTime = now;
                    nextBlinkInterval = 2000 + Math.random() * 4000; // Blink every 2-6 seconds
                }
            }
        }
    }

    renderer.render(scene, camera);
}

// --- 🔗 EXTERNAL CONTROL FOR SYNC ---
window.avatarSpeak = function (audioElement) {
    if (!audioElement) return;

    // Start talking when audio plays
    isTalking = true;
    console.log("🗣️ Avatar started talking");

    // Stop talking when audio ends
    audioElement.onended = () => {
        isTalking = false;
        console.log("🤫 Avatar stopped talking");
    };

    // Also stop if paused manually
    audioElement.onpause = () => {
        isTalking = false;
    };

    // Resume if played again
    audioElement.onplay = () => {
        isTalking = true;
    };
};