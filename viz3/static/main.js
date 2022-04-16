/*
 * Modifed from:
 * https://threejsfundamentals.org/threejs/lessons/threejs-load-obj.html
 *
 * Known Bugs:
 *   - World is inverted
 *   - Resizing the window doesn't resize the canvas
 *   - Text when hovering is positioned at the center bounds of assocated mesh,
 *     instead of where the mouse was hovered at (unlike in Panda3D)
 */
import * as three from 'https://threejsfundamentals.org/threejs/resources/threejs/r127/build/three.module.js';
import * as orbit from 'https://threejsfundamentals.org/threejs/resources/threejs/r127/examples/jsm/controls/OrbitControls.js';
import * as renderer from 'https://threejsfundamentals.org/threejs/resources/threejs/r127/examples/jsm/renderers/CSS2DRenderer.js';

const EventType = {
    Add: 0,
    Remove: 1,
    Move: 2,
    Resize: 3,
    Recolor: 4,
    Retext: 5
};

function objectNameFromPath(path) {
    return "_" + path;
}

function createThreeJSMesh(geometry, name) {
    // See https://threejsfundamentals.org/threejs/lessons/threejs-custom-geometry.html
    // and https://stackoverflow.com/questions/9252764/how-to-create-a-custom-mesh-on-three-js
    // and https://github.com/mrdoob/three.js/blob/master/examples/webgl_buffergeometry.html
    // and https://threejsfundamentals.org/threejs/lessons/threejs-custom-buffergeometry.html
    let threeGeometry = new three.BufferGeometry();

    // Unlike in viz3, Three.js does not store vertexes with triangles indexing
    // into those, but rather just the vertexes of a face
    const positions = [];
    for (let t = 0; t < geometry.triangles.length; t++) {
        for (let ti = 0; ti < geometry.triangles[t].length; ti++) {
            let v = geometry.triangles[t][ti];
            let vertex = geometry.vertexes[v];
            positions.push(new three.Vector3(
                vertex.x,
                vertex.y,
                vertex.z
            ));
        }
    }
    threeGeometry.setFromPoints(positions);

    threeGeometry.computeBoundingSphere();  // Required for proper opacity calculations

    const material = new three.MeshBasicMaterial({
        color: createThreeJSColor(geometry.color),
        // three.Color() from createThreeJSColor() doesn't store opacity
        opacity: geometry.color.a / 255,
        transparent: true,  // for opaque objects
    });
    const mesh = new three.Mesh(threeGeometry, material);
    mesh.castShadow = true;
    material.side = three.DoubleSide;  // for opaque objects

    mesh.position.set(geometry.pos.x, geometry.pos.y, geometry.pos.z);
    mesh.name = name;
    return mesh;
}

function createThreeJSColor(color) {
    return new three.Color(color.r / 255.0, color.g / 255.0, color.b / 255.0);
}

function resizeRendererIfNeeded(renderer) {
    // The canvas is 100% by 100%, and three.js needs to rethink things if
    // the size changes
    const canvas = renderer.domElement;
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    const needResize = canvas.width !== width || canvas.height !== height;
    if (needResize) {
        renderer.setSize(width, height, false);
    }

    return needResize;
}

function createLabelRenderer() {
    const {
        innerWidth,
        innerHeight
    } = window;

    const labelRenderer = new renderer.CSS2DRenderer();
    labelRenderer.setSize(innerWidth, innerHeight);
    labelRenderer.domElement.style.position = 'absolute';
    labelRenderer.domElement.style.top = '0px';
    labelRenderer.domElement.style.pointerEvents = 'none';
    document.body.appendChild(labelRenderer.domElement);

    return labelRenderer;
}

function labelObjectNameFromParent(parentName) {
    return parentName + "_label";
}

function createLabel(text, parentName) {
    const labelDiv = document.createElement('div');
    labelDiv.textContent = text;
    labelDiv.className = 'label';
    labelDiv.style.marginTop = '-1em';

    const labelObj = new renderer.CSS2DObject(labelDiv);
    labelObj.visible = false;
    labelObj.name = labelObjectNameFromParent(parentName);
    return labelObj;
}

function createCamera() {
    // Saw these numbers somewhere, and then copied them. Don't think too hard
    // about them.
    const fov = 50;
    const aspect = 2; // the canvas default
    const near = 0.1;
    const far = 5000;

    let camera = new three.PerspectiveCamera(fov, aspect, near, far);
    camera.position.set(0, 100, 200);
    return camera;
}

function createControls(canvas, camera) {
    let controls = new orbit.OrbitControls(camera, canvas);
    controls.target.set(0, 5, 0);  // starting position
    controls.update();
    return controls;
}

function configureLighting(scene) {
    // Add basic bright top-down lighting
    const light = new three.DirectionalLight(0xffffff);
    light.position.set(0, 1000, 1000);
    scene.add(light);
}

