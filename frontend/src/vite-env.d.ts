/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_GOOGLE_CLIENT_ID?: string
  /** File trong `public/`: `.glb` / `.gltf` hoặc `.fbx` (animation bake). Ví dụ `/models/rig_circle_walk.fbx` */
  readonly VITE_OWLBEAR_GLB_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
