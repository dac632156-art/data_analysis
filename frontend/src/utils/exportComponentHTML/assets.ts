/**
 * assets.ts —— 导出时内联的水彩纹理图（base64）。
 *
 * base64 由 scripts/gen-export-assets.mjs 生成到 assets.generated.ts
 * （vite ?inline 对 4MB/10MB 大图不一定内联，生成式保证单文件导出自包含）。
 * 本文件只做再导出，保持 import 路径稳定。
 */
export { BG_CARD, BG_SLICE } from './assets.generated';