function main() {
    const canvas = document.querySelector('#c');
    const renderer = new three.WebGLRenderer({
        canvas,
        alpha: true,  // whether canvas contains a alpha (transparency) buffer
        antiAlias: true,  // helps make small, but detailed objects, look better
    });
    renderer.setPixelRatio(window.devicePixelRatio);

    const camera = createCamera();
    const controls = createControls(canvas, camera);
    const scene = new three.Scene();
    scene.background = new three.Color('white');
    configureLighting(scene);

    // Used for on-hover text
    const labelRenderer = createLabelRenderer();
    const raycaster = new three.Raycaster();
    const mouse = new three.Vector2();
    const objLabelsFromParentName = new Map();

    // FIXME: Figure out if JS has RAII or at least rewrite with JS' objects,
    //        since this is a poor mans object...
    function addObjLabel(geometry, parentName) {
        let labelObj = createLabel(geometry.text, parentName);
        scene.add(labelObj);

        objLabelsFromParentName.set(parentName, labelObj);
    }
    function addObj(geometry, name) {
        let targetObj = createThreeJSMesh(geometry, name)
        scene.add(targetObj);

        // Not all geometries given will have associated text, be lazy
        if (geometry.text !== "")
            addObjLabel(geometry, name);
    }
    function removeObjLabel(parentName) {
        let labelObj = objLabelsFromParentName.get(parentName);
        scene.remove(labelObj);

        objLabelsFromParentName.delete(parentName);
    }
    function removeObj(name) {
        let targetObj = scene.getObjectByName(name);
        targetObj.geometry.dispose();  // Geometries are cached inside the renderer
        scene.remove(targetObj);

        removeObjLabel(name);
    }
    function moveObj(geometry, name) {
        let targetObj = scene.getObjectByName(name);
        targetObj.position.set(geometry.pos.x, geometry.pos.y, geometry.pos.z);
    }
    function recolorObj(geometry, name) {
        let color = createThreeJSColor(geometry.color);

        let targetObj = scene.getObjectByName(name);
        for (let i = 0; i < targetObj.children.length; i++) {
            let childObj = targetObj.children[i];

            childObj.material.opacity.set(geometry.color.a / 255);
            childObj.material.color.set(color);
            childObj.material.uniforms.needsUpdate = true;  // mark opacity change
        }
    }
    function retextObj(geometry, parentName) {
        if (!objLabelsFromParentName.has(parentName))
            addObjLabel(geometry, parentName);

        let labelObj = objLabelsFromParentName.get(parentName);
        labelObj.element.textContent = geometry.text;
    }

    const eventSource = new EventSource("/events")
    eventSource.onmessage = function(event) {
        const eventData = JSON.parse(event.data);
        const path = eventData.path;
        const eventType = eventData.event_type;
        const geometry = eventData.geometry;

        // TODO: Make an event filter parameter on the /events endpoint so we
        //       don't have to have this
        if (!geometry.should_draw)
            return;

        let targetName = objectNameFromPath(path);
        switch (eventType) {
            case EventType.Add:
                addObj(geometry, targetName);
                break;

            case EventType.Remove:
                removeObj(targetName);
                break;

            case EventType.Move:
                moveObj(geometry, targetName)
                break;

            case EventType.Resize:
                // FIXME! Inefficient; hack!
                removeObj(targetName);
                addObj(geometry, targetName);
                break;

            case EventType.Recolor:
                recolorObj(geometry, targetName);
                break;

            case EventType.Retext:
                retextObj(geometry, targetName);
                break;
        }
    }

    let lastIntersectedParentName = null;
    function render() {
        // Must be called to specify this should be called on next frame
        window.requestAnimationFrame(render);

        if (resizeRendererIfNeeded(renderer)) {
            camera.aspect = canvas.clientWidth / canvas.clientHeight;
            camera.updateProjectionMatrix();
        }

        // Check for text hovering
        raycaster.setFromCamera(mouse, camera);

        // See https://threejs.org/docs/#api/en/core/Raycaster.intersectObjects
        const intersections = raycaster.intersectObjects(scene.children);
        let parentName = null;
        let foundIntersectionWithText = false;

        // We'll end up with multiple intersections, but we really only care
        // about the frontmost one with an associated label/text
        for (let i = 0; i < intersections.length; i++) {
            const intersectedObj = intersections[i].object;
            parentName = intersectedObj.name;

            if (objLabelsFromParentName.has(parentName)) {
                // We do this regardless of whether the last intersected object
                // was this one, since a event may have happened that moved
                // the mesh
                const labelObj = objLabelsFromParentName.get(parentName);
                labelObj.visible = true;

                const lengths = new three.Vector3();
                new three.Box3().setFromObject(intersectedObj).getSize(lengths);
                labelObj.position.set(
                    intersectedObj.position.x,
                    intersectedObj.position.y + lengths.y / 2,
                    intersectedObj.position.z
                );
                foundIntersectionWithText = true;
                break;
            }
        }
        if (lastIntersectedParentName !== null && lastIntersectedParentName !== parentName && objLabelsFromParentName.has(lastIntersectedParentName))
            objLabelsFromParentName.get(lastIntersectedParentName).visible = false;

        if (foundIntersectionWithText)
            lastIntersectedParentName = parentName;

        renderer.render(scene, camera);
        labelRenderer.render(scene, camera);
    }

    function onMouseMove(event) {
        const {
            innerWidth,
            innerHeight
        } = window;

        // Calculate mouse position in normalized device coordinates
        // (-1 to +1 for both components)
        mouse.x = (event.clientX / innerWidth) * 2 - 1;
        mouse.y = -(event.clientY / innerHeight) * 2 + 1;
    }

    window.addEventListener('mousemove', onMouseMove);
    render();
}

main();
