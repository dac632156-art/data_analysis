import BrandMark from './BrandMark';

interface DataMindLogoProps {
  size?: number;
  shape?: 'circle' | 'rounded';
  className?: string;
}

/**
 * Sidebar / 各分析页左上角品牌 logo（圆角胶囊，蓝紫斜杠渐变）。
 */
export default function DataMindLogo({
  size = 32,
  shape = 'rounded',
  className,
}: DataMindLogoProps) {
  return <BrandMark size={size} shape={shape} className={className} />;
}
