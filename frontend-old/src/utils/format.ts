/* 通用格式化工具 */

/**
 * 将字节数格式化为易读字符串（B / KB / MB / GB / TB）。
 * @param bytes 字节数（number）
 * @param decimals 小数位，默认 2
 */
export function formatBytes(bytes: number, decimals = 2): string {
  if (bytes === null || bytes === undefined || Number.isNaN(bytes)) return '0 B';
  if (bytes <= 0) return '0 B';
  const k = 1024;
  const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), units.length - 1);
  const value = bytes / Math.pow(k, i);
  // 整数单位（B）不显示小数
  const fixed = i === 0 ? value.toString() : value.toFixed(decimals);
  return `${fixed} ${units[i]}`;
}
